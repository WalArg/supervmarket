#!/usr/bin/env python3
"""scripts/forensic_raw_analysis.py

Relevamiento Forense Profundo de la Base de Datos Cruda (raw_catalog) y Unificación de EANs.
Detecta:
1. Cobertura de EAN-13 GS1 vs SKUs sintéticos por tienda.
2. Inconsistencias de precios (ratios anómalos > 3x en un mismo modelo).
3. Detección de colisiones de accesorios/repuestos en modelos de electro/tech.
4. Oportunidades de resolución de entidades: Mapeo de tiendas sin EAN (Coppel, Naldo, etc.)
   a EANs canónicos mediante matching de (marca, modelo).
5. Integridad de enlaces e imágenes (URLs relativas, sin protocolo, strings vacíos).
"""

import os
import sys
import json
import sqlite3
import re
from collections import defaultdict, Counter

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api._lib.normalization import (
    extract_model,
    is_accessory,
    is_valid_ean13,
    normalize_ean,
)
from api._lib.stores import STORE_REGISTRY, store_vertical


def run_forensic_analysis(db_path: str = "supervmarket.db"):
    if not os.path.exists(db_path):
        print(f"ERROR: Database file {db_path} does not exist.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print("================================================================================")
    print("      RELEVAMIENTO FORENSE PROFUNDO DE LA BASE CRUDA (raw_catalog)             ")
    print("================================================================================")

    # 1. Resumen Global
    total_raw = cur.execute("SELECT COUNT(*) FROM raw_catalog").fetchone()[0]
    total_prod = cur.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
    total_precios = cur.execute("SELECT COUNT(*) FROM precios").fetchone()[0]
    total_stores = cur.execute("SELECT COUNT(DISTINCT store_name) FROM raw_catalog").fetchone()[0]

    print(f"\n[1] METRICAS GLOBALES DEL DATA LAKE")
    print(f"  * Total registros crudos en raw_catalog: {total_raw:,}")
    print(f"  * Total productos unificados en productos: {total_prod:,}")
    print(f"  * Total ofertas de precios en precios:   {total_precios:,}")
    print(f"  * Total tiendas registradas con datos:   {total_stores} de {len(STORE_REGISTRY)}")

    # 2. Cobertura por Tienda
    stores_stats = cur.execute("""
        SELECT 
            store_name,
            COUNT(*) as total,
            SUM(CASE WHEN ean_raw IS NOT NULL AND length(trim(ean_raw)) = 13 AND ean_raw GLOB '[0-9]*' THEN 1 ELSE 0 END) as ean13_cnt,
            SUM(CASE WHEN ean_raw IS NOT NULL AND length(trim(ean_raw)) = 8 AND ean_raw GLOB '[0-9]*' THEN 1 ELSE 0 END) as ean8_cnt,
            SUM(CASE WHEN ean_raw IS NULL OR trim(ean_raw) = '' OR ean_raw = 'None' OR ean_raw = '0' THEN 1 ELSE 0 END) as sin_ean_cnt,
            SUM(CASE WHEN price_raw <= 0 THEN 1 ELSE 0 END) as sin_precio_cnt,
            SUM(CASE WHEN image_raw IS NULL OR trim(image_raw) = '' THEN 1 ELSE 0 END) as sin_img_cnt,
            SUM(CASE WHEN link_raw IS NULL OR trim(link_raw) = '' OR link_raw NOT LIKE 'http%' THEN 1 ELSE 0 END) as bad_link_cnt
        FROM raw_catalog
        GROUP BY store_name
        ORDER BY total DESC
    """).fetchall()

    print("\n[2] COBERTURA Y CALIDAD DE METADATOS POR TIENDA")
    print(f"{'Tienda':<22} | {'Total':<6} | {'EAN-13 GS1':<12} | {'Sin EAN':<9} | {'Precio<=0':<10} | {'Bad Link':<9} | {'Sin Img':<8}")
    print("-" * 88)

    stores_report = []
    zero_ean_stores = []

    for row in stores_stats:
        st, tot, ean13, ean8, no_ean, no_p, no_img, bad_lnk = row
        pct_ean = (ean13 / tot * 100.0) if tot > 0 else 0.0
        print(f"{st:<22} | {tot:<6d} | {ean13:<5d} ({pct_ean:4.1f}%) | {no_ean:<9d} | {no_p:<10d} | {bad_lnk:<9d} | {no_img:<8d}")
        
        stores_report.append({
            "store": st,
            "total": tot,
            "ean13": ean13,
            "ean13_pct": round(pct_ean, 1),
            "no_ean": no_ean,
            "bad_price": no_p,
            "bad_link": bad_lnk,
            "no_image": no_img,
        })
        if pct_ean < 15.0:
            zero_ean_stores.append(st)

    # 3. Análisis de Oportunidades de Cruce Marca + Modelo -> EAN Canónico
    print("\n[3] RESOLUCION DE IDENTIDAD (CRUCE MARCA + MODELO -> EAN CANONICO)")
    
    # Obtenemos todos los registros válidos con precio > 0
    all_raw = cur.execute("""
        SELECT store_name, external_id, title_raw, brand_raw, ean_raw, price_raw, link_raw, image_raw
        FROM raw_catalog
        WHERE price_raw > 0
    """).fetchall()

    model_to_eans = defaultdict(set)
    model_to_offers = defaultdict(list)
    model_accessories = defaultdict(list)

    for item in all_raw:
        st, ext_id, title, brand, ean, price, link, img = item
        title = title or ""
        brand = brand or ""

        # Verificar si es un accesorio
        is_acc = is_accessory(title)

        # Extraer modelo
        model = extract_model(title, brand)
        if not model or len(model) < 3:
            continue

        brand_clean = brand.strip().upper()
        composite_key = f"{brand_clean}::{model.upper()}"

        clean_ean = normalize_ean(ean) if ean else ""
        has_valid_ean13 = len(clean_ean) == 13 and is_valid_ean13(clean_ean)

        offer_dict = {
            "store": st,
            "ext_id": ext_id,
            "title": title,
            "brand": brand,
            "ean": clean_ean if has_valid_ean13 else "",
            "price": price,
            "link": link,
            "is_accessory": is_acc,
        }

        if is_acc:
            model_accessories[composite_key].append(offer_dict)
        else:
            model_to_offers[composite_key].append(offer_dict)
            if has_valid_ean13:
                model_to_eans[composite_key].add(clean_ean)

    # Evaluar cruces posibles
    multi_store_models = 0
    unifiable_synthetic_offers = 0
    price_divergences = []
    cross_store_examples = []

    for comp_key, offers in model_to_offers.items():
        stores_present = {o["store"] for o in offers}
        if len(stores_present) > 1:
            multi_store_models += 1
            eans_found = model_to_eans.get(comp_key, set())
            
            # Chequear precios
            prices = [o["price"] for o in offers]
            min_p = min(prices)
            max_p = max(prices)
            ratio = max_p / min_p if min_p > 0 else 1.0

            if ratio > 3.0:
                price_divergences.append({
                    "model_key": comp_key,
                    "min_price": min_p,
                    "max_price": max_p,
                    "ratio": round(ratio, 2),
                    "offers": offers,
                })

            # Chequear cuántas ofertas sin EAN se pueden unificar
            if eans_found:
                canonical_ean = sorted(list(eans_found))[0]
                for o in offers:
                    if not o["ean"]:
                        unifiable_synthetic_offers += 1

            if len(cross_store_examples) < 8 and len(stores_present) >= 3:
                cross_store_examples.append({
                    "model_key": comp_key,
                    "canonical_eans": list(eans_found),
                    "stores": list(stores_present),
                    "min_price": min_p,
                    "max_price": max_p,
                    "sample_titles": [f"[{o['store']}] {o['title'][:55]} (${o['price']:,.0f})" for o in offers[:4]],
                })

    print(f"  * Total de Modelos (Marca + Modelo) unívocos detectados: {len(model_to_offers):,}")
    print(f"  * Modelos presentes en MULTIPLES tiendas (comparación directa): {multi_store_models:,}")
    print(f"  * Ofertas sin EAN que PUEDEN UNIFICARSE a un EAN GS1 canónico: {unifiable_synthetic_offers:,}")
    print(f"  * Modelos con dispersión de precio anómala (Ratio > 3.0x): {len(price_divergences)}")

    print("\n[4] EJEMPLOS DE UNIFICACION EXITOSA ENTRE TIENDAS")
    for ex in cross_store_examples[:5]:
        print(f"\n  -> Modelo: {ex['model_key']} | EANs Canónicos: {ex['canonical_eans'] or 'Sin EAN GS1'}")
        print(f"     Tiendas presentes ({len(ex['stores'])}): {', '.join(ex['stores'])}")
        print(f"     Rango de Precios: ${ex['min_price']:,.0f} a ${ex['max_price']:,.0f} ARS")
        for st_line in ex['sample_titles']:
            print(f"       {st_line}")

    # 5. Detección de Colisiones de Accesorios con Modelos de Equipo
    print("\n[5] DETECCION DE COLISIONES DE ACCESORIOS (Fundas, Controles, Cables)")
    accessory_leaks = 0
    for comp_key, acc_list in model_accessories.items():
        if comp_key in model_to_offers:
            accessory_leaks += 1
            if accessory_leaks <= 5:
                eq_sample = model_to_offers[comp_key][0]
                acc_sample = acc_list[0]
                print(f"  ! ALERTA DE COLISION en [{comp_key}]:")
                print(f"      Equipo [{eq_sample['store']}]: {eq_sample['title'][:60]} -> ${eq_sample['price']:,.0f}")
                print(f"      Accesorio [{acc_sample['store']}]: {acc_sample['title'][:60]} -> ${acc_sample['price']:,.0f}")

    print(f"  * Total de modelos donde un accesorio comparte el código del equipo: {accessory_leaks}")

    # Guardar reporte JSON
    report_data = {
        "timestamp": sqlite3.datetime.datetime.utcnow().isoformat() if hasattr(sqlite3, "datetime") else "",
        "global_metrics": {
            "total_raw": total_raw,
            "total_productos": total_prod,
            "total_precios": total_precios,
            "total_stores": total_stores,
        },
        "stores_summary": stores_report,
        "zero_ean_stores": zero_ean_stores,
        "entity_resolution": {
            "total_canonical_models": len(model_to_offers),
            "multi_store_models": multi_store_models,
            "unifiable_synthetic_offers": unifiable_synthetic_offers,
            "price_divergences_count": len(price_divergences),
            "accessory_collisions_count": accessory_leaks,
        },
        "examples": cross_store_examples,
    }

    report_path = os.path.join(ROOT_DIR, "scratch", "forensic_raw_catalog_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Reporte forense guardado en: {report_path}")


if __name__ == "__main__":
    run_forensic_analysis()
