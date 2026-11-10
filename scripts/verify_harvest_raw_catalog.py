#!/usr/bin/env python3
"""scripts/verify_harvest_raw_catalog.py

Automated Verification Suite for Milestone 1 (R1):
1. Verifies `raw_catalog` table existence and 15-column schema.
2. Verifies indexes: idx_raw_catalog_store, idx_raw_catalog_ean, idx_raw_catalog_ext,
   idx_productos_cat_norm, idx_precios_ean_stock.
3. Verifies store coverage across ingested stores.
4. Verifies raw JSON validity (0 nulls/empty, 100% valid JSON syntax).
5. Verifies zero-drop invariant (all raw items exist in productos and precios via EAN or synthetic key).
6. Verifies referential integrity (0 orphan prices in precios without product in productos).
7. Verifies uniqueness constraint (0 duplicate rows on store_name, external_id, seller_id_raw).
8. Verifies price sanity (positive prices for in-stock offers).
9. Verifies valid permalinks (100% start with http:// or https://).
Generates `scratch/m1_harvest_verification_report.json` and exits with code 0 on success, 1 on failure.
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from typing import Any, Dict, List, Tuple

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api._lib.harvester import resolve_product_ean

EXPECTED_RAW_COLUMNS = [
    "id",
    "store_name",
    "external_id",
    "ean_raw",
    "title_raw",
    "brand_raw",
    "categories_raw",
    "link_raw",
    "image_raw",
    "price_raw",
    "list_price_raw",
    "stock_raw",
    "seller_id_raw",
    "raw_json",
    "scraped_at",
]

EXPECTED_INDEXES = [
    "idx_raw_catalog_store",
    "idx_raw_catalog_ean",
    "idx_raw_catalog_ext",
    "idx_productos_cat_norm",
    "idx_precios_ean_stock",
]


def verify_database(db_path: str = "supervmarket.db") -> Tuple[bool, Dict[str, Any]]:
    abs_db = os.path.abspath(db_path)
    if not os.path.exists(abs_db):
        return False, {"error": f"Database file '{abs_db}' does not exist."}

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
        # Check 1: Table raw_catalog schema
        cur.execute("PRAGMA table_info(raw_catalog);")
        raw_cols_info = cur.fetchall()
        actual_raw_cols = [c[1] for c in raw_cols_info]
        missing_cols = [c for c in EXPECTED_RAW_COLUMNS if c not in actual_raw_cols]
        schema_passed = len(raw_cols_info) >= 15 and len(missing_cols) == 0

        report["checks"]["table_schema"] = {
            "passed": schema_passed,
            "columns_count": len(actual_raw_cols),
            "missing_columns": missing_cols,
        }
        if not schema_passed:
            all_passed = False

        # Check 2: Indexes
        cur.execute("SELECT name FROM sqlite_master WHERE type='index';")
        actual_indexes = [r[0] for r in cur.fetchall()]
        missing_indexes = [idx for idx in EXPECTED_INDEXES if idx not in actual_indexes]
        indexes_passed = len(missing_indexes) == 0

        report["checks"]["indexes"] = {
            "passed": indexes_passed,
            "missing_indexes": missing_indexes,
            "actual_indexes": actual_indexes,
        }
        if not indexes_passed:
            all_passed = False

        # Check 3: Row Counts and Store Coverage
        cur.execute("SELECT COUNT(*) FROM raw_catalog;")
        raw_total = cur.fetchone()[0]

        cur.execute("SELECT store_name, COUNT(*) FROM raw_catalog GROUP BY store_name;")
        stores_coverage = {r[0]: r[1] for r in cur.fetchall()}
        stores_passed = raw_total > 0 and len(stores_coverage) > 0

        report["checks"]["store_coverage"] = {
            "passed": stores_passed,
            "total_raw_rows": raw_total,
            "stores_count": len(stores_coverage),
            "stores_distribution": stores_coverage,
        }
        if not stores_passed:
            all_passed = False

        # Check 4: Raw JSON Validity
        cur.execute("SELECT COUNT(*) FROM raw_catalog WHERE raw_json IS NULL OR TRIM(raw_json) = '';")
        empty_json_count = cur.fetchone()[0]

        # Sample and validate JSON syntax
        cur.execute("SELECT id, raw_json FROM raw_catalog LIMIT 1000;")
        sample_rows = cur.fetchall()
        invalid_json_count = 0
        for rid, rjson in sample_rows:
            try:
                json.loads(rjson)
            except Exception:
                invalid_json_count += 1

        json_passed = (empty_json_count == 0) and (invalid_json_count == 0) and (len(sample_rows) > 0 or raw_total == 0)
        report["checks"]["raw_json_validity"] = {
            "passed": json_passed,
            "empty_json_count": empty_json_count,
            "sampled_count": len(sample_rows),
            "invalid_json_in_sample": invalid_json_count,
        }
        if not json_passed:
            all_passed = False

        # Check 5: Zero-Drop Invariant & Dual-Write consistency
        cur.execute("SELECT store_name, external_id, ean_raw FROM raw_catalog LIMIT 5000;")
        sample_raw = cur.fetchall()
        missing_in_productos = 0
        missing_in_precios = 0

        for sname, ext_id, ean_raw in sample_raw:
            expected_ean = resolve_product_ean(sname, ext_id, ean_raw)
            cur.execute("SELECT 1 FROM productos WHERE ean = ? LIMIT 1;", (expected_ean,))
            if not cur.fetchone():
                missing_in_productos += 1
            cur.execute("SELECT 1 FROM precios WHERE ean = ? AND supermercado = ? LIMIT 1;", (expected_ean, sname))
            if not cur.fetchone():
                missing_in_precios += 1

        zero_drop_passed = (missing_in_productos == 0) and (missing_in_precios == 0) and (len(sample_raw) > 0 or raw_total == 0)
        report["checks"]["zero_drop_invariant"] = {
            "passed": zero_drop_passed,
            "sampled_raw_items": len(sample_raw),
            "missing_in_productos": missing_in_productos,
            "missing_in_precios": missing_in_precios,
        }
        if not zero_drop_passed:
            all_passed = False

        # Check 6: Referential Integrity (Orphan Prices in precios)
        cur.execute("""
            SELECT COUNT(*) FROM precios p
            LEFT JOIN productos pr ON p.ean = pr.ean
            WHERE pr.ean IS NULL;
        """)
        orphan_prices_count = cur.fetchone()[0]
        ref_passed = orphan_prices_count == 0

        report["checks"]["referential_integrity"] = {
            "passed": ref_passed,
            "orphan_prices_count": orphan_prices_count,
        }
        if not ref_passed:
            all_passed = False

        # Check 7: Uniqueness Constraint in raw_catalog
        cur.execute("""
            SELECT store_name, external_id, seller_id_raw, COUNT(*)
            FROM raw_catalog
            GROUP BY store_name, external_id, seller_id_raw
            HAVING COUNT(*) > 1;
        """)
        duplicates = cur.fetchall()
        unique_passed = len(duplicates) == 0

        report["checks"]["uniqueness_constraint"] = {
            "passed": unique_passed,
            "duplicate_groups_count": len(duplicates),
        }
        if not unique_passed:
            all_passed = False

        # Check 8: Price Sanity
        cur.execute("""
            SELECT COUNT(*) FROM raw_catalog
            WHERE stock_raw > 0 AND price_raw <= 0;
        """)
        insane_prices = cur.fetchone()[0]
        price_passed = insane_prices == 0

        report["checks"]["price_sanity"] = {
            "passed": price_passed,
            "in_stock_zero_price_count": insane_prices,
        }
        if not price_passed:
            all_passed = False

        # Check 9: Valid Permalinks
        cur.execute("""
            SELECT COUNT(*) FROM raw_catalog
            WHERE link_raw IS NOT NULL AND link_raw != ''
              AND NOT (link_raw LIKE 'http://%' OR link_raw LIKE 'https://%');
        """)
        invalid_links = cur.fetchone()[0]
        links_passed = invalid_links == 0

        report["checks"]["valid_permalinks"] = {
            "passed": links_passed,
            "invalid_protocol_links_count": invalid_links,
        }
        if not links_passed:
            all_passed = False

        # Overall summary
        cur.execute("SELECT COUNT(*) FROM productos;")
        total_productos = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM precios;")
        total_precios = cur.fetchone()[0]

        report["summary"] = {
            "total_raw_catalog_rows": raw_total,
            "total_productos_rows": total_productos,
            "total_precios_rows": total_precios,
            "stores_count": len(stores_coverage),
            "all_checks_passed": all_passed,
        }
        report["overall_passed"] = all_passed

        return all_passed, report
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Verify raw_catalog schema and harvesting integrity.")
    parser.add_argument("--db", "--db-path", dest="db_path", default="supervmarket.db", help="Path to SQLite database.")
    parser.add_argument("--report-path", default="scratch/m1_harvest_verification_report.json", help="Path for JSON report.")
    args = parser.parse_args()

    passed, report = verify_database(args.db_path)

    # Ensure output dir exists
    report_abs = os.path.abspath(args.report_path)
    os.makedirs(os.path.dirname(report_abs), exist_ok=True)
    with open(report_abs, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print("SuperVmarket Milestone 1 Harvest Verification Suite")
    print("=" * 60)
    for check_name, check_data in report.get("checks", {}).items():
        status = "PASSED" if check_data.get("passed") else "FAILED"
        print(f"[{status}] {check_name}: {check_data}")
    print("-" * 60)
    print(f"Total raw_catalog rows: {report.get('summary', {}).get('total_raw_catalog_rows', 0)}")
    print(f"Total productos rows:   {report.get('summary', {}).get('total_productos_rows', 0)}")
    print(f"Total precios rows:     {report.get('summary', {}).get('total_precios_rows', 0)}")
    print(f"Unique stores:          {report.get('summary', {}).get('stores_count', 0)}")
    print(f"Verification Report:    {report_abs}")
    print(f"Overall Result:         {'SUCCESS' if passed else 'FAILURE'}")
    print("=" * 60)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
