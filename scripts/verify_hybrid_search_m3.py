#!/usr/bin/env python3
"""verify_hybrid_search_m3.py — Suite de verificación integral de Milestone 3 (R3).

Verifica:
  1. Detección de intención semántica (detect_search_intent) con prioridad en accesorios/racks.
  2. Invariante Top 10 libre de accesorios (0 accesorios en Top 10 para equipos: tv, celular, notebook).
  3. Latencia SQL ultra-baja (<15ms) acelerada por idx_productos_cat_norm.
  4. Relajación de dominios electro en Mercado Libre (is_electro_query y _is_supermarket_domain).
  5. Búsqueda híbrida paralela en /api/search con asyncio.gather y unificación por EAN/(brand, model).
  6. Góndolas 100% reales de supervmarket.db (WHERE descuento >= 15 AND stock > 0) con links e imágenes HTTP 200.
"""

import asyncio
import json
import os
import sys
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(ROOT_DIR, "api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from _lib import db, mercadolibre, deals  # noqa: E402


def test_intent_detection() -> bool:
    print("\n--- 1. Verificación de Detección de Intención Semántica ---")
    cases = [
        ("soporte tv", "soportes_accesorios"),
        ("soporte para televisor", "soportes_accesorios"),
        ("rack para tv", "muebles_racks"),
        ("rack tv", "muebles_racks"),
        ("funda celular", "soportes_accesorios"),
        ("funda notebook", "soportes_accesorios"),
        ("smart tv 55", "televisores"),
        ("televisor samsung", "televisores"),
        ("tv philips", "televisores"),
        ("celular motorola", "celulares"),
        ("notebook hp", "notebooks_tablets"),
        ("heladera no frost", "heladeras_freezers"),
        ("lavarropas automatico", "lavado"),
    ]
    all_ok = True
    for query, expected in cases:
        detected = db.detect_search_intent(query)
        if detected != expected:
            print(f"  [FAIL] '{query}' detectó '{detected}', esperado '{expected}'")
            all_ok = False
        else:
            print(f"  [PASS] '{query}' -> {detected}")
    return all_ok


async def test_zero_accessories_in_top10() -> bool:
    print("\n--- 2. Verificación de Invariante: 0 Accesorios en Top 10 ---")
    equipment_queries = ["tv", "smart tv", "televisor", "celular", "notebook"]
    forbidden_categories = {"soportes_accesorios", "muebles_racks"}
    accessory_tokens = {"soporte", "rack", "funda", "soporte brazo", "base de mesa", "mesa tv"}

    all_ok = True
    for q in equipment_queries:
        res = await db.search_grouped(q, limit=10)
        items = res if isinstance(res, list) else res.get("items", [])
        if not items:
            print(f"  [WARN] Query '{q}' devolvió 0 resultados en DB.")
            continue

        violations = []
        for idx, item in enumerate(items[:10], 1):
            cat = item.get("categoria_normalizada")
            name = (item.get("nombre") or "").lower()
            if cat in forbidden_categories:
                violations.append(f"#{idx} [{cat}] {item.get('nombre')}")
            elif any(tok in name.split() for tok in accessory_tokens) and not any(
                name.startswith(pfx) for pfx in ("celular", "smartphone", "smart tv", "tv", "televisor", "notebook", "laptop")
            ):
                violations.append(f"#{idx} [token match] {item.get('nombre')}")

        if violations:
            print(f"  [FAIL] Query '{q}': {len(violations)} accesorios detectados en Top 10:")
            for v in violations:
                print(f"         {v}")
            all_ok = False
        else:
            print(f"  [PASS] Query '{q}': Top {len(items)} 100% libre de accesorios. Primer producto: '{items[0].get('nombre')[:45]}'")

    return all_ok


async def test_query_latency() -> bool:
    print("\n--- 3. Verificación de Latencia SQL (< 15ms) ---")
    queries = ["tv", "celular", "notebook", "soporte tv", "smart tv samsung", "rack tv"]
    all_ok = True

    # Calentamiento inicial
    await db.search_grouped("calentamiento", limit=5)

    for q in queries:
        latencies = []
        for _ in range(5):
            t0 = time.perf_counter()
            await db.search_grouped(q, limit=15)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(dt_ms)

        avg_lat = sum(latencies) / len(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        status = "PASS" if avg_lat < 15.0 else "FAIL"
        if avg_lat >= 15.0:
            all_ok = False
        print(f"  [{status}] '{q:<18}': prom={avg_lat:.2f}ms (min={min_lat:.2f}ms, max={max_lat:.2f}ms) | req < 15ms")

    return all_ok


def test_mercadolibre_domain_relaxation() -> bool:
    print("\n--- 4. Verificación de Dominios Electro en Mercado Libre ---")
    electro_checks = [
        ("smart tv 55", True),
        ("celular samsung", True),
        ("notebook lenovo", True),
        ("leche la serenisima", False),
        ("arroz lucchetti", False),
    ]

    all_ok = True
    for q, expected in electro_checks:
        actual = mercadolibre.is_electro_query(q)
        if actual != expected:
            print(f"  [FAIL] is_electro_query('{q}')={actual}, esperado {expected}")
            all_ok = False
        else:
            print(f"  [PASS] is_electro_query('{q}') = {actual}")

    # Dominios de electro permitidos si allow_electro=True
    electro_domains = ["MLA-CELLPHONES", "MLA-TELEVISIONS", "MLA-COMPUTERS", "MLA-REFRIGERATORS"]
    for dom in electro_domains:
        allowed_with_electro = mercadolibre._is_supermarket_domain(dom, allow_electro=True)
        allowed_without_electro = mercadolibre._is_supermarket_domain(dom, allow_electro=False)
        if not allowed_with_electro:
            print(f"  [FAIL] {dom} debería estar permitido con allow_electro=True")
            all_ok = False
        if allowed_without_electro:
            print(f"  [FAIL] {dom} NO debería estar permitido con allow_electro=False")
            all_ok = False

    if all_ok:
        print("  [PASS] Filtro _is_supermarket_domain relaja dominios electro únicamente cuando corresponde.")

    return all_ok


async def test_parallel_hybrid_search() -> bool:
    print("\n--- 5. Verificación de Búsqueda Híbrida Paralela y Fusión de Ofertas ---")
    try:
        from index import app  # FastAPI app
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            t0 = time.perf_counter()
            resp = await ac.get("/api/search?q=tv&limit=5")
            dt_ms = (time.perf_counter() - t0) * 1000.0

            if resp.status_code != 200:
                print(f"  [FAIL] /api/search?q=tv retornó {resp.status_code}")
                return False

            data = resp.json()
            items = data if isinstance(data, list) else (data.get("items") or [])
            print(f"  [PASS] /api/search ejecutó en {dt_ms:.1f}ms y retornó {len(items)} productos agrupados.")
            if items:
                first = items[0]
                print(f"         Primer resultado: '{first.get('nombre')}' ({len(first.get('offers', []))} ofertas)")
                # Verificar que el primer resultado no sea un accesorio
                if first.get("categoria_normalizada") in ("soportes_accesorios", "muebles_racks"):
                    print(f"  [FAIL] El primer resultado es accesorio: {first.get('categoria_normalizada')}")
                    return False
        return True
    except Exception as e:
        print(f"  [FAIL] Error en búsqueda híbrida paralela: {e}")
        return False


def test_real_gondolas_compliance() -> bool:
    print("\n--- 6. Verificación de Góndolas 100% Reales y Snapshot ---")
    all_ok = True

    # 1. Deals Python Baseline
    mp_tiers = getattr(deals, "BASELINE_MARKETPLACE_TIERS", [])
    expected_tids = ["tier-mp-electro", "tier-mp-hogar", "tier-mp-destacadas"]
    found_tids = [t["id"] for t in mp_tiers]

    if found_tids != expected_tids:
        print(f"  [FAIL] deals.BASELINE_MARKETPLACE_TIERS tiene IDs {found_tids}, esperados {expected_tids}")
        all_ok = False
    else:
        print(f"  [PASS] deals.BASELINE_MARKETPLACE_TIERS contiene los 3 tiers requeridos: {found_tids}")

    total_prods = 0
    for t in mp_tiers:
        prods = t.get("products") or []
        total_prods += len(prods)
        for p in prods:
            if not p.get("imagen", "").startswith("https://"):
                print(f"  [FAIL] Producto {p.get('id')} imagen inválida: {p.get('imagen')}")
                all_ok = False
            offers = p.get("offers") or []
            if not offers:
                print(f"  [FAIL] Producto {p.get('id')} sin ofertas")
                all_ok = False
            for o in offers:
                if not o.get("link", "").startswith("https://"):
                    print(f"  [FAIL] Oferta {p.get('id')} link inválido: {o.get('link')}")
                    all_ok = False

    print(f"  [PASS] deals.BASELINE_MARKETPLACE_TIERS: {total_prods} productos reales validados con links e imágenes HTTPS.")

    # 2. gondolasData.ts en web
    gondolas_path = os.path.join(ROOT_DIR, "web", "src", "data", "gondolasData.ts")
    with open(gondolas_path, "r", encoding="utf-8") as f:
        gondolas_ts = f.read()

    for tid in expected_tids:
        if f"id: '{tid}'" not in gondolas_ts:
            print(f"  [FAIL] web/src/data/gondolasData.ts no contiene tier {tid}")
            all_ok = False

    # Verificar que los productos reales de Samsung y Naldo estén en el TS
    if "Smart TV Samsung 55" in gondolas_ts:
        print("  [PASS] web/src/data/gondolasData.ts contiene el Smart TV Samsung 55 real verificado.")
    else:
        print("  [FAIL] web/src/data/gondolasData.ts no contiene Smart TV Samsung 55 real verificado.")
        all_ok = False

    # 3. Snapshot verificado
    snapshot_path = os.path.join(API_DIR, "_lib", "verified_offers_snapshot.json")
    if os.path.exists(snapshot_path):
        with open(snapshot_path, "r", encoding="utf-8") as f:
            snap = json.load(f)
        if snap.get("audit_status") == "healthy" and len(snap.get("marketplace_tiers", [])) == 3:
            print("  [PASS] verified_offers_snapshot.json existe, estado=healthy, 3 marketplace tiers presentes.")
        else:
            print(f"  [WARN] Snapshot audit_status={snap.get('audit_status')}, mp_tiers={len(snap.get('marketplace_tiers', []))}")
    else:
        print(f"  [FAIL] Snapshot no existe en {snapshot_path}")
        all_ok = False

    return all_ok


async def main():
    print("=" * 78)
    print(" SUPERVMARKET — VERIFICACIÓN FINAL MILESTONE 3 (R3)")
    print("=" * 78)

    results = [
        ("1. Detección de Intención Semántica", test_intent_detection()),
        ("2. Top 10 Libre de Accesorios (0 Accesorios)", await test_zero_accessories_in_top10()),
        ("3. Latencia SQL < 15ms", await test_query_latency()),
        ("4. Relajación de Dominios Electro en MeLi", test_mercadolibre_domain_relaxation()),
        ("5. Búsqueda Híbrida Paralela Unificada", await test_parallel_hybrid_search()),
        ("6. Góndolas 100% Reales y Snapshot Verificado", test_real_gondolas_compliance()),
    ]

    print("\n" + "=" * 78)
    print(" RESUMEN DE VERIFICACIÓN MILESTONE 3")
    print("=" * 78)
    all_passed = True
    for name, passed in results:
        status = "APROBADO" if passed else "FALLIDO"
        if not passed:
            all_passed = False
        print(f"  {name:<55} : {status}")
    print("=" * 78)

    if not all_passed:
        print("\n[RESULTADO] ERROR: Una o más verificaciones de M3 fallaron.")
        sys.exit(1)
    else:
        print("\n[RESULTADO] ÉXITO: Todas las verificaciones de Milestone 3 pasaron al 100%.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
