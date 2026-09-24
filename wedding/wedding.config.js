// ─────────────────────────────────────────────────────────────────────────────
//  WEDDING CONFIG — the single source of truth for every page in this folder.
//  Edit this file only; invitation.html, guest.html, magazine.html and
//  hamper.html all read from it. Anything marked TODO still needs your input.
// ─────────────────────────────────────────────────────────────────────────────

// The venue. Every page, card and QR reads these two.
const VENUE_NAME = "Sree Raaga Resorts";
const VENUE_CITY = "Bengaluru";

window.WEDDING = {
  // ── Look ───────────────────────────────────────────────────────────────────
  theme: "midnight",        // "midnight" (indigo & champagne) · "kumkum" (red & gold) · "forest" (green & brass)
                            // preview any of them by adding ?palette=forest to a page URL

  // ── The couple ─────────────────────────────────────────────────────────────
  couple: {
    one: {                                    // the groom
      first: "Shanu", full: "Shanu Choudhary",
      parents: "Mr. Sudhansu Kumar Choudhary & Mrs. Anita Choudhary",
      siblings: "Gaurav Choudhary",
      familyLine: "and the entire Choudhary family",
      familyName: "The Choudharys",
      address: "Near Gupta Medical, Kahalgaon 813203, Bihar",
      role: "son",
    },
    two: {                                    // the bride
      first: "Sonali", full: "Sonali Mohan",
      parents: "Mr. Vijay Mohan & Late Mrs. Shobha Mohan",
      siblings: "Vikash Mohan",
      familyLine: "and the entire Mohan family",
      familyName: "The Mohans",
      address: "501-A1, Prasad Nagar, Wadgaon Sheri, Pune 411014, Maharashtra",
      role: "daughter",
    },
    monogram: "S·S",
    hashtag: "#ShanuWedsSonali",
  },

  // ── Headline date & place (the wedding evening: baraat, jaimala, reception) ─
  wedding: {
    date: "2026-12-11",                 // ISO, local time. Countdown + calendar use this.
    time: "19:00",
    city: VENUE_CITY,
    shloka: "शुभ विवाह",
    shlokaSub: "With the blessings of our families",
  },

  // ── Public URL of the guest page (this is what the QR encodes) ─────────────
  // TODO: deploy this folder and put its final address here, e.g.
  //   https://<app-host>/wedding/guest.html
  guestUrl: "https://example.com/wedding/guest.html",

  // ── Venue ──────────────────────────────────────────────────────────────────
  venue: {
    name: VENUE_NAME,
    address: "No. 1246, Budigere Bypass Road, Devanahalli, Bengaluru, Karnataka 562129",
    mapsQuery: "Sree Raaga Resorts, Budigere Bypass Road, Devanahalli, Bengaluru",   // used for the embedded map + directions link
    landmark: "Off Budigere Cross on the airport side of the city, 25 minutes from Kempegowda International Airport (BLR).",
    parking: "Free parking on the property; valet at the main porch on the wedding evening.",
  },

  // ── Stay ───────────────────────────────────────────────────────────────────
  stay: {
    hotel: "Sree Raaga Resorts, on the property",
    address: "Rooms, villas and row houses across the resort’s five acres. You walk to every event.",
    checkIn: "Thu 10 Dec, from the morning",
    checkOut: "Sat 12 Dec, after the bidai and breakfast",
    note: "Rooms are booked under ‘Choudhary–Mohan wedding’. Your hamper is waiting in the room. December evenings in Bengaluru drop to about 15 °C; bring a shawl for the sangeet lawns and the bidai.",
    shuttle: "Everything happens on the property, so there are no shuttles. Airport and station pick-ups are arranged on request.",
  },

  // ── Travel ─────────────────────────────────────────────────────────────────
  travel: [
    { by: "Air",   text: "Kempegowda International Airport (BLR) is 25 minutes away, the closest a Bengaluru venue can be. Send your flight number on WhatsApp and a car with a marigold tag will be at Arrivals." },
    { by: "Rail",  text: "KSR Bengaluru City (SBC) and Yesvantpur (YPR) are about 1¼ hours by road; Yelahanka (YNK) is closer, about 40 minutes. Share your train and coach and a car will be waiting." },
    { by: "Road",  text: "Take NH-44 towards the airport, exit for Budigere Cross, then Budigere Bypass Road. Pin: search ‘Sree Raaga Resorts’ in Google Maps, or scan the code on your card." },
  ],

  // ── Contacts (guests will call these; keep them answered!) ────────────────
  contacts: [
    { role: "Groom’s side",    name: "Gaurav Choudhary", phone: "+91 00000 00000" },   // TODO number
    { role: "Bride’s side",    name: "Vikash Mohan",     phone: "+91 00000 00000" },   // TODO number
    { role: "Guest relations", name: "To be named",      phone: "+91 00000 00000" },   // TODO
    { role: "Travel & stay",   name: "To be named",      phone: "+91 00000 00000" },   // TODO
  ],
  rsvp: { whatsapp: "910000000000", text: "Hi! RSVP for Shanu & Sonali’s wedding — " },   // TODO digits only, with country code

  // ── The events (the schedule, the dress codes, the menus) ─────────────────
  events: [
    {
      id: "tilak", day: "2026-12-10", start: "13:30", end: "16:00",
      title: "Tilak", kicker: "The First Blessing",
      where: VENUE_NAME,
      dress: "Traditional and light: ivories, creams, pastel silks. Kurtas, saris, suits.",
      palette: ["#F6F1E7", "#D9C08F", "#6E1E2B"],
      note: "The bride’s family welcomes the groom with the tilak, the blessing that opens the wedding. Guests arrive through the morning; lunch follows the ceremony.",
      menu: [
        { station: "Welcome",  items: ["Kesar lassi, aam panna", "Nimbu pani, masala chaas"] },
        { station: "Lunch",    items: ["Litti with baingan chokha & ghee", "Dal pitha, ghugni", "Paneer lababdar, aloo dum, kadhi", "Puri, jeera rice, salad, papad"] },
        { station: "Sweet",    items: ["Anarsa, thekua", "Kesar phirni"] },
      ],
    },
    {
      id: "sangeet", day: "2026-12-10", start: "18:00", end: "23:30",
      title: "Sangeet & Engagement", kicker: "Rings, Then Dancing",
      where: VENUE_NAME,
      dress: "Jewel tones and shimmer: emerald, sapphire, wine. Dance-proof footwear.",
      palette: ["#1F2F5C", "#6E1E2B", "#B8935A"],
      note: "The rings at 7. Family performances from 8, sharp. After that the floor is yours till the DJ is thrown out.",
      timeline: [
        { at: "18:00", what: "Doors, drinks and chaat" },
        { at: "19:00", what: "Engagement: the rings" },
        { at: "20:00", what: "Sangeet performances" },
        { at: "21:30", what: "Dinner opens; the floor stays open" },
      ],
      menu: [
        { station: "Passed around", items: ["Galouti on ulte tawa parathas", "Paneer tikka, hara bhara kebab", "Amritsari fish, chicken malai tikka", "Dahi ke kebab"] },
        { station: "Chaat lane",    items: ["Pani puri (five waters)", "Dahi bhalla, papdi chaat", "Aloo tikki with chole"] },
        { station: "Live",          items: ["Pasta & risotto bar", "Dim sum basket (veg / chicken)", "Tandoor: naan, kulcha, roti"] },
        { station: "Mains",         items: ["Dal makhani, paneer lababdar", "Murgh musallam, mutton rogan josh", "Subz miloni, jeera rice, biryani (veg / gosht)"] },
        { station: "Dessert",       items: ["Gulab jamun with rabri", "Moong dal halwa", "Tiramisu, fruit tart", "Paan counter"] },
        { station: "Bar",           items: ["Signature: Marigold Sour, Kumkum Negroni", "Wines, whiskies, gin & tonic bar", "Mocktails: jamun spritz, kokum cooler"] },
      ],
    },
    {
      id: "haldi", day: "2026-12-11", start: "11:00", end: "13:30",
      title: "Haldi", kicker: "Turmeric & Marigold",
      where: VENUE_NAME,
      dress: "Yellows, ivories, whites. Cottons you don’t mind turmeric on.",
      palette: ["#E8B73B", "#F6F1E7", "#F3D98B"],
      note: "Sit on the ground, get your hands messy, and sing. Brunch runs alongside; bring sunglasses.",
      menu: [
        { station: "To begin",   items: ["Kesar lassi, aam panna", "Cutting chai, filter coffee"] },
        { station: "Brunch",     items: ["Sattu paratha, dahi", "Poha, jalebi, imarti", "Chhole bhature", "Seasonal fruit, cold-pressed juices"] },
        { station: "Sweet",      items: ["Gaya tilkut, Silao khaja", "Malai kulfi on stick"] },
      ],
    },
    {
      id: "wedding", day: "2026-12-11", start: "19:00", end: "23:59",
      title: "The Wedding", kicker: "Baraat · Jaimala · Reception",
      where: VENUE_NAME,
      dress: "Traditional. Reds, golds, ivories. Silks, bandhgalas, sherwanis, saris, lehengas.",
      palette: ["#6E1E2B", "#B8935A", "#F6F1E7"],
      note: "The baraat arrives at 7 with the band; come early if you are dancing in it. Jaimala at 8, and the reception and dinner run from 8 onwards. The pheras follow later in the night; sit with us for them, it is the heart of the evening.",
      timeline: [
        { at: "19:00", what: "Baraat arrives; swagat at the gate" },
        { at: "20:00", what: "Jaimala" },
        { at: "20:00", what: "Reception and dinner, onwards" },
        { at: "Late",  what: "Pheras at the mandap" },
      ],
      menu: [
        { station: "Welcome",   items: ["Thandai, rose sherbet", "Badam milk"] },
        { station: "Starters",  items: ["Tandoori broccoli, malai soya chaap", "Mutton seekh, murgh tikka", "Corn & cheese balls for the little ones"] },
        { station: "Regional",  items: ["Bihari thali: litti chokha, dal pitha, ghugni", "Maharashtrian: puran poli, bharli vangi, masale bhaat", "Awadhi: nihari, sheermal"] },
        { station: "Mains",     items: ["Paneer butter masala, kadhai vegetables", "Dal tadka, dal makhani", "Chicken korma, mutton kosha", "Assorted breads, pulao, biryani"] },
        { station: "Live",      items: ["Carving station: roast lamb, roast chicken", "Wood-fired pizza", "Teppanyaki noodles"] },
        { station: "Dessert",   items: ["Wedding cake", "Anarsa, thekua, khaja", "Kesar phirni, rasmalai", "Ice cream trolley, meetha paan"] },
      ],
    },
    {
      id: "bidai", day: "2026-12-12", start: "05:00", end: "06:30",
      title: "Bidai", kicker: "Before Sunrise",
      where: VENUE_NAME,
      dress: "Whatever you slept in, plus a shawl. It will be cold and it will be early.",
      palette: ["#C9A4A0", "#F6F1E7", "#B8935A"],
      note: "Before the sun is up, the bride and groom leave together. Bring a handkerchief. Chai and breakfast are laid out for everyone who stayed up, and for everyone who didn’t.",
      menu: [
        { station: "Before dawn", items: ["Adrak chai, kahwa, filter coffee", "Poha, upma", "Puri sabzi", "Fruit, biscuits, tilkut for the road"] },
      ],
    },
  ],

  // ── Words on the invitation & magazine ─────────────────────────────────────
  copy: {
    inviteLine: "request the pleasure of your company at the wedding of their children",
    welcomeLetter: [
      "Thank you for travelling to be with us. Some of you have crossed the city, some of you have crossed the country, and all of you have crossed something to be here.",
      "This little book is your companion for the three days: where to be, when, what to wear, and what you will eat. Keep it in your bag. Tear pages out. Spill chai on it.",
      "The only thing we ask is that you put your phone down for the pheras. We will have photographers for that; we want your eyes, not your lens.",
    ],
    story: [   // TODO: replace with your own story in your own words
      "Two families, two ends of the country: the Choudharys of Kahalgaon on the banks of the Ganga, and the Mohans of Pune. It took a while for the two to find each other, and no time at all to agree.",
      "Between the tilak on the 10th and the bidai before dawn on the 12th, we get two days to bring everyone we love into one place. That, more than anything, is what this wedding is for.",
      "Thank you for making the journey. We will spend the rest of our lives making it worth it.",
    ],
    giftNote: "Your presence is the present. If you insist, the blessing box will be at the reception; please, no boxed gifts.",
    thankYou: "Thank you for being the best part of our story.",
  },
};
