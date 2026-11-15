"""Sensors: status of the current delivery and its booked time slot."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import AhConfigEntry
from .const import (
    OPT_BARGAINS,
    OPT_DELIVERY_DETAILS,
    OPT_DELIVERY_SLOTS,
    OPT_FAVORITES,
    OPT_MEMBER_CARDS,
    OPT_RECEIPT_DETAILS,
    OPT_STORE,
    opt,
)
from .coordinator import AhCoordinator, AhExtraCoordinator, AhInfoCoordinator
from .entity import AhEntity
from .model import STATES, Delivery, saved_in_month, spent_in_month, spent_per_month, store_open_state


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
    rt = entry.runtime_data
    new: list[SensorEntity] = []
    if opt(entry, OPT_DELIVERY_DETAILS):
        new += [AhEtaSensor(c), AhClosingTimeSensor(c)]
    if opt(entry, OPT_RECEIPT_DETAILS):
        new.append(AhSavedMonthSensor(x, rt.receipts))
    i = rt.info
    if i is not None:
        if opt(entry, OPT_STORE) or opt(entry, OPT_BARGAINS):
            new.append(AhStoreSensor(i))
        if opt(entry, OPT_BARGAINS):
            new.append(AhBargainsSensor(i))
        if opt(entry, OPT_FAVORITES):
            new.append(AhFavoritesSensor(i))
        if opt(entry, OPT_MEMBER_CARDS):
            new.append(AhBonusCardSensor(i))
        if opt(entry, OPT_DELIVERY_SLOTS):
            new.append(AhFreeSlotSensor(i))
    async_add_entities(new)


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
        d = self.coordinator.data
        return {
            "items": [f"{i.quantity}x {i.title}" for i in d.basket][:150],
            "product_ids": [i.product_id for i in d.basket][:150],
            "total_price": d.basket_total,
            "discount": d.basket_discount,
        }


def _latest_paid(data):
    return next((r for r in data.receipts if r.amount > 0), None)


class AhLastReceiptSensor(AhEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:receipt-text"

    _unrecorded_attributes = frozenset({"lines", "discounts", "payments", "recent", "receipt_id"})

    def __init__(self, extra: AhExtraCoordinator) -> None:
        super().__init__(extra, "last_receipt")

    @property
    def native_value(self) -> datetime | None:
        r = _latest_paid(self.coordinator.data)
        return r.when if r else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Lines of the newest receipt (when receipt details are on) and the latest receipts."""
        data = self.coordinator.data
        r = _latest_paid(data)
        cache = self.coordinator.receipt_cache
        attrs: dict[str, Any] = {
            "receipt_id": r.id if r else None,
            "recent": [{"id": x.id, "date": x.when.isoformat(), "amount": x.amount}
                       for x in data.receipts if x.amount > 0][:20],
        }
        d = cache.details.get(r.id) if r else None
        if d is not None:
            attrs.update(
                lines=[{"name": l.name, "quantity": l.quantity, "price": l.price, "amount": l.amount,
                        "product_id": cache.webshop_for(l.pos_id), "image": cache.image_for(l.pos_id)}
                       for l in d.lines][:150],
                discounts=[{"name": n, "amount": a} for n, a in d.discounts][:50],
                payments=[{"method": m, "amount": a} for m, a in d.payments],
                saved=d.discount_total,
            )
        return attrs


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

    _unrecorded_attributes = frozenset({"per_month"})

    def __init__(self, extra: AhExtraCoordinator) -> None:
        super().__init__(extra, "spent_month")

    @property
    def native_value(self) -> float:
        now = dt_util.now()
        return spent_in_month(self.coordinator.data.receipts, now.year, now.month, dt_util.get_default_time_zone())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"per_month": spent_per_month(self.coordinator.data.receipts, dt_util.get_default_time_zone())}


class AhBonusSensor(AhEntity, SensorEntity):
    """Number of offers in a bonus section for the current bonus week."""

    _attr_icon = "mdi:tag-heart"
    _attr_native_unit_of_measurement = "aanbiedingen"
    _unrecorded_attributes = frozenset({"offers", "details"})

    def __init__(self, extra: AhExtraCoordinator, key: str) -> None:
        super().__init__(extra, key)
        self._key = key

    def _section(self):
        d = self.coordinator.data
        return d.bonus_personal if self._key == "bonus_personal" else d.bonus_previous

    def _offers(self):
        """Personal bonus from bonuspage/v1/personal (prices, activation) when AH gives it."""
        d = self.coordinator.data
        return d.personal_offers if self._key == "bonus_personal" and d.personal_offers else None

    @property
    def native_value(self) -> int:
        offers = self._offers()
        return len(offers) if offers is not None else self._section().count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data
        offers = self._offers()
        attrs: dict[str, Any] = {
            "offers": [o.title + (f" - {o.discount}" if o.discount else "") for o in offers][:150]
            if offers is not None else self._section().items[:150],
            "period_start": d.bonus_start.isoformat() if d.bonus_start else None,
            "period_end": d.bonus_end.isoformat() if d.bonus_end else None,
        }
        if offers is not None:
            attrs["details"] = [
                {"title": o.title, "discount": o.discount, "category": o.category, "activated": o.activated,
                 "price": o.price, "was": o.was, "product_id": o.product_id, "image": o.image}
                for o in offers][:100]
            attrs["activated"] = sum(1 for o in offers if o.activated)
        return attrs


# ------------------------------------------------------------------ v0.5 extras


class AhEtaSensor(AhEntity, SensorEntity):
    """Arrival window from AH track & trace (only on the delivery day)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:truck-fast"

    def __init__(self, coordinator: AhCoordinator) -> None:
        super().__init__(coordinator, "delivery_eta")

    @property
    def native_value(self) -> datetime | None:
        t = self.coordinator.data.track
        return t.eta_start if t else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        t = self.coordinator.data.track
        return {"eta_end": t.eta_end.isoformat() if t and t.eta_end else None,
                "track_type": t.type if t else None, "message": t.message if t else None}


class AhClosingTimeSensor(AhEntity, SensorEntity):
    """Until when the current order can still be changed in the AH app."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:cart-clock"

    def __init__(self, coordinator: AhCoordinator) -> None:
        super().__init__(coordinator, "order_closing_time")

    @property
    def native_value(self) -> datetime | None:
        d = self.coordinator.data.order_details
        cur = self.coordinator.data.current
        if d is None or cur is None or d.order_id != cur.order_id or cur.state not in ("gepland", "tijd_bekend"):
            return None
        return d.closing_time

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        d = data.order_details
        return {
            "minimum_order_value": data.minimum_order,
            "submittable": data.submittable,
            "cancellable": d.cancellable if d else None,
            "has_invoice": bool(d and d.invoice_id),
            "products": d.products if d else None,
        }


class AhSavedMonthSensor(AhEntity, SensorEntity):
    """Discounts on this month's in-store receipts (from the receipt details)."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:piggy-bank"

    def __init__(self, extra: AhExtraCoordinator, cache) -> None:
        super().__init__(extra, "saved_month")
        self._cache = cache

    @property
    def native_value(self) -> float:
        now = dt_util.now()
        return saved_in_month(list(self._cache.details.values()), self.coordinator.data.receipts,
                              now.year, now.month, dt_util.get_default_time_zone())


class AhStoreSensor(AhEntity, SensorEntity):
    """Your favourite AH store (as set in the AH app): open/closed and opening hours."""

    _attr_icon = "mdi:store"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["open", "closed"]
    _unrecorded_attributes = frozenset({"hours"})

    def __init__(self, info: AhInfoCoordinator) -> None:
        super().__init__(info, "store")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.store is not None

    @property
    def native_value(self) -> str | None:
        store = self.coordinator.data.store
        return ("open" if store_open_state(store, dt_util.now())[0] else "closed") if store else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        store = self.coordinator.data.store
        if store is None:
            return {}
        _, opens, closes = store_open_state(store, dt_util.now())
        return {
            "store_id": store.id, "store_name": store.name, "store_type": store.store_type, "city": store.city,
            "street": store.street, "opens_today": opens, "closes_today": closes,
            "hours": {d: (f"{h[0]}-{h[1]}" if h else None) for d, h in sorted(store.hours.items())[:14]},
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # open/closed changes with the clock, not only when the AH data refreshes
        self.async_on_remove(
            async_track_time_interval(self.hass, self._tick, timedelta(minutes=1))
        )

    @callback
    def _tick(self, _now) -> None:
        self.async_write_ha_state()


class AhBargainsSensor(AhEntity, SensorEntity):
    """Laatste kans (marked-down products) in your store."""

    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = "producten"
    _unrecorded_attributes = frozenset({"items"})

    def __init__(self, info: AhInfoCoordinator) -> None:
        super().__init__(info, "bargains")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.bargains is not None

    @property
    def native_value(self) -> int | None:
        b = self.coordinator.data.bargains
        return len(b) if b is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"items": [
            {"title": b.title, "category": b.category, "price": b.price_now, "was": b.price_was,
             "percentage": b.percentage, "expires": b.expires, "stock": b.stock, "product_id": b.product_id}
            for b in self.coordinator.data.bargains or []][:100]}


class AhFavoritesSensor(AhEntity, SensorEntity):
    _attr_icon = "mdi:heart"
    _attr_native_unit_of_measurement = "producten"
    _unrecorded_attributes = frozenset({"lists"})

    def __init__(self, info: AhInfoCoordinator) -> None:
        super().__init__(info, "favorites")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.favorites is not None

    @property
    def native_value(self) -> int | None:
        f = self.coordinator.data.favorites
        return sum(x.size for x in f) if f is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"lists": [{"id": f.id, "name": f.name, "size": f.size, "product_ids": f.product_ids[:200]}
                          for f in self.coordinator.data.favorites or []]}


class AhBonusCardSensor(AhEntity, SensorEntity):
    """Bonus card: masked in the state; the full number (for the barcode) stays out of the database."""

    _attr_icon = "mdi:barcode"
    _unrecorded_attributes = frozenset({"barcode", "airmiles", "gall"})

    def __init__(self, info: AhInfoCoordinator) -> None:
        super().__init__(info, "bonus_card")

    @property
    def available(self) -> bool:
        return super().available and bool((self.coordinator.data.cards or {}).get("bonus"))

    @property
    def native_value(self) -> str | None:
        number = (self.coordinator.data.cards or {}).get("bonus")
        return f"•••• {number[-4:]}" if number else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        cards = self.coordinator.data.cards or {}
        return {"barcode": cards.get("bonus"), "airmiles": cards.get("airmiles"), "gall": cards.get("gall"),
                "memberships": self.coordinator.data.memberships}


class AhFreeSlotSensor(AhEntity, SensorEntity):
    """First free delivery moment for the address in the options."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-clock"
    _unrecorded_attributes = frozenset({"slots"})

    def __init__(self, info: AhInfoCoordinator) -> None:
        super().__init__(info, "next_free_slot")

    def _free(self):
        now = dt_util.utcnow()
        return [s for s in self.coordinator.data.slots or [] if not s.full and s.start > now]

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.slots is not None

    @property
    def native_value(self) -> datetime | None:
        free = self._free()
        return free[0].start if free else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"slots": [{"start": s.start.isoformat(), "end": s.end.isoformat(), "price": s.price}
                          for s in self._free()][:60]}
