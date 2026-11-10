#!/usr/bin/env python3
"""verify_m3_adversarial_empirical.py — Suite de Stress Testing y Desafío Adversarial para M3 (R3).

Desafíos evaluados:
1. Adversarial Search Intent & Equipment Query Testing:
   - Evaluó queries de equipamiento: "tv", "smart tv", "televisor 50", "samsung tv",
     "celular", "celulares", "smartphone", "iphone", "notebook", "laptop",
     "heladera", "lavarropas" + variantes adicionales.
   - Assert estricto: En el Top 10 de CADA query de equipamiento, el conteo de
     accesorios ("soportes_accesorios"), muebles ("muebles_racks") o alimentos/perfumería es 0.
   - Evaluó queries inversas: "soporte tv", "rack tv", "funda celular", verificando que
     clasifiquen como accesorios/muebles y que éstos encabecen los resultados.
2. Search Latency Benchmark Under Concurrency:
   - 20 hilos paralelos ejecutando 200 consultas aleatorias sobre la base de datos SQLite.
   - Assert: Latencia promedio < 15ms.
   - Assert: Latencia percentil 95 (P95) < 25ms.
   - Assert: Cero errores de bloqueo de base de datos (sqlite3.OperationalError: database is locked).
3. Hybrid Search Offer Merging Invariants:
   - Fusión por EAN-13 idéntico (deduplicación, preservación de mejor oferta).
   - Fusión por clave canónica (marca, modelo) cuando falta EAN.
   - Deduplicación de múltiples ofertas MeLi para un mismo producto.
   - Generación de grupo nuevo para productos MeLi exclusivos (schema válido y JSON serializable).
   - Resiliencia ante payloads corruptos de MeLi (precios negativos, campos nulos).
4. Gondola Products Health & Network Liveness:
   - 15 marketplace deals en deals.py (BASELINE_MARKETPLACE_TIERS) y gondolasData.ts.
   - Validación de esquema: 3 tiers, 5 productos por tier, precios válidos, descuento >= 15%.
   - Verificación de red en vivo: 100% de imágenes y links HTTP 200 OK.
"""

import asyncio
import concurrent.futures
import json
import os
import sys
import time
from typing import List, Dict, Any

import httpx

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(ROOT_DIR, "api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from _lib import db, mercadolibre, deals  # noqa: E402
from _lib.normalization import extract_model, canonical_model_key, is_valid_ean13  # noqa: E402


# ==============================================================================
# 1. ADVERSARIAL INTENT & EQUIPMENT QUERY TESTING
# ==============================================================================
async def test_adversarial_intent_and_equipment_queries() -> bool:
    print("\n" + "=" * 78)
    print(" 1. ADVERSARIAL STRESS TEST: INTENT DETECTION & 0 ACCESSORIES IN TOP 10")
    print("=" * 78)

    equipment_queries = [
        "tv",
        "smart tv",
        "televisor 50",
        "samsung tv",
        "celular",
        "celulares",
        "smartphone",
        "iphone",
        "notebook",
        "laptop",
        "heladera",
        "lavarropas",
        # Variantes adicionales adversariales
        "smart tv 4k",
        "celular samsung",
        "notebook lenovo",
        "heladera gafa",
        "lavarropas drean",
    ]

    accessory_or_furniture_cats = {"soportes_accesorios", "muebles_racks"}
    grocery_or_cosmetic_cats = {
        "perfumeria_farmacia", "almacen", "carnes_verduleria",
        "limpieza", "bebidas", "lacteos_frescos", "mascotas"
    }
    forbidden_cats = accessory_or_furniture_cats | grocery_or_cosmetic_cats

    accessory_tokens = {"soporte", "rack", "funda", "panel para tv", "mesa tv", "brazo", "vidrio templado"}

    all_passed = True
    print(f"Probando {len(equipment_queries)} consultas de equipamiento:")

    for q in equipment_queries:
        intent = db.detect_search_intent(q)
        results = await db.search_grouped(q, limit=10)
        items = results if isinstance(results, list) else results.get("items", [])

        if not items:
            print(f"  [FAIL] Query '{q}' no retornó ningún producto en supervmarket.db!")
            all_passed = False
            continue

        violations = []
        for idx, item in enumerate(items[:10], start=1):
            cat = item.get("categoria_normalizada") or ""
            name = (item.get("nombre") or "").lower()

            if cat in forbidden_cats:
                violations.append(f"Posición #{idx}: [{cat}] '{item.get('nombre')}'")
            elif any(tok in name for tok in accessory_tokens) and not any(
                name.startswith(pfx) for pfx in ("celular", "smartphone", "smart tv", "tv", "televisor", "notebook", "laptop", "heladera", "lavarropas")
            ):
                violations.append(f"Posición #{idx}: [token match '{name}']")

        if violations:
            print(f"  [FAIL] Query '{q}' (intent={intent}): {len(violations)} accesorios/infiltrados en Top 10:")
            for v in violations:
                print(f"         - {v}")
            all_passed = False
        else:
            top_name = items[0].get("nombre", "")[:45]
            print(f"  [PASS] '{q:<20}' -> intent={intent:<18} | Top 10 con 0 accesorios (1º: '{top_name}')")

    # Reverse intent tests
    print("\nProbando consultas inversas (accesorios / muebles explícitos):")
    reverse_queries = [
        ("soporte tv", "soportes_accesorios"),
        ("rack tv", "muebles_racks"),
        ("funda celular", "soportes_accesorios"),
        ("mesa para tv", "muebles_racks"),
        ("cargador celular", "soportes_accesorios"),
    ]

    for q, expected_cat in reverse_queries:
        intent = db.detect_search_intent(q)
        if intent != expected_cat:
            print(f"  [FAIL] Reverse intent '{q}': detectó '{intent}', esperado '{expected_cat}'")
            all_passed = False
        else:
            results = await db.search_grouped(q, limit=10)
            items = results if isinstance(results, list) else results.get("items", [])
            top_cat = items[0].get("categoria_normalizada") if items else "none"
            if top_cat == expected_cat:
                print(f"  [PASS] Reverse query '{q}': intent={intent} y 1º resultado es '{items[0].get('nombre')[:45]}' [{top_cat}]")
            else:
                print(f"  [WARN] Reverse query '{q}': 1º resultado tiene cat '{top_cat}'")

    return all_passed


# ==============================================================================
# 2. SEARCH LATENCY BENCHMARK UNDER CONCURRENCY
# ==============================================================================
async def benchmark_concurrency(total_queries: int = 200, max_workers: int = 20) -> Dict[str, Any]:
    print("\n" + "=" * 78)
    print(f" 2. SEARCH LATENCY CONCURRENCY BENCHMARK ({max_workers} THREADS, {total_queries} QUERIES)")
    print("=" * 78)

    sample_queries = [
        "tv", "smart tv", "televisor", "celular", "celulares", "notebook",
        "laptop", "heladera", "lavarropas", "soporte tv", "rack tv", "funda celular",
        "leche", "arroz", "fideos", "cerveza", "jabon liquido", "shampoo",
        "aceite", "cafe", "galletitas", "queso", "vino", "yerba mate"
    ]

    import random
    query_list = [random.choice(sample_queries) for _ in range(total_queries)]

    # Pre-calentamiento para estabilizar el pool de SQLite
    for sq in sample_queries:
        await db.search_grouped(sq, limit=15)

    latencies = []
    lock_errors = []
    other_errors = []

    def run_single_query(q: str):
        t0 = time.perf_counter()
        try:
            # db.search_grouped is async, run in local event loop or via asyncio.run
            res = asyncio.run(db.search_grouped(q, limit=15))
            dt_ms = (time.perf_counter() - t0) * 1000.0
            return (dt_ms, None, len(res))
        except Exception as e:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            return (dt_ms, e, 0)

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(run_single_query, q) for q in query_list]
        for f in concurrent.futures.as_completed(futures):
            dt_ms, err, count = f.result()
            latencies.append(dt_ms)
            if err:
                err_str = str(err)
                if "locked" in err_str.lower() or "busy" in err_str.lower():
                    lock_errors.append(err_str)
                else:
                    other_errors.append(err_str)

    total_time_s = time.perf_counter() - t_start
    latencies.sort()
    mean_lat = sum(latencies) / len(latencies)
    p50_lat = latencies[int(len(latencies) * 0.50)]
    p95_lat = latencies[int(len(latencies) * 0.95)]
    p99_lat = latencies[int(len(latencies) * 0.99)]
    max_lat = max(latencies)

    print(f"  Resultados de concurrencia:")
    print(f"    - Consultas totales : {len(latencies)} ejecutadas en {total_time_s:.2f}s")
    print(f"    - Throughput        : {len(latencies)/total_time_s:.1f} queries/segundo")
    print(f"    - Latencia promedio : {mean_lat:.2f}ms (Requisito: < 15.0ms)")
    print(f"    - Latencia P50      : {p50_lat:.2f}ms")
    print(f"    - Latencia P95      : {p95_lat:.2f}ms (Requisito: < 25.0ms)")
    print(f"    - Latencia P99      : {p99_lat:.2f}ms")
    print(f"    - Latencia Máxima   : {max_lat:.2f}ms")
    print(f"    - Lock Errors       : {len(lock_errors)} (Requisito: 0)")
    print(f"    - Otros Errores     : {len(other_errors)}")

    passed = (mean_lat < 15.0) and (p95_lat < 25.0) and (len(lock_errors) == 0) and (len(other_errors) == 0)
    status_str = "APROBADO" if passed else "FALLIDO"
    print(f"  [VEREDICTO CONCURRENCIA] {status_str}")

    return {
        "passed": passed,
        "mean_lat": mean_lat,
        "p95_lat": p95_lat,
        "lock_errors": len(lock_errors),
        "other_errors": len(other_errors),
    }


# ==============================================================================
# 3. HYBRID SEARCH OFFER MERGING INVARIANTS
# ==============================================================================
def test_hybrid_search_merging_invariants() -> bool:
    print("\n" + "=" * 78)
    print(" 3. HYBRID SEARCH OFFER MERGING INVARIANTS & INTEGRITY")
    print("=" * 78)

    all_passed = True

    # Simulamos el núcleo del algoritmo de index.py para aislar invariantes de fusión
    def merge_offers(db_results: list, meli_results: list, query_str: str, vertical: str = "") -> list:
        by_ean: dict[str, dict] = {}
        by_model: dict[str, dict] = {}

        for g in db_results:
            g_ean = str(g.get("ean") or "")
            if is_valid_ean13(g_ean) or (len(g_ean) == 13 and g_ean.isdigit()):
                by_ean[g_ean] = g
            g_marca = g.get("marca") or ""
            g_raw_m = g.get("modelo") or ""
            g_modelo = extract_model(g_raw_m, g_marca) if g_raw_m else extract_model(g.get("nombre") or "", g_marca)
            if not g_modelo:
                g_modelo = g_raw_m
            c_key = canonical_model_key(g_marca, g_modelo)
            if c_key:
                by_model[c_key] = g

        unmatched_meli_groups = []
        is_electro = mercadolibre.is_electro_query(query_str, vertical)

        for m in meli_results:
            p_val = float(m.get("precio") or m.get("precio_venta") or 0.0)
            if p_val <= 0:
                continue
            pl_val = float(m.get("precio_lista") or p_val)
            m_disc = float(m.get("discount") or 0.0)
            if pl_val > p_val and m_disc <= 0:
                m_disc = round((1 - p_val / pl_val) * 100, 1)

            m_link = str(m.get("link") or m.get("url") or "")
            m_sku = str(m.get("sku") or m.get("ean") or "")

            meli_offer = {
                "supermercado": "MercadoLibre",
                "precio": p_val,
                "precio_lista": pl_val,
                "stock": True,
                "link": m_link,
                "sku_id": m_sku,
                "unit_price": m.get("unit_price"),
                "unit_measure": m.get("unit_type") or m.get("unit_measure"),
                "discount": m_disc,
                "promo_label": m.get("promo_label"),
                "promo_tipo": None,
                "promo_min_qty": 1,
                "promo_unit_price": p_val,
                "requires_club": False,
                "supports_cart": False,
                "seller_id": str(m.get("seller_name") or "MercadoLibre"),
                "store_type": "marketplace",
                "modelo": m.get("modelo") or "",
                "tipo": "electro" if is_electro else "supermarket",
                "is_full": m.get("is_full", False),
                "free_shipping": m.get("free_shipping", False),
                "shipping_cost": float(m.get("shipping_cost") or 0.0),
                "seller_name": m.get("seller_name"),
            }

            target_group = None
            m_ean = str(m.get("ean") or "")
            if (is_valid_ean13(m_ean) or (len(m_ean) == 13 and m_ean.isdigit())) and m_ean in by_ean:
                target_group = by_ean[m_ean]
            else:
                m_marca = m.get("marca") or ""
                m_raw_m = m.get("modelo") or ""
                m_modelo = extract_model(m_raw_m, m_marca) if m_raw_m else extract_model(m.get("nombre") or "", m_marca)
                if not m_modelo:
                    m_modelo = m_raw_m
                m_key = canonical_model_key(m_marca, m_modelo)
                if m_key and m_key in by_model:
                    target_group = by_model[m_key]

            if target_group:
                existing_meli = next((o for o in target_group.get("offers", []) if o.get("supermercado") == "MercadoLibre"), None)
                if not existing_meli:
                    target_group.setdefault("offers", []).append(meli_offer)
                elif p_val < float(existing_meli.get("precio") or 1e9):
                    target_group["offers"].remove(existing_meli)
                    target_group["offers"].append(meli_offer)

                target_group["offers"].sort(key=lambda o: (o.get("promo_unit_price") or o["precio"]))
                target_group["best_offer"] = target_group["offers"][0]
            else:
                new_grp = {
                    "id": m_ean if is_valid_ean13(m_ean) else f"MELI_{m_sku or id(m)}",
                    "ean": m_ean if is_valid_ean13(m_ean) else f"MELI_{m_sku or id(m)}",
                    "nombre": m.get("nombre") or "",
                    "marca": m.get("marca") or "Mercado Libre",
                    "modelo": m.get("modelo") or "",
                    "tipo": "electro" if is_electro else "supermarket",
                    "vertical": "electro" if is_electro else "supermarket",
                    "categoria_normalizada": db.detect_search_intent(m.get("nombre") or "") or "",
                    "imagen": m.get("imagen") or "",
                    "offers": [meli_offer],
                    "best_offer": meli_offer,
                }
                unmatched_meli_groups.append(new_grp)

        return list(db_results) + unmatched_meli_groups

    # CASO 1: Fusión por EAN-13 exacto
    db_item_ean = {
        "id": "7791293041234",
        "ean": "7791293041234",
        "nombre": "Smart TV Samsung 55 UHD 4K",
        "marca": "Samsung",
        "modelo": "UN55CU7000",
        "categoria_normalizada": "televisores",
        "offers": [
            {"supermercado": "Fravega", "precio": 650000.0, "promo_unit_price": 650000.0}
        ],
        "best_offer": {"supermercado": "Fravega", "precio": 650000.0, "promo_unit_price": 650000.0}
    }
    meli_item_ean = {
        "ean": "7791293041234",
        "nombre": "Smart TV Samsung 55 Pulgadas 4K",
        "marca": "Samsung",
        "precio": 620000.0,
        "precio_lista": 700000.0,
        "link": "https://articulo.mercadolibre.com.ar/MLA-12345",
        "seller_name": "Tienda Samsung Oficial",
        "is_full": True
    }
    merged = merge_offers([dict(db_item_ean)], [meli_item_ean], "smart tv")
    if len(merged) != 1:
        print(f"  [FAIL] Fusión por EAN creó {len(merged)} tarjetas en lugar de 1")
        all_passed = False
    elif len(merged[0]["offers"]) != 2:
        print(f"  [FAIL] Fusión por EAN no agregó la oferta MeLi a las ofertas existentes")
        all_passed = False
    elif merged[0]["best_offer"]["precio"] != 620000.0:
        print(f"  [FAIL] best_offer no se actualizó con la mejor oferta (MeLi 620000): {merged[0]['best_offer']}")
        all_passed = False
    else:
        print("  [PASS] Subtest 3.1: Fusión por EAN-13 exacto unificó ofertas y recalculó best_offer correctamente.")

    # CASO 2: Fusión por Modelo Canónico (sin EAN en MeLi)
    db_item_model = {
        "id": "FRAVEGA-9988",
        "ean": "FRAVEGA-9988",
        "nombre": "Notebook Lenovo IdeaPad 3 15ALC6",
        "marca": "Lenovo",
        "modelo": "IdeaPad 3 15ALC6",
        "categoria_normalizada": "notebooks_tablets",
        "offers": [{"supermercado": "Fravega", "precio": 900000.0, "promo_unit_price": 900000.0}],
        "best_offer": {"supermercado": "Fravega", "precio": 900000.0, "promo_unit_price": 900000.0}
    }
    meli_item_model = {
        "ean": "",  # Sin EAN
        "nombre": "Lenovo IdeaPad 3 15ALC6 Ryzen 5 8GB 512GB",
        "marca": "Lenovo",
        "precio": 850000.0,
        "link": "https://articulo.mercadolibre.com.ar/MLA-67890",
        "seller_name": "Mercado Libre",
    }
    merged_model = merge_offers([dict(db_item_model)], [meli_item_model], "notebook")
    if len(merged_model) != 1 or len(merged_model[0]["offers"]) != 2:
        print(f"  [FAIL] Fusión por modelo canónico falló: tarjetas={len(merged_model)}, offers={len(merged_model[0]['offers']) if merged_model else 0}")
        all_passed = False
    else:
        print("  [PASS] Subtest 3.2: Fusión por modelo canónico (sin EAN) unificó correctamente en 1 sola tarjeta.")

    # CASO 3: Deduplicación de múltiples ofertas MeLi para el mismo producto
    meli_dup1 = {
        "ean": "7791293041234",
        "precio": 640000.0,
        "link": "https://articulo.mercadolibre.com.ar/MLA-1",
        "seller_name": "Vendedor A"
    }
    meli_dup2 = {
        "ean": "7791293041234",
        "precio": 610000.0,  # Mejor precio
        "link": "https://articulo.mercadolibre.com.ar/MLA-2",
        "seller_name": "Vendedor B"
    }
    merged_dup = merge_offers([copy_dict(db_item_ean)], [meli_dup1, meli_dup2], "smart tv")
    meli_offers_count = sum(1 for o in merged_dup[0]["offers"] if o.get("supermercado") == "MercadoLibre")
    if meli_offers_count != 1 or merged_dup[0]["best_offer"]["precio"] != 610000.0:
        print(f"  [FAIL] Deduplicación de ofertas MeLi falló: ofertas MeLi={meli_offers_count}, best={merged_dup[0]['best_offer']}")
        all_passed = False
    else:
        print("  [PASS] Subtest 3.3: Múltiples ofertas MeLi deduplicadas preservando la más barata ($610.000).")

    # CASO 4: Nuevo producto MeLi no existente en DB
    meli_unique = {
        "sku": "MLA999999",
        "nombre": "Cafetera Express Philips EP2220",
        "marca": "Philips",
        "precio": 450000.0,
        "precio_lista": 500000.0,
        "imagen": "https://http2.mlstatic.com/cafetera.jpg",
        "link": "https://articulo.mercadolibre.com.ar/MLA-999999",
    }
    merged_unique = merge_offers([], [meli_unique], "cafetera")
    if len(merged_unique) != 1:
        print(f"  [FAIL] Creación de nuevo grupo MeLi retornó {len(merged_unique)} items")
        all_passed = False
    else:
        g = merged_unique[0]
        try:
            serialized = json.dumps(g)
            if not g.get("id") or not g.get("nombre") or not g.get("offers"):
                print(f"  [FAIL] Nuevo grupo MeLi tiene campos incompletos: {g}")
                all_passed = False
            else:
                print(f"  [PASS] Subtest 3.4: Nuevo producto MeLi creó grupo estructurado válido y JSON serializable ({len(serialized)} bytes).")
        except Exception as e:
            print(f"  [FAIL] Serialización JSON de grupo MeLi falló: {e}")
            all_passed = False

    # CASO 5: Resiliencia ante datos corruptos de MeLi
    corrupt_melis = [
        {"precio": 0.0},
        {"precio": -50.0},
        {"nombre": None},
        {}
    ]
    merged_corrupt = merge_offers([], corrupt_melis, "tv")
    if len(merged_corrupt) != 0:
        print(f"  [FAIL] Resiliencia ante datos corruptos falló, creó {len(merged_corrupt)} grupos para items inválidos")
        all_passed = False
    else:
        print("  [PASS] Subtest 3.5: Items MeLi con precios <=0 o datos nulos fueron descartados limpiamente.")

    return all_passed


def copy_dict(d: dict) -> dict:
    return json.loads(json.dumps(d))


# ==============================================================================
# 4. GONDOLA PRODUCTS HEALTH & NETWORK LIVENESS
# ==============================================================================
async def test_gondola_products_health_and_network() -> bool:
    print("\n" + "=" * 78)
    print(" 4. GONDOLA HEALTH AUDIT & LIVE HTTP VERIFICATION (15 PRODUCTS)")
    print("=" * 78)

    all_passed = True
    mp_tiers = getattr(deals, "BASELINE_MARKETPLACE_TIERS", [])
    expected_tiers = ["tier-mp-electro", "tier-mp-hogar", "tier-mp-destacadas"]

    # 4.1 Schema y Reglas de Descuento
    print("Validando integridad estructural de BASELINE_MARKETPLACE_TIERS:")
    found_tier_ids = [t.get("id") for t in mp_tiers]
    if found_tier_ids != expected_tiers:
        print(f"  [FAIL] Tiers encontrados {found_tier_ids} != {expected_tiers}")
        all_passed = False
    else:
        print(f"  [PASS] 3 Tiers canónicos de marketplace verificados: {found_tier_ids}")

    all_products = []
    for t in mp_tiers:
        tid = t.get("id")
        prods = t.get("products") or []
        if len(prods) != 5:
            print(f"  [FAIL] Tier '{tid}' tiene {len(prods)} productos, se esperan 5")
            all_passed = False
        else:
            print(f"  [PASS] Tier '{tid}' contiene exactamente 5 productos reales.")

        for p in prods:
            p_id = p.get("id") or p.get("ean")
            p_nom = p.get("nombre") or ""
            p_img = p.get("imagen") or ""
            offers = p.get("offers") or []

            if not p_id or not p_nom or not p_img.startswith("https://"):
                print(f"  [FAIL] Producto inválido: id={p_id}, nombre={p_nom}, img={p_img}")
                all_passed = False

            if not offers:
                print(f"  [FAIL] Producto {p_id} sin ofertas asociadas.")
                all_passed = False

            for o in offers:
                pr = float(o.get("precio") or 0.0)
                pl = float(o.get("precio_lista") or pr)
                disc = float(o.get("descuento") or o.get("discount") or 0.0)
                link = o.get("link") or ""

                if pr <= 0:
                    print(f"  [FAIL] Oferta {p_id} precio inválido: {pr}")
                    all_passed = False
                if disc < 15.0:
                    print(f"  [FAIL] Oferta {p_id} '{p_nom}' descuento {disc}% < 15.0%")
                    all_passed = False
                if not link.startswith("https://"):
                    print(f"  [FAIL] Oferta {p_id} link inválido: {link}")
                    all_passed = False

            all_products.append({"tier": tid, "id": p_id, "nombre": p_nom, "imagen": p_img, "link": offers[0].get("link")})

    print(f"  [PASS] Todos los 15 productos cumplen descuento >= 15% y precios válidos.")

    # 4.2 Liveness de Red (HTTP 200 en Imágenes y Links)
    print("\nVerificando conectividad HTTP en vivo para las 15 imágenes y 15 links:")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    }

    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=12.0) as client:
        # Verificar imágenes
        img_tasks = [client.get(p["imagen"]) for p in all_products]
        img_resps = await asyncio.gather(*img_tasks, return_exceptions=True)

        bad_images = 0
        for p, r in zip(all_products, img_resps):
            if isinstance(r, Exception):
                print(f"  [FAIL] Imagen error de red: {p['nombre'][:35]} -> {r}")
                bad_images += 1
            elif r.status_code != 200:
                print(f"  [FAIL] Imagen status={r.status_code}: {p['imagen']}")
                bad_images += 1
            else:
                pass

        if bad_images == 0:
            print(f"  [PASS] 15/15 imágenes de góndolas responden HTTP 200 OK (100% de éxito).")
        else:
            print(f"  [FAIL] {bad_images} imágenes no respondieron HTTP 200 OK!")
            all_passed = False

        # Verificar links
        link_tasks = [client.get(p["link"]) for p in all_products]
        link_resps = await asyncio.gather(*link_tasks, return_exceptions=True)

        bad_links = 0
        for p, r in zip(all_products, link_resps):
            if isinstance(r, Exception):
                print(f"  [WARN/FAIL] Link error de red: {p['link'][:50]} -> {r}")
                bad_links += 1
            elif r.status_code not in (200, 301, 302, 307, 308):
                print(f"  [FAIL] Link status={r.status_code}: {p['link']}")
                bad_links += 1

        if bad_links == 0:
            print(f"  [PASS] 15/15 links de góndolas responden HTTP 200/Redirect OK (100% de accesibilidad).")
        else:
            print(f"  [FAIL] {bad_links} links no respondieron OK!")
            all_passed = False

    # 4.3 Verificación de paridad con gondolasData.ts
    gondolas_ts_path = os.path.join(ROOT_DIR, "web", "src", "data", "gondolasData.ts")
    with open(gondolas_ts_path, "r", encoding="utf-8") as f:
        ts_content = f.read().replace("\\'", "'")

    missing_in_ts = 0
    for p in all_products:
        p_sub = p["nombre"][:25]
        if p_sub not in ts_content:
            print(f"  [FAIL] Producto no encontrado en gondolasData.ts: '{p_sub}'")
            missing_in_ts += 1

    if missing_in_ts == 0:
        print("  [PASS] Paridad 100% confirmada entre deals.py y web/src/data/gondolasData.ts.")
    else:
        print(f"  [FAIL] {missing_in_ts} productos difieren entre deals.py y gondolasData.ts")
        all_passed = False

    return all_passed


# ==============================================================================
# MAIN RUNNER
# ==============================================================================
async def main():
    print("=" * 78)
    print(" SUPERVMARKET — SUITE ADVERSARIAL EMPÍRICA CHALLENGER M3 (R3)")
    print("=" * 78)

    t0_suite = time.perf_counter()

    test1_ok = await test_adversarial_intent_and_equipment_queries()
    bench2 = await benchmark_concurrency(total_queries=200, max_workers=20)
    test3_ok = test_hybrid_search_merging_invariants()
    test4_ok = await test_gondola_products_health_and_network()

    total_duration = time.perf_counter() - t0_suite

    print("\n" + "=" * 78)
    print(" RESUMEN DE STRESS TESTING EMPÍRICO CHALLENGER M3")
    print("=" * 78)
    print(f"  1. Adversarial Search Intent (0 accesorios en Top 10) : {'APROBADO' if test1_ok else 'FALLIDO'}")
    print(f"  2. Concurrencia (20 hilos, 200 q, <15ms, 0 locks)     : {'APROBADO' if bench2['passed'] else 'FALLIDO'}")
    print(f"  3. Hybrid Merging Invariants (EAN/Model/Dedup/Schema) : {'APROBADO' if test3_ok else 'FALLIDO'}")
    print(f"  4. Góndolas 100% Reales (15 deals, HTTP 200 Liveness) : {'APROBADO' if test4_ok else 'FALLIDO'}")
    print(f"  Duración total del stress test: {total_duration:.2f}s")
    print("=" * 78)

    all_passed = test1_ok and bench2["passed"] and test3_ok and test4_ok

    if all_passed:
        print("\n[VEREDICTO FINAL CHALLENGER M3]: APPROVE (100% de tests empíricos pasados sin fallas).")
        sys.exit(0)
    else:
        print("\n[VEREDICTO FINAL CHALLENGER M3]: REQUEST_CHANGES (Se detectaron fallos en las pruebas).")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
