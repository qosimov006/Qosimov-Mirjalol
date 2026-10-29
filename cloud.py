"""Bulut sozlamalari va xizmatlari (AWS).

Hamma sozlama MUHIT O'ZGARUVCHILARIDAN o'qiladi - kodda parol, kalit yoki manzil YO'Q.

  BTS_STORAGE     json (standart) | postgres | sqlite
  DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD     - RDS ulanishi (parol o'rniga DB_SECRET_ID tavsiya etiladi)
  DB_SECRET_ID    - AWS Secrets Manager'dagi sir nomi (JSON: username, password, host, port, dbname)
  DB_SSLMODE      - standart "require" (RDS bilan trafik shifrlanadi)
  S3_BUCKET       - bo'sh bo'lsa fayllar lokal papkada saqlanadi, to'ldirilsa Amazon S3'da
  S3_PREFIX       - standart "bts/"
  AWS_REGION      - masalan eu-central-1
  CW_NAMESPACE    - to'ldirilsa maxsus metrikalar CloudWatch'ga yuboriladi
  TRUST_PROXY     - 1 bo'lsa nginx qo'ygan X-Forwarded-For'dagi mijoz IP'si ishlatiladi
  BTS_ADMIN_PASSWORD / ADMIN_SECRET_ID - birinchi ishga tushirishda admin paroli (bulutda MAJBURIY; sir JSON: {"password": "..."})
  BTS_SEED_DEMO   - 1 bo'lsa demo operator/kuryer ham yaratiladi (faqat sinov uchun; json rejimida standart)
  BTS_SECRET_KEY  - lokal fayl havolalarini imzolash kaliti (bo'sh bo'lsa har ishga tushirishda yangi yaratiladi)

AWS kalitlari (access key) HECH QACHON yozilmaydi: EC2'ga biriktirilgan IAM rol (instance profile) orqali boto3 o'zi oladi.
boto3 va psycopg2 faqat kerak bo'lganda import qilinadi, shuning uchun lokal ishga tushirish ularsiz ham ishlaydi.
"""
import hashlib
import hmac
import json
import os
import queue
import secrets
import sys
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote

BASE = os.path.dirname(os.path.abspath(__file__))


def env(name, default=""):
    return os.environ.get(name, default).strip()


class Config:
    def __init__(self):
        self.storage = env("BTS_STORAGE", "json").lower()
        self.json_path = env("BTS_DB", os.path.join(BASE, "data", "db.json"))
        self.sqlite_path = env("BTS_SQLITE", os.path.join(BASE, "data", "db.sqlite3"))
        self.db_sslmode = env("DB_SSLMODE", "require")
        self.region = env("AWS_REGION") or env("AWS_DEFAULT_REGION") or None
        self.s3_bucket = env("S3_BUCKET")
        self.s3_prefix = env("S3_PREFIX", "bts/")
        if self.s3_prefix and not self.s3_prefix.endswith("/"):
            self.s3_prefix += "/"
        self.cw_namespace = env("CW_NAMESPACE")
        self.trust_proxy = env("TRUST_PROXY") in ("1", "true", "yes")
        self.local_files = env("BTS_FILES", os.path.join(BASE, "data", "files"))
        self.secret_key = env("BTS_SECRET_KEY") or secrets.token_hex(32)

    def boto(self, service):
        import boto3                                    # pip install boto3 (faqat bulut rejimida)
        return boto3.client(service, region_name=self.region)

    def admin_password(self):
        """Admin parolini muhitdan yoki Secrets Manager'dan oladi (kodda parol yo'q)."""
        pw = env("BTS_ADMIN_PASSWORD")
        sid = env("ADMIN_SECRET_ID")
        if not pw and sid:
            raw = self.boto("secretsmanager").get_secret_value(SecretId=sid)["SecretString"]
            try:
                pw = json.loads(raw).get("password", "")
            except ValueError:
                pw = raw
        return pw

    def db_credentials(self):
        """Parol Secrets Manager'dan (tavsiya) yoki muhit o'zgaruvchisidan olinadi."""
        sid = env("DB_SECRET_ID")
        c = {"host": env("DB_HOST"), "port": int(env("DB_PORT", "5432")), "dbname": env("DB_NAME", "bts"),
             "user": env("DB_USER"), "password": env("DB_PASSWORD")}
        if sid:
            raw = self.boto("secretsmanager").get_secret_value(SecretId=sid)["SecretString"]
            s = json.loads(raw)
            c["user"] = s.get("username", c["user"])
            c["password"] = s.get("password", c["password"])
            c["host"] = s.get("host") or c["host"]
            c["port"] = int(s.get("port") or c["port"])
            c["dbname"] = s.get("dbname") or c["dbname"]
        missing = [k for k in ("host", "user", "password") if not c[k]]
        if missing:
            raise SystemExit("Postgres rejimi uchun sozlama yetishmaydi: %s (DB_HOST, DB_USER, DB_PASSWORD yoki DB_SECRET_ID)" % ", ".join(missing))
        return c


# ----------------------------------------------------------------------------- obyektli saqlash
class ObjectError(Exception):
    pass


class S3Store:
    kind = "s3"

    def __init__(self, cfg):
        self.cfg, self.bucket, self.prefix = cfg, cfg.s3_bucket, cfg.s3_prefix
        self._c = None

    @property
    def c(self):
        if self._c is None:
            self._c = self.cfg.boto("s3")
        return self._c

    def _k(self, key):
        return self.prefix + key

    def put(self, key, data, content_type="application/octet-stream", filename=None):
        extra = {"Bucket": self.bucket, "Key": self._k(key), "Body": data, "ContentType": content_type,
                 "ServerSideEncryption": "AES256"}                       # saqlashda shifrlash
        self.c.put_object(**extra)

    def get(self, key):
        r = self.c.get_object(Bucket=self.bucket, Key=self._k(key))
        return r["Body"].read(), r.get("ContentType", "application/octet-stream")

    def delete(self, key):
        self.c.delete_object(Bucket=self.bucket, Key=self._k(key))

    def list(self, prefix=""):
        out, token = [], None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": self._k(prefix)}
            if token:
                kw["ContinuationToken"] = token
            r = self.c.list_objects_v2(**kw)
            for o in r.get("Contents", []):
                out.append({"key": o["Key"][len(self.prefix):], "size": o["Size"], "modified": o["LastModified"].strftime("%Y-%m-%d %H:%M")})
            if not r.get("IsTruncated"):
                return out
            token = r["NextContinuationToken"]

    def url(self, key, filename=None, expires=300):
        """Vaqtinchalik (presigned) havola: bucket yopiq qoladi, havola 5 daqiqada eskiradi."""
        params = {"Bucket": self.bucket, "Key": self._k(key)}
        if filename:
            params["ResponseContentDisposition"] = 'attachment; filename="%s"' % quote(filename)
        return self.c.generate_presigned_url("get_object", Params=params, ExpiresIn=expires)

    def info(self):
        return {"kind": "s3", "target": "s3://%s/%s" % (self.bucket, self.prefix)}


class LocalStore:
    """S3 o'rniga lokal papka (ishlab chiqish). Havolalar HMAC bilan imzolanadi."""
    kind = "local"

    def __init__(self, cfg):
        self.root, self.secret = cfg.local_files, cfg.secret_key.encode()
        os.makedirs(self.root, exist_ok=True)

    def _p(self, key):
        p = os.path.normpath(os.path.join(self.root, key))
        if not p.startswith(os.path.normpath(self.root) + os.sep):
            raise ObjectError("Noto'g'ri kalit")
        return p

    def put(self, key, data, content_type="application/octet-stream", filename=None):
        p = self._p(key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        with open(p + ".ctype", "w") as f:
            f.write(content_type)

    def get(self, key):
        p = self._p(key)
        if not os.path.isfile(p):
            raise ObjectError("Fayl topilmadi")
        ct = "application/octet-stream"
        if os.path.exists(p + ".ctype"):
            ct = open(p + ".ctype").read().strip() or ct
        with open(p, "rb") as f:
            return f.read(), ct

    def delete(self, key):
        p = self._p(key)
        for x in (p, p + ".ctype"):
            if os.path.exists(x):
                os.remove(x)

    def list(self, prefix=""):
        out = []
        for d, _, files in os.walk(self.root):
            for fn in files:
                if fn.endswith(".ctype"):
                    continue
                full = os.path.join(d, fn)
                key = os.path.relpath(full, self.root).replace(os.sep, "/")
                if key.startswith(prefix):
                    st = os.stat(full)
                    out.append({"key": key, "size": st.st_size, "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")})
        return sorted(out, key=lambda x: x["key"])

    def sign(self, key, exp):
        return hmac.new(self.secret, ("%s|%d" % (key, exp)).encode(), hashlib.sha256).hexdigest()

    def verify(self, key, exp, sig):
        try:
            return int(exp) > time.time() and hmac.compare_digest(self.sign(key, int(exp)), sig)
        except (ValueError, TypeError):
            return False

    def url(self, key, filename=None, expires=300):
        exp = int(time.time()) + expires
        u = "/files/%s?exp=%d&sig=%s" % (quote(key), exp, self.sign(key, exp))
        return u + ("&name=" + quote(filename) if filename else "")

    def info(self):
        return {"kind": "local", "target": self.root}


def make_object_store(cfg):
    return S3Store(cfg) if cfg.s3_bucket else LocalStore(cfg)


# ----------------------------------------------------------------------------- monitoring
def log_json(event, **fields):
    """Bitta qatorli JSON log (stdout -> systemd journal -> CloudWatch Logs)."""
    rec = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "event": event}
    rec.update(fields)
    sys.stdout.write(json.dumps(rec, ensure_ascii=False) + "\n")
    sys.stdout.flush()


class Metrics:
    """Hisoblagichlar xotirada yig'iladi; CW_NAMESPACE berilsa har 60 soniyada CloudWatch'ga yuboriladi."""
    NAMES = ("Requests", "Errors5xx", "OrdersCreated", "LoginFailed", "FilesUploaded")

    def __init__(self, cfg):
        self.cfg = cfg
        self.counts = {n: 0 for n in self.NAMES}
        self.started = time.time()
        self.lock = threading.Lock()
        self.last_error = None
        self.last_push = None
        self._cw = None
        if cfg.cw_namespace:
            threading.Thread(target=self._loop, daemon=True, name="cw-metrics").start()

    def inc(self, name, n=1):
        with self.lock:
            self.counts[name] = self.counts.get(name, 0) + n

    def snapshot(self):
        with self.lock:
            return dict(self.counts)

    def _push(self, delta):
        if self._cw is None:
            self._cw = self.cfg.boto("cloudwatch")
        data = [{"MetricName": k, "Value": float(v), "Unit": "Count"} for k, v in delta.items() if v]
        if data:
            self._cw.put_metric_data(Namespace=self.cfg.cw_namespace, MetricData=data)

    def _loop(self):
        sent = {n: 0 for n in self.NAMES}
        while True:
            time.sleep(60)
            cur = self.snapshot()
            delta = {k: cur[k] - sent.get(k, 0) for k in cur}
            try:
                self._push(delta)
                sent = cur
                self.last_push = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.last_error = None
            except Exception as e:                       # monitoring ilovani to'xtatmasligi kerak
                self.last_error = "%s: %s" % (type(e).__name__, e)
                log_json("metrics_error", error=self.last_error)

    def selftest(self):
        """Bitta maxsus metrikani darhol yuboradi (CloudWatch -> Metrics -> BTSExpress da ko'rinadi)."""
        if not self.cfg.cw_namespace:
            return {"ok": None, "detail": "CW_NAMESPACE sozlanmagan - metrikalar yuborilmaydi (faqat bulutda yoqiladi)"}
        try:
            if self._cw is None:
                self._cw = self.cfg.boto("cloudwatch")
            self._cw.put_metric_data(Namespace=self.cfg.cw_namespace, MetricData=[{"MetricName": "SelfTest", "Value": 1.0, "Unit": "Count"}])
            return {"ok": True, "detail": "SelfTest metrikasi %s namespace'ga yuborildi" % self.cfg.cw_namespace}
        except Exception as e:
            return {"ok": False, "detail": "%s: %s" % (type(e).__name__, e)}
