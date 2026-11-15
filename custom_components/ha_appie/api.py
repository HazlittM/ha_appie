"""Minimal client for the unofficial Albert Heijn mobile API (aiohttp only).

Unofficial: AH can change or block this at any time. All AH specifics live in this file.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlencode

import aiohttp

from .model import (
    BasketItem,
    BonusSection,
    Delivery,
    ListItem,
    Receipt,
    bonus_section_urls,
    list_payload,
    parse_basket,
    parse_bonus_section,
    parse_deliveries,
    parse_list_items,
    parse_order_lines,
    parse_receipts,
    payload_from_uid,
    pick_bonus_period,
    _amount as parse_amount,
    convert_query,
    parse_bargains,
    parse_bonus_offers,
    parse_convert,
    parse_delivery_slots,
    parse_favorite_lists,
    parse_member_cards,
    parse_order_details,
    parse_product_graphql,
    parse_receipt_details,
    parse_recipe,
    parse_recipe_search,
    parse_recipe_suggestions,
    parse_store,
    parse_track_trace,
    parse_value_limits,
    pdf_from_base64,
    receipt_pdf_bytes,
    search_hit,
)

API = "https://api.ah.nl"
CLIENT_ID = "appie-ios"
CLIENT_VERSION = "9.28"
USER_AGENT = "Appie/9.28 (iPhone; iOS 17)"
LOGIN_URL = (
    f"https://login.ah.nl/login?client_id={CLIENT_ID}"
    "&redirect_uri=appie://login-exit&response_type=code"
)
TIMEOUT = aiohttp.ClientTimeout(total=25)

DELIVERIES_QUERY = (
    "{ orderFulfillments(status: ALL) { result { orderId delivery { status method "
    "eta { estimated } slot { date startTime endTime } } } } }"
)
MEMBER_QUERY = "{ member { id } }"
BASKET_QUERY = "{ basket { id items { quantity product { id title brand } } } }"
RECEIPTS_QUERY = (
    "{ posReceiptsPage(pagination: {offset: 0, limit: %d}) "
    "{ posReceipts { id dateTime totalAmount { amount } } } }"
)
ORDER_QUERY = "{ order(id: %d) { orderLines { quantity product { id title brand } } } }"
CLOSED_QUERY = (
    "{ orderFulfillments(status: CLOSED, size: 100) { result { orderId delivery "
    "{ status slot { date startTime endTime } } } } }"
)
SEARCH_PATH = "/mobile-services/product/search/v2"
LIST_PATH = "/mobile-services/shoppinglist/v2/items"
BONUS_PATH = "/mobile-services/"


# ---- v0.5: read-only extras. Never add checkout/cancel/reopen/revert mutations here.
RECEIPT_DETAILS_QUERY = (
    "query FetchReceipt($id: String!) { posReceiptDetails(id: $id) { id products { id quantity name "
    "price { amount } amount { amount } } discounts { name amount { amount } } "
    "payments { method amount { amount } } } }"
)
RECEIPT_PDF_QUERY = "query FetchPosReceiptPdf($id: String!) { posReceiptPdf(id: $id) { pdfBase64 } }"
TRACK_QUERY = (
    "query FetchOrderTrackTrace($orderId: Int!) { order(id: $orderId) { delivery { trackAndTraceV2 "
    "{ orderId type orderType message etaBlock { range { start end } } } } } }"
)
LIMITS_QUERY = (
    "query Limits($orderId: Int!) { orderValueLimits(orderId: $orderId) "
    "{ minimumOrderValue { amount } submittable } }"
)
SLOTS_QUERY = (
    "query Slots($address: MemberAddressInput!) { orderDeliverySlots(address: $address) { date isFullyBooked "
    "slots { startTime endTime isFullyBooked serviceCharge { price { amount } } } } }"
)
BASKET_TOTAL_QUERY = "{ basket { summary { quantity price { totalPrice { amount } discount { amount } } } } }"
_STORE_FIELDS = (
    "id name storeType address { street houseNumber city } "
    "openingDays { date openingHour { openFrom openUntil } }"
)
FAVOURITE_STORE_QUERY = "{ storesFavouriteStore { " + _STORE_FIELDS + " } }"
STORE_QUERY = "query FetchStore($storeId: Int!) { storesInformation(id: $storeId) { " + _STORE_FIELDS + " } }"
BARGAINS_QUERY = (
    "query BargainItems($storeId: String!) { bargainItems(storeId: $storeId) { product { id title brand "
    "salesUnitSize } categoryTitle markdown { markdownType markdownExpirationDate markdownPercentage } "
    "stock bargainPrice { priceWas priceNow } } }"
)
FAVORITES_QUERY = (
    "query Favs($ids: [String!]!) { favoriteListV2(ids: $ids) { id description totalSize items { id productId quantity } } }"
)
FAVORITE_ADD_MUTATION = (
    "mutation AddProductsToFavoriteList($favoriteListId: String!, $products: [FavoriteListProductMutation!]!) "
    "{ favoriteListProductsAddV2(id: $favoriteListId, products: $products) { status errorMessage } }"
)
MEMBER_CARDS_QUERY = "{ member { cards { bonus airmiles gall } memberships } }"  # never name/address/birth date
RECIPE_SEARCH_QUERY = (
    "query FetchRecipes($searchText: String, $size: PageSize, $recipeIds: [Int!]!) { recipeSearchV2("
    "searchText: $searchText, start: 0, size: $size, sortBy: MOST_RELEVANT, recipeIds: $recipeIds) "
    "{ result { id title time { cook } images(renditions: [D445X297]) { url } } } }"
)
RECIPE_QUERY = (
    "query FetchRecipe($id: Int!) { recipe(id: $id) { id title href cookTime servings { number } "
    "ingredients { text } preparation { steps } images(renditions: [D445X297]) { url } } }"
)
RECIPE_SUGGESTIONS_QUERY = (
    "query Suggest($id: Int!) { recipeProductSuggestionsV2(options: { recipeId: $id }) { ingredient { completeText } "
    "productSuggestion { product { id title salesUnitSize } } } }"
)
PRODUCT_QUERY = (  # subset of the app's FetchProductDetails (replaced REST detail/v4/fir, 404 since 2026-11)
    "query FetchProductDetails($productId: Int!) { product(id: $productId) { id title brand category summary icons "
    "salesUnitSize priceV2 { now { amount } was { amount } unitInfo { description price { formattedV2 } } "
    "discount { description } } availability { isOrderable } imagePack { medium { url } large { url } small { url } } } }"
)
NUTRITION_QUERY = (
    "query FetchProduct($productId: Int!) { product(id: $productId) { id tradeItem { gtin "
    "nutritions { nutrients { type name value } } } } }"
)
ORDER_PATH = "/mobile-services/order/v1/"
PRODUCT_PATH = "/mobile-services/product/"
WEBSHOP = {"x-application": "AHWEBSHOP"}


class AhError(Exception):
    """Base error."""


class AhAuthError(AhError):
    """Login/refresh rejected: the user has to log in again."""


class AhApiError(AhError):
    """Anything else that went wrong talking to AH."""


def extract_code(value: str) -> str:
    """Accept a bare code or the full appie://login-exit?code=... redirect."""
    value = value.strip()
    match = re.search(r"[?&]code=([^&#\s]+)", value)
    return match.group(1) if match else value


async def _request(
    session: aiohttp.ClientSession,
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        "x-client-name": CLIENT_ID,
        "x-client-version": CLIENT_VERSION,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)
    try:
        async with session.request(method, API + path, json=body, headers=headers, timeout=TIMEOUT) as resp:
            try:
                data = await resp.json(content_type=None)
            except (aiohttp.ContentTypeError, ValueError):
                data = None
            return resp.status, data
    except (aiohttp.ClientError, TimeoutError) as err:
        raise AhApiError(f"Connection problem: {err}") from err


async def _post(session, path, body, token=None):
    return await _request(session, "POST", path, body, token)


def _tokens(data: Any, old_refresh: str | None = None) -> dict[str, str]:
    if not isinstance(data, dict) or "access_token" not in data:
        raise AhApiError("Unexpected token response")
    refresh = data.get("refresh_token") or old_refresh
    if not refresh:
        raise AhApiError("No refresh token received")
    return {"access_token": data["access_token"], "refresh_token": refresh}


class AhClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_token: str,
        refresh_token: str,
        on_tokens: Callable[[dict[str, str]], Awaitable[None] | None] | None = None,
    ) -> None:
        self._session = session
        self._access = access_token
        self._refresh = refresh_token
        self._on_tokens = on_tokens
        self._refresh_lock = asyncio.Lock()  # refresh tokens are single-use: never refresh twice at once

    @staticmethod
    async def exchange_code(session: aiohttp.ClientSession, code: str) -> dict[str, str]:
        status, data = await _post(
            session, "/mobile-auth/v1/auth/token", {"clientId": CLIENT_ID, "code": code}
        )
        if status in (400, 401, 403):
            raise AhAuthError("Login code rejected (expired or already used?)")
        if status != 200:
            raise AhApiError(f"HTTP {status} while exchanging code")
        return _tokens(data)

    async def async_refresh(self) -> None:
        status, data = await _post(
            session=self._session,
            path="/mobile-auth/v1/auth/token/refresh",
            body={"clientId": CLIENT_ID, "refreshToken": self._refresh},
        )
        if status in (400, 401, 403):
            raise AhAuthError("Refresh token rejected")
        if status != 200:
            raise AhApiError(f"HTTP {status} while refreshing token")
        tokens = _tokens(data, self._refresh)
        self._access, self._refresh = tokens["access_token"], tokens["refresh_token"]
        if self._on_tokens:
            result = self._on_tokens(tokens)
            if result is not None:
                await result

    async def _async_refresh_once(self, used_token: str) -> None:
        """Refresh, unless another request already did while we waited."""
        async with self._refresh_lock:
            if self._access == used_token:
                await self.async_refresh()

    async def _authed(
        self, method: str, path: str, body: dict | None = None, headers: dict[str, str] | None = None
    ) -> Any:
        """Authenticated call; refreshes the token once on 401/403. Returns parsed JSON."""
        for attempt in (0, 1):
            used = self._access
            status, data = await _request(self._session, method, path, body, used, headers)
            if status in (401, 403) and attempt == 0:
                await self._async_refresh_once(used)
                continue
            break
        if status in (401, 403):
            raise AhAuthError("Not authorised")
        if status != 200:
            err = AhApiError(f"HTTP {status} from {path.split('?')[0]}")
            err.status = status
            raise err
        return data

    async def _graphql(self, query: str, variables: dict | None = None) -> dict:
        body: dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables
        data = await self._authed("POST", "/graphql", body)
        if not isinstance(data, dict):
            raise AhApiError("Unexpected GraphQL response")
        if data.get("errors") and not data.get("data"):
            raise AhApiError(str(data["errors"][0].get("message", "GraphQL error"))[:200])
        return data.get("data") or {}

    async def async_member_id(self) -> str:
        data = await self._graphql(MEMBER_QUERY)
        try:
            return str(data["member"]["id"])
        except (KeyError, TypeError) as err:
            raise AhApiError("No member id in response") from err

    async def async_get_deliveries(self) -> list[Delivery]:
        return parse_deliveries(await self._graphql(DELIVERIES_QUERY))

    # ------------------------------------------------------------ extra data

    async def async_get_basket(self) -> list[BasketItem]:
        return parse_basket(await self._graphql(BASKET_QUERY))

    async def async_get_receipts(self, limit: int = 50) -> list[Receipt]:
        return parse_receipts(await self._graphql(RECEIPTS_QUERY % limit))

    async def async_get_order_lines(self, order_id: int) -> list[BasketItem]:
        return parse_order_lines(await self._graphql(ORDER_QUERY % int(order_id)))

    async def async_get_list(self) -> list[ListItem]:
        return parse_list_items(await self._authed("GET", LIST_PATH))

    async def async_add_list_item(
        self, description: str, quantity: int = 1, product_id: int | None = None
    ) -> None:
        await self.async_add_list_items([list_payload(description, quantity, product_id)])

    async def async_add_list_items(self, payloads: list[dict]) -> None:
        if payloads:
            await self._authed("PATCH", LIST_PATH, {"items": payloads})

    async def async_search_products(self, query: str, limit: int = 15) -> list[dict]:
        """Raw AH search hits ({webshopId, title, brand, ...}), most relevant first."""
        path = SEARCH_PATH + "?" + urlencode({"query": query, "sortOn": "RELEVANCE", "size": limit, "page": 0})
        data = await self._authed("GET", path, headers={"x-application": "AHWEBSHOP"})
        hits = (data or {}).get("products") or (data or {}).get("data") or [] if isinstance(data, dict) else []
        return [h for h in hits if isinstance(h, dict)]

    async def async_get_closed_deliveries(self) -> list[Delivery]:
        """Finished and cancelled orders (about the last 6 months)."""
        return parse_deliveries(await self._graphql(CLOSED_QUERY))

    async def async_remove_list_item(self, uid: str) -> None:
        await self._authed("PATCH", LIST_PATH, {"items": [payload_from_uid(uid)]})

    async def async_get_bonus(self, today) -> tuple[Any, BonusSection, BonusSection]:
        """(period, personal, previously_bought) for the bonus period containing `today`."""
        meta = await self._authed("GET", BONUS_PATH + "bonuspage/v3/metadata")
        period = pick_bonus_period(meta, today)
        urls = bonus_section_urls(period)
        empty = BonusSection(0, [])
        sections = []
        for kind in ("PERSONAL", "PREVIOUSLY_BOUGHT"):
            sections.append(
                parse_bonus_section(await self._authed("GET", BONUS_PATH + urls[kind])) if kind in urls else empty
            )
        return period, sections[0], sections[1]

    # ------------------------------------------------------------ v0.5 extras
    # All read-only, except adding to a favourite list (the user's own action).

    async def async_get_receipt_details(self, receipt_id: str):
        return parse_receipt_details(await self._graphql(RECEIPT_DETAILS_QUERY, {"id": str(receipt_id)}))

    async def async_get_receipt_pdf(self, receipt_id: str) -> bytes:
        pdf = receipt_pdf_bytes(await self._graphql(RECEIPT_PDF_QUERY, {"id": str(receipt_id)}))
        if pdf is None:
            raise AhApiError("No receipt PDF")
        return pdf

    async def async_convert_pos_ids(self, pos_ids: list[int]) -> dict[int, int | None]:
        return parse_convert(await self._graphql(convert_query(pos_ids))) if pos_ids else {}

    async def async_get_products(self, ids: list[int]) -> list[dict]:
        if not ids:
            return []
        query = "&".join(f"ids={int(i)}" for i in ids)
        data = await self._authed(
            "GET", f"{PRODUCT_PATH}search/v2/products?{query}&sortOn=INPUT_PRODUCT_IDS", headers=WEBSHOP
        )
        return [p for p in data if isinstance(p, dict)] if isinstance(data, list) else []

    async def async_get_personal_offers(self, monday) -> list:
        path = BONUS_PATH + "bonuspage/v1/personal?" + urlencode({"bonusStartDate": monday.isoformat()})
        return parse_bonus_offers(await self._authed("GET", path, headers=WEBSHOP))

    async def async_get_order_details(self, order_id: int):
        return parse_order_details(
            await self._authed("GET", f"{ORDER_PATH}{int(order_id)}/details-grouped-by-taxonomy", headers=WEBSHOP)
        )

    async def async_get_track_trace(self, order_id: int):
        return parse_track_trace(await self._graphql(TRACK_QUERY, {"orderId": int(order_id)}))

    async def async_get_value_limits(self, order_id: int):
        return parse_value_limits(await self._graphql(LIMITS_QUERY, {"orderId": int(order_id)}))

    async def async_get_invoice_pdf(self, invoice_id: str) -> bytes:
        """The invoice of a delivered order (raw bytes, not JSON)."""
        path = f"{ORDER_PATH}invoice/download?" + urlencode({"invoiceId": invoice_id})
        status, body = 0, b""
        for attempt in (0, 1):
            headers = {
                "User-Agent": USER_AGENT, "x-client-name": CLIENT_ID, "x-client-version": CLIENT_VERSION,
                "Authorization": f"Bearer {self._access}", "Accept": "application/pdf", **WEBSHOP,
            }
            try:
                async with self._session.get(API + path, headers=headers, timeout=TIMEOUT) as resp:
                    status, body = resp.status, await resp.read()
            except (aiohttp.ClientError, TimeoutError) as err:
                raise AhApiError(f"Connection problem: {err}") from err
            if status in (401, 403) and attempt == 0:
                await self._async_refresh_once(headers["Authorization"][7:])
                continue
            break
        if status in (401, 403):
            raise AhAuthError("Not authorised")
        if status != 200:
            raise AhApiError(f"HTTP {status} from invoice")
        if not body.startswith(b"%PDF"):
            pdf = pdf_from_base64(body.decode("ascii", "ignore").strip().strip(chr(34)))  # base64 in a JSON string
            if pdf is None:
                raise AhApiError("Invoice is not a PDF")
            body = pdf
        return body

    async def async_get_delivery_slots(self, address: dict) -> list:
        return parse_delivery_slots(await self._graphql(SLOTS_QUERY, {"address": address}))

    async def async_get_basket_total(self) -> tuple[float | None, float | None]:
        data = await self._graphql(BASKET_TOTAL_QUERY)
        price = (((data.get("basket") or {}).get("summary") or {}).get("price")) or {}
        return parse_amount(price.get("totalPrice")), parse_amount(price.get("discount"))

    async def async_get_store(self, store_id: int | None = None):
        if store_id:
            return parse_store((await self._graphql(STORE_QUERY, {"storeId": int(store_id)})).get("storesInformation"))
        data = (await self._graphql(FAVOURITE_STORE_QUERY)).get("storesFavouriteStore")
        if isinstance(data, list):
            data = data[0] if data else None
        return parse_store(data)

    async def async_get_bargains(self, store_id: int) -> list:
        return parse_bargains(await self._graphql(BARGAINS_QUERY, {"storeId": str(store_id)}))

    async def async_get_favorite_lists(self) -> list:
        return parse_favorite_lists(await self._graphql(FAVORITES_QUERY, {"ids": []}))

    async def async_add_to_favorite_list(self, list_id: str, product_id: int, quantity: int = 1) -> None:
        data = await self._graphql(FAVORITE_ADD_MUTATION, {
            "favoriteListId": list_id, "products": [{"productId": int(product_id), "quantity": int(quantity)}]})
        result = data.get("favoriteListProductsAddV2") or {}
        if result.get("status") not in (None, "SUCCESS"):
            raise AhApiError(str(result.get("errorMessage") or result.get("status"))[:200])

    async def async_get_member_cards(self):
        return parse_member_cards(await self._graphql(MEMBER_CARDS_QUERY))

    async def async_get_product_details(self, product_id: int) -> dict | None:
        variables = {"productId": int(product_id)}
        details = await self._graphql(PRODUCT_QUERY, variables)
        try:
            nutrition = await self._graphql(NUTRITION_QUERY, variables)
        except AhApiError:
            nutrition = None  # nutrition is a nice-to-have
        return parse_product_graphql(details, nutrition)

    async def async_get_product_by_gtin(self, gtin: str) -> dict | None:
        if not re.fullmatch(r"[0-9]{8,14}", gtin or ""):
            raise AhApiError("Invalid barcode")
        data = await self._authed("GET", f"{PRODUCT_PATH}search/v1/gtin/{gtin}", headers=WEBSHOP)
        return search_hit(data) if isinstance(data, dict) else None

    async def async_search_recipes(self, query: str, size: int = 12) -> list[dict]:
        return parse_recipe_search(await self._graphql(
            RECIPE_SEARCH_QUERY, {"searchText": query, "size": int(size), "recipeIds": []}))

    async def async_get_recipe(self, recipe_id: int) -> dict | None:
        return parse_recipe(await self._graphql(RECIPE_QUERY, {"id": int(recipe_id)}))

    async def async_get_recipe_suggestions(self, recipe_id: int) -> dict:
        return parse_recipe_suggestions(await self._graphql(RECIPE_SUGGESTIONS_QUERY, {"id": int(recipe_id)}))
