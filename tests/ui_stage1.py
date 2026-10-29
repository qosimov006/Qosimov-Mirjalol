"""1-bosqich UI testi: kalkulyator, mijoz kabineti, ofislar, audit."""
import os, subprocess, sys, tempfile, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
_t = tempfile.mkdtemp()
env = dict(os.environ, PORT="8793", BTS_DB=os.path.join(_t, "db.json"), BTS_FILES=os.path.join(_t, "files"))
srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py")], env=env, stdout=subprocess.DEVNULL)
time.sleep(1.2)
U = "http://localhost:8793/"
errors = []
try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)
        pg = b.new_context(viewport={"width": 1280, "height": 900}).new_page()
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(U); pg.wait_for_selector("#calcForm")
        pg.fill("#calcForm [name=weight]", "3"); pg.click("#calcForm button"); pg.wait_for_function("document.querySelector('#calcRes').innerText.includes('so')")
        assert "kg" in pg.inner_text("#calcRes"); pg.screenshot(path=OUT + "/s1_home.png")
        pg.goto(U + "#/offices"); pg.wait_for_selector("#of_b tr"); assert pg.locator("#of_b tr").count() > 100
        pg.goto(U + "#/login"); pg.click("#regLink"); f = "#regForm "
        pg.fill(f + "[name=name]", "Test Mijoz"); pg.fill(f + "[name=phone]", "93 555 66 77"); pg.fill(f + "[name=password]", "parol12345"); pg.click(f + "button")
        pg.wait_for_selector("text=Salom, Test Mijoz"); assert "Operator paneli" not in pg.inner_text("#nav")
        pg.goto(U + "#/customer/new"); pg.wait_for_selector("#cf")
        c = "#cf "
        pg.fill(c + "[name=receiver_name]", "Vali"); pg.fill(c + "[name=receiver_phone]", "91 765 43 21")
        pg.select_option(c + "[name=receiver_region]", "Farg'ona viloyati"); pg.fill(c + "[name=address]", "Qo'qon, Navoiy 5")
        pg.select_option(c + "[name=product]", index=1); pg.fill(c + "[name=weight]", "2.5")
        pg.wait_for_function("document.querySelector('#cq').innerText.includes('Narx')"); pg.screenshot(path=OUT + "/s2_customer_new.png", full_page=True)
        pg.click(c + "button"); pg.wait_for_selector("table"); assert "BTS-00001" in pg.inner_text("#tab") and "Qabul qilindi" in pg.inner_text("#tab")
        pg.screenshot(path=OUT + "/s3_customer_orders.png")
        pg.click("[data-cancel]"); pg.wait_for_selector("#modalBox button >> text=Bekor qilish"); pg.click("#modalBox button >> text=Bekor qilish"); pg.wait_for_selector("text=Bekor qilindi >> nth=0")
        pg.click("#logoutBtn"); pg.wait_for_timeout(500); pg.goto(U + "#/login"); pg.reload(); pg.wait_for_selector("#lu"); pg.fill("#lu", "admin"); pg.fill("#lp", "admin123"); pg.click("#loginForm button"); pg.wait_for_timeout(500)
        pg.goto(U + "#/admin/audit"); pg.wait_for_selector("table"); t = pg.inner_text("#tab"); assert "onlayn buyurtma" in t and "mijoz bekor qildi" in t
        pg.screenshot(path=OUT + "/s4_audit.png")
        pg.goto(U + "#/operator"); pg.reload(); pg.wait_for_selector(".tiles")
        pg.click("[data-dd] >> nth=0"); pg.click("[data-shift]"); pg.wait_for_selector("#bp_list .bp-item")
        n = pg.locator("#bp_list .bp-item").count(); assert n > 100
        pg.fill("#bp_q", "bag'dod"); assert 0 < pg.locator("#bp_list .bp-item").count() < n
        pg.locator("#bp_list .bp-item").first.click(); assert not pg.locator("#bp_ok").is_disabled(); pg.screenshot(path=OUT + "/s5_picker.png")
        pg.click("#bp_ok"); pg.wait_for_timeout(600); assert "BAG" in pg.inner_text("#userbox").upper()
        for sub in ("cash", "kpi", "complaints"):
            pg.goto(U + "#/operator/" + sub); pg.wait_for_selector("#tab .card, #tab .grid")
        pg.screenshot(path=OUT + "/s6_complaints.png")
    print("JS xatolari:", errors or "yo'q"); print("UI 1-bosqich: OK"); sys.exit(1 if errors else 0)
finally:
    srv.terminate()
