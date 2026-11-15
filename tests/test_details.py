"""Run: python3 -I tests/test_details.py  (no Home Assistant needed). All data below is made up."""
import base64
import importlib.util
import sys
from datetime import date, datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "model", Path(__file__).parent.parent / "custom_components/ha_appie/model.py"
)
m = importlib.util.module_from_spec(spec)
sys.modules["model"] = m
spec.loader.exec_module(m)
tz = timezone.utc

# ---- amounts and garbage
assert m._amount({"amount": 1.234}) == 1.23 and m._amount("2,50") == 2.5 and m._amount(3) == 3.0
assert m._amount(None) is None and m._amount({}) is None and m._amount("x") is None and m._amount(True) is None

# ---- receipt details
rd = m.parse_receipt_details({"posReceiptDetails": {"id": "r1", "products": [
    {"id": 111, "quantity": 2, "name": "VOORBEELD MELK", "price": {"amount": 1.1}, "amount": {"amount": 2.2}},
    {"id": None, "quantity": 1.5, "name": "BANANEN", "price": None, "amount": {"amount": 1.0}},
    {"name": ""}, "junk"],
    "discounts": [{"name": "BONUS", "amount": {"amount": -0.5}}, {"name": "x"}, "y"],
    "payments": [{"method": "PIN", "amount": {"amount": 2.7}}]}})
assert [l.name for l in rd.lines] == ["VOORBEELD MELK", "BANANEN"], rd
assert rd.lines[0].pos_id == 111 and rd.lines[1].pos_id is None and rd.lines[1].quantity == 1.5
assert rd.discounts == [("BONUS", -0.5)] and rd.discount_total == 0.5 and rd.payments == [("PIN", 2.7)]
assert m.ReceiptDetails.from_dict(rd.as_dict()) == rd                       # survives .storage
assert m.parse_receipt_details(None) is None and m.parse_receipt_details({"posReceiptDetails": {}}) is None

pdf = b"%PDF-1.4 test"
assert m.receipt_pdf_bytes({"posReceiptPdf": {"pdfBase64": base64.b64encode(pdf).decode()}}) == pdf
assert m.receipt_pdf_bytes({"posReceiptPdf": {"pdfBase64": base64.b64encode(b"<html>").decode()}}) is None
assert m.receipt_pdf_bytes(None) is None and m.pdf_from_base64("!!!") is None

assert m.convert_query([1, 22]) == "{ p1: productConvertId(sourceId: 1) p22: productConvertId(sourceId: 22) }"
assert m.parse_convert({"p1": 555, "p22": -1, "p3": None, "x": 1, "pbad": 2}) == {1: 555, 22: None, 3: None}
assert m.product_image({"images": [{"width": 800, "url": "a"}, {"width": 200, "url": "b"}, {"width": "?", "url": "c"}]}) == "b"
assert m.product_image({}) is None

rc = m.parse_receipts({"posReceiptsPage": {"posReceipts": [
    {"id": "r1", "dateTime": "2026-11-04T08:00:00Z", "totalAmount": {"amount": 20}},
    {"id": "r2", "dateTime": "2026-10-30T08:00:00Z", "totalAmount": {"amount": 10.5}},
    {"id": "r3", "dateTime": "2026-10-02T08:00:00Z", "totalAmount": {"amount": 0}}]}})
r2 = m.ReceiptDetails("r2", [], [("BONUS", -2.0)], [])
assert m.saved_in_month([rd, r2], rc, 2026, 11, tz) == 0.5 and m.saved_in_month([rd, r2], rc, 2026, 10, tz) == 2.0
assert m.spent_per_month(rc, tz) == {"2026-11": 20.0, "2026-10": 10.5}
print("details: kassabon-tests geslaagd")

# ---- personal bonus
offers = m.parse_bonus_offers({"bonusGroupOrProducts": [
    {"product": {"webshopId": 9, "brand": "AH", "title": "Voorbeeldkaas", "bonusMechanism": "25% korting",
                 "currentPrice": 2.0, "priceBeforeBonus": 2.5, "activationStatus": "ACTIVATED",
                 "images": [{"width": 200, "url": "img"}]}},
    {"bonusGroup": {"segmentDescription": "Alle thee", "discountLabels": [{"defaultDescription": "2e halve prijs"}],
                    "activationStatus": "ACTIVATABLE"}},
    {"bonusGroup": {}}, "junk"]})
assert [o.title for o in offers] == ["AH Voorbeeldkaas", "Alle thee", "Bonus"], offers
assert offers[0].activated is True and offers[1].activated is False and offers[2].activated is None
assert offers[0].price == 2.0 and offers[0].was == 2.5 and offers[0].image == "img" and offers[1].discount == "2e halve prijs"
assert m.parse_bonus_offers(None) == []
print("details: bonus-tests geslaagd")

# ---- delivery
od = m.parse_order_details({"orderId": 42, "orderState": "SUBMITTED", "closingTime": "2026-11-12T22:59:00Z",
                            "invoiceId": "", "cancellable": True, "groupedProductsInTaxonomy": [
                                {"orderedProducts": [{"quantity": 2}, {"quantity": "x"}]}, {"orderedProducts": [{"quantity": 1}]}]})
assert od.order_id == 42 and od.products == 3 and od.invoice_id is None and od.cancellable
assert od.closing_time == datetime(2026, 11, 12, 22, 59, tzinfo=timezone.utc)
assert m.parse_order_details({"orderId": 1, "invoiceId": 777}).invoice_id == "777"
assert m.parse_order_details(None) is None and m.parse_order_details({"orderId": "x"}) is None

tt = m.parse_track_trace({"order": {"delivery": {"trackAndTraceV2": {"type": "IN_TRANSIT", "message": "Onderweg",
                          "etaBlock": {"range": {"start": "2026-11-13T09:30:00Z", "end": "2026-11-13T10:00:00Z"}}}}}})
assert tt.type == "IN_TRANSIT" and tt.eta_start.hour == 9 and tt.eta_end.minute == 0
assert m.parse_track_trace({"order": {"delivery": {"trackAndTraceV2": [{"type": "PREPARING"}]}}}).eta_start is None
assert m.parse_track_trace({"order": None}) is None and m.parse_track_trace(None) is None
assert m.parse_value_limits({"orderValueLimits": {"minimumOrderValue": {"amount": 50}, "submittable": False}}) == (50.0, False)
assert m.parse_value_limits(None) == (None, None)

sl = m.parse_delivery_slots({"orderDeliverySlots": [
    {"date": "x", "isFullyBooked": False, "slots": [
        {"startTime": "2026-11-14T17:00:00Z", "endTime": "2026-11-14T18:00:00Z", "isFullyBooked": True},
        {"startTime": "2026-11-14T07:00:00Z", "endTime": "2026-11-14T08:00:00Z", "serviceCharge": {"price": {"amount": 4.95}}},
        {"startTime": None}]},
    {"isFullyBooked": True, "slots": [{"startTime": "2026-11-15T07:00:00Z", "endTime": "2026-11-15T08:00:00Z"}]}, "junk"]})
assert [(s.start.day, s.start.hour, s.full) for s in sl] == [(14, 7, False), (14, 17, True), (15, 7, True)]
assert sl[0].price == 4.95 and m.parse_delivery_slots(None) == []
print("details: bezorg-tests geslaagd")

# ---- store and last chance
st = m.parse_store({"id": 1234, "name": "Voorbeeldstad Centrum", "storeType": "REGULAR",
                    "address": {"street": "Voorbeeldstraat", "houseNumber": "1", "city": "Voorbeeldstad"},
                    "openingDays": [[{"date": "2026-11-16", "openingHour": {"openFrom": "08:00", "openUntil": "21:00"}},
                                     {"date": "2026-11-17", "openingHour": None}],
                                    {"date": "2026-11-23T00:00:00", "openingHour": {"openFrom": "09:00:00", "openUntil": "18:00:00"}}]})
assert st.id == 1234 and st.street == "Voorbeeldstraat 1" and st.city == "Voorbeeldstad"
assert st.hours == {"2026-11-16": ("08:00", "21:00"), "2026-11-17": None, "2026-11-23": ("09:00", "18:00")}, st.hours
assert m.store_open_state(st, datetime(2026, 11, 16, 7, 59)) == (False, "08:00", "21:00")
assert m.store_open_state(st, datetime(2026, 11, 16, 8, 0))[0] is True
assert m.store_open_state(st, datetime(2026, 11, 16, 21, 0))[0] is False
assert m.store_open_state(st, datetime(2026, 11, 17, 12, 0)) == (False, None, None)
assert m.parse_store(None) is None and m.parse_store({"id": "abc"}) is None and m.parse_store({"id": 5}).name == "AH 5"

bg = m.parse_bargains({"bargainItems": [
    {"product": {"id": 7, "title": "Voorbeeldbrood"}, "categoryTitle": "Brood", "stock": "3",
     "markdown": {"markdownPercentage": 35, "markdownExpirationDate": "2026-11-15"},
     "bargainPrice": {"priceWas": "2.19", "priceNow": "1.42"}}, {"stock": "veel"}, "junk"]})
assert bg[0].price_now == 1.42 and bg[0].price_was == 2.19 and bg[0].stock == 3 and bg[0].percentage == 35
assert bg[1].stock is None and bg[1].title == "Onbekend product" and m.parse_bargains({"bargainItems": None}) == []
print("details: winkel-tests geslaagd")

# ---- favourites, cards
fl = m.parse_favorite_lists({"favoriteListV2": [
    {"id": "abc", "description": "Mijn favorieten", "totalSize": 2, "items": [{"productId": 1}, {"productId": "x"}, {}]},
    {"id": "def", "items": None}, {"description": "geen id"}]})
assert [(f.id, f.name, f.size, f.product_ids) for f in fl] == [("abc", "Mijn favorieten", 2, [1]), ("def", "Favorieten", 0, [])]
cards, ms = m.parse_member_cards({"member": {"cards": {"bonus": "2620000000001", "airmiles": None, "gall": "", "x": 1},
                                             "memberships": ["PREMIUM", None]}})
assert cards == {"bonus": "2620000000001"} and ms == ["PREMIUM"]
assert m.parse_member_cards(None) == ({}, [])
assert m.ean13_valid("4006381333931") and not m.ean13_valid("4006381333932") and not m.ean13_valid("123")
print("details: favorieten/kaart-tests geslaagd")

# ---- product details, search hits
gp = m.parse_product_graphql({"product": {"id": 5, "title": "AH Voorbeeldmelk", "salesUnitSize": "1 l",
    "icons": ["NUTRISCORE_B", "VEGETARIAN", "X"], "priceV2": {"now": {"amount": 1.0}, "was": {"amount": 1.29},
    "unitInfo": {"description": "prijs per liter", "price": {"formattedV2": "1.00"}}, "discount": {"description": "2 voor 2,00"}},
    "imagePack": {"medium": [{"url": "m"}], "small": {"url": "s"}}, "availability": {"isOrderable": True}}},
    {"product": {"tradeItem": {"gtin": "08710000000000", "nutritions": [{"nutrients": [
        {"name": "Energie", "value": "200 kJ"}, {"name": None}]}]}}})
assert gp["nutriscore"] == "B" and gp["diet"] == ["Vegetarisch"] and gp["image"] == "m" and gp["price"] == 1.0
assert gp["was"] == 1.29 and gp["bonus"] == "2 voor 2,00" and gp["unit_price"] == "prijs per liter 1.00"
assert gp["nutrients"] == [{"name": "Energie", "value": "200 kJ"}] and gp["gtin"] == "08710000000000"
assert m.parse_product_graphql({"product": {"id": 1}})["image"] is None and m.parse_product_graphql(None) is None
# AH sometimes sends lists where one object is expected: never crash
gl = m.parse_product_graphql({"product": [{"id": 7, "title": "X", "priceV2": [{"now": {"amount": 2}, "discount": [], "unitInfo": [{"description": "per kg", "price": [{"formattedV2": "9.99"}]}]}],
    "availability": [], "imagePack": [{"small": [{"url": "s"}]}], "icons": "NUTRISCORE_A"}]},
    {"product": [{"tradeItem": [{"gtin": "1", "nutritions": {"nutrients": [{"name": "Vet", "value": "1 g"}]}}]}]})
assert gl["product_id"] == 7 and gl["price"] == 2.0 and gl["unit_price"] == "per kg 9.99" and gl["image"] == "s"
assert gl["bonus"] is None and gl["nutrients"] == [{"name": "Vet", "value": "1 g"}] and gl["gtin"] == "1"
assert m.parse_product_graphql({"product": "x"}) is None and m.parse_product_graphql([1]) is None

h = m.search_hit({"webshopId": 3, "title": "AH Thee", "currentPrice": 1.0, "priceBeforeBonus": 1.5, "isBonus": True,
                  "bonusMechanism": "1+1"})
assert h["price"] == 1.0 and h["was"] == 1.5 and h["bonus"] == "1+1"
assert m.search_hit({"webshopId": 3, "title": "X", "priceBeforeBonus": 2})["was"] is None
assert m.search_hit({"title": "geen id"}) is None
print("details: product-tests geslaagd")

# ---- Allerhande
rs = m.parse_recipe_search({"recipeSearchV2": {"result": [
    {"id": 1, "title": "Voorbeeldpasta", "time": {"cook": 20}, "images": [{"url": "i"}]}, {"title": "geen id"}]}})
assert rs == [{"id": 1, "title": "Voorbeeldpasta", "minutes": 20, "image": "i"}]
rp = m.parse_recipe({"recipe": {"id": 1, "title": " Voorbeeldpasta ", "href": "/allerhande/recept/R-R1/x",
                                "servings": {"number": 2}, "ingredients": [{"text": "300 g spaghetti"}, {"text": None}],
                                "preparation": {"steps": ["Kook.", 3]}}})
assert rp["title"] == "Voorbeeldpasta" and rp["persons"] == 2 and rp["ingredients"] == ["300 g spaghetti"]
assert rp["url"] == "https://www.ah.nl/allerhande/recept/R-R1/x" and rp["steps"] == ["Kook."]
assert m.parse_recipe({"recipe": {"title": "x", "servings": {"number": True}}})["persons"] == 4
assert m.parse_recipe(None) is None
sg = m.parse_recipe_suggestions({"recipeProductSuggestionsV2": [
    {"ingredient": {"completeText": "300 g spaghetti "}, "productSuggestion": {"product": {"id": 62, "title": "AH Spaghetti", "salesUnitSize": "500 g"}}},
    {"ingredient": {"completeText": "zout"}, "productSuggestion": None}, "junk"]})
assert sg == {"300 g spaghetti": (62, "AH Spaghetti", "500 g")}
# the imported ingredient lines parse like typed ones, so pins can be matched on the raw text
assert m.parse_ingredient("300 g spaghetti").raw == "300 g spaghetti"
print("details: Allerhande-tests geslaagd")
