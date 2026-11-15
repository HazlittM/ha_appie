"""Data update coordinators."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AhApiError, AhAuthError, AhClient, AhError
from .const import (
    DOMAIN,
    OPT_BARGAINS,
    OPT_CITY,
    OPT_DELIVERY_DETAILS,
    OPT_DELIVERY_SLOTS,
    OPT_FAVORITES,
    OPT_HOUSE_EXTRA,
    OPT_HOUSE_NUMBER,
    OPT_MEMBER_CARDS,
    OPT_PERSONAL_BONUS,
    OPT_POSTAL_CODE,
    OPT_RECEIPT_DETAILS,
    OPT_RECEIPT_IMAGES,
    OPT_STORE,
    OPT_STORE_ID,
    OPT_STREET,
    SCAN_INTERVAL_DELIVERY_DAY,
    SCAN_INTERVAL_EXTRA,
    SCAN_INTERVAL_IDLE,
    SCAN_INTERVAL_INFO,
    opt,
)
from .model import (
    Bargain,
    BonusOffer,
    Delivery,
    ExtraData,
    FavoriteList,
    OrderDetails,
    ReceiptDetails,
    Slot,
    StoreInfo,
    TrackTrace,
    detect_events,
    is_delivery_day,
    pick_current,
    product_image,
)
from .regulars import Regulars

_LOGGER = logging.getLogger(__name__)
DETAILS_MAX_AGE = timedelta(minutes=15)  # order details (change-until, invoice) of the current order
RECEIPTS_WITH_DETAILS = 40  # newest receipts whose lines we keep (they never change)


async def _soft(name: str, coro):
    """Run an optional fetch: any AH error (also 401/403 on an endpoint we are not allowed to use)
    only makes that one value unavailable; it never breaks setup or triggers a re-login."""
    try:
        return await coro
    except AhError as err:
        _LOGGER.debug("Optional %s not available: %s", name, err)
    except (KeyError, TypeError, ValueError) as err:  # unexpected shape
        _LOGGER.debug("Optional %s had an unexpected answer: %s", name, err)
    return None


@dataclass
class AhData:
    deliveries: list[Delivery]
    current: Delivery | None
    events: list[tuple[str, Delivery]] = field(default_factory=list)
    order_details: OrderDetails | None = None
    track: TrackTrace | None = None
    minimum_order: float | None = None
    submittable: bool | None = None


class AhCoordinator(DataUpdateCoordinator[AhData]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_IDLE),
        )
        self.client = AhClient(
            async_get_clientsession(hass),
            entry.data["access_token"],
            entry.data["refresh_token"],
            on_tokens=self._save_tokens,
        )
        self._states: dict[int, str] = {}
        self._details_at: datetime | None = None

    def _save_tokens(self, tokens: dict[str, str]) -> None:
        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, **tokens}
        )

    async def _async_update_data(self) -> AhData:
        try:
            deliveries = await self.client.async_get_deliveries()
        except AhAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AhApiError as err:
            raise UpdateFailed(str(err)) from err

        today = dt_util.now().date()
        events = detect_events(self._states, deliveries)
        self._states = {d.order_id: d.state for d in deliveries}
        for event_type, d in events:
            _LOGGER.debug("Delivery %s -> %s", d.order_id, event_type)

        self.update_interval = timedelta(
            seconds=SCAN_INTERVAL_DELIVERY_DAY
            if is_delivery_day(deliveries, today)
            else SCAN_INTERVAL_IDLE
        )
        data = AhData(deliveries, pick_current(deliveries, today), events)
        if opt(self.config_entry, OPT_DELIVERY_DETAILS):
            await self._async_details(data, today)
        return data

    async def _async_details(self, data: AhData, today: date) -> None:
        """ETA, change-until and minimum order value of the current order (all optional)."""
        cur = data.current
        old = self.data
        if cur is None:
            return
        same = old is not None and old.order_details is not None and old.order_details.order_id == cur.order_id
        now = dt_util.utcnow()
        if same and self._details_at and now - self._details_at < DETAILS_MAX_AGE and not data.events:
            data.order_details, data.minimum_order, data.submittable = (
                old.order_details, old.minimum_order, old.submittable)
        else:
            data.order_details = await _soft("order details", self.client.async_get_order_details(cur.order_id))
            if cur.state in ("gepland", "tijd_bekend"):
                limits = await _soft("order value limits", self.client.async_get_value_limits(cur.order_id))
                if limits:
                    data.minimum_order, data.submittable = limits
            self._details_at = now
        if cur.state in ("gepland", "tijd_bekend") and cur.day <= today:
            data.track = await _soft("track & trace", self.client.async_get_track_trace(cur.order_id))
        elif cur.state == "bezorgd" and old is not None and old.track is not None and same:
            data.track = old.track


class ReceiptCache:
    """Receipt lines never change: keep them (and product photos) in .storage instead of refetching."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store = Store(hass, 1, f"{DOMAIN}_receipts_{entry_id}")
        self.details: dict[str, ReceiptDetails] = {}
        self.webshop: dict[int, int | None] = {}  # pos id -> webshop id (None: no match)
        self.images: dict[int, str | None] = {}  # webshop id -> image url

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        for rid, d in (data.get("details") or {}).items():
            try:
                self.details[rid] = ReceiptDetails.from_dict(d)
            except (KeyError, TypeError, ValueError):
                continue
        self.webshop = {int(k): (int(v) if v else None) for k, v in (data.get("webshop") or {}).items()}
        self.images = {int(k): v for k, v in (data.get("images") or {}).items()}

    async def async_save(self) -> None:
        await self._store.async_save({
            "details": {rid: d.as_dict() for rid, d in self.details.items()},
            "webshop": {str(k): v or 0 for k, v in self.webshop.items()},
            "images": {str(k): v for k, v in self.images.items()},
        })

    def image_for(self, pos_id: int | None) -> str | None:
        web = self.webshop.get(pos_id) if pos_id is not None else None
        return self.images.get(web) if web else None

    def webshop_for(self, pos_id: int | None) -> int | None:
        return self.webshop.get(pos_id) if pos_id is not None else None

    async def async_sync(self, client: AhClient, receipts, images: bool) -> None:
        keep = [r for r in receipts if r.amount > 0][:RECEIPTS_WITH_DETAILS]
        changed = False
        for r in keep:
            if r.id in self.details:
                continue
            d = await _soft("receipt details", client.async_get_receipt_details(r.id))
            if d is None:
                break  # endpoint unavailable: try again next time
            self.details[r.id] = d
            changed = True
        wanted = {r.id for r in keep}
        for rid in [k for k in self.details if k not in wanted]:
            del self.details[rid]
            changed = True
        if images and keep and keep[0].id in self.details:
            changed |= await self._async_images(client, self.details[keep[0].id])
        if changed:
            await self.async_save()

    async def _async_images(self, client: AhClient, details: ReceiptDetails) -> bool:
        """Photos for the lines of the newest receipt only (that is what the card shows)."""
        todo = [l.pos_id for l in details.lines if l.pos_id is not None and l.pos_id not in self.webshop][:60]
        changed = False
        if todo:
            converted = await _soft("product id conversion", client.async_convert_pos_ids(todo))
            if converted is None:
                return False
            for pos in todo:
                self.webshop[pos] = converted.get(pos)
            changed = True
        need = sorted({w for l in details.lines if (w := self.webshop.get(l.pos_id)) and w not in self.images})[:60]
        if need:
            products = await _soft("product photos", client.async_get_products(need))
            if products is None:
                return changed
            found = {int(p["webshopId"]): product_image(p) for p in products if p.get("webshopId") is not None}
            for w in need:
                self.images[w] = found.get(w)
            changed = True
        return changed


class AhExtraCoordinator(DataUpdateCoordinator[ExtraData]):
    """Slow-moving data: basket, receipts, shopping list, order contents and bonus."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, deliveries: AhCoordinator, regulars: "Regulars",
        receipts: ReceiptCache | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_extra",
            update_interval=timedelta(seconds=SCAN_INTERVAL_EXTRA),
        )
        self._deliveries = deliveries
        self.client = deliveries.client
        self.regulars = regulars
        self.receipt_cache = receipts or ReceiptCache(hass, entry.entry_id)

    async def _async_update_data(self) -> ExtraData:
        old = self.data or ExtraData()
        new = replace(old)
        today = dt_util.now().date()
        failures = 0
        parts = 0

        async def part(name, coro):
            """Run one fetch; keep the previous value if it fails, but surface auth errors."""
            nonlocal failures, parts
            parts += 1
            try:
                return await coro
            except AhAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except AhApiError as err:
                failures += 1
                _LOGGER.debug("Fetching %s failed: %s", name, err)
                return None

        if (v := await part("basket", self.client.async_get_basket())) is not None:
            new.basket = v
        if (v := await part("receipts", self.client.async_get_receipts())) is not None:
            new.receipts = v
        if (v := await part("shopping list", self.client.async_get_list())) is not None:
            new.shopping_list = v
        current = self._deliveries.data.current if self._deliveries.data else None
        if current is not None:
            if (v := await part("order", self.client.async_get_order_lines(current.order_id))) is not None:
                new.order_products = v
        else:
            new.order_products = []
        await part("history", self.regulars.async_sync(self.client))
        new.regulars, new.known = self.regulars.regulars, self.regulars.known
        if (v := await part("bonus", self.client.async_get_bonus(today))) is not None:
            period, new.bonus_personal, new.bonus_previous = v
            new.bonus_start = _iso(period, "bonusStartDate")
            new.bonus_end = _iso(period, "bonusEndDate")

        if parts and failures == parts:
            raise UpdateFailed("All requests failed")

        # ---- v0.5 extras: optional, never counted as failures
        entry = self.config_entry
        if (v := await _soft("basket total", self.client.async_get_basket_total())) is not None:
            new.basket_total, new.basket_discount = v
        if opt(entry, OPT_RECEIPT_DETAILS) and new.receipts:
            await self.receipt_cache.async_sync(self.client, new.receipts, bool(opt(entry, OPT_RECEIPT_IMAGES)))
        if opt(entry, OPT_PERSONAL_BONUS):
            monday = new.bonus_start or (today - timedelta(days=today.weekday()))
            offers = await _soft("personal bonus", self.client.async_get_personal_offers(monday))
            if offers is not None:
                new.personal_offers = offers
        return new


@dataclass
class InfoData:
    store: StoreInfo | None = None
    bargains: list[Bargain] | None = None
    favorites: list[FavoriteList] | None = None
    cards: dict[str, str] | None = None
    memberships: list[str] = field(default_factory=list)
    slots: list[Slot] | None = None


class AhInfoCoordinator(DataUpdateCoordinator[InfoData]):
    """Hourly, all optional: favourite store, last chance, favourite lists, cards, free slots.
    Never fails: each value is None (entity unavailable) when AH does not give it."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: AhClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_info",
            update_interval=timedelta(seconds=SCAN_INTERVAL_INFO),
        )
        self.client = client

    async def _async_update_data(self) -> InfoData:
        entry = self.config_entry
        new = InfoData()
        old = self.data or InfoData()
        if opt(entry, OPT_STORE) or opt(entry, OPT_BARGAINS):
            store_id = int(opt(entry, OPT_STORE_ID) or 0) or None
            new.store = await _soft("store", self.client.async_get_store(store_id)) or old.store
            if opt(entry, OPT_BARGAINS) and new.store is not None:
                new.bargains = await _soft("last chance", self.client.async_get_bargains(new.store.id))
        if opt(entry, OPT_FAVORITES):
            new.favorites = await _soft("favourite lists", self.client.async_get_favorite_lists())
        if opt(entry, OPT_MEMBER_CARDS):
            cards = await _soft("member cards", self.client.async_get_member_cards())
            if cards is not None:
                new.cards, new.memberships = cards
            else:
                new.cards, new.memberships = old.cards, old.memberships
        if opt(entry, OPT_DELIVERY_SLOTS) and (address := slot_address(entry.options)):
            new.slots = await _soft("delivery slots", self.client.async_get_delivery_slots(address))
        return new


def slot_address(options: dict) -> dict[str, Any] | None:
    """The address the user typed in the options (never read from the AH account)."""
    try:
        number = int(str(options.get(OPT_HOUSE_NUMBER) or "").strip())
    except ValueError:
        return None
    postal = str(options.get(OPT_POSTAL_CODE) or "").replace(" ", "").upper()
    street, city = str(options.get(OPT_STREET) or "").strip(), str(options.get(OPT_CITY) or "").strip()
    if not (postal and street and city):
        return None
    address: dict[str, Any] = {"street": street, "houseNumber": number, "postalCode": postal, "city": city,
                               "countryCode": "NLD"}
    if extra := str(options.get(OPT_HOUSE_EXTRA) or "").strip():
        address["houseNumberExtra"] = extra
    return address


def _iso(period: dict | None, key: str):
    try:
        return date.fromisoformat(period[key])
    except (TypeError, KeyError, ValueError):
        return None
