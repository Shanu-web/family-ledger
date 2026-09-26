/* Shared helpers for the wedding suite. Requires wedding.config.js (window.WEDDING)
   and, for QR rendering, assets/vendor/qrcode-generator.js. */
(function () {
  const W = window.WEDDING;
  const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  const DAYS = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];

  function parseISO(iso) { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); }
  function ordinal(n) { const s = ["th","st","nd","rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }
  function fmtDate(iso, style) {
    const d = parseISO(iso);
    if (style === "long")  return `${DAYS[d.getDay()]}, ${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
    if (style === "day")   return DAYS[d.getDay()];
    if (style === "short") return `${DAYS[d.getDay()].slice(0,3)} ${d.getDate()} ${MONTHS[d.getMonth()].slice(0,3)}`;
    if (style === "dnum")  return String(d.getDate()).padStart(2, "0");
    if (style === "month") return MONTHS[d.getMonth()];
    if (style === "year")  return String(d.getFullYear());
    if (style === "ord")   return `${DAYS[d.getDay()]}, the ${ordinal(d.getDate())} of ${MONTHS[d.getMonth()]}, ${d.getFullYear()}`;
    return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
  }
  function fmtTime(hm) {
    const [h, m] = hm.split(":").map(Number);
    const ap = h >= 12 ? "pm" : "am"; const hh = ((h + 11) % 12) + 1;
    return m ? `${hh}:${String(m).padStart(2,"0")} ${ap}` : `${hh} ${ap}`;
  }
  function days() {
    const map = new Map();
    for (const e of W.events) { if (!map.has(e.day)) map.set(e.day, []); map.get(e.day).push(e); }
    for (const m of (W.meals || [])) { if (!map.has(m.day)) map.set(m.day, []); }
    return [...map.keys()].sort().map((day, i) => ({
      day, index: i + 1,
      events: map.get(day),
      meals: (W.meals || []).filter(m => m.day === day),
      // ceremonies and meals interleaved by start time; meals attached to a ceremony ride with it
      agenda: [...map.get(day).map(e => ({ kind: "event", ...e })), ...(W.meals || []).filter(m => m.day === day && !m.for).map(m => ({ kind: "meal", ...m }))]
                .sort((a, b) => a.start.localeCompare(b.start)),
    }));
  }
  function mealsFor(eventId) { return (W.meals || []).filter(m => m.for === eventId); }

  /* ── SVG motifs ─────────────────────────────────────────────────────── */
  function sealSVG(text) {
    const t = (text || W.couple.monogram).split("·");
    const a = t[0] || "", b = t[1] || "";
    return `<svg viewBox="0 0 120 120" aria-hidden="true">
      <circle cx="60" cy="60" r="57" fill="none" stroke="currentColor" stroke-width="1.2"/>
      <circle cx="60" cy="60" r="51" fill="none" stroke="currentColor" stroke-width=".7" opacity=".7"/>
      <g fill="currentColor"><circle cx="60" cy="6" r="1.6"/><circle cx="60" cy="114" r="1.6"/><circle cx="6" cy="60" r="1.6"/><circle cx="114" cy="60" r="1.6"/></g>
      <text x="43" y="72" text-anchor="middle" font-family="Cormorant Garamond, Georgia, serif" font-size="46" font-weight="400" fill="currentColor">${a}</text>
      <text x="60" y="66" text-anchor="middle" font-family="Cormorant Garamond, Georgia, serif" font-style="italic" font-size="22" fill="currentColor" opacity=".8">&amp;</text>
      <text x="79" y="72" text-anchor="middle" font-family="Cormorant Garamond, Georgia, serif" font-size="46" font-weight="400" fill="currentColor">${b}</text>
    </svg>`;
  }
  // Ganesha, drawn as a single continuous gold line: crown, ears, head, eyes, trunk curling to his left, one tusk, belly, hands.
  function ganeshaSVG() {
    return `<svg viewBox="0 0 120 130" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-label="Shree Ganesha">
      <path d="M46 24 Q60 6 74 24"/><path d="M52 21 Q60 12 68 21"/><circle cx="60" cy="8" r="1.6" fill="currentColor" stroke="none"/>
      <path d="M40 30 Q22 26 16 42 Q12 58 30 62"/><path d="M80 30 Q98 26 104 42 Q108 58 90 62"/>
      <path d="M40 30 Q60 18 80 30 Q92 42 86 58 Q80 70 68 72 L52 72 Q40 70 34 58 Q28 42 40 30 Z"/>
      <path d="M60 33 L60 38"/>
      <path d="M46 47 Q50 43 54 47"/><path d="M66 47 Q70 43 74 47"/>
      <path d="M66 58 L66 78 Q66 98 50 100 Q38 100 40 92 Q42 86 50 90"/>
      <path d="M54 58 L54 72 Q54 78 60 80"/>
      <path d="M72 70 Q84 72 80 82"/>
      <path d="M40 80 Q26 92 30 108 Q36 122 60 122 Q84 122 90 108 Q94 92 80 80"/>
      <path d="M30 96 Q18 100 22 110 Q26 116 34 112"/><path d="M90 96 Q102 100 98 110 Q94 116 86 112"/>
      <path d="M26 110 Q22 106 24 102"/>
      <path d="M96 108 Q100 100 92 96"/><circle cx="97" cy="99" r="3.2"/><path d="M95 97 Q97 94 99 97"/>
      <path d="M34 122 Q60 130 86 122"/>
    </svg>`;
  }
  // Ganesha for the top of a page: the photo in a gold arch (mehrab) when one is set, else the line drawing.
  function ganesha() {
    return W.wedding.ganeshImage
      ? `<span class="arch"><img src="${W.wedding.ganeshImage}" alt="Shree Ganesha"></span>`
      : `<span class="ganesha">${ganeshaSVG()}</span>`;
  }
  // A five-petal lotus, for the midpoints of the ornate frame.
  function lotusSVG() {
    return `<svg viewBox="0 0 40 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linejoin="round" aria-hidden="true">
      <path d="M20 22 Q12 14 20 2 Q28 14 20 22 Z"/>
      <path d="M20 22 Q8 18 8 6 Q17 10 20 22 Z"/><path d="M20 22 Q32 18 32 6 Q23 10 20 22 Z"/>
      <path d="M20 22 Q4 22 2 12 Q12 12 20 22 Z"/><path d="M20 22 Q36 22 38 12 Q28 12 20 22 Z"/>
    </svg>`;
  }
  // A paisley flourish for the corners of the ornate frame.
  function paisleySVG() {
    return `<svg viewBox="0 0 60 60" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" aria-hidden="true">
      <path d="M2 58 V2 H58"/>
      <path d="M8 52 V8 H52" opacity=".55"/>
      <path d="M14 44 Q12 22 30 16 Q44 12 46 24 Q48 36 34 36 Q24 36 26 26 Q28 20 36 22"/>
      <path d="M14 44 Q22 46 30 40"/><path d="M14 44 Q16 36 22 34" opacity=".7"/>
      <circle cx="40" cy="30" r="1.2" fill="currentColor" stroke="none"/>
    </svg>`;
  }
  // The ornate frame: double rule, paisley corners, lotus at each side's midpoint.
  function ornate() {
    return `<span class="orn c tl">${paisleySVG()}</span><span class="orn c tr">${paisleySVG()}</span><span class="orn c bl">${paisleySVG()}</span><span class="orn c br">${paisleySVG()}</span>
      <span class="orn l t">${lotusSVG()}</span><span class="orn l b">${lotusSVG()}</span><span class="orn l ls">${lotusSVG()}</span><span class="orn l rs">${lotusSVG()}</span>`;
  }
  function cornerSVG() {
    return `<svg viewBox="0 0 22 22" fill="none" stroke="currentColor" stroke-width="1"><path d="M1 21 V1 H21"/><path d="M5 21 V5 H21" opacity=".5"/></svg>`;
  }
  function corners() {
    return ["tl","tr","bl","br"].map(p => `<span class="corner ${p}">${cornerSVG()}</span>`).join("");
  }
  const ICON = {
    map: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 21s-6-5.2-6-11a6 6 0 0 1 12 0c0 5.8-6 11-6 11z"/><circle cx="12" cy="10" r="2.2"/></svg>`,
    cal: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="5" width="18" height="16" rx="1"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>`,
    wa:  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 20l1.3-3.9A8 8 0 1 1 8 18.7L4 20z"/><path d="M9.5 9.5c0 3 2 5 5 5l1-1.5-2-1-1 1a4 4 0 0 1-2-2l1-1-1-2-1 .5z" fill="currentColor" stroke="none"/></svg>`,
    phone: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/></svg>`,
    share: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 13v6h14v-6"/></svg>`,
  };

  /* ── The card front, one source for print and web ──────────────────── */
  function cardFront(opts) {
    opts = opts || {}; const one = W.couple.one, two = W.couple.two;
    const r = (n) => opts.animate === false ? "" : ` reveal${n ? " d" + n : ""}`;
    return `
    ${ornate()}
    <div class="${r(0).trim()}">${ganesha()}</div>
    <p class="mantra${r(0)}">${W.wedding.ganesh}</p>
    <p class="eyebrow${r(1)}">${W.wedding.shlokaSub}</p>
    <p class="hosts${r(2)}">${one.parents}</p>
    <p class="invite${r(2)}">${W.copy.inviteLine}</p>
    <h1 class="display names${r(3)}"><em>${one.first}</em><span class="with">${W.copy.withLine}</span><em>${two.first}</em></h1>
    <p class="of${r(3)}">${two.role} of <b>${two.parents}</b></p>
    <div class="rule${r(3)}"><i></i></div>
    <div class="date${r(4)}">
      <span class="dow">${fmtDate(W.wedding.date, "day")}</span>
      <span class="dd">${fmtDate(W.wedding.date, "dnum")}</span>
      <span class="yr">${fmtDate(W.wedding.date, "year")}</span>
      <span class="mo">${fmtDate(W.wedding.date, "month")} · ${fmtTime(W.wedding.time)}</span>
    </div>
    <p class="venue${r(4)}">${W.venue.name}<small>${W.venue.address}</small></p>
    <p class="compliments${r(5)}">${W.copy.complimentsLine}<b>${one.siblings ? one.siblings + " " : ""}${one.familyLine}</b></p>`;
  }

  /* ── QR ─────────────────────────────────────────────────────────────── */
  // Renders an SVG QR (error-correction H so the seal in the centre is safe).
  function qrSVG(url, opts) {
    opts = Object.assign({ fg: "#1C1A18", bg: "#FFFFFF", seal: true, quiet: 2 }, opts || {});
    if (typeof qrcode !== "function") return `<div class="meta">QR library missing</div>`;
    const qr = qrcode(0, opts.seal ? "H" : "M"); qr.addData(url); qr.make();
    const n = qr.getModuleCount(), q = opts.quiet, S = n + q * 2;
    const mid = n / 2, hole = opts.seal ? Math.floor(n * 0.16) : 0;    // ≈ 10% of area, well within H's 30%
    let d = "";
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) {
      if (!qr.isDark(r, c)) continue;
      if (opts.seal && Math.abs(r + .5 - mid) < hole && Math.abs(c + .5 - mid) < hole) continue;
      d += `M${c + q} ${r + q}h1v1h-1z`;
    }
    const sealBox = hole * 2 - 0.4, sx = mid + q - sealBox / 2;
    const seal = opts.seal ? `<g transform="translate(${sx} ${sx}) scale(${sealBox / 120})"><circle cx="60" cy="60" r="60" fill="${opts.bg}"/><g style="color:${opts.fg}">${sealSVG()}</g></g>` : "";
    return `<svg viewBox="0 0 ${S} ${S}" shape-rendering="crispEdges" role="img" aria-label="QR code to the guest page"><rect width="${S}" height="${S}" fill="${opts.bg}"/><path d="${d}" fill="${opts.fg}"/>${seal}</svg>`;
  }

  /* ── Calendar (.ics) ────────────────────────────────────────────────── */
  function icsStamp(iso, hm) { return iso.replace(/-/g, "") + "T" + hm.replace(":", "") + "00"; }
  function ics() {
    const L = ["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//wedding//EN","CALSCALE:GREGORIAN"];
    for (const e of W.events) {
      L.push("BEGIN:VEVENT",
        `UID:${e.id}@${(W.couple.hashtag || W.couple.one.first + W.couple.two.first).replace('#','').toLowerCase()}`,
        `DTSTART:${icsStamp(e.day, e.start)}`, `DTEND:${icsStamp(e.day, e.end)}`,
        `SUMMARY:${e.title} — ${W.couple.one.first} & ${W.couple.two.first}`,
        `LOCATION:${e.where}`, `DESCRIPTION:${(e.kicker + ". Dress: " + e.dress).replace(/,/g, "\\,")}`,
        "END:VEVENT");
    }
    L.push("END:VCALENDAR");
    return L.join("\r\n");
  }
  function downloadICS() {
    const blob = new Blob([ics()], { type: "text/calendar" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = `${W.couple.one.first}-${W.couple.two.first}-wedding.ics`; a.click();
  }
  function hasRSVP() { return !!(W.rsvp && W.rsvp.whatsapp); }
  function contacts() { return (W.contacts || []).filter(c => c.phone); }
  function rsvpLink() { return `https://wa.me/${W.rsvp.whatsapp}?text=${encodeURIComponent(W.rsvp.text)}`; }
  function mapsEmbed() { return `https://www.google.com/maps?q=${encodeURIComponent(W.venue.mapsQuery)}&output=embed`; }
  function directions() { return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(W.venue.mapsQuery)}`; }
  function swatches(p) { return `<span class="swatches">${p.map(c => `<i style="background:${c}"></i>`).join("")}</span>`; }
  function countdown(el) {
    const target = new Date(`${W.wedding.date}T${W.wedding.time}:00`);
    const tick = () => {
      const ms = target - Date.now();
      if (ms <= 0) { el.textContent = "Today"; return; }
      const d = Math.floor(ms / 864e5), h = Math.floor(ms % 864e5 / 36e5), m = Math.floor(ms % 36e5 / 6e4);
      el.innerHTML = `<span class="num">${d}</span> days <span class="num">${h}</span> hrs <span class="num">${m}</span> min`;
    };
    tick(); setInterval(tick, 30000);
  }

  // The address the QR encodes: the configured guestUrl, or, while that is still the placeholder,
  // the page's own origin (so a fresh Netlify deploy is correct without editing anything).
  function guestUrl() {
    if (W.guestUrl && !/example\.com/.test(W.guestUrl)) return W.guestUrl;
    if (typeof location !== "undefined" && /^https?:/.test(location.protocol)) return location.origin + location.pathname.replace(/[^/]*$/, "") + "#schedule";
    return W.guestUrl;
  }
  const city = W.wedding.city || "";
  const cityDot = city ? " · " + city : "";
  window.WX = { hasRSVP, contacts, cardFront, guestUrl, mealsFor, ganesha, ganeshaSVG, lotusSVG, paisleySVG, ornate, city, cityDot, W, fmtDate, fmtTime, days, sealSVG, corners, ICON, qrSVG, ics, downloadICS, rsvpLink, mapsEmbed, directions, swatches, countdown, parseISO };
})();
