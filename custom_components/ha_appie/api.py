"""Minimal client for the unofficial Albert Heijn mobile API (aiohttp only).

Unofficial: AH can change or block this at any time. All AH specifics live in this file.
"""
from __future__ import annotations

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

    async def _authed(
        self, method: str, path: str, body: dict | None = None, headers: dict[str, str] | None = None
    ) -> Any:
        """Authenticated call; refreshes the token once on 401/403. Returns parsed JSON."""
        for attempt in (0, 1):
            status, data = await _request(self._session, method, path, body, self._access, headers)
            if status in (401, 403) and attempt == 0:
                await self.async_refresh()
                continue
            break
        if status in (401, 403):
            raise AhAuthError("Not authorised")
        if status != 200:
            err = AhApiError(f"HTTP {status} from {path.split('?')[0]}")
            err.status = status
            raise err
        return data

    async def _graphql(self, query: str) -> dict:
        data = await self._authed("POST", "/graphql", {"query": query})
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
