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
    return [...map.entries()].map(([day, events], i) => ({ day, events, index: i + 1 }));
  }

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
        `UID:${e.id}@${W.couple.hashtag.replace('#','').toLowerCase()}`,
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

  window.WX = { W, fmtDate, fmtTime, days, sealSVG, corners, ICON, qrSVG, ics, downloadICS, rsvpLink, mapsEmbed, directions, swatches, countdown, parseISO };
})();
