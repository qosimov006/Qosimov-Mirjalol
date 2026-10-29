"""Bulut qatlami testlari: python3 tests/test_cloud.py

A) SQLite + lokal fayllar          (BTS_STORAGE=sqlite)
B) PostgreSQL + S3 + CloudWatch     (haqiqiy PostgreSQL serveri `psql` orqali, boto3 esa SOXTA - tests/fakes)
B qismi uchun PGSHIM_SOCKET (PostgreSQL unix-socket papkasi, 'bts' bazasi) kerak; bo'lmasa o'tkazib yuboriladi.
Haqiqiy AWS (RDS/S3/CloudWatch) bu testlarda ISHLATILMAYDI - u uchun deploy/ dagi ko'rsatmalarga qarang.
"""
import base64, json, os, subprocess, sys, tempfile, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKES = os.path.join(ROOT, "tests", "fakes")
fails = []
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def check(name, cond, extra=""):
    print(("OK   " if cond else "FAIL ") + name + (("  -> " + str(extra)) if not cond and extra else ""))
    if not cond:
        fails.append(name)


class Srv:
    def __init__(self, port, **env):
        self.port = port
        e = dict(os.environ, PORT=str(port), **env)
        self.p = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py")], env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for _ in range(50):
            try:
                urllib.request.urlopen("http://localhost:%d/api/health" % port, timeout=1)
                break
            except urllib.error.HTTPError:
                break
            except Exception:
                time.sleep(0.2)

    def call(self, method, path, body=None, tok=None, raw=False):
        req = urllib.request.Request("http://localhost:%d%s" % (self.port, path), method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + tok} if tok else {})})
        try:
            r = urllib.request.urlopen(req)
            b = r.read()
            return r.status, (b if raw else json.loads(b or b"{}"))
        except urllib.error.HTTPError as ex:
            b = ex.read()
            return ex.code, (b if raw else json.loads(b or b"{}"))

    def login(self, u, p):
        return self.call("POST", "/api/login", {"username": u, "password": p})[1].get("token")

    def stop(self):
        self.p.terminate()
        out = self.p.communicate(timeout=5)[0]
        return out


ORDER = {"sender_name": "Ali", "sender_phone": "90 123 45 67", "receiver_name": "Vali", "receiver_phone": "+998 91 765 43 21",
         "address": "Toshkent", "product": "Kitob", "weight": "1.5", "price": "25000", "payer": "Qabul qiluvchi"}


def full_flow(s, label, s3):
    A, O, K = s.login("admin", "admin123"), s.login("operator", "operator123"), s.login("kuryer1", "kuryer123")
    st, h = s.call("GET", "/api/health")
    check(label + ": health 200", st == 200 and h["status"] == "ok" and h["database"] == "up", h)
    st, o = s.call("POST", "/api/orders", dict(ORDER, courier_id=3), O)
    check(label + ": buyurtma yaratildi", st == 201, o)
    oid = o["id"]
    check(label + ": yo'l varaqasi obyektli saqlashga yozildi", o.get("waybill_key") == "waybills/%s.html" % o["code"], o)
    st, w = s.call("GET", "/api/orders/waybill?code=" + o["code"], tok=O)
    check(label + ": yo'l varaqasi havolasi", st == 200 and "url" in w, w)

    b64 = lambda b: base64.b64encode(b).decode()
    st, r = s.call("POST", "/api/orders/%d/files" % oid, {"name": "isbot rasmi.png", "type": "image/png", "data": b64(PNG), "kind": "proof"}, K)
    check(label + ": kuryer isbot rasmini yukladi", st == 201 and r["files"][0]["kind"] == "Yetkazish isboti", r)
    key = r["files"][0]["key"]
    st, u = s.call("GET", "/api/orders/%d/files/0" % oid, tok=O)
    check(label + ": fayl havolasi (5 daqiqalik)", st == 200 and u["expires_s"] == 300, u)
    if s3:
        check(label + ": havola S3 presigned", u["url"].startswith("https://bts-test-bucket.s3.amazonaws.com/bts/orders/"), u)
        check(label + ": fayl S3 papkasida", os.path.exists(os.path.join(os.environ["FAKE_AWS"], "s3", "bts-test-bucket", "bts", key)))
    else:
        st, body = s.call("GET", u["url"], raw=True)
        check(label + ": imzolangan havola faylni beradi", st == 200 and body == PNG)
        st, _ = s.call("GET", u["url"].split("&sig=")[0] + "&sig=00", raw=True)
        check(label + ": noto'g'ri imzo 403", st == 403)
        st, _ = s.call("GET", "/files/orders/x?exp=1&sig=1", raw=True)
        check(label + ": eskirgan/begona havola 403", st == 403)
    # rad etilishi kerak bo'lganlar
    check(label + ": .exe rad", s.call("POST", "/api/orders/%d/files" % oid, {"name": "a.exe", "type": "application/x-msdownload", "data": b64(b"MZ")}, K)[0] == 400)
    check(label + ": mazmun turiga mos emas", s.call("POST", "/api/orders/%d/files" % oid, {"name": "a.png", "type": "image/png", "data": b64(b"not a png")}, K)[0] == 400)
    check(label + ": 5 MB dan katta", s.call("POST", "/api/orders/%d/files" % oid, {"name": "a.pdf", "type": "application/pdf", "data": b64(b"%PDF" + b"0" * (5 * 1024 * 1024))}, K)[0] == 400)
    check(label + ": noto'g'ri base64", s.call("POST", "/api/orders/%d/files" % oid, {"name": "a.png", "type": "image/png", "data": "***"}, K)[0] == 400)
    check(label + ": yuklashga kirishsiz 401", s.call("POST", "/api/orders/%d/files" % oid, {"name": "a.png", "type": "image/png", "data": b64(PNG)})[0] == 401)
    st, o2 = s.call("POST", "/api/orders", dict(ORDER, receiver_phone="+998 90 111 22 00"), O)       # kuryerga biriktirilmagan
    check(label + ": begona buyurtmaga kuryer yuklay olmaydi", s.call("POST", "/api/orders/%d/files" % o2["id"], {"name": "a.png", "type": "image/png", "data": b64(PNG)}, K)[0] == 404)
    check(label + ": kuryer fayl o'chira olmaydi", s.call("DELETE", "/api/orders/%d/files/0" % oid, tok=K)[0] == 403)
    check(label + ": yo'l bilan chiqib ketish (../) imkonsiz", "/" not in r["files"][0]["name"] and ".." not in r["files"][0]["name"])

    # eksport
    st, e = s.call("POST", "/api/exports", tok=A)
    check(label + ": CSV eksport saqlashga yozildi", st == 201 and e["key"].startswith("exports/orders-"), e)
    st, lst = s.call("GET", "/api/exports", tok=A)
    check(label + ": eksportlar ro'yxati", st == 200 and any(i["key"] == e["key"] for i in lst["items"]), lst)
    check(label + ": eksport faqat admin", s.call("POST", "/api/exports", tok=O)[0] == 403)

    # holat va selftest
    st, c = s.call("GET", "/api/cloud/status", tok=A)
    check(label + ": cloud status", st == 200 and c["database"]["ok"] and c["database"]["rows"]["orders"] >= 2, c)
    check(label + ": status operatorga yopiq", s.call("GET", "/api/cloud/status", tok=O)[0] == 403)
    check(label + ": status parol/kalit oshkor qilmaydi", "password" not in json.dumps(c).lower() and "secret" not in json.dumps(c).lower())
    st, t = s.call("POST", "/api/cloud/selftest", tok=A)
    names = {x["name"].split(" (")[0]: x for x in t["checks"]}
    check(label + ": selftest DB", names["Ma'lumotlar bazasi"]["ok"], t)
    check(label + ": selftest obyektli saqlash", names["Obyektli saqlash"]["ok"], t)
    return c, oid


# ---------------------------------------------------------------- A) SQLite
tmp = tempfile.mkdtemp()
envA = dict(BTS_STORAGE="sqlite", BTS_SQLITE=os.path.join(tmp, "t.sqlite3"), BTS_FILES=os.path.join(tmp, "files"), BTS_SECRET_KEY="test-only-key", BTS_SEED_DEMO="1")
s = Srv(8801, **envA)
c, oid = full_flow(s, "sqlite", s3=False)
check("sqlite: status turi", c["database"]["kind"] == "sqlite")
s.stop()
s = Srv(8801, **envA)                       # qayta ishga tushirish: ma'lumot saqlanib qolganmi
A = s.login("admin", "admin123")
st, lst = s.call("GET", "/api/orders", tok=A)
check("sqlite: qayta ishga tushgach buyurtmalar saqlangan", st == 200 and lst["total"] >= 2 and any(o["id"] == oid and o["files"] for o in lst["items"]), lst)
st, o3 = s.call("POST", "/api/orders", ORDER, s.login("operator", "operator123"))
check("sqlite: raqam davom etadi (takrorlanmaydi)", st == 201 and o3["id"] > oid + 1, o3)
s.stop()

# ---------------------------------------------------------------- B) PostgreSQL + S3 + CloudWatch (soxta boto3)
if os.environ.get("PGSHIM_SOCKET"):
    aws = tempfile.mkdtemp()
    os.environ["FAKE_AWS"] = aws
    subprocess.run(["psql", "-X", "-q", "-h", os.environ["PGSHIM_SOCKET"], "-U", "postgres", "-d", "bts", "-c",
                    "DROP TABLE IF EXISTS orders, customers, users, kv"], check=True)
    envB = dict(BTS_SEED_DEMO="1", BTS_STORAGE="postgres", DB_SECRET_ID="bts/db", FAKE_SECRET_ID="bts/db",
                FAKE_SECRET_JSON=json.dumps({"username": "u", "password": "pw-from-secrets-manager", "host": "rds.example", "port": 5432, "dbname": "bts"}),
                S3_BUCKET="bts-test-bucket", S3_PREFIX="bts/", AWS_REGION="eu-central-1", CW_NAMESPACE="BTSExpress", TRUST_PROXY="1",
                PYTHONPATH=FAKES, FAKE_AWS=aws)
    s = Srv(8802, **envB)
    c, oid = full_flow(s, "postgres+s3", s3=True)
    check("postgres: status turi/versiya", c["database"]["kind"] == "postgres" and "PostgreSQL 16" in c["database"]["version"], c["database"])
    check("s3: status maqsadi", c["objects"]["target"] == "s3://bts-test-bucket/bts/", c["objects"])
    cw = open(os.path.join(aws, "cloudwatch.jsonl")).read() if os.path.exists(os.path.join(aws, "cloudwatch.jsonl")) else ""
    check("cloudwatch: SelfTest metrikasi yuborildi", '"ns": "BTSExpress"' in cw and "SelfTest" in cw, cw)
    s.call("POST", "/api/login", {"username": "nobody", "password": "x"})
    out = s.stop()
    lines = [json.loads(l) for l in out.splitlines() if l.startswith("{")]
    check("log: JSON qatorlar (startup, request)", any(l["event"] == "startup" for l in lines) and any(l["event"] == "request" and l["path"] == "/api/orders" for l in lines))
    check("log: parol va token loglarda yo'q", "pw-from-secrets-manager" not in out and "admin123" not in out)
    s = Srv(8802, **envB)
    A = s.login("admin", "admin123")
    st, lst = s.call("GET", "/api/orders", tok=A)
    check("postgres: qayta ishga tushgach ma'lumot saqlangan", lst["total"] >= 2 and any(o["id"] == oid for o in lst["items"]), lst)
    st, h = s.call("GET", "/api/health")
    check("postgres: health qayta ishga tushgach", st == 200)
    s.stop()
else:
    print("SKIP PostgreSQL testi (PGSHIM_SOCKET yo'q)")

# ---------------------------------------------------------------- bulutda boshlang'ich admin paroli
sd = tempfile.mkdtemp()
base = dict(BTS_STORAGE="sqlite", BTS_FILES=os.path.join(sd, "f"))
p = subprocess.run([sys.executable, os.path.join(ROOT, "server.py")], env=dict(os.environ, PORT="8804", BTS_SQLITE=os.path.join(sd, "a.db"), **base),
                   capture_output=True, text=True, timeout=20)
check("bulut: admin paroli berilmasa ishga tushmaydi", p.returncode != 0 and "admin paroli" in (p.stderr + p.stdout))
s = Srv(8804, BTS_SQLITE=os.path.join(sd, "b.db"), BTS_ADMIN_PASSWORD="Long-Test-Pass-1", **base)
check("bulut: admin berilgan parol bilan kiradi", bool(s.login("admin", "Long-Test-Pass-1")))
check("bulut: standart admin123 ishlamaydi", not s.login("admin", "admin123"))
check("bulut: demo foydalanuvchilar yaratilmaydi", not s.login("operator", "operator123") and not s.login("kuryer1", "kuryer123"))
s.stop()
aws2 = tempfile.mkdtemp()
s = Srv(8804, BTS_SQLITE=os.path.join(sd, "c.db"), ADMIN_SECRET_ID="bts/admin", FAKE_SECRET_ID="bts/admin", FAKE_SECRET_JSON=json.dumps({"password": "From-Secrets-Mgr-9"}),
        PYTHONPATH=FAKES, FAKE_AWS=aws2, AWS_REGION="eu-central-1", **base)
check("bulut: admin paroli Secrets Manager'dan", bool(s.login("admin", "From-Secrets-Mgr-9")))
s.stop()

# ---------------------------------------------------------------- postgres sozlamasi yetishmasa
p = subprocess.run([sys.executable, os.path.join(ROOT, "server.py")], env=dict(os.environ, BTS_STORAGE="postgres", PORT="8803", DB_HOST="", DB_PASSWORD=""),
                   capture_output=True, text=True, timeout=20)
check("postgres: sozlama yo'q bo'lsa tushunarli xato bilan to'xtaydi", p.returncode != 0 and "DB_HOST" in (p.stderr + p.stdout))

print("\n" + ("Hamma bulut testlari o'tdi" if not fails else "XATOLAR: %s" % fails))
sys.exit(1 if fails else 0)
