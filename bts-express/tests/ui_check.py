import os, subprocess, sys, tempfile, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
os.makedirs(OUT, exist_ok=True)
_t = tempfile.mkdtemp()
env = dict(os.environ, PORT="8792", BTS_DB=os.path.join(_t, "db.json"), BTS_FILES=os.path.join(_t, "files"))
srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py")], env=env, stdout=subprocess.DEVNULL)
time.sleep(1.2)
U = "http://localhost:8792/"
errors = []
def login(page, u, p):
    page.goto(U + "#/login"); page.fill("#lu", u); page.fill("#lp", p); page.click("#loginForm button"); page.wait_for_timeout(500)
    if u == "operator":
        page.wait_for_timeout(500); page.evaluate("async () => { me = await api('POST', '/shift', {branch: '0112'}); closeModal(); render(); }"); page.wait_for_timeout(400)
def close_label(pg, shot=None):
    """Saqlangach chek (yorliq) avtomatik chiqadi: borligini tekshirib, yopamiz."""
    pg.wait_for_selector("#labelBox"); assert pg.locator("#labelBox svg").count() == 3 and "EHTIYOT" in pg.inner_text("#labelBox") and "Farg'ona yo'li" in pg.inner_text("#labelBox")
    url = None
    if shot:
        pg.locator("#labelBox").screenshot(path=OUT + "/" + shot)
        svg = pg.locator(".lc-qr svg").evaluate("e => e.outerHTML").replace('width="96" height="96"', 'width="400" height="400"')
        q = pg.context.new_page(); q.set_viewport_size({"width": 440, "height": 440}); q.set_content("<body style='margin:20px;background:#fff'>" + svg); q.screenshot(path=OUT + "/qr.png"); q.close()
        import cv2
        url, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(OUT + "/qr.png"))
        assert "/#/t/BTS-" in url, "QR-kod o'qilmadi: %r" % url
    pg.keyboard.press("Escape"); pg.wait_for_selector("#labelBox", state="hidden")
    return url


try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)
        def newpage(w=1280, h=900):
            ctx = b.new_context(viewport={"width": w, "height": h}); pg = ctx.new_page()
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errors.append(str(e) + " | " + str(getattr(e, "stack", ""))[:400]))
            pg.on("dialog", lambda d: d.accept()); return pg
        # operator
        pg = newpage(); login(pg, "operator", "operator123")
        pg.wait_for_selector(".tiles"); assert pg.locator(".tiles .tile").count() == 25; assert "XODIMLAR OFISI" in pg.inner_text(".officebar").upper()
        assert not pg.locator("#side .lbl").first.is_visible(); pg.click("#burger"); pg.wait_for_timeout(350); assert pg.locator("#side .lbl").first.is_visible(); pg.screenshot(path=OUT + "/0b_menu_open.png"); pg.click(".officebar"); pg.wait_for_timeout(350); assert not pg.locator("#side .lbl").first.is_visible()
        pg.click("[data-dd]"); assert pg.locator(".ddm").first.is_visible(); pg.click(".officebar"); assert not pg.locator(".ddm").first.is_visible()
        pg.screenshot(path=OUT + "/0_operator_home.png")
        pg.goto(U + "#/operator/prices"); pg.wait_for_selector("#pw_kg"); pg.fill("#pw_kg", "3"); assert "Jami" in pg.inner_text("#pw_out"); pg.screenshot(path=OUT + "/0c_prices.png")
        pg.goto(U + "#/operator/offices"); pg.wait_for_selector("#of_l table"); pg.select_option("#of_r", "Sirdaryo viloyati"); assert "YANGIYER" in pg.inner_text("#of_l").upper() and "QO'YLIQ" not in pg.inner_text("#of_l").upper(); pg.screenshot(path=OUT + "/0d_offices.png")
        pg.goto(U + "#/operator/delivered"); pg.wait_for_selector("#ol"); assert pg.input_value("#fs") == "Yetkazildi"
        pg.goto(U + "#/operator"); pg.wait_for_selector(".tiles")
        pg.click(".tile.primary"); pg.wait_for_selector("#orderForm")
        import re
        pg.fill("#orderForm [name=weight]", "3"); assert re.sub(r"\D", "", pg.input_value("#sum")) == "16000", pg.input_value("#sum")
        pg.check("#orderForm [name=door_delivery]"); assert re.sub(r"\D", "", pg.input_value("#sum")) == "26000"
        assert re.sub(r"\D", "", pg.inner_text("#q_total")) == "29120", pg.inner_text("#q_total")
        pg.uncheck("#orderForm [name=door_delivery]")
        pg.fill("#orderForm [name=width]", "50"); pg.fill("#orderForm [name=height]", "40"); pg.fill("#orderForm [name=length]", "30")
        assert pg.input_value("#orderForm [name=vw_view]") == "12.00" and re.sub(r"\D", "", pg.input_value("#sum")) == "43000"
        for k in ("width", "height", "length"): pg.fill("#orderForm [name=%s]" % k, "")
        pg.screenshot(path=OUT + "/1a_form_empty.png", full_page=True)
        for i in range(3):
            f = {"sender_phone": "90 123 45 6%d" % i, "sender_name": "Ali %d" % i, "receiver_phone": "91 765 43 2%d" % i,
                 "receiver_name": "Vali %d" % i, "address": "Toshkent, Chilonzor %d" % i, "weight": "1.5"}
            for k, v in f.items(): pg.fill("#orderForm [name=%s]" % k, v)
            pg.wait_for_timeout(450); pg.evaluate("closeModal()")
            pg.select_option("#orderForm [name=product]", index=1); pg.select_option("#orderForm [name=payment_type]", index=1)
            pg.select_option("#orderForm [name=courier_id]", index=1); pg.check("#orderForm [name=door_delivery]")
            if i == 0:
                pg.select_option("#orderForm [name=receiver_region]", "Farg'ona viloyati"); assert pg.locator("#orderForm [name=receiver_district] option").count() == 20; assert pg.locator("#orderForm [name=receiver_district] option", has_text="Qo'qon shahri").count() == 1; assert pg.locator("#orderForm [name=receiver_district] option", has_text="Bag'dod tumani").count() == 1
                assert pg.locator("#orderForm [name=receiver_branch] option").count() == 20 and pg.locator("#orderForm [name=receiver_branch] option", has_text="QO'YLIQ").count() == 0
                pg.select_option("#orderForm [name=receiver_district]", "Bag'dod tumani"); assert pg.locator("#orderForm [name=receiver_branch] option").count() == 2; assert "BAG'DOD" in pg.locator("#orderForm [name=receiver_branch] option").nth(1).inner_text()
                pg.screenshot(path=OUT + "/1b_form_filled.png", full_page=True)
            pg.click("#saveBtn"); pg.wait_for_selector("#done .success"); qr_url = close_label(pg, "10_label.png") if not globals().get("qr_url") else close_label(pg)
            if i == 0:
                pg.click("#copyBtn"); assert pg.input_value("#orderForm [name=sender_name]") == "Ali 0"; assert pg.input_value("#orderForm [name=receiver_region]") == "Farg'ona viloyati"
                pg.screenshot(path=OUT + "/1c_form_copied.png", full_page=True)
                for k in ("sender_phone", "sender_name", "receiver_phone", "receiver_name", "address"): pg.fill("#orderForm [name=%s]" % k, "")
                pg.select_option("#orderForm [name=receiver_region]", "")
        pg.screenshot(path=OUT + "/1_operator_new.png", full_page=True)
        def quick(pg, tag, pay="Kelishuv", payer=None):
            f = {"sender_phone": "90 555 00 %02d" % tag, "sender_name": "Bal %d" % tag, "receiver_phone": "91 555 11 %02d" % tag, "receiver_name": "Qab %d" % tag, "address": "Samarqand, Registon %d" % tag, "weight": "1"}
            for k, v in f.items(): pg.fill("#orderForm [name=%s]" % k, v); pg.wait_for_timeout(450); pg.evaluate("closeModal()")
            pg.select_option("#orderForm [name=product]", index=2); pg.select_option("#orderForm [name=payment_type]", pay)
            pg.check("#orderForm [name=door_delivery]")
        # --- Kuryerga berish
        pg.goto(U + "#/operator/new"); pg.wait_for_selector("#orderForm"); quick(pg, 1)
        pg.select_option("#orderForm [name=courier_id]", ""); pg.click("#saveBtn"); pg.wait_for_selector("#done .success"); close_label(pg)
        pg.click("#side a[href='#/operator/assign']"); pg.wait_for_selector(".ck"); assert pg.locator(".ck").count() == 1
        pg.screenshot(path=OUT + "/1d_assign.png"); pg.click("#aa"); pg.click("#ab"); pg.wait_for_selector(".empty"); assert "yo'q" in pg.inner_text(".empty")
        # --- Shaxsiy hisob (balans)
        pg.goto(U + "#/operator/new"); pg.wait_for_selector("#orderForm"); quick(pg, 2, "Balans")
        pg.click("#saveBtn"); pg.wait_for_function("document.querySelector('#toast').innerText.includes('yetarli emas')")
        pg.click("[data-acct=sender]"); pg.wait_for_selector("#ta"); pg.fill("#ta", "100000"); pg.click("#tf .btn"); pg.wait_for_selector("#tf")
        pg.wait_for_function("document.querySelector('.stat b') && document.querySelector('.stat b').innerText.replace(/\\D/g,'') === '100000'")
        pg.screenshot(path=OUT + "/1e_account_modal.png"); pg.keyboard.press("Escape")
        pg.click("#rf"); pg.wait_for_timeout(700); pg.screenshot(path=OUT + "/1f_balans_form.png", full_page=True)
        pg.click("#saveBtn"); pg.wait_for_selector("#done .success"); close_label(pg)
        pg.goto(U + "#/operator/customers"); pg.wait_for_selector("[data-acct]"); assert "Bal 2" in pg.inner_text("tbody")
        pg.click("#side a[href='#/operator/track']"); pg.fill("#tq", "2"); pg.press("#tq", "Enter"); pg.wait_for_selector("#tr .card"); pg.screenshot(path=OUT + "/2a_operator_track.png")
        pg.goto(U + "#/operator/stats"); pg.wait_for_selector(".chart"); pg.screenshot(path=OUT + "/2b_operator_stats.png")
        pg.goto(U + "#/operator/today"); pg.wait_for_selector("tr[data-id]"); assert pg.locator("tr[data-id]").count() == 5
        pg.goto(U + "#/operator/orders"); pg.wait_for_selector("tr[data-id]"); pg.screenshot(path=OUT + "/2_operator_orders.png")
        pg.click("tr[data-id]"); pg.wait_for_selector("#pw"); pg.screenshot(path=OUT + "/3_operator_modal.png")
        assert pg.locator("tr[data-id]").count() == 5
        # customer autofill
        pg.keyboard.press("Escape"); pg.goto(U + "#/operator/new"); pg.wait_for_selector("#orderForm")
        pg.fill("#orderForm [name=sender_phone]", "901234560"); pg.dispatch_event("#orderForm [name=sender_phone]", "change")
        assert pg.input_value("#orderForm [name=sender_name]") == "Ali 0", pg.input_value("#orderForm [name=sender_name]")
        pg.goto(U + "#/operator/customers"); pg.wait_for_selector("tbody tr"); assert pg.locator("tbody tr").count() == 10
        pm = newpage(390, 800); login(pm, "operator", "operator123"); pm.wait_for_selector(".tiles"); pm.screenshot(path=OUT + "/2c_operator_home_mobile.png")
        pm.click("#burger"); pm.wait_for_timeout(400); pm.screenshot(path=OUT + "/2d_operator_menu_mobile.png")
        pm.click("#side a[href='#/operator/customers']"); pm.wait_for_selector("tbody tr")
        # courier (mobile)
        pg2 = newpage(390, 800); login(pg2, "kuryer1", "kuryer123"); pg2.wait_for_selector(".corder")
        assert pg2.locator(".corder").count() == 4
        pg2.screenshot(path=OUT + "/4_courier_mobile.png", full_page=True)
        pg2.click("button[data-st=\"Yo'lda\"]"); pg2.wait_for_timeout(500)
        pg2.locator("button[data-st=Yetkazildi]").first.click(); pg2.click("#cy"); pg2.wait_for_timeout(500)
        pg2.locator("button[data-st=\"Bekor qilindi\"]").first.click(); pg2.fill("#rr", "Telefon o'chiq"); pg2.click("#rf .danger"); pg2.wait_for_timeout(500)
        pg2.screenshot(path=OUT + "/5_courier_after.png", full_page=True)
        pc = newpage(); login(pc, "kuryer1", "kuryer123"); pc.wait_for_selector(".corder, .empty"); pc.screenshot(path=OUT + "/5b_courier_desktop.png")
        # admin
        pg3 = newpage(); login(pg3, "admin", "admin123")
        pg3.wait_for_selector(".tiles"); assert pg3.locator(".tiles .tile").count() == 17; pg3.screenshot(path=OUT + "/6a_admin_home.png")
        pg3.goto(U + "#/admin/tariff"); pg3.wait_for_selector("#trf"); pg3.fill("#trf [name=per_kg]", "4000"); pg3.click("#trf button"); pg3.wait_for_selector("#toast.show"); pg3.screenshot(path=OUT + "/6b_admin_tariff.png")
        pg3.goto(U + "#/admin/dict"); pg3.wait_for_selector("#df"); pg3.screenshot(path=OUT + "/6c_admin_dict.png")
        pg3.goto(U + "#/admin/overview"); pg3.wait_for_selector(".chart"); pg3.screenshot(path=OUT + "/6_admin_overview.png", full_page=True)
        pg3.goto(U + "#/admin/orders"); pg3.wait_for_selector("tr[data-id]"); pg3.click("tr[data-id]"); pg3.wait_for_selector("#mf"); pg3.screenshot(path=OUT + "/7_admin_order_modal.png")
        # fayl yuklash (admin oynasi)
        png = os.path.join(_t, "p.png"); open(png, "wb").write(b"\x89PNG\r\n\x1a\n" + b"0" * 50)
        pg3.set_input_files("[data-upload]", png); pg3.wait_for_selector(".frow"); assert "p.png" in pg3.inner_text("#fbox")
        pg3.screenshot(path=OUT + "/7b_admin_files.png")
        pg3.keyboard.press("Escape")
        with pg3.expect_download() as d: pg3.click("#fx")
        # bulut holati sahifasi
        pg3.goto(U + "#/admin/cloud"); pg3.wait_for_selector("#st"); pg3.click("#st"); pg3.wait_for_selector("#str table")
        assert "Ma'lumotlar bazasi" in pg3.inner_text("#str") and "\u274c" not in pg3.inner_text("#str")
        pg3.click("#ex"); pg3.wait_for_selector("#exl table"); pg3.screenshot(path=OUT + "/7c_admin_cloud.png", full_page=True)
        pg3.goto(U + "#/admin/users"); pg3.wait_for_selector("#uf"); pg3.fill("#uf [name=name]", "Test Op"); pg3.fill("#uf [name=username]", "testop"); pg3.fill("#uf [name=password]", "secret12")
        pg3.select_option("#uf [name=role]", "operator"); pg3.click("#uf button"); pg3.wait_for_timeout(500)
        assert "testop" in pg3.inner_text("#ul"); pg3.screenshot(path=OUT + "/8_admin_users.png", full_page=True)
        # public tracking
        pg4 = newpage(); pg4.goto(U); pg4.fill("#trackId", "1"); pg4.click("#trackForm button"); pg4.wait_for_selector(".steps"); pg4.screenshot(path=OUT + "/9_home_track.png", full_page=True)
        # QR ochgan sahifa: ochiq (kirmagan) foydalanuvchiga shaxsiy ma'lumotsiz ko'rinadi
        pq = newpage(); pq.goto(qr_url.replace("http://localhost:8000/", U)); pq.wait_for_selector(".parcel")
        t = pq.inner_text(".parcel"); assert "Qayerga" in t and "shaxsiy ma'lumotlari" in t and "+998" not in t, t
        pq.screenshot(path=OUT + "/11_qr_public.png")
        b.close()
finally:
    srv.terminate()
errors = [e for e in errors if "status of 400" not in e]   # kutilgan: balans yetarli emas (400)
print("JS xatolari:", errors or "yo'q"); print("Skrinshotlar:", OUT)
