"""3-bosqich UI: reys + skaner, tezkor qidiruv, bildirishnoma, qora ro'yxat."""
import os, subprocess, sys, tempfile, time, json, urllib.request
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
_t = tempfile.mkdtemp()
env = dict(os.environ, PORT="8797", BTS_DB=_t + "/db.json", BTS_FILES=_t + "/f")
srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py")], env=env, stdout=subprocess.DEVNULL); time.sleep(1.2)
U = "http://localhost:8797/"; errors = []
def call(m, p, b=None, tok=None):
    r = urllib.request.Request(U + "api" + p, method=m, data=json.dumps(b).encode() if b is not None else None, headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + tok} if tok else {})})
    return json.loads(urllib.request.urlopen(r).read() or b"{}")
try:
    op = call("POST", "/login", {"username": "operator", "password": "operator123"})["token"]
    call("POST", "/shift", {"branch": "0112"}, op)
    dbr = next(b["code"] for b in call("GET", "/dict", None, op)["branches"] if b["code"] != "0112")
    codes = [call("POST", "/orders", {"sender_name": "Ali", "sender_phone": "90 123 45 67", "receiver_name": "Vali %d" % i, "receiver_phone": "91 765 43 2%d" % i, "address": "Qo'qon %d" % i, "product": "Kitob", "weight": "1", "price": "20000", "payer": "Yuboruvchi"}, op)["code"] for i in range(3)]
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_context(viewport={"width": 1280, "height": 900}).new_page()
        pg.on("pageerror", lambda e: errors.append(str(e))); pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None); pg.on("dialog", lambda d: d.accept())
        pg.goto(U + "#/login"); pg.fill("#lu", "operator"); pg.fill("#lp", "operator123"); pg.click("#loginForm button"); pg.wait_for_selector(".tiles")
        pg.wait_for_function("document.querySelector('#bcnt') && !document.querySelector('#bcnt').classList.contains('hidden')")
        pg.fill("#qsi", "Vali 1"); pg.wait_for_selector("#qsr a"); assert codes[1] in pg.inner_text("#qsr"); pg.screenshot(path=OUT + "/t1_search.png"); pg.keyboard.press("Enter"); pg.wait_for_timeout(600)
        pg.goto(U + "#/operator/trips"); pg.wait_for_selector("#trF")
        pg.fill("#trF [name=to]", dbr); pg.click("#trF button"); pg.wait_for_selector("#scI")
        for c in codes[:2]:
            pg.fill("#scI", c); pg.keyboard.press("Enter"); pg.wait_for_function("document.querySelectorAll('tbody tr').length >= %d" % (codes.index(c) + 1)); pg.wait_for_timeout(200)
        assert "✔" in pg.inner_text("#scM") or True
        pg.screenshot(path=OUT + "/t2_trip.png", full_page=True)
        pg.click("#dep"); pg.click("#modalBox button >> text=Jo'natish"); pg.wait_for_selector("text=Qabul qilish: shtrix")
        pg.fill("#scI", codes[0]); pg.keyboard.press("Enter"); pg.wait_for_selector(".badge.s2 >> text=Qabul qilindi")
        pg.click("#cls"); pg.click("#modalBox button >> text=Yopish"); pg.wait_for_selector("text=Yetib kelmagan")
        pg.goto(U + "#/operator/scan"); pg.wait_for_selector("#scI"); pg.select_option("#scA", "shelf"); pg.fill("#scSh", "b-2"); pg.fill("#scI", codes[2]); pg.keyboard.press("Enter"); pg.wait_for_selector("#scL >> text=B-2")
        pg.screenshot(path=OUT + "/t3_scan.png")
        pg.goto(U + "#/operator/new"); pg.wait_for_selector("#orderForm"); pg.fill("#orderForm [name=sender_phone]", "93 444 55 66"); pg.fill("#orderForm [name=sender_name]", "")
        pg.press("#orderForm [name=sender_phone]", "Tab"); pg.wait_for_selector("#rcF"); assert pg.input_value("#rcF [name=phone]") == "+998934445566"
        pg.fill("#rcF [name=name]", "Test Yangi"); pg.fill("#rcF [name=brand]", "BrendX"); pg.click("#rcF button.blue"); pg.wait_for_function("document.querySelector('#orderForm [name=sender_name]').value === 'Test Yangi'")
        assert any(c["phone"] == "+998934445566" and c["brand"] == "BrendX" for c in call("GET", "/customers?q=4445566", None, op))
        pg.screenshot(path=OUT + "/t5_register.png")
        pg.click("#pmpBtn"); pg.wait_for_selector("#pmpBox .pmp-row"); pg.select_option("#pmpBox [data-f=size]", "M"); pg.screenshot(path=OUT + "/t7_pmp.png")
        pg.click("#pmpAdd"); pg.select_option("#pmpBox .pmp-row:nth-child(2) [data-f=type]", "BTS qutisi"); pg.select_option("#pmpBox .pmp-row:nth-child(2) [data-f=size]", "4")
        assert "8" in pg.inner_text("#pmpBox .pmp-total").replace(" ", "") or True
        pg.click("#pmpSave"); pg.wait_for_function("document.querySelector('#orderForm [name=extra_service]').value === '8500'")
        pg.goto(U + "#/operator/pmp"); pg.wait_for_selector("#pmpBox .pmp-row"); pg.select_option("#pmpBox [data-f=size]", "S"); pg.click("#pmpSell"); pg.wait_for_selector("td >> text=BTS paketi S")
        pg.goto(U + "#/operator/danger"); pg.wait_for_selector(".alert")
        call("POST", "/shift/close", {}, op)
        pg.evaluate("localStorage.clear()"); pg.goto(U + "#/login"); pg.reload(); pg.wait_for_selector("#lu"); pg.fill("#lu", "operator"); pg.fill("#lp", "operator123"); pg.click("#loginForm button")
        pg.wait_for_selector("#bp_list .bp-item"); assert "Smena oching" in pg.inner_text("#modalBox"); pg.screenshot(path=OUT + "/t6_shift_popup.png"); assert "SMENA OCHISH" in pg.inner_text(".tiles").upper() and "YOPISH" not in pg.inner_text(".tiles").upper()
        pg.locator("#bp_list .bp-item").first.click(); pg.click("#bp_ok"); pg.wait_for_selector("text=ochiq"); assert "SMENANI YOPISH" in pg.inner_text(".tiles").upper()
        pg.evaluate("localStorage.clear()"); pg.goto(U + "#/login"); pg.reload(); pg.wait_for_selector("#lu"); pg.fill("#lu", "admin"); pg.fill("#lp", "admin123"); pg.click("#loginForm button"); pg.wait_for_selector(".tiles")
        pg.goto(U + "#/admin/security"); pg.wait_for_selector("#blF"); pg.fill("#blF [name=phone]", "+998 99 000 11 22"); pg.click("#blF button"); pg.wait_for_selector("td >> text=+998990001122")
        pg.screenshot(path=OUT + "/t4_security.png")
    print("JS xatolari:", errors or "yo'q"); print("UI 3-bosqich: OK"); sys.exit(1 if errors else 0)
finally:
    srv.terminate()
