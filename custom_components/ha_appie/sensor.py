"""Sensors: status of the current delivery and its booked time slot."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import AhConfigEntry
from .coordinator import AhCoordinator, AhExtraCoordinator
from .entity import AhEntity
from .model import STATES, Delivery, spent_in_month


def _slot(delivery: Delivery, t) -> datetime:
    return datetime.combine(delivery.day, t, tzinfo=dt_util.get_default_time_zone())


async def async_setup_entry(
    hass: HomeAssistant, entry: AhConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    c = entry.runtime_data.deliveries
    x = entry.runtime_data.extra
    async_add_entities(
        [
            AhStatusSensor(c),
            AhSlotSensor(c, "slot_start", lambda d: _slot(d, d.start)),
            AhSlotSensor(c, "slot_end", lambda d: _slot(d, d.end)),
            AhOrderProductsSensor(x, c),
            AhBasketSensor(x),
            AhLastReceiptSensor(x),
            AhLastReceiptAmountSensor(x),
            AhSpentMonthSensor(x),
            AhBonusSensor(x, "bonus_personal"),
            AhBonusSensor(x, "bonus_previous"),
        ]
    )


class AhStatusSensor(AhEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATES
    _attr_icon = "mdi:truck-delivery"

    def __init__(self, coordinator: AhCoordinator) -> None:
        super().__init__(coordinator, "status")

    @property
    def native_value(self) -> str:
        cur = self.coordinator.data.current
        return cur.state if cur else "geen"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        attrs: dict[str, Any] = {
            "upcoming": [d.day.isoformat() for d in data.deliveries if d.state in ("gepland", "tijd_bekend")],
        }
        if (cur := data.current) is not None:
            attrs.update(
                order_id=cur.order_id,
                ah_status=cur.status,
                method=cur.method,
                # Raw delivery.eta.estimated from AH; not understood yet, kept for diagnosis.
                eta_estimated=cur.eta,
            )
        return attrs


class AhSlotSensor(AhEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: AhCoordinator, key: str, getter: Callable[[Delivery], datetime]) -> None:
        super().__init__(coordinator, key)
        self._getter = getter

    @property
    def native_value(self) -> datetime | None:
        cur = self.coordinator.data.current
        return self._getter(cur) if cur else None


# ------------------------------------------------------------------ extra data
# List-type attributes are kept out of the recorder database (they can be long).


class AhOrderProductsSensor(AhEntity, SensorEntity):
    """Number of products in the current/next order, with the product names."""

    _attr_icon = "mdi:cart-check"
    _attr_native_unit_of_measurement = "producten"
    _unrecorded_attributes = frozenset({"products"})

    def __init__(self, extra: AhExtraCoordinator, deliveries: AhCoordinator) -> None:
        super().__init__(extra, "order_products")

    @property
    def native_value(self) -> int:
        return sum(i.quantity for i in self.coordinator.data.order_products)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"products": [f"{i.quantity}x {i.title}" for i in self.coordinator.data.order_products][:150]}


class AhBasketSensor(AhEntity, SensorEntity):
    _attr_icon = "mdi:basket"
    _attr_native_unit_of_measurement = "producten"
    _unrecorded_attributes = frozenset({"items"})

    def __init__(self, extra: AhExtraCoordinator) -> None:
        super().__init__(extra, "basket")

    @property
    def native_value(self) -> int:
        return sum(i.quantity for i in self.coordinator.data.basket)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"items": [f"{i.quantity}x {i.title}" for i in self.coordinator.data.basket][:150]}


def _latest_paid(data):
    return next((r for r in data.receipts if r.amount > 0), None)


class AhLastReceiptSensor(AhEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:receipt-text"

    def __init__(self, extra: AhExtraCoordinator) -> None:
        super().__init__(extra, "last_receipt")

    @property
    def native_value(self) -> datetime | None:
        r = _latest_paid(self.coordinator.data)
        return r.when if r else None


class AhLastReceiptAmountSensor(AhEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_suggested_display_precision = 2

    def __init__(self, extra: AhExtraCoordinator) -> None:
        super().__init__(extra, "last_receipt_amount")

    @property
    def native_value(self) -> float | None:
        r = _latest_paid(self.coordinator.data)
        return r.amount if r else None


class AhSpentMonthSensor(AhEntity, SensorEntity):
    """Sum of in-store receipts this month (based on the latest 50 receipts)."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_suggested_display_precision = 2

    def __init__(self, extra: AhExtraCoordinator) -> None:
        super().__init__(extra, "spent_month")

    @property
    def native_value(self) -> float:
        now = dt_util.now()
        return spent_in_month(self.coordinator.data.receipts, now.year, now.month, dt_util.get_default_time_zone())


class AhBonusSensor(AhEntity, SensorEntity):
    """Number of offers in a bonus section for the current bonus week."""

    _attr_icon = "mdi:tag-heart"
    _attr_native_unit_of_measurement = "aanbiedingen"
    _unrecorded_attributes = frozenset({"offers"})

    def __init__(self, extra: AhExtraCoordinator, key: str) -> None:
        super().__init__(extra, key)
        self._key = key

    def _section(self):
        d = self.coordinator.data
        return d.bonus_personal if self._key == "bonus_personal" else d.bonus_previous

    @property
    def native_value(self) -> int:
        return self._section().count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data
        return {
            "offers": self._section().items[:150],
            "period_start": d.bonus_start.isoformat() if d.bonus_start else None,
            "period_end": d.bonus_end.isoformat() if d.bonus_end else None,
        }
