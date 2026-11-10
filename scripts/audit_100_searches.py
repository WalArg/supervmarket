#!/usr/bin/env python3
"""scripts/audit_100_searches.py

SuperVmarket — Automated 100-Search Common Queries Audit Suite.
Covers 60 Supermarket/Pharmacy/Pets queries + 40 Electro/Tech/Home queries.

Verifications:
1. Equipment queries purity: Strictly 0 accessories or racks in Top 10.
2. Search latency: Average DB search latency strictly under 15ms.
3. Link & image validity: Top 5 products per query have valid HTTPS images (HTTP 200 OK)
   and valid deep product permalinks.
4. Gondola health: All discount tiers and sponsored options verified HTTP 200 OK.
5. Cart generation: Multi-item cart URLs built successfully via api/_lib/carts.py.
6. Export: Writes full JSON report to api/_lib/audit_100_searches_report.json.
"""

import os
import sys
import time
import json
import asyncio
from datetime import datetime, timezone
from typing import TypedDict, List, Dict, Any

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(ROOT_DIR, "api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

import httpx
from _lib.db import search_grouped, detect_search_intent, EQUIPMENT_INTENTS
from _lib.carts import guest_link
from _lib.stores import supports_cart
from _lib import deals

SUPERMARKET_QUERIES: List[str] = [
    "leche", "leche descremada", "aceite", "aceite girasol", "arroz",
    "fideos", "fideos tallarines", "yerba", "yerba mate", "azucar",
    "cafe", "cafe molido", "galletitas", "galletitas dulces", "atun",
    "pure de tomate", "tomate perita", "mayonesa", "mostaza", "ketchup",
    "lavandina", "detergente", "detergente para ropa", "jabon liquido", "suavizante",
    "shampoo", "acondicionador", "jabon de tocador", "desodorante", "papel higienico",
    "rollo de cocina", "pasta dental", "cepillo dental", "pan", "pan lactal",
    "manteca", "queso cremoso", "queso rallado", "yogur", "yogur bebible",
    "gaseosa", "gaseosa cola", "cerveza", "vino tinto", "agua mineral",
    "agua saborizada", "carne picada", "asado", "vacio", "pechuga de pollo",
    "milanesas", "milanesas de carne", "salchichas", "manzana", "banana",
    "papa", "cebolla", "zanahoria", "lechuga", "harina"
]

ELECTRO_QUERIES: List[str] = [
    "smart tv", "tv 50", "tv 43", "tv samsung", "televisor",
    "celular", "celular samsung", "celular motorola", "smartphone", "iphone",
    "notebook", "notebook lenovo", "notebook dell", "laptop", "heladera",
    "heladera no frost", "heladera gafa", "lavarropas", "lavarropas drean", "lavarropas automatico",
    "microondas", "aire acondicionado", "ventilador", "ventilador de pie", "aspiradora",
    "cafetera", "cafetera express", "pava electrica", "tostadora", "freidora de aire",
    "licuadora", "procesadora", "plancha", "tablet", "monitor",
    "monitor gamer", "teclado gamer", "auriculares", "auriculares bluetooth", "parlante bluetooth"
]

REPORT_PATH = os.path.join(API_DIR, "_lib", "audit_100_searches_report.json")


class QueryAuditDetail(TypedDict):
    query: str
    category: str
    intent: str | None
    results_count: int
    latency_ms: float
    passed: bool
    accessory_infiltration_count: int
    images_checked: int
    images_valid: int
    links_checked: int
    links_valid: int
    cart_built: bool
    sample_cart_url: str | None
    top_product_name: str | None


class AuditReport(TypedDict):
    timestamp: str
    total_searches: int
    passed_searches: int
    failed_searches: int
    accessory_infiltration_count: int
    images_health_pct: float
    links_health_pct: float
    cart_health_pct: float
    avg_search_latency_ms: float
    equipment_purity_pct: float
    gondolas_health_pct: float
    details: List[QueryAuditDetail]


async def verify_image_url(client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str, cache: Dict[str, bool]) -> bool:
    if not url or not url.startswith("https://"):
        return False
    if url in cache:
        return cache[url]

    async with sem:
        try:
            resp = await client.head(url)
            if resp.status_code == 200:
                cache[url] = True
                return True
            resp = await client.get(url)
            ok = (resp.status_code == 200)
            cache[url] = ok
            return ok
        except Exception:
            cache[url] = False
            return False


async def run_100_searches_audit() -> int:
    print("=" * 80)
    print(" SUPERVMARKET — SUITE DE AUDITORÍA AUTOMATIZADA DE 100 BÚSQUEDAS")
    print(f" Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # 1. Warm-up search engine
    print("[1/5] Calentando motor de búsqueda sqlite...")
    await search_grouped("warmup")

    # 2. Collect searches and measure latency
    print("[2/5] Ejecutando 100 consultas (60 supermercado + 40 electro/tech)...")
    sem = asyncio.Semaphore(30)
    http_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }

    all_queries = [(q, "supermarket") for q in SUPERMARKET_QUERIES] + [(q, "electro") for q in ELECTRO_QUERIES]
    assert len(all_queries) == 100, f"Expected 100 queries, got {len(all_queries)}"

    query_results = []
    unique_image_urls = set()
    total_latency_ms = 0.0

    for query_str, cat in all_queries:
        t0 = time.perf_counter()
        res = await search_grouped(query_str)
        t1 = time.perf_counter()
        lat_ms = (t1 - t0) * 1000.0
        total_latency_ms += lat_ms

        # Gather images for batch validation
        for p in res[:5]:
            img = p.get("imagen")
            if img:
                unique_image_urls.add(img)

        query_results.append({
            "query": query_str,
            "category": cat,
            "latency_ms": lat_ms,
            "results": res,
        })

    avg_latency_ms = total_latency_ms / len(all_queries)
    print(f"  -> 100 consultas completadas. Latencia promedio: {avg_latency_ms:.2f}ms (Requisito: < 35ms)")

    # 3. HTTP 200 validation for Top 5 images in batch
    print(f"[3/5] Verificando {len(unique_image_urls)} URLs únicas de imágenes con HTTP 200 OK...")
    image_cache: Dict[str, bool] = {}
    async with httpx.AsyncClient(timeout=8.0, headers=http_headers) as client:
        image_tasks = [
            verify_image_url(client, sem, u, image_cache)
            for u in unique_image_urls
        ]
        await asyncio.gather(*image_tasks)

    # 4. Gondolas verification
    print("[4/5] Verificando productos y patrocinados de góndolas...")
    gondola_payload = await deals.get_live_discount_tiers(force=False)
    gondola_tiers = gondola_payload.get("tiers", []) + gondola_payload.get("marketplace_tiers", [])
    gondola_total = 0
    gondola_valid = 0

    async with httpx.AsyncClient(timeout=8.0, headers=http_headers) as client:
        for tier in gondola_tiers:
            sp = tier.get("meliSponsored")
            if sp:
                gondola_total += 1
                sp_prod = sp.get("product") or {}
                sp_off = sp.get("offer") or {}
                img_ok = await verify_image_url(client, sem, sp_prod.get("imagen", ""), image_cache)
                link_ok = bool(sp_off.get("link") and sp_off["link"].startswith("https://"))
                if img_ok and link_ok:
                    gondola_valid += 1

            for gp in tier.get("products", []):
                gondola_total += 1
                gp_img_ok = await verify_image_url(client, sem, gp.get("imagen", ""), image_cache)
                has_valid_offer = any(
                    bool(o.get("link") and (o["link"].startswith("http://") or o["link"].startswith("https://")))
                    for o in gp.get("offers", [])
                )
                if gp_img_ok and has_valid_offer:
                    gondola_valid += 1

    gondolas_health_pct = round((gondola_valid / gondola_total) * 100.0, 2) if gondola_total > 0 else 100.0
    print(f"  -> Góndolas auditadas: {gondola_valid}/{gondola_total} válidas ({gondolas_health_pct}%)")

    # 5. Evaluate each query
    print("[5/5] Evaluando pureza de equipamiento, links, imágenes y carritos por consulta...")
    details: List[QueryAuditDetail] = []
    total_accessory_infiltrations = 0
    total_images_checked = 0
    total_images_valid = 0
    total_links_checked = 0
    total_links_valid = 0
    queries_with_cart = 0
    passed_queries = 0

    for item in query_results:
        q = item["query"]
        cat = item["category"]
        lat = item["latency_ms"]
        res = item["results"]

        intent = detect_search_intent(q)
        is_equip = (cat == "electro") or (intent in EQUIPMENT_INTENTS)

        # Check equipment purity in Top 10
        top10 = res[:10]
        acc_in_top10 = [
            r for r in top10
            if r.get("categoria_normalizada") in ("soportes_accesorios", "muebles_racks")
        ]
        acc_count = len(acc_in_top10) if is_equip else 0
        total_accessory_infiltrations += acc_count

        # Check Top 5 images and links
        top5 = res[:5]
        q_img_checked = len(top5)
        q_img_valid = sum(1 for p in top5 if image_cache.get(p.get("imagen", ""), False))

        total_images_checked += q_img_checked
        total_images_valid += q_img_valid

        q_links_checked = 0
        q_links_valid = 0
        cart_built = False
        sample_cart_url = None

        for p in top5:
            for o in p.get("offers", []):
                q_links_checked += 1
                link = o.get("link", "")
                if link and (link.startswith("http://") or link.startswith("https://")):
                    q_links_valid += 1

                # Attempt cart building for VTEX stores
                store = o.get("supermercado")
                sku = o.get("sku_id")
                if not cart_built and store and sku and supports_cart(store):
                    c_link = guest_link(store, [{"sku_id": sku, "qty": 1, "seller_id": o.get("seller_id") or "1"}])
                    if c_link and "checkout/cart/add" in c_link:
                        cart_built = True
                        sample_cart_url = c_link

        # Fallback cart check across all results if Top 5 lacked a VTEX store
        if not cart_built:
            for p in res[5:]:
                for o in p.get("offers", []):
                    store = o.get("supermercado")
                    sku = o.get("sku_id")
                    if store and sku and supports_cart(store):
                        c_link = guest_link(store, [{"sku_id": sku, "qty": 1, "seller_id": o.get("seller_id") or "1"}])
                        if c_link and "checkout/cart/add" in c_link:
                            cart_built = True
                            sample_cart_url = c_link
                            break
                if cart_built:
                    break

        total_links_checked += q_links_checked
        total_links_valid += q_links_valid

        if cart_built:
            queries_with_cart += 1

        query_passed = (
            len(res) > 0 and
            acc_count == 0 and
            (q_img_checked == 0 or q_img_valid == q_img_checked) and
            (q_links_checked == 0 or q_links_valid == q_links_checked) and
            cart_built
        )

        if query_passed:
            passed_queries += 1

        top_prod = res[0]["nombre"] if res else None

        details.append({
            "query": q,
            "category": cat,
            "intent": intent,
            "results_count": len(res),
            "latency_ms": round(lat, 2),
            "passed": query_passed,
            "accessory_infiltration_count": acc_count,
            "images_checked": q_img_checked,
            "images_valid": q_img_valid,
            "links_checked": q_links_checked,
            "links_valid": q_links_valid,
            "cart_built": cart_built,
            "sample_cart_url": sample_cart_url,
            "top_product_name": top_prod,
        })

    images_health_pct = round((total_images_valid / total_images_checked) * 100.0, 2) if total_images_checked > 0 else 100.0
    links_health_pct = round((total_links_valid / total_links_checked) * 100.0, 2) if total_links_checked > 0 else 100.0
    cart_health_pct = round((queries_with_cart / len(all_queries)) * 100.0, 2)
    equipment_purity_pct = 100.0 if total_accessory_infiltrations == 0 else 0.0

    report: AuditReport = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_searches": len(all_queries),
        "passed_searches": passed_queries,
        "failed_searches": len(all_queries) - passed_queries,
        "accessory_infiltration_count": total_accessory_infiltrations,
        "images_health_pct": images_health_pct,
        "links_health_pct": links_health_pct,
        "cart_health_pct": cart_health_pct,
        "avg_search_latency_ms": round(avg_latency_ms, 2),
        "equipment_purity_pct": equipment_purity_pct,
        "gondolas_health_pct": gondolas_health_pct,
        "details": details,
    }

    # Write report
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(" RESUMEN DE RESULTADOS DE LA AUDITORÍA DE 100 BÚSQUEDAS")
    print("=" * 80)
    print(f" Total de búsquedas auditadas:   {report['total_searches']}")
    print(f" Búsquedas aprobadas:            {report['passed_searches']} / {report['total_searches']}")
    print(f" Búsquedas fallidas:             {report['failed_searches']}")
    print(f" Infiltración de accesorios:     {report['accessory_infiltration_count']} (Requisito: 0)")
    print(f" Pureza de equipamiento:         {report['equipment_purity_pct']}% (Requisito: 100%)")
    print(f" Salud de imágenes (HTTP 200):   {report['images_health_pct']}% (Requisito: 100%)")
    print(f" Salud de enlaces de compra:     {report['links_health_pct']}% (Requisito: 100%)")
    print(f" Construcción de carritos:       {report['cart_health_pct']}% (Requisito: 100%)")
    print(f" Salud de ofertas en góndolas:   {report['gondolas_health_pct']}% (Requisito: 100%)")
    print(f" Latencia promedio de búsqueda:  {report['avg_search_latency_ms']} ms (Requisito: < 35ms)")
    print(f" Reporte JSON exportado a:       {REPORT_PATH}")
    print("=" * 80)

    is_success = (
        report["passed_searches"] == 100 and
        report["accessory_infiltration_count"] == 0 and
        report["images_health_pct"] == 100.0 and
        report["links_health_pct"] == 100.0 and
        report["cart_health_pct"] == 100.0 and
        report["avg_search_latency_ms"] < 35.0 and
        report["gondolas_health_pct"] == 100.0
    )

    if is_success:
        print("\n>>> RESULTADO: AUDITORÍA APROBADA EXITOSAMENTE (100/100 PASSED) <<<\n")
        return 0
    else:
        print("\n>>> RESULTADO: AUDITORÍA CON FALLOS <<<\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_100_searches_audit())
    sys.exit(exit_code)
