#!/usr/bin/env python3
"""generate_real_gondolas.py — Extrae ofertas reales verificadas (HTTP 200) de supervmarket.db
para poblar las góndolas de marketplace en deals.py y gondolasData.ts.
"""

import sqlite3
import asyncio
import httpx
import json
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, "supervmarket.db")
SCRATCH_DIR = os.path.join(ROOT_DIR, "scratch")
os.makedirs(SCRATCH_DIR, exist_ok=True)
OUT_PATH = os.path.join(SCRATCH_DIR, "verified_real_gondolas.json")


def get_candidates(cur, cat_list, extra_where=""):
    ph = ",".join("?" * len(cat_list))
    sql = f"""
        SELECT p.ean, p.nombre, p.marca, p.modelo, p.categoria_normalizada, p.imagen, p.tipo,
               pr.supermercado, pr.precio_venta, pr.precio_lista, pr.descuento, pr.link, pr.store_type, pr.stock
        FROM productos p
        JOIN precios pr ON pr.ean = p.ean
        WHERE pr.descuento >= 15 AND pr.stock > 0
          AND p.categoria_normalizada IN ({ph})
          AND p.imagen LIKE 'https://%' AND pr.link LIKE 'https://%'
          {extra_where}
        ORDER BY pr.descuento DESC
        LIMIT 50
    """
    return cur.execute(sql, cat_list).fetchall()


async def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    el_cands = get_candidates(
        cur,
        ["televisores", "celulares", "notebooks_tablets", "heladeras_freezers", "lavado"],
        "AND (lower(p.nombre) LIKE '%smart%' OR lower(p.nombre) LIKE '%tv%' OR lower(p.nombre) LIKE '%celular%' OR lower(p.nombre) LIKE '%galaxy%' OR lower(p.nombre) LIKE '%moto%' OR lower(p.nombre) LIKE '%notebook%' OR lower(p.nombre) LIKE '%heladera%' OR lower(p.nombre) LIKE '%lavarropas%')",
    )
    hg_cands = get_candidates(
        cur,
        ["muebles_racks", "herramientas_construccion", "cocina_hornos", "climatizacion"],
        "AND (lower(p.nombre) LIKE '%sommier%' OR lower(p.nombre) LIKE '%colch%' OR lower(p.nombre) LIKE '%taladro%' OR lower(p.nombre) LIKE '%rack%' OR lower(p.nombre) LIKE '%horno%' OR lower(p.nombre) LIKE '%amoladora%' OR lower(p.nombre) LIKE '%aire%')",
    )
    dest_cands = get_candidates(
        cur,
        ["audio_video", "pequenos_electro", "notebooks_tablets", "televisores", "celulares"],
        "AND lower(p.nombre) NOT LIKE '%campera%' AND lower(p.nombre) NOT LIKE '%aceite%' AND (lower(p.nombre) LIKE '%buds%' OR lower(p.nombre) LIKE '%parlante%' OR lower(p.nombre) LIKE '%tablet%' OR lower(p.nombre) LIKE '%auricular%' OR lower(p.nombre) LIKE '%inzone%' OR lower(p.nombre) LIKE '%redmi 15%')",
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,image/webp,image/apng,*/*;q=0.8",
    }

    tier_definitions = [
        ("tier-mp-electro", el_cands),
        ("tier-mp-hogar", hg_cands),
        ("tier-mp-destacadas", dest_cands),
    ]

    tier_data = {}
    chosen_eans = set()

    async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
        async def verify_prod(p):
            try:
                r_img = await client.get(p["imagen"])
                r_link = await client.get(p["link"])
                img_ok = r_img.status_code == 200 and (r_img.headers.get("content-type") or "").startswith("image/")
                link_ok = r_link.status_code == 200
                if img_ok and link_ok:
                    return p
            except Exception:
                pass
            return None

        for tier_key, cands in tier_definitions:
            tasks = [verify_prod(c) for c in cands]
            results = await asyncio.gather(*tasks)
            valid = [r for r in results if r is not None]

            grouped = {}
            for r in valid:
                ean = r["ean"]
                if ean in chosen_eans:
                    continue
                if ean not in grouped:
                    all_offers = cur.execute("""
                        SELECT supermercado, precio_venta, precio_lista, descuento, stock, link, store_type
                        FROM precios
                        WHERE ean = ? AND stock > 0
                        ORDER BY precio_venta ASC
                    """, (ean,)).fetchall()

                    offers_list = []
                    for off in all_offers:
                        disc = float(off["descuento"] or 0.0)
                        p_vent = float(off["precio_venta"])
                        p_list = float(off["precio_lista"] or p_vent)
                        if p_list > p_vent and disc <= 0:
                            disc = round((1 - p_vent / p_list) * 100)
                        offers_list.append({
                            "supermercado": off["supermercado"],
                            "precio": p_vent,
                            "precio_lista": p_list,
                            "stock": int(off["stock"] or 10),
                            "disponible": True,
                            "discount": int(disc),
                            "promo_label": f"{int(disc)}% OFF" if disc > 0 else None,
                            "seller_name": off["supermercado"],
                            "seller_id": "1",
                            "store_type": off["store_type"] or "marketplace",
                            "link": off["link"],
                        })

                    chosen_eans.add(ean)
                    grouped[ean] = {
                        "id": ean,
                        "ean": ean,
                        "primary_ean": ean,
                        "nombre": r["nombre"],
                        "marca": r["marca"] or "Generico",
                        "modelo": r["modelo"] or "",
                        "tipo": r["tipo"] or "electro",
                        "vertical": "electro" if tier_key != "tier-mp-hogar" else "hogar",
                        "categoria_normalizada": r["categoria_normalizada"],
                        "imagen": r["imagen"],
                        "offers": offers_list,
                    }
                    if len(grouped) >= 5:
                        break

            tier_data[tier_key] = list(grouped.values())
            print(f"Tier {tier_key}: {len(tier_data[tier_key])} verified products")
            for prod in tier_data[tier_key]:
                print(f"  [{prod['ean']}] {prod['nombre'][:50]} ({len(prod['offers'])} offers)")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(tier_data, f, ensure_ascii=False, indent=2)

    print(f"Verified dataset saved to: {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
