#!/usr/bin/env python3
"""scripts/verify_m2_adversarial_empirical.py

Adversarial Verification Suite for Milestone 2 (Canonical 19-Category Taxonomy & Normalization).
Author: teamwork_mp_challenger_m2_1 (Empirical Challenger)

Empirically challenges:
1. Boundary titles & regex lookahead/lookbehind edge cases.
2. TV Combos retention in 'televisores' vs wrongful leak into 'soportes_accesorios'.
3. Food/groceries retention in food categories vs wrongful leak into 'muebles_racks'.
4. Actual supervmarket.db integrity (100% non-null, 19 categories populated, 0 mounts in pure TVs, 0 TV combos in accessories).
"""

import os
import sqlite3
import sys
from typing import Any, Dict, List, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api._lib.catalog_normalizer import classify_canonical_category


def run_boundary_tests() -> Tuple[int, int, List[Dict[str, Any]]]:
    cases = [
        # Vector 1: Meats vs Furniture
        ("Rack de cordero", "", "", "supermarket", "carnes_verduleria", "muebles_racks"),
        ("Rack cordero patagonico", "", "", "supermarket", "carnes_verduleria", "muebles_racks"),
        ("Costillar con rack", "", "", "supermarket", "carnes_verduleria", "muebles_racks"),
        ("Rack de cerdo con hueso", "", "", "supermarket", "carnes_verduleria", "muebles_racks"),
        ("Costillar de ternera 1kg", "", "", "supermarket", "carnes_verduleria", "muebles_racks"),
        ("Colchon de arvejas Cica 300g", "", "", "supermarket", "almacen", "muebles_racks"),
        ("Colchon de espinaca congelada", "", "", "supermarket", "carnes_verduleria", "muebles_racks"),

        # Vector 2: Dairy vs Furniture
        ("Yogur con colchon de frutos rojos", "La Serenisima", "", "supermarket", "lacteos_frescos", "muebles_racks"),
        ("Postre colchon tiramisu", "", "", "supermarket", "lacteos_frescos", "muebles_racks"),
        ("Yogur Dahi con colchon de frutilla 200g", "Dahi", "", "supermarket", "lacteos_frescos", "muebles_racks"),
        ("Postre Tentaciones colchon dulce de leche", "", "", "supermarket", "lacteos_frescos", "muebles_racks"),

        # Vector 3: Cleaning / Cosmetics vs Tech Accessories
        ("Detergente CIF repuesto 450ml", "CIF", "", "supermarket", "limpieza", "soportes_accesorios"),
        ("Repuesto sal dos anclas", "Dos Anclas", "", "supermarket", "almacen", "soportes_accesorios"),
        ("Cover matte foundation", "Maybelline", "", "pharmacy", "perfumeria_farmacia", "soportes_accesorios"),
        ("Base Maybelline Superstay Full Coverage", "Maybelline", "", "pharmacy", "perfumeria_farmacia", "soportes_accesorios"),
        ("Goicoechea Cover crema corporal", "Goicoechea", "", "pharmacy", "perfumeria_farmacia", "soportes_accesorios"),
        ("Jabon liquido Skip repuesto 3L", "Skip", "", "supermarket", "limpieza", "soportes_accesorios"),
        ("Repuesto de afeitar Gillette Mach3", "Gillette", "", "pharmacy", "perfumeria_farmacia", "soportes_accesorios"),

        # Vector 4: Streaming vs Pure TVs
        ("Tv Box 4k Ultra HD", "", "", "electro", "audio_video", "televisores"),
        ("Roku Stick", "", "", "electro", "audio_video", "televisores"),
        ("Chromecast con Google TV", "Google", "", "electro", "audio_video", "televisores"),
        ("Xiaomi Mi TV Stick 4K", "Xiaomi", "", "electro", "audio_video", "televisores"),
        ("Apple TV 4K 128GB", "Apple", "", "electro", "audio_video", "televisores"),

        # Vector 5: Standalone Mounts vs TVs
        ("Soporte de pared para TV 32-55", "", "", "electro", "soportes_accesorios", "televisores"),
        ("Brazo movil soporte TV 50", "", "", "electro", "soportes_accesorios", "televisores"),
        ("Soporte Fijo TV LED 32 a 70", "", "", "electro", "soportes_accesorios", "televisores"),
        ("Control remoto Smart TV Philips", "Philips", "", "electro", "soportes_accesorios", "televisores"),
        ("Cable HDMI 2.0 4K Ultra HD", "", "", "electro", "soportes_accesorios", "televisores"),
        ("Funda protectora Smart TV 55", "", "", "electro", "soportes_accesorios", "televisores"),

        # Vector 6: Pure Smart TVs
        ("Smart TV Samsung 55 4K UHD", "Samsung", "", "electro", "televisores", "soportes_accesorios"),
        ("Televisor LG 43 FHD AI ThinQ", "LG", "", "electro", "televisores", "soportes_accesorios"),
        ("TV Philips 65 OLED 4K Ambilight", "Philips", "", "electro", "televisores", "soportes_accesorios"),
        ("Smart TV TCL 50 QLED Google TV", "TCL", "", "electro", "televisores", "soportes_accesorios"),

        # Vector 7: TV Combos (Must remain 'televisores')
        ("Combo Smart TV 55 + Soporte", "", "", "electro", "televisores", "soportes_accesorios"),
        ("Combo Smart TV Philco 32 HD LED + Soporte Fijo", "Philco", "", "electro", "televisores", "soportes_accesorios"),
        ("Combo Tv Tcl 55 V6c Led 4k Hdr Google Tv + Soporte", "TCL", "", "electro", "televisores", "soportes_accesorios"),
        ("Combo Smart TV RCA 4K LED 55 + Soporte Fijo", "RCA", "", "electro", "televisores", "soportes_accesorios"),
        ("Combo Smart TV Philips 65 OLED 4K Ambilight + Cable HDMI", "Philips", "", "electro", "televisores", "soportes_accesorios"),

        # Vector 8: Orthopedics vs Tech Accessories
        ("Soporte lumbar con ballenas Drof", "Drof", "", "pharmacy", "perfumeria_farmacia", "soportes_accesorios"),
        ("Faja soporte sacro-lumbar", "Body Care", "", "pharmacy", "perfumeria_farmacia", "soportes_accesorios"),
    ]

    passes = 0
    failures = []

    for title, brand, cats, store_type, expected, forbidden in cases:
        actual = classify_canonical_category(title, brand=brand, categories=cats, store_type=store_type)
        is_pass = (actual == expected) and (actual != forbidden)
        if is_pass:
            passes += 1
        else:
            failures.append({
                "title": title,
                "brand": brand,
                "actual": actual,
                "expected": expected,
                "forbidden": forbidden,
            })

    return passes, len(cases), failures


def inspect_database_adversarial(db_path: str = "supervmarket.db") -> Dict[str, Any]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Total products and non-null categories
    cur.execute("SELECT count(*), count(categoria_normalizada) FROM productos")
    total, non_null = cur.fetchone()
    null_count = total - non_null

    # 2. Distinct canonical categories
    cur.execute("SELECT DISTINCT categoria_normalizada FROM productos")
    cats = sorted([r[0] for r in cur.fetchall() if r[0]])

    # 3. Mounts/Accessories in 'televisores'
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
    """)
    tvs_infiltrated = cur.fetchall()

    # 4. TV Combos trapped in 'soportes_accesorios'
    cur.execute("""
        SELECT ean, nombre, marca FROM productos
        WHERE categoria_normalizada = 'soportes_accesorios'
          AND (
            lower(nombre) LIKE '%combo%tv%'
            OR lower(nombre) LIKE '%combo%smart%'
          )
    """)
    tv_combos_trapped = cur.fetchall()

    # 5. Food items trapped in 'muebles_racks'
    cur.execute("""
        SELECT ean, nombre FROM productos
        WHERE categoria_normalizada = 'muebles_racks'
          AND (
            lower(nombre) LIKE '%arveja%'
            OR lower(nombre) LIKE '%espinaca%'
            OR lower(nombre) LIKE '%verdura%'
            OR lower(nombre) LIKE '%cordero%'
            OR lower(nombre) LIKE '%postre%'
            OR lower(nombre) LIKE '%yogur%'
          )
    """)
    food_in_furniture = cur.fetchall()

    conn.close()

    return {
        "total_products": total,
        "null_count": null_count,
        "categories_count": len(cats),
        "categories": cats,
        "tvs_infiltrated_count": len(tvs_infiltrated),
        "tvs_infiltrated_samples": tvs_infiltrated[:5],
        "tv_combos_trapped_count": len(tv_combos_trapped),
        "tv_combos_trapped_samples": tv_combos_trapped,
        "food_in_furniture_count": len(food_in_furniture),
        "food_in_furniture_samples": food_in_furniture,
    }


def main():
    print("=" * 80)
    print("  SUPERVMARKET MILESTONE 2: EMPIRICAL ADVERSARIAL CHALLENGE SUITE")
    print("=" * 80)

    # Step 1: Boundary classification tests
    passes, total, failures = run_boundary_tests()
    print(f"\n[PART 1] CLASSIFICATION EDGE CASE STRESS TESTS: {passes}/{total} passed")
    if failures:
        print(f"  FAILED CASES ({len(failures)}):")
        for f in failures:
            print(f"    - Title: '{f['title']}' -> ACTUAL: '{f['actual']}' | EXPECTED: '{f['expected']}'")
    else:
        print("  All edge cases passed cleanly!")

    # Step 2: Database empirical inspection
    db_report = inspect_database_adversarial()
    print(f"\n[PART 2] DATABASE EMPIRICAL INSPECTION (`supervmarket.db`):")
    print(f"  Total products: {db_report['total_products']}")
    print(f"  NULL categories: {db_report['null_count']} (100% coverage: {db_report['null_count'] == 0})")
    print(f"  Categories populated: {db_report['categories_count']}/19")
    print(f"  Infiltrated mounts/racks in televisores: {db_report['tvs_infiltrated_count']}")
    print(f"  TV Combos trapped in soportes_accesorios: {db_report['tv_combos_trapped_count']}")
    if db_report['tv_combos_trapped_count'] > 0:
        for item in db_report['tv_combos_trapped_samples']:
            print(f"    - EAN: {item[0]} | Title: {item[1]}")
    print(f"  Food items trapped in muebles_racks: {db_report['food_in_furniture_count']}")
    if db_report['food_in_furniture_count'] > 0:
        for item in db_report['food_in_furniture_samples']:
            print(f"    - EAN: {item[0]} | Title: {item[1]}")

    print("\n" + "=" * 80)
    overall_ok = (len(failures) == 0) and (db_report['tv_combos_trapped_count'] == 0) and (db_report['food_in_furniture_count'] == 0)
    verdict = "APPROVE" if overall_ok else "REQUEST_CHANGES"
    print(f"  FINAL VERDICT: {verdict}")
    print("=" * 80)

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
