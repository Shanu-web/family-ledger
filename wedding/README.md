# The wedding suite — Shanu & Sonali

Four pieces, one design system, one config file. Everything a guest touches
looks like it came from the same hand: the invitation they receive, the page
the QR opens, the magazine on the bed, and the hamper it leans against.

| # | Piece | File | Output |
|---|-------|------|--------|
| 00 | **The website** | `index.html` | The public site: a sealed envelope you tap, the card slides out in 3D and tilts with your phone, marigold petals, countdown tiles, the three days, venue map, menus, stay, contacts, RSVP. `assets/og.jpg` is the WhatsApp link preview. |
| 01 | **The invitation** | `invitation.html` | Digital (share the link) and a two-sided **A5 card** when printed |
| 02 | **The guest page** | `guest.html` | What the **QR opens**: map, countdown, schedule, dress codes, menus, stay, travel, contacts, RSVP, add-to-calendar |
| 03 | **The magazine** | `magazine.html` | **16-page A5 booklet**, saddle-stitched: welcome, families, story, schedule, events, menus, map, little things |
| 04 | **The room hamper** | `hamper.html` | Three tiers, contents matrix, packaging, budget, 10-step logistics, plus **printable A6 note cards and tags** |
| — | Suite index | `suite.html` | Internal: links to every piece, shows the palette and type |

Open `suite.html` for the internal index, or run the app and visit `/wedding/` for the public site.

## 1. Edit one file

Everything reads from **`wedding.config.js`**: names, parents, date, venue,
hotel, travel, contacts, WhatsApp RSVP number, the five events (times, venue,
dress code, colour palette, note, menu) and the copy (welcome letter, story,
gift note). Values marked `SAMPLE` are placeholders; change them and every
page updates. No build step.

What is already in: the venue, both families with parents, brothers and home addresses,
the monogram S·S, the hashtag, and the three days (10 Dec tilak 1:30 pm and
sangeet + engagement 6 pm; 11 Dec haldi 11 am and baraat 7 pm with jaimala and
reception from 8 pm; 12 Dec bidai before sunrise).

Still marked `TODO` in the config, in order of urgency:

1. `guestUrl` — the public address of `guest.html`. **This is what every QR encodes.**
2. `rsvp.whatsapp` and the four contact numbers (Gaurav and Vikash are named; numbers are zeros).
3. `copy.story` — three short paragraphs in your own words.
4. `theme` — which of the three palettes (below).

Venue is set: Sree Raaga Resorts, No. 1246, Budigere Bypass Road, Devanahalli,
Bengaluru 562129 (25 minutes from BLR airport). The resort is booked
exclusively, 55 rooms, 10–12 December, and the menus on every page are the
resort's own (all vegetarian). Counts, counters, staffing and the quotation
live in `planner/catering-and-booking.md`, never on a guest page.

The card follows the traditional order: Shree Ganeshaya Namah at the top,
the groom's parents as hosts, "the wedding ceremony of their son Shanu with
Sonali, daughter of …", the date and venue, and "with best compliments" from
Gaurav and the Choudhary family. The front is a deep navy card in gold with
an ornate frame (paisley corners, lotus at each side); the back is ivory
with the programme, the QR and both families' addresses.

## 2. Publish the guest page (so the QR works)

The folder is plain static HTML. Two easy routes:

- **This app.** `app.py` mounts the folder at `/wedding`, so on the deployed
  host the guest page is `https://<your-host>/wedding/guest.html`.
- **Netlify drag-and-drop.** Run `bash wedding/tools/build_site.sh` and drop
  the zip it makes onto app.netlify.com/drop. The site root is the invitation;
  `guest.html` and `magazine.html` sit beside it. The zip leaves out the
  planner notes, the hamper page and the tools, so nothing internal goes public.
  The QR encodes the deployed address automatically until `guestUrl` is set.

Put the final URL in `guestUrl`, reload the pages, and the QR on the
invitation back, the magazine back cover and the hamper note card all point
there. For the printer, export a vector QR:

```bash
pip install segno
python3 wedding/tools/make_qr.py    # writes assets/qr-guest.svg/.png and qr-directions.svg/.png
```

Test the QR on a phone **before** the print run.

## 3. Print specs (hand these to the printer)

**Invitation card** — open `invitation.html`, print to PDF (⌘/Ctrl-P, "Save as
PDF", no margins, background graphics on). You get two A5 pages: front and back.

- Size A5 (148 × 210 mm), printed both sides. Add 3 mm bleed; the design has an 11 mm safe margin.
- Stock: 350 gsm uncoated ivory cotton or wood-free board. Never gloss. The front prints as a solid navy flood; ask for a proof.
- Upgrade: print the front on navy board and hot-foil the gold (Ganesha, frame, names) instead of printing it; a gold-lined C5 envelope with names in gold ink.

**Magazine** — open `magazine.html`, print to PDF the same way. You get 16
single A5 pages in reading order; the printer imposes them for saddle-stitch.

- A5 portrait, 16 pages (multiple of four; if you add pages, add four).
- Cover: 300 gsm with soft-touch matte lamination; optional gold foil on the seal.
- Inside: 150–170 gsm uncoated or matte art paper. Two staples.
- Colour: the cover is solid kumkum with a gold lattice; ask for a proof, the red must not drift orange.

**Hamper printables** — open `hamper.html`, print to PDF: sheet 1 has two A6
note cards, sheet 2 has eight 90 × 55 mm tags. Note cards on 300 gsm ivory;
tags on 350 gsm kumkum board (or print the kumkum, and punch a 4 mm hole
where the circle is). Cut on the dashed lines.

## 4. The design system (why it looks the way it does)

The rule: one palette, two typefaces, three motifs, nothing else anywhere.

- **Palette.** Three to choose from, set once with `theme` in the config
  (preview any page with `?palette=forest` etc.). Each is one strong colour,
  one metallic, a warm paper, and a single accent used at most once per page.
  - `midnight` (default) · **Midnight & Champagne**: deep indigo `#1B2A41`, champagne gold `#B99A63`, warm white `#F4EFE6`, marigold accent.
  - `forest` · **Forest & Brass**: deep green `#1E3A34`, brass `#B08D57`, bone white `#F3EFE7`, terracotta accent.
  - `kumkum` · **Kumkum & Ivory**: sindoor red `#6E1E2B`, old gold `#B8935A`, ivory `#F6F1E7`, rose accent. The classic, done quietly.
  Each event also has a three-swatch palette for its dress code; that is for
  the guests' clothes and does not leak into the page design.
- **Type.** *Cormorant Garamond* for display (light weight for names, italic
  for warmth, never bold) and *Karla* for everything small (eyebrows are 11 px
  uppercase tracked at 0.22 em). *Tiro Devanagari Hindi* only for the shloka.
- **Motifs.** A jaali lattice (never above 30 % opacity), a hairline rule with a
  diamond, and the monogram seal, which also sits in the centre of the QR.

All tokens live in `assets/wedding.css`; shared helpers (date formatting,
QR rendering, the `.ics` calendar export, the seal SVG) in `assets/wedding.js`.
The QR is drawn client-side by the vendored MIT library
`assets/vendor/qrcode-generator.js`, at error-correction level H so the seal
in the middle is safe.

## 5. The event manager's timeline

| When | Do |
|------|----|
| T‑10 weeks | Lock names, dates, venues, hotel block, and the five events in `wedding.config.js`. Register the domain or decide on the app URL. |
| T‑9 weeks | Publish the guest page, set `guestUrl`, test the QR on three phones. Send the **digital invitation** link to the long-distance list first. |
| T‑8 weeks | Print proofs of the card and the magazine cover. Sign off the red. Order the hamper's handmade pieces (Madhubani, Bhagalpuri stoles, diyas). |
| T‑6 weeks | Print run: cards, envelopes, magazine, note cards, tags, itinerary cards. Hand-deliver / courier the physical cards. |
| T‑4 weeks | RSVPs closed on WhatsApp. Room list and hamper tiers finalised. Menu tasting; update the menus in the config if anything changes (the guest page updates instantly, the magazine is already printed, so lock menus before T‑6). |
| T‑1 week | Shelf-stable hamper items in. Shuttle timings confirmed with the hotel; the guest page says "45 minutes before each event", keep it true. |
| T‑2 days | Hamper assembly line at the hotel. Magazines into the baskets. |
| Check-in day | Baskets placed two hours before the first arrival. Contacts on the guest page are live and answered. |

## 6. Files

```
wedding/
├── index.html            landing: the four pieces, palette, type
├── invitation.html       digital invite + A5 print (front/back)
├── guest.html            QR landing: map, schedule, menus, stay, contacts
├── magazine.html         16-page A5 booklet (spreads on screen, pages in print)
├── hamper.html           hamper plan + printable note cards and tags (A4)
├── wedding.config.js     ← the only file you need to edit
├── assets/
│   ├── wedding.css       design tokens, motifs, components
│   ├── wedding.js        helpers: dates, QR, .ics, seal
│   ├── qr-guest.*        print-ready QR exports (regenerate with tools/make_qr.py)
│   └── vendor/qrcode-generator.js   MIT, Kazuhiko Arase
├── planner/catering-and-booking.md   counts, counters, rates — planners only
└── tools/make_qr.py      vector QR export for the printer
```
