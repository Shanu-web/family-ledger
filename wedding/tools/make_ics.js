// Writes wedding/shanu-sonali.ics from wedding.config.js (run by build_site.sh; also committed).
const fs = require("fs"), path = require("path");
global.window = {}; require(path.join(__dirname, "..", "wedding.config.js")); const W = window.WEDDING;
const stamp = (iso, hm) => iso.replace(/-/g, "") + "T" + hm.replace(":", "") + "00";
const esc = s => String(s).replace(/\\/g, "\\\\").replace(/;/g, "\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
const fold = l => l.match(/.{1,70}/g).join("\r\n ");
const L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Shanu & Sonali//Wedding//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
  `X-WR-CALNAME:${esc(W.couple.one.first + " & " + W.couple.two.first)}`, "X-WR-TIMEZONE:Asia/Kolkata",
  "BEGIN:VTIMEZONE", "TZID:Asia/Kolkata", "BEGIN:STANDARD", "DTSTART:19700101T000000", "TZOFFSETFROM:+0530", "TZOFFSETTO:+0530", "TZNAME:IST", "END:STANDARD", "END:VTIMEZONE"];
const now = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z/, "Z");
for (const e of W.events) {
  L.push("BEGIN:VEVENT", `UID:${e.id}-${W.wedding.date}@shanukisonali`, `DTSTAMP:${now}`,
    `DTSTART;TZID=Asia/Kolkata:${stamp(e.day, e.start)}`, `DTEND;TZID=Asia/Kolkata:${stamp(e.day, e.end)}`,
    fold(`SUMMARY:${esc(e.title + " · " + W.couple.one.first + " & " + W.couple.two.first)}`),
    fold(`LOCATION:${esc(W.venue.name + ", " + W.venue.address)}`),
    fold(`DESCRIPTION:${esc(e.kicker + ". " + e.note + " Dress: " + e.dress)}`),
    "END:VEVENT");
}
L.push("END:VCALENDAR");
fs.writeFileSync(path.join(__dirname, "..", "shanu-sonali.ics"), L.join("\r\n") + "\r\n");
console.log("wrote shanu-sonali.ics with", W.events.length, "events");
