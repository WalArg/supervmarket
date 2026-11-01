"""deals.py — Motor dinámico de ofertas y mayores descuentos en vivo para SuperVmarket.

Consulta en tiempo real los catálogos y promociones vigentes de supermercados
(Carrefour, Día, Coto, Mercado Libre) clasificando automáticamente los productos
en los 4 niveles de megadescuentos:
  1. 2da Unidad al 70% y 80% OFF — Promociones en Pareja
  2. Liquidaciones Directas y Bombas de Ahorro (Hasta 75% OFF)
  3. 50% OFF y 2x1 — Mitad de Precio
  4. Canasta Básica y Esenciales — Gran Ahorro (25% a 45% OFF)

Incluye caché inteligente en memoria (TTL 15 min), soporte de actualización forzada (force=true),
descarte automático de imágenes erróneas y fallback continuo a ofertas base curadas.
"""

import asyncio
import copy
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from . import parsers, mercadolibre

# Imágenes de VTEX erróneas o descontinuadas conocidas
BAD_IMAGE_PATTERNS = ["607590", "879659", "843734", "ids/314352", "ids/345227"]

# Caché en memoria: cp -> (timestamp, data_dict)
_DEALS_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_SECONDS = 900.0  # 15 minutos


# ---------------------------------------------------------------------------
# BASELINE CURADO GARANTIZADO (Fallback y base inicial)
# ---------------------------------------------------------------------------
BASELINE_TIERS = [
    {
        "id": "tier-70-80",
        "title": "2da Unidad al 70% y 80% OFF — Promociones en Pareja",
        "subtitle": "Llevando 2 unidades: la 2da al 70% y 80% OFF en súper (precio unitario efectivo)",
        "badge": "2da al 70% y 80%",
        "percentLabel": "70% y 80% OFF",
        "icon": "flame",
        "meliSponsored": {
            "product": {
                "ean": "7793704000913",
                "nombre": "Yerba Mate Playadito Despalada Bajo Polvo 500g",
                "marca": "Playadito",
                "imagen": "https://http2.mlstatic.com/D_NQ_NP_636867-MLA99433947676_112025-F.jpg",
                "offers": [],
            },
            "offer": {
                "supermercado": "MercadoLibre",
                "precio": 3489,
                "precio_lista": 5490,
                "stock": 120,
                "link": "https://www.mercadolibre.com.ar/p/MLA45978933",
                "seller_name": "Tienda Oficial Playadito",
                "is_full": True,
                "discount": 36,
                "promo_label": "36% OFF",
                "unit_measure": "kg",
                "unit_price": 6978,
            },
        },
        "products": [
            {
                "ean": "7622201735296",
                "nombre": "Galletitas Oreo x 118 g",
                "marca": "Oreo",
                "imagen": "https://farmacityar.vteximg.com.br/arquivos/ids/298494/251535_galletitas-oreo-x-118-g_imagen-1.jpg?v=639229342479300000",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 2639,
                        "precio_lista": 2639,
                        "stock": 80,
                        "link": "https://www.carrefour.com.ar/galletitas-dulce-oreo-rellenas-con-crema-118-g-715949/p",
                        "discount": 35,
                        "promo_label": "2do al 70% ($1.715 c/u x2)",
                        "promo_min_qty": 2,
                        "unit_measure": "kg",
                        "unit_price": 22364,
                    },
                    {
                        "supermercado": "Dia",
                        "precio": 2639,
                        "precio_lista": 2639,
                        "stock": 1024,
                        "link": "https://diaonline.supermercadosdia.com.ar/galletitas-oreo-rellenas-con-crema-sabor-original-menos-sodio-118-gr-271629/p",
                        "discount": 25,
                        "promo_label": "2do al 50% ($1.979 c/u x2)",
                        "promo_min_qty": 2,
                        "unit_measure": "kg",
                        "unit_price": 22364,
                    },
                ],
            },
            {
                "ean": "7791290796430",
                "nombre": "Jabón Líquido Skip Limpieza Activa Doypack 800ml",
                "marca": "Skip",
                "imagen": "https://farmaonline.vteximg.com.br/arquivos/ids/1458225/8144165_0.jpg?v=639252564197900000",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 3084,
                        "precio_lista": 4745,
                        "stock": 50,
                        "link": "https://www.carrefour.com.ar/jabon-liquido-skip-bio-enzimas-doypack-800-ml-695715/p",
                        "discount": 35,
                        "promo_label": "35% OFF Directo",
                        "unit_measure": "lt",
                        "unit_price": 3855,
                    },
                ],
            },
            {
                "ean": "8480017311238",
                "nombre": "Repelente para Insectos en Aerosol Bonté 170 Ml",
                "marca": "Bonté",
                "imagen": "https://ardiaprod.vteximg.com.br/arquivos/ids/343110/Repelente-para-Insectos-en-Aerosol-Bonte-170-Ml-_1.jpg?v=638727039719730000",
                "offers": [
                    {
                        "supermercado": "Dia",
                        "precio": 890,
                        "precio_lista": 4490,
                        "stock": 120,
                        "link": "https://diaonline.supermercadosdia.com.ar/repelente-para-insectos-en-aerosol-bonte-170-ml-210739/p",
                        "discount": 80,
                        "promo_label": "80% OFF Liquidación",
                        "unit_measure": "ml",
                        "unit_price": 5235,
                    },
                ],
            },
            {
                "ean": "8480017006529",
                "nombre": "Huevo de Pascua De Chocolate Delicious 30 Gr",
                "marca": "Delicious",
                "imagen": "https://ardiaprod.vteximg.com.br/arquivos/ids/294248/Huevo-de-Pascua-De-Chocolate-Delicious-30-Gr-_1.jpg",
                "offers": [
                    {
                        "supermercado": "Dia",
                        "precio": 1393,
                        "precio_lista": 1990,
                        "stock": 45,
                        "link": "https://diaonline.supermercadosdia.com.ar/huevo-de-pascua-de-chocolate-delicious-30-gr-6529/p",
                        "discount": 30,
                        "promo_label": "30% OFF Liquidación",
                        "unit_measure": "kg",
                        "unit_price": 46433,
                    },
                ],
            },
            {
                "ean": "7790040133464",
                "nombre": "Galletitas Pepitos Con Chips De Chocolate 119 Gr",
                "marca": "Pepitos",
                "imagen": "https://ardiaprod.vteximg.com.br/arquivos/ids/353536/Galletitas-Pepitos-Con-Chips-De-Chocolate-119-Gr-_1.jpg?v=638913145488400000",
                "offers": [
                    {
                        "supermercado": "Dia",
                        "precio": 2480,
                        "precio_lista": 2480,
                        "stock": 90,
                        "link": "https://diaonline.supermercadosdia.com.ar/galletitas-pepitos-con-chips-de-chocolate-119-gr-271628/p",
                        "discount": 25,
                        "promo_label": "2do al 50% ($1.860 c/u x2)",
                        "promo_min_qty": 2,
                        "unit_measure": "kg",
                        "unit_price": 20840,
                    },
                ],
            },
        ],
    },
    {
        "id": "tier-60",
        "title": "Liquidaciones Directas y Bombas de Ahorro (Hasta 75% OFF)",
        "subtitle": "Grandes rebajas y liquidaciones directas de stock en bebidas y limpieza",
        "badge": "Hasta 75% OFF",
        "percentLabel": "35% a 75%",
        "icon": "zap",
        "meliSponsored": {
            "product": {
                "ean": "7790990003220",
                "nombre": "Jabón Líquido Para Ropa Ariel Platinum 2.7 Lt",
                "marca": "Ariel",
                "imagen": "https://http2.mlstatic.com/D_NQ_NP_965238-MLA99857152273_112025-F.jpg",
                "offers": [],
            },
            "offer": {
                "supermercado": "MercadoLibre",
                "precio": 15000,
                "precio_lista": 19929,
                "stock": 50,
                "link": "https://www.mercadolibre.com.ar/p/MLA27822874",
                "seller_name": "Tienda Oficial P&G",
                "is_full": True,
                "discount": 25,
                "promo_label": "25% OFF",
                "unit_measure": "lt",
                "unit_price": 5555,
            },
        },
        "products": [
            {
                "ean": "7798134193752",
                "nombre": "Whisky Petakon en Petaca 380 Ml",
                "marca": "Petakon",
                "imagen": "https://carrefourar.vteximg.com.br/arquivos/ids/871496/7798134193752_02.jpg?v=639140991134370000",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 690,
                        "precio_lista": 2529,
                        "stock": 30,
                        "link": "https://www.carrefour.com.ar/whisky-petakon-en-petaca-380-ml-720918/p",
                        "discount": 73,
                        "promo_label": "73% OFF Liquidación",
                        "unit_measure": "lt",
                        "unit_price": 1816,
                    },
                ],
            },
            {
                "ean": "7798138555999",
                "nombre": "Bolsa de residuos Trash 45x60 x 10 uni",
                "marca": "Trash",
                "imagen": "https://carrefourar.vtexassets.com/arquivos/ids/444211/7798138555999_02.jpg",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 300,
                        "precio_lista": 800,
                        "stock": 80,
                        "link": "https://www.carrefour.com.ar/bolsa-de-residuos-trash-45x60-x-10-uni-748411/p",
                        "discount": 62,
                        "promo_label": "62% OFF Directo",
                        "unit_measure": "u",
                        "unit_price": 30,
                    },
                ],
            },
            {
                "ean": "7790520023027",
                "nombre": "Insecticida Raid Mata Moscas y Mosquitos 370 ml",
                "marca": "Raid",
                "imagen": "https://carrefourar.vteximg.com.br/arquivos/ids/896173/7790520023027_02.jpg",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 3119,
                        "precio_lista": 7409,
                        "stock": 45,
                        "link": "https://www.carrefour.com.ar/insecticida-raid-mata-moscas-y-mosquitos-nueva-formula-x2-mas-rapido-en-aerosol-370-ml-703700/p",
                        "discount": 58,
                        "promo_label": "58% OFF Directo",
                        "unit_measure": "lt",
                        "unit_price": 8430,
                    },
                ],
            },
            {
                "ean": "7794450000781",
                "nombre": "Vino Tinto Álamos Malbec 750 Ml",
                "marca": "Álamos",
                "imagen": "https://ardiaprod.vteximg.com.br/arquivos/ids/314458/Vino-Tinto-Alamos-Malbec-750-Ml-_1.jpg?v=638599428555500000",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 11265,
                        "precio_lista": 11265,
                        "stock": 80,
                        "link": "https://www.carrefour.com.ar/vino-tinto-malbec-seleccion-alamos-750-cc/p",
                        "discount": 33,
                        "promo_label": "3x2 ($7.510 c/u x3)",
                        "promo_min_qty": 3,
                        "unit_measure": "lt",
                        "unit_price": 15020,
                    },
                ],
            },
        ],
    },
    {
        "id": "tier-50",
        "title": "50% OFF y 2x1 — Mitad de Precio",
        "subtitle": "Promociones 2x1 y 50% directo para duplicar tu changuito al 50%",
        "badge": "50% OFF (2x1)",
        "percentLabel": "50% (2x1)",
        "icon": "percent",
        "meliSponsored": {
            "product": {
                "ean": "7790580112341",
                "nombre": "Chocolate Águila Clásico Semi Amargo 100g",
                "marca": "Águila",
                "imagen": "https://http2.mlstatic.com/D_NQ_NP_799008-MLA99335082066_112025-F.jpg",
                "offers": [],
            },
            "offer": {
                "supermercado": "MercadoLibre",
                "precio": 5385,
                "precio_lista": 7387,
                "stock": 120,
                "link": "https://www.mercadolibre.com.ar/p/MLA20028685",
                "seller_name": "Mercado Libre Supermercado",
                "is_full": True,
                "discount": 27,
                "promo_label": "27% OFF",
                "unit_measure": "kg",
                "unit_price": 53850,
            },
        },
        "products": [
            {
                "ean": "7790070336026",
                "nombre": "Fideos Lucchetti Tirabuzón 500 G",
                "marca": "Lucchetti",
                "imagen": "https://masonlineprod.vteximg.com.br/arquivos/ids/334621/Fideos-Lucchetti-Tirabuzon-500-G-1-49865.jpg?v=638623893699570000",
                "offers": [
                    {
                        "supermercado": "Dia",
                        "precio": 1050,
                        "precio_lista": 1850,
                        "stock": 80,
                        "link": "https://diaonline.supermercadosdia.com.ar/tirabuzon-n-34-luchetti-500-gr-144397/p",
                        "discount": 43,
                        "promo_label": "43% OFF Directo",
                        "unit_measure": "kg",
                        "unit_price": 2100,
                    },
                ],
            },
            {
                "ean": "7798342410321",
                "nombre": "Cerveza Honey Lazybee Bierhaus 473 Ml",
                "marca": "Bierhaus",
                "imagen": "https://ardiaprod.vteximg.com.br/arquivos/ids/371798/Cerveza-Honey-Lazybee-Bierhaus-473-Ml-_1.jpg?v=639156448571370000",
                "offers": [
                    {
                        "supermercado": "Dia",
                        "precio": 1690,
                        "precio_lista": 3395,
                        "stock": 55,
                        "link": "https://diaonline.supermercadosdia.com.ar/cerveza-honey-lazybee-bierhaus-473-ml-313120/p",
                        "discount": 50,
                        "promo_label": "50% OFF Directo",
                        "unit_measure": "lt",
                        "unit_price": 3572,
                    },
                ],
            },
            {
                "ean": "7798060850026",
                "nombre": "Manteca Tonadita Calidad Extra 200 G",
                "marca": "Tonadita",
                "imagen": "https://static.cotodigital3.com.ar/sitios/fotos/large/00228600/00228676.jpg",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 4399,
                        "precio_lista": 4399,
                        "stock": 60,
                        "link": "https://www.carrefour.com.ar/manteca-tonadita-calidad-extra-200-g/p",
                        "discount": 15,
                        "promo_label": "15% Tarjeta Carrefour",
                        "unit_measure": "kg",
                        "unit_price": 21995,
                    },
                ],
            },
            {
                "ean": "7798138555186",
                "nombre": "Protector Diario Doncella Sin Perfume 20 Ud",
                "marca": "Doncella",
                "imagen": "https://ardiaprod.vteximg.com.br/arquivos/ids/341793/Protector-Diario-Doncella-Sin-Perfume-Anatomicos-20-Ud-_1.jpg",
                "offers": [
                    {
                        "supermercado": "Dia",
                        "precio": 1290,
                        "precio_lista": 1290,
                        "stock": 90,
                        "link": "https://diaonline.supermercadosdia.com.ar/protector-diario-doncella-sin-perfume-anatomicos-20-ud-272890/p",
                        "discount": 0,
                        "promo_label": "Precio Ahorro Dia",
                        "unit_measure": "u",
                        "unit_price": 64,
                    },
                ],
            },
        ],
    },
    {
        "id": "tier-40",
        "title": "Canasta Básica y Esenciales — Gran Ahorro (25% a 45% OFF)",
        "subtitle": "Descuentos directos en aceites, detergentes, yerba y lácteos de consumo diario",
        "badge": "Hasta 45% OFF",
        "percentLabel": "25% - 45%",
        "icon": "tag",
        "meliSponsored": {
            "product": {
                "ean": "7790070228147",
                "nombre": "Aceite Cocinero Girasol 1.5 Lt",
                "marca": "Cocinero",
                "imagen": "https://http2.mlstatic.com/D_NQ_NP_698462-MLA99441253166_112025-F.jpg",
                "offers": [],
            },
            "offer": {
                "supermercado": "MercadoLibre",
                "precio": 7299,
                "precio_lista": 8500,
                "stock": 90,
                "link": "https://www.mercadolibre.com.ar/p/MLA19779083",
                "seller_name": "Tienda Oficial Cocinero",
                "is_full": True,
                "discount": 14,
                "promo_label": "14% OFF",
                "unit_measure": "lt",
                "unit_price": 4866,
            },
        },
        "products": [
            {
                "ean": "7790742363008",
                "nombre": "Leche La Serenísima Clásica Entera 1 L",
                "marca": "La Serenísima",
                "imagen": "https://static.cotodigital3.com.ar/sitios/fotos/large/00251800/00251875.jpg",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 2269,
                        "precio_lista": 3030,
                        "stock": 110,
                        "link": "https://www.carrefour.com.ar/leche-la-serenisima-clasica-3-1l-720719/p",
                        "discount": 25,
                        "promo_label": "25% OFF Directo",
                        "unit_measure": "lt",
                        "unit_price": 2269,
                    },
                ],
            },
            {
                "ean": "7790310985571",
                "nombre": "Nachos Sabor a Queso Doritos 200 G",
                "marca": "Doritos",
                "imagen": "https://carrefourar.vteximg.com.br/arquivos/ids/904460/7790310985571_E01.jpg",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 5699,
                        "precio_lista": 9499,
                        "stock": 45,
                        "link": "https://www.carrefour.com.ar/nachos-sabor-a-queso-doritos-200-g-721960/p",
                        "discount": 40,
                        "promo_label": "40% OFF Directo",
                        "promo_min_qty": 1,
                        "unit_measure": "kg",
                        "unit_price": 28495,
                    },
                ],
            },
            {
                "ean": "7790310985793",
                "nombre": "Chizitos de Maíz Queso Cheetos Original 140 G",
                "marca": "Cheetos",
                "imagen": "https://carrefourar.vteximg.com.br/arquivos/ids/904233/7790310985793_E01.jpg",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 3509,
                        "precio_lista": 5849,
                        "stock": 50,
                        "link": "https://www.carrefour.com.ar/chizitos-de-maiz-sabor-a-queso-cheetos-original-140-g-729770-/p",
                        "discount": 40,
                        "promo_label": "40% OFF Directo",
                        "unit_measure": "kg",
                        "unit_price": 25064,
                    },
                ],
            },
            {
                "ean": "7790310985588",
                "nombre": "Papas Fritas Lays Clásicas 330 G",
                "marca": "Lays",
                "imagen": "https://carrefourar.vteximg.com.br/arquivos/ids/904216/7790310985588_E01.jpg",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 6299,
                        "precio_lista": 10499,
                        "stock": 40,
                        "link": "https://www.carrefour.com.ar/papas-fritas-lays-clasicas-330-g-721964/p",
                        "discount": 40,
                        "promo_label": "40% OFF Directo",
                        "unit_measure": "kg",
                        "unit_price": 19087,
                    },
                ],
            },
            {
                "ean": "7790717150857",
                "nombre": "Cerveza 1890 Quilmes 354 Ml",
                "marca": "Quilmes",
                "imagen": "https://ardiaprod.vteximg.com.br/arquivos/ids/393322/Cerveza-1890-Quilmes-354-Ml-_1.jpg",
                "offers": [
                    {
                        "supermercado": "Dia",
                        "precio": 1090,
                        "precio_lista": 1890,
                        "stock": 90,
                        "link": "https://diaonline.supermercadosdia.com.ar/cerveza-1890-quilmes-354-ml-14806/p",
                        "discount": 42,
                        "promo_label": "42% OFF Directo",
                        "unit_measure": "lt",
                        "unit_price": 3079,
                    },
                ],
            },
        ],
    },
]


def _format_live_product(p: dict) -> dict:
    price = float(p.get("precio_venta") or 0)
    list_p = float(p.get("precio_lista") or price)
    disc = int(round(float(p.get("descuento") or 0)))
    promo = p.get("promo_etiqueta") or (f"{disc}% OFF Directo" if disc > 0 else "Precio Ahorro")
    promo_unit = float(p.get("precio_promo_unit") or price)
    min_qty = int(p.get("promo_min_qty") or 1)

    # Si la promo requiere llevar varias unidades (ej. 2do al 70%, 2x1), el precio principal
    # en la góndola debe ser el precio unitario de góndola (para coincidir con el que muestra la web),
    # y la etiqueta de promo especifica el precio efectivo por unidad llevando el combo.
    display_price = price
    if min_qty > 1 and 0 < promo_unit < price and "(" not in promo:
        promo = f"{promo} (${int(round(promo_unit)):,} c/u x{min_qty})".replace(",", ".")

    return {
        "ean": p.get("ean") or str(p.get("itemId") or int(time.time())),
        "nombre": p.get("nombre") or "",
        "marca": p.get("marca") or "",
        "imagen": p.get("imagen") or "",
        "offers": [
            {
                "supermercado": p.get("supermercado") or "Supermercado",
                "precio": display_price,
                "precio_lista": list_p,
                "stock": int(p.get("stock") or 50),
                "link": p.get("link") or "",
                "discount": disc,
                "promo_label": promo,
                "promo_min_qty": min_qty,
                "unit_measure": p.get("unidad_medida") or "u",
                "unit_price": p.get("precio_por_unidad") or display_price,
            }
        ],
    }


async def _fetch_category_deals(
    client: httpx.AsyncClient,
    store: str,
    category: str,
    limit: int = 20,
) -> list[dict]:
    if store == "Dia":
        url = (
            f"https://diaonline.supermercadosdia.com.ar/api/catalog_system/pub/products/search/"
            f"{category}?O=OrderByBestDiscountDESC&_from=0&_to={limit}"
        )
    elif store == "Carrefour":
        url = (
            f"https://www.carrefour.com.ar/api/catalog_system/pub/products/search/"
            f"{category}?O=OrderByBestDiscountDESC&_from=0&_to={limit}"
        )
    else:
        return []

    try:
        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0 SuperVmarket/2.0"})
        if r.status_code in (200, 206):
            items = []
            for raw in r.json():
                p = parsers.parse_vtex_product(raw, store)
                if not p:
                    continue
                img = p.get("imagen") or ""
                if not img or any(bad in img for bad in BAD_IMAGE_PATTERNS):
                    continue
                pv = float(p.get("precio_venta") or 0)
                pl = float(p.get("precio_lista") or pv)
                if pv <= 0 or pl > pv * 4.0:
                    continue
                items.append(p)
            return items
    except Exception:
        pass
    return []


def _has_real_discount_or_promo(prod: dict) -> bool:
    for off in prod.get("offers") or []:
        disc = float(off.get("discount") or 0)
        min_qty = int(off.get("promo_min_qty") or 1)
        label = str(off.get("promo_label") or "")
        if disc >= 10 or min_qty > 1 or "%" in label:
            return True
    return False


async def _revalidate_baseline_products(
    client: httpx.AsyncClient,
    baseline_tiers: list[dict],
) -> list[dict]:
    """Revalida en lote todos los productos del baseline contra Carrefour y Día en vivo.

    Actualiza precio de góndola, precio de lista, descuento y etiqueta promocional,
    descarta ofertas sin stock y desaloja productos sin descuento real si el nivel
    ya cuenta con al menos 4 productos válidos.
    """
    tiers_copy = copy.deepcopy(baseline_tiers)
    eans: list[str] = []
    seen_eans: set[str] = set()
    for t in tiers_copy:
        for p in t.get("products") or []:
            ean = str(p.get("ean") or "").strip()
            if ean and ean not in seen_eans:
                seen_eans.add(ean)
                eans.append(ean)

    if not eans:
        return tiers_copy

    fq_query = "&".join(f"fq=alternateIds_Ean:{e}" for e in eans)
    stores_cfg = [
        ("Carrefour", f"https://www.carrefour.com.ar/api/catalog_system/pub/products/search?{fq_query}&_from=0&_to=49"),
        ("Dia", f"https://diaonline.supermercadosdia.com.ar/api/catalog_system/pub/products/search?{fq_query}&_from=0&_to=49"),
    ]

    async def _fetch_store_batch(store_name: str, url: str) -> tuple[str, list[dict]]:
        try:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0 SuperVmarket/2.0"}, timeout=4.5)
            if r.status_code in (200, 206):
                data = r.json()
                if isinstance(data, list):
                    return store_name, data
        except Exception:
            pass
        return store_name, []

    batch_results = await asyncio.gather(
        *[_fetch_store_batch(s, u) for s, u in stores_cfg],
        return_exceptions=True,
    )

    live_map: dict[tuple[str, str], dict] = {}
    oos_set: set[tuple[str, str]] = set()

    for res in batch_results:
        if not isinstance(res, tuple) or len(res) != 2:
            continue
        store_name, raw_list = res
        for raw in raw_list:
            if not isinstance(raw, dict):
                continue
            parsed = parsers.parse_vtex_product(raw, store_name)
            if parsed and parsed.get("ean"):
                p_ean = str(parsed["ean"]).strip()
                if int(parsed.get("stock") or 0) > 0 and float(parsed.get("precio_venta") or 0) > 0:
                    live_map[(p_ean, store_name)] = parsed
                else:
                    oos_set.add((p_ean, store_name))
            else:
                # Extraer EAN del raw cuando fue descartado por falta de stock
                raw_items = raw.get("items") or []
                for sku in raw_items:
                    c_ean = str(sku.get("ean") or "").replace("~", "").strip()
                    if c_ean:
                        oos_set.add((c_ean, store_name))

    for t in tiers_copy:
        revalidated_prods: list[dict] = []
        for prod in t.get("products") or []:
            ean = str(prod.get("ean") or "").strip()
            new_offers: list[dict] = []
            seen_stores: set[str] = set()

            for off in prod.get("offers") or []:
                store = str(off.get("supermercado") or "").strip()
                seen_stores.add(store)
                if (ean, store) in oos_set and (ean, store) not in live_map:
                    continue
                if (ean, store) in live_map:
                    live_p = live_map[(ean, store)]
                    if int(live_p.get("stock") or 0) <= 0:
                        continue
                    fmt = _format_live_product(live_p)
                    live_off = fmt["offers"][0]
                    new_offers.append(live_off)
                    live_img = fmt.get("imagen") or ""
                    if live_img.startswith("https://") and not any(b in live_img for b in BAD_IMAGE_PATTERNS):
                        if not str(prod.get("imagen") or "").startswith("https://") or any(
                            b in str(prod.get("imagen") or "") for b in BAD_IMAGE_PATTERNS
                        ):
                            prod["imagen"] = live_img
                else:
                    if int(off.get("stock") or 0) > 0 and float(off.get("precio") or 0) > 0:
                        if float(off.get("precio_lista") or 0) < float(off.get("precio") or 0):
                            off["precio_lista"] = off["precio"]
                        if not off.get("promo_label"):
                            disc_v = int(round(float(off.get("discount") or 0)))
                            off["promo_label"] = f"{disc_v}% OFF Directo" if disc_v > 0 else "Precio Ahorro"
                        new_offers.append(off)

            # Si la otra cadena también tiene oferta con descuento activo para este EAN en vivo, sumarla
            for candidate_store in ("Carrefour", "Dia"):
                if candidate_store not in seen_stores and (ean, candidate_store) in live_map:
                    live_p = live_map[(ean, candidate_store)]
                    if int(live_p.get("stock") or 0) > 0:
                        fmt = _format_live_product(live_p)
                        cand_off = fmt["offers"][0]
                        if (
                            float(cand_off.get("discount") or 0) >= 10
                            or int(cand_off.get("promo_min_qty") or 1) > 1
                            or "%" in str(cand_off.get("promo_label") or "")
                        ):
                            new_offers.append(cand_off)

            if not new_offers:
                continue

            # Si hay ofertas con descuento real y otras sin descuento, conservar solo las que tienen promo real
            disc_offers = [
                o for o in new_offers
                if float(o.get("discount") or 0) >= 10
                or int(o.get("promo_min_qty") or 1) > 1
                or "%" in str(o.get("promo_label") or "")
            ]
            prod["offers"] = disc_offers if disc_offers else new_offers
            revalidated_prods.append(prod)

        discounted = [p for p in revalidated_prods if _has_real_discount_or_promo(p)]
        non_discounted = [p for p in revalidated_prods if not _has_real_discount_or_promo(p)]

        if len(discounted) >= 4:
            t["products"] = discounted
        else:
            needed = 4 - len(discounted)
            t["products"] = discounted + non_discounted[: max(0, needed)]

    return tiers_copy


async def get_live_discount_tiers(
    cp: Optional[str] = None,
    force: bool = False,
) -> dict:
    """Devuelve los niveles de ofertas con productos en vivo y caché inteligente."""
    cache_key = str(cp or "global")
    now = time.time()

    if not force and cache_key in _DEALS_CACHE:
        cached_ts, cached_data = _DEALS_CACHE[cache_key]
        if now - cached_ts < _CACHE_TTL_SECONDS:
            return cached_data

    # Categorías clave de supermercado
    categories = [
        "almacen",
        "bebidas",
        "limpieza",
        "lacteos-y-productos-frescos",
        "perfumeria",
    ]

    live_t70: list[dict] = []
    live_t60: list[dict] = []
    live_t50: list[dict] = []
    live_t40: list[dict] = []
    revalidated_baseline: list[dict] = copy.deepcopy(BASELINE_TIERS)
    live_sponsored: dict[str, dict] = {}

    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            cat_tasks = []
            for cat in categories:
                cat_tasks.append(_fetch_category_deals(client, "Dia", cat, limit=15))
                cat_tasks.append(_fetch_category_deals(client, "Carrefour", cat, limit=15))

            all_results = await asyncio.gather(
                *cat_tasks,
                _revalidate_baseline_products(client, BASELINE_TIERS),
                mercadolibre.fetch_live_sponsored_tiers(client),
                return_exceptions=True,
            )

            cat_results = all_results[:-2]
            reval_res = all_results[-2]
            spons_res = all_results[-1]

            if isinstance(reval_res, list) and reval_res:
                revalidated_baseline = reval_res
            if isinstance(spons_res, dict):
                live_sponsored = spons_res

            flat_parsed: list[dict] = []
            for r in cat_results:
                if isinstance(r, list):
                    flat_parsed.extend(r)

            seen_names = set()
            for p in flat_parsed:
                name_key = (p.get("nombre") or "").strip().lower()
                if not name_key or name_key in seen_names:
                    continue
                seen_names.add(name_key)

                disc = float(p.get("descuento") or 0)
                promo = str(p.get("promo_etiqueta") or "")
                formatted = _format_live_product(p)

                if "70%" in promo or "80%" in promo or disc >= 70:
                    live_t70.append(formatted)
                elif disc >= 50 or "50%" in promo or "2x1" in promo:
                    live_t50.append(formatted)
                elif disc >= 35:
                    live_t60.append(formatted)
                elif disc >= 20:
                    live_t40.append(formatted)

    except Exception:
        pass

    is_live_fetch = (len(live_t70) + len(live_t60) + len(live_t50) + len(live_t40) > 0) or bool(live_sponsored)

    # Si las fuentes en vivo fallaron por completo, intentar recuperar snapshot verificado de DB
    if not is_live_fetch:
        try:
            from . import db
            if hasattr(db, "load_verified_deals_snapshot"):
                try:
                    snap = db.load_verified_deals_snapshot(cp=cache_key)
                except TypeError:
                    snap = db.load_verified_deals_snapshot()
                if asyncio.iscoroutine(snap):
                    snap = await snap
                if isinstance(snap, dict) and snap.get("tiers"):
                    _DEALS_CACHE[cache_key] = (now, snap)
                    return snap
        except Exception:
            pass

    # Ensamblar los 4 niveles combinando ofertas en vivo con el baseline revalidado
    def _merge_tier(live_items: list[dict], baseline_products: list[dict]) -> list[dict]:
        merged = []
        seen = set()
        for it in live_items:
            key = it["nombre"].strip().lower()
            if key not in seen:
                seen.add(key)
                merged.append(it)
        for it in baseline_products:
            key = it["nombre"].strip().lower()
            if key not in seen:
                seen.add(key)
                merged.append(it)

        # Desalojar productos sin descuento real si el tier ya tiene >= 4 productos con descuento
        valid_disc = [p for p in merged if _has_real_discount_or_promo(p)]
        if len(valid_disc) >= 4:
            return valid_disc
        return merged

    final_tiers = []
    for b_tier in revalidated_baseline:
        t_id = b_tier["id"]
        if t_id == "tier-70-80":
            prods = _merge_tier(live_t70, b_tier["products"])
        elif t_id == "tier-60":
            prods = _merge_tier(live_t60, b_tier["products"])
        elif t_id == "tier-50":
            prods = _merge_tier(live_t50, b_tier["products"])
        else:
            prods = _merge_tier(live_t40, b_tier["products"])

        sponsored = live_sponsored.get(t_id) or b_tier.get("meliSponsored")

        final_tiers.append({
            **b_tier,
            "meliSponsored": sponsored,
            "products": prods,
        })

    data_payload = {
        "tiers": final_tiers,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "is_live": is_live_fetch,
        "total_deals": sum(len(t["products"]) for t in final_tiers),
    }

    try:
        from . import db
        if hasattr(db, "save_verified_deals_snapshot"):
            try:
                res_save = db.save_verified_deals_snapshot(data_payload, cp=cache_key)
            except TypeError:
                res_save = db.save_verified_deals_snapshot(data_payload)
            if asyncio.iscoroutine(res_save):
                await res_save
    except Exception:
        pass

    _DEALS_CACHE[cache_key] = (now, data_payload)
    return data_payload


async def audit_deals_health(cp: Optional[str] = None) -> dict:
    """Audita en vivo la integridad de todos los niveles de ofertas y patrocinados de Mercado Libre."""
    data = await get_live_discount_tiers(cp=cp, force=False)
    tiers = data.get("tiers") or []
    issues: list[dict] = []
    total_products = 0

    for tier in tiers:
        t_id = str(tier.get("id") or "unknown")

        # 1. Auditar meliSponsored
        sp = tier.get("meliSponsored") or {}
        sp_prod = sp.get("product") or {}
        sp_off = sp.get("offer") or {}
        if not sp_prod or not sp_off:
            issues.append({"tier": t_id, "target": "meliSponsored", "issue": "missing_sponsored_block"})
        else:
            sp_price = float(sp_off.get("precio") or 0)
            sp_list = float(sp_off.get("precio_lista") or 0)
            sp_link = str(sp_off.get("link") or "")
            sp_img = str(sp_prod.get("imagen") or "")
            sp_promo = str(sp_off.get("promo_label") or "").strip()

            if sp_price <= 0:
                issues.append({"tier": t_id, "target": "meliSponsored", "issue": "invalid_precio", "value": sp_price})
            if sp_list < sp_price:
                issues.append({"tier": t_id, "target": "meliSponsored", "issue": "precio_lista_lt_precio", "value": (sp_list, sp_price)})
            if not sp_link.startswith("https://"):
                issues.append({"tier": t_id, "target": "meliSponsored", "issue": "invalid_link", "value": sp_link})
            if not sp_img.startswith("https://") or any(bad in sp_img for bad in BAD_IMAGE_PATTERNS):
                issues.append({"tier": t_id, "target": "meliSponsored", "issue": "invalid_image", "value": sp_img})
            if not sp_promo:
                issues.append({"tier": t_id, "target": "meliSponsored", "issue": "missing_promo_label"})

        # 2. Auditar productos del tier
        prods = tier.get("products") or []
        for prod in prods:
            total_products += 1
            p_name = str(prod.get("nombre") or prod.get("ean") or "unknown")
            p_img = str(prod.get("imagen") or "")
            if not p_img.startswith("https://") or any(bad in p_img for bad in BAD_IMAGE_PATTERNS):
                issues.append({"tier": t_id, "product": p_name, "issue": "invalid_image", "value": p_img})

            offers = prod.get("offers") or []
            if not offers:
                issues.append({"tier": t_id, "product": p_name, "issue": "no_offers"})
            for off in offers:
                o_price = float(off.get("precio") or 0)
                o_list = float(off.get("precio_lista") or 0)
                o_link = str(off.get("link") or "")
                o_promo = str(off.get("promo_label") or "").strip()
                if o_price <= 0:
                    issues.append({"tier": t_id, "product": p_name, "issue": "invalid_precio", "value": o_price})
                if o_list < o_price:
                    issues.append({"tier": t_id, "product": p_name, "issue": "precio_lista_lt_precio", "value": (o_list, o_price)})
                if not o_link.startswith("https://"):
                    issues.append({"tier": t_id, "product": p_name, "issue": "invalid_link", "value": o_link})
                if not o_promo:
                    issues.append({"tier": t_id, "product": p_name, "issue": "missing_promo_label"})

    return {
        "status": "healthy" if not issues else "degraded",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "tiers_count": len(tiers),
        "total_products": total_products,
        "issues": issues,
    }
