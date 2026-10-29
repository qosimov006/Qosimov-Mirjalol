"use strict";
const STATUSES = ["Qabul qilindi", "Yo'lda", "Yetkazildi", "Bekor qilindi"];
const ROLE_NAME = {admin: "Admin", operator: "Operator", courier: "Kuryer", customer: "Mijoz"};
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const money = n => new Intl.NumberFormat("uz-UZ").format(Math.round(n || 0)) + " so'm";
const badge = s => `<span class="badge s${STATUSES.indexOf(s)}">${esc(s)}</span>`;
const debounce = (fn, ms = 300) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
let renderId = 0, me = null, token = localStorage.getItem("bts_token") || "", timers = [];

/* ---------- API ---------- */
async function api(method, url, body, raw) {
  let r;
  try {
    r = await fetch("/api" + url, {
      method, headers: {"Content-Type": "application/json", ...(token ? {Authorization: "Bearer " + token} : {})},
      body: body ? JSON.stringify(body) : undefined
    });
  } catch {
    throw new Error(location.protocol === "file:"
      ? "Sahifa fayl sifatida ochilgan. Serverni ishga tushiring va brauzerda http://localhost:8000 manziliga kiring"
      : "Server bilan aloqa yo'q. server.py ishga tushirilganini tekshiring");
  }
  if (raw && r.ok) return r;
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401 && token) { logoutLocal(); location.hash = "#/login"; }
    throw new Error(data.error || "Xatolik yuz berdi");
  }
  return data;
}
const guard = fn => async (...a) => { try { return await fn(...a); } catch (e) { toast(e.message, true); } };

/* ---------- UI yordamchilar ---------- */
function toast(msg, err) {
  const t = $("#toast"); t.textContent = msg; t.className = "toast show" + (err ? " err" : "");
  clearTimeout(toast.t); toast.t = setTimeout(() => t.className = "toast", 3000);
}
function openModal(html, small) { $("#modalBox").className = "modal-box" + (small ? " sm" : ""); $("#modalBox").innerHTML = html; $("#modal").classList.remove("hidden"); }
function closeModal() { $("#modal").classList.add("hidden"); }
$("#modal").addEventListener("click", e => { if (e.target.id === "modal") closeModal(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });
function confirmBox(text, okLabel = "Tasdiqlash") {
  return new Promise(res => {
    openModal(`<h2>${esc(text)}</h2><div class="acts" style="margin-top:18px"><button class="btn danger" id="cy">${okLabel}</button><button class="btn sec" id="cn">Bekor</button></div>`, true);
    $("#cy").onclick = () => { closeModal(); res(true); }; $("#cn").onclick = () => { closeModal(); res(false); };
  });
}
function askReason(title) {
  return new Promise(res => {
    openModal(`<h2>${esc(title)}</h2><form id="rf"><label>Sabab</label><textarea id="rr" required maxlength="300" autofocus></textarea>
      <div class="acts" style="margin-top:14px"><button class="btn danger">Bekor qilish</button><button type="button" class="btn sec" id="rn">Orqaga</button></div></form>`, true);
    $("#rf").onsubmit = e => { e.preventDefault(); const v = $("#rr").value.trim(); closeModal(); res(v); };
    $("#rn").onclick = () => { closeModal(); res(null); };
  });
}
const readForm = f => Object.fromEntries(new FormData(f).entries());
function on(root, ev, sel, fn) { root.addEventListener(ev, e => { const t = e.target.closest(sel); if (t && root.contains(t)) fn(t, e); }); }
const mapLink = a => "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(a);

function logoutLocal() { window.__shiftAsked = false; token = ""; me = null; localStorage.removeItem("bts_token"); }
async function logout() { try { await api("POST", "/logout"); } catch {} logoutLocal(); location.hash = "#/"; render(); }

/* ---------- Ikonkalar ---------- */
const ICONS = {
  download: '<path d="M12 4v11M7 11l5 5 5-5M4 20h16"/>',
  upload: '<path d="M12 16V5M7 9l5-5 5 5M4 20h16"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l3 3 5-6"/>',
  undo: '<path d="M4 9h11a5 5 0 0 1 0 10H8M4 9l4-4M4 9l4 4"/>',
  file: '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5M9 13h7M9 17h7"/>',
  pin: '<path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
  cloud: '<path d="M7 18a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 18 8.5a4.8 4.8 0 0 1-.5 9.5z"/>',
  clip: '<path d="M20 11.5l-8 8a5 5 0 0 1-7-7l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7L9.5 17a1.7 1.7 0 0 1-2.4-2.4l7.5-7.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 3-6 6.5-6s6.5 2.4 6.5 6"/><path d="M16 4.7a3.5 3.5 0 0 1 0 6.6M18 14.3c2.2.6 3.5 2.5 3.5 5.7"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l5 5"/>',
  chart: '<path d="M5 20V11M11 20V4M17 20v-6M3 20h18"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
  home: '<path d="M3 11l9-8 9 8M5 9.5V21h5v-6h4v6h5V9.5"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  logout: '<path d="M9 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h4M16 8l4 4-4 4M20 12H9"/>',
  print: '<path d="M7 9V3h10v6M7 17H4v-7h16v7h-3"/><path d="M7 14h10v7H7z"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
  truck: '<path d="M3 6h11v10H3zM14 9h4l3 3v4h-7z"/><circle cx="7" cy="18" r="1.8"/><circle cx="17" cy="18" r="1.8"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 21V5"/>',
  tag: '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
};
const ico = n => `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n]}</svg>`;

/* ---------- Operator qobig'i ---------- */
const MENUS = {
  operator: [["", "Uy", "home"], ["new", "Pochta qabul qilish", "mail"], ["orders", "Yo'l varaqalari ro'yxati", "list"],
    ["today", "Bugungi buyurtmalar", "clock"], ["assign", "Kuryerga bering", "truck"], ["delivery", "Pochta yetkazib berish", "upload"],
    ["delivered", "Yetkazilgan yuklar hisoboti", "check"], ["returns", "Qaytarish jo'natmalari", "undo"], ["customers", "Mijozlar", "users"],
    ["track", "Pochtani kuzatish", "search"], ["prices", "Narxlar", "file"], ["offices", "Bizning ofislarimiz", "pin"], ["stats", "Ko'rsatkichlarim", "chart"]],
  admin: [["", "Uy", "home"], ["overview", "Statistika", "chart"], ["orders", "Buyurtmalar", "list"], ["users", "Foydalanuvchilar", "shield"],
    ["customers", "Mijozlar", "users"], ["tariff", "Tariflar", "tag"], ["dict", "Ma'lumotnomalar", "book"], ["cloud", "Bulut holati", "cloud"], ["audit", "Audit log", "clip"], ["security", "Qora ro'yxat va zaxira", "shield"], ["kpi", "KPI", "chart"], ["complaints", "Shikoyatlar", "clip"], ["cash", "Inkassatsiya", "tag"]],
  courier: [["", "Mening buyurtmalarim", "list"]],
};
function sideHTML(first, cur) {
  const link = (h, t, i, on) => `<a href="#${h}" class="${on ? "on" : ""}" title="${esc(t)}">${ico(i)}<span class="lbl">${t}</span></a>`;
  return MENUS[first].map(([k, t, i]) => link(`/${first}${k ? "/" + k : ""}`, t, i, k === cur)).join("") +
    `<hr>` + link("/", "Mijozlar uchun sahifa", "globe") +
    (me.role === "admin" && first !== "admin" ? link("/admin", "Admin paneli", "shield") : "") +
    (me.role === "admin" && first !== "operator" ? link("/operator", "Operator paneli", "mail") : "") +
    `<a href="#" data-logout title="Chiqish">${ico("logout")}<span class="lbl">Chiqish ( ${esc(me.username.toUpperCase())} )</span></a>`;
}
$("#burger").onclick = e => { e.stopPropagation(); document.body.classList.toggle("side-open"); };
document.addEventListener("click", e => {
  if (!e.target.closest("#qs") && $("#qsr")) $("#qsr").classList.add("hidden");
  const dd = e.target.closest(".dd");
  document.querySelectorAll(".dd.open").forEach(x => { if (x !== dd) x.classList.remove("open"); });
  if (e.target.closest("[data-dd]")) { dd.classList.toggle("open"); return; }
  if (e.target.closest("[data-profile]")) { e.preventDefault(); profileModal(); }
  if (e.target.closest("[data-shift]")) { e.preventDefault(); shiftModal(); }
  if (e.target.closest("[data-logout]")) { e.preventDefault(); logout(); }
  if (e.target.closest("#side a") || e.target.closest(".ddm a")) document.body.classList.remove("side-open");
  else if (!e.target.closest("#side")) document.body.classList.remove("side-open");
});
function shellBarHTML(first) {
  const base = first === "admin" ? "admin" : "operator";
  const docs = first === "admin"
    ? [["admin/orders", "Buyurtmalar ro'yxati"], ["admin/tariff", "Tariflar"], ["admin/dict", "Ma'lumotnomalar"]]
    : [["operator/orders", "Yo'l varaqalari ro'yxati"], ["operator/prices", "Narxlar"], ["operator/offices", "Bizning ofislarimiz"]];
  const dd = (t, items) => `<div class="dd"><button class="ddb" data-dd>${t} <svg viewBox="0 0 24 24" class="ico"><path d="M6 9l6 6 6-6"/></svg></button><div class="ddm">${items}</div></div>`;
  return dd("Sozlamalar", (me.role !== "courier" ? `<a href="#" data-shift>Smena ochish (ofis tanlash)</a>` : "") + `<a href="#" data-profile>Profil va parolni o'zgartirish</a><a href="#/">Mijozlar uchun sahifa</a>`) +
    dd("Hujjatlar", docs.map(([h, t]) => `<a href="#/${h}">${t}</a>`).join("")) +
    `<form class="qs" id="qs" autocomplete="off"><input id="qsi" placeholder="Raqam, shtrix-kod, telefon, ism…"><div class="qsr hidden" id="qsr"></div></form>` +
    (first === "operator" || first === "admin" ? `<div class="dd"><button class="iconbtn bell" data-dd id="bell" title="Bildirishnomalar">${ico("check")}<span class="bcnt hidden" id="bcnt"></span></button><div class="ddm" id="bellm"><span class="muted small" style="padding:10px 14px;display:block">Yuklanmoqda…</span></div></div>` : "");
}

function wireShellBar() {
  const inp = $("#qsi"), box = $("#qsr");
  inp.oninput = debounce(async () => {
    const q = inp.value.trim();
    if (q.length < 2) { box.classList.add("hidden"); return; }
    try {
      const r = await api("GET", "/find?q=" + encodeURIComponent(q));
      box.innerHTML = r.length ? r.map(o => `<a href="#/t/${esc(o.code)}"><b>${esc(o.code)}</b> ${esc(o.receiver)} <span class="muted small">${esc(o.receiver_phone)}</span> ${badge(o.status)}</a>`).join("") : `<span class="muted small" style="padding:10px 14px;display:block">Topilmadi</span>`;
      box.classList.remove("hidden");
    } catch {}
  });
  $("#qs").onsubmit = e => { e.preventDefault(); const f = box.querySelector("a"); if (f) { location.hash = f.getAttribute("href"); box.classList.add("hidden"); inp.value = ""; } };
  box.onclick = () => { box.classList.add("hidden"); inp.value = ""; };
  if ($("#bell")) api("GET", "/notifications").then(n => {
    if (n.total) { $("#bcnt").textContent = n.total; $("#bcnt").classList.remove("hidden"); }
    $("#bellm").innerHTML = n.items.length ? n.items.map(i => `<a href="${i.link}"><b>${i.count}</b> ${esc(i.text)}</a>`).join("") : `<span class="muted small" style="padding:10px 14px;display:block">Yangi xabar yo'q 🎉</span>`;
  }).catch(() => {});
}

/* ---------- Router ---------- */
const HOME = {admin: "/admin", operator: "/operator", courier: "/courier", customer: "/customer"};
const ROUTES = {
  "": {title: "Bosh sahifa", roles: null, view: viewHome},
  login: {title: "Kirish", roles: null, view: viewLogin},
  operator: {title: "Operator paneli", roles: ["operator", "admin"], view: viewOperator},
  courier: {title: "Kuryer paneli", roles: ["courier"], view: viewCourier},
  customer: {title: "Mijoz kabineti", roles: ["customer"], view: viewCustomer},
  offices: {title: "Ofislarimiz", roles: null, view: viewOffices},
  admin: {title: "Admin paneli", roles: ["admin"], view: viewAdmin},
  t: {title: "Pochta ma'lumoti", roles: null, view: viewParcel},
};
async function render() {
  ++renderId;
  timers.forEach(clearInterval); timers = [];
  if (token && !me) { try { me = await api("GET", "/me"); } catch { me = null; } }
  const [first = "", ...restP] = (location.hash.slice(2) || "").split("/"), sub = restP.join("/");
  const route = ROUTES[first] || ROUTES[""];
  if (route.roles && (!me || !route.roles.includes(me.role))) { location.hash = me ? "#" + HOME[me.role] : "#/login"; return; }
  const items = [["", "Bosh sahifa"], ["offices", "Ofislarimiz"]];
  if (me) {
    if (me.role === "customer") items.push(["customer", "Mening kabinetim"]);
    if (me.role === "operator" || me.role === "admin") items.push(["operator", "Operator paneli"]);
    if (me.role === "courier") items.push(["courier", "Kuryer paneli"]);
    if (me.role === "admin") items.push(["admin", "Admin paneli"]);
  }
  const shell = !!me && !!MENUS[first];
  document.body.classList.toggle("shell", shell);
  document.body.classList.remove("side-open");
  $("#side").innerHTML = shell ? sideHTML(first, sub) : "";
  $("#shellbar").innerHTML = shell ? shellBarHTML(first) : "";
  $("#nav").innerHTML = items.map(([p, t]) => `<a href="#/${p}" class="${p === first ? "on" : ""}">${t}</a>`).join("");
  $("#userbox").innerHTML = !me ? `<a class="btn sm" href="#/login">Kirish</a>` : shell
    ? `<button class="who" id="profileBtn" title="Profil"><span class="uinfo"><b>${esc(me.name)}</b><small>${ROLE_NAME[me.role]} · ${me.office ? esc(me.office.name) : "BTS Express"}</small></span><span class="avatar">${esc(me.name.trim()[0].toUpperCase())}</span></button>`
    : `<button class="who" id="profileBtn" title="Profil">${esc(me.name)} · ${ROLE_NAME[me.role]}</button><button class="btn sec sm" id="logoutBtn">Chiqish</button>`;
  if (me) { $("#profileBtn").onclick = profileModal; if ($("#logoutBtn")) $("#logoutBtn").onclick = logout; }
  if (shell && $("#qs")) wireShellBar();
  if (me && me.role === "operator" && me.shift && me.shift.stale && !(first === "operator" && sub === "shift")) { location.hash = "#/operator/shift"; return; }
  if (me && me.role === "operator" && me.shift && !me.shift.open && !window.__shiftAsked) { window.__shiftAsked = true; setTimeout(() => shiftModal("Smena oching").catch(() => {}), 300); }
  document.title = route.title + " · BTS Express";
  const app = $("#app"); app.innerHTML = ""; window.scrollTo(0, 0);
  await route.view(app, sub);
}
window.addEventListener("hashchange", render);

function tabsHTML(base, tabs, cur) {
  return `<div class="tabs">${tabs.map(([k, t]) => `<a href="#/${base}/${k}" class="${k === cur ? "on" : ""}">${t}</a>`).join("")}</div>`;
}

/* ---------- Profil ---------- */
async function shiftModal(title) {
  const d = await api("GET", "/dict");
  const KEY = "bts_recent_offices";
  let recent = []; try { recent = JSON.parse(localStorage.getItem(KEY) || "[]"); } catch {}
  let sel = me.office ? me.office.code : "";
  const all = d.branches.slice().sort((a, b) => a.name.localeCompare(b.name));
  const label = b => b.code + " " + b.name;
  openModal(`<div class="bp"><h2>${esc(title || "Qaysi ofisda ishlayapsiz?")}</h2><p class="muted">Har kuni ishni boshlashdan oldin smena oching: nomini yozing yoki ro'yxatdan tanlang. Yorliqdagi jo'natuvchi manzili shu ofis manzili bo'ladi.</p>
    <input id="bp_q" class="bp-q" placeholder="Ofis nomi, kodi yoki viloyat…" autocomplete="off">
    <div class="bp-recent" id="bp_recent"></div><div class="bp-list" id="bp_list"></div>
    <div class="bp-foot"><div id="bp_sel" class="muted"></div><div class="acts"><button class="btn" id="bp_ok" disabled>Smenani ochish</button><button class="btn sec" type="button" onclick="closeModal()">Keyinroq</button></div></div></div>`);
  const draw = () => {
    const q = $("#bp_q").value.trim().toLowerCase();
    const list = all.filter(b => !q || (b.code + " " + b.name + " " + (b.region || "") + " " + (b.district || "")).toLowerCase().includes(q));
    const groups = {};
    list.forEach(b => (groups[b.name[0].toUpperCase()] ||= []).push(b));
    $("#bp_list").innerHTML = Object.keys(groups).sort().map(L => `<div class="bp-letter">${esc(L)}</div><div class="bp-grid">${groups[L].map(b =>
      `<button type="button" class="bp-item ${b.code === sel ? "sel" : ""}" data-c="${esc(b.code)}" title="${esc(b.region || "")}"><b>${esc(b.code)}</b> ${esc(b.name)}</button>`).join("")}</div>`).join("") || `<div class="empty">Ma'lumot yo'q</div>`;
    const rc = recent.map(c => d.branches.find(b => b.code === c)).filter(Boolean);
    $("#bp_recent").innerHTML = rc.length ? `<span class="muted small">YAQINDA</span>` + rc.map(b => `<button type="button" class="bp-chip ${b.code === sel ? "sel" : ""}" data-c="${esc(b.code)}">${esc(label(b))}</button>`).join("") : "";
    const cur = d.branches.find(b => b.code === sel);
    $("#bp_sel").innerHTML = cur ? `Tanlandi: <b>${esc(label(cur))}</b><br><span class="small">${esc(cur.address || d.org.address || "")}</span>` : "Ofis tanlanmagan";
    $("#bp_ok").disabled = !cur;
  };
  $("#bp_q").oninput = draw;
  on($("#modalBox"), "click", "[data-c]", b => { sel = b.dataset.c; draw(); });
  $("#bp_ok").onclick = guard(async () => {
    me = await api("POST", "/shift", {branch: sel});
    localStorage.setItem(KEY, JSON.stringify([sel, ...recent.filter(c => c !== sel)].slice(0, 4)));
    closeModal(); toast("Smena ochildi: " + me.office.name); render();
  });
  draw(); $("#bp_q").focus();
}

function profileModal() {
  openModal(`<h2>${esc(me.name)}</h2><p class="muted">Login: <b>${esc(me.username)}</b> · ${ROLE_NAME[me.role]}</p>
    <h3>Parolni o'zgartirish</h3><form id="pf" class="form-grid">
    <div><label>Joriy parol</label><input type="password" name="old" required></div>
    <div><label>Yangi parol (kamida 6 belgi)</label><input type="password" name="new" minlength="6" required></div>
    <div class="full acts"><button class="btn">Saqlash</button><button type="button" class="btn sec" onclick="closeModal()">Yopish</button></div></form>`, true);
  $("#pf").onsubmit = guard(async e => { e.preventDefault(); await api("POST", "/password", readForm(e.target)); closeModal(); toast("Parol yangilandi"); });
}

/* ---------- Bosh sahifa ---------- */
function stepsHTML(status) {
  if (status === "Bekor qilindi") return `<div class="steps"><div class="done">Qabul qilindi</div><div class="bad cur">Bekor qilindi</div></div>`;
  const i = STATUSES.indexOf(status);
  return `<div class="steps">${STATUSES.slice(0, 3).map((s, k) => `<div class="${k < i ? "done" : k === i ? "done cur" : ""}">${s}</div>`).join("")}</div>`;
}
function viewHome(el) {
  el.innerHTML = `
  <section class="card hero">
    <h1>BTS Express pochta xizmati</h1>
    <p>Jo'natmangiz holatini buyurtma raqami orqali tez va oson kuzating.</p>
    <form class="track" id="trackForm"><input id="trackId" placeholder="Masalan: BTS-00001" required autocomplete="off"><button class="btn">Kuzatish</button></form>
  </section>
  <div id="trackRes"></div>
  <section class="card"><h2>Narx kalkulyatori</h2>
    <form id="calcForm" class="form-grid">
      <div><label>Og'irligi (kg)</label><input name="weight" type="number" step="0.01" min="0.01" max="1000" required></div>
      <div><label>Uzunlik (sm)</label><input name="length" type="number" min="0" placeholder="0"></div>
      <div><label>Kenglik (sm)</label><input name="width" type="number" min="0" placeholder="0"></div>
      <div><label>Balandlik (sm)</label><input name="height" type="number" min="0" placeholder="0"></div>
      <div style="align-self:end"><label class="chk"><input type="checkbox" name="door_delivery"> Eshikkacha yetkazish</label></div>
      <div style="align-self:end"><button class="btn">Hisoblash</button></div></form>
    <div id="calcRes" class="muted" style="margin-top:10px"></div></section>
  <div class="grid wide">
    <div class="card"><h2>Tez qabul</h2><p class="muted">Operator buyurtmani bir necha soniyada kiritadi, doimiy mijozlar ma'lumoti avtomatik to'ldiriladi.</p></div>
    <div class="card"><h2>Mas'ul kuryer</h2><p class="muted">Har bir buyurtma kuryerga biriktiriladi, kuryer holatni o'zi yangilaydi.</p></div>
    <div class="card"><h2>To'liq kuzatuv</h2><p class="muted">Qabul qilindi, yo'lda, yetkazildi — barcha bosqichlar vaqti bilan saqlanadi.</p></div>
  </div>`;
  $("#calcForm").onsubmit = async e => {
    e.preventDefault();
    const f = e.target.elements;
    try {
      const q = await api("POST", "/calc", {weight: f.weight.value, length: f.length.value, width: f.width.value, height: f.height.value, door_delivery: f.door_delivery.checked});
      $("#calcRes").innerHTML = `<b style="font-size:1.4em;color:inherit">${money(q.price)}</b> <span class="small">(hisoblanadigan og'irlik: ${q.chargeable_kg} kg${q.door_fee ? ", eshikkacha: " + money(q.door_fee) : ""}, QQS ${money(q.vat_amount)} bilan)</span>`;
    } catch (err) { $("#calcRes").textContent = err.message; }
  };
  $("#trackForm").onsubmit = async e => {
    e.preventDefault();
    const box = $("#trackRes");
    try {
      const o = await api("GET", "/track?id=" + encodeURIComponent($("#trackId").value));
      box.innerHTML = `<div class="card"><h2>${esc(o.code)} ${badge(o.status)}</h2>
        <div class="muted small">Mahsulot: ${esc(o.product)} · Yaratilgan: ${esc(o.created)}</div>${stepsHTML(o.status)}
        <ul class="tl">${o.history.slice().reverse().map(h => `<li><b>${esc(h.status)}</b><div class="muted small">${esc(h.time)}</div></li>`).join("")}</ul></div>`;
    } catch (err) { box.innerHTML = `<div class="card empty">${esc(err.message)}</div>`; }
  };
}

/* ---------- QR-kod ochadigan sahifa: #/t/BTS-00001 ---------- */
async function viewParcel(el, code) {
  const rid = renderId;
  code = decodeURIComponent(code || "");
  let full = null;
  if (me) { try { full = (await api("GET", "/orders?per=1&q=" + encodeURIComponent(code))).items.find(x => x.code === code || x.barcode === code) || null; } catch {} }
  let pub = null, err = "";
  try { pub = await api("GET", "/track?id=" + encodeURIComponent(code)); } catch (e) { err = e.message; }
  if (rid !== renderId) return;
  if (!pub) { el.innerHTML = `<div class="card empty">${esc(err || "Pochta topilmadi")}</div>`; return; }
  const hist = `<ul class="tl">${pub.history.slice().reverse().map(h => `<li><b>${esc(h.status)}</b><div class="muted small">${esc(h.time)}</div></li>`).join("")}</ul>`;
  el.innerHTML = `<div class="parcel"><div class="card"><h2>${esc(pub.code)} ${badge(pub.status)}</h2>
    <div class="muted small">Shtrix-kod: ${esc(spaced(pub.barcode))} · Qabul qilingan: ${esc(pub.created)}</div>${stepsHTML(pub.status)}
    ${full ? detailsHTML(full) : `<dl class="kv"><dt>Mahsulot</dt><dd>${esc(pub.product)}</dd><dt>Og'irligi</dt><dd>${esc(pub.weight)} kg · ${esc(pub.quantity)} dona${pub.package ? " · " + esc(pub.package) : ""}</dd>
      <dt>Qayerdan</dt><dd>${esc(pub.from || "—")}</dd><dt>Qayerga</dt><dd>${esc(pub.to || "—")}${pub.door_delivery ? " (eshikkacha)" : ""}</dd></dl>
      <p class="muted small">Yuboruvchi va qabul qiluvchining shaxsiy ma'lumotlari faqat tizimga kirgan xodimlarga ko'rsatiladi.</p>`}
    <h3>Tarix</h3>${hist}
    ${full ? `<div class="acts"><button class="btn" id="pw">🖨 Chekni ko'rish</button></div>` : ""}</div></div>`;
  if (full) $("#pw").onclick = () => labelModal(full);
}

/* ---------- Kirish ---------- */
function viewLogin(el) {
  if (me) { location.hash = "#" + HOME[me.role]; return; }
  el.innerHTML = `<div class="login"><h1>Tizimga kirish</h1><p class="sub">Admin, operator yoki kuryer sifatida kiring.</p>
  <form class="card" id="loginForm">
    <div><label>Login</label><input id="lu" required autofocus autocomplete="username"></div>
    <div><label>Parol</label><input id="lp" type="password" required autocomplete="current-password"></div>
    <button class="btn" style="width:100%">Kirish</button>
    <div class="hint">Demo: admin/admin123 · operator/operator123 · kuryer1/kuryer123</div>
  </form>
  <p class="sub" style="margin-top:18px">Mijozmisiz? <a href="#" id="regLink">Ro'yxatdan o'tish</a></p>
  <form class="card hidden" id="regForm">
    <div><label>Ism</label><input name="name" required maxlength="80"></div>
    <div><label>Telefon (login bo'ladi)</label><input name="phone" type="tel" placeholder="+998 90 123 45 67" required></div>
    <div><label>Parol (kamida 8 belgi)</label><input name="password" type="password" minlength="8" required autocomplete="new-password"></div>
    <button class="btn" style="width:100%">Ro'yxatdan o'tish</button></form></div>`;
  $("#regLink").onclick = e => { e.preventDefault(); $("#regForm").classList.toggle("hidden"); };
  $("#regForm").onsubmit = async e => {
    e.preventDefault();
    try {
      const r = await api("POST", "/register", readForm(e.target));
      token = r.token; me = r.user; localStorage.setItem("bts_token", token);
      location.hash = "#" + HOME[me.role]; render();
    } catch (err) { toast(err.message, true); }
  };
  $("#loginForm").onsubmit = async e => {
    e.preventDefault();
    try {
      const r = await api("POST", "/login", {username: $("#lu").value, password: $("#lp").value});
      token = r.token; me = r.user; localStorage.setItem("bts_token", token);
      location.hash = "#" + HOME[me.role]; render();
    } catch (err) { toast(err.message, true); }
  };
}

/* ---------- Buyurtma formasi ---------- */
function orderFormHTML(o = {}, couriers = null) {
  const v = k => esc(o[k] ?? "");
  return `
  <fieldset><legend>Yuboruvchi</legend><div class="form-grid">
    <div><label>Yuboruvchi telefoni</label><input name="sender_phone" type="tel" list="custList" placeholder="+998 90 123 45 67" value="${v("sender_phone")}" required></div>
    <div><label>Yuboruvchi ismi</label><input name="sender_name" maxlength="80" value="${v("sender_name")}" required></div></div></fieldset>
  <fieldset><legend>Qabul qiluvchi</legend><div class="form-grid">
    <div><label>Qabul qiluvchi telefoni</label><input name="receiver_phone" type="tel" list="custList" placeholder="+998 90 123 45 67" value="${v("receiver_phone")}" required></div>
    <div><label>Qabul qiluvchi ismi</label><input name="receiver_name" maxlength="80" value="${v("receiver_name")}" required></div>
    <div class="full"><label>Manzil</label><input name="address" maxlength="250" value="${v("address")}" required></div></div></fieldset>
  <fieldset><legend>Jo'natma</legend><div class="form-grid">
    <div><label>Mahsulot</label><input name="product" maxlength="120" value="${v("product")}" required></div>
    <div><label>Og'irligi (kg)</label><input name="weight" type="number" step="0.01" min="0.01" max="1000" value="${v("weight")}" required></div>
    <div><label>Yetkazib berish narxi (so'm)</label><input name="price" type="number" step="500" min="0" value="${v("price")}" required><small class="muted" data-hint></small></div>
    <div><label>To'lovchi</label><select name="payer">${["Yuboruvchi", "Qabul qiluvchi"].map(p => `<option ${p === (o.payer || "Yuboruvchi") ? "selected" : ""}>${p}</option>`).join("")}</select></div>
    ${couriers ? `<div><label>Kuryer (ixtiyoriy)</label><select name="courier_id"><option value="">— keyinroq biriktiriladi —</option>${couriers.map(c => `<option value="${c.id}">${esc(c.name)} (${c.open} ta faol)</option>`).join("")}</select></div>` : ""}
    <div class="full"><label>Izoh (ixtiyoriy)</label><input name="note" maxlength="300" value="${v("note")}"></div></div></fieldset>`;
}
/* mijoz bazasidan avtomatik to'ldirish */
function wireCustomers(form, customers) {
  const norm = v => { const d = v.replace(/\D/g, ""); return d.length === 9 ? "+998" + d : d.length === 12 ? "+" + d : v; };
  const asked = new Set();
  [["sender_phone", "sender_name", "sender_address"], ["receiver_phone", "receiver_name", "address"]].forEach(([p, n, a]) => {
    const inp = form.elements[p];
    inp.addEventListener("change", async () => {
      const ph = norm(inp.value);
      let c = customers.find(x => x.phone === ph);
      if (!c && /^\+998\d{9}$/.test(ph)) {                 // ro'yxatda yo'q bo'lsa, bazadan tekshiramiz, topilmasa ro'yxatdan o'tkazamiz
        try { c = (await api("GET", "/customers?limit=5&q=" + encodeURIComponent(ph))).find(x => x.phone === ph); } catch {}
        if (c) customers.push(c);
        else if (!asked.has(ph)) { asked.add(ph); return registerCustomerModal(ph, form.elements[n].value, rec => { customers.push(rec); inp.value = rec.phone; form.elements[n].value = rec.name; form.elements[n].focus(); }); }
      }
      if (!c) return;
      inp.value = c.phone;
      if (!form.elements[n].value) form.elements[n].value = c.name;
      if (a && form.elements[a] && !form.elements[a].value && c.address) form.elements[a].value = c.address;
    });
  });
}
function registerCustomerModal(phone, name, done) {
  openModal(`<h2 style="font-size:16px;text-transform:uppercase">Yangi mijozni ro'yxatdan o'tkazing</h2><p class="muted small">Bu telefon raqam bazada yo'q. Ismini yozing, mijoz bazaga qo'shiladi.</p>
    <form id="rcF" class="form-grid"><div class="full"><label>To'liq ism *</label><input name="name" required maxlength="80" value="${esc(name || "")}" autofocus></div>
    <div class="full"><label>Brend nomi</label><input name="brand" maxlength="80"></div>
    <div><label>Telefon raqami *</label><input name="phone" type="tel" required value="${esc(phone)}"></div>
    <div><label>Jins *</label><select name="gender"><option value="erkak">erkak</option><option value="ayol">ayol</option></select></div>
    <div class="full acts" style="justify-content:flex-end"><button type="button" class="btn sec" onclick="closeModal()">Keyinroq</button><button class="btn blue">Saqlash</button></div></form>`, true);
  $("#rcF").onsubmit = guard(async e => { e.preventDefault(); const rec = await api("POST", "/customers", readForm(e.target)); closeModal(); toast("Mijoz bazaga qo'shildi: " + rec.name); done(rec); });
}

/* ---------- Yo'lxat chop etish ---------- */
function labelModal(o) {
  openModal(`${labelHTML(o)}<div class="acts no-print" style="justify-content:center"><button class="btn lbl-print" id="lblPrint">CHOP ETISH</button><button class="btn sec" onclick="closeModal()">Yopish</button></div>
    <p class="muted small no-print" style="text-align:center;margin:6px 0 0">QR-kodni telefon bilan skanerlasangiz, shu pochta ma'lumotlari ochiladi.</p>`);
  $("#modalBox").classList.add("lblbox");
  $("#lblPrint").onclick = () => { document.body.classList.add("printing"); window.print(); };
}
window.addEventListener("afterprint", () => document.body.classList.remove("printing"));
const printWaybill = labelModal;

/* ---------- Buyurtmalar ro'yxati (umumiy komponent) ---------- */
function ordersPanel(el, opt) {
  const S = {page: 1, q: "", status: "", from: "", to: "", courier_id: "", ...opt.state};
  let couriers = [], items = [];
  el.innerHTML = `<div class="bar">
    <div class="grow"><label>Qidirish</label><input id="fq" placeholder="Raqam, ism, telefon, manzil, mahsulot..."></div>
    <div><label>Holat</label><select id="fs"><option value="">Barchasi</option>${STATUSES.map(s => `<option>${s}</option>`).join("")}</select></div>
    <div><label>Dan</label><input id="ff" type="date"></div><div><label>Gacha</label><input id="ft" type="date"></div>
    ${opt.admin ? `<div><label>Kuryer</label><select id="fc"><option value="">Barchasi</option><option value="none">Biriktirilmagan</option></select></div>` : ""}
    ${opt.admin ? `<button class="btn sec" id="fx">⬇ CSV</button>` : ""}
  </div><div id="ol"></div>`;
  const qs = (extra = "") => `?page=${S.page}&per=${opt.per || 12}&q=${encodeURIComponent(S.q)}&status=${encodeURIComponent(S.status)}&from=${S.from}&to=${S.to}&courier_id=${S.courier_id}${extra}`;
  const load = guard(async () => {
    const r = await api("GET", "/orders" + qs());
    items = r.items; S.page = r.page;
    $("#ol", el).innerHTML = !items.length ? `<div class="empty">Buyurtmalar topilmadi</div>` : `<div class="tablewrap"><table><thead><tr>
      <th>Raqam</th><th>Yuboruvchi</th><th>Qabul qiluvchi</th><th>Manzil</th><th>Mahsulot</th><th>Narx</th><th>Kuryer</th><th>Holat</th></tr></thead><tbody>
      ${items.map(o => `<tr class="click" data-id="${o.id}">
        <td><b>${esc(o.code)}</b><div class="muted small">${esc(o.created)}</div></td>
        <td>${esc(o.sender_name)}<div class="muted small">${esc(o.sender_phone)}</div></td>
        <td>${esc(o.receiver_name)}<div class="muted small">${esc(o.receiver_phone)}</div></td>
        <td>${esc(o.address)}</td><td>${esc(o.product)}<div class="muted small">${esc(o.weight)} kg</div></td>
        <td>${money(o.price)}</td><td>${esc(o.courier_name || "—")}</td><td>${badge(o.status)}</td></tr>`).join("")}</tbody></table></div>
      <div class="pager"><span class="muted small">Jami: ${r.total} ta</span><div class="acts">
        <button class="btn sec sm" data-pg="${r.page - 1}" ${r.page <= 1 ? "disabled" : ""}>← Oldingi</button>
        <span class="muted small" style="align-self:center">${r.page} / ${r.pages}</span>
        <button class="btn sec sm" data-pg="${r.page + 1}" ${r.page >= r.pages ? "disabled" : ""}>Keyingi →</button></div></div>`;
  });
  const reset = () => { S.page = 1; load(); };
  $("#fq", el).value = S.q; $("#fs", el).value = S.status;
  $("#fq", el).oninput = debounce(e => { S.q = e.target.value; reset(); });
  $("#fs", el).onchange = e => { S.status = e.target.value; reset(); };
  $("#ff", el).onchange = e => { S.from = e.target.value; reset(); };
  $("#ft", el).onchange = e => { S.to = e.target.value; reset(); };
  if (opt.admin) {
    api("GET", "/couriers").then(c => { couriers = c; $("#fc", el).innerHTML += c.map(x => `<option value="${x.id}">${esc(x.name)}</option>`).join(""); });
    $("#fc", el).onchange = e => { S.courier_id = e.target.value; reset(); };
    $("#fx", el).onclick = guard(async () => {
      const r = await api("GET", "/orders/export" + qs().replace(/page=\d+&per=\d+&/, ""), null, true);
      const a = document.createElement("a"); a.href = URL.createObjectURL(await r.blob()); a.download = "buyurtmalar.csv"; a.click();
    });
  }
  on(el, "click", "[data-pg]", b => { if (b.disabled) return; S.page = +b.dataset.pg; load(); });
  on(el, "click", "tr[data-id]", async tr => {
    const o = items.find(x => x.id === +tr.dataset.id);
    if (opt.admin) { if (!couriers.length) couriers = await api("GET", "/couriers"); adminOrderModal(o, couriers, load); } else viewOrderModal(o);
  });
  load();
  return load;
}
function historyHTML(o) {
  return `<ul class="tl">${o.history.slice().reverse().map(h => `<li><b>${esc(h.status)}</b><div class="muted small">${esc(h.time)} · ${esc(h.by)}${h.reason ? " · Sabab: " + esc(h.reason) : ""}</div></li>`).join("")}</ul>`;
}
function detailsHTML(o) {
  return `<dl class="kv"><dt>Yuboruvchi</dt><dd>${esc(o.sender_name)} · ${esc(o.sender_phone)}</dd>
    <dt>Qabul qiluvchi</dt><dd>${esc(o.receiver_name)} · ${esc(o.receiver_phone)}</dd><dt>Manzil</dt><dd>${esc(o.address)}</dd>
    <dt>Mahsulot</dt><dd>${esc(o.product)} · ${esc(o.weight)} kg</dd><dt>Narx</dt><dd>${money(o.price)} (to'lovchi: ${esc(o.payer || "Yuboruvchi")})</dd>
    <dt>Kuryer</dt><dd>${esc(o.courier_name || "— biriktirilmagan")}${o.courier_phone ? " · " + esc(o.courier_phone) : ""}</dd>
    ${o.sender_region ? `<dt>Jo'natish joyi</dt><dd>${esc([o.sender_region, o.sender_district, o.sender_branch].filter(Boolean).join(", "))}${o.sender_address ? " · " + esc(o.sender_address) : ""}</dd>` : ""}
    ${o.receiver_region || o.receiver_branch ? `<dt>Qabul qilish joyi</dt><dd>${esc([o.receiver_region, o.receiver_district, o.receiver_branch].filter(Boolean).join(", "))}${o.door_delivery ? " · eshikkacha" : ""}</dd>` : ""}
    ${o.receiver_phone2 ? `<dt>Tel2</dt><dd>${esc(o.receiver_phone2)}</dd>` : ""}
    ${o.package || o.quantity ? `<dt>Qadoq</dt><dd>${esc(o.package || "—")} · ${esc(o.quantity || 1)} dona${o.vol_weight ? " · hajm og'irligi " + esc(o.vol_weight) + " kg" : ""}</dd>` : ""}
    ${o.payment_type ? `<dt>To'lov turi</dt><dd>${esc(o.payment_type)}${o.vat_amount != null ? " · QQS " + money(o.vat_amount) : ""}${o.paid_from_balance ? " · shaxsiy hisobdan to'langan" + (o.refunded ? " (qaytarilgan)" : "") : ""}</dd>` : ""}
    ${o.by_call ? `<dt>Qo'ng'iroq</dt><dd>Ha</dd>` : ""}${o.transport ? `<dt>Transport</dt><dd>${esc(o.transport)}</dd>` : ""}
    ${o.note ? `<dt>Izoh</dt><dd>${esc(o.note)}</dd>` : ""}${o.cancel_reason ? `<dt>Bekor sababi</dt><dd>${esc(o.cancel_reason)}</dd>` : ""}
    ${o.trip_id ? `<dt>Reys</dt><dd>${esc(o.trip_id)}</dd>` : ""}${o.shelf ? `<dt>Shkaf</dt><dd>${esc(o.shelf)}</dd>` : ""}
    <dt>Yaratgan</dt><dd>${esc(o.created_by)} · ${esc(o.created)}</dd></dl>` + ((o.edits || []).length ? `<h4 style="margin:14px 0 6px">Tahrir tarixi</h4><ul class="tl">${o.edits.slice().reverse().map(e => `<li><b>${esc(e.by)}</b><div class="muted small">${esc(e.time)} · ${Object.entries(e.changes).map(([k, v]) => esc(k) + ": " + esc(v[0] ?? "—") + " → " + esc(v[1] ?? "—")).join("; ")}</div></li>`).join("")}</ul>` : "");
}

/* ---------- Fayllar (Amazon S3) ---------- */
const fmtSize = n => n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB";
function readB64(file) {
  return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(",")[1]); r.onerror = () => rej(new Error("Faylni o'qib bo'lmadi")); r.readAsDataURL(file); });
}
async function uploadFile(orderId, file, kind) {
  if (file.size > 5 * 1024 * 1024) throw new Error("Fayl hajmi 5 MB dan oshmasligi kerak");
  return api("POST", `/orders/${orderId}/files`, {name: file.name, type: file.type, data: await readB64(file), kind});
}
async function openFile(orderId, i) { const r = await api("GET", `/orders/${orderId}/files/${i}`); location.href = r.url; }
function filesHTML(o, canDelete) {
  const f = o.files || [];
  return `<h3 style="margin-top:20px">${ico("clip")} Fayllar <span class="muted small">(Amazon S3)</span></h3>
    ${f.length ? `<div class="filelist">${f.map((x, i) => `<div class="frow"><span>${esc(x.kind)} · <a href="#" data-open="${i}">${esc(x.name)}</a> <span class="muted small">${fmtSize(x.size)} · ${esc(x.by)} · ${esc(x.time)}</span></span>
      ${canDelete ? `<button class="btn sec sm" data-fdel="${i}">O'chirish</button>` : ""}</div>`).join("")}</div>` : `<div class="muted small">Fayl yuklanmagan</div>`}
    <div class="acts"><label class="btn sec">+ Rasm yoki PDF yuklash<input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" data-upload hidden></label>
    ${o.waybill_key ? `<a class="btn sec" href="#" data-waybill>S3'dagi yo'l varaqasi</a>` : ""}</div>`;
}
function mountFiles(box, o, canDelete, kind) {
  const draw = () => { box.innerHTML = filesHTML(o, canDelete); };
  draw();
  on(box, "click", "[data-open]", guard(async (b, e) => { e.preventDefault(); await openFile(o.id, +b.dataset.open); }));
  on(box, "click", "[data-waybill]", guard(async (b, e) => { e.preventDefault(); const r = await api("GET", "/orders/waybill?code=" + encodeURIComponent(o.code)); location.href = r.url; }));
  on(box, "click", "[data-fdel]", guard(async b => {
    if (!await confirmBox("Fayl o'chirilsinmi?", "O'chirish")) return;
    Object.assign(o, await api("DELETE", `/orders/${o.id}/files/${b.dataset.fdel}`)); draw(); toast("Fayl o'chirildi");
  }));
  on(box, "change", "[data-upload]", guard(async inp => {
    if (!inp.files[0]) return;
    toast("Yuklanmoqda…"); Object.assign(o, await uploadFile(o.id, inp.files[0], kind)); draw(); toast("Fayl yuklandi");
  }));
}
function viewOrderModal(o) {
  openModal(`<h2>${esc(o.code)} ${badge(o.status)}</h2>${detailsHTML(o)}<div class="acts"><button class="btn" id="pw">🖨 Yo'lxat</button><button class="btn sec" onclick="closeModal()">Yopish</button></div>
    <div id="fbox"></div><h3 style="margin-top:20px">Tarix</h3>${historyHTML(o)}`);
  $("#pw").onclick = () => printWaybill(o);
  mountFiles($("#fbox"), o, false, "attachment");
}
function adminOrderModal(o, couriers, reload) {
  openModal(`<h2>${esc(o.code)} ${badge(o.status)}</h2>
    <div class="form-grid" style="margin-bottom:8px">
      <div><label>Holat</label><select id="mst">${STATUSES.map(s => `<option ${s === o.status ? "selected" : ""}>${s}</option>`).join("")}</select></div>
      <div><label>Kuryer</label><select id="mcr"><option value="">— biriktirilmagan —</option>${couriers.map(c => `<option value="${c.id}" ${c.id === o.courier_id ? "selected" : ""}>${esc(c.name)} (${c.open} ta faol)</option>`).join("")}</select></div>
      <div class="full" id="rbox" style="display:none"><label>Bekor qilish sababi</label><input id="mre" maxlength="300"></div></div>
    <form id="mf"><h3 style="margin-top:16px">Ma'lumotlarni o'zgartirish</h3>${orderFormHTML(o)}
      <div class="acts"><button class="btn">Saqlash</button><button type="button" class="btn sec" id="mpw">🖨 Yo'lxat</button>
      <button type="button" class="btn danger" id="mdel">O'chirish</button><button type="button" class="btn sec" onclick="closeModal()">Yopish</button></div></form>
    <div id="fbox"></div><h3 style="margin-top:22px">Tarix</h3>${historyHTML(o)}`);
  mountFiles($("#fbox"), o, true, "attachment");
  const toggle = () => $("#rbox").style.display = $("#mst").value === "Bekor qilindi" && o.status !== "Bekor qilindi" ? "" : "none";
  $("#mst").onchange = toggle; toggle();
  $("#mpw").onclick = () => printWaybill(o);
  $("#mf").onsubmit = guard(async e => {
    e.preventDefault();
    const st = $("#mst").value, cr = $("#mcr").value;
    if (st !== o.status && st === "Bekor qilindi" && !$("#mre").value.trim()) return toast("Bekor qilish sababini kiriting", true);
    await api("PUT", "/orders/" + o.id, readForm(e.target));
    if (st !== o.status) await api("POST", `/orders/${o.id}/status`, {status: st, reason: $("#mre").value});
    if (String(cr) !== String(o.courier_id ?? "")) await api("POST", `/orders/${o.id}/assign`, {courier_id: cr || null});
    closeModal(); toast("Saqlandi"); reload();
  });
  $("#mdel").onclick = guard(async () => {
    if (!await confirmBox(o.code + " buyurtmasi o'chirilsinmi?", "O'chirish")) return;
    await api("DELETE", "/orders/" + o.id); toast("O'chirildi"); reload();
  });
}

/* ---------- Mijozlar ---------- */
async function customersPanel(el) {
  el.innerHTML = `<div class="card"><div class="bar"><div class="grow"><label>Qidirish</label><input id="cq" placeholder="Ism yoki telefon"></div></div><div id="cl"></div></div>`;
  const load = guard(async () => {
    const list = await api("GET", "/customers?q=" + encodeURIComponent($("#cq").value));
    if (!$("#cl")) return;
    $("#cl").innerHTML = list.length ? `<div class="tablewrap"><table><thead><tr><th>Ism</th><th>Telefon</th><th>Oxirgi manzil</th><th>Buyurtmalar</th><th>Hisob</th><th>Oxirgi</th><th></th></tr></thead><tbody>
      ${list.map(c => `<tr><td>${esc(c.name)}</td><td><a href="tel:${esc(c.phone)}">${esc(c.phone)}</a></td><td>${esc(c.address || "—")}</td><td>${c.orders}</td><td>${money(c.balance || 0)}</td><td class="muted small">${esc(c.last || "")}</td>
      <td><button class="btn sec sm" data-acct="${esc(c.phone)}" data-name="${esc(c.name)}">Shaxsiy hisob</button></td></tr>`).join("")}</tbody></table></div>`
      : `<div class="empty">Mijozlar topilmadi. Buyurtma yaratilganda mijozlar avtomatik saqlanadi.</div>`;
  });
  $("#cq").oninput = debounce(load); load();
  on(el, "click", "[data-acct]", guard(b => accountModal(b.dataset.acct, b.dataset.name, load)));
}

/* ---------- Tarif ---------- */
let tariff = null;
const calcPrice = w => {
  const t = tariff, raw = t.base + t.per_kg * Math.max(0, w - t.free_kg);
  return Math.ceil(raw / t.round_to - 1e-9) * t.round_to;
};
function wireTariff(form) {
  if (!tariff) return;
  const w = form.elements.weight, p = form.elements.price, hint = $("[data-hint]", form);
  if (hint) hint.textContent = `Tarif: ${money(tariff.base)} (${tariff.free_kg} kg gacha) + har kg uchun ${money(tariff.per_kg)}`;
  let manual = false;
  p.addEventListener("input", () => { manual = true; });
  w.addEventListener("input", () => { if (!manual && +w.value > 0) p.value = calcPrice(+w.value); });
  form.addEventListener("reset", () => { manual = false; });
}

/* ---------- Operator paneli ---------- */
const pageHead = (t, i) => `<div class="pagehead">${ico(i)}<h1>${t}</h1></div>`;
const todayISO = () => new Date().toISOString().slice(0, 10);

async function viewOperator(el, sub) {
  const rid = renderId;
  if (sub === "orders" || sub === "today") {
    el.innerHTML = pageHead(sub === "today" ? "Bugungi buyurtmalar" : "Buyurtmalar ro'yxati", sub === "today" ? "clock" : "list") + `<div class="card" id="tab"></div>`;
    return void ordersPanel($("#tab"), {admin: false, state: sub === "today" ? {from: todayISO(), to: todayISO()} : {}});
  }
  const FILTERED = {delivery: ["Pochta yetkazib berish", "upload", "Yo'lda"], delivered: ["Yetkazilgan yuklar hisoboti", "check", "Yetkazildi"], returns: ["Qaytarish jo'natmalari", "undo", "Bekor qilindi"]};
  if (FILTERED[sub]) {
    const [t, i, st] = FILTERED[sub];
    el.innerHTML = pageHead(t, i) + `<div class="card" id="tab"></div>`;
    return void ordersPanel($("#tab"), {admin: false, state: {status: st}});
  }
  if (sub === "prices") return operatorPrices(el, rid);
  if (sub === "offices") return operatorOffices(el, rid);
  if (sub === "customers") { el.innerHTML = pageHead("Mijozlar", "users") + `<div id="tab"></div>`; return customersPanel($("#tab")); }
  if (sub === "track") return operatorTrack(el);
  if (sub === "assign") return operatorAssign(el, rid);
  if (sub === "stats") return operatorStats(el, rid);
  if (sub === "cash") { el.innerHTML = pageHead("Inkassatsiya", "tag") + `<div id="tab"></div>`; return cashPanel($("#tab")); }
  if (sub === "kpi") { el.innerHTML = pageHead("KPI", "chart") + `<div id="tab"></div>`; return kpiPanel($("#tab")); }
  if (sub === "complaints") { el.innerHTML = pageHead("Shikoyatlar ro'yxati", "clip") + `<div id="tab"></div>`; return complaintsPanel($("#tab")); }
  if (sub === "shift") { el.innerHTML = pageHead("Smena monitoringi", "check") + `<div id="tab"></div>`; return shiftPanel($("#tab")); }
  if (sub === "moves") { el.innerHTML = pageHead("Pochta harakati", "list") + `<div id="tab"></div>`; return movementsPanel($("#tab")); }
  if (sub === "pmp") { el.innerHTML = pageHead("Qadoqlash materiallari (PMP)", "file") + `<div id="tab"></div>`; return pmpPanel($("#tab")); }
  if (sub === "warehouse") { el.innerHTML = pageHead("Ombor: qatorlar va shkaflar", "file") + `<div id="tab"></div>`; return warehousePanel($("#tab")); }
  if (sub.startsWith("trips/")) { el.innerHTML = pageHead("Reys", "truck") + `<div id="tab"></div>`; return tripsPanel($("#tab"), sub.split("/")[1]); }
  if (sub === "trips") { el.innerHTML = pageHead("Reyslar (manifest)", "truck") + `<div id="tab"></div>`; return tripsPanel($("#tab")); }
  if (sub === "scan") { el.innerHTML = pageHead("Skaner rejimi", "search") + `<div id="tab"></div>`; return scanPanel($("#tab")); }
  if (sub === "danger") { el.innerHTML = pageHead("Xavfli yuklar", "shield") + `<div id="tab"></div>`; return dangerPanel($("#tab")); }
  if (sub === "handover") { el.innerHTML = pageHead("Pochtani topshirish", "check") + `<div id="tab"></div>`; return handoverPanel($("#tab")); }
  if (sub === "new") return operatorNew(el, rid);
  /* Uy: kartochkalar */
  let ms = null; try { ms = await api("GET", "/mystats"); } catch {}
  if (rid !== renderId) return;
  const T = (k, t, i, c, n) => `<a class="tile ${c || ""}" href="#/operator/${k}" ${k === "shift" && !(me.shift && me.shift.open) ? "data-shift" : ""}>${n ? `<span class="cnt">${n}</span>` : ""}${ico(i)}<span>${t}</span></a>`;
  const groups = [
    ["Operatsion vazifalar", [["new", "Pochta qabul qilish", "plus", "primary"], ["orders", "Yo'l varaqalari ro'yxati", "list"], ["today", "Bugungi buyurtmalar", "clock", "", ms ? ms.all_today : null],
      ["assign", "Kuryerga bering", "truck"], ["delivery", "Pochta yetkazib berish", "upload"], ["handover", "Pochtani topshirish", "check"], ["warehouse", "Ombor (qatorlar va shkaflar)", "file"],
      ["scan", "Skaner rejimi", "search"], ["trips", "Reyslar (manifest)", "truck"], ["pmp", "Qadoqlash materiallari (PMP)", "file"],
      ["returns", "Qaytarish jo'natmalari", "undo"], ["moves", "Pochta harakati", "list"]]],
    ["Mijozlar va ma'lumot", [["customers", "Mijozlar", "users"], ["track", "Pochtani kuzatish", "search"], ["prices", "Narxlar", "file"], ["offices", "Bizning ofislarimiz", "pin"]]],
    ["Hisobotlar", [["delivered", "Yetkazilgan yuklar hisoboti", "check"], ["stats", "Ko'rsatkichlarim", "chart"], ["kpi", "KPI", "chart"], ["cash", "Inkassatsiya idorasi", "tag"], ["shift", me.shift && me.shift.open ? "Smenani yopish (Z)" : "Smena ochish", me.shift && me.shift.open ? "check" : "plus", me.shift && me.shift.open ? "" : "primary"]]],
    ["Sifat nazorati", [["complaints", "Shikoyatlar ro'yxati", "clip"], ["danger", "Xavfli yuklar", "shield"]]],
  ];
  const sh = me.shift || {};
  const banner = sh.stale ? `<div class="alert">⚠ Kechagi smena (${esc(sh.code)}) yopilmagan. <a href="#/operator/shift">Smenani yopish</a>, so'ng yangi smena oching.</div>`
    : sh.open ? `<div class="alert" style="background:#ecf8f0;border-color:#b7e2c6;color:#1e6b3a">✔ Smena <b>${esc(sh.code)}</b> ochiq · boshlangan: ${esc(sh.start)} · <a href="#/operator/shift">Smena monitoringi</a></div>`
    : `<div class="alert">⚠ Smena ochilmagan — buyurtma qabul qilib bo'lmaydi. <a href="#" data-shift>Smena ochish</a></div>`;
  el.innerHTML = `<div class="officebar">Xodimlar ofisi${me.office ? " · " + esc(me.office.code + " " + me.office.name) : ""}</div>${banner}<div class="homebar"><a class="btn blue" href="#/operator/stats">Ko'rsatkichlarim</a></div>
    ${groups.map(([h, ts]) => `<h3 class="sec">${h}</h3><div class="tiles">${ts.map(t => T(...t)).join("")}</div>`).join("")}
    <div class="tiles" style="margin-top:22px"><a class="tile" href="#/">${ico("globe")}<span>Mijozlar uchun sahifa</span></a><a class="tile exit" href="#" data-logout>${ico("logout")}<span>Chiqish</span></a></div>`;
}

async function operatorPrices(el, rid) {
  const t = await api("GET", "/tariff");
  try { window.__pk = (await api("GET", "/dict")).packaging; } catch {}
  if (rid !== renderId) return;
  const rows = [["Boshlang'ich narx", money(t.base)], ["Bepul og'irlik", t.free_kg + " kg"], ["Har qo'shimcha kg", money(t.per_kg)],
    ["Yaxlitlash", money(t.round_to)], ["Eshikkacha yetkazish", money(t.door_fee)], ["QQS", t.vat + " %"], ["Hajm bo'luvchi", t.vol_divisor]];
  el.innerHTML = pageHead("Narxlar", "file") + `<div class="grid"><div class="card"><h3>Joriy tarif</h3>
    <table><tbody>${rows.map(([k, v]) => `<tr><td>${k}</td><td><b>${v}</b></td></tr>`).join("")}</tbody></table></div>
    <div class="card"><h3>Qadoqlash materiallari</h3>${(window.__pk || []).map(p => `<h4 style="margin:8px 0 4px">${esc(p.type)}</h4><div class="chips">${p.sizes.map(z => `<span class="chip">${esc(z.size)} · ${z.price ? money(z.price) : "—"}</span>`).join("")}</div>`).join("")}</div>
    <div class="card"><h3>Narx hisoblagich</h3><div class="form-grid"><div><label>Og'irlik (kg)</label><input id="pw_kg" type="number" min="0" step="any"></div>
    <div><label>Eshikkacha yetkazish</label><select id="pw_door"><option value="0">Yo'q</option><option value="1">Ha</option></select></div></div>
    <p id="pw_out" class="muted" style="margin-top:14px">Og'irlikni kiriting</p></div></div>`;
  tariff = t;
  const calc = () => {
    const w = +$("#pw_kg").value; if (!(w > 0)) { $("#pw_out").textContent = "Og'irlikni kiriting"; return; }
    const net = calcPrice(w) + ($("#pw_door").value === "1" ? t.door_fee : 0), vat = Math.round(net * t.vat / 100);
    $("#pw_out").innerHTML = `Summa: <b>${money(net)}</b> · QQS: ${money(vat)} · Jami: <b>${money(net + vat)}</b>`;
  };
  $("#pw_kg").oninput = calc; $("#pw_door").onchange = calc;
}

async function operatorOffices(el, rid) {
  const d = await api("GET", "/dict");
  if (rid !== renderId) return;
  el.innerHTML = pageHead("Bizning ofislarimiz", "pin") + `<div class="card"><div class="bar"><div class="grow"><label>Qidirish</label><input id="of_q" placeholder="Kod yoki nom"></div>
    <div><label>Viloyat</label><select id="of_r"><option value="">Barchasi</option>${Object.keys(d.regions).map(r => `<option>${esc(r)}</option>`).join("")}</select></div></div><div id="of_l"></div></div>`;
  const draw = () => {
    const q = $("#of_q").value.trim().toLowerCase(), r = $("#of_r").value;
    const list = d.branches.filter(b => (!r || b.region === r) && (!q || (b.code + " " + b.name).toLowerCase().includes(q)));
    $("#of_l").innerHTML = list.length ? `<div class="tablewrap"><table><thead><tr><th>Kod</th><th>Ofis</th><th>Viloyat</th><th>Tuman / shahar</th></tr></thead><tbody>
      ${list.slice(0, 300).map(b => `<tr><td><b>${esc(b.code)}</b></td><td>${esc(b.name)}</td><td>${esc(b.region || "—")}</td><td>${esc(b.district || "—")}</td></tr>`).join("")}</tbody></table></div>
      <div class="muted small" style="margin-top:8px">${list.length} ta ofis${list.length > 300 ? " (dastlabki 300 tasi)" : ""}</div>` : `<div class="empty">Ofis topilmadi</div>`;
  };
  $("#of_q").oninput = debounce(draw, 200); $("#of_r").onchange = draw; draw();
}

const FL = (name, label, {type = "text", req = false, ro = false, attrs = "", cls = "", value = ""} = {}) =>
  `<div class="fl ${req ? "req" : ""} ${cls}"><label>${label}</label><input name="${name}" type="${type}" ${req ? "required" : ""} ${ro ? "readonly" : ""} value="${esc(value)}" ${attrs}></div>`;
const SEL = (name, label, opts, {req = false, cls = "", first = "---"} = {}) =>
  `<div class="fl ${req ? "req" : ""} ${cls}"><label>${label}</label><select name="${name}" ${req ? "required" : ""}><option value="">${first}</option>${opts.map(o => `<option>${esc(o)}</option>`).join("")}</select></div>`;
const fmt = n => new Intl.NumberFormat("uz-UZ").format(Math.round(n || 0));

function bigOrderHTML(dict, couriers) {
  const regs = Object.keys(dict.regions), org = dict.org || {};
  return `
  <div class="of-top">
    <label class="chk pill"><input type="checkbox" name="by_call"> Qo'ng'iroq</label>
    <button type="button" class="btn sm acct" data-acct="sender">${ico("user")} Shaxsiy hisob (yuboruvchi)</button>
    <span class="muted small">Buyurtma qabul qilish · ${esc(me.name)}</span>
  </div>
  <div class="of-cols">
   <div class="of-col">
    <div class="of-row c2">${FL("date", "Sana", {type: "date", value: todayISO()})}${FL("sender_phone", "Telefon", {type: "tel", req: true, attrs: 'list="custList" placeholder="+998 90 123 45 67"'})}</div>
    <div class="of-row">${FL("sender_name", "Yuboruvchi", {req: true, attrs: 'maxlength="80"'})}</div>
    <div class="of-row c3">${SEL("sender_region", "Viloyat / shahar", regs, {req: true})}${SEL("sender_district", "Tuman / shahar", [])}${SEL("sender_branch", "Filial", [])}</div>
    <div class="of-row">${FL("sender_address", "Jo'natuvchining manzili", {attrs: 'maxlength="250"'})}</div>
    <div class="of-row c2">${SEL("product", "Ichkarida", dict.contents, {req: true})}${SEL("package", "Paket", dict.packages)}</div>
    <div class="of-row c3">${FL("weight", "Vazni (kg)", {type: "number", req: true, attrs: 'step="0.01" min="0.01" max="1000"'})}${FL("vw_view", "Hajm og'irligi (kg)", {ro: true, value: "0"})}${FL("quantity", "Miqdori", {type: "number", value: "1", attrs: 'min="1" step="1"'})}</div>
    <div class="of-row c4">${FL("width", "Kenglik (sm)", {type: "number", attrs: 'min="0" step="0.1"'})}${FL("height", "Balandligi (sm)", {type: "number", attrs: 'min="0" step="0.1"'})}${FL("length", "Uzunlik (sm)", {type: "number", attrs: 'min="0" step="0.1"'})}${FL("vol_view", "Hajmi (sm³)", {ro: true, value: "0"})}</div>
    <div class="of-row c2">${SEL("courier_id", "Kuryer", [], {first: "— keyinroq biriktiriladi —"})}${SEL("transport", "Transport turi", dict.transports, {first: "Avtomatik"})}</div>
    <div class="of-row c2">${FL("barcode", "Mijoz shtrix-kodi", {attrs: 'maxlength="60"'})}${FL("note", "Izoh", {attrs: 'maxlength="300"'})}</div>
   </div>
   <div class="of-col">
    <div class="of-row" style="grid-template-columns:1fr auto;align-items:center"><label class="chk"><input type="checkbox" name="door_delivery"> Yetkazib berish (eshikkacha)</label>
      <button type="button" class="btn sm acct" data-acct="receiver">${ico("user")} Shaxsiy hisob</button></div>
    <div class="of-row c2">${FL("receiver_phone", "Tel1", {type: "tel", req: true, attrs: 'list="custList" placeholder="+998 90 123 45 67"'})}${FL("receiver_phone2", "Tel2", {type: "tel"})}</div>
    <div class="of-row">${FL("receiver_name", "Qabul qiluvchi", {req: true, attrs: 'maxlength="80"'})}</div>
    <div class="of-row c3">${SEL("receiver_region", "Viloyat / shahar", regs)}${SEL("receiver_district", "Tuman / shahar", [])}${SEL("receiver_branch", "Filial", [], {req: true})}</div>
    <div class="of-row">${FL("address", "Manzil", {attrs: 'maxlength="250" placeholder="Tuman, ko\'cha, uy raqami"'})}</div>
    <div class="receipt">
      <h4>Elektron chek raqami</h4>
      <div class="org"><b>Tashkilot:</b><span>${esc(org.name || "")}</span><b>INN:</b><span>${esc(org.inn || "")}</span><b>Manzil:</b><span>${esc(org.address || "")}</span><b>Sayt:</b><span>${esc(org.site || "")}</span></div>
      <table><thead><tr><th>Boshlang'ich narx</th><th>Qo'shimcha kg</th><th>Yetkazib berish</th><th>Qo'shimcha xizmat</th></tr></thead>
        <tbody><tr><td id="q_base">0</td><td id="q_kg">0</td><td id="q_door">0</td><td id="q_extra">0</td></tr></tbody></table>
      <div class="sumrow">
        ${FL("price_view", "Summa:", {ro: true, value: "0", attrs: 'id="sum"'})}
        ${FL("extra_service", "Qo'shimcha xizmat:", {type: "number", attrs: 'min="0" step="500"'})}
        <button type="button" class="btn blue" id="pmpBtn" title="Qadoqlash materiallari (PMP)">📦 PMP</button>
        ${SEL("payment_type", "To'lov turi", dict.payment_types, {req: true})}
        <button type="button" class="refresh" id="rf" title="Qayta hisoblash">⟳</button>
      </div>
      <div class="of-row c2" style="margin:14px 0 0">${SEL("payer", "To'lovchi", ["Yuboruvchi", "Qabul qiluvchi"], {first: "Yuboruvchi"})}<span></span></div>
      <div class="tot"><span>QQS (${tariff.vat}%): <b id="q_vat" style="font-size:inherit">0</b> so'm · QQS bilan summa:</span><b id="q_total">0</b></div>
      <div class="cash" id="bal">Mijoz hisobida: —</div>
      <div class="cash">Kassir: ${esc(me.name)}</div>
    </div>
   </div>
  </div>
  <div class="of-foot">
    <button class="btn green" id="saveBtn">💾 Saqlash</button>
    <div class="acts"><button type="button" class="btn redo" id="closeBtn">✕ Yopiq</button><button type="button" class="btn yellow" id="copyBtn">⧉ Nusxalash</button></div>
  </div>`;
}

function quoteLocal(f) {
  const t = tariff, g = n => +(f.elements.namedItem(n) || {}).value || 0;  // "length" nomi form.elements.length bilan to'qnashadi
  const w = g("weight"), volume = g("length") * g("width") * g("height"), vw = volume / t.vol_divisor, cw = Math.max(w, vw);
  const tar = cw > 0 ? Math.ceil((t.base + t.per_kg * Math.max(0, cw - t.free_kg)) / t.round_to - 1e-9) * t.round_to : 0;
  const door = f.elements.door_delivery.checked ? t.door_fee : 0, extra = Math.max(0, g("extra_service"));
  const net = tar + door + extra, vat = Math.floor(net * t.vat / 100 + 0.5);
  return {volume, vw, tar, door, extra, net, vat, total: net + vat};
}

function cascade(form, prefix, dict) {
  const reg = form.elements[prefix + "_region"], dis = form.elements[prefix + "_district"], br = form.elements[prefix + "_branch"];
  const opts = a => `<option value="">---</option>` + a.map(x => `<option>${esc(x)}</option>`).join("");
  // Filial faqat tanlangan viloyatniki; tuman tanlangan bo'lsa shu tumanniki (tumansiz filiallar butun viloyat uchun)
  const fillBranches = () => {
    const keep = br.value;
    const list = dict.branches.filter(b => reg.value && b.region === reg.value && (!dis.value || !b.district || b.district === dis.value));
    br.innerHTML = opts(list.map(b => b.code + " - " + b.name));
    if (keep) br.value = keep;
  };
  reg.onchange = () => { dis.innerHTML = opts(dict.regions[reg.value] || []); fillBranches(); };
  dis.onchange = fillBranches;
  reg.onchange();
}

async function operatorNew(el, rid) {
  el.innerHTML = pageHead("Pochta qabul qilish", "mail") + `<div id="tab"></div>`;
  const tab = $("#tab");
  const [customers, couriers, tf, dict] = await Promise.all([api("GET", "/customers?limit=500"), api("GET", "/couriers"), api("GET", "/tariff"), api("GET", "/dict")]);
  if (rid !== renderId) return;
  tariff = tf;
  tab.innerHTML = `<datalist id="custList">${customers.map(c => `<option value="${esc(c.phone)}">${esc(c.name)}</option>`).join("")}</datalist>
    <div id="done"></div><form class="of" id="orderForm" novalidate>${bigOrderHTML(dict, couriers)}</form>`;
  const form = $("#orderForm"), E = form.elements;
  E.courier_id.innerHTML = `<option value="">— keyinroq biriktiriladi —</option>` + couriers.map(c => `<option value="${c.id}">${esc(c.name)} (${c.open} ta faol)</option>`).join("");
  cascade(form, "sender", dict); cascade(form, "receiver", dict);
  const setDefaults = () => {
    const o = me.office;
    E.sender_region.value = o ? o.region : Object.keys(dict.regions)[0]; E.sender_region.onchange();
    if (o) { if (o.district) { E.sender_district.value = o.district; E.sender_district.onchange(); } E.sender_branch.value = o.code + " - " + o.name; }
    sync();
  };
  const sync = () => {
    const door = E.door_delivery.checked;
    E.address.required = door; E.receiver_branch.required = !door;
    E.address.closest(".fl").classList.toggle("req", door); E.receiver_branch.closest(".fl").classList.toggle("req", !door);
    const q = quoteLocal(form);
    E.vw_view.value = q.vw.toFixed(2); E.vol_view.value = Math.round(q.volume);
    E.price_view.value = fmt(q.net);
    $("#q_base").textContent = fmt(q.tar ? tariff.base : 0); $("#q_kg").textContent = fmt(q.tar ? q.tar - tariff.base : 0);
    $("#q_door").textContent = fmt(q.door); $("#q_extra").textContent = fmt(q.extra);
    $("#q_vat").textContent = fmt(q.vat); $("#q_total").textContent = fmt(q.total);
  };
  let lastTotal = 0;
  const payerPhone = () => (E.payer.value === "Qabul qiluvchi" ? E.receiver_phone.value : E.sender_phone.value).trim();
  const showBal = bal => {
    const b = $("#bal"); if (!b) return;
    if (bal == null) { b.textContent = "Mijoz hisobida: —"; b.style.color = ""; return; }
    const short = E.payment_type.value === "Balans" && bal < lastTotal;
    b.textContent = `Mijoz hisobida: ${money(bal)}` + (short ? " — mablag' yetarli emas!" : "");
    b.style.color = short ? "#ff9d8a" : "";
  };
  let bal = null;
  const refreshBalance = debounce(async () => {
    const ph = payerPhone(); if (!ph) { bal = null; return showBal(null); }
    try { bal = (await api("GET", "/customers/balance?phone=" + encodeURIComponent(ph))).balance; } catch { bal = null; }
    showBal(bal);
  }, 400);
  form.addEventListener("input", () => { sync(); lastTotal = quoteLocal(form).total; showBal(bal); });
  form.addEventListener("change", () => { sync(); lastTotal = quoteLocal(form).total; refreshBalance(); });
  $("#rf").onclick = () => { sync(); refreshBalance(); };
  on(tab, "click", "[data-acct]", guard(b => {
    const pre = b.dataset.acct, ph = E[pre + "_phone"].value.trim();
    if (!ph) return toast("Avval telefon raqamini kiriting", true);
    return accountModal(ph, E[pre + "_name"].value, refreshBalance);
  }));
  wireCustomers(form, customers); setDefaults();

  let last = null, pack = [];
  const prices = dict.packaging || [];
  $("#pmpBtn").onclick = () => prices.length && pmpModal(prices, pack, rows => {
    pack = rows; const tot = pmpTotal(prices, rows);
    E.extra_service.value = tot || ""; E.extra_service.dispatchEvent(new Event("input", {bubbles: true}));
    $("#pmpBtn").textContent = pack.length ? "📦 PMP · " + money(tot) : "📦 PMP";
  });
  const payload = () => {
    const o = {};
    for (const [k, v] of new FormData(form).entries()) if (v !== "" && !k.endsWith("_view")) o[k] = v;
    o.by_call = E.by_call.checked; o.door_delivery = E.door_delivery.checked; o.auto_price = true;
    if (pack.length) o.packaging = pack;
    return o;
  };
  form.onsubmit = guard(async e => {
    e.preventDefault();
    if (!form.reportValidity()) return;
    const body = payload();
    const o = await api("POST", "/orders", body);
    last = body; form.reset(); pack = []; $("#pmpBtn").textContent = "📦 PMP"; setDefaults(); bal = null; showBal(null);
    $("#done").innerHTML = `<div class="card success"><h2>✅ Buyurtma qabul qilindi: ${esc(o.code)}</h2>
      <p class="muted">Summa: <b>${money(o.price)}</b> (QQS bilan). Mijoz shu raqam bilan bosh sahifada holatni kuzata oladi.</p>
      <div class="acts"><button class="btn" id="pw">🖨 Yo'lxatni chop etish</button><button class="btn sec" id="nx">+ Yangi buyurtma</button><a class="btn sec" href="#/operator">← Uyga</a></div></div>`;
    $("#pw").onclick = () => printWaybill(o);
    $("#nx").onclick = () => { $("#done").innerHTML = ""; E.sender_phone.focus(); };
    toast("Buyurtma saqlandi: " + o.code); window.scrollTo(0, 0); labelModal(o);
    if (o.warnings) setTimeout(() => toast("⚠ " + o.warnings[0], true), 3200);
    api("GET", "/customers?limit=500").then(c => { customers.splice(0, customers.length, ...c); const dl = $("#custList"); if (dl) dl.innerHTML = c.map(x => `<option value="${esc(x.phone)}">${esc(x.name)}</option>`).join(""); });
  });
  $("#closeBtn").onclick = () => { location.hash = "#/operator"; };
  $("#copyBtn").onclick = () => {
    if (!last) return toast("Nusxalash uchun avval buyurtmani saqlang", true);
    for (const pre of ["sender", "receiver"]) {
      E[pre + "_region"].value = last[pre + "_region"] || ""; E[pre + "_region"].onchange();
      E[pre + "_district"].value = last[pre + "_district"] || ""; E[pre + "_district"].onchange();
      const bv = last[pre + "_branch"] || ""; if (bv && ![...E[pre + "_branch"].options].some(o => o.value === bv)) E[pre + "_branch"].add(new Option(bv, bv)); E[pre + "_branch"].value = bv;
    }
    for (const [k, v] of Object.entries(last)) {
      const f = E.namedItem(k); if (!f || /_(region|district|branch)$/.test(k) || f.type === "button") continue;
      if (f.type === "checkbox") f.checked = !!v; else f.value = v;
    }
    sync(); toast("Oxirgi buyurtma ma'lumotlari ko'chirildi");
  };
}

const LEDGER = {topup: "To'ldirish", order: "Buyurtma uchun", refund: "Qaytarildi"};
async function accountModal(phone, name, after) {
  const d = await api("GET", "/customers/balance?phone=" + encodeURIComponent(phone));
  openModal(`<h2>Shaxsiy hisob</h2><p><b>${esc(d.name || name || "Yangi mijoz")}</b> · ${esc(d.phone)}</p>
    <div class="stat" style="margin-bottom:16px"><b>${money(d.balance)}</b><span>Hisobdagi mablag'</span></div>
    <form id="tf" class="form-grid"><div><label>To'ldirish summasi (so'm)</label><input id="ta" type="number" min="1" step="any" required autofocus></div>
      ${d.exists ? "" : `<div><label>Mijoz ismi (yangi mijoz)</label><input id="tn" value="${esc(name || "")}" required></div>`}
      <div class="full acts"><button class="btn">To'ldirish</button><button type="button" class="btn sec" onclick="closeModal()">Yopish</button></div></form>
    <h3 style="margin-top:20px">So'nggi operatsiyalar</h3>
    ${d.ledger.length ? `<div class="tablewrap"><table><thead><tr><th>Vaqt</th><th>Turi</th><th>Summa</th><th>Buyurtma</th></tr></thead><tbody>${d.ledger.map(l => `<tr><td class="small">${esc(l.time)}</td><td>${LEDGER[l.type] || esc(l.type)}</td>
      <td style="color:${l.amount < 0 ? "var(--bad)" : "var(--ok)"};font-weight:600">${l.amount > 0 ? "+" : ""}${money(l.amount)}</td><td>${esc(l.order || "")}</td></tr>`).join("")}</tbody></table></div>` : `<div class="muted small">Operatsiyalar yo'q</div>`}`);
  $("#tf").onsubmit = guard(async e => {
    e.preventDefault();
    await api("POST", "/customers/topup", {phone: d.phone, amount: $("#ta").value, name: $("#tn") ? $("#tn").value : ""});
    toast("Hisob to'ldirildi"); if (after) after(); accountModal(phone, name, after);
  });
}

async function operatorAssign(el, rid) {
  el.innerHTML = pageHead("Kuryerga berish", "truck") + `<div class="card" id="tab"></div>`;
  const tab = $("#tab");
  const load = guard(async () => {
    const [r, cs] = await Promise.all([api("GET", "/orders?courier_id=none&per=200"), api("GET", "/couriers")]);
    if (rid !== renderId) return;
    const list = r.items.filter(o => !["Yetkazildi", "Bekor qilindi"].includes(o.status));
    if (!list.length) { tab.innerHTML = `<div class="empty">Kuryersiz buyurtma yo'q 🎉</div>`; return; }
    if (!cs.length) { tab.innerHTML = `<div class="empty">Faol kuryerlar yo'q. Avval admin kuryer qo'shsin.</div>`; return; }
    tab.innerHTML = `<div class="bar"><div><label>Kuryer</label><select id="ac">${cs.map(c => `<option value="${c.id}">${esc(c.name)} (${c.open} ta faol)</option>`).join("")}</select></div>
      <button class="btn" id="ab">Tanlanganlarni biriktirish</button><button class="btn sec" id="aa">Hammasini tanlash</button><span class="muted small">Kuryersiz: ${list.length} ta</span></div>
      <div class="tablewrap"><table><thead><tr><th></th><th>Raqam</th><th>Qabul qiluvchi</th><th>Manzil</th><th>Mahsulot</th><th>Narx</th></tr></thead><tbody>
      ${list.map(o => `<tr><td><input type="checkbox" class="ck" value="${o.id}" style="width:18px;height:18px"></td><td><b>${esc(o.code)}</b><div class="muted small">${esc(o.created)}</div></td>
        <td>${esc(o.receiver_name)}<div class="muted small">${esc(o.receiver_phone)}</div></td><td>${esc(o.address)}</td><td>${esc(o.product)}<div class="muted small">${esc(o.weight)} kg</div></td><td>${money(o.price)}</td></tr>`).join("")}</tbody></table></div>`;
    $("#aa").onclick = () => { const all = $$(".ck", tab); const on = all.some(c => !c.checked); all.forEach(c => c.checked = on); };
    $("#ab").onclick = guard(async () => {
      const ids = $$(".ck:checked", tab).map(c => c.value);
      if (!ids.length) return toast("Buyurtmalarni tanlang", true);
      for (const id of ids) await api("POST", `/orders/${id}/assign`, {courier_id: $("#ac").value});
      toast(ids.length + " ta buyurtma kuryerga biriktirildi"); load();
    });
  });
  load();
}

function operatorTrack(el) {
  el.innerHTML = pageHead("Pochtani kuzatish", "search") + `<form class="card track" id="tf" style="max-width:none;margin-bottom:20px">
    <input id="tq" placeholder="Buyurtma raqami, telefon yoki ism" required autofocus autocomplete="off"><button class="btn">Qidirish</button></form><div id="tr"></div>`;
  let found = [];
  $("#tf").onsubmit = guard(async e => {
    e.preventDefault();
    let q = $("#tq").value.trim(); if (/^\d{1,6}$/.test(q)) q = "BTS-" + q.padStart(5, "0");
    found = (await api("GET", "/orders?per=10&q=" + encodeURIComponent(q))).items;
    $("#tr").innerHTML = found.length ? found.map((o, i) => `<div class="card"><h2>${esc(o.code)} ${badge(o.status)}</h2>${stepsHTML(o.status)}${detailsHTML(o)}
      <div class="acts"><button class="btn sm" data-print="${i}">🖨 Yo'lxat</button></div><h3 style="margin-top:18px">Tarix</h3>${historyHTML(o)}</div>`).join("")
      : `<div class="card empty">Hech narsa topilmadi</div>`;
  });
  on(el, "click", "[data-print]", b => printWaybill(found[+b.dataset.print]));
}

async function operatorStats(el, rid) {
  el.innerHTML = pageHead("Ko'rsatkichlarim", "chart") + `<div id="tab"></div>`;
  const s = await api("GET", "/mystats");
  if (rid !== renderId) return;
  const max = Math.max(1, ...s.days.map(d => d.count));
  $("#tab").innerHTML = `<div class="grid">
    <div class="stat"><b>${s.today}</b><span>Bugun qabul qilganim</span></div><div class="stat"><b>${s.week}</b><span>So'nggi 7 kun</span></div>
    <div class="stat"><b>${s.total}</b><span>Jami qabul qilganim</span></div><div class="stat"><b>${money(s.today_sum)}</b><span>Bugungi summa</span></div>
    ${STATUSES.map(st => `<div class="stat"><b>${s[st]}</b><span>${badge(st)}</span></div>`).join("")}</div>
    <div class="card"><h2>So'nggi 7 kun</h2><div class="chart">${s.days.map(d => `<div class="col"><b>${d.count}</b><i style="height:${Math.round(d.count / max * 100)}px"></i><span>${d.date.slice(5)}</span></div>`).join("")}</div></div>`;
}

/* ---------- Kuryer paneli ---------- */
async function viewCourier(el, sub) {
  const rid = renderId, hist = sub === "history";
  el.innerHTML = `<h1>Kuryer paneli</h1>${tabsHTML("courier", [["", "Bugungi marshrut"], ["history", "Tarix va daromad"]], sub)}<div id="cs" class="grid"></div><div id="cbody"></div>`;
  let st = null; try { st = await api("GET", "/courier/stats"); } catch {}
  if (rid !== renderId) return;
  const mx = st ? Math.max(1, ...st.days.map(d => d.count)) : 1;
  $("#cs").innerHTML = st ? (hist
    ? `<div class="stat"><b>${st.today}</b><span>Bugun yetkazildi</span></div><div class="stat"><b>${st.week}</b><span>7 kunda</span></div><div class="stat"><b>${st.month}</b><span>30 kunda</span></div>
       <div class="stat"><b>${st.rate}%</b><span>Muvaffaqiyat (bekor: ${st.cancelled})</span></div><div class="stat"><b>${st.avg_hours == null ? "—" : st.avg_hours + " soat"}</b><span>O'rtacha yetkazish vaqti</span></div>
       <div class="stat"><b>${money(st.earn_today)}</b><span>Bugungi haq (${money(st.fee)} × ${st.today})</span></div><div class="stat"><b>${money(st.earn_month)}</b><span>30 kunlik haq</span></div>`
    : `<div class="stat ${st.active ? "warn" : ""}"><b>${st.active}</b><span>Faol buyurtma</span></div><div class="stat"><b>${st.today}</b><span>Bugun yetkazildi</span></div>
       <div class="stat"><b>${money(st.sum_today)}</b><span>Bugungi summa</span></div><div class="stat"><b>${money(st.earn_today)}</b><span>Bugungi haq</span></div>`) : "";
  if (hist) {
    $("#cbody").innerHTML = `<div class="card"><h2>So'nggi 7 kun (yetkazilganlar)</h2><div class="chart">${st.days.map(d => `<div class="col"><b>${d.count}</b><i style="height:${Math.round(d.count / mx * 100)}px"></i><span>${d.date.slice(5)}</span></div>`).join("")}</div></div><div class="card" id="hl"></div>`;
    const all = (await api("GET", "/orders?per=200")).items.filter(o => ["Yetkazildi", "Bekor qilindi"].includes(o.status));
    $("#hl").innerHTML = `<h2>Yakunlangan buyurtmalar</h2><div class="tablewrap"><table><thead><tr><th>Raqam</th><th>Qabul qiluvchi</th><th>Manzil</th><th>Summa</th><th>Holat</th></tr></thead><tbody>
      ${all.map(o => `<tr><td><a href="#/t/${esc(o.code)}">${esc(o.code)}</a></td><td>${esc(o.receiver_name)}</td><td>${esc(o.address)}</td><td>${money(o.price)}</td><td>${badge(o.status)}</td></tr>`).join("") || `<tr><td colspan="5" class="empty">Yo'q</td></tr>`}</tbody></table></div>`;
    return;
  }
  $("#cbody").innerHTML = `<div class="bar"><div><label>Qidirish</label><input id="cq" placeholder="Ism, telefon, manzil, raqam"></div><div><label>Ko'rsatish</label><select id="cf"><option value="active">Faol (qabul qilingan va yo'lda)</option><option value="">Barchasi</option>${STATUSES.map(s => `<option>${s}</option>`).join("")}</select></div></div>
    <div id="cprog"></div><div id="clist"></div>`;
  let all = [];
  const draw = () => {
    const f = $("#cf").value, q = $("#cq").value.toLowerCase();
    const open = all.filter(o => !["Yetkazildi", "Bekor qilindi"].includes(o.status));
    const today = new Date().toISOString().slice(0, 10);
    const doneT = all.filter(o => o.status === "Yetkazildi" && o.history.some(h => h.status === "Yetkazildi" && h.time.startsWith(today))).length;
    const pct = doneT + open.length ? Math.round(100 * doneT / (doneT + open.length)) : 0;
    $("#cprog").innerHTML = `<div class="card"><div class="small muted">Bugungi reja: ${doneT} / ${doneT + open.length} yetkazildi</div><div class="bar-bg" style="width:100%;height:12px;margin-top:6px"><div class="bar-fg" style="width:${pct}%;height:12px"></div></div></div>`;
    let list = f === "active" ? open.slice().reverse() : f ? all.filter(o => o.status === f) : all;
    if (q) list = list.filter(o => [o.code, o.receiver_name, o.receiver_phone, o.address, o.product].join(" ").toLowerCase().includes(q));
    const card = o => `<div class="corder">
      <div class="row"><b>${esc(o.code)}</b>${badge(o.status)}</div>
      <div class="big">${esc(o.receiver_name)}</div>
      <div><a class="btn sec sm" href="tel:${esc(o.receiver_phone)}">📞 ${esc(o.receiver_phone)}</a> <a class="btn sec sm" href="${mapLink(o.address)}" target="_blank" rel="noopener">📍 Xaritada</a>
        ${o.receiver_phone2 ? `<a class="btn sec sm" href="tel:${esc(o.receiver_phone2)}">📞 ${esc(o.receiver_phone2)}</a>` : ""}</div>
      <div style="margin-top:6px">${esc(o.address)}</div>
      <div class="muted small" style="margin-top:4px">${esc(o.product)} · ${esc(o.weight)} kg · ${money(o.price)} (to'lovchi: ${esc(o.payer || "Yuboruvchi")}) · Yuboruvchi: ${esc(o.sender_name)}, ${esc(o.sender_phone)}</div>
      ${o.shelf ? `<div class="small" style="margin-top:4px">🗄 Shkaf: <b>${esc(o.shelf)}</b></div>` : ""}
      ${o.note ? `<div class="small" style="margin-top:4px">📝 ${esc(o.note)}</div>` : ""}
      ${o.cancel_reason ? `<div class="small" style="color:var(--bad)">Bekor sababi: ${esc(o.cancel_reason)}</div>` : ""}
      ${["Yetkazildi", "Bekor qilindi"].includes(o.status) ? "" : `<div class="acts" style="margin-top:12px">
        ${o.status === "Qabul qilindi" ? `<button class="btn lg" data-id="${o.id}" data-st="Yo'lda">Yo'lga chiqdim</button>` : ""}
        <button class="btn ok lg" data-id="${o.id}" data-st="Yetkazildi">Yetkazildi</button>
        <button class="btn sec lg" data-id="${o.id}" data-code="1">Kod bilan topshirish</button>
        <button class="btn danger lg" data-id="${o.id}" data-st="Bekor qilindi">Bekor qilish</button></div>`}
      <div class="acts" style="margin-top:8px"><label class="btn sec">${ico("clip")} Isbot rasmi${(o.files || []).length ? " (" + o.files.length + ")" : ""}<input type="file" accept="image/jpeg,image/png,image/webp" data-proof="${o.id}" hidden></label></div></div>`;
    if (!list.length) { $("#clist").innerHTML = `<div class="card empty">${f === "active" ? "Hozircha faol buyurtma yo'q 🎉" : "Buyurtmalar yo'q"}</div>`; return; }
    // Faol buyurtmalar hudud bo'yicha guruhlanadi (marshrutni rejalashtirish oson bo'ladi)
    const groups = {};
    list.forEach(o => (groups[o.receiver_district || o.receiver_region || "Boshqa"] ||= []).push(o));
    $("#clist").innerHTML = Object.entries(groups).map(([g, os]) => `<h3 class="sec">${esc(g)} · ${os.length}</h3>${os.map(card).join("")}`).join("");
  };
  const load = async () => {
    try { all = (await api("GET", "/orders?per=200")).items; } catch (e) { return toast(e.message, true); }
    if (rid !== renderId) return;
    draw();
  };
  on(el, "click", "button[data-st]", guard(async b => {
    const st = b.dataset.st; let reason;
    if (st === "Bekor qilindi") { reason = await askReason("Bekor qilish sababi"); if (!reason) return; }
    else if (st === "Yetkazildi" && !await confirmBox("Buyurtma yetkazildimi?", "Ha, yetkazildi")) return;
    await api("POST", `/orders/${b.dataset.id}/status`, {status: st, reason}); toast("Holat yangilandi"); render();
  }));
  on(el, "click", "button[data-code]", b => {
    openModal(`<h2>Kod bilan topshirish</h2><p class="muted">Qabul qiluvchi 4 xonali kodni aytadi (u kodni o'z kabinetida ko'radi).</p><form id="pcF"><input name="code" inputmode="numeric" maxlength="4" required autofocus style="font-size:24px;letter-spacing:8px;text-align:center"><div class="acts" style="margin-top:14px"><button class="btn">Topshirish</button><button type="button" class="btn sec" onclick="closeModal()">Bekor</button></div></form>`, true);
    $("#pcF").onsubmit = guard(async e => { e.preventDefault(); await api("POST", `/orders/${b.dataset.id}/handover`, readForm(e.target)); closeModal(); toast("Topshirildi"); render(); });
  });
  on(el, "change", "input[data-proof]", guard(async inp => {
    if (!inp.files[0]) return;
    toast("Yuklanmoqda…"); await uploadFile(inp.dataset.proof, inp.files[0], "proof"); toast("Isbot rasmi yuklandi"); load();
  }));
  $("#cf").onchange = draw; $("#cq").oninput = draw; await load();
}

async function adminHome(el, rid) {
  let st = null; try { st = await api("GET", "/stats"); } catch {}
  if (rid !== renderId) return;
  const T = (h, t, i, c, n, tip) => `<a class="tile ${c || ""}" href="#/${h}">${n ? `<span class="cnt" title="${tip || ""}">${n}</span>` : ""}${ico(i)}<span>${t}</span></a>`;
  const groups = [
    ["Boshqaruv", [["admin/overview", "Statistika", "chart"], ["admin/orders", "Buyurtmalar", "list", "primary", st && st.unassigned, "Kuryersiz buyurtmalar"], ["admin/users", "Foydalanuvchilar", "shield"],
      ["admin/customers", "Mijozlar", "users"], ["admin/kpi", "KPI", "chart"], ["admin/cash", "Inkassatsiya", "tag"], ["admin/complaints", "Shikoyatlar", "clip", "", st && st.open_complaints, "Hal qilinmagan"]]],
    ["Sozlamalar", [["admin/tariff", "Tariflar", "tag"], ["admin/dict", "Ma'lumotnomalar", "book"], ["admin/cloud", "Bulut holati", "cloud"], ["admin/audit", "Audit log", "clip"], ["admin/security", "Qora ro'yxat va zaxira", "shield"]]],
    ["Tezkor amallar", [["operator/new", "Pochta qabul qilish", "plus"], ["operator", "Operator paneli", "mail"], ["operator/warehouse", "Ombor", "file", "", st && st.unplaced, "Shkafga joylanmagan"], ["operator/moves", "Pochta harakati", "list"]]],
  ];
  const late = st && st.overdue_count ? `<div class="alert">⚠ ${st.overdue_count} ta buyurtma 3 kundan ortiq yetkazilmagan — <a href="#/admin/overview">ko'rish</a></div>` : "";
  el.innerHTML = `<div class="homebar"><a class="btn blue" href="#/admin/overview">Statistika</a></div>${late}
    ${groups.map(([h, ts]) => `<h3 class="sec">${h}</h3><div class="tiles">${ts.map(t => T(...t)).join("")}</div>`).join("")}
    <div class="tiles" style="margin-top:22px"><a class="tile exit" href="#" data-logout>${ico("logout")}<span>Chiqish</span></a></div>`;
}
function packagingFrom(lines) {
  const m = new Map();
  lines.forEach(ln => { const [t, z, p] = ln.split("|").map(x => x.trim()); if (!t || !z) throw new Error("Qadoq qatori noto'g'ri: " + ln); if (!m.has(t)) m.set(t, []); m.get(t).push({size: z, price: +p || 0}); });
  return [...m].map(([type, sizes]) => ({type, sizes}));
}
async function adminDict(tab) {
  const d = await api("GET", "/dict"), org = d.org || {};
  const lines = a => a.join("\n");
  tab.innerHTML = `<form class="card" id="df"><h2>Ma'lumotnomalar</h2>
    <p class="muted">Operator formasidagi tanlov ro'yxatlari. Har bir qatorga bitta qiymat yozing. Ro'yxatlar namuna — o'zingiznikiga moslab to'ldiring.</p>
    <div class="dictgrid">
      <div style="grid-column:1/-1"><label>Hududlar (format: <code>Viloyat: tuman1, tuman2, ...</code>)</label><textarea id="d_regions" rows="10">${esc(Object.entries(d.regions).map(([k, v]) => k + ": " + v.join(", ")).join("\n"))}</textarea></div>
      <div style="grid-column:1/-1"><label>Filiallar (format: <code>kod - nom | viloyat | tuman | manzil</code>; tuman va manzil ixtiyoriy)</label><textarea id="d_branches" rows="6">${esc(d.branches.map(b => b.code + " - " + b.name + (b.region ? " | " + b.region : "") + " | " + (b.district || "") + " | " + (b.address || "")).join("\n"))}</textarea></div>
      <div><label>Ichkarida (jo'natma turi)</label><textarea id="d_contents">${esc(lines(d.contents))}</textarea></div>
      <div><label>Paket</label><textarea id="d_packages">${esc(lines(d.packages))}</textarea></div>
      <div><label>To'lov turlari</label><textarea id="d_payment_types">${esc(lines(d.payment_types))}</textarea></div>
      <div><label>Transport turlari</label><textarea id="d_transports">${esc(lines(d.transports))}</textarea></div>
      <div style="grid-column:1/-1"><label>Qadoqlash materiallari narxi (format: <code>tur | hajm | narx</code>; narx 0 = hali belgilanmagan)</label><textarea id="d_packaging" rows="8">${esc((d.packaging || []).flatMap(p => p.sizes.map(z => p.type + " | " + z.size + " | " + z.price)).join("\n"))}</textarea></div>
    </div>
    <h3 style="margin-top:20px">Tashkilot (elektron chekda ko'rinadi)</h3>
    <div class="form-grid"><div><label>Nomi</label><input id="o_name" value="${esc(org.name)}"></div><div><label>INN</label><input id="o_inn" value="${esc(org.inn)}"></div>
      <div><label>Manzil</label><input id="o_address" value="${esc(org.address)}"></div><div><label>Sayt</label><input id="o_site" value="${esc(org.site)}"></div></div>
    <div style="margin-top:16px"><button class="btn">Saqlash</button></div></form>`;
  const list = id => $("#" + id).value.split("\n").map(x => x.trim()).filter(Boolean);
  $("#df").onsubmit = guard(async e => {
    e.preventDefault();
    const regions = {};
    for (const ln of list("d_regions")) { const i = ln.indexOf(":"); if (i < 1) throw new Error("Hudud qatori noto'g'ri: " + ln); regions[ln.slice(0, i).trim()] = ln.slice(i + 1).split(",").map(x => x.trim()).filter(Boolean); }
    const branches = list("d_branches").map(ln => { const [l, r = "", t = "", ad = ""] = ln.split("|"); const i = l.indexOf(" - "); if (i < 1) throw new Error("Filial qatori noto'g'ri: " + ln); return {code: l.slice(0, i).trim(), name: l.slice(i + 3).trim(), region: r.trim(), district: t.trim(), address: ad.trim()}; });
    await api("PUT", "/dict", {regions, branches, contents: list("d_contents"), packages: list("d_packages"), payment_types: list("d_payment_types"), transports: list("d_transports"), packaging: packagingFrom(list("d_packaging")),
      org: {name: $("#o_name").value, inn: $("#o_inn").value, address: $("#o_address").value, site: $("#o_site").value}});
    toast("Ma'lumotnomalar saqlandi");
  });
}

async function adminTariff(tab) {
  const t = await api("GET", "/tariff"); tariff = t;
  tab.innerHTML = `<form class="card" id="trf" style="max-width:640px"><h2>Yetkazib berish tarifi</h2>
    <p class="muted">Narx = boshlang'ich narx + (hisoblanadigan og'irlik − bepul og'irlik) × har kg narxi (yuqoriga yaxlitlanadi) + eshikkacha yetkazib berish + qo'shimcha xizmat, ustiga QQS. Hisoblanadigan og'irlik — haqiqiy og'irlik va hajm og'irligi (uzunlik×kenglik×balandlik ÷ bo'luvchi) ning kattasi. Operator formasida summa shu qoidada avtomatik chiqadi.</p>
    <div class="form-grid">
      <div><label>Boshlang'ich narx (so'm)</label><input name="base" type="number" min="0" step="any" value="${t.base}" required></div>
      <div><label>Boshlang'ich narxga kiruvchi og'irlik (kg)</label><input name="free_kg" type="number" min="0" step="any" value="${t.free_kg}" required></div>
      <div><label>Har qo'shimcha kg uchun (so'm)</label><input name="per_kg" type="number" min="0" step="any" value="${t.per_kg}" required></div>
      <div><label>Yaxlitlash (so'm)</label><input name="round_to" type="number" min="1" step="any" value="${t.round_to}" required></div>
      <div><label>Eshikkacha yetkazib berish (so'm)</label><input name="door_fee" type="number" min="0" step="any" value="${t.door_fee}" required></div>
      <div><label>QQS (%)</label><input name="vat" type="number" min="0" max="100" step="any" value="${t.vat}" required></div>
      <div><label>Hajm bo'luvchisi (sm³ → kg)</label><input name="vol_divisor" type="number" min="1" step="any" value="${t.vol_divisor}" required></div>
      <div><label>Kuryerga haq (har yetkazilgan buyurtma uchun, so'm)</label><input name="courier_fee" type="number" min="0" step="any" value="${t.courier_fee ?? 0}"></div></div>
    <div id="ex" class="hint"></div><div style="margin-top:16px"><button class="btn">Saqlash</button></div></form>`;
  const form = $("#trf");
  const show = () => {
    const d = Object.fromEntries(new FormData(form).entries()); const old = tariff;
    tariff = {base: +d.base, per_kg: +d.per_kg, free_kg: +d.free_kg, round_to: Math.max(1, +d.round_to)};
    $("#ex").innerHTML = "Namuna: " + [1, 2, 5, 10, 20].map(w => `<b>${w} kg</b> → ${money(calcPrice(w))}`).join(" · "); tariff = old;
  };
  form.addEventListener("input", () => { const old = tariff; show(); tariff = old; }); show();
  form.onsubmit = guard(async e => { e.preventDefault(); tariff = await api("PUT", "/tariff", readForm(form)); toast("Tarif saqlandi"); show(); });
}


async function adminCloud(tab) {
  const rid = renderId;
  const draw = async () => {
    const c = await api("GET", "/cloud/status");
    if (rid !== renderId) return;
    const ec2 = c.ec2 || {}, db = c.database || {}, ob = c.objects || {}, mo = c.monitoring || {}, ap = c.app || {};
    const st = ok => `<span class="badge ${ok ? "s2" : "s3"}">${ok ? "ishlayapti" : "xato"}</span>`;
    const up = s => s > 3600 ? Math.floor(s / 3600) + " soat " + Math.floor(s % 3600 / 60) + " daq" : Math.floor(s / 60) + " daq " + (s % 60) + " s";
    tab.innerHTML = `<div class="grid cloudgrid">
      <div class="card"><h3>Hisoblash (EC2)</h3><dl class="kv"><dt>Instance</dt><dd>${esc(ec2.instance_id || "— (EC2 emas / lokal)")}</dd><dt>Turi</dt><dd>${esc(ec2.instance_type || "—")}</dd>
        <dt>Zona</dt><dd>${esc(ec2.zone || "—")}</dd><dt>Public IP</dt><dd>${esc(ec2.public_ip || "—")}</dd><dt>Host</dt><dd>${esc(ap.host)}</dd><dt>OT</dt><dd>${esc(ap.os)}</dd>
        <dt>Python</dt><dd>${esc(ap.python)}</dd><dt>Ilova</dt><dd>v${esc(ap.version)} · ishlash vaqti ${up(ap.uptime_s)}</dd></dl></div>
      <div class="card"><h3>Ma'lumotlar bazasi ${st(db.ok)}</h3><dl class="kv"><dt>Turi</dt><dd>${esc(db.kind)}</dd><dt>Manzil</dt><dd>${esc(db.target || db.path || "—")}</dd>
        <dt>Versiya</dt><dd>${esc(db.version || "—")}</dd>${db.rows ? `<dt>Qatorlar</dt><dd>buyurtmalar: ${db.rows.orders} · mijozlar: ${db.rows.customers} · foydalanuvchilar: ${db.rows.users}</dd>` : ""}
        ${db.error ? `<dt>Xato</dt><dd>${esc(db.error)}</dd>` : ""}</dl></div>
      <div class="card"><h3>Obyektli saqlash</h3><dl class="kv"><dt>Turi</dt><dd>${ob.kind === "s3" ? "Amazon S3" : "Lokal papka (S3 sozlanmagan)"}</dd><dt>Manzil</dt><dd>${esc(ob.target)}</dd><dt>Region</dt><dd>${esc(ob.region || "—")}</dd>
        <dt>Shifrlash</dt><dd>${ob.kind === "s3" ? "SSE-S3 (AES-256), havolalar 5 daqiqalik" : "—"}</dd></dl></div>
      <div class="card"><h3>Monitoring (CloudWatch)</h3><dl class="kv"><dt>Namespace</dt><dd>${esc(mo.namespace || "sozlanmagan")}</dd>
        <dt>So'rovlar</dt><dd>${mo.counters.Requests} · 5xx xato: ${mo.counters.Errors5xx}</dd><dt>Buyurtmalar</dt><dd>${mo.counters.OrdersCreated} · fayllar: ${mo.counters.FilesUploaded} · kirish xatolari: ${mo.counters.LoginFailed}</dd>
        <dt>Oxirgi yuborish</dt><dd>${esc(mo.last_push || "—")}</dd>${mo.last_error ? `<dt>Xato</dt><dd>${esc(mo.last_error)}</dd>` : ""}</dl></div></div>
      <div class="card"><div class="bar"><h3 class="grow" style="margin:0">Bulut ulanishini tekshirish</h3><button class="btn" id="st">Tekshirishni boshlash</button></div>
        <div id="str" class="muted small">Ma'lumotlar bazasiga yozish-o'qish, obyektli saqlashga fayl yuklash-olish-o'chirish va CloudWatch'ga metrika yuborish sinab ko'riladi. Natijani hisobot uchun skrinshot qilishingiz mumkin.</div></div>
      <div class="card"><div class="bar"><h3 class="grow" style="margin:0">Hisobotlar eksporti (CSV)</h3><button class="btn" id="ex">Buyurtmalarni saqlashga eksport qilish</button></div><div id="exl"></div></div>`;
    $("#st").onclick = guard(async () => {
      $("#str").textContent = "Tekshirilmoqda…";
      const r = await api("POST", "/cloud/selftest");
      $("#str").innerHTML = `<table class="tbl"><tbody>${r.checks.map(x => `<tr><td>${x.ok === null ? "➖" : x.ok ? "✅" : "❌"}</td><td>${esc(x.name)}</td><td class="muted small">${esc(x.detail)}</td></tr>`).join("")}</tbody></table><div class="muted small" style="margin-top:6px">${esc(r.time)}</div>`;
    });
    const exlist = async () => {
      const r = await api("GET", "/exports");
      $("#exl").innerHTML = r.items.length ? `<table class="tbl"><thead><tr><th>Fayl</th><th>Hajm</th><th>Sana</th></tr></thead><tbody>${r.items.map(i => `<tr><td><a href="${esc(i.url)}">${esc(i.key)}</a></td><td>${fmtSize(i.size)}</td><td>${esc(i.modified)}</td></tr>`).join("")}</tbody></table>
        <div class="muted small" style="margin-top:6px">Saqlangan joy: ${esc(r.target)}</div>` : `<div class="muted small">Hali eksport qilinmagan</div>`;
    };
    $("#ex").onclick = guard(async () => { await api("POST", "/exports"); toast("Eksport saqlandi"); exlist(); });
    exlist();
  };
  await draw();
}
async function viewAdmin(el, sub) {
  const rid = renderId;
  if (!sub) return adminHome(el, rid);
  const T = {overview: ["Statistika", "chart"], orders: ["Buyurtmalar", "list"], users: ["Foydalanuvchilar", "shield"], customers: ["Mijozlar", "users"], tariff: ["Tariflar", "tag"], dict: ["Ma'lumotnomalar", "book"], cloud: ["Bulut holati", "cloud"], audit: ["Audit log", "clip"], security: ["Qora ro'yxat va zaxira", "shield"], kpi: ["KPI", "chart"], complaints: ["Shikoyatlar", "clip"], cash: ["Inkassatsiya", "tag"]};
  const [title, icon] = T[sub] || T.overview;
  el.innerHTML = pageHead(title, icon) + `<div id="tab"></div>`;
  const tab = $("#tab");
  if (sub === "orders") {
    tab.innerHTML = `<div class="bar"><button class="btn" id="nb">+ Yangi buyurtma</button></div><div class="card" id="op"></div>`;
    ordersPanel($("#op"), {admin: true});
    $("#nb").onclick = () => { location.hash = "#/operator/new"; };
    return;
  }
  if (sub === "users") return adminUsers(tab);
  if (sub === "customers") return customersPanel(tab);
  if (sub === "tariff") return adminTariff(tab);
  if (sub === "dict") return adminDict(tab);
  if (sub === "cloud") return adminCloud(tab);
  if (sub === "audit") return adminAudit(tab);
  if (sub === "security") return securityPanel(tab);
  if (sub === "kpi") return kpiPanel(tab);
  if (sub === "complaints") return complaintsPanel(tab);
  if (sub === "cash") return cashPanel(tab);
  const s = await api("GET", "/stats");
  if (rid !== renderId) return;
  const bars = (arr, key = "count", fmt = x => x) => { const m = Math.max(1, ...arr.map(a => a[key])); return arr.map(a => `<div class="hb"><span class="hl">${esc(a.name)}</span><div class="hbar"><i style="width:${Math.round(a[key] / m * 100)}%"></i></div><b>${fmt(a[key])}</b></div>`).join("") || `<div class="empty">Ma'lumot yo'q</div>`; };
  const tmax = Math.max(1, ...s.trend.map(d => d.count));
  tab.innerHTML = `${s.overdue_count ? `<div class="alert">⚠ ${s.overdue_count} ta buyurtma 3 kundan ortiq yetkazilmagan</div>` : ""}
    <div class="grid">
      <div class="stat"><b>${s.total}</b><span>Jami buyurtmalar</span></div>
      <div class="stat"><b>${s.delivery_rate}%</b><span>Yetkazib berilgan ulush</span></div>
      <div class="stat"><b>${s.avg_hours == null ? "—" : s.avg_hours + " soat"}</b><span>O'rtacha yetkazish vaqti</span></div>
      ${STATUSES.map(st => `<div class="stat"><b>${s[st]}</b><span>${badge(st)}</span></div>`).join("")}
      <div class="stat ${s.unassigned ? "warn" : ""}"><b>${s.unassigned}</b><span>Kuryersiz faol buyurtma</span></div>
      <div class="stat ${s.open_complaints ? "warn" : ""}"><b>${s.open_complaints}</b><span>Hal qilinmagan shikoyat</span></div>
      <div class="stat"><b>${money(s.revenue)}</b><span>Yetkazilganlardan tushum</span></div>
      <div class="stat"><b>${money(s.pending_revenue)}</b><span>Kutilayotgan tushum</span></div>
      <div class="stat"><b>${s.customers}</b><span>Mijozlar</span></div>
      <div class="stat"><b>${s.online}</b><span>Onlayn buyurtmalar</span></div></div>
    <div class="grid wide">
      <div class="card"><h2>So'nggi 14 kun (yangi buyurtmalar)</h2><div class="chart">${s.trend.map(d => `<div class="col" title="${money(d.revenue)}"><b>${d.count}</b><i style="height:${Math.round(d.count / tmax * 100)}px"></i><span>${d.date.slice(5)}</span></div>`).join("")}</div></div>
      <div class="card"><h2>Tushum (14 kun)</h2>${bars(s.trend.map(d => ({name: d.date.slice(5), count: d.revenue})).filter(d => d.count), "count", money)}</div></div>
    <div class="grid wide">
      <div class="card"><h2>Qabul qiluvchi viloyatlar</h2>${bars(s.by_region)}</div>
      <div class="card"><h2>To'lov turlari</h2>${bars(s.by_payment)}</div>
      <div class="card"><h2>Eng faol mijozlar</h2>${bars(s.top_customers)}</div></div>
    <div class="grid wide">
      <div class="card"><h2>Kuryerlar</h2>${s.couriers.length ? `<div class="tablewrap"><table><thead><tr><th>Kuryer</th><th>Faol</th><th>Yetkazgan</th><th>Samaradorlik</th></tr></thead><tbody>
        ${s.couriers.map(c => `<tr><td>${esc(c.name)}</td><td>${c.open}</td><td>${c.delivered}</td><td><div class="bar-bg"><div class="bar-fg" style="width:${c.rate}%"></div></div> ${c.rate}%</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty">Kuryerlar yo'q</div>`}</div>
      <div class="card"><h2>Kechikkan buyurtmalar</h2>${s.overdue.length ? `<div class="tablewrap"><table><thead><tr><th>Raqam</th><th>Qabul qiluvchi</th><th>Holat</th><th>Kuryer</th></tr></thead><tbody>
        ${s.overdue.map(o => `<tr><td><a href="#/t/${esc(o.code)}">${esc(o.code)}</a><div class="muted small">${esc(o.created)}</div></td><td>${esc(o.receiver)}</td><td>${badge(o.status)}</td><td>${esc(o.courier)}</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty">Kechikkan buyurtma yo'q 🎉</div>`}</div></div>
    <div class="card"><h2>Foydalanuvchilar</h2><div class="chips">${Object.entries(s.users_by_role).map(([r, n]) => `<span class="chip">${ROLE_NAME[r]}: ${n}</span>`).join("")}</div></div>`;
}

async function adminUsers(tab) {
  const BR = (await api("GET", "/dict")).branches;
  tab.innerHTML = `<div class="card"><h2>Foydalanuvchilar</h2><div id="ul"></div></div>
    <div class="card"><h2>Yangi foydalanuvchi</h2><form id="uf" class="form-grid">
      <div><label>Ism</label><input name="name" required maxlength="80"></div><div><label>Telefon</label><input name="phone" type="tel" placeholder="+998..."></div>
      <div><label>Rol</label><select name="role"><option value="courier">Kuryer</option><option value="operator">Operator</option><option value="admin">Admin</option></select></div>
      <div><label>Ofis (smena joyi)</label><select name="branch"><option value="">—</option>${BR.map(b => `<option value="${esc(b.code)}">${esc(b.code + " - " + b.name)}</option>`).join("")}</select></div>
      <div><label>Login</label><input name="username" required minlength="3" autocomplete="off"></div>
      <div><label>Parol (kamida 6 belgi)</label><input name="password" type="password" minlength="6" required autocomplete="new-password"></div>
      <div style="align-self:end"><button class="btn">Qo'shish</button></div></form></div>`;
  let users = [];
  const load = guard(async () => {
    users = await api("GET", "/users");
    if (!$("#ul")) return;
    $("#ul").innerHTML = `<div class="tablewrap"><table><thead><tr><th>Ism</th><th>Rol</th><th>Login</th><th>Telefon</th><th>Ofis</th><th>Holat</th><th></th></tr></thead><tbody>
      ${users.map(u => `<tr class="${u.active ? "" : "inactive"}"><td>${esc(u.name)}</td><td>${ROLE_NAME[u.role]}</td><td>${esc(u.username)}</td><td>${esc(u.phone || "—")}</td><td>${esc(u.office ? u.office.name : "—")}</td>
      <td>${u.active ? "Faol" : "O'chirilgan"}</td><td><div class="acts">
        <button class="btn sec sm" data-a="pw" data-id="${u.id}">Parol</button>
        ${u.id === me.id ? "" : `<button class="btn sec sm" data-a="toggle" data-id="${u.id}">${u.active ? "O'chirib qo'yish" : "Yoqish"}</button><button class="btn danger sm" data-a="del" data-id="${u.id}">O'chirish</button>`}
      </div></td></tr>`).join("")}</tbody></table></div>`;
  });
  on(tab, "click", "[data-a]", guard(async b => {
    const u = users.find(x => x.id === +b.dataset.id), a = b.dataset.a;
    if (a === "toggle") { await api("PUT", "/users/" + u.id, {active: !u.active}); toast("Yangilandi"); load(); }
    else if (a === "del") { if (await confirmBox(`${u.name} o'chirilsinmi?`, "O'chirish")) { await api("DELETE", "/users/" + u.id); toast("O'chirildi"); load(); } }
    else if (a === "pw") {
      openModal(`<h2>${esc(u.name)}: yangi parol</h2><form id="npf"><input type="password" id="np" minlength="6" required placeholder="Kamida 6 belgi"><div class="acts" style="margin-top:14px"><button class="btn">Saqlash</button><button type="button" class="btn sec" onclick="closeModal()">Bekor</button></div></form>`, true);
      $("#npf").onsubmit = guard(async e => { e.preventDefault(); await api("PUT", "/users/" + u.id, {password: $("#np").value}); closeModal(); toast("Parol yangilandi"); });
    }
  }));
  $("#uf").onsubmit = guard(async e => { e.preventDefault(); await api("POST", "/users", readForm(e.target)); e.target.reset(); toast("Foydalanuvchi qo'shildi"); load(); });
  load();
}

async function cashPanel(tab) {
  const c = await api("GET", "/collection");
  tab.innerHTML = `<div class="grid"><div class="stat"><b>${money(c.expected)}</b><span>Kutilayotgan naqd pul (${c.orders} ta yetkazilgan buyurtma)</span></div></div>
    <div class="card"><form id="cashF" class="form-grid"><div><label>Topshirilayotgan summa (so'm)</label><input name="amount" type="number" min="0" step="1" value="${c.expected}" required></div>
    <div><label>Izoh (ixtiyoriy)</label><input name="note" maxlength="300"></div>
    <div class="full acts"><button class="btn">Kassaga topshirish</button></div></form></div>
    <div class="card"><h3>Topshirishlar tarixi</h3><div class="tablewrap"><table><thead><tr><th>Vaqt</th><th>Xodim</th><th>Ofis</th><th>Buyurtma</th><th>Kutilgan</th><th>Topshirildi</th><th>Farq</th><th>Izoh</th></tr></thead><tbody>
    ${c.history.map(h => `<tr><td>${esc(h.time)}</td><td>${esc(h.user)}</td><td>${esc(h.branch || "—")}</td><td>${h.orders}</td><td>${money(h.expected)}</td><td>${money(h.amount)}</td><td style="color:${h.diff ? "#c0392b" : "inherit"}">${h.diff ? money(h.diff) : "—"}</td><td>${esc(h.note || "")}</td></tr>`).join("") || `<tr><td colspan="8" class="empty">Hali topshirilmagan</td></tr>`}</tbody></table></div></div>`;
  $("#cashF").onsubmit = guard(async e => { e.preventDefault(); await api("POST", "/collection", readForm(e.target)); toast("Inkassatsiya yozildi"); cashPanel(tab); });
}

async function kpiPanel(tab) {
  const draw = async () => {
    const f = readForm($("#kf"));
    const rows = await api("GET", `/kpi?from=${f.from || ""}&to=${f.to || ""}`);
    $("#kb").innerHTML = `<div class="card"><div class="tablewrap"><table><thead><tr><th>Xodim</th><th>Rol</th><th>Qabul qilgan</th><th>Summa</th><th>Yetkazgan</th><th>Qaytgan/bekor</th><th>O'rtacha vaqt</th></tr></thead><tbody>
      ${rows.map(r => `<tr><td>${esc(r.name)}</td><td>${ROLE_NAME[r.role]}</td><td>${r.created}</td><td>${money(r.created_sum)}</td><td>${r.delivered}</td><td>${r.returned}</td><td>${r.avg_hours == null ? "—" : r.avg_hours + " soat"}</td></tr>`).join("") || `<tr><td colspan="7" class="empty">Ma'lumot yo'q</td></tr>`}</tbody></table></div></div>`;
  };
  tab.innerHTML = `<div class="card"><form id="kf" class="form-grid"><div><label>Dan</label><input type="date" name="from"></div><div><label>Gacha</label><input type="date" name="to"></div>
    <div style="align-self:end"><button class="btn">Ko'rsatish</button></div></form></div><div id="kb"></div>`;
  $("#kf").onsubmit = guard(e => { e.preventDefault(); return draw(); });
  await draw();
}

async function complaintsPanel(tab) {
  const cust = me.role === "customer";
  const r = await api("GET", "/complaints");
  const list = cust ? r : r.items;
  tab.innerHTML = `${cust ? "" : `<div class="grid">${["Yangi", "Ko'rilmoqda", "Hal qilindi"].map(k => `<div class="stat"><b>${r.stats[k] || 0}</b><span>${k}</span></div>`).join("")}</div>`}
    <div class="card"><h3>Yangi shikoyat</h3><form id="cmF" class="form-grid">
    <div><label>Buyurtma raqami (ixtiyoriy)</label><input name="order" placeholder="BTS-00001"></div>
    <div class="full"><label>Matn</label><textarea name="text" rows="3" maxlength="200" required minlength="5"></textarea></div>
    <div class="full acts"><button class="btn">Yuborish</button></div></form></div>
    <div class="card"><h3>Shikoyatlar</h3><div class="tablewrap"><table><thead><tr><th>#</th><th>Vaqt</th>${cust ? "" : "<th>Kim</th>"}<th>Buyurtma</th><th>Matn</th><th>Holat</th><th>${cust ? "Javob" : ""}</th></tr></thead><tbody>
    ${list.map(c => `<tr><td>${c.id}</td><td>${esc(c.time)}</td>${cust ? "" : `<td>${esc(c.user)}<div class="muted small">${esc(c.phone || "")}</div></td>`}<td>${esc(c.order || "—")}</td><td>${esc(c.text)}</td><td>${esc(c.status)}</td>
      <td>${cust ? esc(c.answer || "") : `<button class="btn sec sm" data-cm="${c.id}">Javob / holat</button>`}</td></tr>`).join("") || `<tr><td colspan="7" class="empty">Shikoyat yo'q</td></tr>`}</tbody></table></div></div>`;
  $("#cmF").onsubmit = guard(async e => { e.preventDefault(); await api("POST", "/complaints", readForm(e.target)); toast("Shikoyat yuborildi"); complaintsPanel(tab); });
  on(tab, "click", "[data-cm]", b => {
    const c = list.find(x => x.id === +b.dataset.cm);
    openModal(`<h2>Shikoyat #${c.id}</h2><p>${esc(c.text)}</p><form id="cmU" class="form-grid"><div><label>Holat</label><select name="status">${["Yangi", "Ko'rilmoqda", "Hal qilindi"].map(x => `<option ${x === c.status ? "selected" : ""}>${x}</option>`).join("")}</select></div>
      <div class="full"><label>Javob</label><textarea name="answer" rows="3" maxlength="200">${esc(c.answer || "")}</textarea></div><div class="full acts"><button class="btn">Saqlash</button><button type="button" class="btn sec" onclick="closeModal()">Yopish</button></div></form>`, true);
    $("#cmU").onsubmit = guard(async e => { e.preventDefault(); await api("PUT", "/complaints/" + c.id, readForm(e.target)); closeModal(); complaintsPanel(tab); });
  });
}

async function shiftPanel(tab, month) {
  month = month || new Date().toISOString().slice(0, 7);
  const [r, list] = await Promise.all([api("GET", "/shift/report"), api("GET", "/shifts?month=" + month)]);
  const sh = r.shift;
  tab.innerHTML = `<div class="card"><div class="bar"><div class="grow"><h3 style="margin:0">${sh.open ? `Smena ${esc(sh.code)} ochiq` : "Smena ochilmagan"}</h3>
      <div class="muted small">${sh.stale ? "" : ""}${sh.open ? "Boshlangan: " + esc(sh.start) + (r.office ? " · " + esc(r.office.code + " " + r.office.name) : "") : "Ishni boshlash uchun smena oching."}${sh.stale ? ' <b style="color:var(--bad)">Kechagi smena yopilmagan!</b>' : ""}</div></div>
      ${sh.open ? `<button class="btn danger" id="shClose">Smenani yopish — Z</button>` : `<button class="btn lg" data-shift>Smena ochish — ofisni tanlang</button>`}</div></div>
    ${sh.stale ? `<div class="alert">⚠ Bu smena kechagi kundan qolgan. Avval uni yoping (kassadagi naqd pulni kiriting), keyin bugungi smenani oching.</div>` : ""}
    ${sh.open ? `<div class="grid"><div class="stat"><b>${r.orders}</b><span>Smenadagi buyurtmalar</span></div><div class="stat"><b>${money(r.sum)}</b><span>Jami summa</span></div>
      <div class="stat"><b>${money(r.cash_expected)}</b><span>Kassada bo'lishi kerak (naqd)</span></div>${Object.entries(r.by_payment).map(([k, v]) => `<div class="stat"><b>${money(v)}</b><span>${esc(k)}</span></div>`).join("")}</div>` : ""}
    <div class="card"><div class="bar"><h3 class="grow" style="margin:0">Smena monitoringi</h3><input type="month" id="shM" value="${month}" style="width:auto"></div>
    <div class="tablewrap"><table><thead><tr><th>№</th><th>Smena</th><th>Xodim</th><th>Boshlandi</th><th>Tugadi</th><th>Ofis</th><th>Buyurtma</th><th>Naqd (kutilgan)</th><th>Topshirilgan</th><th>Kamchilik</th><th>Balans</th><th>To'lanmagan</th></tr></thead><tbody>
    ${list.map((x, i) => `<tr><td>${i + 1}</td><td><b>${esc(x.code || "—")}</b> ${x.status === "Ochiq" ? `<span class="badge s1">ochiq</span>` : ""}</td><td>${esc(x.user)}</td><td>${esc(x.start)}</td><td>${esc(x.end || "—")}</td><td>${esc(x.branch)}</td>
      <td>${x.orders ?? "—"}</td><td>${x.cash_expected == null ? "—" : money(x.cash_expected)}</td><td>${x.cash == null ? "—" : money(x.cash)}</td><td style="color:${x.diff ? "var(--bad)" : "inherit"}">${x.diff == null ? "—" : x.diff ? money(x.diff) : "0"}</td>
      <td>${x.by_payment ? money(x.by_payment["Balans"] || 0) : "—"}</td><td>${x.by_payment ? money(x.by_payment["To'lanmagan"] || 0) : "—"}</td></tr>`).join("") || `<tr><td colspan="12" class="empty">Bu oyda smena yo'q</td></tr>`}</tbody></table></div></div>`;
  $("#shM").onchange = e => shiftPanel(tab, e.target.value || month);
  if ($("#shClose")) $("#shClose").onclick = () => {
    openModal(`<h2>Smenani yopish</h2><p class="muted">Kassadagi haqiqiy naqd pulni kiriting. Kutilgan: <b>${money(r.cash_expected)}</b></p>
      <form id="szF" class="form-grid"><div class="full"><label>Topshirilayotgan naqd pul (so'm)</label><input name="cash" type="number" min="0" step="1" value="${r.cash_expected}" required></div>
      <div class="full"><label>Izoh</label><input name="note" maxlength="300"></div><div class="full acts"><button class="btn danger">Smenani yopish</button><button type="button" class="btn sec" onclick="closeModal()">Bekor</button></div></form>`, true);
    $("#szF").onsubmit = guard(async e => { e.preventDefault(); await api("POST", "/shift/close", readForm(e.target)); me = await api("GET", "/me"); window.__shiftAsked = false; closeModal(); toast("Smena yopildi. Yangi smena ochish uchun ofisni tanlang"); render(); });
  };
}

async function movementsPanel(tab) {
  const ev = await api("GET", "/movements?limit=200");
  tab.innerHTML = `<div class="card"><div class="tablewrap"><table><thead><tr><th>Vaqt</th><th>Buyurtma</th><th>Holat</th><th>Kim</th><th>Izoh</th></tr></thead><tbody>
    ${ev.map(e => `<tr><td>${esc(e.time)}</td><td><a href="#/t/${esc(e.code)}">${esc(e.code)}</a></td><td>${badge(e.status)}</td><td>${esc(e.by)}</td><td>${esc(e.reason)}</td></tr>`).join("") || `<tr><td colspan="5" class="empty">Yo'q</td></tr>`}</tbody></table></div></div>`;
}

/* ---------- Qadoqlash materiallari (PMP) ---------- */
function pmpRowsHTML(prices, rows) {
  const types = prices.map(p => p.type);
  return rows.map((r, i) => {
    const sizes = (prices.find(p => p.type === r.type) || {sizes: []}).sizes;
    const z = sizes.find(x => x.size === r.size), pr = z ? z.price : 0;
    return `<div class="pmp-row" data-i="${i}"><div><label>Qadoqlash turi</label><select data-f="type">${types.map(t => `<option ${t === r.type ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></div>
      <div><label>Hajmi</label><select data-f="size"><option value="">---</option>${sizes.map(x => `<option value="${esc(x.size)}" ${x.size === r.size ? "selected" : ""}>${esc(x.size)}${x.price ? "" : " (narx yo'q)"}</option>`).join("")}</select></div>
      <div><label>Miqdori</label><input type="number" min="1" max="1000" value="${r.qty}" data-f="qty"></div>
      <div><label>Narxi</label><input value="${pr ? money(pr) : ""}" disabled></div><div><label>Jami</label><input value="${pr ? money(pr * r.qty) : ""}" disabled></div>
      <button type="button" class="btn danger sm" data-del="${i}">−</button></div>`;
  }).join("");
}
function pmpEditor(box, prices, rows, onChange) {
  const draw = () => { box.innerHTML = pmpRowsHTML(prices, rows) + `<div class="pmp-total">Jami: <b>${money(pmpTotal(prices, rows))}</b></div>`; onChange && onChange(); };
  box.addEventListener("change", e => {
    const row = e.target.closest(".pmp-row"); if (!row) return;
    const r = rows[+row.dataset.i], f = e.target.dataset.f;
    r[f] = f === "qty" ? Math.max(1, +e.target.value || 1) : e.target.value;
    if (f === "type") r.size = "";
    draw();
  });
  box.addEventListener("click", e => { const b = e.target.closest("[data-del]"); if (b) { rows.splice(+b.dataset.del, 1); draw(); } });
  draw(); return draw;
}
const pmpTotal = (prices, rows) => rows.reduce((t, r) => { const p = (prices.find(x => x.type === r.type) || {sizes: []}).sizes.find(z => z.size === r.size); return t + (p ? p.price * r.qty : 0); }, 0);

function pmpModal(prices, current, onSave) {
  const rows = current.length ? current.map(x => ({type: x.type, size: x.size, qty: x.qty})) : [{type: prices[0].type, size: "", qty: 1}];
  openModal(`<h2 style="text-align:center">Qadoqlash materiallari (PMP)</h2><div class="acts" style="justify-content:flex-end"><button type="button" class="btn blue" id="pmpAdd">+ Qo'shish</button></div>
    <div id="pmpBox"></div><div class="acts" style="justify-content:flex-end;margin-top:14px"><button type="button" class="btn danger" id="pmpClr">O'chirish</button><button type="button" class="btn ok" id="pmpSave">Saqlash</button></div>`);
  const draw = pmpEditor($("#pmpBox"), prices, rows);
  $("#pmpAdd").onclick = () => { rows.push({type: prices[0].type, size: "", qty: 1}); draw(); };
  $("#pmpClr").onclick = () => { onSave([]); closeModal(); };
  $("#pmpSave").onclick = () => { const ok = rows.filter(r => r.size); if (ok.some(r => !(prices.find(p => p.type === r.type).sizes.find(z => z.size === r.size) || {}).price)) return toast("Narxi belgilanmagan o'lcham tanlangan", true); onSave(ok); closeModal(); };
}

async function pmpPanel(tab) {
  const d = await api("GET", "/packaging");
  const rows = [{type: d.prices[0].type, size: "", qty: 1}];
  tab.innerHTML = `<div class="grid"><div class="stat"><b>${money(d.today_total)}</b><span>Bugungi qadoq sotuvi</span></div></div>
    <div class="grid wide"><div class="card"><h3>Qadoq sotish</h3><div id="pmpBox"></div><div class="acts" style="margin-top:12px"><button class="btn blue" id="pmpAdd">+ Qo'shish</button><button class="btn ok" id="pmpSell">Sotish</button></div></div>
    <div class="card"><h3>Narxlar</h3>${d.prices.map(p => `<h4 style="margin:10px 0 4px">${esc(p.type)}</h4><div class="chips">${p.sizes.map(z => `<span class="chip">${esc(z.size)} · ${z.price ? money(z.price) : "narx yo'q"}</span>`).join("")}</div>`).join("")}</div></div>
    <div class="card"><h3>Bugungi sotuvlar</h3><div class="tablewrap"><table><thead><tr><th>Vaqt</th><th>Xodim</th><th>Qadoq</th><th>Summa</th></tr></thead><tbody>
    ${d.sales.map(x => `<tr><td>${esc(x.time)}</td><td>${esc(x.user)}</td><td>${x.items.map(i => esc(i.type + " " + i.size + " × " + i.qty)).join(", ")}</td><td>${money(x.total)}</td></tr>`).join("") || `<tr><td colspan="4" class="empty">Bugun sotuv yo'q</td></tr>`}</tbody></table></div></div>`;
  const draw = pmpEditor($("#pmpBox"), d.prices, rows);
  $("#pmpAdd").onclick = () => { rows.push({type: d.prices[0].type, size: "", qty: 1}); draw(); };
  $("#pmpSell").onclick = guard(async () => {
    const items = rows.filter(r => r.size); if (!items.length) throw new Error("Hajmni tanlang");
    const r = await api("POST", "/packaging/sell", {items}); toast("Sotildi: " + money(r.total)); pmpPanel(tab);
  });
}

async function warehousePanel(tab) {
  const w = await api("GET", "/warehouse");
  tab.innerHTML = `<div class="grid"><div class="stat"><b>${w.items.length}</b><span>Ombordagi pochta</span></div><div class="stat"><b>${w.unplaced}</b><span>Shkafga joylanmagan</span></div>
    <div class="stat"><b>${Object.keys(w.shelves).length}</b><span>Band shkaflar</span></div></div>
    <div class="card"><div class="chips">${Object.entries(w.shelves).map(([k, n]) => `<button class="chip" data-shelf="${esc(k)}">${esc(k)} · ${n}</button>`).join("") || `<span class="muted">Hali shkafga joylanmagan</span>`}</div>
    <div class="form-grid" style="margin-top:12px"><div><label>Qidirish (raqam, mahsulot, shkaf)</label><input id="wq"></div></div>
    <div class="tablewrap"><table><thead><tr><th>Raqam</th><th>Mahsulot</th><th>Qabul qiluvchi</th><th>Qayerga</th><th>Holat</th><th>Shkaf</th></tr></thead><tbody id="wb"></tbody></table></div></div>`;
  const draw = () => {
    const q = $("#wq").value.toLowerCase();
    $("#wb").innerHTML = w.items.filter(i => !q || (i.code + " " + i.product + " " + i.shelf + " " + i.receiver).toLowerCase().includes(q)).map(i =>
      `<tr><td><a href="#/t/${esc(i.code)}">${esc(i.code)}</a></td><td>${esc(i.product)}</td><td>${esc(i.receiver)}</td><td>${esc(i.to)}</td><td>${badge(i.status)}</td>
       <td><input class="shelf" data-id="${i.id}" value="${esc(i.shelf)}" maxlength="12" placeholder="A-1" style="width:90px"></td></tr>`).join("") || `<tr><td colspan="6" class="empty">Yo'q</td></tr>`;
  };
  $("#wq").oninput = draw; draw();
  on(tab, "click", "[data-shelf]", b => { $("#wq").value = b.dataset.shelf; draw(); });
  on(tab, "change", ".shelf", guard(async inp => { await api("POST", `/orders/${inp.dataset.id}/shelf`, {shelf: inp.value}); toast("Saqlandi"); }));
}

const KIND_ST = {Ochiq: "s0", "Yo'lda": "s1", Yopilgan: "s2"};
async function tripsPanel(tab, openId) {
  if (openId) return tripDetail(tab, openId);
  const [list, d] = await Promise.all([api("GET", "/trips"), api("GET", "/dict")]);
  const nm = c => { const b = d.branches.find(x => x.code === c); return b ? c + " " + b.name : c; };
  tab.innerHTML = `<div class="card"><h3>Yangi reys</h3><form id="trF" class="form-grid">
    <div><label>Qayerdan</label><input value="${esc(me.office ? me.office.code + " " + me.office.name : "Smena oching")}" disabled></div>
    <div><label>Qayerga (ofis)</label><input name="to" list="brList" placeholder="Kod yoki nom" required><datalist id="brList">${d.branches.map(b => `<option value="${esc(b.code + " - " + b.name)}">`).join("")}</datalist></div>
    <div class="full"><label>Izoh</label><input name="note" maxlength="300" placeholder="Mashina raqami, haydovchi…"></div>
    <div class="full acts"><button class="btn">Reys ochish</button></div></form></div>
    <div class="card"><h3>Reyslar</h3><div class="tablewrap"><table><thead><tr><th>Reys</th><th>Yo'nalish</th><th>Buyurtma</th><th>Qabul qilingan</th><th>Holat</th><th>Yaratilgan</th><th></th></tr></thead><tbody>
    ${list.map(t => `<tr><td><b>${esc(t.code)}</b></td><td>${esc(nm(t.from))} → ${esc(nm(t.to))}</td><td>${t.orders_n}</td><td>${t.received_n}</td><td><span class="badge ${KIND_ST[t.status] || ""}">${esc(t.status)}</span>${t.missing.length ? `<div class="small" style="color:var(--bad)">Yetib kelmagan: ${esc(t.missing.join(", "))}</div>` : ""}</td>
      <td>${esc(t.created)}<div class="muted small">${esc(t.by)}</div></td><td><a class="btn sec sm" href="#/operator/trips/${t.id}">Ochish</a></td></tr>`).join("") || `<tr><td colspan="7" class="empty">Reys yo'q</td></tr>`}</tbody></table></div></div>`;
  $("#trF").onsubmit = guard(async e => { e.preventDefault(); const t = await api("POST", "/trips", readForm(e.target)); toast("Reys ochildi: " + t.code); location.hash = "#/operator/trips/" + t.id; });
}

async function tripDetail(tab, id) {
  const draw = async () => {
    const t = await api("GET", `/trips/${id}`);
    const open = t.status === "Ochiq", way = t.status === "Yo'lda";
    tab.innerHTML = `<div class="grid"><div class="stat"><b>${esc(t.code)}</b><span>${esc(t.from)} → ${esc(t.to)}</span></div><div class="stat"><b>${t.orders_n}</b><span>Yuklangan</span></div><div class="stat"><b>${t.received_n}</b><span>Qabul qilingan</span></div>
      <div class="stat"><b><span class="badge ${KIND_ST[t.status] || ""}">${esc(t.status)}</span></b><span>${esc(t.note || "")}</span></div></div>
    ${open || way ? `<div class="card"><form id="scF" class="form-grid"><div class="full"><label>${open ? "Yuklash: shtrix-kod yoki raqamni skanerlang" : "Qabul qilish: shtrix-kod yoki raqamni skanerlang"} va Enter bosing</label><input id="scI" autofocus autocomplete="off" inputmode="numeric" placeholder="BTS-00001 yoki 12 xonali shtrix-kod" style="font-size:18px"></div></form><div id="scM" class="small muted"></div></div>` : ""}
    <div class="card"><div class="tablewrap"><table><thead><tr><th>Raqam</th><th>Mahsulot</th><th>Qabul qiluvchi</th><th>Qayerga</th><th>Og'irlik</th><th>Holat</th><th></th></tr></thead><tbody>
      ${t.items.map(o => `<tr><td><a href="#/t/${esc(o.code)}">${esc(o.code)}</a></td><td>${esc(o.product)}</td><td>${esc(o.receiver)}</td><td>${esc(o.to)}</td><td>${esc(o.weight)} kg</td>
        <td>${way || t.status === "Yopilgan" ? (o.received ? `<span class="badge s2">Qabul qilindi</span>` : `<span class="badge s1">Kutilmoqda</span>`) : badge(o.status)}</td>
        <td>${open ? `<button class="btn sec sm" data-un="${esc(o.code)}">Olib tashlash</button>` : ""}</td></tr>`).join("") || `<tr><td colspan="7" class="empty">Hali yuklanmagan</td></tr>`}</tbody></table></div>
      <div class="acts" style="margin-top:14px">${open ? `<button class="btn" id="dep" ${t.orders_n ? "" : "disabled"}>Reysni jo'natish</button>` : ""}${way ? `<button class="btn" id="cls">Reysni yopish</button>` : ""}<a class="btn sec" href="#/operator/trips">← Reyslar</a><button class="btn sec" onclick="window.print()">Chop etish</button></div>
      ${t.missing.length ? `<div class="alert" style="margin-top:12px">Yetib kelmagan: ${esc(t.missing.join(", "))}</div>` : ""}</div>`;
    const inp = $("#scI");
    if (inp) {
      inp.focus();
      $("#scF").onsubmit = async e => {
        e.preventDefault(); const q = inp.value.trim(); if (!q) return; inp.value = "";
        try { const r = await api("POST", `/trips/${id}/${open ? "load" : "receive"}`, {q}); $("#scM").innerHTML = `<span style="color:var(--ok)">✔ ${esc(r.order.code)} · ${esc(r.order.receiver)}</span>`; await draw(); }
        catch (err) { $("#scM").innerHTML = `<span style="color:var(--bad)">✖ ${esc(err.message)}</span>`; inp.focus(); }
      };
    }
    on(tab, "click", "[data-un]", guard(async b => { await api("POST", `/trips/${id}/unload`, {q: b.dataset.un}); draw(); }));
    if ($("#dep")) $("#dep").onclick = guard(async () => { if (await confirmBox("Reys jo'natilsinmi? Buyurtmalar «Yo'lda» holatiga o'tadi.", "Jo'natish")) { await api("POST", `/trips/${id}/depart`); toast("Reys jo'natildi"); draw(); } });
    if ($("#cls")) $("#cls").onclick = guard(async () => { if (await confirmBox(t.orders_n - t.received_n ? `${t.orders_n - t.received_n} ta buyurtma hali qabul qilinmagan. Baribir yopilsinmi?` : "Reys yopilsinmi?", "Yopish")) { await api("POST", `/trips/${id}/close`); toast("Reys yopildi"); draw(); } });
  };
  await draw();
}

async function scanPanel(tab) {
  const log = [];
  tab.innerHTML = `<div class="card"><div class="form-grid"><div><label>Amal</label><select id="scA"><option value="info">Ma'lumot ko'rish</option><option value="shelf">Shkafga joylash</option><option value="Yo'lda">Holat: Yo'lda</option><option value="Yetkazildi">Holat: Yetkazildi</option></select></div>
    <div id="scShW" class="hidden"><label>Shkaf (masalan A-3)</label><input id="scSh" maxlength="12"></div>
    <div class="full"><label>Shtrix-kod / raqam (skaner Enter yuboradi)</label><input id="scI" autofocus autocomplete="off" style="font-size:20px" placeholder="Skanerlang…"></div></div></div><div class="card" id="scL"><div class="muted">Hali skanerlanmagan</div></div>`;
  const A = $("#scA"), I = $("#scI");
  A.onchange = () => { $("#scShW").classList.toggle("hidden", A.value !== "shelf"); I.focus(); };
  $("#scI").parentElement.parentElement.onsubmit = null;
  I.onkeydown = guard(async e => {
    if (e.key !== "Enter") return; e.preventDefault();
    const q = I.value.trim(); if (!q) return; I.value = "";
    let msg, ok = true;
    try {
      const r = await api("GET", "/find?q=" + encodeURIComponent(q)); const o = r[0];
      if (!o) throw new Error("Topilmadi: " + q);
      if (A.value === "shelf") { const sh = $("#scSh").value; await api("POST", `/orders/${o.id}/shelf`, {shelf: sh}); msg = `${o.code} → shkaf ${sh || "—"}`; }
      else if (A.value === "info") msg = `${o.code} · ${o.receiver} · ${o.to} · ${o.status}${o.shelf ? " · shkaf " + o.shelf : ""}`;
      else { await api("POST", `/orders/${o.id}/status`, {status: A.value}); msg = `${o.code} → ${A.value}`; }
    } catch (err) { ok = false; msg = err.message; }
    log.unshift([ok, msg, new Date().toLocaleTimeString()]);
    $("#scL").innerHTML = log.slice(0, 30).map(([k, m, t]) => `<div class="small" style="padding:4px 0;color:${k ? "var(--ok)" : "var(--bad)"}">${k ? "✔" : "✖"} ${esc(m)} <span class="muted">${t}</span></div>`).join("");
    I.focus();
  });
}

function dangerPanel(tab) {
  const rows = [["Portlovchi va yonuvchi moddalar", "Benzin, gaz ballonlari, petardalar, o'q-dorilar, tez alangalanuvchi suyuqliklar."], ["Zaharli va kimyoviy moddalar", "Kislotalar, pestitsidlar, simob, zaharli kukunlar."],
    ["Akkumulyatorlar", "Alohida qadoqda, ko'pi bilan ruxsat etilgan hajmda (litiy batareyalar uchun ogohlantirish)."], ["Qurol va giyohvand moddalar", "Taqiqlangan, qabul qilinmaydi."], ["Tez buziladigan mahsulotlar", "Go'sht, sut mahsulotlari: faqat sovutgichli qadoqda va qisqa muddatga."],
    ["Pul va qimmatbaho buyumlar", "Faqat sug'urta e'lon qilingan holda."], ["Jonli hayvonlar va o'simliklar", "Qabul qilinmaydi."]];
  tab.innerHTML = `<div class="card"><p class="muted">Quyidagi yuklar qabul qilinmaydi yoki maxsus shart bilan qabul qilinadi. Shubha bo'lsa, buyurtmani qabul qilishdan oldin adminga murojaat qiling.</p>
    ${rows.map(([h, t]) => `<div class="alert" style="background:#fff;border-color:#ebecf2;color:inherit"><b>⚠ ${h}</b><div class="muted small" style="font-weight:400">${t}</div></div>`).join("")}</div>`;
}

async function securityPanel(tab) {
  const bl = await api("GET", "/blacklist");
  tab.innerHTML = `<div class="card"><h3>Qora ro'yxat (telefon raqamlar)</h3><p class="muted small">Bu raqamlar bilan buyurtma qabul qilinmaydi.</p>
    <form id="blF" class="form-grid"><div><label>Telefon</label><input name="phone" type="tel" placeholder="+998 90 123 45 67" required></div><div><label>Sabab</label><input name="reason" maxlength="300"></div><div style="align-self:end"><button class="btn">Qo'shish</button></div></form>
    <div class="tablewrap"><table><thead><tr><th>Telefon</th><th>Sabab</th><th>Qo'shgan</th><th></th></tr></thead><tbody>
    ${bl.map(b => `<tr><td>${esc(b.phone)}</td><td>${esc(b.reason)}</td><td>${esc(b.by)}<div class="muted small">${esc(b.time)}</div></td><td><button class="btn danger sm" data-bl="${esc(b.phone)}">Olib tashlash</button></td></tr>`).join("") || `<tr><td colspan="4" class="empty">Ro'yxat bo'sh</td></tr>`}</tbody></table></div></div>
    <div class="card"><h3>Zaxira nusxa</h3><p class="muted small">Barcha ma'lumotlar JSON faylga yuklab olinadi (parollar kiritilmaydi). Faylni xavfsiz joyda saqlang.</p><button class="btn" id="bkB">Zaxirani yuklab olish</button></div>`;
  $("#blF").onsubmit = guard(async e => { e.preventDefault(); await api("POST", "/blacklist", readForm(e.target)); toast("Qo'shildi"); securityPanel(tab); });
  on(tab, "click", "[data-bl]", guard(async b => { await api("DELETE", "/blacklist?phone=" + encodeURIComponent(b.dataset.bl)); securityPanel(tab); }));
  $("#bkB").onclick = guard(async () => {
    const r = await fetch("/api/backup", {headers: {Authorization: "Bearer " + token}});
    if (!r.ok) throw new Error("Yuklab bo'lmadi");
    const a = document.createElement("a"); a.href = URL.createObjectURL(await r.blob()); a.download = "bts-zaxira.json"; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  });
}

async function handoverPanel(tab) {
  tab.innerHTML = `<div class="card"><p class="muted">Mijoz o'z kabinetidagi 4 xonali topshirish kodini aytadi. Buyurtma raqami va kodni kiriting.</p>
    <form id="hoF" class="form-grid"><div><label>Buyurtma raqami</label><input name="id" placeholder="BTS-00001" required></div><div><label>Topshirish kodi</label><input name="code" inputmode="numeric" maxlength="4" required></div>
    <div class="full acts"><button class="btn">Topshirish</button></div></form></div>`;
  $("#hoF").onsubmit = guard(async e => {
    e.preventDefault();
    const f = readForm(e.target), n = parseInt(String(f.id).replace(/\D/g, ""), 10);
    if (!n) throw new Error("Buyurtma raqami noto'g'ri");
    const o = await api("POST", `/orders/${n}/handover`, {code: f.code});
    toast(o.code + " topshirildi"); e.target.reset();
  });
}

async function adminAudit(tab) {
  const rows = await api("GET", "/audit?limit=300");
  tab.innerHTML = `<div class="card"><p class="muted">Oxirgi ${rows.length} ta amal (eng yangisi tepada).</p><div class="tablewrap"><table><thead><tr><th>Vaqt</th><th>Foydalanuvchi</th><th>Amal</th><th>Tafsilot</th><th>IP</th></tr></thead><tbody>
    ${rows.map(r => `<tr><td>${esc(r.time)}</td><td>${esc(r.user)} <span class="muted small">${esc(r.role)}</span></td><td>${esc(r.action)}</td><td>${esc(r.detail)}</td><td>${esc(r.ip)}</td></tr>`).join("") || `<tr><td colspan="5" class="empty">Hozircha yozuv yo'q</td></tr>`}</tbody></table></div></div>`;
}

/* ---------- Ofislar (ochiq) ---------- */
async function viewOffices(el) {
  const d = await api("GET", "/public/offices");
  el.innerHTML = `<h1>Ofislarimiz</h1><div class="card"><div class="form-grid"><div><label>Viloyat</label><select id="of_r"><option value="">Hammasi</option>${Object.keys(d.regions).map(r => `<option>${esc(r)}</option>`).join("")}</select></div>
    <div><label>Qidirish</label><input id="of_q" placeholder="Nom yoki manzil"></div></div><div class="tablewrap"><table><thead><tr><th>Kod</th><th>Ofis</th><th>Hudud</th><th>Manzil</th></tr></thead><tbody id="of_b"></tbody></table></div></div>`;
  const draw = () => {
    const r = $("#of_r").value, q = $("#of_q").value.toLowerCase();
    $("#of_b").innerHTML = d.offices.filter(o => (!r || o.region === r) && (!q || (o.name + " " + o.address).toLowerCase().includes(q)))
      .map(o => `<tr><td>${esc(o.code)}</td><td>${esc(o.name)}</td><td>${esc([o.region, o.district].filter(Boolean).join(", "))}</td><td>${esc(o.address)}</td></tr>`).join("");
  };
  $("#of_r").onchange = draw; $("#of_q").oninput = draw; draw();
}

/* ---------- Mijoz kabineti ---------- */
async function viewCustomer(el, sub) {
  const rid = renderId;
  el.innerHTML = `<h1>Salom, ${esc(me.name)}!</h1>${tabsHTML("customer", [["", "Buyurtmalarim"], ["new", "Yangi buyurtma"], ["complaint", "Shikoyat"]], sub)}<div id="tab"></div>`;
  const tab = $("#tab");
  if (sub === "complaint") return complaintsPanel(tab);
  if (sub === "new") return customerNew(tab, rid);
  const list = await api("GET", "/my/orders");
  if (rid !== renderId) return;
  tab.innerHTML = list.length ? `<div class="card"><div class="tablewrap"><table><thead><tr><th>Raqam</th><th></th><th>Mahsulot</th><th>Qayerga / qayerdan</th><th>Narx</th><th>Holat</th><th></th></tr></thead><tbody>
    ${list.map(o => `<tr><td><a href="#/t/${esc(o.code)}">${esc(o.code)}</a><div class="muted small">${esc(o.created)}</div></td><td>${o.direction === "out" ? "Yuborilgan" : "Kelayotgan"}</td><td>${esc(o.product)}</td>
      <td>${esc(o.direction === "out" ? o.address : o.sender_name)}</td><td>${money(o.price)}</td><td>${badge(o.status)}${o.pickup_code && o.direction === "in" ? `<div class="small">Topshirish kodi: <b>${esc(o.pickup_code)}</b></div>` : ""}</td>
      <td>${o.direction === "out" && o.status === STATUSES[0] ? `<button class="btn danger sm" data-cancel="${o.id}">Bekor qilish</button>` : ""}</td></tr>`).join("")}</tbody></table></div></div>`
    : `<div class="card empty">Hozircha buyurtma yo'q. <a href="#/customer/new">Birinchi buyurtmani bering</a>.</div>`;
  on(tab, "click", "[data-cancel]", guard(async b => {
    if (await confirmBox("Buyurtma bekor qilinsinmi?", "Bekor qilish")) { await api("POST", "/my/orders/" + b.dataset.cancel + "/cancel"); toast("Bekor qilindi"); render(); }
  }));
}
async function customerNew(tab, rid) {
  const dict = await api("GET", "/dict");
  if (rid !== renderId) return;
  const regs = Object.keys(dict.regions);
  const SELn = (n, l, opts, req) => `<div><label>${l}</label><select name="${n}" ${req ? "required" : ""}><option value="">---</option>${opts.map(x => `<option>${esc(x)}</option>`).join("")}</select></div>`;
  tab.innerHTML = `<div class="card"><form id="cf" class="form-grid">
    <div><label>Qabul qiluvchi ismi</label><input name="receiver_name" required maxlength="80"></div>
    <div><label>Qabul qiluvchi telefoni</label><input name="receiver_phone" type="tel" placeholder="+998 90 123 45 67" required></div>
    ${SELn("receiver_region", "Viloyat", regs, true)}${SELn("receiver_district", "Tuman", [])}${SELn("receiver_branch", "Filial (olib ketish)", [])}
    <div class="full"><label>Manzil (eshikkacha yetkazish uchun)</label><input name="address" maxlength="250"></div>
    <div><label>Mahsulot</label><select name="product" required><option value="">---</option>${dict.contents.map(x => `<option>${esc(x)}</option>`).join("")}</select></div>
    <div><label>Og'irligi (kg)</label><input name="weight" type="number" step="0.01" min="0.01" required></div>
    <div><label>Uzunlik / kenglik / balandlik (sm)</label><div style="display:flex;gap:6px"><input name="length" type="number" min="0" placeholder="U"><input name="width" type="number" min="0" placeholder="K"><input name="height" type="number" min="0" placeholder="B"></div></div>
    <div style="align-self:end"><label class="chk"><input type="checkbox" name="door_delivery"> Eshikkacha yetkazish</label></div>
    <div class="full"><label>Izoh</label><input name="note" maxlength="300"></div>
    <div class="full" id="cq" style="font-weight:600"></div>
    <div class="full acts"><button class="btn">Buyurtma berish</button></div></form></div>`;
  const f = $("#cf"), E = f.elements;
  cascade(f, "receiver", dict);
  const quote = async () => {
    if (!(+E.weight.value > 0)) { $("#cq").textContent = ""; return; }
    try { const q = await api("POST", "/calc", {weight: E.weight.value, length: E.length.value, width: E.width.value, height: E.height.value, door_delivery: E.door_delivery.checked}); $("#cq").textContent = "Narx: " + money(q.price); } catch {}
  };
  f.addEventListener("input", quote); f.addEventListener("change", quote);
  f.onsubmit = guard(async e => {
    e.preventDefault();
    const b = readForm(f);
    if (!b.address && !b.receiver_branch) throw new Error("Manzilni yoki filialni ko'rsating");
    const o = await api("POST", "/my/orders", b);
    toast("Buyurtma qabul qilindi: " + o.code); location.hash = "#/customer";
  });
}

render();

if (location.protocol === "file:") {
  document.body.insertAdjacentHTML("afterbegin", `<div style="background:#fff3cd;color:#6b4e00;padding:12px 20px;text-align:center;font-weight:600">
    ⚠ Bu sahifa to'g'ridan-to'g'ri fayldan ochilgan, shuning uchun ishlamaydi. start.bat (Windows) yoki start.sh ni ishga tushiring, so'ng brauzerda <u>http://localhost:8000</u> ni oching.</div>`);
}
