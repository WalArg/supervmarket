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


BASELINE_MARKETPLACE_TIERS = [
    {
        "id": "tier-mp-electro",
        "title": "Electrodomésticos y Tecnología — Hasta 40% OFF y Cuotas",
        "subtitle": "Smart TVs, celulares, notebooks, lavarropas y heladeras con financiación",
        "badge": "Electro & Tech",
        "percentLabel": "Hasta 40% OFF + Cuotas",
        "icon": "zap",
        "products": [
            {
                "id": "8806095483245",
                "ean": "8806095483245",
                "primary_ean": "8806095483245",
                "nombre": "Smart TV Samsung 50 pulgadas Crystal UHD 4K UN50DU7000",
                "marca": "Samsung",
                "modelo": "UN50DU7000",
                "model_key": "MODEL_SAMSUNG_UN50DU7000",
                "tipo": "electro",
                "vertical": "electro",
                "imagen": "https://carrefourar.vtexassets.com/arquivos/ids/623696/8806095459345_01.jpg",
                "offers": [
                    {
                        "supermercado": "Provincia Compras",
                        "precio": 649999.0,
                        "precio_lista": 899999.0,
                        "stock": 25,
                        "disponible": True,
                        "discount": 28,
                        "promo_label": "28% OFF + 24 Cuotas sin interés",
                        "seller_name": "Samsung Oficial",
                        "seller_id": "1",
                        "store_type": "marketplace",
                        "modelo": "UN50DU7000",
                        "tipo": "electro",
                        "cuotas": 24,
                        "sin_interes": True,
                        "cuotas_info": "24 cuotas sin interés de $27.083 con Banco Provincia",
                        "cuota_monto": 27083.29,
                        "link": "https://www.provinciacompras.com.ar/smart-tv-samsung-50-crystal-uhd-4k-un50du7000/p",
                    },
                    {
                        "supermercado": "Fravega",
                        "precio": 679999.0,
                        "precio_lista": 899999.0,
                        "stock": 40,
                        "disponible": True,
                        "discount": 24,
                        "promo_label": "24% OFF",
                        "seller_name": "Frávega",
                        "seller_id": "1",
                        "store_type": "electro",
                        "modelo": "UN50DU7000",
                        "tipo": "electro",
                        "cuotas": 6,
                        "sin_interes": True,
                        "cuotas_info": "6 cuotas sin interés de $113.333",
                        "cuota_monto": 113333.17,
                        "link": "https://www.fravega.com/p/smart-tv-samsung-50-crystal-uhd-4k-un50du7000-502847/p",
                    },
                ],
            },
            {
                "id": "8806095368290",
                "ean": "8806095368290",
                "primary_ean": "8806095368290",
                "nombre": "Celular Samsung Galaxy A15 128GB 4GB RAM Azul",
                "marca": "Samsung",
                "modelo": "SM-A155M",
                "model_key": "MODEL_SAMSUNG_SMA155M_128GB",
                "tipo": "celulares",
                "vertical": "electro",
                "imagen": "https://fravega.vtexassets.com/arquivos/ids/1628352/SM-A155M_01.jpg",
                "offers": [
                    {
                        "supermercado": "On City",
                        "precio": 299999.0,
                        "precio_lista": 399999.0,
                        "stock": 50,
                        "disponible": True,
                        "discount": 25,
                        "promo_label": "25% OFF",
                        "seller_name": "Bulonfer",
                        "seller_id": "bulonfer",
                        "store_type": "marketplace",
                        "modelo": "SM-A155M",
                        "tipo": "celulares",
                        "cuotas": 6,
                        "sin_interes": True,
                        "cuotas_info": "6 cuotas sin interés de $49.999",
                        "cuota_monto": 49999.83,
                        "link": "https://www.oncity.com/celular-samsung-galaxy-a15-128gb-azul/p?seller=bulonfer",
                    }
                ],
            },
            {
                "id": "0196803273465",
                "ean": "0196803273465",
                "primary_ean": "0196803273465",
                "nombre": "Notebook Lenovo IdeaPad 1 15.6 pulgadas Ryzen 3 8GB 256GB SSD",
                "marca": "Lenovo",
                "modelo": "82VG0007AR",
                "model_key": "MODEL_LENOVO_82VG0007AR",
                "tipo": "notebooks",
                "vertical": "electro",
                "imagen": "https://cetrogar.vtexassets.com/arquivos/ids/243678/lenovo-ideapad-1.jpg",
                "offers": [
                    {
                        "supermercado": "Cetrogar",
                        "precio": 589999.0,
                        "precio_lista": 799999.0,
                        "stock": 20,
                        "disponible": True,
                        "discount": 26,
                        "promo_label": "26% OFF",
                        "seller_name": "Cetrogar",
                        "seller_id": "1",
                        "store_type": "electro",
                        "modelo": "82VG0007AR",
                        "tipo": "notebooks",
                        "cuotas": 12,
                        "sin_interes": True,
                        "cuotas_info": "12 cuotas sin interés de $49.166",
                        "cuota_monto": 49166.58,
                        "link": "https://www.cetrogar.com.ar/notebook-lenovo-ideapad-1-15amn7-ryzen-3-8gb-256gb/p",
                    }
                ],
            },
            {
                "id": "7795473024846",
                "ean": "7795473024846",
                "primary_ean": "7795473024846",
                "nombre": "Lavarropas Automático Drean Next 6.06 ECO 6kg Blanco",
                "marca": "Drean",
                "modelo": "NEXT 6.06 ECO",
                "model_key": "MODEL_DREAN_NEXT606ECO",
                "tipo": "lavarropas",
                "vertical": "electro",
                "imagen": "https://naldo.vtexassets.com/arquivos/ids/187654/drean-next-606.jpg",
                "offers": [
                    {
                        "supermercado": "Naldo",
                        "precio": 619999.0,
                        "precio_lista": 789999.0,
                        "stock": 15,
                        "disponible": True,
                        "discount": 21,
                        "promo_label": "21% OFF",
                        "seller_name": "Naldo",
                        "seller_id": "1",
                        "store_type": "electro",
                        "modelo": "NEXT 6.06 ECO",
                        "tipo": "lavarropas",
                        "cuotas": 6,
                        "sin_interes": True,
                        "cuotas_info": "6 cuotas sin interés de $103.333",
                        "cuota_monto": 103333.17,
                        "link": "https://www.naldo.com.ar/lavarropas-automatico-drean-next-6-06-eco-6-kg/p",
                    }
                ],
            },
            {
                "id": "7793669874831",
                "ean": "7793669874831",
                "primary_ean": "7793669874831",
                "nombre": "Heladera con Freezer Gafa HGF388AFB Blanca 374L",
                "marca": "Gafa",
                "modelo": "HGF388AFB",
                "model_key": "MODEL_GAFA_HGF388AFB",
                "tipo": "heladeras",
                "vertical": "electro",
                "imagen": "https://fravega.vtexassets.com/arquivos/ids/173491/gafa-hgf388afb.jpg",
                "offers": [
                    {
                        "supermercado": "Fravega",
                        "precio": 729999.0,
                        "precio_lista": 949999.0,
                        "stock": 18,
                        "disponible": True,
                        "discount": 23,
                        "promo_label": "23% OFF",
                        "seller_name": "Frávega",
                        "seller_id": "1",
                        "store_type": "electro",
                        "modelo": "HGF388AFB",
                        "tipo": "heladeras",
                        "cuotas": 6,
                        "sin_interes": True,
                        "cuotas_info": "6 cuotas sin interés de $121.666",
                        "cuota_monto": 121666.5,
                        "link": "https://www.fravega.com/p/heladera-con-freezer-gafa-hgf388afb-blanca-374l-481309/p",
                    }
                ],
            },
        ],
    },
    {
        "id": "tier-mp-hogar",
        "title": "Hogar, Herramientas y Climatización — Gran Ahorro",
        "subtitle": "Taladros, hidrolavadoras, pequeños electrodomésticos y climatización",
        "badge": "Hogar & Taller",
        "percentLabel": "Hasta 35% OFF",
        "icon": "tag",
        "products": [
            {
                "id": "0885911467407",
                "ean": "0885911467407",
                "primary_ean": "0885911467407",
                "nombre": "Taladro Percutor Black+Decker TM500 500W Mandril 10mm",
                "marca": "Black+Decker",
                "modelo": "TM500",
                "model_key": "MODEL_BLACKDECKER_TM500",
                "tipo": "herramientas",
                "vertical": "marketplace",
                "imagen": "https://easyar.vtexassets.com/arquivos/ids/284910/taladro-tm500.jpg",
                "offers": [
                    {
                        "supermercado": "Easy",
                        "precio": 48999.0,
                        "precio_lista": 69999.0,
                        "stock": 60,
                        "disponible": True,
                        "discount": 30,
                        "promo_label": "30% OFF Directo",
                        "seller_name": "Easy",
                        "seller_id": "1",
                        "store_type": "marketplace",
                        "modelo": "TM500",
                        "tipo": "herramientas",
                        "cuotas": 3,
                        "sin_interes": True,
                        "cuotas_info": "3 cuotas sin interés de $16.333",
                        "cuota_monto": 16333.0,
                        "link": "https://www.easy.com.ar/taladro-percutor-500w-tm500-black-decker/p",
                    }
                ],
            },
            {
                "id": "4054278496450",
                "ean": "4054278496450",
                "primary_ean": "4054278496450",
                "nombre": "Hidrolavadora Alta Presión Kärcher K2 Compact 110 Bar",
                "marca": "Kärcher",
                "modelo": "K2 COMPACT",
                "model_key": "MODEL_KARCHER_K2COMPACT",
                "tipo": "herramientas",
                "vertical": "electro",
                "imagen": "https://fravega.vtexassets.com/arquivos/ids/1582910/karcher-k2-compact.jpg",
                "offers": [
                    {
                        "supermercado": "Fravega",
                        "precio": 149999.0,
                        "precio_lista": 199999.0,
                        "stock": 30,
                        "disponible": True,
                        "discount": 25,
                        "promo_label": "25% OFF",
                        "seller_name": "Kärcher Oficial",
                        "seller_id": "karcheroficial",
                        "store_type": "electro",
                        "modelo": "K2 COMPACT",
                        "tipo": "herramientas",
                        "cuotas": 6,
                        "sin_interes": True,
                        "cuotas_info": "6 cuotas sin interés de $24.999",
                        "cuota_monto": 24999.83,
                        "link": "https://www.fravega.com/p/hidrolavadora-karcher-k2-compact-110-bar-1400w-502194/p?seller=karcheroficial",
                    }
                ],
            },
            {
                "id": "7798089400820",
                "ean": "7798089400820",
                "primary_ean": "7798089400820",
                "nombre": "Aire Acondicionado Split BGH Silent Air 3500W Frío/Calor Inverter",
                "marca": "BGH",
                "modelo": "BS35WCCR",
                "model_key": "MODEL_BGH_BS35WCCR",
                "tipo": "climatizacion",
                "vertical": "electro",
                "imagen": "https://cetrogar.vtexassets.com/arquivos/ids/221948/aire-bgh-bs35wccr.jpg",
                "offers": [
                    {
                        "supermercado": "Cetrogar",
                        "precio": 799999.0,
                        "precio_lista": 1099999.0,
                        "stock": 22,
                        "disponible": True,
                        "discount": 27,
                        "promo_label": "27% OFF + 12 Cuotas",
                        "seller_name": "BGH",
                        "seller_id": "arbghprodio",
                        "store_type": "electro",
                        "modelo": "BS35WCCR",
                        "tipo": "climatizacion",
                        "cuotas": 12,
                        "sin_interes": True,
                        "cuotas_info": "12 cuotas sin interés de $66.666",
                        "cuota_monto": 66666.58,
                        "link": "https://www.cetrogar.com.ar/aire-acondicionado-split-bgh-silent-air-3500w-frio-calor/p?seller=arbghprodio",
                    }
                ],
            },
            {
                "id": "8710103855583",
                "ean": "8710103855583",
                "primary_ean": "8710103855583",
                "nombre": "Pava Eléctrica Philips Daily Collection HD4691 Acero Inoxidable 1.7L",
                "marca": "Philips",
                "modelo": "HD4691",
                "model_key": "MODEL_PHILIPS_HD4691",
                "tipo": "pequeno electro",
                "vertical": "electro",
                "imagen": "https://tienda.philips.com.ar/arquivos/ids/156782/hd4691.jpg",
                "offers": [
                    {
                        "supermercado": "Philips",
                        "precio": 64999.0,
                        "precio_lista": 89999.0,
                        "stock": 45,
                        "disponible": True,
                        "discount": 28,
                        "promo_label": "28% OFF Directo",
                        "seller_name": "Philips Oficial",
                        "seller_id": "1",
                        "store_type": "electro",
                        "modelo": "HD4691",
                        "tipo": "pequeno electro",
                        "cuotas": 6,
                        "sin_interes": True,
                        "cuotas_info": "6 cuotas sin interés de $10.833",
                        "cuota_monto": 10833.17,
                        "link": "https://www.tienda.philips.com.ar/pava-electrica-philips-hd4691-acero-1-7-l/p",
                    }
                ],
            },
            {
                "id": "3016661144783",
                "ean": "3016661144783",
                "primary_ean": "3016661144783",
                "nombre": "Cafetera Moulinex Nescafé Dolce Gusto Mini Me Negra",
                "marca": "Moulinex",
                "modelo": "PV120858",
                "model_key": "MODEL_MOULINEX_PV120858",
                "tipo": "pequeno electro",
                "vertical": "electro",
                "imagen": "https://tienda.moulinex.com.ar/arquivos/ids/155981/mini-me-negra.jpg",
                "offers": [
                    {
                        "supermercado": "Moulinex",
                        "precio": 119999.0,
                        "precio_lista": 169999.0,
                        "stock": 35,
                        "disponible": True,
                        "discount": 29,
                        "promo_label": "29% OFF Tienda Oficial",
                        "seller_name": "Moulinex Oficial",
                        "seller_id": "1",
                        "store_type": "electro",
                        "modelo": "PV120858",
                        "tipo": "pequeno electro",
                        "cuotas": 6,
                        "sin_interes": True,
                        "cuotas_info": "6 cuotas sin interés de $19.999",
                        "cuota_monto": 19999.83,
                        "link": "https://tienda.moulinex.com.ar/cafetera-dolce-gusto-mini-me-negra/p",
                    }
                ],
            },
        ],
    },
    {
        "id": "tier-mp-destacadas",
        "title": "Ofertas Destacadas de Marketplaces — Precios Bomba",
        "subtitle": "Oportunidades de Provincia Compras, On City, Frávega, Cetrogar y Naldo",
        "badge": "Marketplaces",
        "percentLabel": "Financiación y Rebajas",
        "icon": "flame",
        "products": [
            {
                "id": "8718863035122",
                "ean": "8718863035122",
                "primary_ean": "8718863035122",
                "nombre": "Smart TV Philips 43 pulgadas Full HD 43PFD6917 Android TV",
                "marca": "Philips",
                "modelo": "43PFD6917",
                "model_key": "MODEL_PHILIPS_43PFD6917",
                "tipo": "electro",
                "vertical": "marketplace",
                "imagen": "https://provinciacompras.vtexassets.com/arquivos/ids/248912/philips-43pfd6917.jpg",
                "offers": [
                    {
                        "supermercado": "Provincia Compras",
                        "precio": 449999.0,
                        "precio_lista": 599999.0,
                        "stock": 40,
                        "disponible": True,
                        "discount": 25,
                        "promo_label": "25% OFF + 24 Cuotas Banco Provincia",
                        "seller_name": "Bidcom",
                        "seller_id": "bidcom003",
                        "store_type": "marketplace",
                        "modelo": "43PFD6917",
                        "tipo": "electro",
                        "cuotas": 24,
                        "sin_interes": True,
                        "cuotas_info": "24 cuotas sin interés de $18.750 con Banco Provincia",
                        "cuota_monto": 18750.0,
                        "link": "https://www.provinciacompras.com.ar/smart-tv-philips-43-full-hd-android-tv-43pfd6917/p?seller=bidcom003",
                    }
                ],
            },
            {
                "id": "7798089400783",
                "ean": "7798089400783",
                "primary_ean": "7798089400783",
                "nombre": "Microondas BGH Quick Chef 20 Litros Digital Blanco B120M20",
                "marca": "BGH",
                "modelo": "B120M20",
                "model_key": "MODEL_BGH_B120M20",
                "tipo": "pequeno electro",
                "vertical": "marketplace",
                "imagen": "https://oncity.vtexassets.com/arquivos/ids/194832/bgh-b120m20.jpg",
                "offers": [
                    {
                        "supermercado": "On City",
                        "precio": 149999.0,
                        "precio_lista": 199999.0,
                        "stock": 25,
                        "disponible": True,
                        "discount": 25,
                        "promo_label": "25% OFF",
                        "seller_name": "Bulonfer",
                        "seller_id": "bulonfer",
                        "store_type": "marketplace",
                        "modelo": "B120M20",
                        "tipo": "pequeno electro",
                        "cuotas": 6,
                        "sin_interes": True,
                        "cuotas_info": "6 cuotas sin interés de $24.999",
                        "cuota_monto": 24999.83,
                        "link": "https://www.oncity.com/microondas-bgh-quick-chef-20l-digital-b120m20/p?seller=bulonfer",
                    }
                ],
            },
            {
                "id": "6925281987519",
                "ean": "6925281987519",
                "primary_ean": "6925281987519",
                "nombre": "Auriculares Inalámbricos JBL Tune 520BT Bluetooth Pure Bass",
                "marca": "JBL",
                "modelo": "T520BT",
                "model_key": "MODEL_JBL_T520BT",
                "tipo": "audio",
                "vertical": "electro",
                "imagen": "https://fravega.vtexassets.com/arquivos/ids/1678912/jbl-tune-520bt.jpg",
                "offers": [
                    {
                        "supermercado": "Fravega",
                        "precio": 69999.0,
                        "precio_lista": 99999.0,
                        "stock": 80,
                        "disponible": True,
                        "discount": 30,
                        "promo_label": "30% OFF Directo",
                        "seller_name": "TLR",
                        "seller_id": "fravegasellerprd160",
                        "store_type": "electro",
                        "modelo": "T520BT",
                        "tipo": "audio",
                        "cuotas": 3,
                        "sin_interes": True,
                        "cuotas_info": "3 cuotas sin interés de $23.333",
                        "cuota_monto": 23333.0,
                        "link": "https://www.fravega.com/p/auriculares-inalambricos-jbl-tune-520bt-negro-502810/p?seller=fravegasellerprd160",
                    }
                ],
            },
            {
                "id": "7793862002345",
                "ean": "7793862002345",
                "primary_ean": "7793862002345",
                "nombre": "Ventilador de Pie Liliana VTX20 20 Pulgadas Orbital 90W",
                "marca": "Liliana",
                "modelo": "VTX20",
                "model_key": "MODEL_LILIANA_VTX20",
                "tipo": "climatizacion",
                "vertical": "electro",
                "imagen": "https://cetrogar.vtexassets.com/arquivos/ids/198234/liliana-vtx20.jpg",
                "offers": [
                    {
                        "supermercado": "Cetrogar",
                        "precio": 74999.0,
                        "precio_lista": 99999.0,
                        "stock": 50,
                        "disponible": True,
                        "discount": 25,
                        "promo_label": "25% OFF",
                        "seller_name": "Cetrogar",
                        "seller_id": "1",
                        "store_type": "electro",
                        "modelo": "VTX20",
                        "tipo": "climatizacion",
                        "cuotas": 6,
                        "sin_interes": True,
                        "cuotas_info": "6 cuotas sin interés de $12.499",
                        "cuota_monto": 12499.83,
                        "link": "https://www.cetrogar.com.ar/ventilador-de-pie-liliana-vtx20-20-pulgadas/p",
                    }
                ],
            },
            {
                "id": "8806095267449",
                "ean": "8806095267449",
                "primary_ean": "8806095267449",
                "nombre": "Tablet Samsung Galaxy Tab A9 8.7 pulgadas 64GB Wi-Fi Gris",
                "marca": "Samsung",
                "modelo": "SM-X110",
                "model_key": "MODEL_SAMSUNG_SMX110_64GB",
                "tipo": "tablets",
                "vertical": "electro",
                "imagen": "https://shop.samsung.com.ar/arquivos/ids/187912/galaxy-tab-a9.jpg",
                "offers": [
                    {
                        "supermercado": "Samsung",
                        "precio": 279999.0,
                        "precio_lista": 349999.0,
                        "stock": 30,
                        "disponible": True,
                        "discount": 20,
                        "promo_label": "20% OFF Tienda Oficial",
                        "seller_name": "Samsung Oficial",
                        "seller_id": "1",
                        "store_type": "electro",
                        "modelo": "SM-X110",
                        "tipo": "tablets",
                        "cuotas": 6,
                        "sin_interes": True,
                        "cuotas_info": "6 cuotas sin interés de $46.666",
                        "cuota_monto": 46666.5,
                        "link": "https://shop.samsung.com.ar/galaxy-tab-a9-64gb-silver/p",
                    }
                ],
            },
        ],
    },
]

# Asegurar que cada producto en BASELINE_MARKETPLACE_TIERS tenga best_offer
for _tier in BASELINE_MARKETPLACE_TIERS:
    for _prod in _tier["products"]:
        if "best_offer" not in _prod and _prod.get("offers"):
            _prod["best_offer"] = _prod["offers"][0]


def extract_financing_info(commertial_offer: dict, price: float = 0.0, store_name: str = "") -> dict:
    """Extrae la mejor opción de cuotas y financiación desde commertialOffer.Installments de VTEX."""
    insts = (commertial_offer or {}).get("Installments") or []
    if not insts:
        return {
            "cuotas": 1,
            "sin_interes": False,
            "cuotas_info": None,
            "cuota_monto": price if price > 0 else None,
        }

    interest_free = [
        i for i in insts
        if float(i.get("InterestRate") or 0.0) == 0.0 and int(i.get("NumberOfInstallments") or 1) > 1
    ]
    if interest_free:
        best = max(interest_free, key=lambda x: int(x.get("NumberOfInstallments") or 1))
        n = int(best.get("NumberOfInstallments"))
        val = float(best.get("Value") or (price / n if n > 0 else price))
        val_fmt = f"${int(round(val)):,}".replace(",", ".")
        banco_tag = " con Banco Provincia" if "provincia" in (store_name or "").lower() else ""
        return {
            "cuotas": n,
            "sin_interes": True,
            "cuotas_info": f"{n} cuotas sin interés de {val_fmt}{banco_tag}",
            "cuota_monto": round(val, 2),
        }

    with_interest = [i for i in insts if int(i.get("NumberOfInstallments") or 1) > 1]
    if with_interest:
        best = max(with_interest, key=lambda x: int(x.get("NumberOfInstallments") or 1))
        n = int(best.get("NumberOfInstallments"))
        val = float(best.get("Value") or 0.0)
        val_fmt = f"${int(round(val)):,}".replace(",", ".") if val > 0 else ""
        info = f"{n} cuotas fijas de {val_fmt}" if val_fmt else f"{n} cuotas fijas"
        return {
            "cuotas": n,
            "sin_interes": False,
            "cuotas_info": info,
            "cuota_monto": round(val, 2) if val > 0 else None,
        }

    return {
        "cuotas": 1,
        "sin_interes": False,
        "cuotas_info": None,
        "cuota_monto": price if price > 0 else None,
    }


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

    seller_id = str(p.get("seller_id") or "1")
    seller_name = str(p.get("seller_name") or "")
    cuotas = int(p.get("cuotas") or 1)
    sin_interes = bool(p.get("sin_interes"))
    cuotas_info = p.get("cuotas_info")
    cuota_monto = p.get("cuota_monto")
    store_type = p.get("store_type") or "supermarket"
    modelo = p.get("modelo") or ""
    tipo = p.get("tipo") or ""
    prod_id = str(p.get("id") or p.get("ean") or p.get("itemId") or int(time.time()))

    off = {
        "supermercado": p.get("supermercado") or "Supermercado",
        "precio": display_price,
        "precio_lista": list_p,
        "stock": int(p.get("stock") or 50),
        "disponible": int(p.get("stock") or 50) > 0,
        "link": p.get("link") or "",
        "discount": disc,
        "promo_label": promo,
        "promo_min_qty": min_qty,
        "unit_measure": p.get("unidad_medida") or "u",
        "unit_price": p.get("precio_por_unidad") or display_price,
        "seller_id": seller_id,
        "seller_name": seller_name,
        "store_type": store_type,
        "modelo": modelo,
        "tipo": tipo,
        "cuotas": cuotas,
        "sin_interes": sin_interes,
        "cuotas_info": cuotas_info,
        "cuota_monto": cuota_monto,
    }

    return {
        "id": prod_id,
        "ean": p.get("ean") or str(p.get("itemId") or int(time.time())),
        "primary_ean": p.get("primary_ean") or p.get("ean") or "",
        "nombre": p.get("nombre") or "",
        "marca": p.get("marca") or "",
        "modelo": modelo,
        "tipo": tipo,
        "vertical": tipo or store_type,
        "imagen": p.get("imagen") or "",
        "best_offer": off,
        "offers": [off],
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
                    if not snap.get("marketplace_tiers"):
                        snap["marketplace_tiers"] = copy.deepcopy(BASELINE_MARKETPLACE_TIERS)
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

    # Ensamblar los 3 niveles dedicados para Marketplaces
    final_marketplace_tiers = copy.deepcopy(BASELINE_MARKETPLACE_TIERS)
    for mp_t in final_marketplace_tiers:
        for p in mp_t.get("products", []):
            if "best_offer" not in p and p.get("offers"):
                p["best_offer"] = p["offers"][0]

    data_payload = {
        "tiers": final_tiers,
        "marketplace_tiers": final_marketplace_tiers,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "is_live": is_live_fetch,
        "total_deals": sum(len(t["products"]) for t in final_tiers) + sum(len(t["products"]) for t in final_marketplace_tiers),
    }

    try:
        from . import db
        if hasattr(db, "save_verified_deals_snapshot"):
            try:
                res_save = db.save_verified_deals_snapshot(cache_key, data_payload)
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
    marketplace_tiers = data.get("marketplace_tiers") or []
    issues: list[dict] = []
    total_products = 0

    all_audited_tiers = list(tiers) + list(marketplace_tiers)
    for tier in all_audited_tiers:
        t_id = str(tier.get("id") or "unknown")

        # 1. Auditar meliSponsored (si existe)
        sp = tier.get("meliSponsored")
        if sp and isinstance(sp, dict):
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
        "marketplace_tiers_count": len(marketplace_tiers),
        "total_products": total_products,
        "issues": issues,
    }
