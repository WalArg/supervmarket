#!/usr/bin/env python3
"""build_verified_gondolas.py — Construye el dataset definitivo de góndolas de marketplace
a partir de supervmarket.db, verificando HTTP 200 en links e imágenes.
"""

import sqlite3
import asyncio
import httpx
import json
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, "supervmarket.db")
OUT_JSON = os.path.join(ROOT_DIR, "scratch", "verified_real_gondolas.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,image/webp,image/apng,*/*;q=0.8",
}

ELECTRO_EANS = [
    "8806097622369",  # Smart TV Samsung 55'' Qled 4K Q6F
    "8806099122164",  # Galaxy A07 Black 64GB
    "7790894902162",  # Celular Moto Edge70 Fusion 5g Azul 12/256gb
    "6932554444792",  # Celular Xiaomi Redmi A5 Ocean Blue 4/128gb
    "NALDO-44923",    # Notebook Hp 15-Fc0251la R5-7520u Amd15" 8/512 Gb
]

HOGAR_EANS = [
    "CAR10170208140190-VDT",  # Combo Sommier Norcee 140x190
    "7796448064287",          # Colchón Zafiro Express Light 1 plaza
    "CAR10150203140190-VDT",  # Combo Sommier Zeta Pillow 140x190
    "7796448067400",          # Colchón Serta Joplin 2 plazas
    "CAR10150208140190-VDT",  # Combo Sommier Malmok 140x190
]

DESTACADAS_EANS = [
    "SONYSTORE-2939",  # Parlantes para Auto de 4 pulgadas XS-GTF1039
    "SONYSTORE-2936",  # Parlantes para Auto de 6,5 pulgadas XS-GTF1639
    "6932554402822",   # Celular Xiaomi Redmi 15 8/256gb Midnight Black
    "8806095658322",   # Galaxy Buds3 Pro White
    "8806095658346",   # Galaxy Buds3 Pro Gray
]


async def fetch_product_data(cur, ean: str, tier_id: str, client: httpx.AsyncClient):
    prod_row = cur.execute("""
        SELECT ean, nombre, marca, modelo, categoria_normalizada, imagen, tipo
        FROM productos
        WHERE ean = ?
    """, (ean,)).fetchone()
    if not prod_row:
        raise ValueError(f"Product not found: {ean}")

    offers_rows = cur.execute("""
        SELECT supermercado, precio_venta, precio_lista, descuento, stock, link, store_type
        FROM precios
        WHERE ean = ? AND stock > 0
        ORDER BY precio_venta ASC
    """, (ean,)).fetchall()

    offers = []
    best_link = None
    for off in offers_rows:
        pv = float(off["precio_venta"])
        pl = float(off["precio_lista"] or pv)
        disc = float(off["descuento"] or 0)
        if pl > pv and disc <= 0:
            disc = round((1 - pv / pl) * 100)
        link = off["link"]
        if not best_link and link:
            best_link = link
        offers.append({
            "supermercado": off["supermercado"],
            "precio": pv,
            "precio_lista": pl,
            "stock": int(off["stock"] or 10),
            "disponible": True,
            "discount": int(disc),
            "promo_label": f"{int(disc)}% OFF" if disc > 0 else "Precio Especial",
            "seller_name": off["supermercado"],
            "seller_id": "1",
            "store_type": off["store_type"] or ("electro" if tier_id != "tier-mp-hogar" else "hogar"),
            "link": link,
        })

    img = prod_row["imagen"]
    # Verificar HTTP 200 para imagen y link principal
    r_img = await client.get(img)
    if r_img.status_code != 200 or not (r_img.headers.get("content-type") or "").startswith("image/"):
        raise ValueError(f"Image HTTP failed ({r_img.status_code}): {img}")

    r_link = await client.get(best_link)
    if r_link.status_code != 200:
        raise ValueError(f"Link HTTP failed ({r_link.status_code}): {best_link}")

    return {
        "id": str(prod_row["ean"]),
        "ean": str(prod_row["ean"]),
        "primary_ean": str(prod_row["ean"]),
        "nombre": prod_row["nombre"],
        "marca": prod_row["marca"] or "Generico",
        "modelo": prod_row["modelo"] or "",
        "tipo": prod_row["tipo"] or ("electro" if tier_id != "tier-mp-hogar" else "hogar"),
        "vertical": "electro" if tier_id != "tier-mp-hogar" else "hogar",
        "categoria_normalizada": prod_row["categoria_normalizada"],
        "imagen": img,
        "offers": offers,
    }


async def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    tiers = {
        "tier-mp-electro": ELECTRO_EANS,
        "tier-mp-hogar": HOGAR_EANS,
        "tier-mp-destacadas": DESTACADAS_EANS,
    }

    result = {}
    async with httpx.AsyncClient(timeout=10.0, headers=HEADERS, follow_redirects=True) as client:
        for tid, eans in tiers.items():
            result[tid] = []
            for ean in eans:
                p = await fetch_product_data(cur, ean, tid, client)
                result[tid].append(p)
                print(f"[{tid}] OK: {ean} - {p['nombre'][:45]} | {len(p['offers'])} offers")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nSuccessfully verified and wrote {sum(len(v) for v in result.values())} products to {OUT_JSON}")


if __name__ == "__main__":
    asyncio.run(main())
