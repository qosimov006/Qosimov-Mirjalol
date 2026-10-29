"""API testlari: python3 tests/test_api.py  (vaqtinchalik baza bilan, asl ma'lumotga tegmaydi)"""
import json, os, subprocess, sys, tempfile, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8791
B = "http://localhost:%d/api" % PORT
tmp = tempfile.mkdtemp()
env = dict(os.environ, PORT=str(PORT), BTS_DB=os.path.join(tmp, "db.json"), BTS_FILES=os.path.join(tmp, "files"))
srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py")], env=env, stdout=subprocess.DEVNULL)
time.sleep(1.2)
fails = []


def call(method, path, body=None, tok=None):
    req = urllib.request.Request(B + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + tok} if tok else {})})
    try:
        r = urllib.request.urlopen(req)
        raw = r.read().decode()
        return r.status, (json.loads(raw) if r.headers.get_content_type() == "application/json" else raw)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def check(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def login(u, p):
    s, d = call("POST", "/login", {"username": u, "password": p})
    return d.get("token")


try:
    A, O, K = login("admin", "admin123"), login("operator", "operator123"), login("kuryer1", "kuryer123")
    check("login 3 rol", all([A, O, K]))
    check("noto'g'ri parol 401", call("POST", "/login", {"username": "admin", "password": "x"})[0] == 401)
    for _ in range(6):
        s, _d = call("POST", "/login", {"username": "zzz", "password": "x"})
    check("login throttling 429", s == 429)

    order = {"sender_name": "Ali", "sender_phone": "90 123 45 67", "receiver_name": "Vali", "receiver_phone": "+998 91 765 43 21",
             "address": "Toshkent", "product": "Kitob", "weight": "1.5", "price": "25000", "payer": "Qabul qiluvchi"}
    s, o = call("POST", "/orders", order, O)
    check("buyurtma yaratish + telefon normallashtirish", s == 201 and o["sender_phone"] == "+998901234567" and o["code"] == "BTS-00001")
    s, me_ = call("GET", "/me", None, O)
    check("operator ofisi 0112", me_.get("office", {}).get("code") == "0112" and "Farg'ona yo'li" in me_["office"]["address"])
    check("yorliq manzili = ofis manzili", "Farg'ona yo'li" in o.get("office_address", "") and o["sender_branch"].startswith("0112"))
    s, d_ = call("GET", "/dict", None, O); br = next(b for b in d_["branches"] if b["code"] != "0112")
    check("noto'g'ri ofis 400", call("POST", "/shift", {"branch": "nope"}, O)[0] == 400)
    s, me2 = call("POST", "/shift", {"branch": br["code"]}, O)
    check("smena boshqa ofisda", s == 200 and me2["office"]["code"] == br["code"])
    s, o2 = call("POST", "/orders", order, O)
    check("yangi buyurtma yangi ofis manzili bilan", s == 201 and o2["office_address"] == br["address"] and o2["office_address"] != o["office_address"])
    call("POST", "/shift", {"branch": "0112"}, O)
    check("shtrix-kod 12 xonali", len(o.get("barcode", "")) == 12 and o["barcode"].endswith("%08d" % o["id"]))
    s, t = call("GET", "/track?id=" + o["barcode"][:3] + "%20" + o["barcode"][3:6] + "%20" + o["barcode"][6:])
    check("shtrix-kod bo'yicha kuzatuv (probelli ham)", s == 200 and t["code"] == o["code"] and "sender_phone" not in t and "receiver_phone" not in t)
    check("kuryer buyurtma yarata olmaydi", call("POST", "/orders", order, K)[0] == 403)
    check("tokensiz 401", call("GET", "/orders")[0] == 401)
    check("validatsiya: telefon", call("POST", "/orders", {**order, "sender_phone": "123"}, O)[0] == 400)
    check("validatsiya: og'irlik", call("POST", "/orders", {**order, "weight": "-1"}, O)[0] == 400)
    check("validatsiya: bo'sh maydon", call("POST", "/orders", {**order, "address": " "}, O)[0] == 400)

    s, c = call("GET", "/customers", None, O)
    check("mijozlar avtomatik saqlandi", s == 200 and len(c) == 2)
    check("kuryer mijozlarni ko'ra olmaydi", call("GET", "/customers", None, K)[0] == 403)

    check("kuryer hozircha buyurtmani ko'rmaydi", call("GET", "/orders", None, K)[1]["total"] == 0)
    check("kuryer holat o'zgartira olmaydi (biriktirilmagan)", call("POST", "/orders/1/status", {"status": "Yo'lda"}, K)[0] == 403)
    check("operator biriktira oladi", call("POST", "/orders/1/assign", {"courier_id": 3}, O)[0] == 200)
    check("kuryer endi ko'radi", call("GET", "/orders", None, K)[1]["total"] == 1)
    check("kuryer: Yo'lda", call("POST", "/orders/1/status", {"status": "Yo'lda"}, K)[1]["status"] == "Yo'lda")
    check("bekor qilish sababsiz 400", call("POST", "/orders/1/status", {"status": "Bekor qilindi"}, K)[0] == 400)
    check("kuryer: Yetkazildi", call("POST", "/orders/1/status", {"status": "Yetkazildi"}, K)[1]["status"] == "Yetkazildi")
    check("kuryer yakunlangan holatni o'zgartira olmaydi", call("POST", "/orders/1/status", {"status": "Yo'lda"}, K)[0] == 400)
    check("admin yakunlanganni qaytara oladi", call("POST", "/orders/1/status", {"status": "Yo'lda"}, A)[0] == 200)
    s, o = call("POST", "/orders/1/status", {"status": "Bekor qilindi", "reason": "Mijoz rad etdi"}, A)
    check("sabab bilan bekor qilish", s == 200 and o["cancel_reason"] == "Mijoz rad etdi")
    check("operator o'chira olmaydi", call("DELETE", "/orders/1", None, O)[0] == 403)
    check("operator tahrir qila olmaydi", call("PUT", "/orders/1", order, O)[0] == 403)
    check("admin tahrirlaydi", call("PUT", "/orders/1", {**order, "product": "Telefon"}, A)[1]["product"] == "Telefon")

    s, t = call("GET", "/track?id=1")
    check("kuzatuv (raqam bilan) va maxfiy maydonlar yo'q", s == 200 and t["code"] == "BTS-00001" and "receiver_phone" not in t and "by" not in t["history"][0])
    check("kuzatuv: topilmadi 404", call("GET", "/track?id=BTS-99999")[0] == 404)

    for i in range(14):
        call("POST", "/orders", order, O)
    s, r = call("GET", "/orders?per=10&page=2", None, A)
    check("sahifalash", r["total"] == 16 and r["pages"] == 2 and len(r["items"]) == 6)
    check("qidiruv/filtr", call("GET", "/orders?q=telefon", None, A)[1]["total"] == 1 and call("GET", "/orders?status=Bekor%20qilindi", None, A)[1]["total"] == 1)
    s, csvtxt = call("GET", "/orders/export", None, A)
    check("CSV eksport", s == 200 and csvtxt.count("\n") >= 16 and "BTS-00001" in csvtxt)

    check("tarif o'qish", call("GET", "/tariff", None, O)[1]["per_kg"] == 3000)
    check("operator tarifni o'zgartira olmaydi", call("PUT", "/tariff", {"base": 1, "per_kg": 1, "free_kg": 0, "round_to": 1}, O)[0] == 403)
    check("tarif noto'g'ri qiymat 400", call("PUT", "/tariff", {"base": -5, "per_kg": 1, "free_kg": 0, "round_to": 1}, A)[0] == 400)
    check("admin tarifni yangilaydi", call("PUT", "/tariff", {"base": 12000, "per_kg": 3500, "free_kg": 1, "round_to": 500}, A)[1]["base"] == 12000)
    full = {**order, "auto_price": True, "weight": "3", "door_delivery": True, "extra_service": 1000, "price": "",
            "receiver_branch": "0112 - QO'YLIQ", "length": 0, "width": 0, "height": 0, "quantity": 2, "by_call": True, "receiver_phone2": "93 695 38 79"}
    s, fo = call("POST", "/orders", full, O)
    check("avto narx: 19000 + yetkazish 10000 + xizmat 1000 + QQS 12%", s == 201 and fo["price_net"] == 30000 and fo["vat_amount"] == 3600 and fo["price"] == 33600)
    s, fo = call("POST", "/orders", {**full, "weight": "1", "length": 50, "width": 40, "height": 30, "door_delivery": False, "extra_service": 0}, O)
    check("hajm og'irligi (50x40x30/5000=12kg)", s == 201 and fo["vol_weight"] == 12 and fo["price_net"] == 50500)
    s, fo = call("POST", "/orders", {**full, "address": "", "door_delivery": False}, O)
    check("manzilsiz: filial bo'yicha manzil", s == 201 and fo["address"].startswith("Filial: 0112"))
    check("manzil ham filial ham yo'q 400", call("POST", "/orders", {**full, "address": "", "receiver_branch": ""}, O)[0] == 400)
    check("quote", call("POST", "/quote", {"weight": 3}, O)[1]["price"] == 21280)
    d = call("GET", "/dict", None, O)[1]
    check("ma'lumotnoma o'qish", "Toshkent shahri" in d["regions"] and "Kelishuv" in d["payment_types"])
    check("operator ma'lumotnomani o'zgartira olmaydi", call("PUT", "/dict", d, O)[0] == 403)
    d["contents"].append("YANGI TOIFA")
    check("admin ma'lumotnomani yangilaydi", "YANGI TOIFA" in call("PUT", "/dict", d, A)[1]["contents"])
    check("ma'lumotnoma noto'g'ri 400", call("PUT", "/dict", {**d, "regions": {}}, A)[0] == 400)
    # --- shaxsiy hisob (balans)
    bo = {**order, "auto_price": True, "payment_type": "Balans", "price": "", "payer": "Yuboruvchi"}
    s, e1 = call("POST", "/orders", {**bo, "sender_phone": "+998909990001"}, O)
    check("balans yetarli emas -> 400", s == 400 and "yetarli emas" in e1["error"])
    check("hisobni to'ldirish", call("POST", "/customers/topup", {"phone": "90 999 00 01", "amount": 100000, "name": "Hisobchi"}, O)[1]["balance"] == 100000)
    check("topup: yangi mijoz ismsiz 400", call("POST", "/customers/topup", {"phone": "+998909990002", "amount": 5}, O)[0] == 400)
    check("topup: kuryer ruxsatsiz", call("POST", "/customers/topup", {"phone": "+998909990001", "amount": 5}, K2 if False else K)[0] in (401, 403))
    s, ob = call("POST", "/orders", {**bo, "sender_phone": "+998909990001", "weight": "1"}, O)
    check("balansdan to'lash", s == 201 and ob["paid_from_balance"] and call("GET", "/customers/balance?phone=%2B998909990001", None, O)[1]["balance"] == 100000 - ob["price"])
    s, rb = call("POST", "/orders/%d/status" % ob["id"], {"status": "Bekor qilindi", "reason": "test"}, A)
    check("bekor qilinsa balansga qaytariladi", s == 200 and call("GET", "/customers/balance?phone=%2B998909990001", None, O)[1]["balance"] == 100000)
    call("POST", "/orders/%d/status" % ob["id"], {"status": "Yo'lda"}, A)
    call("POST", "/orders/%d/status" % ob["id"], {"status": "Bekor qilindi", "reason": "yana"}, A)
    check("ikki marta qaytarilmaydi", call("GET", "/customers/balance?phone=%2B998909990001", None, O)[1]["balance"] == 100000)
    s, ms = call("GET", "/mystats", None, O)
    check("operator ko'rsatkichlari", s == 200 and ms["total"] == 20 and ms["today"] == 20 and len(ms["days"]) == 7)
    check("kuryer mystats ko'ra olmaydi", call("GET", "/mystats", None, K)[0] == 403)
    s, st = call("GET", "/stats", None, A)
    check("statistika", s == 200 and st["total"] == 20 and len(st["days"]) == 7 and st["customers"] == 3)

    s, u = call("POST", "/users", {"name": "Yangi kuryer", "username": "kur2", "password": "secret1", "role": "courier", "phone": "901112244"}, A)
    check("foydalanuvchi qo'shish", s == 201 and u["phone"] == "+998901112244")
    check("login band", call("POST", "/users", {"name": "x", "username": "KUR2", "password": "secret1", "role": "courier"}, A)[0] == 400)
    check("operator foydalanuvchi qo'sha olmaydi", call("POST", "/users", {"name": "x", "username": "kur3", "password": "secret1", "role": "courier"}, O)[0] == 403)
    K2 = login("kur2", "secret1")
    check("yangi kuryer kira oladi", bool(K2))
    call("PUT", "/users/%d" % u["id"], {"active": False}, A)
    check("o'chirilgan hisob kira olmaydi", login("kur2", "secret1") is None and call("GET", "/me", None, K2)[0] == 401)
    check("o'zini o'chira olmaydi", call("DELETE", "/users/1", None, A)[0] == 400)
    check("parol almashtirish", call("POST", "/password", {"old": "operator123", "new": "newpass1"}, O)[0] == 200 and login("operator", "newpass1"))
    check("parol: noto'g'ri joriy", call("POST", "/password", {"old": "bad", "new": "newpass1"}, O)[0] == 400)
    check("kuryer o'chirilganda buyurtmalar bo'shaydi", call("DELETE", "/users/3", None, A)[0] == 200 and all(x["courier_id"] is None for x in call("GET", "/orders?per=50", None, A)[1]["items"]))
    # --- 1-bosqich: scrypt, mijoz kabineti, kalkulyator, audit
    s, cq = call("POST", "/calc", {"weight": "2", "door_delivery": True})
    check("ochiq kalkulyator", s == 200 and cq["price"] > 0 and cq["door_fee"] > 0)
    check("kalkulyator og'irliksiz 400", call("POST", "/calc", {})[0] == 400)
    check("ochiq ofislar", call("GET", "/public/offices")[1]["offices"][0]["address"] != "")
    s, rg = call("POST", "/register", {"name": "Mijoz Bir", "phone": "93 111 22 33", "password": "qisqa"})
    check("qisqa parol 400", s == 400)
    s, rg = call("POST", "/register", {"name": "Mijoz Bir", "phone": "93 111 22 33", "password": "uzunparol1"})
    C = rg.get("token")
    check("mijoz ro'yxatdan o'tdi", s == 201 and rg["user"]["role"] == "customer" and rg["user"]["username"] == "+998931112233")
    check("takroriy telefon 409", call("POST", "/register", {"name": "X", "phone": "+998931112233", "password": "uzunparol1"})[0] == 409)
    check("mijoz login", login("+998931112233", "uzunparol1") is not None)
    check("mijoz hamma buyurtmani ko'rolmaydi", call("GET", "/orders", None, C)[0] == 403)
    check("mijoz admin sahifasiga kirolmaydi", call("GET", "/users", None, C)[0] == 403 and call("GET", "/audit", None, C)[0] == 403)
    mo = {"receiver_name": "Vali", "receiver_phone": "91 765 43 21", "receiver_region": "Farg'ona viloyati", "address": "Qo'qon", "product": "Kitob", "weight": "2", "price": "1", "courier_id": 1}
    s, co = call("POST", "/my/orders", mo, C)
    check("onlayn buyurtma (narx serverda hisoblanadi)", s == 201 and co["online"] and co["sender_phone"] == "+998931112233" and co["price"] != 1 and co["courier_id"] is None)
    s, mine = call("GET", "/my/orders", None, C)
    check("mening buyurtmalarim", s == 200 and len(mine) == 1 and mine[0]["direction"] == "out")
    s, cx = call("POST", "/my/orders/%d/cancel" % co["id"], {}, C)
    check("mijoz bekor qiladi", s == 200 and cx["status"] == "Bekor qilindi")
    check("qayta bekor 400", call("POST", "/my/orders/%d/cancel" % co["id"], {}, C)[0] == 400)
    s, au = call("GET", "/audit", None, A)
    check("audit log yozilgan", s == 200 and {"login", "onlayn buyurtma", "mijoz bekor qildi"} <= {r["action"] for r in au})
    # --- 2-bosqich: inkassatsiya, KPI, shikoyat, topshirish kodi
    s, co_ = call("GET", "/collection", None, O)
    check("inkassatsiya GET", s == 200 and "expected" in co_ and "history" in co_)
    s, rec = call("POST", "/collection", {"amount": co_["expected"], "note": "kun yakuni"}, O)
    check("inkassatsiya topshirildi", s == 201 and rec["diff"] == 0)
    check("KPI", call("GET", "/kpi", None, A)[0] == 200 and call("GET", "/kpi", None, C)[0] == 403)
    s, cm = call("POST", "/complaints", {"order": "BTS-00001", "text": "Kech keldi"}, C)
    check("shikoyat yuborildi", s == 201 and cm["status"] == "Yangi")
    s, up = call("PUT", "/complaints/%d" % cm["id"], {"status": "Hal qilindi", "answer": "Uzr"}, O)
    check("shikoyatga javob", s == 200 and up["status"] == "Hal qilindi")
    s, mc = call("GET", "/complaints", None, C)
    check("mijoz o'z shikoyatini ko'radi", s == 200 and len(mc) == 1 and mc[0]["answer"] == "Uzr")
    check("smena hisoboti", call("GET", "/shift/report", None, O)[0] == 200 and call("GET", "/movements", None, O)[0] == 200)
    s, wh = call("GET", "/warehouse", None, O)
    check("ombor ro'yxati", s == 200 and wh["items"] and wh["unplaced"] == len(wh["items"]))
    wid = wh["items"][0]["id"]
    check("shkaf noto'g'ri belgi 400", call("POST", "/orders/%d/shelf" % wid, {"shelf": "a b!"}, O)[0] == 400)
    s, sh = call("POST", "/orders/%d/shelf" % wid, {"shelf": "a-3"}, O)
    check("shkafga joylash", s == 200 and sh["shelf"] == "A-3" and call("GET", "/warehouse", None, O)[1]["shelves"] == {"A-3": 1})
    check("mijoz ombor ko'rolmaydi", call("GET", "/warehouse", None, C)[0] == 403)
    # --- 3-bosqich: kengaytirilgan admin va kuryer ko'rsatkichlari
    s, st3 = call("GET", "/stats", None, A)
    check("admin: kengaytirilgan statistika", s == 200 and len(st3["trend"]) == 14 and st3["by_region"] and "overdue" in st3 and "users_by_role" in st3 and 0 <= st3["delivery_rate"] <= 100)
    s, k1 = call("POST", "/users", {"name": "Kuryer Yangi", "role": "courier", "username": "kuryer9", "password": "kuryer999"}, A)
    K9 = login("kuryer9", "kuryer999")
    check("kuryer statistikasi bo'sh", call("GET", "/courier/stats", None, K9)[1]["total"] == 0)
    check("operator kuryer statistikasini ko'rolmaydi", call("GET", "/courier/stats", None, O)[0] == 403)
    call("PUT", "/tariff", {"base": 10000, "per_kg": 3000, "free_kg": 1, "round_to": 500, "courier_fee": 7000}, A)
    s, no = call("POST", "/orders", dict(order, courier_id=k1["id"]), O)
    check("kuryerga biriktirildi", s == 201 and no["courier_id"] == k1["id"])
    check("begona kuryer kod bilan topshira olmaydi", call("POST", "/orders/%d/handover" % no["id"], {"code": "0000"}, K)[0] in (404, 401, 403))
    check("noto'g'ri kod 400", call("POST", "/orders/%d/handover" % no["id"], {"code": "abcd"}, K9)[0] == 400)
    s, hv = call("POST", "/orders/%d/status" % no["id"], {"status": "Yetkazildi"}, K9)
    cs9 = call("GET", "/courier/stats", None, K9)[1]
    check("kuryer statistikasi: haq hisoblandi", s == 200 and cs9["today"] == 1 and cs9["earn_today"] == 7000 and cs9["rate"] == 100)
finally:
    srv.terminate()
print("\n%d xato" % len(fails) if fails else "\nHamma testlar o'tdi")
sys.exit(1 if fails else 0)
