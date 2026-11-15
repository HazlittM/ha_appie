"""Receipt and invoice PDFs: fetched on demand, saved only where the user asks."""
from __future__ import annotations

from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .api import AhApiError


def _latest_receipt(rt):
    return next((r for r in rt.extra.data.receipts if r.amount > 0), None)


async def _latest_invoice(rt) -> tuple[str, str]:
    """(order id, invoice id) of the newest delivered order that has an invoice."""
    client = rt.deliveries.client
    current = rt.deliveries.data.order_details if rt.deliveries.data else None
    if current and current.invoice_id:
        return str(current.order_id), current.invoice_id
    closed = [d for d in await client.async_get_closed_deliveries() if d.state == "bezorgd"]
    for d in sorted(closed, key=lambda d: d.day, reverse=True)[:3]:
        details = await client.async_get_order_details(d.order_id)
        if details and details.invoice_id:
            return str(d.order_id), details.invoice_id
    raise AhApiError("No invoice found")


async def async_fetch_pdf(rt, kind: str, ref: str) -> tuple[str, bytes]:
    """kind 'receipt' (ref = receipt id or 'latest') or 'invoice' (ref = order id or 'latest')."""
    client = rt.deliveries.client
    if kind == "receipt":
        if ref == "latest":
            r = _latest_receipt(rt)
            if r is None:
                raise AhApiError("No receipt")
            ref = r.id
        receipt = next((r for r in rt.extra.data.receipts if r.id == ref), None)
        when = dt_util.as_local(receipt.when).strftime("%Y-%m-%d_%H%M") if receipt else "bon"
        return f"AH-kassabon_{when}.pdf", await client.async_get_receipt_pdf(ref)
    if kind == "invoice":
        if ref == "latest":
            order_id, invoice_id = await _latest_invoice(rt)
        else:
            details = await client.async_get_order_details(int(ref))
            if not details or not details.invoice_id:
                raise AhApiError("This order has no invoice (yet)")
            order_id, invoice_id = ref, details.invoice_id
        return f"AH-factuur_{order_id}.pdf", await client.async_get_invoice_pdf(invoice_id)
    raise ValueError("unknown kind")


async def async_save_pdf(hass: HomeAssistant, rt, kind: str, ref: str, folder: str) -> str:
    target = Path(folder.strip() or "/media/ha_appie")
    if not target.is_absolute():
        target = Path(hass.config.path(str(target)))
    if not hass.config.is_allowed_path(str(target)):
        raise HomeAssistantError(
            f"Map {target} is niet toegestaan; gebruik /media/... of voeg hem toe aan allowlist_external_dirs"
        )
    name, pdf = await async_fetch_pdf(rt, kind, ref)

    def _write() -> str:
        target.mkdir(parents=True, exist_ok=True)
        path = target / name
        path.write_bytes(pdf)
        return str(path)

    return await hass.async_add_executor_job(_write)
