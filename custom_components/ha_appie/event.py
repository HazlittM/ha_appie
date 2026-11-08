"""Event entity: fires when a delivery gets a time, is delivered or cancelled."""
from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AhConfigEntry
from .coordinator import AhCoordinator
from .entity import AhEntity
from .model import EVENT_TYPES


async def async_setup_entry(
    hass: HomeAssistant, entry: AhConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([AhDeliveryEvent(entry.runtime_data.deliveries)])


class AhDeliveryEvent(AhEntity, EventEntity):
    _attr_event_types = EVENT_TYPES
    _attr_icon = "mdi:truck-check"

    def __init__(self, coordinator: AhCoordinator) -> None:
        super().__init__(coordinator, "delivery")

    @callback
    def _handle_coordinator_update(self) -> None:
        for event_type, d in self.coordinator.data.events:
            self._trigger_event(
                event_type,
                {
                    "order_id": d.order_id,
                    "date": d.day.isoformat(),
                    "slot_start": d.start.isoformat(timespec="minutes"),
                    "slot_end": d.end.isoformat(timespec="minutes"),
                    "eta_estimated": d.eta,
                },
            )
        super()._handle_coordinator_update()
