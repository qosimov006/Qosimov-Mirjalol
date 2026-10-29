"""SINOV UCHUN soxta 'psycopg2': so'rovlarni haqiqiy PostgreSQL serveriga `psql` orqali yuboradi.
Maqsad - SQL dialektini (JSONB, ON CONFLICT ...) haqiqiy PostgreSQL'da tekshirish. Ishlab chiqarishda emas, haqiqiy psycopg2 ishlatiladi."""
import os
import subprocess


class OperationalError(Exception):
    pass


def _lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


class Cursor:
    def __init__(self):
        self.rows = []

    def execute(self, sql, params=()):
        parts = sql.split("%s")
        assert len(parts) == len(params) + 1, (sql, params)
        full = parts[0] + "".join(_lit(p) + parts[i + 1] for i, p in enumerate(params))
        cmd = ["psql", "-X", "-q", "-At", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-h", os.environ["PGSHIM_SOCKET"], "-U", "postgres", "-d", os.environ.get("PGSHIM_DB", "bts"), "-c", full]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(r.stderr.strip())
        self.rows = [tuple(line.split("\t")) for line in r.stdout.splitlines()] if "SELECT" in full.upper()[:8] or "RETURNING" in full.upper() else []
        # INSERT/DELETE/CREATE chiqishi ("INSERT 0 1") -q bilan ko'rsatilmaydi

    def fetchall(self):
        return [tuple(int(x) if x.isdigit() else x for x in r) if len(r) == 1 else r for r in self.rows]

    def fetchone(self):
        r = self.fetchall()
        return r[0] if r else None


class Conn:
    def cursor(self): return Cursor()
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass


def connect(**kw):
    assert kw.get("sslmode") == "require", "sslmode=require bo'lishi kerak"
    return Conn()
