"""Validación de carrito EN VIVO y regionalizada (stock + precio c/promos + envío según CP).

Usa la simulación pública de VTEX (`/api/checkout/pub/orderForms/simulation?sc=XX`),
pasando el Sales Channel correcto de cada cadena (Jumbo=32, Disco=33, Vea=34, Farmacity=4, On City=2, Moulinex=3, Josimar=5, etc.),
calculando el precio real con descuentos por cantidad (`sellingPrice` y `totals`), preservando
el seller_id dinámico de cada ítem en marketplaces (`seller={seller_id}`), y separando
el costo de Envío a Domicilio (`delivery`) del Retiro en Sucursal (`pickup-in-point`).
"""
import httpx
from .stores import (
    VTEX_DOMAINS,
    get_store_meta,
    supports_cart,
    free_shipping_threshold,
    sales_channel,
    decorate_store_url,
)
from . import regions

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
}


def guest_link(store: str, items: list[dict], seller: str = "1") -> str | None:
    """Genera el enlace de compra directa / checkout preservando el seller_id dinámico por cada ítem."""
    if not supports_cart(store):
        return None

    domain = VTEX_DOMAINS.get(store)
    if not domain:
        meta = get_store_meta(store)
        domain = meta["dominio"] if meta and meta.get("plataforma") == "vtex" else None
    if not domain:
        return None

    default_sc = sales_channel(store)
    parts = []
    for i in items:
        sku = i.get("sku_id")
        if not sku:
            continue
        qty = i.get("qty", 1)
        # Resuelve dinámicamente: seller_id del dict (LiveOffer/parsers) -> seller -> parámetro fallback -> "1"
        item_seller = str(i.get("seller_id") or i.get("seller") or seller or "1")
        item_sc = str(i.get("sc") or i.get("sales_channel") or default_sc)
        parts.append(f"sku={sku}&qty={qty}&seller={item_seller}&sc={item_sc}")

    if not parts:
        return None

    raw_url = f"{domain}/checkout/cart/add?{'&'.join(parts)}"
    return decorate_store_url(raw_url, store, "checkout")


async def validate_cart(store: str, items: list[dict], cp: str | None = None) -> dict:
    if not supports_cart(store):
        return {
            "status": "compare_only",
            "message": f"{store} no permite armar el carrito automáticamente.",
            "checkout_url": None,
        }

    meta = get_store_meta(store)
    base = VTEX_DOMAINS.get(store) or (meta["dominio"] if meta else None)
    if not base:
        return {"status": "error", "message": f"Dominio no encontrado para {store}", "checkout_url": None}

    sc = sales_channel(store)
    valid_items = [i for i in items if i.get("sku_id")]
    if not valid_items:
        return {"status": "error", "message": "Sin SKUs válidos para simular.", "checkout_url": None}

    def _make_payload(default_seller: str = "1") -> dict:
        return {
            "items": [
                {
                    "id": str(i["sku_id"]),
                    "quantity": int(i.get("qty", 1)),
                    "seller": str(i.get("seller_id") or i.get("seller") or default_seller or "1"),
                }
                for i in valid_items
            ],
            "country": "ARG",
            **({"postalCode": cp} if cp else {}),
        }

    try:
        async with httpx.AsyncClient(timeout=18) as client:
            r = await client.post(
                f"{base}/api/checkout/pub/orderForms/simulation",
                params={"sc": sc},
                json=_make_payload("1"),
                headers=HEADERS,
            )
            sim = r.json()

            # Si con seller="1" VTEX no encontró stock para ítems que dependían del seller por defecto,
            # y hay un seller regional para ese CP, reintentar con el seller regional
            items_returned = sim.get("items") or []
            has_unresolved_items = (
                not items_returned
                or any(it.get("availability") != "available" for it in items_returned)
            )
            has_default_seller_items = any(
                not (i.get("seller_id") or i.get("seller"))
                for i in valid_items
            )

            if has_unresolved_items and has_default_seller_items and cp:
                cov = await regions.coverage(cp)
                store_cov = next((c for c in cov if c["supermercado"] == store), None)
                reg_sellers = (store_cov or {}).get("sellers") or []
                if reg_sellers and str(reg_sellers[0]) != "1":
                    r2 = await client.post(
                        f"{base}/api/checkout/pub/orderForms/simulation",
                        params={"sc": sc},
                        json=_make_payload(str(reg_sellers[0])),
                        headers=HEADERS,
                    )
                    sim2 = r2.json()
                    if sim2.get("items"):
                        sim = sim2

        by_id = {str(i["sku_id"]): i for i in valid_items}
        sin_stock = []
        subtotal_base = 0.0
        total_efectivo = 0.0
        items_detail = []

        for it in sim.get("items", []):
            sku_id = str(it.get("id"))
            ref = by_id.get(sku_id) or {}
            avail = it.get("availability") == "available"
            qty = int(it.get("quantity") or 1)

            # En VTEX simulation, price y sellingPrice vienen en centavos
            unit_base = (it.get("price") or 0) / 100.0
            unit_selling = (it.get("sellingPrice") or it.get("price") or 0) / 100.0

            if not avail:
                sin_stock.append(ref.get("nombre") or sku_id)
            else:
                subtotal_base += unit_base * qty
                total_efectivo += unit_selling * qty

            items_detail.append({
                "sku_id": sku_id,
                "nombre": ref.get("nombre"),
                "available": avail,
                "qty": qty,
                "unit_price": round(unit_base, 2),
                "selling_price": round(unit_selling, 2),
                "line_total": round(unit_selling * qty, 2),
            })

        # Si algún SKU pedido ni siquiera fue devuelto en sim["items"], marcarlo sin stock
        returned_ids = {str(it.get("id")) for it in sim.get("items", [])}
        for sku_id, ref in by_id.items():
            if sku_id not in returned_ids:
                sin_stock.append(ref.get("nombre") or sku_id)

        # Usar totals consolidados de VTEX (Items + Discounts) cuando estén presentes
        totals_map = {t.get("id"): (t.get("value") or 0) / 100.0 for t in (sim.get("totals") or [])}
        if "Items" in totals_map and totals_map["Items"] > 0:
            subtotal_base = totals_map["Items"]
            total_efectivo = totals_map["Items"] + totals_map.get("Discounts", 0.0)

        promos_aplicadas = [
            b.get("name")
            for b in ((sim.get("ratesAndBenefitsData") or {}).get("rateAndBenefitsIdentifiers") or [])
            if b.get("name")
        ]

        # Separar envío a domicilio (delivery) de retiro en tienda (pickup-in-point)
        envio_domicilio = None
        retiro_sucursal = None
        for li in sim.get("logisticsInfo") or []:
            for sla in li.get("slas") or []:
                price = (sla.get("price") or 0) / 100.0
                channel = sla.get("deliveryChannel", "delivery")
                if channel == "pickup-in-point":
                    retiro_sucursal = price if retiro_sucursal is None else min(retiro_sucursal, price)
                else:
                    envio_domicilio = price if envio_domicilio is None else min(envio_domicilio, price)

        mensajes = [m.get("text", "") for m in (sim.get("messages") or []) if m.get("text")]
        threshold = free_shipping_threshold(store)
        falta_gratis = max(0.0, round(threshold - total_efectivo, 2)) if threshold else 0.0

        return {
            "status": "warning" if sin_stock else "ok",
            "supermercado": store,
            "cp": cp,
            "subtotal_sin_promos": round(subtotal_base, 2),
            "total": round(total_efectivo, 2),
            "ahorro_promos": round(max(0.0, subtotal_base - total_efectivo), 2),
            "promos_aplicadas": promos_aplicadas,
            "envio": round(envio_domicilio, 2) if envio_domicilio is not None else None,
            "retiro_gratis": retiro_sucursal == 0,
            "sin_stock": sin_stock,
            "items": items_detail,
            "mensajes": mensajes,
            "falta_envio_gratis": falta_gratis,
            "checkout_url": guest_link(store, valid_items),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "checkout_url": guest_link(store, valid_items),
        }
