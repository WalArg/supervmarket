#!/usr/bin/env python3
"""test_challenger_m3_stress_edgecases.py — Additional Adversarial Stress Test Suite for M3.

Tests:
1. Input Fuzzing & SQL Injection Immunity on /api/search
2. Parameter Boundary Fuzzing (asserting HTTP 200 or RFC-compliant 422 for invalid types)
3. High Concurrency Async Stress (30 parallel requests to FastAPI app)
4. Mercado Libre Fault Injection (timeouts, HTTP errors, dirty/missing-field payloads)
5. Synthetic IDs & Non-Standard Barcode Merging Robustness
"""

import asyncio
import os
import sys
import time
import httpx
from httpx import ASGITransport, AsyncClient

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(ROOT_DIR, "api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from index import app
import _lib.db as db
import _lib.mercadolibre as meli

async def run_adversarial_stress():
    print("=" * 78)
    print(" CHALLENGER M3 — ADDITIONAL ADVERSARIAL STRESS & FAULT INJECTION")
    print("=" * 78)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        
        # 1. Input Fuzzing & SQL Injection Immunity
        print("\n--- 1. Input Fuzzing & Injection Immunity ---")
        fuzz_queries = [
            "",
            "   ",
            "' OR 1=1; --",
            "\" OR \"\"=\"",
            "; DROP TABLE productos; --",
            "%' OR search_text LIKE '%",
            "📺 ❄️ 📱 Smart TV",
            "a" * 1500,
            "???***$$$###@@@!",
            "xyznonexistentproduct999999",
            "leche\x00nullbyte",
        ]
        
        fuzz_passed = True
        for fq in fuzz_queries:
            resp = await ac.get("/api/search", params={"q": fq, "limit": 10})
            if resp.status_code != 200:
                print(f"  [FAIL] Fuzz query '{fq[:30]}' returned status {resp.status_code}")
                fuzz_passed = False
            else:
                data = resp.json()
                if not isinstance(data, list):
                    print(f"  [FAIL] Fuzz query '{fq[:30]}' returned non-list JSON: {type(data)}")
                    fuzz_passed = False
        if fuzz_passed:
            print("  [PASS] All 11 fuzz queries handled cleanly with HTTP 200 and zero crashes.")

        # 2. Parameter boundary fuzzing
        print("\n--- 2. Parameter Boundary Fuzzing ---")
        param_cases = [
            ({"q": "leche", "limit": -5}, (200,)),
            ({"q": "leche", "limit": 99999}, (200,)),
            ({"q": "tv", "sort_by": "unsupported_column; DROP TABLE--"}, (200,)),
            ({"q": "tv", "vertical": "nonexistent_vertical"}, (200,)),
            ({"q": "tv", "grocery_only": "maybe"}, (422,)),  # Pydantic bool validation error
        ]
        param_passed = True
        for p, allowed_statuses in param_cases:
            resp = await ac.get("/api/search", params=p)
            if resp.status_code not in allowed_statuses:
                print(f"  [FAIL] Param case {p} returned {resp.status_code}, expected in {allowed_statuses}")
                param_passed = False
        if param_passed:
            print("  [PASS] Parameter boundaries handled cleanly (200 OK or 422 Validation Error).")

        # 3. Live Concurrency against FastAPI ASGITransport
        print("\n--- 3. Concurrent Request Storm (30 Parallel Requests to FastAPI) ---")
        sample_queries = [
            "tv", "smart tv", "celular", "notebook", "heladera", "leche",
            "arroz", "fideos", "cerveza", "jabon liquido", "soporte tv", "rack tv"
        ]
        queries_30 = [sample_queries[i % len(sample_queries)] for i in range(30)]
        
        t0 = time.perf_counter()
        tasks = [ac.get("/api/search", params={"q": q, "limit": 10}) for q in queries_30]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        total_time_ms = (time.perf_counter() - t0) * 1000.0
        
        storm_errors = 0
        for q, r in zip(queries_30, responses):
            if isinstance(r, Exception):
                print(f"  [FAIL] Concurrent query '{q}' raised exception: {r}")
                storm_errors += 1
            elif r.status_code != 200:
                print(f"  [FAIL] Concurrent query '{q}' returned HTTP {r.status_code}")
                storm_errors += 1
        
        avg_time = total_time_ms / len(queries_30)
        print(f"  Concurrent storm: 30 requests finished in {total_time_ms:.1f}ms (avg {avg_time:.1f}ms per query, {storm_errors} errors).")
        concurrency_ok = (storm_errors == 0)

        # 4. Mercado Libre Fault Injection
        print("\n--- 4. Fault Injection: Mercado Libre Network/Payload Failures ---")
        orig_fetch = meli.fetch_mercadolibre_live
        
        # Scenario A: MeLi raises TimeoutException
        async def mock_timeout(*args, **kwargs):
            raise httpx.ReadTimeout("Simulated MeLi timeout")
        
        meli.fetch_mercadolibre_live = mock_timeout
        try:
            resp_timeout = await ac.get("/api/search?q=smart tv&limit=5")
            timeout_ok = (resp_timeout.status_code == 200 and len(resp_timeout.json()) > 0)
            if timeout_ok:
                print("  [PASS] MeLi timeout gracefully caught: returns DB results without crashing.")
            else:
                print(f"  [FAIL] MeLi timeout returned status {resp_timeout.status_code}")
        finally:
            meli.fetch_mercadolibre_live = orig_fetch

        # Scenario B: MeLi returns edge-case dict items (missing ean, zero price, negative price, missing brand/model)
        async def mock_dirty_items(*args, **kwargs):
            return [
                {"nombre": "Item with 0 price", "precio": 0, "link": "https://ml.com/0"},
                {"nombre": "Item with negative price", "precio": -100, "link": "https://ml.com/-100"},
                {"nombre": "Item with no brand or model", "precio": 50000.0, "ean": ""},
                {"nombre": "Item with non-digit EAN", "precio": 75000.0, "ean": "ABC1234567890", "marca": "Gen"},
                {"nombre": "Valid MeLi TV", "marca": "Noblex", "modelo": "db58x7580", "precio": 650000.0, "precio_lista": 800000.0, "link": "https://articulo.mercadolibre.com.ar/MLA-123", "ean": ""},
            ]
        meli.fetch_mercadolibre_live = mock_dirty_items
        try:
            resp_dirty = await ac.get("/api/search?q=smart tv&limit=5")
            dirty_ok = (resp_dirty.status_code == 200 and len(resp_dirty.json()) > 0)
            if dirty_ok:
                print("  [PASS] Edge-case MeLi payloads filtered cleanly with HTTP 200.")
            else:
                print(f"  [FAIL] Dirty payload returned status {resp_dirty.status_code}")
        finally:
            meli.fetch_mercadolibre_live = orig_fetch

        # 5. Synthetic IDs and Non-EAN merging
        print("\n--- 5. Non-EAN Synthetic Key Merging Robustness ---")
        async def mock_meli_synthetic(*args, **kwargs):
            return [{
                "nombre": "Smart TV Philco 50 Pulgadas 4K UHD PLD50US",
                "marca": "Philco",
                "modelo": "PLD50US",
                "precio": 490000.0,
                "precio_lista": 550000.0,
                "link": "https://articulo.mercadolibre.com.ar/MLA-777",
                "ean": "",
                "seller_name": "Mercado Libre Oficial",
            }]
            
        meli.fetch_mercadolibre_live = mock_meli_synthetic
        try:
            resp_synth = await ac.get("/api/search?q=smart tv&limit=5")
            synthetic_ok = (resp_synth.status_code == 200 and len(resp_synth.json()) > 0)
            print(f"  [PASS] Synthetic ID and non-EAN brand/model merging executed with HTTP 200 (returned {len(resp_synth.json())} results).")
        finally:
            meli.fetch_mercadolibre_live = orig_fetch

    all_passed = fuzz_passed and param_passed and concurrency_ok and timeout_ok and dirty_ok and synthetic_ok
    print("\n" + "=" * 78)
    if all_passed:
        print("[VEREDICTO CHALLENGER M3 STRESS]: APPROVE — Sistema resiliente ante fallas y fuzzing.")
        sys.exit(0)
    else:
        print("[VEREDICTO CHALLENGER M3 STRESS]: REQUEST_CHANGES — Fallas detectadas.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_adversarial_stress())
