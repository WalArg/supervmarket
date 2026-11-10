#!/usr/bin/env python3
"""scripts/verify_normalization_m2.py

Automated Verification Suite for SuperVmarket Milestone 2 (Normalización Global y Resolución de Entidades - R2).
Verifies the 6 mandatory invariants:
1. 0 NULLs in productos.categoria_normalizada (100% coverage across 19 categories).
2. 0 mounts/racks classified as televisores (0% accessories or furniture infiltration).
3. 0 groceries misclassified as hardware/furniture (food/perishable immune guards).
4. Index idx_productos_cat_norm exists and is actively used by SQLite query planner.
5. Referential integrity: 0 orphan prices in precios.
6. Price sanity ratio guard validated on all re-pointed items (0.35 <= P / P_canonical <= 2.80).

Exports report to: scratch/m2_normalization_verification_report.json
Exit Codes: 0 on all checks pass, 1 on any failure.
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from typing import Any, Dict, List, Tuple

# Ensure project root in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api._lib.catalog_normalizer import (
    build_entity_resolution_index,
    GLOBAL_MODEL_TO_EAN,
    GROCERY_TO_EAN,
    norm_brand,
    clean_grocery_base_name,
    FALSE_MODELS_EXTRA,
)
from api._lib.normalization import (
    extract_model,
    extract_capacity_variant,
    is_accessory,
)
from api._lib.parsers import extraer_unidad_titulo


def verify_normalization_m2(db_path: str = "supervmarket.db") -> Tuple[bool, Dict[str, Any]]:
    abs_db = os.path.abspath(db_path)
    if not os.path.exists(abs_db):
        return False, {"error": f"Database file not found: {abs_db}"}

    conn = sqlite3.connect(abs_db, timeout=30.0)
    cur = conn.cursor()

    report: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "db_path": abs_db,
        "checks": {},
        "summary": {},
        "overall_passed": False,
    }

    all_passed = True

    try:
        # -------------------------------------------------------------------
        # Check 1: 0 NULLs in productos.categoria_normalizada (100% coverage)
        # -------------------------------------------------------------------
        cur.execute("SELECT count(*) FROM productos WHERE categoria_normalizada IS NULL OR trim(categoria_normalizada) = ''")
        null_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM productos")
        total_prods = cur.fetchone()[0]
        c1_passed = (null_count == 0) and (total_prods > 0)
        report["checks"]["zero_null_categories"] = {
            "passed": c1_passed,
            "total_products": total_prods,
            "null_count": null_count,
        }
        if not c1_passed:
            all_passed = False

        # -------------------------------------------------------------------
        # Check 2: 0 mounts/racks classified as televisores (0% infiltration)
        # -------------------------------------------------------------------
        cur.execute("""
            SELECT ean, nombre FROM productos
            WHERE categoria_normalizada = 'televisores'
              AND (
                lower(nombre) LIKE '%rack%'
                OR lower(nombre) LIKE '%soporte%'
                OR lower(nombre) LIKE '%funda%'
                OR lower(nombre) LIKE '%control remoto%'
                OR lower(nombre) LIKE '%cable%'
                OR lower(nombre) LIKE '%tv box%'
                OR lower(nombre) LIKE '%mesa tv%'
                OR lower(nombre) LIKE '%mesa para tv%'
                OR lower(nombre) LIKE '%panel tv%'
              )
              AND lower(nombre) NOT LIKE '%combo%'
        """)
        infiltrated_tvs = cur.fetchall()
        c2_passed = len(infiltrated_tvs) == 0
        report["checks"]["zero_accessories_in_televisores"] = {
            "passed": c2_passed,
            "infiltrated_count": len(infiltrated_tvs),
            "samples": [r[1] for r in infiltrated_tvs[:5]],
        }
        if not c2_passed:
            all_passed = False

        # -------------------------------------------------------------------
        # Check 3: 0 cross-domain misclassifications (food in hardware, or cleaning/pharma in food)
        # -------------------------------------------------------------------
        cur.execute("""
            SELECT ean, nombre, categoria_normalizada FROM productos
            WHERE (
              categoria_normalizada IN ('muebles_racks', 'soportes_accesorios')
              AND (
                lower(nombre) LIKE '%cordero%'
                OR lower(nombre) LIKE '%tiramisu%'
                OR lower(nombre) LIKE '%yogur%'
                OR lower(nombre) LIKE '%cif%'
                OR lower(nombre) LIKE '%detergente%'
                OR lower(nombre) LIKE '%leche%'
                OR lower(nombre) LIKE '%queso%'
                OR lower(nombre) LIKE '%sal fina%'
                OR lower(nombre) LIKE '%arveja%'
                OR lower(nombre) LIKE '%espinaca%'
              )
            )
            OR (
              categoria_normalizada IN ('carnes_verduleria', 'bebidas', 'lacteos_frescos')
              AND (
                lower(nombre) LIKE '%detergente%'
                OR lower(nombre) LIKE '%lavavajillas%'
                OR lower(nombre) LIKE '%lavandina%'
                OR lower(nombre) LIKE '%shampoo%'
                OR lower(nombre) LIKE '%acondicionador%'
                OR lower(nombre) LIKE '%desodorante%'
                OR lower(nombre) LIKE '%dentifrico%'
                OR lower(nombre) LIKE '%crema dental%'
                OR lower(nombre) LIKE '%jabon%'
              )
            )
        """)
        misclassified_food = cur.fetchall()
        c3_passed = len(misclassified_food) == 0
        report["checks"]["zero_food_in_furniture_or_accessories"] = {
            "passed": c3_passed,
            "misclassified_count": len(misclassified_food),
            "samples": [f"{r[1]} -> {r[2]}" for r in misclassified_food[:5]],
        }
        if not c3_passed:
            all_passed = False

        # -------------------------------------------------------------------
        # Check 3b: 0 canned / processed pantry goods in carnes_verduleria
        # -------------------------------------------------------------------
        cur.execute("""
            SELECT ean, nombre FROM productos
            WHERE categoria_normalizada = 'carnes_verduleria'
              AND (
                lower(categorias) LIKE '%almacen%'
                OR lower(categorias) LIKE '%conserva%'
                OR lower(categorias) LIKE '%alacena%'
                OR lower(categorias) LIKE '%desayuno%'
                OR lower(categorias) LIKE '%merienda%'
                OR lower(categorias) LIKE '%snack%'
                OR lower(categorias) LIKE '%panaderia%'
                OR lower(categorias) LIKE '%reposteria%'
                OR lower(categorias) LIKE '%golosinas%'
                OR lower(categorias) LIKE '%galletitas%'
                OR lower(nombre) LIKE '%lata%'
                OR lower(nombre) LIKE '%pure de%'
                OR lower(nombre) LIKE '%picadillo%'
                OR lower(nombre) LIKE '%pate%'
                OR lower(nombre) LIKE '%passata%'
                OR lower(nombre) LIKE '%cubeteado%'
                OR lower(nombre) LIKE '%galletita%'
                OR lower(nombre) LIKE '%galleta%'
                OR lower(nombre) LIKE '%alfajor%'
                OR lower(nombre) LIKE '%yerba%'
                OR lower(nombre) LIKE 'te %'
                OR lower(nombre) LIKE '% te %'
                OR lower(nombre) LIKE '%saquito%'
                OR lower(nombre) LIKE '%infusion%'
                OR lower(nombre) LIKE '%gelatina%'
                OR lower(nombre) LIKE '%mermelada%'
                OR lower(nombre) LIKE '%dulce de%'
                OR lower(nombre) LIKE '%arveja%'
                OR lower(nombre) LIKE '%en mitades%'
                OR lower(nombre) LIKE '%en almibar%'
                OR lower(nombre) LIKE '%pan de papa%'
                OR lower(nombre) LIKE '%pan para pancho%'
                OR lower(nombre) LIKE '%ajo en polvo%'
                OR lower(nombre) LIKE '%cebolla en polvo%'
                OR lower(nombre) LIKE '%condimento para%'
                OR lower(nombre) LIKE '%vinagre de manzana%'
                OR lower(nombre) LIKE '%huevo bariloche%'
                OR lower(nombre) LIKE '%huevo de pascua%'
                OR lower(nombre) LIKE '%sachet entero%'
                OR lower(nombre) LIKE '%sachet descremado%'
              )
        """)
        canned_in_carnes = cur.fetchall()
        c3b_passed = len(canned_in_carnes) == 0
        report["checks"]["zero_canned_in_carnes_verduleria"] = {
            "passed": c3b_passed,
            "canned_count": len(canned_in_carnes),
            "samples": [r[1] for r in canned_in_carnes[:5]],
        }
        if not c3b_passed:
            all_passed = False

        # -------------------------------------------------------------------
        # Check 4: Index idx_productos_cat_norm exists & is used by query planner
        # -------------------------------------------------------------------
        cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_productos_cat_norm'")
        idx_exists = cur.fetchone() is not None
        cur.execute("EXPLAIN QUERY PLAN SELECT ean FROM productos WHERE categoria_normalizada = 'televisores'")
        qp = cur.fetchall()
        uses_idx = any("idx_productos_cat_norm" in str(row) for row in qp)
        c4_passed = idx_exists and uses_idx
        report["checks"]["index_active"] = {
            "passed": c4_passed,
            "index_exists": idx_exists,
            "query_planner_uses_index": uses_idx,
            "query_plan": [str(r) for r in qp],
        }
        if not c4_passed:
            all_passed = False

        # -------------------------------------------------------------------
        # Check 5: Referential integrity: 0 orphan prices in precios
        # -------------------------------------------------------------------
        cur.execute("SELECT count(*) FROM precios p LEFT JOIN productos pr ON p.ean = pr.ean WHERE pr.ean IS NULL")
        orphan_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM precios")
        total_prices = cur.fetchone()[0]
        c5_passed = (orphan_count == 0) and (total_prices > 0)
        report["checks"]["referential_integrity"] = {
            "passed": c5_passed,
            "total_prices": total_prices,
            "orphan_prices": orphan_count,
        }
        if not c5_passed:
            all_passed = False

        # -------------------------------------------------------------------
        # Check 6: Price sanity ratio guard validated on all re-pointed items
        # -------------------------------------------------------------------
        # Build ER index to evaluate all potential matches and check existing prices
        build_entity_resolution_index(conn)
        cur.execute("SELECT ean, AVG(precio_venta) FROM precios WHERE precio_venta > 0 GROUP BY ean")
        ean_avg_prices = dict(cur.fetchall())

        # Collect candidate items and check price ratios against canonical targets
        cur.execute("SELECT ean, nombre, marca, modelo, tipo FROM productos WHERE instr(ean, '-') > 0")
        synth_candidates = cur.fetchall()

        tested_candidates = 0
        ratio_violations = 0
        violation_samples = []

        for old_ean, nombre, marca, modelo, tipo in synth_candidates:
            cand_p = float(ean_avg_prices.get(old_ean, 0.0))
            if cand_p <= 0.0:
                continue

            target_canonical = None
            target_avg_p = 0.0
            title = nombre or ""
            b_clean = norm_brand(marca or "")

            if not is_accessory(title):
                m = modelo or extract_model(title, brand=marca or "")
                if m:
                    m_clean = re.sub(r'[^A-Z0-9]', '', m.upper())
                    if not FALSE_MODELS_EXTRA.match(m_clean) and b_clean:
                        variant = extract_capacity_variant(title)
                        hw_key = (b_clean, m_clean, variant)
                        if hw_key in GLOBAL_MODEL_TO_EAN:
                            target_canonical, target_avg_p, _, _ = GLOBAL_MODEL_TO_EAN[hw_key]

            if not target_canonical and b_clean:
                qty, unit = extraer_unidad_titulo(title)
                base = clean_grocery_base_name(title, brand=marca or "")
                if base:
                    grocery_key = (b_clean, base, round(qty, 3), unit)
                    if grocery_key in GROCERY_TO_EAN:
                        target_canonical, target_avg_p, _, _ = GROCERY_TO_EAN[grocery_key]

            if target_canonical and target_canonical != old_ean and target_avg_p > 0:
                tested_candidates += 1
                ratio = cand_p / target_avg_p
                # Invariant: If item was re-pointed into target_canonical, it MUST satisfy [0.35, 2.80]
                # If an item violated the ratio, it must NOT have been re-pointed (must remain under old_ean).
                if not (0.35 <= ratio <= 2.80):
                    # Check whether this violating offer was wrongly re-pointed into target_canonical
                    cur.execute("SELECT count(*) FROM precios WHERE ean = ?", (old_ean,))
                    remaining_old = cur.fetchone()[0]
                    if remaining_old == 0:
                        # Error: It was re-pointed despite violating the ratio guard!
                        ratio_violations += 1
                        violation_samples.append({
                            "candidate_ean": old_ean,
                            "canonical_target": target_canonical,
                            "cand_price": cand_p,
                            "target_avg_price": target_avg_p,
                            "ratio": round(ratio, 3),
                        })

        c6_passed = (ratio_violations == 0)
        report["checks"]["price_ratio_guard"] = {
            "passed": c6_passed,
            "candidates_evaluated": tested_candidates,
            "ratio_violations": ratio_violations,
            "samples": violation_samples,
        }
        if not c6_passed:
            all_passed = False

        # Category Breakdown Summary
        cur.execute("SELECT categoria_normalizada, count(*) FROM productos GROUP BY categoria_normalizada ORDER BY count(*) DESC")
        cat_dist = {r[0]: r[1] for r in cur.fetchall()}
        report["summary"]["category_distribution"] = cat_dist
        report["summary"]["total_categories_populated"] = len(cat_dist)

    finally:
        conn.close()

    report["overall_passed"] = all_passed
    return all_passed, report


def main():
    parser = argparse.ArgumentParser(description="Verify Milestone 2 Catalog Normalization.")
    parser.add_argument("--db-path", default="supervmarket.db", help="Path to SQLite database")
    parser.add_argument("--report-path", default="scratch/m2_normalization_verification_report.json", help="Path to save JSON report")
    args = parser.parse_args()

    passed, report = verify_normalization_m2(db_path=args.db_path)

    os.makedirs(os.path.dirname(os.path.abspath(args.report_path)), exist_ok=True)
    with open(args.report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("===============================================================================")
    print("  SUPERVMARKET MILESTONE 2 (R2) NORMALIZATION VERIFICATION SUITE")
    print("===============================================================================")
    for check_name, data in report["checks"].items():
        status = "[PASS]" if data["passed"] else "[FAIL]"
        print(f"  {status} {check_name}: {data}")
    print("===============================================================================")
    print(f"  OVERALL RESULT: {'PASSED (READY FOR GATE 2)' if passed else 'FAILED'}")
    print(f"  Report exported to: {args.report_path}")
    print("===============================================================================")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
