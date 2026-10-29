/* Jo'natma yorlig'i (chek): shtrix-kod (Code 128), QR-kod va BTS uslubidagi yorliq. Tashqi kutubxonasiz. */

/* ---------- QR-kod (Model 2, bayt rejimi, xatoni tuzatish darajasi L, 1-10 versiya) ---------- */
const QR = (() => {
  const EXP = new Array(512), LOG = new Array(256);
  let x = 1;
  for (let i = 0; i < 255; i++) { EXP[i] = x; LOG[x] = i; x <<= 1; if (x & 256) x ^= 0x11d; }
  for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255];
  const mul = (a, b) => (a && b ? EXP[LOG[a] + LOG[b]] : 0);
  const rsGen = n => { let g = [1]; for (let i = 0; i < n; i++) { const ng = new Array(g.length + 1).fill(0); for (let j = 0; j < g.length; j++) { ng[j] ^= g[j]; ng[j + 1] ^= mul(g[j], EXP[i]); } g = ng; } return g; };
  const rsEnc = (data, n) => { const g = rsGen(n), res = new Array(n).fill(0); for (const d of data) { const f = d ^ res[0]; res.shift(); res.push(0); if (f) for (let i = 0; i < n; i++) res[i] ^= mul(g[i + 1], f); } return res; };
  // versiya: [bir blokdagi EC baytlar, bloklardagi ma'lumot baytlari]
  const VER = {1: [7, [19]], 2: [10, [34]], 3: [15, [55]], 4: [20, [80]], 5: [26, [108]], 6: [18, [68, 68]], 7: [20, [78, 78]],
    8: [24, [97, 97]], 9: [30, [116, 116]], 10: [18, [68, 68, 69, 69]]};
  const ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]};
  const bit = (v, i) => ((v >>> i) & 1) === 1;

  function encode(text) {
    const bytes = Array.from(new TextEncoder().encode(text));
    let ver = 0;
    for (let v = 1; v <= 10; v++) {
      const cap = VER[v][1].reduce((a, b) => a + b, 0) * 8;
      if (4 + (v < 10 ? 8 : 16) + bytes.length * 8 <= cap) { ver = v; break; }
    }
    if (!ver) throw new Error("QR uchun matn juda uzun");
    const [ecLen, sizes] = VER[ver], total = sizes.reduce((a, b) => a + b, 0);
    const bits = [];
    const put = (val, n) => { for (let i = n - 1; i >= 0; i--) bits.push((val >>> i) & 1); };
    put(4, 4); put(bytes.length, ver < 10 ? 8 : 16); bytes.forEach(b => put(b, 8));
    put(0, Math.min(4, total * 8 - bits.length));
    while (bits.length % 8) bits.push(0);
    const data = [];
    for (let i = 0; i < bits.length; i += 8) data.push(parseInt(bits.slice(i, i + 8).join(""), 2));
    for (let pad = 0xec; data.length < total; pad ^= 0xec ^ 0x11) data.push(pad);
    const blocks = [], ecs = [];
    let off = 0;
    for (const n of sizes) { const b = data.slice(off, off + n); off += n; blocks.push(b); ecs.push(rsEnc(b, ecLen)); }
    const out = [];
    for (let i = 0; i < Math.max(...sizes); i++) blocks.forEach(b => { if (i < b.length) out.push(b[i]); });
    for (let i = 0; i < ecLen; i++) ecs.forEach(e => out.push(e[i]));

    const size = 17 + 4 * ver;
    const mod = Array.from({length: size}, () => new Array(size).fill(false));
    const fn = Array.from({length: size}, () => new Array(size).fill(false));
    const setF = (xx, yy, v) => { if (xx >= 0 && yy >= 0 && xx < size && yy < size) { mod[yy][xx] = v; fn[yy][xx] = true; } };
    for (let i = 0; i < size; i++) { setF(6, i, i % 2 === 0); setF(i, 6, i % 2 === 0); }
    for (const [cx, cy] of [[3, 3], [size - 4, 3], [3, size - 4]])
      for (let dy = -4; dy <= 4; dy++) for (let dx = -4; dx <= 4; dx++) { const d = Math.max(Math.abs(dx), Math.abs(dy)); setF(cx + dx, cy + dy, d !== 2 && d !== 4); }
    const ap = ALIGN[ver];
    ap.forEach((ax, i) => ap.forEach((ay, j) => {
      if ((i === 0 && j === 0) || (i === 0 && j === ap.length - 1) || (i === ap.length - 1 && j === 0)) return;
      for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) setF(ax + dx, ay + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
    }));
    const drawFormat = mask => {
      const d = (1 << 3) | mask;                          // L = 01
      let rem = d; for (let i = 0; i < 10; i++) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
      const f = ((d << 10) | rem) ^ 0x5412;
      for (let i = 0; i <= 5; i++) setF(8, i, bit(f, i));
      setF(8, 7, bit(f, 6)); setF(8, 8, bit(f, 7)); setF(7, 8, bit(f, 8));
      for (let i = 9; i < 15; i++) setF(14 - i, 8, bit(f, i));
      for (let i = 0; i < 8; i++) setF(size - 1 - i, 8, bit(f, i));
      for (let i = 8; i < 15; i++) setF(8, size - 15 + i, bit(f, i));
      setF(8, size - 8, true);
    };
    drawFormat(0);
    if (ver >= 7) {
      let rem = ver; for (let i = 0; i < 12; i++) rem = (rem << 1) ^ ((rem >>> 11) * 0x1f25);
      const v = (ver << 12) | rem;
      for (let i = 0; i < 18; i++) { const a = size - 11 + (i % 3), b = Math.floor(i / 3); setF(a, b, bit(v, i)); setF(b, a, bit(v, i)); }
    }
    // ma'lumotni joylash (zigzag)
    const all = []; out.forEach(b => { for (let i = 7; i >= 0; i--) all.push((b >>> i) & 1); });
    let k = 0;
    for (let right = size - 1; right >= 1; right -= 2) {
      if (right === 6) right = 5;
      for (let vert = 0; vert < size; vert++) for (let j = 0; j < 2; j++) {
        const xx = right - j, up = ((right + 1) & 2) === 0, yy = up ? size - 1 - vert : vert;
        if (!fn[yy][xx] && k < all.length) { mod[yy][xx] = all[k++] === 1; }
      }
    }
    const MASK = [(a, b) => (a + b) % 2 === 0, (a, b) => b % 2 === 0, (a, b) => a % 3 === 0, (a, b) => (a + b) % 3 === 0,
      (a, b) => (Math.floor(a / 3) + Math.floor(b / 2)) % 2 === 0, (a, b) => ((a * b) % 2) + ((a * b) % 3) === 0,
      (a, b) => (((a * b) % 2) + ((a * b) % 3)) % 2 === 0, (a, b) => (((a + b) % 2) + ((a * b) % 3)) % 2 === 0];
    const applyMask = m => { for (let yy = 0; yy < size; yy++) for (let xx = 0; xx < size; xx++) if (!fn[yy][xx] && MASK[m](xx, yy)) mod[yy][xx] = !mod[yy][xx]; };
    const penalty = () => {
      let p = 0;
      const line = get => {
        let run = 1;
        for (let i = 1; i < size; i++) { if (get(i) === get(i - 1)) { run++; if (run === 5) p += 3; else if (run > 5) p++; } else run = 1; }
        // finder o'xshash naqsh
        for (let i = 0; i + 11 <= size; i++) {
          const s = []; for (let j = 0; j < 11; j++) s.push(get(i + j) ? 1 : 0);
          const t = s.join("");
          if (t === "10111010000" || t === "00001011101") p += 40;
        }
      };
      for (let a = 0; a < size; a++) { line(i => mod[a][i]); line(i => mod[i][a]); }
      for (let yy = 0; yy < size - 1; yy++) for (let xx = 0; xx < size - 1; xx++) { const c = mod[yy][xx]; if (c === mod[yy][xx + 1] && c === mod[yy + 1][xx] && c === mod[yy + 1][xx + 1]) p += 3; }
      let dark = 0; mod.forEach(r => r.forEach(c => { if (c) dark++; }));
      p += Math.floor(Math.abs(dark * 20 - size * size * 10) / (size * size)) * 10;
      return p;
    };
    let best = 0, bestP = Infinity;
    for (let m = 0; m < 8; m++) { applyMask(m); drawFormat(m); const p = penalty(); if (p < bestP) { bestP = p; best = m; } applyMask(m); }
    applyMask(best); drawFormat(best);
    return mod;
  }
  function svg(text, px) {
    const m = encode(text), n = m.length, q = 2;
    let d = "";
    m.forEach((row, y) => row.forEach((c, xx) => { if (c) d += `M${xx + q} ${y + q}h1v1h-1z`; }));
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${n + 2 * q} ${n + 2 * q}" width="${px}" height="${px}" shape-rendering="crispEdges"><rect width="100%" height="100%" fill="#fff"/><path d="${d}" fill="#000"/></svg>`;
  }
  return {encode, svg};
})();

/* ---------- Shtrix-kod: Code 128 (C to'plami, faqat raqamlar) ---------- */
const CODE128 = ["212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213", "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132", "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211", "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313", "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331", "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111", "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214", "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111", "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141", "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141", "114131", "311141", "411131", "211412", "211214", "211232", "2331112"];
function code128Widths(digits) {
  if (digits.length % 2) digits = "0" + digits;
  const vals = [105];
  for (let i = 0; i < digits.length; i += 2) vals.push(+digits.slice(i, i + 2));
  let sum = 105; for (let i = 1; i < vals.length; i++) sum += vals[i] * i;
  vals.push(sum % 103, 106);
  return vals.map(v => CODE128[v]).join("");
}
function barcodeSVG(digits, w, h) {
  const widths = code128Widths(digits), mods = widths.split("").reduce((a, c) => a + +c, 0);
  let xx = 0, d = "", bar = true;
  for (const c of widths) { if (bar) d += `M${xx} 0h${c}v1h-${c}z`; xx += +c; bar = !bar; }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${mods} 1" preserveAspectRatio="none" width="${w}" height="${h}" shape-rendering="crispEdges"><path d="${d}" fill="#000"/></svg>`;
}

/* ---------- Yorliq ---------- */
const spaced = d => d.replace(/(\d{3})(?=\d)/g, "$1 ");
function labelURL(o) { return location.origin.replace(/^file:.*/, "http://localhost:8000") + "/#/t/" + encodeURIComponent(o.code); }
function labelHTML(o) {
  const e = typeof esc === "function" ? esc : String;
  const br = String(o.receiver_branch || ""), m = br.match(/^(\d+)\s*-\s*(.*)$/);
  const bcode = m ? m[1] : "", bname = m ? m[2] : br;
  const region2 = bcode ? (bcode.length === 5 && bcode[0] === "9" ? bcode.slice(1, 3) : bcode.slice(0, 2)) : "";
  const title = ((bname || String(o.receiver_district || o.receiver_region || "").replace(/ (shahri|tumani)$/i, "")) + " " + region2).trim().toUpperCase();
  const place = o.receiver_district || o.receiver_region || "";
  const addr = [o.receiver_region, o.receiver_district, o.address].filter(Boolean).join(", ");
  const saddr = [o.sender_region, o.sender_district, o.sender_address].filter(Boolean).join(", ");
  const barcode = o.barcode || "000000000000";
  const t = String(o.created || ""), dt = t.length >= 16 ? t.slice(8, 10) + "." + t.slice(5, 7) + "." + t.slice(0, 4) + " " + t.slice(11, 16) : t;
  const price = new Intl.NumberFormat("en-US").format(Math.round(o.price || 0)).replace(/,/g, " ");
  const vol = o.volume_cm3 ? o.volume_cm3 : 0;
  return `<div class="lbl-wrap" id="labelBox">
    <div class="lbl-title">${e(title)}</div>
    <div class="lbl-main"><div class="lbl-num">${e(barcode)}</div>
    <div class="lbl-card">
      <div class="lc-head"><div class="lc-logo"><span>BTS</span></div><div class="lc-bc">${barcodeSVG(barcode, "100%", 92)}<div class="lc-bcn">${spaced(barcode)}</div></div></div>
      <div class="vl">FILIAL</div><div class="lc-filial"><div class="a">${e(place)}</div><div class="b">${e(br || (o.door_delivery ? "ESHIKKACHA" : ""))}</div></div>
      <div class="vl">QABUL QILUVCHI</div>
      <div class="lc-recv"><div><b>F.I.SH:</b> ${e(o.receiver_name)}</div><div><b>MANZIL:</b> ${e(addr)}</div><div class="tel"><b>TELEFON:</b> ${e(o.receiver_phone)}${o.receiver_phone2 ? ", " + e(o.receiver_phone2) : ""}</div></div>
      <div class="lc-price"><small>BTS XIZMATI</small><b>${price}</b></div>
      <div class="vl">OPSIYA</div><div class="lc-opt"><svg viewBox="0 0 48 48" class="optico"><rect x="9" y="9" width="30" height="30" fill="none" stroke="#000" stroke-width="3" rx="2"/><path d="M24 15v18M28 19c-1-2-7-2-7 1.5s7 1.500 7 5-6 3.500-8 1" fill="none" stroke="#000" stroke-width="2.600"/><path d="M4 18h8M4 18l3-3M4 18l3 3M44 30h-8M44 30l-3-3M44 30l-3 3" fill="none" stroke="#000" stroke-width="2.200"/></svg>
        <span>${e(o.payment_type || "")}${o.door_delivery ? " · ESHIKKACHA" : ""}</span></div>
      <div class="lc-blank"></div>
      <div class="vl">VAZN</div><div class="lc-w"><b>Ichida:</b> ${e(o.product)} &nbsp;<b>Soni:</b> ${e(o.quantity || 1)}<br><b>Vazn:</b> ${e(o.weight)} kg &nbsp;<b>Hajm:</b> ${e(vol)} &nbsp;<b>Qadoq:</b> ${e(o.package || "—")}</div>
      <div class="vl">DIQQAT</div><div class="lc-warn">EHTIYOT BO'LING!</div>
      <div class="vl">YUBORUVCHI</div>
      <div class="lc-send"><div><b>F.I.SH:</b> ${e(o.sender_name)}</div><div><b>MANZIL:</b> ${e(o.office_address || saddr)}</div><div class="tel"><b>TELEFON:</b> ${e(o.sender_phone)}</div>
        <div class="by">${e(o.created_by || "")} &nbsp; ${e(dt)}</div></div>
      <div class="lc-qr">${QR.svg(labelURL(o), 96)}</div>
    </div></div></div>`;
}
