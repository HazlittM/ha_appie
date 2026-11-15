/* HA Appie card v0.5.0 - built into the HA Appie integration (no build step, no dependencies). */
(() => {
  const VERSION = "0.5.0";
  const DOMAIN = "ha_appie";

  // ---------------------------------------------------------------------------
  // HA 2026.8+ scoped custom-element registry race (home-assistant/frontend#52960):
  // define now, and again on whichever registry won once HA has booted.
  // Reference: benct/lovelace-multiple-entity-row#434 (MIT).
  // ---------------------------------------------------------------------------
  function healDefine(name, ctor) {
    if (customElements.get(name)) return;
    try {
      customElements.define(name, ctor);
    } catch (err) {
      console.warn(`HA Appie: re-defining ${name} failed`, err);
    }
  }
  function defineElement(name, ctor) {
    const registry = customElements;
    if (!registry.get(name)) registry.define(name, ctor);
    registry.whenDefined("home-assistant").then(() => healDefine(name, ctor));
    setTimeout(() => healDefine(name, ctor), 5000);
  }

  // ---------------------------------------------------------------------------
  // Texts
  // ---------------------------------------------------------------------------
  const T = {
    nl: {
      tab_list: "Lijst", tab_delivery: "Bezorging", tab_bonus: "Bonus", tab_receipts: "Bonnen",
      tab_recipes: "Recepten", tab_store: "Winkel", tab_card: "Bonuskaart",
      search_ph: "Zoek een product…", search: "Zoeken", add: "Toevoegen", added: "Op je lijst gezet",
      free_text_ph: "Tekst op de lijst, bv. '2 melk'", list: "Boodschappenlijst", list_empty: "Je lijst is leeg.",
      tick: "Afvinken", regulars: "Vaste producten", regulars_add: "Zet op lijst", regulars_reset: "Standaard",
      regulars_hint: "Aantal per product voor deze week (0 = overslaan).", basket: "Winkelmand",
      total: "Totaal", discount: "Korting", none: "Niets", status: "Status", slot: "Bezorgslot",
      eta: "Verwachte aankomst", change_until: "Wijzigen tot", minimum: "Minimumbedrag",
      order: "Bestelling", products: "producten", invoice: "Factuur (PDF)", free_slots: "Vrije bezorgmomenten",
      no_delivery: "Geen bezorging gepland.", personal_bonus: "Persoonlijke Bonus", previous_bonus: "Bonus op eerder gekocht",
      activated: "Geactiveerd", not_activated: "Nog activeren in de app", period: "Bonusweek",
      last_receipt: "Laatste kassabon", saved: "Bespaard", saved_month: "Bespaard deze maand",
      spent_month: "Uitgegeven deze maand", per_month: "Uitgaven per maand", recent: "Eerdere bonnen",
      pdf_open: "PDF bekijken", pdf_save: "Opslaan in /media", payments: "Betaald", lines: "regels",
      own_recipes: "Mijn recepten", persons: "personen", recipe_to_list: "Op lijst", allerhande: "Allerhande",
      recipe_ph: "Zoek een Allerhande-recept…", import: "Overnemen", open_ah: "Op ah.nl", ingredients: "Ingrediënten",
      steps: "Bereiding", minutes: "min", imported: "Recept overgenomen", store: "Favoriete winkel",
      open: "Open", closed: "Dicht", today: "Vandaag", until: "tot", opens: "opent om", hours: "Openingstijden",
      last_chance: "Laatste kans", stock: "op voorraad", expires: "t/m", card_hint: "Laat deze code scannen bij de kassa. Zet je scherm op fel.",
      card_none: "Zet 'Bonuskaart' aan in de opties van HA Appie om je kaart hier te tonen.",
      favorites: "Favorieten", to_favorites: "Aan favorieten", saved_to: "Opgeslagen:", close: "Sluiten",
      not_available: "Niet beschikbaar", loading: "Laden…", error: "Mislukt", no_results: "Niets gevonden.",
      states: { geen: "Geen bezorging", gepland: "Gepland", tijd_bekend: "Tijd bekend", bezorgd: "Bezorgd", geannuleerd: "Geannuleerd", onbekend: "Onbekend" },
      reload: "Nieuwe versie van de kaart: herlaad de pagina.", missing: "HA Appie is niet gevonden. Is de integratie ingesteld?",
      allergens: "Bevat", product_info: "Productinfo", nutrition: "Voedingswaarde",
    },
    en: {
      tab_list: "List", tab_delivery: "Delivery", tab_bonus: "Bonus", tab_receipts: "Receipts",
      tab_recipes: "Recipes", tab_store: "Store", tab_card: "Bonus card",
      search_ph: "Search a product…", search: "Search", add: "Add", added: "Added to your list",
      free_text_ph: "Text for the list, e.g. '2 milk'", list: "Shopping list", list_empty: "Your list is empty.",
      tick: "Tick off", regulars: "Regular products", regulars_add: "Add to list", regulars_reset: "Default",
      regulars_hint: "Quantity per product this week (0 = skip).", basket: "Basket",
      total: "Total", discount: "Discount", none: "Nothing", status: "Status", slot: "Delivery slot",
      eta: "Expected arrival", change_until: "Change until", minimum: "Minimum order",
      order: "Order", products: "products", invoice: "Invoice (PDF)", free_slots: "Free delivery slots",
      no_delivery: "No delivery planned.", personal_bonus: "Personal Bonus", previous_bonus: "Bonus on previously bought",
      activated: "Activated", not_activated: "Activate in the app", period: "Bonus week",
      last_receipt: "Latest receipt", saved: "Saved", saved_month: "Saved this month",
      spent_month: "Spent this month", per_month: "Spending per month", recent: "Earlier receipts",
      pdf_open: "Open PDF", pdf_save: "Save to /media", payments: "Paid", lines: "lines",
      own_recipes: "My recipes", persons: "persons", recipe_to_list: "To list", allerhande: "Allerhande",
      recipe_ph: "Search an Allerhande recipe…", import: "Import", open_ah: "On ah.nl", ingredients: "Ingredients",
      steps: "Preparation", minutes: "min", imported: "Recipe imported", store: "Favourite store",
      open: "Open", closed: "Closed", today: "Today", until: "until", opens: "opens at", hours: "Opening hours",
      last_chance: "Last chance", stock: "in stock", expires: "until", card_hint: "Let the till scan this code. Turn your screen brightness up.",
      card_none: "Switch on 'Bonus card' in the HA Appie options to show your card here.",
      favorites: "Favourites", to_favorites: "To favourites", saved_to: "Saved:", close: "Close",
      not_available: "Not available", loading: "Loading…", error: "Failed", no_results: "Nothing found.",
      states: { geen: "No delivery", gepland: "Planned", tijd_bekend: "Time known", bezorgd: "Delivered", geannuleerd: "Cancelled", onbekend: "Unknown" },
      reload: "New card version: reload the page.", missing: "HA Appie not found. Is the integration set up?",
      allergens: "Contains", product_info: "Product info", nutrition: "Nutrition",
    },
  };
  let LANG = "nl";
  const t = (key) => (T[LANG] && T[LANG][key]) ?? T.en[key] ?? key;
  const setLang = (hass) => {
    const l = (hass?.locale?.language || hass?.language || "nl").toLowerCase();
    LANG = l.startsWith("nl") ? "nl" : "en";
  };

  const TABS = [
    ["list", "mdi:cart-outline"],
    ["delivery", "mdi:truck-delivery-outline"],
    ["bonus", "mdi:sale"],
    ["receipts", "mdi:receipt-text-outline"],
    ["recipes", "mdi:chef-hat"],
    ["store", "mdi:store-outline"],
    ["card", "mdi:barcode"],
  ];

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const num = (v) => (v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? null : Number(v));
  const money = (v) => {
    const n = num(v);
    if (n === null) return "";
    return new Intl.NumberFormat(LANG === "nl" ? "nl-NL" : "en-GB", { style: "currency", currency: "EUR" }).format(n);
  };
  // AH-style price: big euros, small raised cents
  const price = (v, cls = "") => {
    const n = num(v);
    if (n === null) return "";
    const [e, c] = n.toFixed(2).split(".");
    return `<span class="price ${cls}">${e}<sup>.${c}</sup></span>`;
  };
  const dfmt = (iso, opts) => {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return new Intl.DateTimeFormat(LANG === "nl" ? "nl-NL" : "en-GB", opts).format(d);
  };
  const time = (iso) => dfmt(iso, { hour: "2-digit", minute: "2-digit" });
  const day = (iso) => dfmt(iso, { weekday: "short", day: "numeric", month: "short" });
  const dayTime = (iso) => dfmt(iso, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  const icon = (name, cls = "") => `<ha-icon class="${cls}" icon="${esc(name)}"></ha-icon>`;
  const img = (url, alt = "") => (url ? `<img loading="lazy" src="${esc(url)}" alt="${esc(alt)}" referrerpolicy="no-referrer">` : icon("mdi:food-apple-outline", "noimg"));

  // Integration logo (brand/icon.png): blue tile, white house outline, basket
  const LOGO = `<svg viewBox="0 0 64 64" aria-hidden="true"><rect x="1" y="1" width="62" height="62" rx="14" fill="#00a0e2" stroke="#fff" stroke-width="2"/><path d="M32 10.2 53.1 28.2v25.6H10.9V28.2Z" fill="#fff"/><path d="M32 16.3 49 30.4v19.8H15V30.4Z" fill="#00a0e2"/><path d="M26 35a6.2 7.2 0 0 1 12 0" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"/><rect x="21.1" y="37.5" width="21.8" height="2.6" rx="1.2" fill="#fff"/><path d="M22.4 39h19.2l-2.3 10.3H24.7Z" fill="#fff"/><path d="M28.2 41.2v6.7M32 41.2v6.7M35.8 41.2v6.7" stroke="#00a0e2" stroke-width="1.4"/></svg>`;

  // EAN-13 for the bonus card
  const EAN_L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"];
  const EAN_G = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111"];
  const EAN_R = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001110", "1010000", "1000100", "1001000", "1110100"];
  const EAN_PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"];
  function ean13Valid(code) {
    if (!/^\d{13}$/.test(code || "")) return false;
    const d = code.split("").map(Number);
    const sum = d.slice(0, 12).reduce((s, x, i) => s + x * (i % 2 ? 3 : 1), 0);
    return (10 - (sum % 10)) % 10 === d[12];
  }
  function ean13Svg(code) {
    const d = code.split("").map(Number);
    let bits = "101";
    const parity = EAN_PARITY[d[0]];
    for (let i = 1; i <= 6; i++) bits += (parity[i - 1] === "L" ? EAN_L : EAN_G)[d[i]];
    bits += "01010";
    for (let i = 7; i <= 12; i++) bits += EAN_R[d[i]];
    bits += "101";
    const guard = new Set([0, 1, 2, 45, 46, 47, 48, 49, 92, 93, 94]);
    let rects = "";
    for (let i = 0; i < bits.length; i++) {
      if (bits[i] === "1") rects += `<rect x="${i + 9}" y="2" width="1" height="${guard.has(i) ? 58 : 52}"/>`;
    }
    const digits = `<text x="4" y="66">${d[0]}</text><text x="31" y="66" text-anchor="middle" textLength="38">${code.slice(1, 7)}</text><text x="77" y="66" text-anchor="middle" textLength="38">${code.slice(7)}</text>`;
    return `<svg class="ean" viewBox="0 0 113 70" role="img" aria-label="EAN-13"><rect width="113" height="70" fill="#fff"/><g fill="#000">${rects}</g><g font-family="monospace" font-size="8" fill="#000">${digits}</g></svg>`;
  }

  // Entities are found by their translation_key (not by entity_id, which is translated)
  function findEntities(hass) {
    const out = { regulars: [] };
    const reg = hass?.entities || {};
    for (const [id, e] of Object.entries(reg)) {
      if (e.platform !== DOMAIN) continue;
      const domain = id.split(".")[0];
      if (e.translation_key) out[`${domain}.${e.translation_key}`] ??= id;
      if (domain === "number" && !e.translation_key) {
        const st = hass.states[id];
        if (st && st.attributes.product_id !== undefined && st.attributes.standaard !== undefined) out.regulars.push(id);
      }
    }
    out.regulars.sort((a, b) => String(hass.states[a]?.attributes.friendly_name).localeCompare(String(hass.states[b]?.attributes.friendly_name)));
    return out;
  }

  // ---------------------------------------------------------------------------
  // Self-update: a tablet that stays open for days picks up a new card by itself
  // ---------------------------------------------------------------------------
  const RELOAD_KEY = "ha-appie-card-reloaded-for";
  let lastUpdateCheck = 0;
  let pendingVersion = null;
  async function checkForNewerCard(hass) {
    if (Date.now() - lastUpdateCheck < 15 * 60 * 1000 || document.visibilityState === "hidden") return;
    lastUpdateCheck = Date.now();
    try {
      const resources = await hass.callWS({ type: "lovelace/resources" });
      const ours = (resources || []).find((r) => String(r.url).includes("/ha_appie_static/ha-appie-card.js"));
      const served = ours && new URL(ours.url, location.origin).searchParams.get("v");
      if (!served || served === VERSION) return;
      const editing = new URLSearchParams(location.search).has("edit");
      let guard = null;
      try { guard = sessionStorage.getItem(RELOAD_KEY); } catch (e) { /* private mode */ }
      if (!editing && guard !== served) {
        try { sessionStorage.setItem(RELOAD_KEY, served); } catch (e) { /* ignore */ }
        location.reload();
        return;
      }
      pendingVersion = served;
    } catch (e) {
      /* YAML-mode resources or no admin: nothing to check */
    }
  }
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") lastUpdateCheck = 0; });

  // ---------------------------------------------------------------------------
  // Styles (AH look on top of the HA theme; works in light and dark)
  // ---------------------------------------------------------------------------
  const STYLE = `
  :host { --ah: #00a0e2; --ah-deep: #0077b6; --ah-bonus: #ff7a00; --ah-ok: #2e9d4f; --ah-tile: #ffffff;
    --ah-soft: color-mix(in srgb, var(--ah) 9%, var(--card-background-color, #fff));
    --ah-line: var(--divider-color, rgba(0,0,0,.12)); display: block; }
  ha-card { overflow: hidden; }
  .ct { container-type: inline-size; }
  .head { background: var(--ah); color: #fff; padding: 12px 14px 0; }
  .brand { display: flex; align-items: center; gap: 6px 10px; min-height: 40px; flex-wrap: wrap; }
  .brand svg { width: 34px; height: 34px; flex: none; border-radius: 9px; }
  .brand .title { font-size: 1.15rem; font-weight: 700; letter-spacing: .1px; flex: 1; white-space: nowrap; }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; margin-left: auto; }
  .chip { display: inline-flex; align-items: center; gap: 4px; background: rgba(255,255,255,.18); color: #fff;
    border-radius: 999px; padding: 3px 9px; font-size: .78rem; font-weight: 600; white-space: nowrap; }
  .chip ha-icon { --mdc-icon-size: 15px; }
  .chip.warn { background: #fff; color: var(--ah-deep); }
  .tabs { display: flex; gap: 2px; overflow-x: auto; scrollbar-width: none; margin: 10px -14px 0; padding: 0 10px; }
  .tabs::-webkit-scrollbar { display: none; }
  .tab { flex: none; display: inline-flex; align-items: center; gap: 6px; border: 0; cursor: pointer; font: inherit;
    font-size: .88rem; font-weight: 600; color: rgba(255,255,255,.9); background: transparent; padding: 9px 12px 10px;
    border-radius: 12px 12px 0 0; }
  .tab ha-icon { --mdc-icon-size: 18px; }
  .tab.active { background: var(--card-background-color, #fff); color: var(--ah-deep); }
  .tab:focus-visible { outline: 2px solid #fff; outline-offset: -3px; }
  .body { padding: 14px; display: grid; gap: 14px; }
  .section { display: grid; gap: 8px; }
  .section > h3 { margin: 0; font-size: .95rem; font-weight: 700; display: flex; align-items: center; gap: 8px; }
  .section > h3 .count { margin-left: auto; font-weight: 600; color: var(--secondary-text-color); font-size: .82rem; }
  .muted { color: var(--secondary-text-color); font-size: .85rem; }
  .row { display: flex; align-items: center; gap: 10px; min-height: 40px; }
  .row .grow { flex: 1; min-width: 0; }
  .row .name { overflow-wrap: anywhere; }
  .row .sub { color: var(--secondary-text-color); font-size: .8rem; }
  .list { display: grid; border: 1px solid var(--ah-line); border-radius: 12px; overflow: hidden; }
  .list > .row { padding: 6px 10px; border-top: 1px solid var(--ah-line); }
  .list > .row:first-child { border-top: 0; }
  .search { display: flex; gap: 8px; }
  input[type=text], input[type=search] { flex: 1; min-width: 0; font: inherit; color: var(--primary-text-color);
    background: var(--ah-soft); border: 1px solid transparent; border-radius: 999px; padding: 10px 14px; outline: none; }
  input:focus { border-color: var(--ah); background: var(--card-background-color); }
  .btn { font: inherit; font-weight: 700; font-size: .88rem; border: 0; border-radius: 999px; padding: 9px 14px; cursor: pointer;
    background: var(--ah); color: #fff; display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
  .btn.ghost { background: var(--ah-soft); color: var(--ah-deep); }
  .btn.small { padding: 6px 10px; font-size: .8rem; }
  .btn:disabled { opacity: .55; cursor: default; }
  .btn ha-icon { --mdc-icon-size: 18px; }
  .iconbtn { border: 0; background: transparent; color: var(--secondary-text-color); cursor: pointer; border-radius: 50%;
    width: 36px; height: 36px; display: inline-flex; align-items: center; justify-content: center; flex: none; }
  .iconbtn:hover { background: var(--ah-soft); color: var(--ah-deep); }
  .iconbtn.add { background: var(--ah); color: #fff; }
  .stepper { display: inline-flex; align-items: center; background: var(--ah-soft); border-radius: 999px; flex: none; }
  .stepper button { border: 0; background: transparent; width: 32px; height: 32px; border-radius: 50%; cursor: pointer;
    color: var(--ah-deep); font-size: 1.1rem; font-weight: 700; }
  .stepper span { min-width: 22px; text-align: center; font-weight: 700; }
  .thumb { width: 44px; height: 44px; border-radius: 10px; background: var(--ah-tile); flex: none; display: flex;
    align-items: center; justify-content: center; overflow: hidden; border: 1px solid var(--ah-line); }
  .thumb img { width: 100%; height: 100%; object-fit: contain; }
  .thumb .noimg { color: #b9c6d0; --mdc-icon-size: 22px; }
  .price { font-weight: 800; font-size: 1.05rem; white-space: nowrap; }
  .price sup { font-size: .62em; top: -.45em; margin-left: 1px; }
  .was { color: var(--secondary-text-color); text-decoration: line-through; font-size: .8rem; margin-right: 4px; }
  .bonus { display: inline-block; background: var(--ah-bonus); color: #fff; font-weight: 800; font-size: .72rem;
    border-radius: 6px; padding: 2px 6px; text-transform: uppercase; letter-spacing: .3px; }
  .badge { display: inline-block; border-radius: 6px; padding: 2px 6px; font-size: .72rem; font-weight: 700;
    background: var(--ah-soft); color: var(--ah-deep); }
  .badge.ok { background: color-mix(in srgb, var(--ah-ok) 16%, transparent); color: var(--ah-ok); }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
  .stepper button { width: 30px; height: 30px; }
  .tile { border: 1px solid var(--ah-line); border-radius: 14px; overflow: hidden; display: flex; flex-direction: column;
    background: var(--card-background-color); }
  .tile .pic { background: var(--ah-tile); aspect-ratio: 4 / 3; display: flex; align-items: center; justify-content: center; position: relative; }
  .tile .pic img { width: 100%; height: 100%; object-fit: contain; }
  .tile .pic.cover img { object-fit: cover; }
  .tile .pic .bonus { position: absolute; left: 8px; top: 8px; }
  .tile .pic .badge { position: absolute; right: 8px; top: 8px; }
  .tile .info { padding: 8px 10px 10px; display: grid; gap: 4px; flex: 1; }
  .tile .info .name { font-size: .86rem; font-weight: 600; line-height: 1.25; }
  .tile .foot { display: flex; align-items: center; gap: 2px; margin-top: auto; }
  .tile .foot .iconbtn { width: 32px; height: 32px; }
  .tile .foot .iconbtn ha-icon { --mdc-icon-size: 20px; }
  .tile .foot .grow { flex: 1; }
  .minis { position: absolute; right: 6px; top: 6px; display: grid; gap: 4px; }
  .minis.inline { position: static; display: flex; }
  .mini { width: 28px; height: 28px; border-radius: 50%; border: 1px solid var(--ah-line); background: #fff; color: var(--ah-deep);
    display: inline-flex; align-items: center; justify-content: center; cursor: pointer; padding: 0; }
  .mini ha-icon { --mdc-icon-size: 17px; }
  .mini:hover { background: var(--ah); color: #fff; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; }
  .kpi { background: var(--ah-soft); border-radius: 14px; padding: 10px 12px; display: grid; gap: 2px; }
  .kpi .label { font-size: .78rem; color: var(--secondary-text-color); font-weight: 600; }
  .kpi .value { font-size: 1.15rem; font-weight: 800; }
  .kpi .value.big { font-size: 1.4rem; color: var(--ah-deep); }
  .hero { background: var(--ah-soft); border-radius: 16px; padding: 14px; display: grid; gap: 6px; }
  .hero .state { font-size: 1.3rem; font-weight: 800; color: var(--ah-deep); display: flex; align-items: center; gap: 8px; }
  .bars { display: grid; gap: 6px; }
  .bar { display: grid; grid-template-columns: 70px 1fr auto; align-items: center; gap: 8px; font-size: .82rem; }
  .bar .track { height: 10px; background: var(--ah-soft); border-radius: 999px; overflow: hidden; }
  .bar .fill { height: 100%; background: var(--ah); border-radius: 999px; }
  .hours { display: grid; grid-template-columns: auto 1fr; gap: 2px 14px; font-size: .86rem; }
  .hours .today { font-weight: 800; color: var(--ah-deep); }
  .barcode { background: #fff; border-radius: 16px; padding: 16px; display: grid; justify-items: center; gap: 8px; }
  .barcode .ean { width: min(100%, 360px); height: auto; }
  .barcode .label { color: #003b73; font-weight: 800; display: flex; align-items: center; gap: 8px; }
  .barcode .label svg { width: 26px; height: 26px; }
  .empty { color: var(--secondary-text-color); font-size: .9rem; padding: 6px 2px; }
  .notice { background: color-mix(in srgb, var(--ah-bonus) 14%, transparent); border-radius: 12px; padding: 8px 12px; font-size: .85rem; }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; }
  .modal-back { position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 10; display: flex; align-items: center;
    justify-content: center; padding: 16px; }
  .modal { background: var(--card-background-color, #fff); color: var(--primary-text-color); border-radius: 18px;
    width: min(560px, 100%); max-height: 88vh; overflow: auto; box-shadow: 0 10px 40px rgba(0,0,0,.3); }
  .modal .mhead { position: sticky; top: 0; background: var(--ah); color: #fff; padding: 12px 14px; display: flex; align-items: center; gap: 8px; z-index: 1; }
  .modal .mhead .grow { flex: 1; font-weight: 800; }
  .modal .mhead .iconbtn { color: #fff; }
  .modal .mbody { padding: 14px; display: grid; gap: 12px; }
  .modal .hero-img { width: 100%; border-radius: 12px; max-height: 240px; object-fit: cover; }
  ol.steps { margin: 0; padding-left: 20px; display: grid; gap: 6px; }
  .spin { animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .spin { animation: none; } }
  @container (max-width: 640px) {
    .tab .label { display: none; }
    .tab.active .label { display: inline; }
    .grid { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
    .bar { grid-template-columns: 58px 1fr auto; }
  }`;

  // ---------------------------------------------------------------------------
  // The card
  // ---------------------------------------------------------------------------
  class HaAppieCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._tab = null;
      this._st = {
        q: "", results: null, searching: false, qty: {},
        rq: "", recipes: null, rsearching: false,
        todo: null, todoFor: null, free: "",
        modal: null, busy: {},
      };
      this._html = "";
      this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
      this.shadowRoot.addEventListener("keydown", (ev) => this._onKey(ev));
      this.shadowRoot.addEventListener("input", (ev) => this._onInput(ev));
      this.shadowRoot.addEventListener("mousedown", (ev) => { this._downOnBack = ev.target.classList?.contains("modal-back"); });
    }

    static getStubConfig() {
      return { type: "custom:ha-appie-card" };
    }

    static getConfigForm() {
      const tabs = TABS.map(([k]) => k);
      return {
        schema: [
          { name: "title", selector: { text: {} } },
          { name: "default_tab", selector: { select: { mode: "dropdown", options: tabs.map((k) => ({ value: k, label: t(`tab_${k}`) })) } } },
          {
            type: "grid", name: "", schema: tabs.map((k) => ({ name: `show_${k}`, default: true, selector: { boolean: {} } })),
          },
          { name: "show_images", default: true, selector: { boolean: {} } },
          { name: "show_regulars", default: true, selector: { boolean: {} } },
          { name: "max_items", default: 12, selector: { number: { min: 3, max: 60, mode: "box" } } },
        ],
        computeLabel: (s) => {
          const nl = LANG === "nl";
          const L = {
            title: nl ? "Titel" : "Title", default_tab: nl ? "Starttabblad" : "Start tab",
            show_images: nl ? "Productfoto's tonen" : "Show product photos",
            show_regulars: nl ? "Vaste producten op de lijst-tab" : "Regular products on the list tab",
            max_items: nl ? "Maximaal aantal tegels per onderdeel" : "Maximum tiles per section",
          };
          if (s.name?.startsWith("show_") && !L[s.name]) return `${nl ? "Tab" : "Tab"}: ${t(`tab_${s.name.slice(5)}`)}`;
          return L[s.name] ?? s.name;
        },
      };
    }

    setConfig(config) {
      this._config = { title: "Albert Heijn", default_tab: "list", show_images: true, max_items: 12, ...config };
      const fromUrl = new URLSearchParams(location.search).get("appie_tab");
      if (!this._tab || this._lastDefault !== this._config.default_tab) this._tab = fromUrl || this._config.default_tab;
      this._lastDefault = this._config.default_tab;
      this._render(true);
    }

    set hass(hass) {
      const first = !this._hass;
      this._hass = hass;
      setLang(hass);
      this._e = findEntities(hass);
      checkForNewerCard(hass);
      const todo = this._e["todo.shopping_list"];
      const stamp = todo && hass.states[todo]?.last_updated;
      if (todo && stamp !== this._st.todoFor) {
        this._st.todoFor = stamp;
        this._loadTodo(todo);
      }
      if (first) this._render(true);
      else this._render();
    }

    getCardSize() { return 8; }
    getGridOptions() { return { columns: 12, min_columns: 6, rows: "auto" }; }

    connectedCallback() {
      this._onLocation = () => {
        const tab = new URLSearchParams(location.search).get("appie_tab");
        if (tab && tab !== this._tab) { this._tab = tab; this._render(true); }
      };
      window.addEventListener("location-changed", this._onLocation);
    }
    disconnectedCallback() { window.removeEventListener("location-changed", this._onLocation); }

    // ---- data helpers
    _s(key) { const id = this._e?.[key]; return id ? this._hass.states[id] : undefined; }
    _attr(key, a) { return this._s(key)?.attributes?.[a]; }
    _ok(st) { return st && st.state !== "unavailable" && st.state !== "unknown"; }
    _shown(tab) {
      if (this._config[`show_${tab}`] === false) return false;
      if (tab === "card") return !!this._s("sensor.bonus_card") || this._config.show_card === true;
      if (tab === "store") return !!(this._s("sensor.store") || this._s("sensor.bargains"));
      return true;
    }

    async _loadTodo(entity) {
      try {
        const r = await this._hass.callWS({ type: "todo/item/list", entity_id: entity });
        this._st.todo = (r.items || []).filter((i) => i.status !== "completed");
      } catch (e) {
        this._st.todo = null;
      }
      this._render();
    }

    async _service(service, data = {}, response = false) {
      if (response) {
        const r = await this._hass.callWS({ type: "call_service", domain: DOMAIN, service, service_data: data, return_response: true });
        return r?.response;
      }
      return this._hass.callService(DOMAIN, service, data);
    }

    _toast(message) {
      this.dispatchEvent(new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true }));
    }

    async _busy(key, fn) {
      if (this._st.busy[key]) return;
      this._st.busy[key] = true;
      this._render();
      try {
        await fn();
      } catch (err) {
        this._toast(`${t("error")}: ${err?.message || err}`);
      } finally {
        delete this._st.busy[key];
        this._render();
      }
    }

    async _openPdf(kind, ref) {
      await this._busy(`pdf-${kind}`, async () => {
        const resp = await this._hass.fetchWithAuth(`/api/ha_appie/pdf/${kind}/${encodeURIComponent(ref)}`);
        if (!resp.ok) throw new Error(t("not_available"));
        const url = URL.createObjectURL(await resp.blob());
        const w = window.open(url, "_blank");
        if (!w) { const a = document.createElement("a"); a.href = url; a.download = `${kind}.pdf`; a.click(); }
        setTimeout(() => URL.revokeObjectURL(url), 60000);
      });
    }

    // ---- events
    _onInput(ev) {
      const el = ev.target;
      if (el.id === "q") this._st.q = el.value;
      if (el.id === "rq") this._st.rq = el.value;
      if (el.id === "free") this._st.free = el.value;
    }

    _onKey(ev) {
      if (ev.key === "Escape" && this._st.modal) { this._st.modal = null; this._render(); return; }
      if (ev.key !== "Enter") return;
      const id = ev.target.id;
      if (id === "q") this._doSearch();
      if (id === "rq") this._doRecipeSearch();
      if (id === "free") this._addFree();
    }

    _onClick(ev) {
      const target = ev.target.closest("[data-a]");
      if (!target) {
        if (ev.target.classList?.contains("modal-back") && this._downOnBack) { this._st.modal = null; this._render(); }
        return;
      }
      const a = target.dataset.a;
      const v = target.dataset.v;
      const st = this._st;
      const h = this._hass;
      switch (a) {
        case "tab": this._tab = v; this._render(); break;
        case "search": this._doSearch(); break;
        case "qty": {
          const [pid, d] = v.split(":");
          st.qty[pid] = Math.max(1, Math.min(50, (st.qty[pid] || 1) + Number(d)));
          this._render();
          break;
        }
        case "addp": {
          const [pid, title] = [Number(v), target.dataset.t];
          this._busy(`add-${pid}`, async () => {
            await this._service("add_product", { product_id: pid, title, quantity: st.qty[pid] || 1 }, true);
            this._toast(`${t("added")}: ${st.qty[pid] || 1}x ${title}`);
            st.qty[pid] = 1;
          });
          break;
        }
        case "fav":
          this._busy(`fav-${v}`, async () => {
            const r = await this._service("add_to_favorites", { product_id: Number(v) }, true);
            this._toast(`${t("to_favorites")}: ${r?.list || ""}`);
          });
          break;
        case "info":
          this._busy(`info-${v}`, async () => {
            st.modal = { kind: "product", data: await this._service("product_details", { product_id: Number(v) }, true) };
          });
          break;
        case "tick":
          this._busy(`tick-${v}`, async () => {
            await h.callService("todo", "update_item", { item: v, status: "completed" }, { entity_id: this._e["todo.shopping_list"] });
            st.todo = (st.todo || []).filter((i) => i.uid !== v);
          });
          break;
        case "free": this._addFree(); break;
        case "reg": {
          const [id, d] = v.split("|");
          const cur = Number(h.states[id]?.state) || 0;
          h.callService("number", "set_value", { value: Math.max(0, Math.min(30, cur + Number(d))) }, { entity_id: id });
          break;
        }
        case "press": h.callService("button", "press", {}, { entity_id: v }); this._toast("✓"); break;
        case "more": this._more(v); break;
        case "pdf": this._openPdf(target.dataset.k, v); break;
        case "pdfsave":
          this._busy(`save-${target.dataset.k}`, async () => {
            const r = await this._service(target.dataset.k === "invoice" ? "save_invoice_pdf" : "save_receipt_pdf", { id: v }, true);
            this._toast(`${t("saved_to")} ${r?.path || ""}`);
          });
          break;
        case "receipt":
          this._busy(`receipt-${v}`, async () => {
            st.modal = { kind: "receipt", id: v, data: await this._service("get_receipt", { id: v }, true) };
          });
          break;
        case "rsearch": this._doRecipeSearch(); break;
        case "recipe":
          this._busy(`recipe-${v}`, async () => {
            st.modal = { kind: "recipe", data: await this._service("get_recipe", { recipe_id: Number(v) }, true) };
          });
          break;
        case "import":
          this._busy(`import-${v}`, async () => {
            const r = await this._service("import_recipe", { recipe_id: Number(v) }, true);
            this._toast(`${t("imported")}: ${r?.recipe || ""}`);
          });
          break;
        case "recsel": h.callService("select", "select_option", { option: v }, { entity_id: this._e["select.recipe_select"] }); break;
        case "persons": {
          const id = this._e["number.recipe_persons"];
          const cur = Number(h.states[id]?.state) || 1;
          h.callService("number", "set_value", { value: Math.max(1, Math.min(30, cur + Number(v))) }, { entity_id: id });
          break;
        }
        case "close": st.modal = null; this._render(); break;
        default: break;
      }
    }

    _more(entityId) {
      this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
    }

    _addFree() {
      const text = (this._st.free || "").trim();
      const id = this._e["todo.shopping_list"];
      if (!text || !id) return;
      this._busy("free", async () => {
        await this._hass.callService("todo", "add_item", { item: text }, { entity_id: id });
        this._st.free = "";
        const input = this.shadowRoot.getElementById("free");
        if (input) input.value = "";
      });
    }

    _doSearch() {
      const q = (this._st.q || "").trim();
      if (!q) return;
      this._busy("search", async () => {
        this._st.results = null;
        const r = await this._service("search_products", { query: q, limit: Number(this._config.max_items) || 12 }, true);
        this._st.results = r?.products || [];
      });
    }

    _doRecipeSearch() {
      const q = (this._st.rq || "").trim();
      if (!q) return;
      this._busy("rsearch", async () => {
        this._st.recipes = null;
        const r = await this._service("search_recipes", { query: q, limit: Number(this._config.max_items) || 12 }, true);
        this._st.recipes = r?.recipes || [];
      });
    }

    // ---- render
    _render(force = false) {
      if (!this._config) return;
      const markup = this._markup();
      if (!force && markup === this._html) return;
      this._html = markup;
      const root = this.shadowRoot;
      const active = root.activeElement;
      const keep = active && active.id ? { id: active.id, s: active.selectionStart, e: active.selectionEnd } : null;
      const scrollers = [...root.querySelectorAll("[data-scroll]")].map((el) => [el.dataset.scroll, el.scrollLeft, el.scrollTop]);
      root.innerHTML = `<style>${STYLE}</style>${markup}`;
      for (const [key, left, top] of scrollers) {
        const el = root.querySelector(`[data-scroll="${key}"]`);
        if (el) { el.scrollLeft = left; el.scrollTop = top; }
      }
      for (const [id, val] of [["q", this._st.q], ["rq", this._st.rq], ["free", this._st.free]]) {
        const el = root.getElementById(id);
        if (el) el.value = val || "";
      }
      if (keep) {
        const el = root.getElementById(keep.id);
        if (el) { el.focus(); try { el.setSelectionRange(keep.s, keep.e); } catch (e) { /* not a text input */ } }
      }
    }

    _markup() {
      const h = this._hass;
      if (!h) return `<ha-card><div class="body muted">${esc(t("loading"))}</div></ha-card>`;
      const e = this._e || {};
      if (!e["sensor.status"] && !e["todo.shopping_list"]) {
        return `<ha-card><div class="head"><div class="brand">${LOGO}<div class="title">${esc(this._config.title)}</div></div><div style="height:12px"></div></div><div class="body"><div class="empty">${esc(t("missing"))}</div></div></ha-card>`;
      }
      const tabs = TABS.filter(([k]) => this._shown(k));
      if (!tabs.some(([k]) => k === this._tab)) this._tab = tabs[0]?.[0] || "list";
      const body = this[`_tab_${this._tab}`] ? this[`_tab_${this._tab}`]() : "";
      return `<ha-card><div class="ct">
        <div class="head">
          <div class="brand">${LOGO}<div class="title">${esc(this._config.title)}</div><div class="chips">${this._chips()}</div></div>
          <div class="tabs" role="tablist" data-scroll="tabs">${tabs.map(([k, ic]) => `<button class="tab ${k === this._tab ? "active" : ""}" role="tab" aria-selected="${k === this._tab}" data-a="tab" data-v="${k}">${icon(ic)}<span class="label">${esc(t(`tab_${k}`))}</span></button>`).join("")}</div>
        </div>
        <div class="body">${pendingVersion ? `<div class="notice">${esc(t("reload"))}</div>` : ""}${body}</div>
      </div></ha-card>${this._modal()}`;
    }

    _chips() {
      const out = [];
      const status = this._s("sensor.status");
      if (this._ok(status) && status.state !== "geen") {
        const states = T[LANG].states;
        const eta = this._s("sensor.delivery_eta");
        const label = this._ok(eta) ? `${time(eta.state)}` : states[status.state] || status.state;
        out.push(`<span class="chip ${status.state === "tijd_bekend" ? "warn" : ""}">${icon("mdi:truck-delivery")}${esc(label)}</span>`);
      }
      const store = this._s("sensor.store");
      if (this._ok(store)) {
        const open = store.state === "open";
        const a = store.attributes;
        out.push(`<span class="chip">${icon(open ? "mdi:store-check" : "mdi:store-off")}${esc(open ? `${t("open")} ${t("until")} ${a.closes_today || ""}` : t("closed"))}</span>`);
      }
      return out.join("");
    }

    _sectionTitle(text, ic, count = "", entity = "") {
      return `<h3>${icon(ic)}${esc(text)}${count !== "" ? `<span class="count">${esc(count)}</span>` : ""}${entity ? `<button class="iconbtn" data-a="more" data-v="${esc(entity)}" aria-label="info">${icon("mdi:dots-horizontal")}</button>` : ""}</h3>`;
    }

    _thumb(url, alt) {
      return this._config.show_images === false ? "" : `<div class="thumb">${img(url, alt)}</div>`;
    }

    _productTile(p, extra = "") {
      const st = this._st;
      const pid = p.product_id;
      const qty = st.qty[pid] || 1;
      const images = this._config.show_images !== false;
      const minis = pid ? `<button class="mini" data-a="info" data-v="${pid}" aria-label="${esc(t("product_info"))}">${icon(st.busy[`info-${pid}`] ? "mdi:loading" : "mdi:information-variant", st.busy[`info-${pid}`] ? "spin" : "")}</button>${this._s("sensor.favorites") ? `<button class="mini" data-a="fav" data-v="${pid}" aria-label="${esc(t("to_favorites"))}">${icon(st.busy[`fav-${pid}`] ? "mdi:loading" : "mdi:heart-outline", st.busy[`fav-${pid}`] ? "spin" : "")}</button>` : ""}` : "";
      const pic = images ? `<div class="pic">${img(p.image, p.title)}${p.bonus ? `<span class="bonus">${esc(p.bonus)}</span>` : ""}<div class="minis">${minis}</div></div>` : "";
      const busy = st.busy[`add-${pid}`];
      const add = pid ? `<div class="foot"><div class="stepper"><button data-a="qty" data-v="${pid}:-1" aria-label="-">−</button><span>${qty}</span><button data-a="qty" data-v="${pid}:1" aria-label="+">+</button></div><span class="grow"></span>
          ${images ? "" : `<div class="minis inline">${minis}</div>`}
          <button class="iconbtn add" data-a="addp" data-v="${pid}" data-t="${esc(p.title)}" aria-label="${esc(t("add"))}" ${busy ? "disabled" : ""}>${icon(busy ? "mdi:loading" : "mdi:cart-plus", busy ? "spin" : "")}</button></div>` : "";
      const priceLine = p.price != null ? `<div>${p.was ? `<span class="was">${money(p.was)}</span>` : ""}${price(p.price)}</div>` : "";
      return `<div class="tile">${pic}<div class="info">
        <div class="name">${esc(p.title)}</div>
        ${!images && p.bonus ? `<div><span class="bonus">${esc(p.bonus)}</span></div>` : ""}
        ${extra ? `<div>${extra}</div>` : ""}
        <div class="muted">${esc([p.size, p.unit_price].filter(Boolean).join(" · "))}</div>
        ${priceLine}${add}
      </div></div>`;
    }

    // ---- tab: list
    _tab_list() {
      const st = this._st;
      const e = this._e;
      const parts = [];
      // search
      let results = "";
      if (st.busy.search) results = `<div class="empty">${esc(t("loading"))}</div>`;
      else if (st.results && !st.results.length) results = `<div class="empty">${esc(t("no_results"))}</div>`;
      else if (st.results) results = `<div class="grid">${st.results.map((p) => this._productTile(p)).join("")}</div>`;
      parts.push(`<div class="section"><div class="search"><input id="q" type="search" placeholder="${esc(t("search_ph"))}" autocomplete="off" enterkeyhint="search"><button class="btn" data-a="search">${icon("mdi:magnify")}<span>${esc(t("search"))}</span></button></div>${results}</div>`);
      // shopping list
      const todo = e["todo.shopping_list"];
      if (todo) {
        const items = st.todo || [];
        const rows = items.map((i) => `<div class="row"><div class="grow name">${esc(i.summary)}</div><button class="iconbtn" data-a="tick" data-v="${esc(i.uid)}" aria-label="${esc(t("tick"))}">${icon(st.busy[`tick-${i.uid}`] ? "mdi:loading" : "mdi:check-circle-outline", st.busy[`tick-${i.uid}`] ? "spin" : "")}</button></div>`).join("");
        parts.push(`<div class="section">${this._sectionTitle(t("list"), "mdi:format-list-checks", items.length || "", todo)}
          <div class="search"><input id="free" type="text" placeholder="${esc(t("free_text_ph"))}" autocomplete="off" enterkeyhint="done"><button class="btn ghost" data-a="free" aria-label="${esc(t("add"))}">${icon("mdi:plus")}</button></div>
          ${items.length ? `<div class="list">${rows}</div>` : `<div class="empty">${esc(st.todo === null ? t("loading") : t("list_empty"))}</div>`}</div>`);
      }
      // regulars
      if (this._config.show_regulars !== false && e.regulars.length) {
        const rows = e.regulars.map((id) => {
          const s = this._hass.states[id];
          const q = Number(s.state) || 0;
          return `<div class="row"><div class="grow"><div class="name">${esc(String(s.attributes.friendly_name || "").replace(/^HA Appie\s+/, ""))}</div><div class="sub">${esc(s.attributes.besteld_in || "")}</div></div>
            <div class="stepper"><button data-a="reg" data-v="${esc(id)}|-1" aria-label="-">−</button><span>${q}</span><button data-a="reg" data-v="${esc(id)}|1" aria-label="+">+</button></div></div>`;
        }).join("");
        const addBtn = e["button.add_regulars"];
        const resetBtn = e["button.reset_quantities"];
        parts.push(`<div class="section">${this._sectionTitle(t("regulars"), "mdi:repeat", e.regulars.length)}
          <div class="muted">${esc(t("regulars_hint"))}</div><div class="list">${rows}</div>
          <div class="actions">${addBtn ? `<button class="btn" data-a="press" data-v="${esc(addBtn)}">${icon("mdi:cart-arrow-down")}${esc(t("regulars_add"))}</button>` : ""}${resetBtn ? `<button class="btn ghost" data-a="press" data-v="${esc(resetBtn)}">${icon("mdi:restore")}${esc(t("regulars_reset"))}</button>` : ""}</div></div>`);
      }
      // basket
      const basket = this._s("sensor.basket");
      if (this._ok(basket) && Number(basket.state) > 0) {
        const a = basket.attributes;
        const items = (a.items || []).map((x) => `<div class="row"><div class="grow name">${esc(x)}</div></div>`).join("");
        parts.push(`<div class="section">${this._sectionTitle(t("basket"), "mdi:basket-outline", basket.state, this._e["sensor.basket"])}
          ${a.total_price != null ? `<div class="kpis"><div class="kpi"><span class="label">${esc(t("total"))}</span><span class="value">${money(a.total_price)}</span></div>${a.discount ? `<div class="kpi"><span class="label">${esc(t("discount"))}</span><span class="value">${money(a.discount)}</span></div>` : ""}</div>` : ""}
          <div class="list">${items}</div></div>`);
      }
      return parts.join("");
    }

    // ---- tab: delivery
    _tab_delivery() {
      const status = this._s("sensor.status");
      const parts = [];
      if (!this._ok(status) || status.state === "geen") {
        parts.push(`<div class="hero"><div class="state">${icon("mdi:truck-outline")}${esc(t("no_delivery"))}</div></div>`);
      } else {
        const start = this._s("sensor.slot_start");
        const end = this._s("sensor.slot_end");
        const eta = this._s("sensor.delivery_eta");
        const until = this._s("sensor.order_closing_time");
        const label = T[LANG].states[status.state] || status.state;
        parts.push(`<div class="hero"><div class="state">${icon(status.state === "bezorgd" ? "mdi:check-circle" : "mdi:truck-delivery")}${esc(label)}</div>
          ${this._ok(start) ? `<div>${esc(t("slot"))}: <b>${esc(day(start.state))} ${esc(time(start.state))}${this._ok(end) ? `–${esc(time(end.state))}` : ""}</b></div>` : ""}
          ${this._ok(eta) ? `<div>${esc(t("eta"))}: <b>${esc(time(eta.state))}${eta.attributes.eta_end ? `–${esc(time(eta.attributes.eta_end))}` : ""}</b>${eta.attributes.message ? ` · ${esc(eta.attributes.message)}` : ""}</div>` : ""}
        </div>`);
        const k = [];
        if (this._ok(until)) k.push(`<div class="kpi"><span class="label">${esc(t("change_until"))}</span><span class="value">${esc(dayTime(until.state))}</span></div>`);
        const min = until?.attributes?.minimum_order_value;
        if (min != null) k.push(`<div class="kpi"><span class="label">${esc(t("minimum"))}</span><span class="value">${money(min)}</span></div>`);
        const op = this._s("sensor.order_products");
        if (this._ok(op)) k.push(`<div class="kpi"><span class="label">${esc(t("order"))}</span><span class="value">${esc(op.state)} ${esc(t("products"))}</span></div>`);
        if (k.length) parts.push(`<div class="kpis">${k.join("")}</div>`);
        if (until?.attributes?.has_invoice) {
          parts.push(`<div class="actions"><button class="btn" data-a="pdf" data-k="invoice" data-v="latest">${icon("mdi:file-pdf-box")}${esc(t("invoice"))}</button><button class="btn ghost" data-a="pdfsave" data-k="invoice" data-v="latest">${icon("mdi:content-save")}${esc(t("pdf_save"))}</button></div>`);
        }
        const items = op?.attributes?.products || [];
        if (items.length) parts.push(`<div class="section">${this._sectionTitle(t("order"), "mdi:cart-check", items.length)}<div class="list">${items.map((x) => `<div class="row"><div class="grow name">${esc(x)}</div></div>`).join("")}</div></div>`);
      }
      const free = this._s("sensor.next_free_slot");
      if (free && free.attributes.slots) {
        const slots = free.attributes.slots.slice(0, Number(this._config.max_items) || 12);
        parts.push(`<div class="section">${this._sectionTitle(t("free_slots"), "mdi:calendar-clock", slots.length)}<div class="list">${slots.map((s) => `<div class="row"><div class="grow">${esc(day(s.start))} ${esc(time(s.start))}–${esc(time(s.end))}</div>${s.price != null ? `<span>${money(s.price)}</span>` : ""}</div>`).join("") || `<div class="empty">${esc(t("none"))}</div>`}</div></div>`);
      }
      return parts.join("");
    }

    // ---- tab: bonus
    _tab_bonus() {
      const parts = [];
      const max = Number(this._config.max_items) || 12;
      const pers = this._s("sensor.bonus_personal");
      if (this._ok(pers)) {
        const a = pers.attributes;
        const period = a.period_start ? `${day(a.period_start)} – ${day(a.period_end)}` : "";
        let body;
        if (a.details) {
          body = `<div class="grid">${a.details.slice(0, max).map((o) => this._productTile(
            { product_id: o.product_id, title: o.title, image: o.image, price: o.price, was: o.was && o.was !== o.price ? o.was : null, bonus: o.discount || "Bonus" },
            o.activated === true ? `<span class="badge ok">${esc(t("activated"))}</span>` : o.activated === false ? `<span class="badge">${esc(t("not_activated"))}</span>` : "",
          )).join("")}</div>`;
        } else {
          body = `<div class="list">${(a.offers || []).slice(0, max * 2).map((o) => `<div class="row"><span class="bonus">Bonus</span><div class="grow name">${esc(o)}</div></div>`).join("")}</div>`;
        }
        parts.push(`<div class="section">${this._sectionTitle(t("personal_bonus"), "mdi:account-star", pers.state, this._e["sensor.bonus_personal"])}${period ? `<div class="muted">${esc(t("period"))}: ${esc(period)}</div>` : ""}${body}</div>`);
      }
      const prev = this._s("sensor.bonus_previous");
      if (this._ok(prev) && (prev.attributes.offers || []).length) {
        parts.push(`<div class="section">${this._sectionTitle(t("previous_bonus"), "mdi:history", prev.state, this._e["sensor.bonus_previous"])}<div class="list">${prev.attributes.offers.slice(0, max * 2).map((o) => `<div class="row"><span class="bonus">Bonus</span><div class="grow name">${esc(o)}</div></div>`).join("")}</div></div>`);
      }
      return parts.join("") || `<div class="empty">${esc(t("none"))}</div>`;
    }

    // ---- tab: receipts
    _tab_receipts() {
      const parts = [];
      const last = this._s("sensor.last_receipt");
      const amount = this._s("sensor.last_receipt_amount");
      const spent = this._s("sensor.spent_month");
      const saved = this._s("sensor.saved_month");
      const k = [];
      if (this._ok(spent)) k.push(`<div class="kpi"><span class="label">${esc(t("spent_month"))}</span><span class="value big">${money(spent.state)}</span></div>`);
      if (this._ok(saved)) k.push(`<div class="kpi"><span class="label">${esc(t("saved_month"))}</span><span class="value big">${money(saved.state)}</span></div>`);
      if (k.length) parts.push(`<div class="kpis">${k.join("")}</div>`);
      if (this._ok(last)) {
        const a = last.attributes;
        const lines = a.lines || [];
        const rows = lines.map((l) => `<div class="row">${this._thumb(l.image, l.name)}<div class="grow"><div class="name">${esc(l.name)}</div><div class="sub">${l.quantity && l.quantity !== 1 ? `${esc(String(l.quantity).replace(".", ","))} × ${money(l.price)}` : ""}</div></div><span>${money(l.amount)}</span>${l.product_id ? `<button class="iconbtn" data-a="addp" data-v="${l.product_id}" data-t="${esc(l.name)}" aria-label="${esc(t("add"))}">${icon("mdi:cart-plus")}</button>` : ""}</div>`).join("");
        const disc = (a.discounts || []).map((d) => `<div class="row"><span class="bonus">${esc(t("discount"))}</span><div class="grow name">${esc(d.name)}</div><span>${money(d.amount)}</span></div>`).join("");
        const pay = (a.payments || []).map((p) => `<div class="row"><div class="grow">${esc(t("payments"))}: ${esc(p.method)}</div><b>${money(p.amount)}</b></div>`).join("");
        parts.push(`<div class="section">${this._sectionTitle(t("last_receipt"), "mdi:receipt-text", dayTime(last.state), this._e["sensor.last_receipt"])}
          <div class="kpis"><div class="kpi"><span class="label">${esc(t("total"))}</span><span class="value">${this._ok(amount) ? money(amount.state) : ""}</span></div>${a.saved ? `<div class="kpi"><span class="label">${esc(t("saved"))}</span><span class="value">${money(a.saved)}</span></div>` : ""}</div>
          ${lines.length ? `<div class="list">${rows}${disc}${pay}</div>` : ""}
          ${a.receipt_id ? `<div class="actions"><button class="btn" data-a="pdf" data-k="receipt" data-v="${esc(a.receipt_id)}">${icon(this._st.busy["pdf-receipt"] ? "mdi:loading" : "mdi:file-pdf-box", this._st.busy["pdf-receipt"] ? "spin" : "")}${esc(t("pdf_open"))}</button><button class="btn ghost" data-a="pdfsave" data-k="receipt" data-v="${esc(a.receipt_id)}">${icon("mdi:content-save")}${esc(t("pdf_save"))}</button></div>` : ""}</div>`);
        const recent = (a.recent || []).slice(1, 1 + (Number(this._config.max_items) || 12));
        if (recent.length) {
          parts.push(`<div class="section">${this._sectionTitle(t("recent"), "mdi:receipt-text-clock-outline", recent.length)}<div class="list">${recent.map((r) => `<div class="row"><div class="grow">${esc(dayTime(r.date))}</div><b>${money(r.amount)}</b><button class="iconbtn" data-a="receipt" data-v="${esc(r.id)}" aria-label="open">${icon(this._st.busy[`receipt-${r.id}`] ? "mdi:loading" : "mdi:chevron-right", this._st.busy[`receipt-${r.id}`] ? "spin" : "")}</button></div>`).join("")}</div></div>`);
        }
      }
      const pm = spent?.attributes?.per_month;
      if (pm && Object.keys(pm).length) {
        const entries = Object.entries(pm).slice(0, 6).reverse();
        const top = Math.max(...entries.map(([, v]) => v), 1);
        parts.push(`<div class="section">${this._sectionTitle(t("per_month"), "mdi:chart-bar")}<div class="bars">${entries.map(([m, v]) => `<div class="bar"><span>${esc(dfmt(`${m}-01T12:00:00`, { month: "short", year: "2-digit" }))}</span><div class="track"><div class="fill" style="width:${Math.round((v / top) * 100)}%"></div></div><b>${money(v)}</b></div>`).join("")}</div></div>`);
      }
      return parts.join("") || `<div class="empty">${esc(t("none"))}</div>`;
    }

    // ---- tab: recipes
    _tab_recipes() {
      const st = this._st;
      const parts = [];
      const sel = this._s("select.recipe_select");
      if (sel && (sel.attributes.options || []).length) {
        const persons = this._s("number.recipe_persons");
        const add = this._e["button.recipe_add"];
        parts.push(`<div class="section">${this._sectionTitle(t("own_recipes"), "mdi:book-open-variant", sel.attributes.options.length, this._e["select.recipe_select"])}
          <div class="actions">${sel.attributes.options.map((o) => `<button class="btn ${o === sel.state ? "" : "ghost"} small" data-a="recsel" data-v="${esc(o)}">${esc(o)}</button>`).join("")}</div>
          ${this._ok(sel) ? `<div class="row"><div class="grow name"><b>${esc(sel.state)}</b></div>${this._ok(persons) ? `<div class="stepper"><button data-a="persons" data-v="-1">−</button><span>${esc(persons.state)}</span><button data-a="persons" data-v="1">+</button></div><span class="muted">${esc(t("persons"))}</span>` : ""}${add ? `<button class="btn" data-a="press" data-v="${esc(add)}">${icon("mdi:cart-arrow-down")}${esc(t("recipe_to_list"))}</button>` : ""}</div>` : ""}</div>`);
      }
      let results = "";
      if (st.busy.rsearch) results = `<div class="empty">${esc(t("loading"))}</div>`;
      else if (st.recipes && !st.recipes.length) results = `<div class="empty">${esc(t("no_results"))}</div>`;
      else if (st.recipes) {
        results = `<div class="grid">${st.recipes.map((r) => `<div class="tile">${this._config.show_images === false ? "" : `<div class="pic cover">${img(r.image, r.title)}</div>`}<div class="info"><div class="name">${esc(r.title)}</div>${r.minutes ? `<div class="muted">${icon("mdi:timer-outline")} ${esc(r.minutes)} ${esc(t("minutes"))}</div>` : ""}<div class="foot"><button class="btn ghost small" data-a="recipe" data-v="${esc(r.id)}">${icon(st.busy[`recipe-${r.id}`] ? "mdi:loading" : "mdi:book-open-page-variant", st.busy[`recipe-${r.id}`] ? "spin" : "")}${esc(t("ingredients"))}</button></div></div></div>`).join("")}</div>`;
      }
      parts.push(`<div class="section">${this._sectionTitle(t("allerhande"), "mdi:chef-hat")}<div class="search"><input id="rq" type="search" placeholder="${esc(t("recipe_ph"))}" autocomplete="off" enterkeyhint="search"><button class="btn" data-a="rsearch">${icon("mdi:magnify")}<span>${esc(t("search"))}</span></button></div>${results}</div>`);
      return parts.join("");
    }

    // ---- tab: store
    _tab_store() {
      const parts = [];
      const store = this._s("sensor.store");
      if (this._ok(store)) {
        const a = store.attributes;
        const open = store.state === "open";
        const todayKey = new Date().toLocaleDateString("sv-SE");
        const hours = Object.entries(a.hours || {}).filter(([d]) => d >= todayKey).slice(0, 7);
        parts.push(`<div class="hero"><div class="state">${icon(open ? "mdi:store-check" : "mdi:store-off")}${esc(a.store_name || "")}</div>
          <div><span class="badge ${open ? "ok" : ""}">${esc(open ? t("open") : t("closed"))}</span> ${a.opens_today ? `${esc(t("today"))} ${esc(a.opens_today)}–${esc(a.closes_today)}` : ""}</div>
          <div class="muted">${esc([a.street, a.city].filter(Boolean).join(", "))}</div></div>`);
        if (hours.length) parts.push(`<div class="section">${this._sectionTitle(t("hours"), "mdi:clock-outline")}<div class="hours">${hours.map(([d, h]) => `<span class="${d === todayKey ? "today" : ""}">${esc(dfmt(`${d}T12:00:00`, { weekday: "long", day: "numeric", month: "short" }))}</span><span class="${d === todayKey ? "today" : ""}">${esc(h || t("closed"))}</span>`).join("")}</div></div>`);
      }
      const bargains = this._s("sensor.bargains");
      if (bargains) {
        const items = (bargains.attributes.items || []).slice(0, Number(this._config.max_items) || 12);
        parts.push(`<div class="section">${this._sectionTitle(t("last_chance"), "mdi:timer-sand", this._ok(bargains) ? bargains.state : "", this._e["sensor.bargains"])}
          ${!this._ok(bargains) ? `<div class="empty">${esc(t("not_available"))}</div>` : items.length ? `<div class="list">${items.map((b) => `<div class="row"><span class="bonus">${b.percentage ? `-${esc(Math.round(b.percentage))}%` : esc(t("last_chance"))}</span><div class="grow"><div class="name">${esc(b.title)}</div><div class="sub">${esc([b.category, b.stock != null ? `${b.stock} ${t("stock")}` : "", b.expires ? `${t("expires")} ${day(b.expires)}` : ""].filter(Boolean).join(" · "))}</div></div><div>${b.was ? `<span class="was">${money(b.was)}</span>` : ""}${price(b.price)}</div></div>`).join("")}</div>` : `<div class="empty">${esc(t("none"))}</div>`}</div>`);
      }
      return parts.join("") || `<div class="empty">${esc(t("not_available"))}</div>`;
    }

    // ---- tab: bonus card
    _tab_card() {
      const card = this._s("sensor.bonus_card");
      const code = card?.attributes?.barcode;
      if (!code) return `<div class="empty">${esc(t("card_none"))}</div>`;
      const bars = ean13Valid(code) ? ean13Svg(code) : `<div style="color:#000;font:700 1.4rem monospace">${esc(code)}</div>`;
      return `<div class="barcode"><div class="label">${LOGO}Bonuskaart</div>${bars}</div><div class="muted">${esc(t("card_hint"))}</div>`;
    }

    // ---- modal
    _modal() {
      const m = this._st.modal;
      if (!m || !m.data) return "";
      let title = "";
      let body = "";
      if (m.kind === "recipe") {
        const r = m.data;
        title = r.title;
        body = `${r.image && this._config.show_images !== false ? `<img class="hero-img" src="${esc(r.image)}" alt="" referrerpolicy="no-referrer">` : ""}
          <div class="muted">${esc([r.persons ? `${r.persons} ${t("persons")}` : "", r.minutes ? `${r.minutes} ${t("minutes")}` : ""].filter(Boolean).join(" · "))}</div>
          <div class="actions"><button class="btn" data-a="import" data-v="${esc(r.id)}">${icon(this._st.busy[`import-${r.id}`] ? "mdi:loading" : "mdi:book-plus", this._st.busy[`import-${r.id}`] ? "spin" : "")}${esc(t("import"))}</button>${r.url ? `<a class="btn ghost" style="text-decoration:none" href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${icon("mdi:open-in-new")}${esc(t("open_ah"))}</a>` : ""}</div>
          <div class="section"><h3>${icon("mdi:format-list-bulleted")}${esc(t("ingredients"))}</h3><div class="list">${(r.ingredients || []).map((i) => `<div class="row"><div class="grow">${esc(i)}</div></div>`).join("")}</div></div>
          ${(r.steps || []).length ? `<div class="section"><h3>${icon("mdi:pot-steam-outline")}${esc(t("steps"))}</h3><ol class="steps">${r.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol></div>` : ""}`;
      } else if (m.kind === "receipt") {
        const r = m.data;
        title = t("tab_receipts");
        const recent = (this._s("sensor.last_receipt")?.attributes?.recent || []).find((x) => x.id === m.id);
        if (recent) title = `${dayTime(recent.date)} · ${money(recent.amount)}`;
        body = `<div class="list">${(r.lines || []).map((l) => `<div class="row">${this._thumb(l.image, l.name)}<div class="grow name">${esc(l.name)}</div><span>${money(l.amount)}</span></div>`).join("")}${(r.discounts || []).map((d) => `<div class="row"><span class="bonus">${esc(t("discount"))}</span><div class="grow">${esc(d.name)}</div><span>${money(d.amount)}</span></div>`).join("")}</div>
          ${r.saved ? `<div>${esc(t("saved"))}: <b>${money(r.saved)}</b></div>` : ""}
          <div class="actions"><button class="btn" data-a="pdf" data-k="receipt" data-v="${esc(m.id)}">${icon("mdi:file-pdf-box")}${esc(t("pdf_open"))}</button><button class="btn ghost" data-a="pdfsave" data-k="receipt" data-v="${esc(m.id)}">${icon("mdi:content-save")}${esc(t("pdf_save"))}</button></div>`;
      } else if (m.kind === "product") {
        const p = m.data;
        title = p.title;
        body = `${p.image && this._config.show_images !== false ? `<div class="tile"><div class="pic">${img(p.image, p.title)}${p.bonus ? `<span class="bonus">${esc(p.bonus)}</span>` : ""}</div></div>` : ""}
          <div class="row"><div class="grow muted">${esc([p.size, p.unit_price].filter(Boolean).join(" · "))}</div>${price(p.price)}</div>
          ${p.nutriscore ? `<div><span class="badge">Nutri-Score ${esc(p.nutriscore)}</span> ${(p.diet || []).map((d) => `<span class="badge ok">${esc(d)}</span>`).join(" ")}</div>` : ""}
          ${(p.allergens || []).length ? `<div><b>${esc(t("allergens"))}:</b> ${esc(p.allergens.join(", "))}</div>` : ""}
          ${p.summary ? `<div class="muted">${esc(String(p.summary).replace(/<[^>]*>/g, " "))}</div>` : ""}
          ${p.ingredients ? `<div class="muted">${esc(p.ingredients)}</div>` : ""}
          ${(p.nutrients || []).length ? `<div class="section"><h3>${icon("mdi:nutrition")}${esc(t("nutrition"))}</h3><div class="list">${p.nutrients.map((n) => `<div class="row"><div class="grow">${esc(n.name)}</div><span>${esc(n.value)}</span></div>`).join("")}</div></div>` : ""}`;
      }
      return `<div class="modal-back"><div class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="mhead"><div class="grow">${esc(title)}</div><button class="iconbtn" data-a="close" aria-label="${esc(t("close"))}">${icon("mdi:close")}</button></div><div class="mbody">${body}</div></div></div>`;
    }
  }

  defineElement("ha-appie-card", HaAppieCard);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === "ha-appie-card")) {
    window.customCards.push({
      type: "ha-appie-card",
      name: "HA Appie",
      description: "Albert Heijn: lijst, bezorging, bonus, kassabonnen, recepten, winkel en bonuskaart",
      preview: true,
      documentationURL: "https://github.com/HazlittM/ha_appie",
    });
  }
  console.info(`%c HA-APPIE-CARD %c v${VERSION} `, "color:#fff;background:#00a0e2;font-weight:bold", "color:#00a0e2;background:#fff;font-weight:bold");
})();
