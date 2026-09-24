// ─────────────────────────────────────────────────────────────────────────────
//  WEDDING CONFIG — the single source of truth for every page in this folder.
//  Edit this file only; invitation.html, guest.html, magazine.html and
//  hamper.html all read from it. Values marked SAMPLE are placeholders.
// ─────────────────────────────────────────────────────────────────────────────
window.WEDDING = {
  // ── The couple ─────────────────────────────────────────────────────────────
  couple: {
    one: { first: "Shanu", full: "Shanu Choudhary", parents: "Smt. Sunita & Shri Rajesh Choudhary" },          // SAMPLE parents
    two: { first: "Aanya", full: "Aanya Sharma",    parents: "Smt. Meera & Shri Vikram Sharma" },              // SAMPLE partner + parents
    monogram: "S·A",
    hashtag: "#ShanuWedsAanya",
  },

  // ── Headline date & city (the wedding day itself) ──────────────────────────
  wedding: {
    date: "2026-11-28",                 // ISO, local time. Countdown + calendar use this.
    time: "18:00",
    city: "Patna",
    shloka: "शुभ विवाह",                // shown in Devanagari on the cover
    shlokaSub: "With the blessings of our families",
  },

  // ── Public URL of the guest page (this is what the QR encodes) ─────────────
  // Deploy this folder and put its final address here, e.g.
  //   https://shanu-aanya.in/guest.html   or   https://<app-host>/wedding/guest.html
  guestUrl: "https://example.com/wedding/guest.html",   // SAMPLE

  // ── Venue ──────────────────────────────────────────────────────────────────
  venue: {
    name: "The Courtyard at Bailey Road",                // SAMPLE
    address: "Bailey Road, Patna, Bihar 800014",         // SAMPLE
    mapsQuery: "Bailey Road, Patna, Bihar",              // used for the embedded map + directions link
    mapsUrl: "https://maps.google.com/?q=Bailey+Road,+Patna,+Bihar",
    landmark: "Opposite Patna High Court gate, 3 km from Patna Junction",
    parking: "Valet at the main porch. Overflow parking in the east lot.",
  },

  // ── Stay ───────────────────────────────────────────────────────────────────
  stay: {
    hotel: "Hotel Chanakya, Patna",                                  // SAMPLE
    address: "Beer Chand Patel Path, Patna 800001",
    checkIn: "Fri 27 Nov, from 12:00",
    checkOut: "Mon 30 Nov, by 11:00",
    note: "Rooms are booked under ‘Choudhary–Sharma wedding’. Your hamper is waiting in the room.",
    shuttle: "Shuttles leave the hotel lobby 45 minutes before every event.",
  },

  // ── Travel ─────────────────────────────────────────────────────────────────
  travel: [
    { by: "Air",   text: "Jay Prakash Narayan Airport (PAT) is 25 minutes from the hotel. A car with a marigold tag will be waiting at Arrivals." },
    { by: "Rail",  text: "Patna Junction (PNBE) and Rajendra Nagar Terminal (RJPB) are both 15 minutes away." },
    { by: "Road",  text: "NH-22 and NH-31 both bring you to Bailey Road. Share your ETA on WhatsApp and a car will meet you at the hotel." },
  ],

  // ── Contacts (guests will call these; keep them answered!) ────────────────
  contacts: [
    { role: "Guest relations", name: "Rohit", phone: "+91 98765 00001" },   // SAMPLE
    { role: "Travel & stay",   name: "Neha",  phone: "+91 98765 00002" },   // SAMPLE
    { role: "Groom's side",    name: "Amit",  phone: "+91 98765 00003" },   // SAMPLE
    { role: "Bride's side",    name: "Priya", phone: "+91 98765 00004" },   // SAMPLE
  ],
  rsvp: { whatsapp: "919876500001", text: "Hi! RSVP for Shanu & Aanya's wedding — " },   // SAMPLE number, digits only with country code

  // ── The events (the schedule, the dress codes, the menus) ─────────────────
  // Each event: id, day (ISO), start/end (24h), title, kicker, where, dress,
  // palette (colours guests can lean into), note, and menu (array of stations).
  events: [
    {
      id: "haldi", day: "2026-11-27", start: "10:00", end: "12:30",
      title: "Haldi", kicker: "Turmeric & Marigold",
      where: "Poolside Lawn, Hotel Chanakya",
      dress: "Yellows, ivories, whites. Cottons you don’t mind turmeric on.",
      palette: ["#E8B73B", "#F6F1E7", "#F3D98B"],
      note: "Sit on the ground, get your hands messy, and sing. Bring sunglasses; the lawn faces east.",
      menu: [
        { station: "To begin",   items: ["Kesar lassi, aam panna", "Masala chaas"] },
        { station: "Breakfast",  items: ["Litti with baingan chokha & ghee", "Sattu paratha, dahi", "Poha, jalebi, imarti", "Seasonal fruit, cold-pressed juices"] },
      ],
    },
    {
      id: "mehndi", day: "2026-11-27", start: "15:00", end: "18:00",
      title: "Mehndi", kicker: "Henna & Ghazals",
      where: "The Terrace Garden, Hotel Chanakya",
      dress: "Greens and teals, light silhouettes. Flats, please; it is a garden.",
      palette: ["#4F6F52", "#A6B99A", "#F6F1E7"],
      note: "Twelve mehndi artists, a ghazal trio, and a chaat lane. Wear what you can eat chaat in.",
      menu: [
        { station: "Chaat lane",   items: ["Pani puri (five waters)", "Dahi bhalla, papdi chaat", "Aloo tikki with chole", "Bhutte ka kees"] },
        { station: "Tea counter",  items: ["Cutting chai, Kashmiri kahwa", "Filter coffee", "Nankhatai, mathri, shakkarpara"] },
        { station: "Sweet",        items: ["Gaya tilkut, Silao khaja", "Malai kulfi on stick"] },
      ],
    },
    {
      id: "sangeet", day: "2026-11-27", start: "19:30", end: "23:30",
      title: "Sangeet", kicker: "The Night We Dance",
      where: "The Grand Ballroom, Hotel Chanakya",
      dress: "Jewel tones and shimmer: emerald, sapphire, wine. Dance-proof footwear.",
      palette: ["#1F2F5C", "#6E1E2B", "#B8935A"],
      note: "Performances start sharp at 20:30. Family sets first, then the floor is yours till the DJ is thrown out.",
      menu: [
        { station: "Passed around", items: ["Galouti on ulte tawa parathas", "Paneer tikka, hara bhara kebab", "Amritsari fish, chicken malai tikka", "Dahi ke kebab"] },
        { station: "Live",          items: ["Pasta & risotto bar", "Dim sum basket (veg / chicken)", "Tandoor: naan, kulcha, roti"] },
        { station: "Mains",         items: ["Dal makhani, paneer lababdar", "Murgh musallam, mutton rogan josh", "Subz miloni, jeera rice, biryani (veg / gosht)"] },
        { station: "Dessert",       items: ["Gulab jamun with rabri", "Moong dal halwa", "Tiramisu, fruit tart", "Paan counter"] },
        { station: "Bar",           items: ["Signature: Marigold Sour, Kumkum Negroni", "Wines, whiskies, gin & tonic bar", "Mocktails: jamun spritz, kokum cooler"] },
      ],
    },
    {
      id: "wedding", day: "2026-11-28", start: "18:00", end: "23:59",
      title: "The Wedding", kicker: "Baraat · Jaimala · Pheras",
      where: "The Courtyard at Bailey Road",
      dress: "Traditional. Reds, golds, ivories. Silks, bandhgalas, sherwanis, saris, lehengas.",
      palette: ["#6E1E2B", "#B8935A", "#F6F1E7"],
      note: "Baraat leaves the hotel at 17:30 with the band. Jaimala at 19:30. Pheras at 21:30 under the courtyard mandap; sit with us, it is the heart of the evening.",
      timeline: [
        { at: "17:30", what: "Baraat departs the hotel" },
        { at: "18:00", what: "Baraat welcome (swagat) at the venue gate" },
        { at: "19:30", what: "Jaimala" },
        { at: "20:00", what: "Dinner opens" },
        { at: "21:30", what: "Pheras at the mandap" },
        { at: "23:30", what: "Vidaai" },
      ],
      menu: [
        { station: "Welcome",   items: ["Thandai, rose sherbet", "Badam milk"] },
        { station: "Starters",  items: ["Tandoori broccoli, malai soya chaap", "Mutton seekh, murgh tikka", "Corn & cheese balls for the little ones"] },
        { station: "Regional",  items: ["Bihari thali: litti chokha, dal pitha, ghugni", "Awadhi: nihari, sheermal", "South: appam & stew, Chettinad chicken"] },
        { station: "Mains",     items: ["Paneer butter masala, kadhai vegetables", "Dal tadka, dal makhani", "Chicken korma, mutton kosha", "Assorted breads, pulao, biryani"] },
        { station: "Dessert",   items: ["Anarsa, thekua, khaja", "Kesar phirni, rasmalai", "Ice cream trolley", "Meetha paan"] },
      ],
    },
    {
      id: "reception", day: "2026-11-29", start: "19:00", end: "23:00",
      title: "Reception", kicker: "One Last Evening Together",
      where: "The Lawns, Hotel Chanakya",
      dress: "Evening formal. Black tie, gowns, dark suits, drape saris.",
      palette: ["#1C1A18", "#B8935A", "#C9A4A0"],
      note: "A slow evening: a string quartet, a long dinner, a few speeches, and the couple at the door to say thank you to every one of you.",
      menu: [
        { station: "Canapés",  items: ["Beetroot & goat cheese tarts", "Smoked salmon blinis", "Truffle mushroom vol-au-vents", "Mini vada pav sliders"] },
        { station: "Live",     items: ["Carving station: roast lamb, roast chicken", "Wood-fired pizza", "Sushi & maki (veg / fish)", "Teppanyaki noodles"] },
        { station: "Mains",    items: ["Lasagne (veg / meat), grilled fish in lemon butter", "Thai green & red curry, jasmine rice", "Dal, paneer, seasonal sabzi, breads"] },
        { station: "Dessert",  items: ["Wedding cake", "Crème brûlée, chocolate fondant", "Kulfi falooda, jalebi with rabri"] },
        { station: "Bar",      items: ["Champagne toast at 21:00", "Full bar, single malts", "Espresso martini bar"] },
      ],
    },
  ],

  // ── Words on the invitation & magazine ─────────────────────────────────────
  copy: {
    inviteLine: "request the pleasure of your company at the wedding of their children",
    welcomeLetter: [
      "Thank you for travelling to be with us. Some of you have crossed the city, some of you have crossed oceans, and all of you have crossed something to be here.",
      "This little book is your companion for the three days: where to be, when, what to wear, and what you will eat. Keep it in your bag. Tear pages out. Spill chai on it.",
      "The only thing we ask is that you put your phone down for the pheras. We will have photographers for that; we want your eyes, not your lens.",
    ],
    story: [
      "We met in the queue for the wrong counter at Patna Junction in 2019. Both of us had been sent to the wrong window, both of us were annoyed, and one of us was smug about being right. (It was Aanya.)",
      "Seven years, two cities, one very patient set of parents on each side, and one proposal on the terrace where the mehndi will be, and here we are.",
      "This is the wedding we always wanted: at home, in Patna, with every one of you.",
    ],
    giftNote: "Your presence is the present. If you insist, the couple’s blessing box will be at the reception; please, no boxed gifts.",
    thankYou: "Thank you for being the best part of our story.",
  },
};
