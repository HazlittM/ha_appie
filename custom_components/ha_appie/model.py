"""Data model and pure logic for Albert Heijn deliveries (no Home Assistant imports)."""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any
from urllib.parse import quote, unquote

# Raw AH status -> our state name.
STATUS_MAP = {
    "SUBMITTED": "gepland",
    "SUBMITTED_WITH_SIMACAN_ETA": "tijd_bekend",
    "DELIVERED": "bezorgd",
    "CANCELLED": "geannuleerd",
}
STATES = ["geen", "gepland", "tijd_bekend", "bezorgd", "geannuleerd", "onbekend"]
OPEN_STATES = {"gepland", "tijd_bekend"}
# State change -> event type.
EVENT_FOR_STATE = {"tijd_bekend": "tijd_bekend", "bezorgd": "bezorgd", "geannuleerd": "geannuleerd"}
EVENT_TYPES = list(EVENT_FOR_STATE.values())


@dataclass(frozen=True)
class Delivery:
    order_id: int
    status: str  # raw AH status
    method: str | None
    day: date
    start: time
    end: time
    eta: Any = None  # raw value of delivery.eta.estimated (not yet understood)

    @property
    def state(self) -> str:
        return STATUS_MAP.get(self.status, "onbekend")


def parse_deliveries(data: dict | None) -> list[Delivery]:
    """Turn the GraphQL `data` object into a sorted list of deliveries."""
    result = ((data or {}).get("orderFulfillments") or {}).get("result") or []
    out: list[Delivery] = []
    for item in result:
        try:
            d = item["delivery"]
            slot = d["slot"]
            out.append(
                Delivery(
                    order_id=int(item["orderId"]),
                    status=str(d["status"]),
                    method=d.get("method"),
                    day=date.fromisoformat(slot["date"]),
                    start=time.fromisoformat(slot["startTime"]),
                    end=time.fromisoformat(slot["endTime"]),
                    eta=(d.get("eta") or {}).get("estimated"),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out, key=lambda x: (x.day, x.start))


def pick_current(deliveries: list[Delivery], today: date) -> Delivery | None:
    """The delivery the sensors should describe.

    Open delivery today (or overdue) first, then one finished today (so "bezorgd"
    stays visible for the rest of the day), then the next upcoming one.
    """
    open_ = [d for d in deliveries if d.state in OPEN_STATES]
    if open_ and open_[0].day <= today:
        return open_[0]
    done_today = [d for d in deliveries if d.day == today and d.state in ("bezorgd", "geannuleerd")]
    if done_today:
        return done_today[-1]
    return open_[0] if open_ else None


def is_delivery_day(deliveries: list[Delivery], today: date) -> bool:
    return any(d.state in OPEN_STATES and d.day <= today for d in deliveries)


def detect_events(previous: dict[int, str], deliveries: list[Delivery]) -> list[tuple[str, Delivery]]:
    """Events for orders whose state changed since `previous` (order_id -> state).

    An empty `previous` (first refresh) never produces events.
    """
    if not previous:
        return []
    events = []
    for d in deliveries:
        old = previous.get(d.order_id)
        if old is not None and old != d.state and d.state in EVENT_FOR_STATE:
            events.append((EVENT_FOR_STATE[d.state], d))
    return events


# ---------------------------------------------------------------- extra data

@dataclass(frozen=True)
class BasketItem:
    title: str
    quantity: int
    product_id: int | None = None


@dataclass(frozen=True)
class Receipt:
    id: str
    when: datetime
    amount: float


@dataclass(frozen=True)
class ListItem:
    uid: str  # "prd:<id>:<quoted text>" or "txt:<quoted text>" (same scheme as python-appie)
    description: str
    quantity: int
    product_id: int | None = None


@dataclass(frozen=True)
class BonusSection:
    count: int
    items: list[str]


@dataclass
class ExtraData:
    basket: list[BasketItem] = field(default_factory=list)
    receipts: list[Receipt] = field(default_factory=list)
    shopping_list: list[ListItem] = field(default_factory=list)
    order_products: list[BasketItem] = field(default_factory=list)
    bonus_start: date | None = None
    bonus_end: date | None = None
    bonus_personal: BonusSection = field(default_factory=lambda: BonusSection(0, []))
    bonus_previous: BonusSection = field(default_factory=lambda: BonusSection(0, []))
    regulars: list["RegularProduct"] = field(default_factory=list)
    known: dict[int, tuple[str, int]] = field(default_factory=dict)  # product_id -> (title, times ordered)


def _title(product: dict | None) -> str:
    p = product or {}
    brand, title = p.get("brand"), p.get("title")
    if brand and title and title.lower().startswith(brand.lower()):
        brand = None  # AH titles usually already start with the brand
    return " ".join(x for x in (brand, title) if x) or "Onbekend product"


def parse_lines(lines: list | None) -> list[BasketItem]:
    """Basket items or order lines ({quantity, product{title brand}})."""
    out = []
    for line in lines or []:
        try:
            prod = line.get("product") or {}
            pid = prod.get("id")
            out.append(BasketItem(_title(prod), int(line.get("quantity") or 0), int(pid) if pid is not None else None))
        except (AttributeError, TypeError, ValueError):
            continue
    return out


def parse_basket(data: dict | None) -> list[BasketItem]:
    return parse_lines(((data or {}).get("basket") or {}).get("items"))


def parse_order_lines(data: dict | None) -> list[BasketItem]:
    return parse_lines(((data or {}).get("order") or {}).get("orderLines"))


def parse_receipts(data: dict | None) -> list[Receipt]:
    """Newest first. Receipts with amount 0 (returns/deposit) are kept; callers decide."""
    rows = ((data or {}).get("posReceiptsPage") or {}).get("posReceipts") or []
    out = []
    for r in rows:
        try:
            when = datetime.fromisoformat(str(r["dateTime"]).replace("Z", "+00:00"))
            amount = float((r.get("totalAmount") or {}).get("amount") or 0)
            out.append(Receipt(str(r["id"]), when, amount))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out, key=lambda x: x.when, reverse=True)


def spent_in_month(receipts: list[Receipt], year: int, month: int, tz) -> float:
    total = 0.0
    for r in receipts:
        local = r.when.astimezone(tz)
        if local.year == year and local.month == month and r.amount > 0:
            total += r.amount
    return round(total, 2)


def make_uid(description: str, product_id: int | None) -> str:
    enc = quote(description, safe="")
    return f"prd:{int(product_id)}:{enc}" if product_id is not None else f"txt:{enc}"


def parse_list_items(payload: dict | None) -> list[ListItem]:
    out = []
    for item in (payload or {}).get("items") or []:
        try:
            product = (item.get("productDetails") or {}).get("product") or {}
            pid = product.get("webshopId")
            desc = (
                item.get("description")
                or product.get("title")
                or (item.get("vagueTermDetails") or {}).get("searchTermValue")
                or f"Item {item.get('listItemId', '?')}"
            )
            out.append(ListItem(make_uid(desc, pid), desc, int(item.get("quantity", 1)),
                                int(pid) if pid is not None else None))
        except (AttributeError, TypeError, ValueError):
            continue
    return out


def list_payload(description: str, quantity: int = 1, product_id: int | None = None, remove: bool = False) -> dict:
    """One item for PATCH /shoppinglist/v2/items (quantity 0 removes)."""
    q = 0 if remove else quantity
    base = {"description": description, "quantity": q, "type": "SHOPPABLE", "strikeThrough": False}
    if product_id is not None:
        return {**base, "productId": int(product_id), "originCode": "PRD", "searchTerm": description}
    return {**base, "originCode": "TXT"}


def payload_from_uid(uid: str, remove: bool = True) -> dict:
    if uid.startswith("prd:"):
        _, pid, enc = uid.split(":", 2)
        return list_payload(unquote(enc), 1, int(pid), remove)
    if uid.startswith("txt:"):
        return list_payload(unquote(uid.split(":", 1)[1]), 1, None, remove)
    raise ValueError(f"Unsupported list item id: {uid}")


def pick_bonus_period(metadata: dict | None, today: date) -> dict | None:
    for p in (metadata or {}).get("periods") or []:
        try:
            if date.fromisoformat(p["bonusStartDate"]) <= today <= date.fromisoformat(p["bonusEndDate"]):
                return p
        except (KeyError, TypeError, ValueError):
            continue
    return None


def bonus_section_urls(period: dict | None) -> dict[str, str]:
    """bonusType (PERSONAL, PREVIOUSLY_BOUGHT, ...) -> relative url."""
    urls: dict[str, str] = {}
    for tab in (period or {}).get("tabs") or []:
        for m in tab.get("urlMetadataList") or []:
            if m.get("bonusType") and m.get("url") and m["bonusType"] not in urls:
                urls[m["bonusType"]] = m["url"]
    return urls


def parse_bonus_section(data: dict | None) -> BonusSection:
    """Summaries only (product title or discount text + category)."""
    items = []
    for entry in (data or {}).get("bonusGroupOrProducts") or []:
        if "product" in entry:
            items.append(_title(entry["product"]))
        elif "bonusGroup" in entry:
            g = entry["bonusGroup"] or {}
            items.append(" - ".join(x for x in (g.get("category"), g.get("discountDescription")) if x) or "Bonus")
    return BonusSection(len(items), items)


# ------------------------------------------------------- regulars & matching

@dataclass(frozen=True)
class RegularProduct:
    product_id: int
    title: str
    orders: int  # in how many of the considered orders it appeared
    of: int  # number of orders considered
    default_qty: int  # median quantity per order


def compute_regulars(
    orders: list[list[BasketItem]], max_orders: int = 8, min_share: float = 0.5, max_items: int = 30
) -> tuple[list[RegularProduct], dict[int, tuple[str, int]]]:
    """`orders`: delivered orders, oldest first. Returns (regulars, known products).

    A regular is a product in at least `min_share` of the last `max_orders` orders
    (and in at least 2). `known` counts over all given orders, for matching.
    """
    known: dict[int, list] = {}
    for items in orders:
        seen = set()
        for it in items:
            if it.product_id is None or it.product_id in seen:
                continue
            seen.add(it.product_id)
            rec = known.setdefault(it.product_id, [it.title, 0])
            rec[0], rec[1] = it.title, rec[1] + 1
    known_out = {pid: (t, n) for pid, (t, n) in known.items()}
    recent = orders[-max_orders:]
    if len(recent) < 2:
        return [], known_out
    need = max(2, -(-int(min_share * 100) * len(recent) // 100))  # ceil(share * n)
    stats: dict[int, tuple[str, list[int]]] = {}
    for items in recent:
        per_order: dict[int, int] = {}
        titles: dict[int, str] = {}
        for it in items:
            if it.product_id is None:
                continue
            per_order[it.product_id] = per_order.get(it.product_id, 0) + it.quantity
            titles[it.product_id] = it.title
        for pid, q in per_order.items():
            stats.setdefault(pid, (titles[pid], []))[1].append(q)
    regulars = []
    for pid, (title, qs) in stats.items():
        if len(qs) >= need:
            qs_sorted = sorted(qs)
            median = qs_sorted[len(qs_sorted) // 2]
            regulars.append(RegularProduct(pid, title, len(qs), len(recent), max(1, median)))
    regulars.sort(key=lambda r: (-r.orders, r.title.lower()))
    return regulars[:max_items], known_out


_QTY_PATTERNS = (
    re.compile(r"^\s*(\d{1,2})\s*[x×]?\s+(.+?)\s*$", re.I),  # "2 melk", "2x melk"
    re.compile(r"^\s*(.+?)\s*[(\[]?\s*[x×]\s*(\d{1,2})\s*[)\]]?\s*$", re.I),  # "melk x2", "melk (x2)"
    re.compile(r"^\s*(.+?)\s*[(\[]?\s*(\d{1,2})\s*[x×]\s*[)\]]?\s*$", re.I),  # "melk 2x", "melk (2x)"
)


def parse_quantity(text: str) -> tuple[int, str]:
    """"2 melk" / "melk 2x" / "melk (x2)" -> (2, "melk"); default quantity 1."""
    m = _QTY_PATTERNS[0].match(text)
    if m:
        return max(1, int(m.group(1))), m.group(2)
    for pat in _QTY_PATTERNS[1:]:
        m = pat.match(text)
        if m:
            return max(1, int(m.group(2))), m.group(1)
    return 1, text.strip()


def tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", text.replace("'", "").replace("’", ""))


def _stems(t: str) -> set[str]:
    """Crude Dutch stems: diminutives, plurals, doubled vowels ('tomaatjes', 'tomaten' -> 'tomat')."""
    out = {t}
    for suf in ("tjes", "jes", "tje", "je", "en", "s"):
        if t.endswith(suf) and len(t) - len(suf) >= 4:
            out.add(t[: -len(suf)])
    return {re.sub(r"(a)a|(e)e|(o)o|(u)u", lambda m: next(g for g in m.groups() if g), x) for x in out}


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _tok_match(q: str, c: str, fuzzy: bool = False) -> bool:
    if q == c:
        return True
    if fuzzy and min(len(q), len(c)) >= 6 and _edit_distance(q, c) <= 2:  # typos: 'fraise' ~ 'fraiche'
        return True
    for a, b in ((q, c), (c, q)):  # short words: 'ui' / 'uien', 'ei' / 'eieren', 'tomaat' / 'tomaten'
        if b in (a + "en", a + "s", a + "n", a + "e"):
            return True
    if len(q) >= 5 and len(c) >= 5 and _stems(q) & _stems(c):
        return True
    if abs(len(q) - len(c)) > 2:  # only plural/singular-like differences, not "kaas" vs "kaassouffle"
        return False
    n = 0
    for a, b in zip(q, c):
        if a != b:
            break
        n += 1
    return n >= max(4, min(len(q), len(c)) - 1)


_PACKING_WORDS = {"zak", "zakken", "pak", "pakken", "fles", "flessen", "pot", "potten", "doos", "bak", "bakje", "kuipje", "tros"}


def _strict_key(q: list[str], ct: list[str], n: int, pos: int):
    """Similarity of a product title to an ingredient (recipes); None when it is not a fair match.

    Best overlap wins. Not every typed word has to occur ('lays paprika chips' ~ "Lay's Paprika"),
    but 60% must, the matching words must sit together in the title and nothing may follow them
    ("Rode bieten met ui" is no 'rode ui', "Pasta Pestosaus" is no 'pasta').
    """
    ct = [t for t in ct]
    while len(ct) > 1 and (len(ct[-1]) <= 2 or ct[-1].isdigit() or ct[-1] in {"pack", "stuks"}):
        ct = ct[:-1]  # trailing size/pack words ('M', '10', '3-pack')
    hits = [any(_tok_match(qt, c, True) for qt in q) for c in ct]
    if not any(hits):
        return None
    cover = sum(1 for qt in q if any(_tok_match(qt, c, True) for c in ct)) / len(q)
    if cover < (1 if len(q) == 1 else 0.6):
        return None
    first = hits.index(True)
    last = len(hits) - 1 - hits[::-1].index(True)
    if not all(hits[first : last + 1]) or last != len(hits) - 1:
        return None
    prefix = [c for c in ct[:first] if c != "ah"]
    exact = 0 if not prefix and cover == 1 else 1
    extra = 0 if len(prefix) <= 2 else 1  # "AH Groene pesto" over "pizza salami mozzarella pesto"
    missing = round((1 - cover) * len(q)) + len(prefix)  # words that do not fit, on either side
    return (missing, -cover, exact, extra, 0 if n > 0 else 1, -n, 0 if ct[:1] == ["ah"] else 1, len(ct), pos)


def best_product_match(
    query: str,
    known: dict[int, tuple[str, int]],
    results: list[dict],
    strict: bool = False,
) -> tuple[int, str] | None:
    """Pick the product the user most likely means, or None if nothing fits all words.

    `known`: products ordered before. `results`: AH search hits ({webshopId, title, brand}).
    Products you ordered before win; then exact name (ignoring brand); then the word as last
    word of the name; then AH own brand;
    then the shortest name; then search relevance.
    """
    q = tokens(query)
    if strict:  # recipes: brand words are noise
        q = [t for t in q if t != "ah" and t not in _PACKING_WORDS] or q
    if not q:
        return None
    pool: dict[int, tuple[str, int, int]] = {}  # pid -> (title, times_ordered, position)
    for pid, (title, n) in known.items():
        pool[pid] = (title, n, 10_000)
    for pos, r in enumerate(results):
        try:
            pid, title = int(r["webshopId"]), str(r["title"])
        except (KeyError, TypeError, ValueError):
            continue
        old = pool.get(pid)
        pool[pid] = (old[0] if old else title, old[1] if old else 0, pos)
    best = None
    for pid, (title, n, pos) in pool.items():
        ct = tokens(title)
        if strict:
            key = _strict_key(q, ct, n, pos)
            if key is None:
                continue
            if best is None or key < best[0]:
                best = (key, pid, title)
            continue
        if not all(any(_tok_match(qt, c) for c in ct) for qt in q):
            continue
        rest = ct[1:] if ct and ct[0] == "ah" else ct
        exact = 0 if len(rest) == len(q) and all(_tok_match(a, b) for a, b in zip(q, rest)) else 1
        head = 0 if _tok_match(q[-1], ct[-1]) else 1  # Dutch head noun is last: "jonge kaas" over "kaas bitterballen"
        habit = 0 if n > 0 else 1  # what you ordered before wins
        key = (habit, exact, head, -n, 0 if ct[:1] == ["ah"] else 1, len(ct), pos)
        if best is None or key < best[0]:
            best = (key, pid, title)
    return (best[1], best[2]) if best else None



# --------------------------------------------------------------------- recipes

_FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}
_MASS = {"g": 1, "gr": 1, "gram": 1, "kg": 1000, "kilo": 1000}
_VOLUME = {"ml": 1, "cl": 10, "dl": 100, "l": 1000, "liter": 1000}
_COUNT_UNITS = {
    "el", "eetlepel", "eetlepels", "tl", "theelepel", "theelepels", "stuk", "stuks", "teen", "tenen",
    "bos", "bosje", "bosjes", "blik", "blikje", "blikjes", "pak", "pakje", "pakjes", "snufje",
    "plak", "plakje", "plakjes", "zakje", "zakjes", "zak", "zakken", "pakken", "fles", "flessen", "pot", "potten", "doos", "takje", "takjes", "handvol",
}
_AMOUNT_RE = re.compile(r"^(\d+(?:[.,]\d+)?)?\s*([½¼¾⅓⅔])?\s*(?:/\s*(\d+))?")


@dataclass
class IngredientLine:
    raw: str
    name: str
    amount: float | None = None  # in the recipe's base number of persons
    unit: str | None = None


def _to_float(text: str) -> float:
    return float(text.replace(",", "."))


def parse_ingredient(line: str) -> IngredientLine | None:
    """'400 g gehakt' / '2 uien' / '½ tl zout' / 'peper' -> IngredientLine (None for headings and blanks)."""
    raw = line.strip().lstrip("-•*·▢☐ ").strip()
    if not raw or raw.endswith(":"):
        return None
    if raw.lower().rstrip(":") in {"ingrediënten", "ingredienten", "benodigdheden", "bereiding"}:
        return None
    m = _AMOUNT_RE.match(raw)
    amount = None
    rest = raw
    if m and (m.group(1) or m.group(2)):
        amount = _to_float(m.group(1)) if m.group(1) else 0.0
        if m.group(2):
            amount += _FRACTIONS[m.group(2)]
        if m.group(3) and m.group(1) and not m.group(2) and float(m.group(3)):
            amount = _to_float(m.group(1)) / float(m.group(3))
        rest = raw[m.end():].strip()
        rest = re.sub(r"^[-–]\s*\d+(?:[.,]\d+)?\s*", "", rest)  # range "2-3": keep the first number
    unit = None
    parts = rest.split(None, 1)
    if amount is not None and parts and parts[0].lower().rstrip(".") in (set(_MASS) | set(_VOLUME) | _COUNT_UNITS):
        unit = parts[0].lower().rstrip(".")
        rest = parts[1] if len(parts) > 1 else ""
    rest = re.sub(r"^(van|à)\s+", "", rest.strip(), flags=re.I).strip(" ,.")
    if not rest:
        return None
    return IngredientLine(raw=raw, name=rest, amount=amount, unit=unit)


def parse_recipe_text(text: str) -> list[IngredientLine]:
    return [i for line in (text or "").splitlines() if (i := parse_ingredient(line))]


def scale_amount(amount: float | None, base: int, persons: int) -> float | None:
    if amount is None:
        return None
    return amount * persons / max(1, base)


def format_amount(amount: float | None, unit: str | None) -> str:
    if amount is None:
        return ""
    value = round(amount, 1)
    number = str(int(value)) if value == int(value) else str(value).replace(".", ",")
    return f"{number} {unit}" if unit else number


def _dimension(amount: float, unit: str | None) -> tuple[str, float]:
    u = (unit or "").lower()
    if u in _MASS:
        return "mass", amount * _MASS[u]
    if u in _VOLUME:
        return "volume", amount * _VOLUME[u]
    return "count", amount


def parse_pack_size(size: str | None) -> tuple[str, float] | None:
    """AH 'salesUnitSize' ('300 g', '1 kg', '6 stuks', '500 ml') -> (dimension, amount)."""
    m = re.match(r"^\s*(?:ca\.?\s*)?(\d+(?:[.,]\d+)?)\s*([a-zA-Z]+)", size or "")
    if not m:
        return None
    return _dimension(_to_float(m.group(1)), m.group(2))


def packs_needed(amount: float | None, unit: str | None, pack: str | None) -> int:
    """How many packs cover `amount`; 1 when it cannot be compared (spoons, unknown sizes)."""
    if amount is None or amount <= 0:
        return 1
    size = parse_pack_size(pack)
    need = _dimension(amount, unit)
    if size is None or size[0] != need[0] or size[1] <= 0:
        return 1
    if need[0] == "count" and unit and unit.lower() in _COUNT_UNITS and unit.lower() not in {"stuk", "stuks"}:
        return 1  # '2 el', '1 blik': not comparable to a pack of N pieces
    return max(1, math.ceil(need[1] / size[1] - 1e-9))


def search_variants(name: str) -> list[str]:
    """Spellings to try when searching for an ingredient: as typed, without brand, singular/plural, no diminutive."""
    base = " ".join(t for t in name.lower().split() if t != "ah")
    out = [name.strip(), base]
    words = base.split()
    if words:
        last = words[-1]
        stems = []
        if last.endswith("aatjes"):
            stems.append(last[:-6] + "aten")
        elif last.endswith("tjes"):
            stems.append(last[:-4] + "ten")
        elif last.endswith("jes"):
            stems.append(last[:-3] + "en")
        if not last.endswith(("s", "en")):
            stems += [last + "en", last + "s"]
        for v in stems:
            out.append(" ".join(words[:-1] + [v]))
    if len(words) >= 3:  # 'lays paprika chips' -> 'lays paprika': the last word is often just a category
        out.append(" ".join(words[:-1]))
    seen: list[str] = []
    for v in out:
        if v and v not in seen:
            seen.append(v)
    return seen


def parse_alias(text: str) -> tuple[str, str] | None:
    """'cremé fraise = creme fraiche' (or '->') -> (from, to), both normalised; None when malformed."""
    parts = re.split(r"\s*(?:=|->|→)\s*", text.strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    a, b = " ".join(tokens(parts[0])), parts[1].strip()
    return (a, b) if a and b else None


def apply_aliases(name: str, aliases: dict[str, str]) -> str:
    """Your own translations, applied to a whole name or to a phrase inside it (whole words)."""
    norm = " ".join(tokens(name))
    if norm in aliases:
        return aliases[norm]
    for key, value in sorted(aliases.items(), key=lambda kv: -len(kv[0])):
        padded = f" {norm} "
        if f" {key} " in padded:
            return " ".join(f"{padded.replace(f' {key} ', f' {value} ', 1)}".split())
    return name
