"""Run: python3 -I tests/test_model.py  (no Home Assistant needed)."""
import importlib.util
import sys
from datetime import date
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "model", Path(__file__).parent.parent / "custom_components/ha_appie/model.py"
)
m = importlib.util.module_from_spec(spec)
sys.modules["model"] = m
spec.loader.exec_module(m)


def item(oid, status, day, eta=None):
    return {"orderId": oid, "delivery": {"status": status, "method": "HOME_DELIVERY", "eta": eta,
            "slot": {"date": day, "startTime": "09:00", "endTime": "11:00"}}}


def data(*items):
    return {"orderFulfillments": {"result": list(items)}}


today = date(2026, 11, 7)
ds = m.parse_deliveries(data(
    item(2, "SUBMITTED", "2026-11-13"), item(1, "SUBMITTED_WITH_SIMACAN_ETA", "2026-11-07"),
    item(0, "DELIVERED", "2026-10-30"), {"orderId": 9, "delivery": None}, {"junk": 1}))
assert [d.order_id for d in ds] == [0, 1, 2], ds           # sorted, junk skipped
assert [d.state for d in ds] == ["bezorgd", "tijd_bekend", "gepland"]
assert m.pick_current(ds, today).order_id == 1             # open today
assert m.is_delivery_day(ds, today)

done = m.parse_deliveries(data(item(1, "DELIVERED", "2026-11-07"), item(2, "SUBMITTED", "2026-11-13")))
assert m.pick_current(done, today).order_id == 1           # delivered today stays visible
assert not m.is_delivery_day(done, today)
assert m.pick_current(done, date(2026, 11, 8)).order_id == 2   # next day -> upcoming
assert m.pick_current([], today) is None
assert m.parse_deliveries(None) == [] and m.parse_deliveries({}) == []

prev = {1: "gepland", 2: "gepland"}
ev = m.detect_events(prev, m.parse_deliveries(data(item(1, "SUBMITTED_WITH_SIMACAN_ETA", "2026-11-07"), item(2, "SUBMITTED", "2026-11-13"))))
assert [(e, d.order_id) for e, d in ev] == [("tijd_bekend", 1)]
ev = m.detect_events({1: "tijd_bekend"}, m.parse_deliveries(data(item(1, "DELIVERED", "2026-11-07"))))
assert [e for e, _ in ev] == ["bezorgd"]
assert m.detect_events({1: "gepland"}, m.parse_deliveries(data(item(1, "CANCELLED", "2026-11-07"))))[0][0] == "geannuleerd"
assert m.detect_events({}, ds) == []                        # first refresh: no events
assert m.detect_events({1: "tijd_bekend"}, ds) == []        # unchanged: no events
assert m.parse_deliveries(data(item(5, "NIEUW_ONBEKEND", "2026-11-07")))[0].state == "onbekend"
assert m.parse_deliveries(data(item(5, "SUBMITTED", "2026-11-07", {"estimated": "10:20-10:50"})))[0].eta == "10:20-10:50"
print("model: alle tests geslaagd")

# ------------------------------------------------------------ extra data (v0.2)
from datetime import timezone
tz = timezone.utc
b = m.parse_basket({"basket": {"items": [{"quantity": 2, "product": {"brand": "AH", "title": "Melk"}}, {"quantity": 1, "product": None}, "x"]}})
assert [(i.title, i.quantity) for i in b] == [("AH Melk", 2), ("Onbekend product", 1)], b
assert m.parse_basket(None) == [] and m.parse_basket({"basket": None}) == []
assert m.parse_order_lines({"order": {"orderLines": [{"quantity": 3, "product": {"title": "Kaas"}}]}})[0].title == "Kaas"

rc = m.parse_receipts({"posReceiptsPage": {"posReceipts": [
    {"id": "a", "dateTime": "2026-09-04T08:47:00.000Z", "totalAmount": {"amount": 0}},
    {"id": "b", "dateTime": "2026-09-04T08:46:00.000Z", "totalAmount": {"amount": 90.71}},
    {"id": "c", "dateTime": "2026-08-30T07:45:00.000Z", "totalAmount": {"amount": 79.95}},
    {"id": "bad"}]}})
assert [r.id for r in rc] == ["a", "b", "c"]
assert m.spent_in_month(rc, 2026, 9, tz) == 90.71 and m.spent_in_month(rc, 2026, 8, tz) == 79.95
assert m.spent_in_month(rc, 2026, 10, tz) == 0.0

li = m.parse_list_items({"items": [
    {"description": "Brood", "quantity": 2},
    {"productDetails": {"product": {"webshopId": 123, "title": "Melk"}}, "quantity": 1},
    {"vagueTermDetails": {"searchTermValue": "kaas"}}]})
assert [i.uid for i in li] == ["txt:Brood", "prd:123:Melk", "txt:kaas"], li
assert m.payload_from_uid("txt:Brood%20wit")["description"] == "Brood wit"
p = m.payload_from_uid("prd:123:Melk")
assert p["productId"] == 123 and p["quantity"] == 0 and p["originCode"] == "PRD"
assert m.list_payload("Thee", 2) == {"description": "Thee", "quantity": 2, "type": "SHOPPABLE", "strikeThrough": False, "originCode": "TXT"}
try:
    m.payload_from_uid("rare:1"); raise SystemExit("verwacht ValueError")
except ValueError:
    pass

meta = {"periods": [
    {"bonusStartDate": "2026-11-02", "bonusEndDate": "2026-11-08", "tabs": []},
    {"bonusStartDate": "2026-11-09", "bonusEndDate": "2026-11-15", "tabs": [
        {"urlMetadataList": [{"bonusType": "PREVIOUSLY_BOUGHT", "url": "bonuspage/v2/section/previously-bought?x=1"}]},
        {"urlMetadataList": [{"bonusType": "PERSONAL", "url": "bonuspage/v2/section/personal?x=1"}]}]}]}
assert m.pick_bonus_period(meta, date(2026, 11, 7))["bonusStartDate"] == "2026-11-02"
assert m.pick_bonus_period(meta, date(2026, 12, 1)) is None and m.pick_bonus_period(None, today) is None
assert m.bonus_section_urls(m.pick_bonus_period(meta, date(2026, 11, 10))) == {
    "PREVIOUSLY_BOUGHT": "bonuspage/v2/section/previously-bought?x=1", "PERSONAL": "bonuspage/v2/section/personal?x=1"}
assert m.bonus_section_urls(None) == {}
bs = m.parse_bonus_section({"bonusGroupOrProducts": [
    {"product": {"brand": "AH", "title": "Pasta"}},
    {"bonusGroup": {"category": "Groente", "discountDescription": "2e halve prijs"}}, {"bonusGroup": {}}]})
assert bs.count == 3 and bs.items == ["AH Pasta", "Groente - 2e halve prijs", "Bonus"], bs
assert m.parse_bonus_section(None).count == 0
print("model: extra data tests geslaagd")

assert m._title({"brand": "AH", "title": "AH Courgette"}) == "AH Courgette"
assert m._title({"brand": "Spar", "title": "Melk"}) == "Spar Melk"
print("model: titel-test geslaagd")

# ------------------------------------------------- regulars, quantity, matching (v0.3)
assert m.parse_quantity("2 melk") == (2, "melk") and m.parse_quantity("3x kaas") == (3, "kaas")
assert m.parse_quantity("melk 2x") == (2, "melk") and m.parse_quantity("melk (x4)") == (4, "melk")
assert m.parse_quantity("melk (2x)") == (2, "melk") and m.parse_quantity("Courgette") == (1, "Courgette")
assert m.parse_quantity("0 melk")[0] == 1 and m.parse_quantity("7up") == (1, "7up")      # geen cijfer-voor-woord zonder spatie

BI = m.BasketItem
def order(*items): return [BI(t, q, pid) for pid, t, q in items]
o1 = order((1, "AH Bananen tros", 1), (2, "Halfvolle melk", 4), (3, "Cola", 1), (4, "Eenmalig", 1))
o2 = order((1, "AH Bananen tros", 2), (2, "Halfvolle melk", 4), (3, "Cola", 4))
o3 = order((1, "AH Bananen tros", 1), (2, "Halfvolle melk", 3), (1, "AH Bananen tros", 1))   # dubbele regel telt op
reg, known = m.compute_regulars([o1, o2, o3])
assert [(r.product_id, r.orders, r.of, r.default_qty) for r in reg][:2] == [(1, 3, 3, 2), (2, 3, 3, 4)], reg
assert 4 not in [r.product_id for r in reg]                 # eenmalig is geen vast product
assert known[3] == ("Cola", 2) and known[4] == ("Eenmalig", 1)
assert m.compute_regulars([o1], )[0] == []                  # te weinig historie
assert m.compute_regulars([])[1] == {}

K = {10: ("AH Courgette", 3), 11: ("De Zaanse Hoeve Halfvolle melk", 11), 12: ("AH Rundergehakt", 4)}
res = lambda *p: [{"webshopId": a, "title": b} for a, b in p]
# exact + eerder gekocht
assert m.best_product_match("Courgette", K, []) == (10, "AH Courgette")
assert m.best_product_match("halfvolle MELK", K, res((99, "AH Halfvolle melk"))) == (11, "De Zaanse Hoeve Halfvolle melk")
assert m.best_product_match("melk", K, res((99, "AH Volle melk"))) == (11, "De Zaanse Hoeve Halfvolle melk")   # gewoonte wint
# alleen zoekresultaten: relevantie-ruis ("Honig ... courgette ...") verliest van exacte naam
r = res((605446, "Honig Bakplaat mix aardappel, courgette & kip"), (4164, "AH Courgette"), (185202, "AH Biologisch Courgette"))
assert m.best_product_match("courgette", {}, r) == (4164, "AH Courgette")
# AH-merk en kortste naam bij gelijkspel; meervoud/enkelvoud
r = res((1, "Hertog Komkommer"), (2, "AH Komkommer"))
assert m.best_product_match("komkommers", {}, r) == (2, "AH Komkommer")
assert m.best_product_match("bananen", {}, res((5, "AH Bananen tros"), (6, "Banaan chips"))) == (5, "AH Bananen tros")
# niets past -> None (blijft gewone tekst)
assert m.best_product_match("xyzzy", K, res((1, "AH Courgette"))) is None
assert m.best_product_match("", K, []) is None and m.best_product_match("de", {}, []) is None
assert m.best_product_match("melk chocolade", K, res((7, "Chocolade melk"))) == (7, "Chocolade melk")
print("model: weeklijst/matching tests geslaagd")

assert m.best_product_match("kaas", {}, res((1, "AH Kaassouffle"), (2, "AH Jonge kaas plak"))) == (2, "AH Jonge kaas plak")
assert m.best_product_match("kaas", {}, res((1, "AH Kaassouffle"))) is None      # liever tekst laten staan dan fout raden
assert m.best_product_match("bonen", {}, res((3, "AH Witte bonen"))) == (3, "AH Witte bonen")
print("model: kaas-test geslaagd")
assert m.best_product_match("kaas", {}, res((1, "AH Zaanlander Kaas bitterballen"), (2, "Beemster Jonge kaas"))) == (2, "Beemster Jonge kaas")
print("model: kopwoord-test geslaagd")

# --- recepten
p = m.parse_ingredient
assert (p("400 g gehakt").amount, p("400 g gehakt").unit, p("400 g gehakt").name) == (400, "g", "gehakt")
assert (p("2 uien").amount, p("2 uien").unit, p("2 uien").name) == (2, None, "uien")
assert (p("½ tl zout").amount, p("½ tl zout").unit) == (0.5, "tl")
assert p("1,5 kg aardappelen").amount == 1.5 and p("1/2 komkommer").amount == 0.5
assert p("- 250 gram spaghetti").name == "spaghetti" and p("peper").amount is None
assert p("2-3 el olijfolie").amount == 2 and p("2 el olijfolie").name == "olijfolie"
assert p("Ingrediënten") is None and p("Voor de saus:") is None and p("  ") is None
assert p("1 blik tomatenblokjes").name == "tomatenblokjes" and p("3 tenen knoflook").unit == "tenen"
assert [i.name for i in m.parse_recipe_text("Ingrediënten\n400 g gehakt\n\n2 uien\nVoor de saus:\npeper")] == ["gehakt", "uien", "peper"]
assert m.scale_amount(400, 4, 6) == 600 and m.scale_amount(None, 4, 6) is None
assert m.format_amount(600, "g") == "600 g" and m.format_amount(1.5, "kg") == "1,5 kg" and m.format_amount(2, None) == "2"
assert m.packs_needed(600, "g", "500 g") == 2 and m.packs_needed(400, "g", "500 g") == 1
assert m.packs_needed(1.2, "kg", "500 g") == 3 and m.packs_needed(3, "dl", "1 l") == 1
assert m.packs_needed(7, None, "6 stuks") == 2 and m.packs_needed(2, "stuks", "3 stuks") == 1
assert m.packs_needed(2, "el", "500 ml") == 1 and m.packs_needed(None, None, "1 kg") == 1
assert m.packs_needed(3, None, "1 kg") == 1 and m.packs_needed(500, "g", None) == 1
print("model: recepten-tests geslaagd")

# --- recepten: strikte productkeuze
def hit(pid, title, size=None):
    return {"webshopId": pid, "title": title, "salesUnitSize": size}
sm = lambda q, hits, known=None: m.best_product_match(q, known or {}, hits, strict=True)
assert sm("pesto", [hit(1, "Dr. Oetker Ristorante pizza salami mozzarella pesto"), hit(2, "AH Groene pesto")])[0] == 2
assert sm("pasta", [hit(1, "AH Pasta Pestosaus")]) is None
assert sm("rode ui", [hit(1, "AH Rode bieten met ui"), hit(2, "AH Rode uien")])[0] == 2
assert sm("rode ui", [hit(1, "AH Rode bieten met ui")]) is None
assert sm("cherrytomaatjes", [hit(1, "AH Cherrytomaten")])[0] == 1
assert sm("eieren", [hit(1, "AH Biologisch Eieren S M L 4-pack")])[0] == 1
assert sm("AH kipfilet", [hit(1, "AH Scharrel kipfilet")])[0] == 1
assert "cherrytomaten" in m.search_variants("cherrytomaatjes") and "rode uien" in m.search_variants("AH rode ui")
assert m.parse_pack_size("ca. 125 g") == ("mass", 125.0)
print("model: strikte-keuze-tests geslaagd")

# --- typefouten en vertaallijst
assert sm("cremé fraise", [hit(1, "AH Creme fraiche light 15% vet"), hit(2, "De Zaanse Hoeve Creme fraiche")])[0] in (1, 2)
assert m.tokens("Lay's Paprika") == ["lays", "paprika"]
assert sm("lays paprika", [hit(1, "Lay's Paprika")])[0] == 1
assert sm("kaas", [hit(1, "AH Kaassouffle")]) is None
assert m.parse_alias("Cremé Fraise = creme fraiche") == ("creme fraise", "creme fraiche")
assert m.parse_alias("alleen een woord") is None
al = {"creme fraise": "creme fraiche", "lays": "Lay's"}
assert m.apply_aliases("cremé fraise", al) == "creme fraiche"
assert m.apply_aliases("lays paprika chips", al) == "Lay's paprika chips"
assert m.apply_aliases("melk", al) == "melk"
print("model: typfout/vertaal-tests geslaagd")

# --- grootste overeenkomst als laatste automatische stap
assert sm("lays paprika chips", [hit(1, "Lay's Paprika")])[0] == 1
assert sm("lays paprika chips", [hit(1, "Lay's Naturel"), hit(2, "Lay's Oven Baked Paprika"), hit(3, "Lay's Paprika")])[0] == 3
assert sm("pasta", [hit(1, "AH Pasta Pestosaus")]) is None          # één los woord kiest nooit een product
assert sm("kaas", [hit(1, "AH Kaassouffle")]) is None
assert sm("groene pesto basilicum", [hit(1, "AH Pasta Pestosaus"), hit(2, "AH Groene pesto")])[0] == 2
assert "lays paprika" in m.search_variants("lays paprika chips")
print("model: overeenkomst-tests geslaagd")
assert sm("zak lays paprika chips", [hit(1, "Lay's Paprika")])[0] == 1
print("model: verpakkingswoord-test geslaagd")
assert sm("zak lays paprika chips", [hit(1, "AH Stapel op chips paprika"), hit(2, "Lay's Paprika")])[0] == 2
assert sm("zak lays paprika chips", [hit(2, "Lay's Paprika"), hit(1, "AH Stapel op chips paprika")])[0] == 2
print("model: minste-afwijking-test geslaagd")
