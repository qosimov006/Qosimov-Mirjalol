#!/usr/bin/env python3
"""BTS Express Pochta Tizimi - backend.

Faqat Python standart kutubxonasi. Ma'lumotlar JSON faylda saqlanadi.
"""
import base64, csv, io, json, math, os, platform, re, secrets, hashlib, hmac, shutil, socket, threading, mimetypes, time
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

import cloud
import storage

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
CFG = cloud.Config()
STORE = storage.make_store(CFG)          # json | postgres (RDS) | sqlite
OBJECTS = cloud.make_object_store(CFG)   # S3 yoki lokal papka
METRICS = cloud.Metrics(CFG)
STARTED = time.time()
VERSION = "3.0-cloud"
MAX_UPLOAD = 5 * 1024 * 1024
UPLOAD_TYPES = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG",), "image/webp": (b"RIFF",), "application/pdf": (b"%PDF",)}
LOCK = threading.RLock()

SESSION_TTL = 12 * 3600
SESSIONS = {}          # token -> {"uid", "exp"}
FAILS = {}             # (ip, username) -> [timestamps]
MAX_FAILS, FAIL_WINDOW = 5, 300

STATUSES = ["Qabul qilindi", "Yo'lda", "Yetkazildi", "Bekor qilindi"]
COURIER_STATUSES = ["Yo'lda", "Yetkazildi", "Bekor qilindi"]
FINAL = ("Yetkazildi", "Bekor qilindi")
PAYERS = ["Yuboruvchi", "Qabul qiluvchi"]
ROLES = ["admin", "operator", "courier"]
ORDER_FIELDS = ["sender_name", "sender_phone", "receiver_name", "receiver_phone",
                "address", "product", "weight", "price"]
MAXLEN = {"sender_name": 80, "receiver_name": 80, "address": 250, "product": 120, "note": 300, "name": 80}


# ---------------------------------------------------------------- yordamchi
# Boshlang'ich tarif (namuna). Admin "Tariflar" sahifasida o'zgartiradi.
DEFAULT_TARIFF = {"base": 10000, "per_kg": 3000, "free_kg": 1, "round_to": 500,
                  "door_fee": 10000, "vat": 12, "vol_divisor": 5000, "courier_fee": 5000}
TARIFF_KEYS = (("base", 0, True), ("per_kg", 0, True), ("free_kg", 0, True), ("round_to", 1, True),
               ("door_fee", 0, False), ("vat", 0, False), ("vol_divisor", 1, False), ("courier_fee", 0, False))

# Hududlar: manba — O'zbekiston ma'muriy-hududiy bo'linishi (viloyat bo'ysunuvidagi shaharlar + tumanlar).
_REG = [
    ("Toshkent shahri", [], ["Bektemir", "Mirzo Ulug'bek", "Mirobod", "Olmazor", "Sergeli", "Uchtepa", "Chilonzor", "Shayxontohur", "Yunusobod", "Yakkasaroy", "Yashnobod", "Yangihayot"]),
    ("Toshkent viloyati", ["Nurafshon", "Angren", "Bekobod", "Olmaliq", "Ohangaron", "Chirchiq", "Yangiyo'l"],
     ["Bekobod", "Bo'ka", "Bo'stonliq", "Zangiota", "Qibray", "Quyichirchiq", "Oqqo'rg'on", "Ohangaron", "Parkent", "Piskent", "Toshkent", "O'rtachirchiq", "Chinoz", "Yuqorichirchiq", "Yangiyo'l"]),
    ("Andijon viloyati", ["Andijon", "Xonabod"],
     ["Andijon", "Asaka", "Baliqchi", "Bo'z", "Buloqboshi", "Jalaquduq", "Izboskan", "Qo'rg'ontepa", "Marhamat", "Oltinko'l", "Paxtaobod", "Ulug'nor", "Xo'jaobod", "Shahrixon"]),
    ("Buxoro viloyati", ["Buxoro", "Kogon"],
     ["Buxoro", "Vobkent", "Jondor", "Kogon", "Olot", "Peshku", "Romitan", "Shofirkon", "Qorovulbozor", "Qorako'l", "G'ijduvon"]),
    ("Jizzax viloyati", ["Jizzax"],
     ["Arnasoy", "Baxmal", "Do'stlik", "Zarbdor", "Zafarobod", "Zomin", "Mirzacho'l", "Paxtakor", "Forish", "Sharof Rashidov", "G'allaorol", "Yangiobod"]),
    ("Qashqadaryo viloyati", ["Qarshi", "Shahrisabz"],
     ["Dehqonobod", "Kasbi", "Kitob", "Koson", "Mirishkor", "Muborak", "Nishon", "Chiroqchi", "Shahrisabz", "Yakkabog'", "Qamashi", "Qarshi", "G'uzor", "Ko'kdala"]),
    ("Navoiy viloyati", ["Navoiy", "Zarafshon"], ["Karmana", "Konimex", "Navbahor", "Nurota", "Tomdi", "Uchquduq", "Xatirchi", "Qiziltepa"]),
    ("Namangan viloyati", ["Namangan"],
     ["Kosonsoy", "Mingbuloq", "Namangan", "Norin", "Pop", "To'raqo'rg'on", "Uychi", "Uchqo'rg'on", "Chortoq", "Chust", "Yangiqo'rg'on"]),
    ("Samarqand viloyati", ["Samarqand", "Kattaqo'rg'on"],
     ["Bulung'ur", "Jomboy", "Ishtixon", "Kattaqo'rg'on", "Narpay", "Nurobod", "Oqdaryo", "Payariq", "Pastdarg'om", "Paxtachi", "Samarqand", "Toyloq", "Urgut", "Qo'shrabot"]),
    ("Surxondaryo viloyati", ["Termiz"],
     ["Angor", "Boysun", "Denov", "Jarqo'rg'on", "Muzrobod", "Oltinsoy", "Sariosiyo", "Termiz", "Uzun", "Sherobod", "Sho'rchi", "Qiziriq", "Qumqo'rg'on", "Bandixon"]),
    ("Sirdaryo viloyati", ["Guliston", "Yangiyer", "Shirin"], ["Boyovut", "Guliston", "Mirzaobod", "Oqoltin", "Sardoba", "Sayxunobod", "Sirdaryo", "Xovos"]),
    ("Farg'ona viloyati", ["Farg'ona", "Marg'ilon", "Quvasoy", "Qo'qon"],
     ["Beshariq", "Bag'dod", "Buvayda", "Dang'ara", "Yozyovon", "Quva", "Qo'shtepa", "Oltiariq", "Rishton", "So'x", "Toshloq", "O'zbekiston", "Uchko'prik", "Farg'ona", "Furqat"]),
    ("Xorazm viloyati", ["Urganch", "Xiva"],
     ["Bog'ot", "Gurlan", "Urganch", "Xiva", "Xonqa", "Hazorasp", "Shovot", "Yangiariq", "Yangibozor", "Qo'shko'pir", "Tuproqqal'a"]),
    ("Qoraqalpog'iston Respublikasi", ["Nukus"],
     ["Amudaryo", "Beruniy", "Kegeyli", "Qanliko'l", "Qorao'zak", "Qo'ng'irot", "Mo'ynoq", "Nukus", "Taxiatosh", "Taxtako'pir", "To'rtko'l", "Xo'jayli", "Chimboy", "Shumanay", "Ellikqal'a", "Bo'zatov"]),
]
REGIONS = {name: [c + " shahri" for c in cities] + [t + " tumani" for t in tumans] for name, cities, tumans in _REG}
DICT_VERSION = 4
COMPLAINT_KINDS = ["Kech yetkazildi", "Shikastlangan pochta", "Yo'qolgan pochta", "Xodim xulqi", "Narx bo'yicha", "Boshqa"]


def _norm(t):
    return re.sub(r"[^a-z]", "", str(t).lower().replace("o'", "o").replace("g'", "g").replace("'", ""))


def gen_branches():
    """Har bir viloyat/tuman/shahar uchun namunaviy filial (kod: 9 + viloyat raqami + tuman raqami). Haqiqiy kodlarga admin
    "Ma'lumotnomalar"da almashtiradi."""
    out = []
    for i, (region, items) in enumerate(REGIONS.items(), 1):
        for j, d in enumerate(items, 1):
            base = re.sub(r" (shahri|tumani)$", "", d).upper()
            out.append({"code": "9%02d%02d" % (i, j), "name": base, "region": region, "district": d, "address": "%s, %s" % (region, d)})
    return out


def migrate_v4(db):
    """v4: filialga manzil; xodimga ofis (smena joyi). Operatorga standart ofis QO'YLIQ (0112) beriladi."""
    org_addr = db["dict"].get("org", {}).get("address", "")
    for b in db["dict"].get("branches", []):
        if "address" not in b:
            b["address"] = org_addr if b["code"] == "0112" else ", ".join(x for x in (b.get("region"), b.get("district")) if x)
    has0112 = any(b["code"] == "0112" for b in db["dict"].get("branches", []))
    for u in db["users"]:
        if "branch" not in u:
            u["branch"] = "0112" if (u["role"] == "operator" and has0112) else ""


def migrate_branches(db):
    """v3: filiallar viloyat/tumanga bog'lanadi. Viloyatsizlarni nomiga qarab moslashtirishga urinadi, so'ng namunaviylarni qo'shadi."""
    import difflib
    brs = db["dict"].get("branches", [])
    regs = db["dict"].get("regions", REGIONS)
    for b in brs:
        b.setdefault("region", "")
        b.setdefault("district", "")
        if not b["region"]:
            words = [_norm(w) for w in re.split(r"\s+", b["name"]) if len(_norm(w)) > 3]
            best = (0.8, None, None)
            for r, items in regs.items():
                for d in items:
                    dn = _norm(re.sub(r" (shahri|tumani)$", "", d))
                    for w in words:
                        sc = difflib.SequenceMatcher(None, w, dn).ratio()
                        if sc > best[0]:
                            best = (sc, r, d)
            if best[1]:
                b["region"], b["district"] = best[1], best[2]
    have = {b["code"] for b in brs}
    brs += [b for b in gen_branches() if b["code"] not in have]
    db["dict"]["branches"] = brs


# Ma'lumotnomalar (admin "Ma'lumotnomalar" sahifasida tahrirlanadi). Ro'yxatlar namuna.
DEFAULT_DICT = {
    "regions": REGIONS,
    "branches": [{"code": "0112", "name": "QO'YLIQ", "region": "Toshkent shahri", "district": "",
                  "address": "TOSHKENT, Farg'ona yo'li k, 4-uy, 3-xona yoki: naprotiv Bozor"}] + gen_branches(),
    "contents": ["AKSESSUAR", "AMPULA", "BUYUMLAR", "MAISHIY TEXNIKA USKUNALARI", "VATSINKA", "HUJJATLAR", "BOSHQA...",
                 "EHTIYOT QISMLAR", "O'YINCHOQLAR", "KANSERTURA TOVARLARI", "KITOBLAR", "KOSMETIKA", "MEBEL",
                 "TIBBIY ASBOB", "DORILAR", "USKUNA-USKUNALAR", "OBUV (BOLALAR UCHUN)", "OBUV (AYOL)"],
    "packages": ["ZAVOD QADOQLASH", "BTS PAKETI", "BTS qutisi", "QORA PAKET", "BTS konverti", "Yog'och quti", "QOG'OZ",
                 "SHOTLAND", "KO'PIKLI REZINA", "O'RNATILMAGAN", "KONTEYNER", "SUMKA", "Muhr", "Cho'zish"],
    "payment_types": ["Kelishuv", "To'lanmagan", "Balans"],
    "transports": ["Avtomatik", "Avtotransport", "Aviatransport", "Temir yo'l"],
    "org": {"name": "MChJ BTS Express Cargo Servis", "inn": "301050182", "address": "TOSHKENT, Farg'ona yo'li k, 4-uy, 3-xona yoki: naprotiv Bozor", "site": "https://bts.uz"},
}


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 60000).hex()


def scrypt_pw(pw, salt):
    """Zamonaviy parol hash (scrypt, xotirani talab qiladi: GPU/ASIC hujumiga chidamli)."""
    return "s1$" + hashlib.scrypt(pw.encode(), salt=salt.encode(), n=2 ** 14, r=8, p=1, dklen=32).hex()


def check_pw(u, pw):
    stored = u["password"]
    calc = scrypt_pw(pw, u["salt"]) if stored.startswith("s1$") else hash_pw(pw, u["salt"])   # eski pbkdf2 ham taniladi
    return hmac.compare_digest(calc, stored)


def set_pw(u, pw):
    u["salt"] = secrets.token_hex(8)
    u["password"] = scrypt_pw(pw, u["salt"])


def audit(db, u, action, detail="", ip=""):
    """Audit log: kim, qachon, nima qildi (oxirgi 1000 yozuv)."""
    log = db.setdefault("audit", [])
    log.append({"time": now(), "user": (u or {}).get("username", "-"), "role": (u or {}).get("role", "-"),
                "action": action, "detail": str(detail)[:200], "ip": ip})
    del log[:-1000]


def make_user(uid, username, password, role, name, phone=""):
    salt = secrets.token_hex(8)
    return {"id": uid, "username": username, "salt": salt, "password": scrypt_pw(password, salt),
            "role": role, "name": name, "phone": phone, "active": True, "created": now(), "branch": ""}


def norm_phone(v):
    """+998901234567 ko'rinishiga keltiradi. Noto'g'ri bo'lsa None."""
    digits = re.sub(r"\D", "", str(v or ""))
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    if 10 <= len(digits) <= 15 and str(v).strip().startswith("+"):
        return "+" + digits
    return None


def seed_db():
    """Bo'sh bazaga boshlang'ich ma'lumot. Lokal (json) rejimda demo foydalanuvchilar; bulutda faqat admin va uning paroli
    maxfiy joydan (BTS_ADMIN_PASSWORD yoki ADMIN_SECRET_ID) olinadi - kodda yoki repoda standart parol yo'q."""
    demo = STORE.kind == "json" or os.environ.get("BTS_SEED_DEMO") == "1"
    pw = CFG.admin_password()
    if demo:
        users = [make_user(1, "admin", pw or "admin123", "admin", "Administrator"),
                 make_user(2, "operator", "operator123", "operator", "Operator"),
                 make_user(3, "kuryer1", "kuryer123", "courier", "Kuryer Aziz", "+998901112233")]
        users[1]["branch"] = "0112"
        nxt = 4
    else:
        if len(pw) < 10:
            raise SystemExit("Bulut rejimida birinchi ishga tushirish uchun kamida 10 belgili admin paroli kerak: "
                             "BTS_ADMIN_PASSWORD yoki ADMIN_SECRET_ID (Secrets Manager) o'zgaruvchisini bering")
        users, nxt = [make_user(1, "admin", pw, "admin", "Administrator")], 2
    return {"users": users, "orders": [], "customers": {}, "settings": dict(DEFAULT_TARIFF), "dict": json.loads(json.dumps(DEFAULT_DICT)),
            "dict_version": DICT_VERSION, "next_user": nxt, "next_order": 1}


def load_db():
    db = STORE.load()
    fresh = db is None
    if fresh:
        db = seed_db()
    db.setdefault("customers", {})
    db.setdefault("settings", {})
    for k, v in DEFAULT_TARIFF.items():
        db["settings"].setdefault(k, v)
    db.setdefault("dict", json.loads(json.dumps(DEFAULT_DICT)))
    old_ver = db.get("dict_version", 1)
    if old_ver < DICT_VERSION:        # eski qisqa hudud ro'yxatlarini to'liq ro'yxatga yangilash
        for region, items in REGIONS.items():
            old = [x for x in db["dict"]["regions"].get(region, []) if x not in items]   # admin qo'shganlari saqlanadi
            db["dict"]["regions"][region] = items + old
        db["dict_version"] = DICT_VERSION
        fresh = True
    if old_ver < 3 or any("district" not in b for b in db["dict"].get("branches", [])):
        migrate_branches(db)
        fresh = True
    if old_ver < 4 or any("address" not in b for b in db["dict"].get("branches", [])) or any("branch" not in u for u in db["users"]):
        migrate_v4(db)
        fresh = True
    for u in db["users"]:
        u.setdefault("active", True)
    if fresh:
        STORE.save(db)
    return db


def save_db(db):
    STORE.save(db)


def backup_db():
    STORE.backup()


DB = load_db()
backup_db()


def branch_code_of(text):
    m = re.match(r"\s*(\d+)", str(text or ""))
    return m.group(1) if m else ""


def find_branch(db, code):
    return next((b for b in db["dict"].get("branches", []) if b["code"] == code), None) if code else None


def office_address(db, branch_text):
    """Yorliqdagi jo'natuvchi manzili = jo'natilgan ofis (filial) manzili; filialda manzil bo'lmasa tashkilot manzili."""
    b = find_branch(db, branch_code_of(branch_text))
    return (b or {}).get("address") or db["dict"].get("org", {}).get("address", "")


def office_of(db, u):
    b = find_branch(db, u.get("branch"))
    if not b:
        return None
    return {"code": b["code"], "name": b["name"], "region": b.get("region", ""), "district": b.get("district", ""), "address": office_address(db, b["code"])}


def public_user(u):
    d = {k: u.get(k) for k in ("id", "username", "role", "name", "phone", "active", "created", "branch")}
    d["office"] = office_of(DB, u)
    return d


def clean_text(v, field, required=True):
    v = re.sub(r"\s+", " ", str(v or "")).strip()
    if required and not v:
        raise ValueError("Maydon to'ldirilmagan: %s" % field)
    if len(v) > MAXLEN.get(field, 200):
        raise ValueError("Matn juda uzun: %s" % field)
    return v


def compute_quote(db, weight, length=0, width=0, height=0, door=False, extra=0):
    """Narxni hisoblash (frontend ham xuddi shu formulada hisoblaydi)."""
    t = db["settings"]
    volume = max(0, length) * max(0, width) * max(0, height)
    vol_weight = volume / t["vol_divisor"]
    chargeable = max(weight, vol_weight)
    tariff = math.ceil((t["base"] + t["per_kg"] * max(0, chargeable - t["free_kg"])) / t["round_to"] - 1e-9) * t["round_to"] if chargeable > 0 else 0
    door_fee = t["door_fee"] if door else 0
    extra = max(0, extra)
    net = tariff + door_fee + extra
    vat = int(math.floor(net * t["vat"] / 100 + 0.5))
    return {"volume_cm3": round(volume, 2), "vol_weight": round(vol_weight, 3), "chargeable_kg": round(chargeable, 3),
            "tariff": tariff, "door_fee": door_fee, "extra_service": extra, "price_net": net, "vat_amount": vat, "price": net + vat}


OPT_TEXT = ("date", "sender_region", "sender_district", "sender_branch", "sender_address", "receiver_region",
            "receiver_district", "receiver_branch", "package", "transport", "barcode", "payment_type")


def num(d, key, lo, hi, label):
    try:
        v = float(d.get(key) or 0)
    except (TypeError, ValueError):
        raise ValueError("%s son bo'lishi kerak" % label)
    if not lo <= v <= hi:
        raise ValueError("%s noto'g'ri" % label)
    return v


def validate_order(d, db=None):
    c = {}
    for f in ("sender_name", "receiver_name", "product"):
        c[f] = clean_text(d.get(f), f)
    for f in ("sender_phone", "receiver_phone"):
        p = norm_phone(d.get(f))
        if not p:
            raise ValueError("Telefon raqam noto'g'ri (masalan +998901234567)")
        c[f] = p
    if d.get("receiver_phone2"):
        p2 = norm_phone(d.get("receiver_phone2"))
        if not p2:
            raise ValueError("Qabul qiluvchining 2-telefon raqami noto'g'ri")
        c["receiver_phone2"] = p2
    for f in OPT_TEXT:
        if f in d:
            c[f] = clean_text(d[f], f, required=False)
    for f in ("by_call", "door_delivery"):
        if f in d:
            c[f] = bool(d[f]) and d[f] not in ("false", "0", "off")
    addr = clean_text(d.get("address"), "address", required=False)
    if not addr:
        if not c.get("receiver_branch") and not d.get("receiver_branch"):
            raise ValueError("Manzilni yoki qabul qiluvchi filialini ko'rsating")
        br = clean_text(d.get("receiver_branch"), "receiver_branch", required=False)
        place = ", ".join(x for x in (clean_text(d.get("receiver_region"), "x", False), clean_text(d.get("receiver_district"), "x", False)) if x)
        addr = ("Filial: %s %s" % (br, ("(%s)" % place) if place else "")).strip()
    c["address"] = addr
    try:
        c["weight"] = round(float(d.get("weight")), 3)
    except (TypeError, ValueError):
        raise ValueError("Og'irlik son bo'lishi kerak")
    if not 0 < c["weight"] <= 1000:
        raise ValueError("Og'irlik 0 dan katta va 1000 kg dan kichik bo'lishi kerak")
    for f, label in (("length", "Uzunlik"), ("width", "Kenglik"), ("height", "Balandlik")):
        if f in d:
            c[f] = round(num(d, f, 0, 1000, label), 2)
    if "quantity" in d:
        c["quantity"] = int(num(d, "quantity", 1, 10000, "Miqdor"))
    if "extra_service" in d:
        c["extra_service"] = round(num(d, "extra_service", 0, 1e9, "Qo'shimcha xizmat"), 2)
    if d.get("auto_price") and db is not None:
        q = compute_quote(db, c["weight"], c.get("length", 0), c.get("width", 0), c.get("height", 0),
                          c.get("door_delivery", False), c.get("extra_service", 0))
        c.update(volume_cm3=q["volume_cm3"], vol_weight=q["vol_weight"], price_net=q["price_net"],
                 vat_amount=q["vat_amount"], price=q["price"])
    else:
        try:
            c["price"] = round(float(d.get("price")), 2)
        except (TypeError, ValueError):
            raise ValueError("Narx son bo'lishi kerak")
        if not 0 <= c["price"] <= 1e9:
            raise ValueError("Narx noto'g'ri")
    c["payer"] = d.get("payer") if d.get("payer") in PAYERS else PAYERS[0]
    c["note"] = clean_text(d.get("note"), "note", required=False)
    return c


def upsert_customer(db, name, phone, address=None):
    c = db["customers"].setdefault(phone, {"phone": phone, "name": name, "address": "", "orders": 0, "created": now(), "balance": 0, "ledger": []})
    c["name"] = name
    if address:
        c["address"] = address
    c["orders"] += 1
    c["last"] = now()


def money_int(v):
    return int(round(v))


def ledger_add(cust, amount, kind, by, order=None):
    cust["balance"] = round(cust.get("balance", 0) + amount, 2)
    cust.setdefault("ledger", []).append({"time": now(), "amount": amount, "type": kind, "by": by, **({"order": order} if order else {})})
    cust["ledger"] = cust["ledger"][-200:]


def waybill_number(o):
    """12 xonali shtrix-kod raqami: jo'natuvchi filial kodi (4) + buyurtma raqami (8). Yo'lxatdagi shtrix-kodda ishlatiladi."""
    m = re.match(r"\s*(\d+)", str(o.get("sender_branch") or ""))
    return (m.group(1)[:4].zfill(4) if m else "0000") + "%08d" % o["id"]


def order_view(o, db):
    d = dict(o)
    d.pop("pickup_code", None)          # topshirish kodi faqat mijozning o'ziga ko'rinadi
    d["barcode"] = waybill_number(o)
    d.setdefault("office_address", office_address(db, o.get("sender_branch")))
    cr = next((u for u in db["users"] if u["id"] == o.get("courier_id")), None)
    d["courier_name"] = cr["name"] if cr else None
    d["courier_phone"] = cr["phone"] if cr else None
    return d


def filter_orders(orders, q):
    g = lambda k: q.get(k, [""])[0].strip()
    st, s, cid, df, dt = g("status"), g("q").lower(), g("courier_id"), g("from"), g("to")
    if st:
        orders = [o for o in orders if o["status"] == st]
    if cid == "none":
        orders = [o for o in orders if not o.get("courier_id")]
    elif cid.isdigit():
        orders = [o for o in orders if o.get("courier_id") == int(cid)]
    if df:
        orders = [o for o in orders if o["created"][:10] >= df]
    if dt:
        orders = [o for o in orders if o["created"][:10] <= dt]
    if s:
        keys = ("code", "sender_name", "sender_phone", "receiver_name", "receiver_phone", "address", "product")
        orders = [o for o in orders if any(s in str(o[k]).lower() for k in keys)]
    return sorted(orders, key=lambda x: -x["id"])


def orders_csv(db, orders):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Raqam", "Sana", "Yuboruvchi", "Yuboruvchi tel", "Qabul qiluvchi", "Qabul qiluvchi tel",
                "Manzil", "Mahsulot", "Og'irlik kg", "Narx", "To'lovchi", "Kuryer", "Holat", "Izoh"])
    for o in orders:
        v = order_view(o, db)
        w.writerow([o["code"], o["created"], o["sender_name"], o["sender_phone"], o["receiver_name"],
                    o["receiver_phone"], o["address"], o["product"], o["weight"], o["price"],
                    o.get("payer", ""), v["courier_name"] or "", o["status"], o.get("note", "")])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def waybill_html(o):
    from html import escape as e
    rows = [("Raqam", o["code"]), ("Sana", o["created"]), ("Yuboruvchi", "%s (%s)" % (o["sender_name"], o["sender_phone"])),
            ("Qabul qiluvchi", "%s (%s)" % (o["receiver_name"], o["receiver_phone"])), ("Manzil", o["address"]),
            ("Mahsulot", o["product"]), ("Og'irlik", "%s kg" % o["weight"]), ("Narx", "%s so'm" % money_int(o["price"])),
            ("To'lovchi", o.get("payer", "")), ("Holat", o["status"])]
    body = "".join("<tr><th>%s</th><td>%s</td></tr>" % (e(k), e(str(v))) for k, v in rows)
    return ("<!doctype html><html lang=uz><meta charset=utf-8><title>%s</title><style>body{font:14px sans-serif;margin:24px}"
            "table{border-collapse:collapse}th,td{border:1px solid #999;padding:6px 10px;text-align:left}</style>"
            "<h2>BTS Express - yo'l varaqasi %s</h2><table>%s</table></html>" % (e(o["code"]), e(o["code"]), body)).encode("utf-8")


def safe_name(n):
    n = re.sub(r"[^\w.\- ]", "_", os.path.basename(str(n or "fayl")), flags=re.U).strip(". ") or "fayl"
    return n[-80:]


def thread_safe_cloud_call(label, fn):
    """Bulut xizmati (S3 va h.k.) ishlamasa asosiy ish to'xtamasin - log yoziladi."""
    try:
        return fn()
    except Exception as ex:
        cloud.log_json("cloud_error", op=label, error="%s: %s" % (type(ex).__name__, ex))
        return None


_IMDS = {}


def instance_meta():
    """EC2 ichida bo'lsa instance-id va zonani (IMDSv2) qaytaradi; bo'lmasa bo'sh."""
    if "v" in _IMDS:
        return _IMDS["v"]
    out = {}
    try:
        import urllib.request as ur
        t = ur.urlopen(ur.Request("http://169.254.169.254/latest/api/token", method="PUT",
                                  headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"}), timeout=0.4).read().decode()
        for k, path in (("instance_id", "instance-id"), ("instance_type", "instance-type"), ("zone", "placement/availability-zone"), ("public_ip", "public-ipv4")):
            try:
                out[k] = ur.urlopen(ur.Request("http://169.254.169.254/latest/meta-data/" + path, headers={"X-aws-ec2-metadata-token": t}), timeout=0.4).read().decode()
            except Exception:
                pass
    except Exception:
        pass
    _IMDS["v"] = out
    return out


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "BTSExpress/2.0"

    def log_message(self, *a):
        pass

    _t0 = None

    def log_request(self, code="-", size="-"):
        """Har bir API so'rovi: JSON log (CloudWatch Logs) + hisoblagichlar (CloudWatch Metrics)."""
        p = urlparse(self.path).path
        try:
            code = int(code)
        except (TypeError, ValueError):
            code = 0
        if p.startswith("/api/") or p.startswith("/files/"):
            METRICS.inc("Requests")
            if p != "/api/health":
                cloud.log_json("request", method=self.command, path=p, status=code, ms=int((time.time() - (self._t0 or time.time())) * 1000), ip=self.ip())
        if code >= 500:
            METRICS.inc("Errors5xx")

    def ip(self):
        """Nginx ortida: so'nggi X-Forwarded-For elementi (nginx qo'shgan haqiqiy mijoz IP'si)."""
        if CFG.trust_proxy:
            xf = self.headers.get("X-Forwarded-For", "")
            if xf:
                return xf.split(",")[-1].strip()
        return self.client_address[0]

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def err(self, code, msg):
        self.send_json(code, {"error": msg})

    def body(self, limit=1_000_000):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > limit:
                raise ValueError("So'rov hajmi juda katta")
            return json.loads(self.rfile.read(n).decode()) if n else {}
        except ValueError:
            raise
        except Exception:
            return {}

    def token(self):
        a = self.headers.get("Authorization", "")
        return a[7:] if a.startswith("Bearer ") else ""

    def user(self):
        s = SESSIONS.get(self.token())
        if not s:
            return None
        if s["exp"] < time.time():
            SESSIONS.pop(self.token(), None)
            return None
        u = next((x for x in DB["users"] if x["id"] == s["uid"]), None)
        return u if u and u.get("active", True) else None

    def need(self, *roles):
        u = self.user()
        if not u:
            self.err(401, "Tizimga kiring")
            return None
        if roles and u["role"] not in roles:
            self.err(403, "Ruxsat yo'q")
            return None
        return u

    def do_GET(self):
        self._t0 = time.time()
        p = urlparse(self.path)
        if p.path.startswith("/api/"):
            return self.api("GET", p)
        if p.path.startswith("/files/"):
            return self.local_file(p)
        path = "/index.html" if p.path == "/" else p.path
        full = os.path.normpath(os.path.join(STATIC, path.lstrip("/")))
        if not full.startswith(STATIC + os.sep) or not os.path.isfile(full):
            self.send_response(404)
            self.end_headers()
            return
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") or "javascript" in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self): self._t0 = time.time(); self.api("POST", urlparse(self.path))
    def do_PUT(self): self._t0 = time.time(); self.api("PUT", urlparse(self.path))
    def do_DELETE(self): self._t0 = time.time(); self.api("DELETE", urlparse(self.path))

    def local_file(self, p):
        """Lokal rejimda imzolangan havola orqali fayl berish (S3 presigned URL'ning analogi)."""
        q = parse_qs(p.query)
        key = unquote(p.path[len("/files/"):])
        if CFG.s3_bucket or not OBJECTS.verify(key, q.get("exp", [""])[0], q.get("sig", [""])[0]):
            self.send_response(403)
            self.end_headers()
            return
        try:
            data, ctype = OBJECTS.get(key)
        except cloud.ObjectError:
            self.send_response(404)
            self.end_headers()
            return
        name = re.sub(r'[^\w.\- ]', "_", q.get("name", [os.path.basename(key)])[0])
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", 'attachment; filename="%s"' % name)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def api(self, method, p):
        with LOCK:
            try:
                self.route(method, p.path.rstrip("/"), parse_qs(p.query))
            except ValueError as e:
                self.err(400, str(e))
            except (BrokenPipeError, ConnectionResetError):
                pass                      # mijoz sahifani yopib ketdi — xato emas
            except Exception as e:  # noqa
                cloud.log_json("error", path=p.path, error=repr(e)[:300])   # tafsilot faqat logda, mijozga ichki xato matni ko'rsatilmaydi
                try:
                    self.err(500, "Ichki server xatosi")
                except (BrokenPipeError, ConnectionResetError):
                    pass

    # ------------------------------------------------------------ routes
    def route(self, method, path, q):
        db = DB

        # ---- ochiq
        if method == "GET" and path == "/api/health":
            # Load balancer / monitoring uchun: ilova va ma'lumotlar bazasi tirikmi
            try:
                dbok = bool(STORE.ping())
            except Exception as ex:
                cloud.log_json("health_db_error", error="%s: %s" % (type(ex).__name__, ex))
                dbok = False
            return self.send_json(200 if dbok else 503, {"status": "ok" if dbok else "degraded", "database": "up" if dbok else "down",
                                                         "storage": STORE.kind, "objects": OBJECTS.kind, "version": VERSION,
                                                         "uptime_s": int(time.time() - STARTED)})

        if method == "POST" and path == "/api/login":
            d = self.body()
            uname = str(d.get("username", "")).strip()
            key = (self.ip(), uname.lower())
            recent = [t for t in FAILS.get(key, []) if t > time.time() - FAIL_WINDOW]
            if len(recent) >= MAX_FAILS:
                return self.err(429, "Juda ko'p urinish. 5 daqiqadan so'ng qayta urinib ko'ring")
            u = next((x for x in db["users"] if x["username"].lower() == uname.lower()), None)
            ok = u and check_pw(u, str(d.get("password", "")))
            if not ok:
                FAILS[key] = recent + [time.time()]
                METRICS.inc("LoginFailed")
                return self.err(401, "Login yoki parol noto'g'ri")
            if not u.get("active", True):
                return self.err(403, "Hisob o'chirilgan. Administratorga murojaat qiling")
            FAILS.pop(key, None)
            if not u["password"].startswith("s1$"):                 # eski hash — kirishda yangisiga o'tkazamiz
                set_pw(u, str(d.get("password", "")))
            audit(db, u, "login", "", self.ip())
            save_db(db)
            token = secrets.token_hex(24)
            SESSIONS[token] = {"uid": u["id"], "exp": time.time() + SESSION_TTL}
            return self.send_json(200, {"token": token, "user": public_user(u)})

        if method == "POST" and path == "/api/logout":
            SESSIONS.pop(self.token(), None)
            return self.send_json(200, {"ok": True})

        if method == "GET" and path == "/api/track":
            raw = q.get("id", [""])[0].strip()
            code = re.sub(r"\s", "", raw) if re.fullmatch(r"[\d\s]+", raw) else raw.upper()
            if re.fullmatch(r"\d{12}", code):                   # shtrix-kod raqami
                o = next((x for x in db["orders"] if waybill_number(x) == code), None)
            else:
                if re.fullmatch(r"\d{1,6}", code):
                    code = "BTS-%05d" % int(code)
                o = next((x for x in db["orders"] if x["code"] == code), None)
            if not o:
                return self.err(404, "Buyurtma topilmadi")
            # Ochiq sahifa: ism, telefon va aniq manzil ko'rsatilmaydi (QR-kod kimning qo'liga tushishidan qat'i nazar)
            place = lambda r, d_, b: ", ".join(x for x in (r, d_, b) if x)
            return self.send_json(200, {"code": o["code"], "barcode": waybill_number(o), "status": o["status"], "created": o["created"],
                                        "product": o["product"], "weight": o.get("weight"), "quantity": o.get("quantity", 1), "package": o.get("package", ""),
                                        "from": place(o.get("sender_region"), o.get("sender_district"), ""),
                                        "to": place(o.get("receiver_region"), o.get("receiver_district"), o.get("receiver_branch")),
                                        "door_delivery": bool(o.get("door_delivery")),
                                        "history": [{"status": h["status"], "time": h["time"]} for h in o["history"]]})

        # ---- profil
        if method == "GET" and path == "/api/me":
            u = self.need()
            return u and self.send_json(200, public_user(u))

        if method == "POST" and path == "/api/shift":
            u = self.need("operator", "admin")
            if not u:
                return
            bc = branch_code_of(self.body().get("branch"))
            if not find_branch(db, bc):
                return self.err(400, "Ofis topilmadi")
            u["branch"], u["shift_started"] = bc, now()
            audit(db, u, "smena ochildi", bc, self.ip())
            save_db(db)
            cloud.log_json("shift", user=u["username"], branch=bc)
            return self.send_json(200, public_user(u))

        if method == "POST" and path == "/api/password":
            u = self.need()
            if not u:
                return
            d = self.body()
            if not check_pw(u, str(d.get("old", ""))):
                return self.err(400, "Joriy parol noto'g'ri")
            new = str(d.get("new", ""))
            if len(new) < 6:
                return self.err(400, "Yangi parol kamida 6 belgi bo'lishi kerak")
            set_pw(u, new)
            audit(db, u, "parol o'zgartirildi", "", self.ip())
            save_db(db)
            return self.send_json(200, {"ok": True})

        # ---- ochiq: narx kalkulyatori va ofislar
        if method == "POST" and path == "/api/calc":
            d = self.body()
            try:
                f = lambda k: min(max(float(d.get(k) or 0), 0), 1000)
                if f("weight") <= 0:
                    return self.err(400, "Og'irlikni kiriting")
                return self.send_json(200, compute_quote(db, f("weight"), f("length"), f("width"), f("height"), bool(d.get("door_delivery")), 0))
            except (TypeError, ValueError):
                return self.err(400, "Qiymatlar son bo'lishi kerak")

        if method == "GET" and path == "/api/public/offices":
            return self.send_json(200, {"offices": [{"code": b["code"], "name": b["name"], "region": b.get("region", ""),
                                                     "district": b.get("district", ""), "address": b.get("address", "")} for b in db["dict"]["branches"]],
                                        "regions": db["dict"]["regions"], "org": db["dict"].get("org", {})})

        # ---- mijoz kabineti
        if method == "POST" and path == "/api/register":
            d = self.body()
            key = (self.ip(), "register")
            recent = [t for t in FAILS.get(key, []) if t > time.time() - FAIL_WINDOW]
            if len(recent) >= MAX_FAILS:
                return self.err(429, "Juda ko'p urinish. Keyinroq qayta urinib ko'ring")
            FAILS[key] = recent + [time.time()]
            name = clean_text(d.get("name"), "name")
            phone = norm_phone(d.get("phone"))
            pw = str(d.get("password", ""))
            if not phone:
                return self.err(400, "Telefon raqam noto'g'ri (masalan +998901234567)")
            if len(pw) < 8:
                return self.err(400, "Parol kamida 8 belgi bo'lishi kerak")
            if any(x["username"] == phone for x in db["users"]):
                return self.err(409, "Bu telefon raqam ro'yxatdan o'tgan")
            u = make_user(db["next_user"], phone, pw, "customer", name, phone)
            db["next_user"] += 1
            db["users"].append(u)
            audit(db, u, "mijoz ro'yxatdan o'tdi", phone, self.ip())
            save_db(db)
            token = secrets.token_hex(24)
            SESSIONS[token] = {"uid": u["id"], "exp": time.time() + SESSION_TTL}
            return self.send_json(201, {"token": token, "user": public_user(u)})

        if method == "GET" and path == "/api/my/orders":
            u = self.need("customer")
            if not u:
                return
            mine = [o for o in db["orders"] if u["phone"] in (o.get("sender_phone"), o.get("receiver_phone"))]
            return self.send_json(200, [dict(order_view(o, db), direction="out" if o.get("sender_phone") == u["phone"] else "in",
                                             pickup_code=o.get("pickup_code") if o["status"] not in FINAL else "") for o in reversed(mine)])

        if method == "POST" and path == "/api/my/orders":
            u = self.need("customer")
            if not u:
                return
            d = self.body()
            d.update(sender_name=u["name"], sender_phone=u["phone"], auto_price=True, payment_type="To'lanmagan", payer="Yuboruvchi")
            for k in ("courier_id", "price", "extra_service", "sender_branch", "barcode"):
                d.pop(k, None)
            c = validate_order(d, db)
            oid = db["next_order"]
            db["next_order"] += 1
            o = dict(c, id=oid, code="BTS-%05d" % oid, status=STATUSES[0], courier_id=None, cancel_reason="", online=True,
                     created=now(), created_by=u["name"], created_by_id=u["id"], office_address=office_address(db, c.get("sender_branch")),
                     pickup_code="%04d" % secrets.randbelow(10000),
                     history=[{"status": STATUSES[0], "time": now(), "by": u["name"] + " (onlayn)"}])
            db["orders"].append(o)
            upsert_customer(db, c["sender_name"], c["sender_phone"], c.get("sender_address"))
            upsert_customer(db, c["receiver_name"], c["receiver_phone"], c["address"])
            audit(db, u, "onlayn buyurtma", "%s, %s so'm" % (o["code"], money_int(o["price"])), self.ip())
            save_db(db)
            METRICS.inc("OrdersCreated")
            return self.send_json(201, order_view(o, db))

        m = re.fullmatch(r"/api/my/orders/(\d+)/cancel", path)
        if method == "POST" and m:
            u = self.need("customer")
            if not u:
                return
            o = next((x for x in db["orders"] if x["id"] == int(m.group(1)) and x.get("sender_phone") == u["phone"]), None)
            if not o:
                return self.err(404, "Buyurtma topilmadi")
            if o["status"] != STATUSES[0]:
                return self.err(400, "Faqat «%s» holatidagi buyurtmani bekor qilish mumkin" % STATUSES[0])
            o["status"], o["cancel_reason"] = "Bekor qilindi", "Mijoz bekor qildi"
            o["history"].append({"status": "Bekor qilindi", "time": now(), "by": u["name"], "reason": "Mijoz bekor qildi"})
            audit(db, u, "mijoz bekor qildi", o["code"], self.ip())
            save_db(db)
            return self.send_json(200, order_view(o, db))

        if method == "GET" and path == "/api/audit":
            if not self.need("admin"):
                return
            lim = max(1, min(int(q.get("limit", ["200"])[0] or 200), 1000))
            return self.send_json(200, list(reversed(db.get("audit", [])[-lim:])))

        # ---- inkassatsiya, KPI, smena hisoboti, shikoyatlar, harakat
        if path == "/api/collection" and method in ("GET", "POST"):
            u = self.need("operator", "admin")
            if not u:
                return
            code = u.get("branch", "")
            due = [o for o in db["orders"] if o["status"] == "Yetkazildi" and not o.get("collected") and o.get("payment_type", "Naqd") in ("", "Naqd")
                   and (not code or branch_code_of(o.get("sender_branch")) == code)]
            expected = money_int(sum(o["price"] for o in due))
            if method == "GET":
                hist = [c for c in db.get("collections", []) if not code or c["branch"] == code][-30:]
                return self.send_json(200, {"branch": code, "orders": len(due), "expected": expected, "history": list(reversed(hist)),
                                            "items": [{"code": o["code"], "price": o["price"]} for o in due][:200]})
            d = self.body()
            try:
                amount = money_int(float(d.get("amount")))
            except (TypeError, ValueError):
                return self.err(400, "Summa son bo'lishi kerak")
            if amount < 0:
                return self.err(400, "Summa noto'g'ri")
            for o in due:
                o["collected"] = now()
            rec = {"time": now(), "user": u["name"], "branch": code, "expected": expected, "amount": amount, "diff": amount - expected,
                   "orders": len(due), "note": clean_text(d.get("note"), "note", False)}
            db.setdefault("collections", []).append(rec)
            del db["collections"][:-500]
            audit(db, u, "inkassatsiya", "%s so'm (kutilgan %s)" % (amount, expected), self.ip())
            save_db(db)
            return self.send_json(201, rec)

        if method == "GET" and path == "/api/kpi":
            if not self.need("operator", "admin"):
                return
            df, dt = q.get("from", [""])[0], q.get("to", [""])[0]
            inr = lambda t: (not df or t[:10] >= df) and (not dt or t[:10] <= dt)
            rows = {}
            for u in db["users"]:
                if u["role"] in ("operator", "courier", "admin"):
                    rows[u["name"]] = {"name": u["name"], "role": u["role"], "created": 0, "created_sum": 0, "delivered": 0, "returned": 0, "avg_hours": None, "_h": []}
            for o in db["orders"]:
                if inr(o["created"]) and o.get("created_by") in rows and not o.get("online"):
                    r = rows[o["created_by"]]
                    r["created"] += 1
                    r["created_sum"] += money_int(o["price"])
                for h in o["history"]:
                    r = rows.get(h.get("by"))
                    if not r or not inr(h["time"]):
                        continue
                    if h["status"] == "Yetkazildi":
                        r["delivered"] += 1
                        try:
                            r["_h"].append((datetime.strptime(h["time"], "%Y-%m-%d %H:%M") - datetime.strptime(o["created"], "%Y-%m-%d %H:%M")).total_seconds() / 3600)
                        except ValueError:
                            pass
                    elif h["status"] == "Bekor qilindi":
                        r["returned"] += 1
            out = []
            for r in rows.values():
                hs = r.pop("_h")
                r["avg_hours"] = round(sum(hs) / len(hs), 1) if hs else None
                if r["created"] or r["delivered"] or r["returned"]:
                    out.append(r)
            return self.send_json(200, sorted(out, key=lambda r: -(r["created"] + r["delivered"])))

        if method == "GET" and path == "/api/shift/report":
            u = self.need("operator", "admin")
            if not u:
                return
            since = u.get("shift_started") or now()[:10] + " 00:00"
            mine = [o for o in db["orders"] if o.get("created_by_id") == u["id"] and o["created"] >= since]
            by = {}
            for o in mine:
                by[o.get("payment_type") or "Naqd"] = by.get(o.get("payment_type") or "Naqd", 0) + o["price"]
            return self.send_json(200, {"since": since, "office": office_of(db, u), "orders": len(mine), "sum": money_int(sum(o["price"] for o in mine)),
                                        "by_payment": {k: money_int(v) for k, v in by.items()}, "codes": [o["code"] for o in mine][-50:],
                                        "history": list(reversed([x for x in db.get("shifts", []) if x["user"] == u["name"]][-10:]))})

        if method == "POST" and path == "/api/shift/close":
            u = self.need("operator", "admin")
            if not u:
                return
            since = u.get("shift_started") or now()[:10] + " 00:00"
            mine = [o for o in db["orders"] if o.get("created_by_id") == u["id"] and o["created"] >= since]
            rec = {"user": u["name"], "branch": u.get("branch", ""), "start": since, "end": now(), "orders": len(mine), "sum": money_int(sum(o["price"] for o in mine))}
            db.setdefault("shifts", []).append(rec)
            del db["shifts"][:-500]
            u["shift_started"] = ""
            audit(db, u, "smena yopildi", "%d ta, %s so'm" % (rec["orders"], rec["sum"]), self.ip())
            save_db(db)
            return self.send_json(200, rec)

        if method == "GET" and path == "/api/movements":
            if not self.need("operator", "admin"):
                return
            lim = max(1, min(int(q.get("limit", ["100"])[0] or 100), 500))
            ev = [{"code": o["code"], "status": h["status"], "time": h["time"], "by": h.get("by", ""), "reason": h.get("reason", "")} for o in db["orders"] for h in o["history"]]
            ev.sort(key=lambda e: e["time"], reverse=True)
            return self.send_json(200, ev[:lim])

        if path == "/api/complaints" and method == "POST":
            u = self.need()
            if not u:
                return
            d = self.body()
            text = clean_text(d.get("text"), "note")
            if len(text) < 5:
                return self.err(400, "Shikoyat matnini yozing")
            rec = {"id": len(db.setdefault("complaints", [])) + 1, "time": now(), "user": u["name"], "role": u["role"], "phone": u.get("phone", ""),
                   "order": clean_text(d.get("order"), "code", False).upper(), "text": text, "status": "Yangi", "answer": ""}
            db["complaints"].append(rec)
            audit(db, u, "shikoyat", rec["order"], self.ip())
            save_db(db)
            return self.send_json(201, rec)

        if path == "/api/complaints" and method == "GET":
            u = self.need()
            if not u:
                return
            allc = db.get("complaints", [])
            if u["role"] == "customer":
                return self.send_json(200, list(reversed([c for c in allc if c["user"] == u["name"] and c["phone"] == u.get("phone", "")])))
            if u["role"] == "courier":
                return self.err(403, "Ruxsat yo'q")
            st = {}
            for c in allc:
                st[c["status"]] = st.get(c["status"], 0) + 1
            return self.send_json(200, {"items": list(reversed(allc)), "stats": st})

        m = re.fullmatch(r"/api/complaints/(\d+)", path)
        if m and method == "PUT":
            u = self.need("operator", "admin")
            if not u:
                return
            c = next((x for x in db.get("complaints", []) if x["id"] == int(m.group(1))), None)
            if not c:
                return self.err(404, "Shikoyat topilmadi")
            d = self.body()
            if d.get("status") not in ("Yangi", "Ko'rilmoqda", "Hal qilindi"):
                return self.err(400, "Holat noto'g'ri")
            c["status"], c["answer"] = d["status"], clean_text(d.get("answer"), "note", False)
            audit(db, u, "shikoyat holati", "#%d → %s" % (c["id"], c["status"]), self.ip())
            save_db(db)
            return self.send_json(200, c)

        # ---- ombor: qatorlar va shkaflar
        if method == "GET" and path == "/api/warehouse":
            if not self.need("operator", "admin"):
                return
            items = [{"id": o["id"], "code": o["code"], "product": o["product"], "weight": o.get("weight"), "status": o["status"], "created": o["created"],
                      "receiver": o["receiver_name"], "to": ", ".join(x for x in (o.get("receiver_region"), o.get("receiver_district")) if x),
                      "shelf": o.get("shelf", "")} for o in db["orders"] if o["status"] not in FINAL]
            shelves = {}
            for it in items:
                if it["shelf"]:
                    shelves[it["shelf"]] = shelves.get(it["shelf"], 0) + 1
            return self.send_json(200, {"items": list(reversed(items))[:500], "shelves": dict(sorted(shelves.items())), "unplaced": sum(1 for i in items if not i["shelf"])})

        m = re.fullmatch(r"/api/orders/(\d+)/shelf", path)
        if m and method == "POST":
            u = self.need("operator", "admin")
            if not u:
                return
            o = next((x for x in db["orders"] if x["id"] == int(m.group(1))), None)
            if not o:
                return self.err(404, "Buyurtma topilmadi")
            sh = re.sub(r"\s+", "", clean_text(self.body().get("shelf"), "shelf", False)).upper()
            if sh and not re.fullmatch(r"[A-Z0-9\-]{1,12}", sh):
                return self.err(400, "Shkaf belgisi noto'g'ri (masalan A-3)")
            o["shelf"] = sh
            audit(db, u, "shkafga joylandi", "%s → %s" % (o["code"], sh or "—"), self.ip())
            save_db(db)
            return self.send_json(200, {"code": o["code"], "shelf": sh})

        m = re.fullmatch(r"/api/orders/(\d+)/handover", path)
        if m and method == "POST":
            u = self.need("operator", "admin", "courier")
            if not u:
                return
            o = next((x for x in db["orders"] if x["id"] == int(m.group(1))), None)
            if not o or (u["role"] == "courier" and o.get("courier_id") != u["id"]):
                return self.err(404, "Buyurtma topilmadi")
            if o["status"] in FINAL:
                return self.err(400, "Buyurtma allaqachon yakunlangan")
            code = str(self.body().get("code", "")).strip()
            key = ("handover", o["id"])
            recent = [t for t in FAILS.get(key, []) if t > time.time() - FAIL_WINDOW]
            if len(recent) >= MAX_FAILS:
                return self.err(429, "Juda ko'p noto'g'ri urinish. 5 daqiqadan so'ng urinib ko'ring")
            if not o.get("pickup_code") or not hmac.compare_digest(code, o["pickup_code"]):
                FAILS[key] = recent + [time.time()]
                audit(db, u, "noto'g'ri topshirish kodi", o["code"], self.ip())
                return self.err(400, "Topshirish kodi noto'g'ri")
            FAILS.pop(key, None)
            o["status"] = "Yetkazildi"
            o["history"].append({"status": "Yetkazildi", "time": now(), "by": u["name"], "reason": "kod bilan topshirildi"})
            audit(db, u, "kod bilan topshirildi", o["code"], self.ip())
            save_db(db)
            return self.send_json(200, order_view(o, db))

        # ---- buyurtmalar
        if method == "GET" and path == "/api/orders":
            u = self.need("operator", "admin", "courier")
            if not u:
                return
            orders = db["orders"]
            if u["role"] == "courier":
                orders = [o for o in orders if o.get("courier_id") == u["id"]]
            orders = filter_orders(orders, q)
            per = max(1, min(int(q.get("per", ["15"])[0] or 15), 200))
            page = max(1, int(q.get("page", ["1"])[0] or 1))
            pages = max(1, -(-len(orders) // per))
            page = min(page, pages)
            items = [order_view(o, db) for o in orders[(page - 1) * per: page * per]]
            return self.send_json(200, {"items": items, "total": len(orders), "page": page, "pages": pages})

        if method == "GET" and path == "/api/orders/export":
            if not self.need("admin"):
                return
            data = orders_csv(db, filter_orders(db["orders"], q))
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="buyurtmalar.csv"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if method == "POST" and path == "/api/orders":
            u = self.need("operator", "admin")
            if not u:
                return
            d = self.body()
            c = validate_order(d, db)
            if not c.get("sender_branch") and u.get("branch"):         # smena ochilgan ofis jo'natuvchi joyi bo'ladi
                off = office_of(db, u)
                if off:
                    c["sender_region"], c["sender_district"] = off["region"], off["district"]
                    c["sender_branch"] = "%s - %s" % (off["code"], off["name"])
            cid = d.get("courier_id")
            if cid not in (None, ""):
                if not any(x["id"] == int(cid) and x["role"] == "courier" and x.get("active", True) for x in db["users"]):
                    return self.err(400, "Kuryer topilmadi")
                cid = int(cid)
            else:
                cid = None
            pay_phone = None
            if c.get("payment_type") == "Balans":
                pay_phone = c["receiver_phone"] if c["payer"] == "Qabul qiluvchi" else c["sender_phone"]
                bal = db["customers"].get(pay_phone, {}).get("balance", 0)
                if bal < c["price"]:
                    return self.err(400, "Shaxsiy hisobda mablag' yetarli emas (balans: %s so'm, kerak: %s so'm)" % (money_int(bal), money_int(c["price"])))
            oid = db["next_order"]
            db["next_order"] += 1
            o = dict(c, id=oid, code="BTS-%05d" % oid, status=STATUSES[0], courier_id=cid, cancel_reason="",
                     created=now(), created_by=u["name"], created_by_id=u["id"], office_address=office_address(db, c.get("sender_branch")),
                     pickup_code="%04d" % secrets.randbelow(10000),
                     history=[{"status": STATUSES[0], "time": now(), "by": u["name"]}])
            db["orders"].append(o)
            upsert_customer(db, c["sender_name"], c["sender_phone"], c.get("sender_address"))
            upsert_customer(db, c["receiver_name"], c["receiver_phone"], c["address"])
            if pay_phone:
                ledger_add(db["customers"][pay_phone], -c["price"], "order", u["name"], o["code"])
                o["paid_from_balance"] = True
                o["balance_phone"] = pay_phone
            wk = "waybills/%s.html" % o["code"]
            if thread_safe_cloud_call("waybill", lambda: (OBJECTS.put(wk, waybill_html(o), "text/html; charset=utf-8"), True)[1]):
                o["waybill_key"] = wk
            audit(db, u, "buyurtma yaratildi", "%s, %s so'm" % (o["code"], money_int(o["price"])), self.ip())
            save_db(db)
            METRICS.inc("OrdersCreated")
            return self.send_json(201, order_view(o, db))

        m = re.fullmatch(r"/api/orders/(\d+)(/status|/assign)?", path)
        if m:
            oid, sub = int(m.group(1)), m.group(2)
            o = next((x for x in db["orders"] if x["id"] == oid), None)
            if not o:
                return self.err(404, "Buyurtma topilmadi")

            if method == "PUT" and not sub:
                if not self.need("admin"):
                    return
                o.update(validate_order(self.body()))
                save_db(db)
                return self.send_json(200, order_view(o, db))

            if method == "DELETE" and not sub:
                if not self.need("admin"):
                    return
                db["orders"].remove(o)
                save_db(db)
                return self.send_json(200, {"ok": True})

            if method == "POST" and sub == "/status":
                u = self.need("admin", "courier")
                if not u:
                    return
                d = self.body()
                st = d.get("status")
                if st not in (STATUSES if u["role"] == "admin" else COURIER_STATUSES):
                    return self.err(400, "Holat noto'g'ri")
                if u["role"] == "courier":
                    if o.get("courier_id") != u["id"]:
                        return self.err(403, "Bu buyurtma sizga biriktirilmagan")
                    if o["status"] in FINAL:
                        return self.err(400, "Yakunlangan buyurtma holatini kuryer o'zgartira olmaydi")
                if st == o["status"]:
                    return self.send_json(200, order_view(o, db))
                reason = clean_text(d.get("reason"), "note", required=False)
                if st == "Bekor qilindi" and not reason:
                    return self.err(400, "Bekor qilish sababini kiriting")
                if st == "Bekor qilindi" and o.get("paid_from_balance") and not o.get("refunded"):
                    cust = db["customers"].get(o.get("balance_phone"))
                    if cust:
                        ledger_add(cust, o["price"], "refund", u["name"], o["code"])
                        o["refunded"] = True
                o["status"] = st
                o["cancel_reason"] = reason if st == "Bekor qilindi" else ""
                o["history"].append({"status": st, "time": now(), "by": u["name"], **({"reason": reason} if reason else {})})
                audit(db, u, "holat o'zgardi", "%s → %s" % (o["code"], st), self.ip())
                save_db(db)
                return self.send_json(200, order_view(o, db))

            if method == "POST" and sub == "/assign":
                u = self.need("admin", "operator")
                if not u:
                    return
                cid = self.body().get("courier_id")
                if cid in (None, ""):
                    o["courier_id"] = None
                else:
                    c = next((x for x in db["users"] if x["id"] == int(cid) and x["role"] == "courier" and x.get("active", True)), None)
                    if not c:
                        return self.err(400, "Kuryer topilmadi")
                    o["courier_id"] = c["id"]
                save_db(db)
                return self.send_json(200, order_view(o, db))
            return self.err(405, "Metod ruxsat etilmagan")

        # ---- bulut: fayllar, eksport, holat
        m = re.fullmatch(r"/api/orders/(\d+)/files(?:/(\d+))?", path)
        if m:
            u = self.need("admin", "operator", "courier")
            if not u:
                return
            o = next((x for x in db["orders"] if x["id"] == int(m.group(1))), None)
            if not o or (u["role"] == "courier" and o.get("courier_id") != u["id"]):
                return self.err(404, "Buyurtma topilmadi")
            files = o.setdefault("files", [])
            idx = m.group(2)
            if method == "POST" and idx is None:
                d = self.body(limit=int(MAX_UPLOAD * 1.4) + 4096)
                ctype = str(d.get("type", "")).lower()
                if ctype not in UPLOAD_TYPES:
                    return self.err(400, "Faqat rasm (JPG, PNG, WEBP) yoki PDF yuklash mumkin")
                try:
                    raw = base64.b64decode(str(d.get("data", "")), validate=True)
                except Exception:
                    return self.err(400, "Fayl ma'lumoti noto'g'ri")
                if not raw or len(raw) > MAX_UPLOAD:
                    return self.err(400, "Fayl hajmi 5 MB dan oshmasligi kerak")
                if not raw.startswith(UPLOAD_TYPES[ctype]):
                    return self.err(400, "Fayl mazmuni turiga mos emas")
                if len(files) >= 20:
                    return self.err(400, "Bitta buyurtmaga ko'pi bilan 20 ta fayl")
                name = safe_name(d.get("name"))
                key = "orders/%s/%s-%s" % (o["code"], secrets.token_hex(4), name)
                try:
                    OBJECTS.put(key, raw, ctype)
                except Exception as ex:
                    cloud.log_json("cloud_error", op="upload", error="%s: %s" % (type(ex).__name__, ex))
                    return self.err(502, "Faylni saqlab bo'lmadi (obyektli saqlash xizmati javob bermadi)")
                kind = "Yetkazish isboti" if str(d.get("kind")) == "proof" else "Ilova"
                files.append({"key": key, "name": name, "size": len(raw), "type": ctype, "kind": kind, "time": now(), "by": u["name"]})
                save_db(db)
                METRICS.inc("FilesUploaded")
                return self.send_json(201, order_view(o, db))
            if idx is not None and method == "GET":
                if int(idx) >= len(files):
                    return self.err(404, "Fayl topilmadi")
                f = files[int(idx)]
                return self.send_json(200, {"url": OBJECTS.url(f["key"], f["name"]), "expires_s": 300})
            if idx is not None and method == "DELETE":
                if u["role"] != "admin":
                    return self.err(403, "Ruxsat yo'q")
                if int(idx) >= len(files):
                    return self.err(404, "Fayl topilmadi")
                f = files.pop(int(idx))
                thread_safe_cloud_call("delete", lambda: OBJECTS.delete(f["key"]))
                save_db(db)
                return self.send_json(200, order_view(o, db))
            return self.err(405, "Metod ruxsat etilmagan")

        if method == "GET" and path == "/api/orders/waybill":
            u = self.need("admin", "operator")
            if not u:
                return
            o = next((x for x in db["orders"] if x["code"] == q.get("code", [""])[0]), None)
            if not o or not o.get("waybill_key"):
                return self.err(404, "Yo'l varaqasi S3'da topilmadi")
            return self.send_json(200, {"url": OBJECTS.url(o["waybill_key"], o["code"] + ".html"), "expires_s": 300})

        if path == "/api/exports" and method == "POST":
            if not self.need("admin"):
                return
            data = orders_csv(db, filter_orders(db["orders"], q))
            key = "exports/orders-%s.csv" % datetime.now().strftime("%Y%m%d-%H%M%S")
            try:
                OBJECTS.put(key, data, "text/csv; charset=utf-8")
            except Exception as ex:
                cloud.log_json("cloud_error", op="export", error="%s: %s" % (type(ex).__name__, ex))
                return self.err(502, "Eksportni saqlab bo'lmadi (obyektli saqlash xizmati javob bermadi)")
            METRICS.inc("FilesUploaded")
            return self.send_json(201, {"key": key, "size": len(data), "url": OBJECTS.url(key, os.path.basename(key))})

        if path == "/api/exports" and method == "GET":
            if not self.need("admin"):
                return
            items = sorted(OBJECTS.list("exports/"), key=lambda x: x["key"], reverse=True)[:50]
            for it in items:
                it["url"] = OBJECTS.url(it["key"], os.path.basename(it["key"]))
            return self.send_json(200, {"items": items, "target": OBJECTS.info()["target"]})

        if path == "/api/cloud/status" and method == "GET":
            if not self.need("admin"):
                return
            try:
                dbinfo = STORE.info() if hasattr(STORE, "info") else {}
                dbinfo["ok"] = bool(STORE.ping())
            except Exception as ex:
                dbinfo = {"kind": STORE.kind, "ok": False, "error": "%s: %s" % (type(ex).__name__, ex)}
            return self.send_json(200, {
                "app": {"version": VERSION, "uptime_s": int(time.time() - STARTED), "host": socket.gethostname(),
                        "python": platform.python_version(), "os": platform.platform(), "trust_proxy": CFG.trust_proxy},
                "ec2": instance_meta(),
                "database": dbinfo,
                "objects": dict(OBJECTS.info(), region=CFG.region),
                "monitoring": {"namespace": CFG.cw_namespace or None, "counters": METRICS.snapshot(),
                               "last_push": METRICS.last_push, "last_error": METRICS.last_error}})

        if path == "/api/cloud/selftest" and method == "POST":
            if not self.need("admin"):
                return
            checks = []
            marker = secrets.token_hex(4)
            if hasattr(STORE, "roundtrip"):
                try:
                    ok = STORE.roundtrip(marker)
                    checks.append({"name": "Ma'lumotlar bazasi (%s): yozish-o'qish-o'chirish" % STORE.kind, "ok": bool(ok), "detail": "marker " + marker})
                except Exception as ex:
                    checks.append({"name": "Ma'lumotlar bazasi", "ok": False, "detail": "%s: %s" % (type(ex).__name__, ex)})
            else:
                checks.append({"name": "Ma'lumotlar bazasi", "ok": True, "detail": "JSON fayl rejimi (BTS_STORAGE=postgres qilinsa RDS tekshiriladi)"})
            key = "selftest/%s.txt" % marker
            try:
                OBJECTS.put(key, marker.encode(), "text/plain")
                back, _ = OBJECTS.get(key)
                OBJECTS.delete(key)
                checks.append({"name": "Obyektli saqlash (%s): put-get-delete" % OBJECTS.kind, "ok": back == marker.encode(), "detail": OBJECTS.info()["target"] + key})
            except Exception as ex:
                checks.append({"name": "Obyektli saqlash", "ok": False, "detail": "%s: %s" % (type(ex).__name__, ex)})
            r = METRICS.selftest()
            checks.append({"name": "CloudWatch metrika", "ok": r["ok"], "detail": r["detail"]})
            cloud.log_json("selftest", checks=[(c["name"], c["ok"]) for c in checks])
            return self.send_json(200, {"time": now(), "checks": checks})

        # ---- kuryerlar (tanlash uchun)
        if method == "GET" and path == "/api/couriers":
            if not self.need("admin", "operator"):
                return
            active = [x for x in db["users"] if x["role"] == "courier" and x.get("active", True)]
            out = []
            for c in active:
                v = public_user(c)
                v["open"] = sum(1 for o in db["orders"] if o.get("courier_id") == c["id"] and o["status"] not in FINAL)
                out.append(v)
            return self.send_json(200, out)

        # ---- mijozlar
        if method == "GET" and path == "/api/customers":
            if not self.need("admin", "operator"):
                return
            s = q.get("q", [""])[0].lower().strip()
            items = [c for c in db["customers"].values() if not s or s in c["name"].lower() or s in c["phone"]]
            items.sort(key=lambda c: c.get("last", ""), reverse=True)
            lim = int(q.get("limit", ["200"])[0] or 200)
            return self.send_json(200, items[:lim])

        if method == "GET" and path == "/api/customers/balance":
            if not self.need("admin", "operator"):
                return
            phone = norm_phone(q.get("phone", [""])[0])
            if not phone:
                return self.err(400, "Telefon raqam noto'g'ri")
            c = db["customers"].get(phone)
            return self.send_json(200, {"phone": phone, "name": c["name"] if c else "", "exists": bool(c),
                                        "balance": c.get("balance", 0) if c else 0,
                                        "ledger": list(reversed(c.get("ledger", [])[-15:])) if c else []})

        if method == "POST" and path == "/api/customers/topup":
            u = self.need("admin", "operator")
            if not u:
                return
            d = self.body()
            phone = norm_phone(d.get("phone"))
            if not phone:
                return self.err(400, "Telefon raqam noto'g'ri")
            try:
                amount = float(d.get("amount"))
            except (TypeError, ValueError):
                return self.err(400, "Summa son bo'lishi kerak")
            if not 1 <= amount <= 1e9:
                return self.err(400, "Summa 1 dan 1 000 000 000 gacha bo'lishi kerak")
            cust = db["customers"].get(phone)
            if not cust:
                name = clean_text(d.get("name"), "name", required=False)
                if not name:
                    return self.err(400, "Yangi mijoz uchun ismni kiriting")
                cust = db["customers"][phone] = {"phone": phone, "name": name, "address": "", "orders": 0, "created": now(), "balance": 0, "ledger": []}
            ledger_add(cust, round(amount, 2), "topup", u["name"])
            save_db(db)
            return self.send_json(200, {"phone": phone, "name": cust["name"], "balance": cust["balance"]})

        # ---- foydalanuvchilar (admin)
        if path == "/api/users" and method == "GET":
            if not self.need("admin"):
                return
            return self.send_json(200, [public_user(x) for x in db["users"]])

        if path == "/api/users" and method == "POST":
            if not self.need("admin"):
                return
            d = self.body()
            name = clean_text(d.get("name"), "name")
            username = re.sub(r"\s", "", str(d.get("username", "")))
            pw, role = str(d.get("password", "")), d.get("role")
            if role not in ROLES:
                return self.err(400, "Rol noto'g'ri")
            if len(username) < 3 or len(pw) < 6:
                return self.err(400, "Login kamida 3, parol kamida 6 belgi bo'lishi kerak")
            if any(x["username"].lower() == username.lower() for x in db["users"]):
                return self.err(400, "Bu login band")
            phone = norm_phone(d.get("phone")) if d.get("phone") else ""
            if d.get("phone") and not phone:
                return self.err(400, "Telefon raqam noto'g'ri")
            u = make_user(db["next_user"], username, pw, role, name, phone)
            bc = branch_code_of(d.get("branch"))
            if bc and not find_branch(db, bc):
                return self.err(400, "Ofis topilmadi")
            u["branch"] = bc
            db["next_user"] += 1
            db["users"].append(u)
            audit(db, self.user(), "foydalanuvchi qo'shildi", "%s (%s)" % (username, role), self.ip())
            save_db(db)
            return self.send_json(201, public_user(u))

        m = re.fullmatch(r"/api/users/(\d+)", path)
        if m:
            me = self.need("admin")
            if not me:
                return
            uid = int(m.group(1))
            u = next((x for x in db["users"] if x["id"] == uid), None)
            if not u:
                return self.err(404, "Foydalanuvchi topilmadi")
            admins = [x for x in db["users"] if x["role"] == "admin" and x.get("active", True)]
            if method == "PUT":
                d = self.body()
                if "name" in d:
                    u["name"] = clean_text(d["name"], "name")
                if "phone" in d:
                    ph = norm_phone(d["phone"]) if d["phone"] else ""
                    if d["phone"] and not ph:
                        return self.err(400, "Telefon raqam noto'g'ri")
                    u["phone"] = ph
                if "branch" in d:
                    bc = branch_code_of(d["branch"])
                    if bc and not find_branch(db, bc):
                        return self.err(400, "Ofis topilmadi")
                    u["branch"] = bc
                if d.get("password"):
                    if len(str(d["password"])) < 6:
                        return self.err(400, "Parol kamida 6 belgi bo'lishi kerak")
                    u["salt"] = secrets.token_hex(8)
                    set_pw(u, str(d["password"]))
                if "active" in d:
                    if not d["active"] and u["id"] == me["id"]:
                        return self.err(400, "O'zingizni o'chira olmaysiz")
                    if not d["active"] and u["role"] == "admin" and len(admins) <= 1:
                        return self.err(400, "Oxirgi administratorni o'chirib bo'lmaydi")
                    u["active"] = bool(d["active"])
                    if not u["active"]:
                        for t in [t for t, s in SESSIONS.items() if s["uid"] == uid]:
                            SESSIONS.pop(t)
                save_db(db)
                return self.send_json(200, public_user(u))
            if method == "DELETE":
                if u["id"] == me["id"]:
                    return self.err(400, "O'zingizni o'chira olmaysiz")
                if u["role"] == "admin" and len(admins) <= 1:
                    return self.err(400, "Oxirgi administratorni o'chirib bo'lmaydi")
                db["users"].remove(u)
                audit(db, me, "foydalanuvchi o'chirildi", u["username"], self.ip())
                for o in db["orders"]:
                    if o.get("courier_id") == uid:
                        o["courier_id"] = None
                for t in [t for t, s in SESSIONS.items() if s["uid"] == uid]:
                    SESSIONS.pop(t)
                save_db(db)
                return self.send_json(200, {"ok": True})

        # ---- tarif
        if path == "/api/tariff" and method == "GET":
            if not self.need():
                return
            return self.send_json(200, db["settings"])
        if path == "/api/tariff" and method == "PUT":
            if not self.need("admin"):
                return
            d, t = self.body(), dict(db["settings"])
            try:
                for k, lo, required in TARIFF_KEYS:
                    if d.get(k) in (None, "") and not required:
                        continue
                    v = float(d.get(k))
                    if v < lo or v > 1e8:
                        raise ValueError
                    t[k] = int(v) if v == int(v) else v
            except (TypeError, ValueError):
                return self.err(400, "Tarif qiymatlari noto'g'ri")
            db["settings"] = t
            save_db(db)
            return self.send_json(200, t)

        if path == "/api/quote" and method == "POST":
            if not self.need():
                return
            d = self.body()
            try:
                f = lambda k: float(d.get(k) or 0)
                return self.send_json(200, compute_quote(db, f("weight"), f("length"), f("width"), f("height"),
                                                         bool(d.get("door_delivery")), f("extra_service")))
            except (TypeError, ValueError):
                return self.err(400, "Qiymatlar son bo'lishi kerak")

        # ---- ma'lumotnomalar
        if path == "/api/dict" and method == "GET":
            if not self.need():
                return
            return self.send_json(200, db["dict"])
        if path == "/api/dict" and method == "PUT":
            if not self.need("admin"):
                return
            d, out = self.body(), {}
            try:
                regs = d.get("regions")
                if not isinstance(regs, dict) or not regs:
                    raise ValueError("Kamida bitta viloyat kerak")
                out["regions"] = {clean_text(k, "region"): [clean_text(x, "district") for x in v if str(x).strip()] for k, v in regs.items()}
                out["branches"] = [{"code": clean_text(b.get("code"), "code"), "name": clean_text(b.get("name"), "name"),
                                    "region": clean_text(b.get("region"), "region", False),
                                    "district": clean_text(b.get("district"), "district", False),
                                    "address": clean_text(b.get("address"), "address", False)} for b in d.get("branches", [])]
                for k in ("contents", "packages", "payment_types", "transports"):
                    out[k] = [clean_text(x, k) for x in d.get(k, []) if str(x).strip()]
                    if not out[k]:
                        raise ValueError("Ro'yxat bo'sh bo'lmasligi kerak: " + k)
                org = d.get("org") or {}
                out["org"] = {k: clean_text(org.get(k), k, False) for k in ("name", "inn", "address", "site")}
            except (ValueError, AttributeError, TypeError) as e:
                return self.err(400, str(e) if isinstance(e, ValueError) else "Ma'lumot formati noto'g'ri")
            db["dict"] = out
            save_db(db)
            return self.send_json(200, out)

        # ---- operatorning shaxsiy ko'rsatkichlari
        if method == "GET" and path == "/api/mystats":
            u = self.need("operator", "admin")
            if not u:
                return
            mine = [o for o in db["orders"] if o.get("created_by_id") == u["id"]
                    or (not o.get("created_by_id") and o.get("created_by") == u["name"])]
            today = datetime.now().date()
            iso = today.isoformat()
            days = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
            s = {st: sum(1 for o in mine if o["status"] == st) for st in STATUSES}
            s.update(total=len(mine), today=sum(1 for o in mine if o["created"][:10] == iso),
                     week=sum(1 for o in mine if o["created"][:10] >= days[0]),
                     today_sum=sum(o["price"] for o in mine if o["created"][:10] == iso),
                     all_today=sum(1 for o in db["orders"] if o["created"][:10] == iso),
                     days=[{"date": d, "count": sum(1 for o in mine if o["created"][:10] == d)} for d in days])
            return self.send_json(200, s)

        # ---- statistika
        if method == "GET" and path == "/api/stats":
            if not self.need("admin"):
                return
            orders = db["orders"]
            s = {st: sum(1 for o in orders if o["status"] == st) for st in STATUSES}
            s["total"] = len(orders)
            s["revenue"] = sum(o["price"] for o in orders if o["status"] == "Yetkazildi")
            s["pending_revenue"] = sum(o["price"] for o in orders if o["status"] in STATUSES[:2])
            s["unassigned"] = sum(1 for o in orders if not o.get("courier_id") and o["status"] not in FINAL)
            s["customers"] = len(db["customers"])
            today = datetime.now().date()
            days = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
            s["days"] = [{"date": d, "count": sum(1 for o in orders if o["created"][:10] == d)} for d in days]
            s["couriers"] = [{"name": c["name"],
                              "delivered": sum(1 for o in orders if o.get("courier_id") == c["id"] and o["status"] == "Yetkazildi"),
                              "open": sum(1 for o in orders if o.get("courier_id") == c["id"] and o["status"] not in FINAL)}
                             for c in db["users"] if c["role"] == "courier" and c.get("active", True)]
            # --- kengaytirilgan ko'rsatkichlar
            cnt = lambda it: sorted(it.items(), key=lambda kv: -kv[1])
            reg, pay, cus = {}, {}, {}
            for o in orders:
                r = o.get("receiver_region") or "Ko'rsatilmagan"
                reg[r] = reg.get(r, 0) + 1
                p = o.get("payment_type") or "Ko'rsatilmagan"
                pay[p] = pay.get(p, 0) + 1
                cus[o["sender_name"]] = cus.get(o["sender_name"], 0) + 1
            s["by_region"] = [{"name": k, "count": v} for k, v in cnt(reg)[:8]]
            s["by_payment"] = [{"name": k, "count": v} for k, v in cnt(pay)]
            s["top_customers"] = [{"name": k, "count": v} for k, v in cnt(cus)[:5]]
            days14 = [(today - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
            s["trend"] = [{"date": d, "count": sum(1 for o in orders if o["created"][:10] == d),
                           "revenue": money_int(sum(o["price"] for o in orders if o["created"][:10] == d and o["status"] != "Bekor qilindi"))} for d in days14]
            lim = (datetime.now() - timedelta(hours=72)).strftime("%Y-%m-%d %H:%M")
            late = [o for o in orders if o["status"] not in FINAL and o["created"] < lim]
            s["overdue"] = [{"code": o["code"], "created": o["created"], "receiver": o["receiver_name"], "status": o["status"],
                             "courier": next((c["name"] for c in db["users"] if c["id"] == o.get("courier_id")), "—")} for o in late[:20]]
            s["overdue_count"] = len(late)
            hrs = []
            for o in orders:
                d_ = next((h["time"] for h in o["history"] if h["status"] == "Yetkazildi"), None)
                if d_:
                    try:
                        hrs.append((datetime.strptime(d_, "%Y-%m-%d %H:%M") - datetime.strptime(o["created"], "%Y-%m-%d %H:%M")).total_seconds() / 3600)
                    except ValueError:
                        pass
            s["avg_hours"] = round(sum(hrs) / len(hrs), 1) if hrs else None
            s["delivery_rate"] = round(100 * s["Yetkazildi"] / len(orders)) if orders else 0
            s["online"] = sum(1 for o in orders if o.get("online"))
            s["open_complaints"] = sum(1 for c in db.get("complaints", []) if c.get("status") != "Hal qilindi")
            s["unplaced"] = sum(1 for o in orders if o["status"] not in FINAL and not o.get("shelf"))
            s["users_by_role"] = {r: sum(1 for x in db["users"] if x["role"] == r and x.get("active", True)) for r in ("admin", "operator", "courier", "customer")}
            for c in s["couriers"]:
                c["rate"] = round(100 * c["delivered"] / (c["delivered"] + c["open"])) if c["delivered"] + c["open"] else 0
            return self.send_json(200, s)

        # ---- kuryer statistikasi
        if method == "GET" and path == "/api/courier/stats":
            u = self.need("courier")
            if not u:
                return
            fee = db["settings"].get("courier_fee", 0)
            mine = [o for o in db["orders"] if o.get("courier_id") == u["id"]]
            today = datetime.now().date()
            dt = lambda o: next((h["time"] for h in reversed(o["history"]) if h["status"] == "Yetkazildi"), "")
            done = [(o, dt(o)) for o in mine if o["status"] == "Yetkazildi"]
            day = lambda n: (today - timedelta(days=n)).isoformat()
            cnt_since = lambda d: sum(1 for _o, t in done if t[:10] >= d)
            days = [{"date": day(i), "count": sum(1 for _o, t in done if t[:10] == day(i))} for i in range(6, -1, -1)]
            hrs = []
            for o, t in done:
                try:
                    hrs.append((datetime.strptime(t, "%Y-%m-%d %H:%M") - datetime.strptime(o["created"], "%Y-%m-%d %H:%M")).total_seconds() / 3600)
                except ValueError:
                    pass
            fin = len(done) + sum(1 for o in mine if o["status"] == "Bekor qilindi")
            return self.send_json(200, {"active": sum(1 for o in mine if o["status"] not in FINAL), "today": cnt_since(day(0)), "week": cnt_since(day(6)),
                                        "month": cnt_since(day(29)), "total": len(done), "cancelled": sum(1 for o in mine if o["status"] == "Bekor qilindi"),
                                        "rate": round(100 * len(done) / fin) if fin else 0, "avg_hours": round(sum(hrs) / len(hrs), 1) if hrs else None,
                                        "fee": fee, "earn_today": money_int(fee * cnt_since(day(0))), "earn_month": money_int(fee * cnt_since(day(29))),
                                        "sum_today": money_int(sum(o["price"] for o, t in done if t[:10] == day(0))), "days": days})

        self.err(404, "Topilmadi")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    bind = os.environ.get("BIND", "0.0.0.0")          # nginx ortida ishlaganda BIND=127.0.0.1
    print("BTS Express ishga tushdi: http://localhost:%d  (ma'lumotlar: %s, fayllar: %s)" % (port, STORE.kind, OBJECTS.kind))
    cloud.log_json("startup", version=VERSION, storage=STORE.kind, objects=OBJECTS.kind, port=port)
    ThreadingHTTPServer((bind, port), Handler).serve_forever()
