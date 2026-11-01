#!/usr/bin/env python3
"""audit_and_heal.py — Auditoría integral y auto-reparación de ofertas en vivo.

Ejecuta:
  1. Obtención en vivo de los 4 niveles de descuento (`deals.get_live_discount_tiers(force=True)`).
  2. Verificación matemática de precios, precios de lista, descuentos y etiquetas multi-unidad.
  3. Verificación de enlaces permanentes (fichas de producto `/p` o `/p/MLA` / `MLA-`).
  4. Verificación de imágenes contra lista negra de IDs rotos y chequeo HTTP en vivo (`200 OK` + `image/*`).
  5. Filtrado/reparación automática de cualquier producto en vivo defectuoso y persistencia del
     snapshot verificado en `api/_lib/verified_offers_snapshot.json`.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(ROOT_DIR, "api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from _lib import deals  # noqa: E402

BLACKLISTED_IMAGE_PATTERNS = [
    "607590",
    "879659",
    "843734",
    "ids/314352",
    "ids/345227",
]

EXPECTED_TIER_IDS = ["tier-70-80", "tier-60", "tier-50", "tier-40"]
SNAPSHOT_PATH = os.path.join(API_DIR, "_lib", "verified_offers_snapshot.json")


def is_deep_product_link(url: str, is_meli: bool = False) -> bool:
    if not url or not url.startswith("https://"):
        return False
    parsed = urlparse(url)
    if not parsed.netloc or parsed.path in ("", "/"):
        return False
    if is_meli:
        return "/p/MLA" in url or "articulo.mercadolibre.com.ar/MLA-" in url or "MLA-" in url
    return "/p" in parsed.path or "/p/MLA" in url or "MLA-" in url or len(parsed.path.strip("/")) > 5


def is_valid_image_url(url: str) -> bool:
    if not url or not url.startswith("https://"):
        return False
    for pattern in BLACKLISTED_IMAGE_PATTERNS:
        if pattern in url:
            return False
    return True


async def verify_image_http(client: httpx.AsyncClient, url: str) -> tuple[bool, str]:
    if not is_valid_image_url(url):
        return False, "invalid_or_blacklisted_url"
    try:
        resp = await client.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            },
        )
        content_type = (resp.headers.get("content-type") or "").lower()
        if resp.status_code == 200 and content_type.startswith("image/"):
            return True, f"200 ({content_type.split(';')[0]})"
        return False, f"HTTP {resp.status_code} ({content_type})"
    except Exception as exc:
        return False, f"error: {type(exc).__name__}"


def validate_product_entry(prod: dict) -> list[str]:
    errs: list[str] = []
    name = prod.get("nombre") or "<sin_nombre>"
    img = str(prod.get("imagen") or "")
    if not is_valid_image_url(img):
        errs.append(f"Producto '{name}': imagen inválida o en lista negra ({img})")

    offers = prod.get("offers") or []
    if not offers:
        errs.append(f"Producto '{name}': sin ofertas")
        return errs

    for off in offers:
        precio = float(off.get("precio") or 0)
        precio_lista = float(off.get("precio_lista") or precio)
        link = str(off.get("link") or "")
        if precio <= 0:
            errs.append(f"Producto '{name}': precio <= 0 ({precio})")
        if precio_lista < precio:
            errs.append(
                f"Producto '{name}': precio_lista ({precio_lista}) < precio ({precio})"
            )
        if not is_deep_product_link(link, is_meli=(off.get("supermercado") == "MercadoLibre")):
            errs.append(f"Producto '{name}': link inválido o genérico ({link})")
    return errs


def validate_sponsored_entry(tier_id: str, sponsored: dict) -> list[str]:
    errs: list[str] = []
    if not sponsored:
        return [f"{tier_id}: falta meliSponsored"]

    prod = sponsored.get("product") or {}
    off = sponsored.get("offer") or {}
    precio = float(off.get("precio") or 0)
    precio_lista = float(off.get("precio_lista") or 0)
    is_full = off.get("is_full") is True
    link = str(off.get("link") or "")
    img = str(prod.get("imagen") or "")

    if precio <= 0:
        errs.append(f"{tier_id} [meliSponsored]: precio <= 0 ({precio})")
    if precio_lista < precio:
        errs.append(
            f"{tier_id} [meliSponsored]: precio_lista ({precio_lista}) < precio ({precio})"
        )
    if not is_full:
        errs.append(f"{tier_id} [meliSponsored]: is_full no es True")
    if not is_deep_product_link(link, is_meli=True):
        errs.append(f"{tier_id} [meliSponsored]: link inválido ({link})")
    if not is_valid_image_url(img):
        errs.append(f"{tier_id} [meliSponsored]: imagen inválida ({img})")

    return errs


async def run_audit_and_heal(heal: bool = True, check_all_images: bool = True) -> int:
    print("=" * 78)
    print(" SUPERVMARKET — AUDITORÍA Y AUTO-CURACIÓN DE OFERTAS EN VIVO")
    print("=" * 78)

    live_payload = await deals.get_live_discount_tiers(force=True)
    tiers = live_payload.get("tiers") or []
    baseline_by_id = {t["id"]: t for t in getattr(deals, "BASELINE_TIERS", [])}

    tier_ids_found = [t.get("id") for t in tiers]
    missing_tiers = [tid for tid in EXPECTED_TIER_IDS if tid not in tier_ids_found]

    summary_rows: list[dict] = []
    unhealed_issues: list[str] = []
    healed_count = 0

    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
        for tier in tiers:
            tid = tier.get("id", "unknown")
            b_tier = baseline_by_id.get(tid, {})

            # 1. Auditar y curar meliSponsored
            sp_errs = validate_sponsored_entry(tid, tier.get("meliSponsored") or {})
            sp_img = ((tier.get("meliSponsored") or {}).get("product") or {}).get("imagen") or ""
            sp_img_ok, _ = await verify_image_http(client, sp_img)
            if not sp_img_ok:
                sp_errs.append(f"{tid} [meliSponsored]: imagen no responde 200 image/* ({sp_img})")

            if sp_errs and heal and b_tier.get("meliSponsored"):
                tier["meliSponsored"] = b_tier["meliSponsored"]
                healed_count += 1
                sp_errs = validate_sponsored_entry(tid, tier["meliSponsored"])

            unhealed_issues.extend(sp_errs)

            # 2. Auditar y curar productos del carrusel
            products = tier.get("products") or []
            valid_products: list[dict] = []
            removed_in_tier = 0
            checked_images_ok = 0

            # Auditar imágenes en paralelo por nivel
            products_to_check = products if check_all_images else products[:8]
            img_tasks = [
                verify_image_http(client, str(p.get("imagen") or ""))
                for p in products_to_check
            ]
            img_results = await asyncio.gather(*img_tasks)
            img_map = {
                id(p): res for p, res in zip(products_to_check, img_results)
            }

            for p in products:
                p_errs = validate_product_entry(p)
                if id(p) in img_map:
                    ok_http, detail = img_map[id(p)]
                    if ok_http:
                        checked_images_ok += 1
                    else:
                        p_errs.append(
                            f"Producto '{p.get('nombre')}': fallo HTTP imagen ({detail})"
                        )

                if p_errs:
                    if heal:
                        removed_in_tier += 1
                        healed_count += 1
                        continue
                    else:
                        unhealed_issues.extend([f"{tid}: {e}" for e in p_errs])
                valid_products.append(p)

            # Si al curar quedaron pocos productos, completar con baseline verificado
            if heal:
                seen_names = {vp.get("nombre", "").strip().lower() for vp in valid_products}
                for bp in b_tier.get("products") or []:
                    bname = bp.get("nombre", "").strip().lower()
                    if bname not in seen_names and not validate_product_entry(bp):
                        valid_products.append(bp)
                        seen_names.add(bname)
                tier["products"] = valid_products

            summary_rows.append(
                {
                    "tier_id": tid,
                    "sponsored_ok": "OK" if not sp_errs else "FAIL",
                    "products_count": len(tier.get("products") or []),
                    "images_verified": checked_images_ok,
                    "healed_items": removed_in_tier,
                }
            )

    if missing_tiers:
        for mt in missing_tiers:
            unhealed_issues.append(f"Falta el nivel obligatorio: {mt}")

    # Imprimir tabla resumen legible
    print(
        f"{'TIER ID':<14} | {'MELI FULL':<10} | {'PRODUCTOS':<10} | {'IMGS 200 OK':<12} | {'CURADOS':<8}"
    )
    print("-" * 78)
    for row in summary_rows:
        print(
            f"{row['tier_id']:<14} | {row['sponsored_ok']:<10} | "
            f"{row['products_count']:<10} | {row['images_verified']:<12} | {row['healed_items']:<8}"
        )
    print("-" * 78)

    total_products = sum(len(t.get("products") or []) for t in tiers)
    live_payload["total_deals"] = total_products
    live_payload["audited_at"] = datetime.now(timezone.utc).isoformat()
    live_payload["audit_status"] = "healthy" if not unhealed_issues else "degraded"

    if heal:
        os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump(live_payload, f, ensure_ascii=False, indent=2)
        print(f"[HEAL] Snapshot verificado guardado en: {SNAPSHOT_PATH}")

    print(
        f"[RESUMEN] Niveles: {len(tiers)}/4 | Total Productos: {total_products} | "
        f"Items Auto-Curados: {healed_count} | Problemas pendientes: {len(unhealed_issues)}"
    )

    if unhealed_issues:
        print("\n[ERRORES DETECTADOS]:")
        for issue in unhealed_issues:
            print(f"  - {issue}")
        return 1

    print("[OK] Estado de salud de ofertas: HEALTHY (Código 0)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audita y auto-repara el catálogo de ofertas en vivo de SuperVmarket."
    )
    parser.add_argument(
        "--heal",
        dest="heal",
        action="store_true",
        default=True,
        help="Auto-repara ofertas defectuosas y escribe api/_lib/verified_offers_snapshot.json (por defecto activado).",
    )
    parser.add_argument(
        "--no-heal",
        dest="heal",
        action="store_false",
        help="Ejecuta solo auditoría sin escribir el snapshot ni filtrar productos.",
    )
    args = parser.parse_args()
    exit_code = asyncio.run(run_audit_and_heal(heal=args.heal))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
