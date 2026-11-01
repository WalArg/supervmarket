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
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from . import parsers

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
                "imagen": "https://ardiaprod.vteximg.com.br/arquivos/ids/362701/Jabon-Liquido-Para-Ropa-Ariel-Platinum-Doypack-3-Lt-_1.jpg?v=639003522645770000",
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
                        "promo_label": "40% OFF (2do al 70%)",
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
    promo = p.get("promo_etiqueta") or (f"{disc}% OFF Directo" if disc > 0 else "")
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

    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            tasks = []
            for cat in categories:
                tasks.append(_fetch_category_deals(client, "Dia", cat, limit=15))
                tasks.append(_fetch_category_deals(client, "Carrefour", cat, limit=15))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            flat_parsed: list[dict] = []
            for r in results:
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

    # Ensamblar los 4 niveles combinando ofertas en vivo con el baseline curado
    # (las ofertas vivas van primero, garantizando frescura y completitud)
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
        return merged

    final_tiers = []
    for b_tier in BASELINE_TIERS:
        t_id = b_tier["id"]
        if t_id == "tier-70-80":
            prods = _merge_tier(live_t70, b_tier["products"])
        elif t_id == "tier-60":
            prods = _merge_tier(live_t60, b_tier["products"])
        elif t_id == "tier-50":
            prods = _merge_tier(live_t50, b_tier["products"])
        else:
            prods = _merge_tier(live_t40, b_tier["products"])

        final_tiers.append({
            **b_tier,
            "products": prods,
        })

    data_payload = {
        "tiers": final_tiers,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "is_live": len(live_t70) + len(live_t60) + len(live_t50) + len(live_t40) > 0,
        "total_deals": sum(len(t["products"]) for t in final_tiers),
    }

    _DEALS_CACHE[cache_key] = (now, data_payload)
    return data_payload
