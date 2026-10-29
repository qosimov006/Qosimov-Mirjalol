"""Ma'lumotlarni saqlash qatlami.

Ilova ma'lumotlarni xotirada (dict) ushlaydi, bu modul esa ularni doimiy saqlaydi:

  json      - bitta JSON fayl (lokal ishlab chiqish, standart)
  postgres  - PostgreSQL (AWS'da: Amazon RDS)  <- bulut uchun
  sqlite    - SQLite fayl (faqat test / sinov uchun, xuddi shu SQL kodi)

Postgres rejimida ilova (EC2) va ma'lumotlar bazasi (RDS) alohida xizmatlar bo'lib ishlaydi.
Yozishda faqat O'ZGARGAN qatorlar yangilanadi (INSERT .. ON CONFLICT DO UPDATE).
"""
import json
import os
import shutil
import threading
from datetime import datetime

SCALAR_KEYS = ("next_user", "next_order", "dict_version")
DOC_KEYS = ("settings", "dict", "audit", "collections", "shifts", "complaints", "trips", "blacklist", "packaging_sales")          # kv jadvalida JSON hujjat sifatida saqlanadi


def _dump(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# ----------------------------------------------------------------------------- JSON fayl
class JsonFileStore:
    kind = "json"

    def __init__(self, path):
        self.path = path

    def load(self):
        if not os.path.exists(self.path):
            return None
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def save(self, db):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def backup(self):
        if os.path.exists(self.path):
            d = os.path.join(os.path.dirname(self.path), "backup")
            os.makedirs(d, exist_ok=True)
            shutil.copy(self.path, os.path.join(d, "db-%s.json" % datetime.now().strftime("%Y%m%d")))
            for old in sorted(os.listdir(d))[:-14]:
                os.remove(os.path.join(d, old))

    def ping(self):
        return True

    def info(self):
        return {"kind": self.kind, "path": self.path}


# ----------------------------------------------------------------------------- SQL (PostgreSQL / SQLite)
class SqlStore:
    def __init__(self, dialect, connect, label=""):
        assert dialect in ("postgres", "sqlite")
        self.dialect, self.kind, self._connect, self.label = dialect, dialect, connect, label
        self._conn = None
        self._cache = {}
        self._lock = threading.RLock()

    # -- yordamchi
    @property
    def _pg(self):
        return self.dialect == "postgres"

    def _q(self, sql):
        """'?' belgilarini dialektga moslaydi, JSON ustunlari uchun {J} ni almashtiradi."""
        sql = sql.replace("{J}", "JSONB" if self._pg else "TEXT")
        sql = sql.replace("{JP}", "CAST(? AS JSONB)" if self._pg else "?")
        return sql.replace("?", "%s") if self._pg else sql

    def _conn_get(self):
        if self._conn is None:
            self._conn = self._connect()
        return self._conn

    def _reset(self):
        try:
            if self._conn is not None:
                self._conn.close()
        except Exception:
            pass
        self._conn = None

    def _run(self, fn):
        """Ulanish uzilsa (RDS qayta ishga tushsa, bo'sh turib yopilsa) bir marta qayta ulanadi."""
        with self._lock:
            for attempt in (1, 2):
                try:
                    return fn(self._conn_get())
                except Exception as e:
                    name = type(e).__name__
                    try:
                        self._conn.rollback()
                    except Exception:
                        pass
                    if attempt == 1 and name in ("OperationalError", "InterfaceError", "ProgrammingError") and self._pg:
                        self._reset()
                        continue
                    raise

    SCHEMA = (
        "CREATE TABLE IF NOT EXISTS kv (k VARCHAR(64) PRIMARY KEY, data {J} NOT NULL)",
        "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username VARCHAR(64) NOT NULL UNIQUE, data {J} NOT NULL)",
        "CREATE TABLE IF NOT EXISTS customers (phone VARCHAR(20) PRIMARY KEY, data {J} NOT NULL)",
        "CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, code VARCHAR(20) NOT NULL UNIQUE, "
        "status VARCHAR(32) NOT NULL, created VARCHAR(16) NOT NULL, data {J} NOT NULL)",
        "CREATE INDEX IF NOT EXISTS orders_status_idx ON orders (status)",
    )
    UPSERT = {
        "kv": "INSERT INTO kv (k, data) VALUES (?, {JP}) ON CONFLICT (k) DO UPDATE SET data = EXCLUDED.data",
        "users": "INSERT INTO users (id, username, data) VALUES (?, ?, {JP}) ON CONFLICT (id) DO UPDATE SET username = EXCLUDED.username, data = EXCLUDED.data",
        "customers": "INSERT INTO customers (phone, data) VALUES (?, {JP}) ON CONFLICT (phone) DO UPDATE SET data = EXCLUDED.data",
        "orders": "INSERT INTO orders (id, code, status, created, data) VALUES (?, ?, ?, ?, {JP}) "
                  "ON CONFLICT (id) DO UPDATE SET code = EXCLUDED.code, status = EXCLUDED.status, created = EXCLUDED.created, data = EXCLUDED.data",
    }
    DELETE = {"kv": "DELETE FROM kv WHERE k = ?", "users": "DELETE FROM users WHERE id = ?",
              "customers": "DELETE FROM customers WHERE phone = ?", "orders": "DELETE FROM orders WHERE id = ?"}

    def _rows(self, db):
        """db (dict) -> {(jadval, kalit): (parametrlar, json_matn)}"""
        r = {}
        for k in SCALAR_KEYS + DOC_KEYS:
            if k in db:
                j = _dump(db[k])
                r[("kv", k)] = ((k, j), j)
        for u in db["users"]:
            j = _dump(u)
            r[("users", u["id"])] = ((u["id"], u["username"], j), j)
        for phone, c in db["customers"].items():
            j = _dump(c)
            r[("customers", phone)] = ((phone, j), j)
        for o in db["orders"]:
            j = _dump(o)
            r[("orders", o["id"])] = ((o["id"], o["code"], o["status"], o["created"], j), j)
        return r

    # -- ochiq API
    def load(self):
        def work(conn):
            cur = conn.cursor()
            for stmt in self.SCHEMA:
                cur.execute(self._q(stmt))
            conn.commit()
            cur.execute(self._q("SELECT k, data FROM kv"))
            kv = {k: (json.loads(v) if isinstance(v, str) else v) for k, v in cur.fetchall()}
            if "next_order" not in kv:
                return None                                  # bo'sh baza: ilova boshlang'ich ma'lumotni yaratadi
            db = dict(kv)
            for table, key in (("users", "id"), ("orders", "id")):
                cur.execute(self._q("SELECT data FROM %s ORDER BY id" % table))
                db[table] = [json.loads(v) if isinstance(v, str) else v for (v,) in cur.fetchall()]
            cur.execute(self._q("SELECT phone, data FROM customers"))
            db["customers"] = {p: (json.loads(v) if isinstance(v, str) else v) for p, v in cur.fetchall()}
            return db
        db = self._run(work)
        if db is not None:
            self._cache = {k: v[1] for k, v in self._rows(db).items()}
        return db

    def save(self, db):
        rows = self._rows(db)

        def work(conn):
            cur = conn.cursor()
            changed = [k for k, v in rows.items() if self._cache.get(k) != v[1]]
            gone = [k for k in self._cache if k not in rows]
            for k in gone:
                cur.execute(self._q(self.DELETE[k[0]]), (k[1],))
            for k in changed:
                cur.execute(self._q(self.UPSERT[k[0]]), rows[k][0])
            conn.commit()
            return len(changed), len(gone)
        result = self._run(work)
        self._cache = {k: v[1] for k, v in rows.items()}
        return result

    def backup(self):
        pass        # RDS avtomatik zaxira nusxalarini o'zi yuritadi

    def ping(self):
        def work(conn):
            cur = conn.cursor()
            cur.execute("SELECT 1")
            return cur.fetchone()[0] == 1
        return self._run(work)

    def roundtrip(self, marker):
        """Haqiqiy yozish-o'qish-o'chirish sinovi (kv jadvalida)."""
        key = "selftest"

        def work(conn):
            cur = conn.cursor()
            cur.execute(self._q(self.UPSERT["kv"]), (key, _dump({"marker": marker})))
            conn.commit()
            cur.execute(self._q("SELECT data FROM kv WHERE k = ?"), (key,))
            v = cur.fetchone()[0]
            v = json.loads(v) if isinstance(v, str) else v
            cur.execute(self._q(self.DELETE["kv"]), (key,))
            conn.commit()
            return v.get("marker") == marker
        return self._run(work)

    def info(self):
        def work(conn):
            cur = conn.cursor()
            cur.execute("SELECT version()" if self._pg else "SELECT 'SQLite ' || sqlite_version()")
            version = cur.fetchone()[0]
            counts = {}
            for t in ("users", "customers", "orders"):
                cur.execute("SELECT COUNT(*) FROM " + t)
                counts[t] = cur.fetchone()[0]
            return {"kind": self.kind, "target": self.label, "version": version, "rows": counts}
        return self._run(work)


# ----------------------------------------------------------------------------- yaratish
def make_store(cfg):
    """cfg: cloud.Config. BTS_STORAGE = json | postgres | sqlite"""
    kind = cfg.storage
    if kind == "json":
        return JsonFileStore(cfg.json_path)
    if kind == "sqlite":
        import sqlite3
        path = cfg.sqlite_path

        def connect():
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            return sqlite3.connect(path, check_same_thread=False)
        return SqlStore("sqlite", connect, label=path)
    if kind == "postgres":
        c = cfg.db_credentials()

        def connect():
            import psycopg2                                   # pip install psycopg2-binary
            conn = psycopg2.connect(host=c["host"], port=c["port"], dbname=c["dbname"], user=c["user"], password=c["password"],
                                    sslmode=cfg.db_sslmode, connect_timeout=10, application_name="bts-express")
            return conn
        return SqlStore("postgres", connect, label="%s:%s/%s" % (c["host"], c["port"], c["dbname"]))
    raise SystemExit("Noma'lum BTS_STORAGE: %s (json | postgres | sqlite)" % kind)
