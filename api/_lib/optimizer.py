"""Motor del Smart Cart v2: Promociones reales por cantidad + Costo Logístico + Cobertura por CP.

- ahorro     : cada producto donde resulte más barato (evaluando escalones NxM / 2do al X%).
- comodidad  : un único súper (el más económico que cubra la mayor cantidad de productos).
- balanceada : hasta 2 súper, combinación óptima.

Soporta:
- `include_clubs`: activa/desactiva ofertas que requieren Club DIA, Mi Carrefour, Comunidad Coto, etc.
- `include_shipping`: suma el costo de envío cuando un carrito no alcanza el umbral de envío gratis.
- `cp`: excluye automáticamente supermercados que confirman NO entregar en ese Código Postal.
"""
from itertools import combinations
from .db import offers_for_eans
from .stores import (
    supports_cart, free_shipping_threshold, estimated_shipping_cost,
    VTEX_DOMAINS, sales_channel,
)
from . import regions, vtex_mcp, benefits

MODES = {"ahorro": None, "comodidad": 1, "balanceada": 2}


def _calc_offer_line(
    offer: dict,
    qty: int,
    include_clubs: bool,
    selected_cards: set[str] | None = None,
) -> dict:
    """Calcula el precio real para `qty` unidades según las reglas de promoción del producto."""
    base_unit = float(offer["precio"])
    list_unit = float(offer.get("precio_lista") or base_unit)
    min_qty = int(offer.get("promo_min_qty") or 1)
    promo_unit = float(offer.get("promo_unit_price") or base_unit)
    req_club = bool(offer.get("requires_club"))
    promo_label = offer.get("promo_label")

    regular_total = round(max(list_unit, base_unit) * qty, 2)
    base_total = round(base_unit * qty, 2)

    has_club = benefits.user_has_store_club(
        offer["supermercado"], selected_cards or set(), include_clubs_legacy=include_clubs
    )

    # Si requiere membresía/tarjeta y el usuario no tiene esa tarjeta/club, se cobra precio público
    if req_club and not has_club:
        return {
            "line_total": base_total,
            "effective_unit": round(base_unit, 2),
            "regular_total": regular_total,
            "applied_promo": None,
        }

    # Promoción por escalón de cantidad (ej: 2x1, 3x2, 2do al 70%)
    if min_qty > 1 and qty >= min_qty and promo_unit < base_unit:
        bundles = qty // min_qty
        rem = qty % min_qty
        line_total = round((bundles * min_qty * promo_unit) + (rem * base_unit), 2)
        return {
            "line_total": line_total,
            "effective_unit": round(line_total / qty, 2),
            "regular_total": regular_total,
            "applied_promo": promo_label,
        }

    # Promoción en 1 unidad (directa o de club con include_clubs=True)
    if min_qty <= 1 and promo_unit <= base_unit and promo_label:
        line_total = round(promo_unit * qty, 2)
        return {
            "line_total": line_total,
            "effective_unit": round(promo_unit, 2),
            "regular_total": regular_total,
            "applied_promo": promo_label,
        }

    return {
        "line_total": base_total,
        "effective_unit": round(base_unit, 2),
        "regular_total": regular_total,
        "applied_promo": None,
    }


def _assign(
    items: list[dict],
    offers_by_ean: dict,
    allowed_stores: set[str] | None,
    include_clubs: bool = False,
    selected_cards: set[str] | None = None,
):
    """Asigna cada ítem al súper más conveniente dentro de `allowed_stores`."""
    assignment: dict[str, list[dict]] = {}
    merch_total = 0.0
    regular_total = 0.0
    covered = 0

    for it in items:
        ean, qty = it["ean"], max(1, int(it.get("qty", 1)))
        best = None
        best_calc = None

        for o in offers_by_ean.get(ean, []):
            if allowed_stores is not None and o["supermercado"] not in allowed_stores:
                continue
            calc = _calc_offer_line(
                o, qty, include_clubs=include_clubs, selected_cards=selected_cards
            )
            if best is None or calc["line_total"] < best_calc["line_total"]:
                best = o
                best_calc = calc

        if best is not None and best_calc is not None:
            covered += 1
            merch_total += best_calc["line_total"]
            regular_total += best_calc["regular_total"]
            assignment.setdefault(best["supermercado"], []).append({
                **best,
                "qty": qty,
                "precio": best_calc["effective_unit"],
                "precio_base": best["precio"],
                "line_total": best_calc["line_total"],
                "regular_total": best_calc["regular_total"],
                "applied_promo": best_calc["applied_promo"],
            })

    return assignment, round(merch_total, 2), round(regular_total, 2), covered


def _shipping_for_store(store: str, subtotal: float, include_shipping: bool) -> float:
    if not include_shipping or subtotal <= 0:
        return 0.0
    threshold = free_shipping_threshold(store)
    if threshold and subtotal >= threshold:
        return 0.0
    return estimated_shipping_cost(store)


def _best_combo(
    items: list[dict],
    offers_by_ean: dict,
    max_stores: int | None,
    valid_stores: set[str] | None,
    include_clubs: bool = False,
    include_shipping: bool = False,
    selected_cards: set[str] | None = None,
):
    """Mejor solución usando a lo sumo `max_stores` súper (cobertura -> menor costo c/envío -> menos paradas)."""
    stores = sorted({
        o["supermercado"]
        for offs in offers_by_ean.values()
        for o in offs
        if valid_stores is None or o["supermercado"] in valid_stores
    })
    if not stores:
        return {}, 0.0, 0.0, 0.0, 0

    # Si no se incluye envío y es modo ahorro puro, asignar directo al mínimo por producto
    if max_stores is None and not include_shipping:
        asg, merch, reg, cov = _assign(
            items, offers_by_ean, valid_stores, include_clubs=include_clubs, selected_cards=selected_cards
        )
        return asg, merch, 0.0, reg, cov

    max_k = min(len(stores), max_stores or 4)
    best = None
    for k in range(1, max_k + 1):
        for combo in combinations(stores, k):
            asg, merch, reg, cov = _assign(
                items, offers_by_ean, set(combo), include_clubs=include_clubs, selected_cards=selected_cards
            )
            if cov == 0:
                continue
            ship = sum(
                _shipping_for_store(st, sum(i["line_total"] for i in st_items), include_shipping)
                for st, st_items in asg.items()
            )
            grand_total = round(merch + ship, 2)
            score = (cov, -grand_total, -len(asg))
            if best is None or score > best[0]:
                best = (score, asg, merch, round(ship, 2), reg, cov)

    if not best:
        return {}, 0.0, 0.0, 0.0, 0
    return best[1], best[2], best[3], best[4], best[5]


def _build_carts(
    assignment: dict[str, list[dict]],
    include_shipping: bool = False,
    day: str | None = None,
    selected_cards: set[str] | None = None,
):
    carts = []
    active_day = day or benefits.today_weekday_ar()
    cards_set = selected_cards or set()
    for store, items in assignment.items():
        subtotal = round(sum(i["line_total"] for i in items), 2)
        regular_sub = round(sum(i["regular_total"] for i in items), 2)
        ahorro_store = round(max(0.0, regular_sub - subtotal), 2)
        threshold = free_shipping_threshold(store)
        if store == "MercadoLibre" and "meli_plus" in cards_set:
            threshold = 15000
        falta_gratis = max(0.0, round(threshold - subtotal, 2)) if threshold else 0.0
        envio_est = _shipping_for_store(store, subtotal, include_shipping)
        bank_benefit = benefits.best_cart_benefit_for_store(
            store, subtotal, active_day, cards_set
        )
        reintegro_banco = bank_benefit["saving"] if bank_benefit else 0.0

        checkout = None
        if supports_cart(store):
            sc = sales_channel(store)
            parts = [
                f"sku={i['sku_id']}&qty={i['qty']}&seller=1&sc={sc}"
                for i in items if i.get("sku_id")
            ]
            checkout = f"{VTEX_DOMAINS[store]}/checkout/cart/add?{'&'.join(parts)}"
        elif items and items[0].get("link"):
            checkout = items[0].get("link")

        carts.append({
            "supermercado": store,
            "supports_cart": supports_cart(store),
            "checkout_url": checkout,
            "subtotal": subtotal,
            "ahorro": ahorro_store,
            "reintegro_bancario": reintegro_banco,
            "bank_benefit": bank_benefit,
            "envio_estimado": envio_est,
            "free_shipping_threshold": threshold,
            "falta_envio_gratis": falta_gratis,
            "items": [{
                "ean": i["ean"],
                "nombre": i.get("nombre"),
                "sku_id": i.get("sku_id"),
                "precio": i["precio"],
                "precio_base": i["precio_base"],
                "line_total": i["line_total"],
                "applied_promo": i.get("applied_promo"),
                "qty": i["qty"],
                "link": i.get("link"),
            } for i in items],
        })
    carts.sort(key=lambda c: -c["subtotal"])
    return carts


async def optimize(
    items: list[dict],
    mode: str = "ahorro",
    cp: str | None = None,
    include_clubs: bool = False,
    include_shipping: bool = False,
    selected_cards: list[str] | None = None,
    day: str | None = None,
) -> dict:
    """items: [{ean, qty}]. Devuelve el plan con carritos por súper, ahorro real y mejor día de compra."""
    eans = [it["ean"] for it in items]
    offers_by_ean, names = await vtex_mcp.live_offers_for_eans(eans, cp=cp)
    missing_live = [e for e in eans if e not in offers_by_ean]
    if missing_live:
        db_offers, db_names = await offers_for_eans(missing_live)
        for e, offs in db_offers.items():
            offers_by_ean.setdefault(e, []).extend(offs)
        names.update(db_names)

    valid_stores: set[str] | None = None
    excluded_stores: list[str] = []
    if cp:
        cov = await regions.coverage(cp)
        all_known = {c["supermercado"] for c in cov}
        excluded_stores = [c["supermercado"] for c in cov if c.get("delivers") is False]
        valid_stores = (all_known - set(excluded_stores)) | {"MercadoLibre", "LaBarraCCU", "TheFoodMarket"}

    cards_set = set(selected_cards or [])
    active_day = (day or benefits.today_weekday_ar()).lower().strip()

    max_stores = MODES.get(mode, None)
    assignment, merch_total, ship_total, regular_total, _ = _best_combo(
        items,
        offers_by_ean,
        max_stores,
        valid_stores,
        include_clubs=include_clubs,
        include_shipping=include_shipping,
        selected_cards=cards_set,
    )

    found_eans = {i["ean"] for its in assignment.values() for i in its}
    missing = [{"ean": e, "nombre": names.get(e, e)} for e in eans if e not in found_eans]
    carts = _build_carts(
        assignment,
        include_shipping=include_shipping,
        day=active_day,
        selected_cards=cards_set,
    )

    reintegro_total = round(sum(c.get("reintegro_bancario") or 0.0 for c in carts), 2)
    grand_total = round(merch_total + ship_total - reintegro_total, 2)
    ahorro_productos = round(max(0.0, regular_total - merch_total), 2)

    # Calcular qué día de la semana da el mayor reintegro con las tarjetas del usuario
    best_day_info = None
    if cards_set and assignment:
        for d_cand in benefits.WEEKDAYS_ES:
            day_saving = 0.0
            day_labels = []
            for st, st_items in assignment.items():
                sub = round(sum(i["line_total"] for i in st_items), 2)
                b = benefits.best_cart_benefit_for_store(st, sub, d_cand, cards_set)
                if b:
                    day_saving += b["saving"]
                    day_labels.append(f"{st}: {b['label']}")
            day_saving = round(day_saving, 2)
            if day_saving > 0 and (best_day_info is None or day_saving > best_day_info["saving"]):
                best_day_info = {
                    "day": d_cand,
                    "day_label": benefits.WEEKDAY_LABELS.get(d_cand, d_cand.capitalize()),
                    "saving": day_saving,
                    "details": day_labels,
                }

    return {
        "mode": mode,
        "cp": cp,
        "day": active_day,
        "day_label": benefits.WEEKDAY_LABELS.get(active_day, active_day.capitalize()),
        "stops": len(carts),
        "subtotal_mercaderia": merch_total,
        "envio_estimado": ship_total,
        "reintegro_bancario_total": reintegro_total,
        "total": grand_total,
        "ahorro_total": round(ahorro_productos + reintegro_total, 2),
        "best_day_suggestion": best_day_info,
        "excluded_stores": excluded_stores,
        "missing": missing,
        "carts": carts,
    }
