"""Product search state: a query, the AH results, the chosen result and a quantity."""
from __future__ import annotations

import logging
from collections.abc import Callable

from .api import AhClient, AhError
from .model import parse_pack_size

_LOGGER = logging.getLogger(__name__)


class ProductSearch:
    def __init__(self) -> None:
        self.query = ""
        self.results: dict[str, dict] = {}  # label -> {"pid", "title", "size"}
        self.selected: str | None = None
        self.quantity = 1
        self._listeners: list[Callable[[], None]] = []

    def async_add_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb)

    def _notify(self) -> None:
        for cb in list(self._listeners):
            cb()

    async def async_search(self, client: AhClient, query: str) -> None:
        self.query = query.strip()
        self.results, self.selected = {}, None
        if self.query:
            try:
                hits = await client.async_search_products(self.query, limit=20)
            except AhError as err:
                _LOGGER.warning("Product search failed: %s", err)
                hits = []
            for h in hits:
                try:
                    pid, title = int(h["webshopId"]), str(h["title"])
                except (KeyError, TypeError, ValueError):
                    continue
                size = h.get("salesUnitSize")
                price, normal = h.get("currentPrice"), h.get("priceBeforeBonus")
                shown = price if price is not None else normal
                parts = [title]
                if size:
                    parts.append(size)
                if shown is not None:
                    text = f"€{shown:.2f}".replace(".", ",")
                    parts.append(f"{text} BONUS" if price is not None and normal not in (None, price) else text)
                    pack = parse_pack_size(size)
                    if pack and pack[0] in ("mass", "volume") and pack[1] > 0:
                        per = f"€{shown / pack[1] * 1000:.2f}".replace(".", ",")
                        parts.append(f"{per}/{'kg' if pack[0] == 'mass' else 'l'}")
                label = " · ".join(parts)
                n = 2
                while label in self.results:  # identical label twice: keep both choosable
                    label, n = f"{' · '.join(parts)} #{n}", n + 1
                self.results[label] = {"pid": pid, "title": title, "size": size, "price": shown}
            self.selected = next(iter(self.results), None)
        self._notify()

    def select(self, label: str) -> None:
        if label in self.results:
            self.selected = label
            self._notify()

    def set_quantity(self, qty: int) -> None:
        self.quantity = max(1, int(qty))
        self._notify()

    def current(self) -> dict | None:
        return self.results.get(self.selected) if self.selected else None
