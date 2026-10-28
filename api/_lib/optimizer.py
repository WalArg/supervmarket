"""Motor del Smart Cart v2: Promociones reales por cantidad + Costo Logístico + Cobertura por CP.

3 Escenarios Comparativos:
1. Opción Más Barata (`ahorro`)    : Split óptimo en k in [2, 3] supermercados (o 1 si solo 1 entrega/disponible),
                                     maximizando ahorro neto y advirtiendo si el flete supera el ahorro de mercadería.
2. Opción Equilibrada (`balanceada`): Frontera de Pareto comparando el mejor 1-súper vs mejor 2-súper con umbrales
                                     de indiferencia (>= $3.500 ARS y >= 5% de ahorro). Colapsa a 1 si el ahorro
                                     es marginal; prioriza 2 si resuelve productos faltantes.
3. Opción Cómoda (`comodidad`)     : Mejor supermercado individual (k=1) que maximiza cobertura de ítems y
                                     minimiza el costo neto total.
"""
from itertools import combinations
from .db import offers_for_eans
from .stores import (
    supports_cart, free_shipping_threshold, estimated_shipping_cost,
    VTEX_DOMAINS, sales_channel, decorate_store_url,
)
from . import regions, vtex_mcp, benefits

MODES = {"ahorro": (2, 3), "comodidad": (1, 1), "balanceada": (1, 2)}

PARETO_MIN_SAVINGS_ARS = 3500.0
PARETO_MIN_SAVINGS_PCT = 0.05  # 5%


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
    unit_multiplier = float(offer.get("unit_multiplier") or 1.0)
    effective_qty = round(qty * unit_multiplier, 3)

    regular_total = round(max(list_unit, base_unit) * effective_qty, 2)
    base_total = round(base_unit * effective_qty, 2)

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
            "unit_multiplier": unit_multiplier,
        }

    # Promoción por escalón de cantidad (ej: 2x1, 3x2, 2do al 70%)
    if min_qty > 1 and qty >= min_qty and promo_unit < base_unit:
        bundles = qty // min_qty
        rem = qty % min_qty
        line_total = round((bundles * min_qty * promo_unit * unit_multiplier) + (rem * base_unit * unit_multiplier), 2)
        return {
            "line_total": line_total,
            "effective_unit": round(line_total / qty, 2),
            "regular_total": regular_total,
            "applied_promo": promo_label,
            "unit_multiplier": unit_multiplier,
        }

    # Promoción en 1 unidad (directa o de club con include_clubs=True)
    if min_qty <= 1 and promo_unit <= base_unit and promo_label:
        line_total = round(promo_unit * effective_qty, 2)
        return {
            "line_total": line_total,
            "effective_unit": round(promo_unit, 2),
            "regular_total": regular_total,
            "applied_promo": promo_label,
            "unit_multiplier": unit_multiplier,
        }

    return {
        "line_total": base_total,
        "effective_unit": round(base_unit, 2),
        "regular_total": regular_total,
        "applied_promo": None,
        "unit_multiplier": unit_multiplier,
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
        preferred_store = it.get("store") or it.get("supermercado")
        best = None
        best_calc = None

        offs = offers_by_ean.get(ean, [])
        # Si el usuario eligió expresamente un comercio (ej. Mercado Libre en OffersSheet)
        if preferred_store:
            store_offs = [o for o in offs if o.get("supermercado") == preferred_store]
            if store_offs:
                offs = store_offs

        for o in offs:
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
                "ean": ean,
                "nombre": it.get("nombre") or best.get("nombre"),
                "imagen": it.get("imagen") or best.get("imagen") or "",
                "qty": qty,
                "precio": best_calc["effective_unit"],
                "precio_base": best["precio"],
                "line_total": best_calc["line_total"],
                "regular_total": best_calc["regular_total"],
                "applied_promo": best_calc["applied_promo"],
                "unit_multiplier": best_calc.get("unit_multiplier", 1.0),
                "link": it.get("link") or best.get("link") or "",
            })

    return assignment, round(merch_total, 2), round(regular_total, 2), covered


def _shipping_for_store(store: str, subtotal: float, include_shipping: bool) -> float:
    if not include_shipping or subtotal <= 0:
        return 0.0
    threshold = free_shipping_threshold(store)
    if threshold and subtotal >= threshold:
        return 0.0
    return estimated_shipping_cost(store)


def _evaluate_store_combo(
    combo: tuple[str, ...],
    items: list[dict],
    offers_by_ean: dict,
    include_clubs: bool = False,
    include_shipping: bool = False,
    selected_cards: set[str] | None = None,
    active_day: str | None = None,
) -> dict | None:
    """Evalúa de forma exacta una combinación específica de supermercados."""
    asg, merch, reg, cov = _assign(
        items, offers_by_ean, set(combo), include_clubs=include_clubs, selected_cards=selected_cards
    )
    if cov == 0:
        return None

    # Costo de envío y reintegros bancarios
    ship_total = 0.0
    reintegro_total = 0.0
    cards_set = selected_cards or set()
    d_act = active_day or benefits.today_weekday_ar()

    for st, st_items in asg.items():
        st_sub = round(sum(i["line_total"] for i in st_items), 2)
        ship_total += _shipping_for_store(st, st_sub, include_shipping)
        b = benefits.best_cart_benefit_for_store(st, st_sub, d_act, cards_set)
        if b:
            reintegro_total += b["saving"]

    ship_total = round(ship_total, 2)
    reintegro_total = round(reintegro_total, 2)
    net_grand_total = round(merch + ship_total - reintegro_total, 2)

    # Score determinístico:
    # 1. Mayor cobertura de productos
    # 2. Menor total neto (mercadería + flete - reintegros)
    # 3. Menor cantidad de paradas reales
    # 4. Menor subtotal de mercadería
    score = (cov, -net_grand_total, -len(asg), -merch)

    return {
        "score": score,
        "combo": combo,
        "assignment": asg,
        "merch_total": merch,
        "regular_total": reg,
        "covered": cov,
        "ship_total": ship_total,
        "reintegro_total": reintegro_total,
        "net_grand_total": net_grand_total,
        "stops": len(asg),
    }


def _find_best_eval_for_k(
    k: int,
    stores: list[str],
    items: list[dict],
    offers_by_ean: dict,
    include_clubs: bool = False,
    include_shipping: bool = False,
    selected_cards: set[str] | None = None,
    active_day: str | None = None,
) -> dict | None:
    """Encuentra la mejor solución evaluando todas las combinaciones C(stores, k).
    
    Para k >= 2, prioriza soluciones que efectivamente asignen productos a al menos 2 comercios.
    Si ninguna combinación puede asignar a múltiples comercios (ej. un solo comercio tiene stock),
    permite la asignación con la mayor cantidad de comercios posibles.
    """
    if len(stores) < k or k < 1:
        return None

    best = None
    best_split = None

    for combo in combinations(stores, k):
        eval_res = _evaluate_store_combo(
            combo, items, offers_by_ean,
            include_clubs=include_clubs,
            include_shipping=include_shipping,
            selected_cards=selected_cards,
            active_day=active_day,
        )
        if not eval_res:
            continue

        if best is None or eval_res["score"] > best["score"]:
            best = eval_res

        # Para k >= 2, priorizamos que efectivamente sea un split multi-tienda (stops >= 2)
        if k >= 2 and eval_res["stops"] >= 2:
            if best_split is None or eval_res["score"] > best_split["score"]:
                best_split = eval_res

    if k >= 2 and best_split is not None:
        return best_split
    return best


def _enrich_missing_items(
    missing_eans: list[str],
    offers_by_ean: dict[str, list[dict]],
    names: dict[str, str],
    assigned_stores: list[str],
    valid_stores: set[str] | None = None,
) -> list[dict]:
    """Enriquece los productos faltantes de un escenario con sus alternativas en otras tiendas.
    
    Para cada EAN que no pudo asignarse a ninguna de las tiendas asignadas del escenario:
    1. Registra las tiendas asignadas del escenario (`missing_in_assigned_stores`).
    2. Cruza con `offers_by_ean[ean]` para encontrar todas las ofertas disponibles en otros supermercados.
    3. Deduplica por supermercado seleccionando la oferta más conveniente (menor precio unitario efectivo).
    4. Extrae la insignia promocional (`promo_badge`) o descuento porcentual.
    5. Ordena las alternativas de menor a mayor precio.
    """
    enriched: list[dict] = []
    assigned_set = set(assigned_stores)

    for e in missing_eans:
        nombre = names.get(e, e)
        offs = offers_by_ean.get(e, [])

        store_best_offer: dict[str, dict] = {}
        for o in offs:
            st = o.get("supermercado")
            if not st or st in assigned_set:
                continue
            if valid_stores is not None and st not in valid_stores:
                continue

            eff_price = float(o.get("promo_unit_price") or o.get("precio") or 0.0)
            if eff_price <= 0:
                continue

            if st not in store_best_offer:
                store_best_offer[st] = o
            else:
                curr_best = float(store_best_offer[st].get("promo_unit_price") or store_best_offer[st].get("precio") or 0.0)
                if eff_price < curr_best:
                    store_best_offer[st] = o

        alternatives: list[dict] = []
        for st, o in store_best_offer.items():
            price = round(float(o.get("promo_unit_price") or o.get("precio") or 0.0), 2)
            badge = o.get("promo_label") or o.get("applied_promo")
            if not badge and o.get("discount") and float(o["discount"]) >= 5:
                badge = f"{int(o['discount'])}% OFF"

            alternatives.append({
                "supermercado": st,
                "precio": price,
                "promo_badge": badge,
            })

        alternatives.sort(key=lambda a: a["precio"])

        enriched.append({
            "ean": e,
            "nombre": nombre,
            "missing_in_assigned_stores": sorted(list(assigned_stores)),
            "available_in_other_stores": alternatives,
        })

    return enriched


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
        subtotal_merch = round(sum(i["line_total"] for i in items), 2)
        regular_sub = round(sum(i.get("regular_total", i["line_total"]) for i in items), 2)
        volume_discounts_total = round(max(0.0, regular_sub - subtotal_merch), 2)

        bank_benefit = benefits.best_cart_benefit_for_store(
            store, subtotal_merch, active_day, cards_set
        )
        bank_discount_amount = round(bank_benefit["saving"], 2) if bank_benefit else 0.0
        bank_card_applied = bank_benefit["label"] if bank_benefit else None

        threshold = free_shipping_threshold(store)
        has_threshold = threshold > 0
        is_free_shipping = bool(has_threshold and subtotal_merch >= threshold)
        amount_for_free_shipping = max(0.0, round(threshold - subtotal_merch, 2)) if has_threshold else 0.0

        fee = 0.0
        if include_shipping and subtotal_merch > 0 and not is_free_shipping:
            fee = estimated_shipping_cost(store)
        shipping_fee = round(fee, 2)

        final_store_total = round(subtotal_merch - bank_discount_amount + shipping_fee, 2)
        is_vtex = supports_cart(store)

        checkout = None
        if is_vtex:
            sc = sales_channel(store)
            parts = [
                f"sku={i['sku_id']}&qty={i['qty']}&seller=1&sc={sc}"
                for i in items if i.get("sku_id")
            ]
            checkout = f"{VTEX_DOMAINS[store]}/checkout/cart/add?{'&'.join(parts)}"
        elif len(items) == 1 and items[0].get("link"):
            checkout = items[0].get("link")
        elif store == "Coto":
            checkout = "https://www.cotodigital3.com.ar/sitios/cdigi/"
        elif store == "MercadoLibre":
            checkout = items[0].get("link") if (items and len(items) == 1 and items[0].get("link")) else "https://www.mercadolibre.com.ar/gz/cart"
        elif items and items[0].get("link"):
            checkout = items[0].get("link")

        if checkout:
            checkout = decorate_store_url(checkout, store, "checkout")

        # Detalle de productos con soporte dual (legado + extendido)
        items_detail = []
        for i in items:
            qty = i["qty"]
            regular_tot = i.get("regular_total", i["line_total"])
            unit_mult = i.get("unit_multiplier", 1.0)
            precio_base = i.get("precio_base", i["precio"])
            precio_reg = round(regular_tot / qty, 2) if qty > 0 else precio_base
            line_tot = i["line_total"]
            ahorro_line = round(max(0.0, regular_tot - line_tot), 2)
            promo_badge = i.get("applied_promo")
            raw_item_link = i.get("link") or ""
            dec_item_link = decorate_store_url(raw_item_link, store, "item") if raw_item_link else ""

            items_detail.append({
                "ean": i["ean"],
                "nombre": i.get("nombre"),
                "sku_id": i.get("sku_id"),
                "imagen": i.get("imagen") or "",
                "qty": qty,
                "precio": i["precio"],
                "precio_base": precio_base,
                "precio_regular": precio_reg,
                "precio_unitario_efectivo": i["precio"],
                "line_total": line_tot,
                "subtotal_linea": line_tot,
                "unit_multiplier": unit_mult,
                "applied_promo": promo_badge,
                "promo_badge": promo_badge,
                "ahorro_linea": ahorro_line,
                "link": dec_item_link,
            })

        carts.append({
            # Identificación y Checkout
            "supermercado": store,
            "supports_cart": is_vtex,
            "is_vtex": is_vtex,
            "checkout_url": checkout,
            "affiliate_checkout_url": checkout,

            # Mercadería y Descuentos por Volumen
            "subtotal_merch": subtotal_merch,
            "subtotal": subtotal_merch,  # compat StoreCart.tsx
            "volume_discounts_total": volume_discounts_total,
            "ahorro": volume_discounts_total,  # compat StoreCart.tsx

            # Beneficios Financieros y Bancarios
            "bank_discount_amount": bank_discount_amount,
            "reintegro_bancario": bank_discount_amount,  # compat StoreCart.tsx
            "bank_card_applied": bank_card_applied,
            "bank_benefit": bank_benefit,  # compat StoreCart.tsx

            # Logística de Flete y Progreso a Envío Gratis
            "shipping_fee": shipping_fee,
            "envio_estimado": shipping_fee,  # compat StoreCart.tsx
            "free_shipping_threshold": threshold,
            "is_free_shipping": is_free_shipping,
            "amount_for_free_shipping": amount_for_free_shipping,
            "falta_envio_gratis": amount_for_free_shipping,  # compat StoreCart.tsx

            # Total Final de la Tienda
            "final_store_total": final_store_total,

            # Detalle de Líneas de Producto
            "items": items_detail,
        })

    carts.sort(key=lambda c: -c["subtotal_merch"])
    return carts


def _build_plan_from_eval(
    target_mode: str,
    eval_res: dict | None,
    items: list[dict],
    eans: list[str],
    offers_by_ean: dict,
    names: dict,
    valid_stores: set[str] | None,
    excluded_stores: list[str],
    include_shipping: bool,
    cards_set: set[str],
    active_day: str,
    cp: str | None,
) -> dict:
    """Construye la estructura completa de OptimizePlan a partir de la evaluación óptima."""
    if not eval_res:
        missing_all = _enrich_missing_items(
            eans, offers_by_ean, names, assigned_stores=[], valid_stores=valid_stores
        )
        return {
            "mode": target_mode,
            "cp": cp,
            "day": active_day,
            "day_label": benefits.WEEKDAY_LABELS.get(active_day, active_day.capitalize()),
            "stops": 0,
            "subtotal_mercaderia": 0.0,
            "envio_estimado": 0.0,
            "reintegro_bancario_total": 0.0,
            "total": 0.0,
            "ahorro_total": 0.0,
            "best_day_suggestion": None,
            "excluded_stores": excluded_stores,
            "missing": missing_all,
            "carts": [],
        }

    assignment = eval_res["assignment"]
    found_eans = {i["ean"] for its in assignment.values() for i in its}
    missing_eans = [e for e in eans if e not in found_eans]
    assigned_stores = sorted(list(assignment.keys()))

    missing = _enrich_missing_items(
        missing_eans, offers_by_ean, names, assigned_stores, valid_stores=valid_stores
    )

    carts = _build_carts(
        assignment,
        include_shipping=include_shipping,
        day=active_day,
        selected_cards=cards_set,
    )

    merch_total = round(sum(c["subtotal_merch"] for c in carts), 2)
    ship_total = round(sum(c["shipping_fee"] for c in carts), 2)
    reintegro_total = round(sum(c["bank_discount_amount"] for c in carts), 2)
    grand_total = round(merch_total + ship_total - reintegro_total, 2)
    regular_total = round(sum(sum(i.get("regular_total", i["line_total"]) for i in its) for its in assignment.values()), 2)
    ahorro_productos = round(max(0.0, regular_total - merch_total), 2)
    ahorro_total = round(ahorro_productos + reintegro_total, 2)

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
        "mode": target_mode,
        "cp": cp,
        "day": active_day,
        "day_label": benefits.WEEKDAY_LABELS.get(active_day, active_day.capitalize()),
        "stops": len(carts),
        "subtotal_mercaderia": merch_total,
        "envio_estimado": ship_total,
        "reintegro_bancario_total": reintegro_total,
        "total": grand_total,
        "ahorro_total": ahorro_total,
        "best_day_suggestion": best_day_info,
        "excluded_stores": excluded_stores,
        "missing": missing,
        "carts": carts,
    }


async def optimize(
    items: list[dict],
    mode: str = "ahorro",
    cp: str | None = None,
    include_clubs: bool = False,
    include_shipping: bool = False,
    selected_cards: list[str] | None = None,
    day: str | None = None,
) -> dict:
    """Smart Cart Multi-Escenario: Resuelve Ahorro (2-3 súper), Equilibrada (Pareto) y Cómoda (1 súper) en 1 pasada."""
    eans = [it["ean"] for it in items]
    names_hint = {it["ean"]: it["nombre"] for it in items if it.get("nombre")}
    offers_by_ean, names = await vtex_mcp.live_offers_for_eans(eans, cp=cp, names_hint=names_hint)

    missing_live = [it for it in items if it["ean"] not in offers_by_ean]
    if missing_live:
        missing_eans = [it["ean"] for it in missing_live]
        db_offers, db_names = await offers_for_eans(missing_eans)
        for e, offs in db_offers.items():
            offers_by_ean.setdefault(e, []).extend(offs)
        names.update(db_names)
        for it in missing_live:
            if it["ean"] not in names and it.get("nombre"):
                names[it["ean"]] = it["nombre"]

    for it in items:
        pref = it.get("store") or it.get("supermercado")
        if pref and it.get("precio"):
            ean = it["ean"]
            existing = offers_by_ean.setdefault(ean, [])
            if not any(o.get("supermercado") == pref for o in existing):
                existing.append({
                    "supermercado": pref,
                    "ean": ean,
                    "sku_id": it.get("sku_id") or it.get("sku") or "",
                    "nombre": it.get("nombre") or names.get(ean, "Producto"),
                    "precio": float(it["precio"]),
                    "link": it.get("link") or "",
                })

    valid_stores: set[str] | None = None
    excluded_stores: list[str] = []
    if cp:
        cov = await regions.coverage(cp)
        excluded_stores = [c["supermercado"] for c in cov if c.get("delivers") is False]
        if excluded_stores:
            all_known = {c["supermercado"] for c in cov} | {
                "MercadoLibre", "LaBarraCCU", "TheFoodMarket",
                "LaBarata", "TonelPrivado", "DePastura", "ArcorEnCasa", "Coto"
            }
            valid_stores = all_known - set(excluded_stores)

    cards_set = set(selected_cards or [])
    active_day = (day or benefits.today_weekday_ar()).lower().strip()

    available_stores = sorted({
        o["supermercado"]
        for offs in offers_by_ean.values()
        for o in offs
        if valid_stores is None or o["supermercado"] in valid_stores
    })

    # 1. EVALUAR k=1 (Base para Opción Cómoda)
    eval_k1 = _find_best_eval_for_k(
        1, available_stores, items, offers_by_ean,
        include_clubs=include_clubs, include_shipping=include_shipping,
        selected_cards=cards_set, active_day=active_day,
    )

    # 2. EVALUAR k=2
    eval_k2 = _find_best_eval_for_k(
        2, available_stores, items, offers_by_ean,
        include_clubs=include_clubs, include_shipping=include_shipping,
        selected_cards=cards_set, active_day=active_day,
    )

    # 3. EVALUAR k=3
    eval_k3 = _find_best_eval_for_k(
        3, available_stores, items, offers_by_ean,
        include_clubs=include_clubs, include_shipping=include_shipping,
        selected_cards=cards_set, active_day=active_day,
    )

    # ==========================================
    # ESCENARIO 3: Opción Cómoda (k=1)
    # ==========================================
    eval_comoda = eval_k1

    # ==========================================
    # ESCENARIO 1: Opción Más Barata (k in [2, 3] o k=1 si no hay split disponible)
    # ==========================================
    eval_ahorro_cands = [e for e in (eval_k2, eval_k3) if e is not None]
    if eval_ahorro_cands:
        eval_ahorro = max(eval_ahorro_cands, key=lambda x: x["score"])
    else:
        eval_ahorro = eval_k1

    # ==========================================
    # ESCENARIO 2: Opción Equilibrada (Frontera de Pareto)
    # Compara mejor 1-súper (eval_k1) con mejor 2-súper (eval_k2)
    # Umbrales: >= $3.500 ARS y >= 5% de ahorro marginal neto
    # ==========================================
    if eval_k2 is None or eval_k1 is None:
        eval_balanceada = eval_k1 or eval_k2
    else:
        # Si el 2-súper cubre productos faltantes que el 1-súper no cubre -> priorizar 2 súper
        if eval_k2["covered"] > eval_k1["covered"]:
            eval_balanceada = eval_k2
        elif eval_k2["stops"] <= 1:
            eval_balanceada = eval_k1
        else:
            marginal_saving = round(eval_k1["net_grand_total"] - eval_k2["net_grand_total"], 2)
            k1_total = eval_k1["net_grand_total"]
            marginal_pct = (marginal_saving / k1_total) if k1_total > 0 else 0.0

            # Si el ahorro supera ambos umbrales, el split está justificado
            if marginal_saving >= PARETO_MIN_SAVINGS_ARS and marginal_pct >= PARETO_MIN_SAVINGS_PCT:
                eval_balanceada = eval_k2
            else:
                # Si el ahorro es marginal o negativo, colapsar a 1 solo súper
                eval_balanceada = eval_k1

    # Construir los planes completos
    plan_comoda = _build_plan_from_eval(
        "comodidad", eval_comoda, items, eans, offers_by_ean, names,
        valid_stores, excluded_stores, include_shipping, cards_set, active_day, cp
    )
    plan_balanceada = _build_plan_from_eval(
        "balanceada", eval_balanceada, items, eans, offers_by_ean, names,
        valid_stores, excluded_stores, include_shipping, cards_set, active_day, cp
    )
    plan_ahorro = _build_plan_from_eval(
        "ahorro", eval_ahorro, items, eans, offers_by_ean, names,
        valid_stores, excluded_stores, include_shipping, cards_set, active_day, cp
    )

    all_plans = {
        "ahorro": plan_ahorro,
        "balanceada": plan_balanceada,
        "comodidad": plan_comoda,
    }

    total_comoda = plan_comoda["total"]
    total_items_count = len(items)

    # Advertencia logística para Opción Más Barata: si flete extra supera ahorro en mercadería
    logistics_warning = None
    if include_shipping and eval_ahorro and eval_comoda and eval_ahorro["stops"] > 1:
        merch_savings = max(0.0, round(eval_comoda["merch_total"] - eval_ahorro["merch_total"], 2))
        extra_shipping = max(0.0, round(eval_ahorro["ship_total"] - eval_comoda["ship_total"], 2))
        if extra_shipping > merch_savings and extra_shipping > 0:
            logistics_warning = (
                f"El costo extra de envío (${extra_shipping:,.0f} ARS) supera el ahorro en productos (${merch_savings:,.0f} ARS). "
                "Te conviene comprar todo en 1 súper (Opción Cómoda)."
            )
    elif eval_ahorro and eval_ahorro["stops"] >= 3:
        logistics_warning = "Requiere coordinar 3 envíos distintos"

    mode_previews = {}
    for m in ["ahorro", "balanceada", "comodidad"]:
        p = all_plans[m]
        ahorro_vs_com = round(max(0.0, total_comoda - p["total"]), 2)
        ahorro_vs_reg = p["ahorro_total"]

        if total_comoda > 0 and ahorro_vs_com > 0:
            ahorro_pct = round((ahorro_vs_com / total_comoda) * 100, 1)
        elif (p["total"] + ahorro_vs_reg) > 0 and ahorro_vs_reg > 0:
            ahorro_pct = round((ahorro_vs_reg / (p["total"] + ahorro_vs_reg)) * 100, 1)
        else:
            ahorro_pct = 0.0

        covered_count = total_items_count - len(p.get("missing", []))

        # Metadatos semánticos de UX
        if m == "ahorro":
            title = "Opción más barata"
            tagline = "Split óptimo 2-3 súper"
            badge = "MÁXIMO AHORRO"
            l_warn = logistics_warning
        elif m == "balanceada":
            title = "Opción equilibrada"
            tagline = "Ahorro vs conveniencia"
            badge = "RECOMENDADA"
            l_warn = None
        else:
            title = "Opción cómoda"
            tagline = "Todo en 1 solo súper"
            badge = "1 SOLO SÚPER"
            l_warn = "Faltan productos en este supermercado" if len(p.get("missing", [])) > 0 else None

        diff = round(p["total"] - plan_ahorro["total"], 2)

        mode_previews[m] = {
            "mode": m,
            "title": title,
            "tagline": tagline,
            "total": p["total"],
            "ahorro_vs_comoda": ahorro_vs_com,
            "ahorro_vs_regular": ahorro_vs_reg,
            "ahorro_pct": ahorro_pct,
            "supermercados_count": p["stops"],
            "covered_items": covered_count,
            "total_items": total_items_count,
            "badge": badge,
            "logistics_warning": l_warn,
            # Campos retrocompatibles para ListScreen.tsx
            "diff": diff,
            "stops": p["stops"],
            "ahorro_total": p["ahorro_total"],
        }

    # Asignar a cada plan su preview y advertencias correspondientes
    for m, pl in all_plans.items():
        pl["scenario_preview"] = mode_previews[m]
        if m == "ahorro" and logistics_warning:
            pl["logistics_warning"] = logistics_warning

    # Retornar plan activo sin referencias circulares
    active_plan = dict(all_plans.get(mode) or plan_ahorro)
    active_plan["all_plans"] = all_plans
    active_plan["mode_previews"] = mode_previews
    return active_plan
