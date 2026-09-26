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
    hashtag: "#ShanuKiSonali",
    tagline: "Two names. One aesthetic.",          // the line under the names: website hero, card back, magazine back cover
    taglineSub: "The Shanu & Sonali Story",
  },

  // ── Headline date & place (the wedding evening: baraat, jaimala, reception) ─
  wedding: {
    date: "2026-12-11",                 // ISO, local time. Countdown + calendar use this.
    time: "19:00",
    city: VENUE_CITY,
    ganesh: "॥ श्री गणेशाय नमः ॥",
    ganeshImage: "assets/ganesha.jpg",   // the photo at the top of the card; set to "" to use the line drawing instead
    shloka: "शुभ विवाह",
    shlokaSub: "With the blessings of the Almighty and our elders",
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
    hotel: "You are staying at Sree Raaga Resorts, right where the celebrations are.",
    address: "For three days the whole resort is ours: every room, the lawns, the banquet hall and the dining hall. Every ceremony is a short walk from your room.",
    checkIn: "Thu 10 Dec, from the morning (flexible to your arrival)",
    checkOut: "Sat 12 Dec, flexible to your train or flight",
    note: "Your room will be ready at reception when you arrive. December evenings in Bengaluru are about 15 °C.",
    shuttle: "Every ceremony is on the property, a short walk from your room.",
  },

  // ── Travel ─────────────────────────────────────────────────────────────────
  travel: [
    { by: "Air",   text: "Kempegowda International Airport (BLR) is about 25 minutes away. Leave the airport towards Budigere Cross; the resort is on Budigere Bypass Road, Devanahalli." },
    { by: "Rail",  text: "Yelahanka (YNK) is the closest station, about 40 minutes by road. KSR Bengaluru City (SBC) and Yesvantpur (YPR) are about 1¼ hours." },
    { by: "Road",  text: "From the city, take NH-44 towards the airport, exit at Budigere Cross, then Budigere Bypass Road. Search ‘Sree Raaga Resorts’ in Google Maps or use the directions button." },
  ],

  // ── Contacts (guests will call these; keep them answered!) ────────────────
  // Contacts without a phone number are hidden everywhere until you add one.
  contacts: [
    { role: "Groom’s side",    name: "Gaurav Choudhary", phone: "" },
    { role: "Bride’s side",    name: "Vikash Mohan",     phone: "" },
  ],
  // RSVP on WhatsApp: leave whatsapp "" and every RSVP button and bar stays hidden.
  // When ready: digits only with country code, e.g. "919876543210".
  rsvp: { whatsapp: "", text: "Hi! RSVP for Shanu & Sonali’s wedding (#ShanuKiShehnai) — " },

  // ── The events (the schedule, the dress codes, the menus) ─────────────────
  events: [
    {
      id: "tilak", day: "2026-12-10", start: "13:30", end: "15:30",
      title: "Tilak", kicker: "The First Blessing",
      where: VENUE_NAME,
      dress: "Traditional and light: ivories, creams, pastel silks. Kurtas, saris, suits.",
      palette: ["#F6F1E7", "#D9C08F", "#6E1E2B"],
      note: "The bride’s family welcomes the groom with the tilak, the blessing that opens the wedding. A fruit punch is waiting as you arrive; lunch runs alongside the ceremony.",
    },
    {
      id: "sangeet", day: "2026-12-10", start: "18:00", end: "23:00",
      title: "Sangeet & Engagement", kicker: "Rings, Then Dancing",
      where: VENUE_NAME,
      dress: "Jewel tones and shimmer: emerald, sapphire, wine. Dance-proof footwear.",
      palette: ["#1F2F5C", "#6E1E2B", "#B8935A"],
      note: "The rings at 7. Family performances from 8, sharp. Starters go round from 6:30 and dinner is served from 7:30, so eat between dances.",
      timeline: [
        { at: "18:00", what: "Doors and fresh juices" },
        { at: "18:30", what: "Starters and the chaat counter open" },
        { at: "19:00", what: "Engagement: the rings" },
        { at: "19:30", what: "Dinner counters open, till 10" },
        { at: "20:00", what: "Sangeet performances, then the floor is yours" },
      ],
    },
    {
      id: "haldi", day: "2026-12-11", start: "11:00", end: "13:00",
      title: "Haldi", kicker: "Turmeric & Marigold",
      where: VENUE_NAME,
      dress: "Yellows, ivories, whites. Cottons you don’t mind turmeric on.",
      palette: ["#E8B73B", "#F6F1E7", "#F3D98B"],
      note: "Sit on the ground, get your hands messy, and sing. Mint mojitos, watermelon juice and cocktail samosas go round; lunch follows at 1.",
    },
    {
      id: "wedding", day: "2026-12-11", start: "19:00", end: "23:59",
      title: "The Wedding", kicker: "Baraat · Jaimala · Reception",
      where: VENUE_NAME,
      dress: "Traditional. Reds, golds, ivories. Silks, bandhgalas, sherwanis, saris, lehengas.",
      palette: ["#6E1E2B", "#B8935A", "#F6F1E7"],
      note: "The baraat arrives at 7 with the band; come early if you are dancing in it. Jaimala at 8, and the reception runs from 8 onwards with dinner served across eighteen counters till 11:30. The pheras follow later in the night; sit with us for them, it is the heart of the evening.",
      timeline: [
        { at: "19:00", what: "Baraat arrives; swagat at the gate. Dinner counters open" },
        { at: "20:00", what: "Jaimala" },
        { at: "20:00", what: "Reception, onwards" },
        { at: "23:30", what: "Dinner service closes" },
        { at: "Late",  what: "Pheras at the mandap" },
      ],
    },
    {
      id: "bidai", day: "2026-12-12", start: "05:00", end: "06:30",
      title: "Bidai", kicker: "Before Sunrise",
      where: VENUE_NAME,
      dress: "Whatever you slept in. It will be early, and about 15 °C.",
      palette: ["#C9A4A0", "#F6F1E7", "#B8935A"],
      note: "Before the sun is up, the bride and groom leave together. Bring a handkerchief. Tea and coffee are on all night; breakfast is laid out from 8 for everyone who stayed up, and for everyone who didn’t.",
    },
  ],

  // ── Meals (from the resort’s menu, updated 21 September 2026). Entirely vegetarian. ──
  // Each meal: day, start/end, title, optional `for` (the event it belongs to), stations.
  vegetarian: true,
  meals: [
    { id: "lunch-10", day: "2026-12-10", start: "12:30", end: "15:00", title: "Lunch", for: "tilak", stations: [
      { station: "As you arrive", items: ["Fruit punch"] },
      { station: "Beverage",      items: ["Jaljeera"] },
      { station: "Main course",   items: ["Paneer lababdar", "Bharwa bhindi", "Kum palak (mushroom)", "Dal tadka", "Jeera rice, steamed rice"] },
      { station: "Breads",        items: ["Phulka", "Puri"] },
      { station: "Desserts",      items: ["Gulab jamun", "Rasgulla"] },
      { station: "On the side",   items: ["Papad, pickle, curd, salad"] },
    ]},
    { id: "tea-10", day: "2026-12-10", start: "16:00", end: "18:00", title: "High tea", stations: [
      { station: "Beverages", items: ["Tea", "Coffee"] },
      { station: "Snacks",    items: ["Methi pakoda", "Mixed vegetable pakoda", "Dhokla"] },
      { station: "Chutneys",  items: ["Green chutney, sweet chutney, ketchup"] },
    ]},
    { id: "dinner-10", day: "2026-12-10", start: "18:30", end: "22:00", title: "Sangeet dinner", for: "sangeet", stations: [
      { station: "Fresh juices",  items: ["Watermelon", "Pineapple"] },
      { station: "Starters",      items: ["Palak cheese kebab", "Paneer tikka", "Hara bhara kebab"] },
      { station: "Chaat counter", items: ["Dahi vada chaat", "Aloo tikki chaat"] },
      { station: "Soup",          items: ["Manchow soup"] },
      { station: "Chinese",       items: ["Vegetable noodles", "Vegetable Manchurian"] },
      { station: "Main course",   items: ["Matar mushroom", "Palak paneer", "Dal sultani", "Vegetable biryani, steamed rice"] },
      { station: "Breads",        items: ["Missi roti", "Butter naan", "Tandoori roti"] },
      { station: "Desserts",      items: ["Malpua with rabri", "Rajbhog", "Vanilla ice cream"] },
      { station: "On the side",   items: ["Salad, papad, pickle"] },
    ]},
    { id: "breakfast-11", day: "2026-12-11", start: "08:00", end: "10:30", title: "Breakfast", stations: [
      { station: "To start",  items: ["Cut fruits, fresh juice", "Tea, coffee, milk"] },
      { station: "South",     items: ["Idli, vada, dosa", "Sambar, chutney", "Upma, kesari bath"] },
      { station: "North",     items: ["Puri with aloo sagu", "Aloo paratha", "Bread, butter, jam, toast"] },
      { station: "On the side", items: ["Curd, pickle, salad"] },
    ]},
    { id: "haldi-11", day: "2026-12-11", start: "11:00", end: "13:00", title: "Haldi refreshments", for: "haldi", stations: [
      { station: "Beverages", items: ["Mint mojito (non-alcoholic)", "Watermelon juice"] },
      { station: "Snacks",    items: ["Cocktail samosa", "Green chutney, sweet chutney"] },
    ]},
    { id: "lunch-11", day: "2026-12-11", start: "13:00", end: "15:00", title: "Lunch", stations: [
      { station: "Beverages",   items: ["Lemon soda", "Mint mojito (non-alcoholic)", "Watermelon juice"] },
      { station: "Main course", items: ["Aloo kathal", "Panchmel dal", "Chana masala", "Palak paneer kofta", "Steamed rice"] },
      { station: "Breads",      items: ["Kulcha", "Naan", "Tandoori roti"] },
      { station: "Desserts",    items: ["Angoori rasmalai", "Moong dal halwa"] },
      { station: "On the side", items: ["Salad, papad, pickle"] },
    ]},
    { id: "tea-11", day: "2026-12-11", start: "16:00", end: "18:00", title: "High tea", stations: [
      { station: "Beverages", items: ["Tea", "Coffee"] },
      { station: "Bakes",     items: ["Muffins", "Cookies"] },
    ]},
    { id: "dinner-11", day: "2026-12-11", start: "19:00", end: "23:30", title: "Wedding dinner", for: "wedding", stations: [
      { station: "Mocktails",        items: ["The chef’s selection of non-alcoholic mocktails"] },
      { station: "Soups",            items: ["Manchow soup", "Rainbow soup"] },
      { station: "Starters",         items: ["Golden baby corn", "Paneer tikka", "Kalmi vada", "Spring rolls", "Bhokara (paneer-stuffed aloo)"] },
      { station: "Chaat & grill",    items: ["Pani puri", "Dahi kebab", "Palak patta chaat", "Paneer chilla", "Tikki chaat with ragda", "Soya chaap"] },
      { station: "Main course",      items: ["Kadai paneer", "Subz seekh kofta", "Kaju makhana", "Tawa sabzi", "Dal makhani", "Handi dum biryani", "Plain kaju rice", "Pineapple raita"] },
      { station: "Breads",           items: ["Butter naan", "Kulcha", "Missi roti", "Tandoori roti", "Palak puri"] },
      { station: "Chinese & pasta",  items: ["Mongolian hotchpotch", "Hakka noodles", "Red sauce pasta", "White sauce pasta"] },
      { station: "Bihari counter",   items: ["Litti chokha", "Baingan bhaja", "Green chutney, sweet chutney, ghee"] },
      { station: "Punjabi counter",  items: ["Sarson ka saag", "Makki ki roti", "Bajra roti"] },
      { station: "South Indian",     items: ["Plain dosa", "Masala dosa", "Chutney, sambar"] },
      { station: "Momos",            items: ["Vegetable momos"] },
      { station: "Halwa counter",    items: ["Carrot halwa", "Dry fruit tawa halwa"] },
      { station: "Desserts",         items: ["Live jalebi with rabri", "Kesar kulfi", "Mysore pak", "Vanilla ice cream with hot chocolate and nuts"] },
      { station: "On the side",      items: ["Plain curd, salad"] },
    ]},
    { id: "breakfast-12", day: "2026-12-12", start: "08:00", end: "11:00", title: "Breakfast", for: "bidai", stations: [
      { station: "To start",  items: ["Cut fruits, fresh juice", "Tea, coffee, milk"] },
      { station: "South",     items: ["Dosa, idli", "Chutney, sambar", "Upma, kesari bath"] },
      { station: "North",     items: ["Chole puri", "Paneer paratha", "Bread, butter, jam, toast"] },
    ]},
  ],
  alwaysOn: "Chai, coffee and cookies are on all day and all night, from the moment you arrive until you leave, brought to your room whenever you ask.",

  // ── Words on the invitation & magazine ─────────────────────────────────────
  copy: {
    inviteLine: "request the honour of your presence on the auspicious occasion of the wedding ceremony of their son",
    withLine: "with",
    complimentsLine: "With best compliments",
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
