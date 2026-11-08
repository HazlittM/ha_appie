"""Regular ("weekly") products: derived from delivered orders, plus the user's chosen quantities."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .api import AhClient
from .const import DOMAIN
from .model import BasketItem, RegularProduct, compute_regulars

_LOGGER = logging.getLogger(__name__)
KEEP_ORDERS = 12  # delivered orders remembered (their lines never change)


class Regulars:
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store = Store(hass, 1, f"{DOMAIN}_{entry_id}")
        self._orders: dict[int, dict] = {}  # order_id -> {"date": iso, "items": [[pid, title, qty], ...]}
        self._quantities: dict[int, int] = {}  # chosen by the user; missing = default
        self.regulars: list[RegularProduct] = []
        self.known: dict[int, tuple[str, int]] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self._orders = {int(k): v for k, v in (data.get("orders") or {}).items()}
        self._quantities = {int(k): int(v) for k, v in (data.get("quantities") or {}).items()}
        self._recompute()

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "orders": {str(k): v for k, v in self._orders.items()},
                "quantities": {str(k): v for k, v in self._quantities.items()},
            }
        )

    def _recompute(self) -> None:
        ordered = sorted(self._orders.values(), key=lambda o: o["date"])
        history = [[BasketItem(t, q, pid) for pid, t, q in o["items"]] for o in ordered]
        self.regulars, self.known = compute_regulars(history)
        # forget chosen quantities of products that are no longer regular
        keep = {r.product_id for r in self.regulars}
        self._quantities = {k: v for k, v in self._quantities.items() if k in keep}

    async def async_sync(self, client: AhClient) -> None:
        """Fetch the lines of delivered orders we have not seen yet and recompute."""
        closed = [d for d in await client.async_get_closed_deliveries() if d.state == "bezorgd"]
        closed.sort(key=lambda d: d.day)
        changed = False
        for d in closed[-KEEP_ORDERS:]:
            if d.order_id in self._orders:
                continue
            lines = await client.async_get_order_lines(d.order_id)
            self._orders[d.order_id] = {
                "date": d.day.isoformat(),
                "items": [[i.product_id, i.title, i.quantity] for i in lines if i.product_id is not None],
            }
            changed = True
        wanted = {d.order_id for d in closed[-KEEP_ORDERS:]}
        for oid in [o for o in self._orders if o not in wanted]:
            del self._orders[oid]
            changed = True
        if changed or not self.regulars:
            self._recompute()
            await self._async_save()

    # ------------------------------------------------------------ quantities

    def default(self, product_id: int) -> int:
        return next((r.default_qty for r in self.regulars if r.product_id == product_id), 1)

    def quantity(self, product_id: int) -> int:
        return self._quantities.get(product_id, self.default(product_id))

    async def async_set_quantity(self, product_id: int, qty: int) -> None:
        self._quantities[product_id] = max(0, int(qty))
        await self._async_save()

    async def async_reset_quantities(self) -> None:
        self._quantities = {}
        await self._async_save()
