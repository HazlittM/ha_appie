"""Data update coordinator."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AhApiError, AhAuthError, AhClient
from .const import DOMAIN, SCAN_INTERVAL_DELIVERY_DAY, SCAN_INTERVAL_EXTRA, SCAN_INTERVAL_IDLE
from .model import Delivery, ExtraData, detect_events, is_delivery_day, pick_current
from .regulars import Regulars

_LOGGER = logging.getLogger(__name__)


@dataclass
class AhData:
    deliveries: list[Delivery]
    current: Delivery | None
    events: list[tuple[str, Delivery]] = field(default_factory=list)


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
        return AhData(deliveries, pick_current(deliveries, today), events)


class AhExtraCoordinator(DataUpdateCoordinator[ExtraData]):
    """Slow-moving data: basket, receipts, shopping list, order contents and bonus."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, deliveries: AhCoordinator, regulars: "Regulars"
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

    async def _async_update_data(self) -> ExtraData:
        old = self.data or ExtraData()
        new = ExtraData(
            basket=old.basket, receipts=old.receipts, shopping_list=old.shopping_list,
            order_products=old.order_products, bonus_start=old.bonus_start, bonus_end=old.bonus_end,
            bonus_personal=old.bonus_personal, bonus_previous=old.bonus_previous,
            regulars=old.regulars, known=old.known,
        )
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
        return new


def _iso(period: dict | None, key: str):
    from datetime import date

    try:
        return date.fromisoformat(period[key])
    except (TypeError, KeyError, ValueError):
        return None
