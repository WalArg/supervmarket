#!/usr/bin/env python3
"""scripts/relevamiento_tamano_catalogos.py

Releva el tamaño real del catálogo disponible en cada una de las 42 tiendas registradas
consultando el encabezado 'resources' de la API de VTEX, metadata de Endeca de Coto,
y sitemaps/JSON de Shopify/Custom, contrastándolo con lo almacenado actualmente en raw_catalog.
"""

import asyncio
import os
import re
import sqlite3
import sys
import time
from typing import Dict, Any, Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import httpx
from api._lib.stores import STORE_REGISTRY, sales_channel, get_store_meta

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

async def probe_vtex_store_total(client: httpx.AsyncClient, store_name: str, domain: str, sc: str) -> Optional[int]:
    """Queries VTEX search endpoint to extract total from 'resources' header."""
    urls_to_try = [
        f"{domain.rstrip('/')}/api/catalog_system/pub/products/search?_from=0&_to=0" + (f"&sc={sc}" if sc and sc != 'none' else ""),
        f"{domain.rstrip('/')}/api/catalog_system/pub/products/search?_from=0&_to=0",
        f"{domain.rstrip('/')}/api/catalog_system/pub/products/search?O=OrderByTopSaleDESC&_from=0&_to=0",
    ]
    for url in urls_to_try:
        try:
            resp = await client.get(url, timeout=12.0)
            if resp.status_code in (200, 206):
                res_header = resp.headers.get("resources", "")
                if "/" in res_header:
                    val = res_header.split("/")[-1].strip()
                    if val.isdigit() and int(val) > 0:
                        return int(val)
        except Exception:
            continue
    return None

async def probe_coto_total(client: httpx.AsyncClient) -> Optional[int]:
    """Queries Coto Endeca endpoint to find totalNumRecs."""
    url = "https://www.coto.com.ar/sitios/cdigi/categoria?format=json&Nrpp=1&No=0"
    try:
        resp = await client.get(url, timeout=15.0)
        if resp.status_code == 200:
            data = resp.json()
            # Traverse Endeca JSON for totalNumRecs
            def find_total(obj):
                if isinstance(obj, dict):
                    if "totalNumRecs" in obj:
                        return int(obj["totalNumRecs"])
                    for v in obj.values():
                        res = find_total(v)
                        if res is not None:
                            return res
                elif isinstance(obj, list):
                    for item in obj:
                        res = find_total(item)
                        if res is not None:
                            return res
                return None
            return find_total(data)
    except Exception:
        pass
    return None

async def probe_shopify_total(client: httpx.AsyncClient, domain: str) -> Optional[int]:
    """Inspects sitemap_products_*.xml to count total URLs."""
    try:
        sitemap_url = f"{domain.rstrip('/')}/sitemap.xml"
        resp = await client.get(sitemap_url, timeout=12.0)
        if resp.status_code == 200:
            matches = re.findall(r"<loc>\s*(https?://[^<\s]+sitemap_products[^<\s]*\.xml[^<\s]*)\s*</loc>", resp.text, re.IGNORECASE)
            if not matches:
                matches = [f"{domain.rstrip('/')}/sitemap_products_1.xml"]
            total_urls = 0
            for sm in matches[:5]:
                sm_resp = await client.get(sm, timeout=12.0)
                if sm_resp.status_code == 200:
                    urls = re.findall(r"<loc>(https?://[^<]+)</loc>", sm_resp.text)
                    total_urls += len(urls)
            if total_urls > 0:
                return total_urls
    except Exception:
        pass
    return None

async def main():
    conn = sqlite3.connect("supervmarket.db")
    cur = conn.cursor()
    
    # Obtener conteos actuales en la base de datos
    db_counts = dict(cur.execute("SELECT store_name, COUNT(*) FROM raw_catalog GROUP BY store_name").fetchall())
    
    print("================================================================================")
    print(" RELEVAMIENTO DE TAMAÑO TOTAL REAL DE CATÁLOGOS vs BASE ACTUAL SUPERVMARKET")
    print("================================================================================")
    
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
    }
    
    results = []
    
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15.0) as client:
        tasks = []
        for store_key, meta in STORE_REGISTRY.items():
            st_name = meta.get("nombre", store_key)
            dom = meta.get("dominio", "")
            plat = meta.get("plataforma", "vtex")
            sc = sales_channel(store_key)
            tasks.append((store_key, st_name, dom, plat, sc))

        # Medición concurrente con semáforo
        sem = asyncio.Semaphore(10)

        async def probe(item):
            sk, name, dom, plat, sc = item
            async with sem:
                total_real = None
                if plat == "vtex":
                    total_real = await probe_vtex_store_total(client, name, dom, sc)
                elif plat == "shopify":
                    total_real = await probe_shopify_total(client, dom)
                elif "coto" in name.lower():
                    total_real = await probe_coto_total(client)
                
                current = db_counts.get(name, db_counts.get(sk, 0))
                return {
                    "store_key": sk,
                    "store_name": name,
                    "platform": plat,
                    "current_db": current,
                    "real_total": total_real,
                }

        probe_tasks = [probe(it) for it in tasks]
        results = await asyncio.gather(*probe_tasks)

    # Ordenar por tamaño real descendente
    results.sort(key=lambda x: (x["real_total"] or 0), reverse=True)

    print(f"\n{'Tienda':<24} | {'Plataforma':<10} | {'En Base DB':<10} | {'Total Real en Tienda':<22} | {'% En Base':<10} | {'Faltantes':<10}")
    print("-" * 96)

    sum_db = 0
    sum_real = 0
    capped_stores = []

    for r in results:
        st = r["store_name"]
        plat = r["platform"]
        cur_cnt = r["current_db"]
        real_cnt = r["real_total"]
        sum_db += cur_cnt

        if real_cnt is not None:
            sum_real += real_cnt
            pct = (cur_cnt / real_cnt * 100.0) if real_cnt > 0 else 0.0
            missing = max(0, real_cnt - cur_cnt)
            real_str = f"{real_cnt:,} productos"
            pct_str = f"{pct:5.1f}%"
            missing_str = f"{missing:,}"
            if real_cnt > cur_cnt + 500:
                capped_stores.append((st, cur_cnt, real_cnt, missing))
        else:
            real_str = "No expuesto / Live"
            pct_str = "N/A"
            missing_str = "N/A"

        print(f"{st:<24} | {plat:<10} | {cur_cnt:<10,d} | {real_str:<22} | {pct_str:<10} | {missing_str:<10}")

    print("=" * 96)
    print(f"TOTALES MEDIDOS: En Base SuperVmarket = {sum_db:,} | Total Real en Tiendas = {sum_real:,}")
    print(f"Tiendas claramente limitadas por topes previos: {len(capped_stores)}")
    print("\nTop tiendas con mayor cantidad de productos pendientes por recolectar:")
    for st, c, r, m in sorted(capped_stores, key=lambda x: x[3], reverse=True)[:15]:
        print(f"  * {st:<22}: Tenemos {c:,} de {r:,} ({round(c/r*100, 1)}%) -> Faltan {m:,} productos")

if __name__ == "__main__":
    asyncio.run(main())
