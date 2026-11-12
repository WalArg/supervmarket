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
import os
import sqlite3
from typing import Any, Dict, List, Optional

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
                "offers": []
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
                "unit_price": 6978
            }
        },
        "products": [
            {
                "ean": "7622201735296",
                "nombre": "Galletitas Oreo x 118 g",
                "marca": "Oreo",
                "imagen": "https://farmacityar.vteximg.com.br/arquivos/ids/298494/251535_galletitas-oreo-x-118-g_imagen-1.jpg?v=639229342479300000",
                "offers": [
                    {
                        "supermercado": "Dia",
                        "precio": 810,
                        "precio_lista": 1350,
                        "stock": 120,
                        "link": "https://diaonline.supermercadosdia.com.ar/galletitas-oreo-rellenas-con-crema-sabor-original-menos-sodio-118-gr-271629/p",
                        "discount": 40,
                        "promo_label": "40% OFF Directo",
                        "unit_measure": "kg",
                        "unit_price": 6864
                    },
                    {
                        "supermercado": "Masonline",
                        "precio": 798,
                        "precio_lista": 1200,
                        "stock": 80,
                        "link": "https://www.masonline.com.ar/galletitas-dulces-oreo-con-relleno-sabor-a-vainilla-118-gr-13865/p",
                        "discount": 33,
                        "promo_label": "33% OFF",
                        "unit_measure": "kg",
                        "unit_price": 6762
                    },
                    {
                        "supermercado": "Coto",
                        "precio": 1230,
                        "precio_lista": 1230,
                        "stock": 60,
                        "link": "https://www.cotodigital3.com.ar/sitios/cdigi/producto/-galletitas-oreo-rellenas-118-gr/_/A-00503124-00503124-200/p",
                        "unit_measure": "kg",
                        "unit_price": 10423
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 1890,
                        "precio_lista": 2490,
                        "stock": 90,
                        "link": "https://www.mercadolibre.com.ar/p/MLA19754890",
                        "discount": 24,
                        "promo_label": "24% OFF · FULL",
                        "seller_name": "Mercado Libre Supermercado",
                        "is_full": True,
                        "unit_measure": "kg",
                        "unit_price": 16016
                    },
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
                        "unit_price": 22364
                    }
                ]
            },
            {
                "ean": "7791290796430",
                "nombre": "Jabón Líquido Skip Limpieza Activa Doypack 800ml",
                "marca": "Skip",
                "imagen": "https://farmaonline.vteximg.com.br/arquivos/ids/1458225/8144165_0.jpg?v=639252564197900000",
                "offers": [
                    {
                        "supermercado": "Dia",
                        "precio": 2821,
                        "precio_lista": 4340,
                        "stock": 90,
                        "link": "https://diaonline.supermercadosdia.com.ar/jabon-liquido-para-ropa-skip-bio-enzimas-doypack-800-ml-14660/p",
                        "discount": 35,
                        "promo_label": "35% OFF Directo",
                        "unit_measure": "lt",
                        "unit_price": 3526
                    },
                    {
                        "supermercado": "Carrefour",
                        "precio": 3084,
                        "precio_lista": 4745,
                        "stock": 50,
                        "link": "https://www.carrefour.com.ar/jabon-liquido-skip-bio-enzimas-doypack-800-ml-695715/p",
                        "discount": 35,
                        "promo_label": "35% OFF Directo",
                        "unit_measure": "lt",
                        "unit_price": 3855
                    },
                    {
                        "supermercado": "Farmacity",
                        "precio": 3626,
                        "precio_lista": 4835,
                        "stock": 45,
                        "link": "https://www.farmacity.com/jabon-liquido-skip-bio-enzimas-800-ml/p",
                        "discount": 25,
                        "promo_label": "25% OFF Directo",
                        "unit_measure": "lt",
                        "unit_price": 4532
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 3490,
                        "precio_lista": 4990,
                        "stock": 100,
                        "link": "https://www.mercadolibre.com.ar/p/MLA28475920",
                        "discount": 30,
                        "promo_label": "30% OFF · FULL",
                        "seller_name": "Tienda Oficial Unilever",
                        "is_full": True,
                        "unit_measure": "lt",
                        "unit_price": 4362
                    },
                    {
                        "supermercado": "Coto",
                        "precio": 4346,
                        "precio_lista": 4346,
                        "stock": 70,
                        "link": "https://www.cotodigital3.com.ar/sitios/cdigi/producto/-jabon-liquido-skip-bio-enzimas-doypack-800-ml/_/A-00498765-00498765-200/p",
                        "unit_measure": "lt",
                        "unit_price": 5432
                    }
                ]
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
                        "unit_price": 5235
                    }
                ]
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
                        "unit_price": 46433
                    }
                ]
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
                        "unit_price": 20840
                    }
                ]
            }
        ]
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
                "offers": []
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
                "unit_price": 5555
            }
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
                        "unit_price": 1816
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 1490,
                        "precio_lista": 2200,
                        "stock": 50,
                        "link": "https://www.mercadolibre.com.ar/p/MLA24589211",
                        "discount": 32,
                        "promo_label": "32% OFF · FULL",
                        "seller_name": "Bebidas Oficial",
                        "is_full": True,
                        "unit_measure": "lt",
                        "unit_price": 3921
                    },
                    {
                        "supermercado": "Coto",
                        "precio": 1890,
                        "precio_lista": 1890,
                        "stock": 40,
                        "link": "https://www.cotodigital3.com.ar/sitios/cdigi/producto/-whisky-petakon-380-ml/_/A-00412345-00412345-200/p",
                        "unit_measure": "lt",
                        "unit_price": 4973
                    },
                    {
                        "supermercado": "Dia",
                        "precio": 1990,
                        "precio_lista": 1990,
                        "stock": 35,
                        "link": "https://diaonline.supermercadosdia.com.ar/whisky-petakon-petaca-380-ml-19823/p",
                        "unit_measure": "lt",
                        "unit_price": 5236
                    }
                ]
            },
            {
                "ean": "7798138555999",
                "nombre": "Bolsa de residuos Trash 45x60 x 10 uni",
                "marca": "Trash",
                "imagen": "https://carrefourar.vteximg.com.br/arquivos/ids/461042/2695706000003_01.jpg",
                "offers": [
                    {
                        "supermercado": "Disco",
                        "precio": 228,
                        "precio_lista": 380,
                        "stock": 60,
                        "link": "https://www.disco.com.ar/bolsa-residuos-trash-45x60-x10/p",
                        "discount": 40,
                        "promo_label": "40% OFF Directo",
                        "unit_measure": "u",
                        "unit_price": 23
                    },
                    {
                        "supermercado": "Carrefour",
                        "precio": 300,
                        "precio_lista": 800,
                        "stock": 80,
                        "link": "https://www.carrefour.com.ar/bolsa-de-residuos-trash-45x60-x-10-uni-748411/p",
                        "discount": 62,
                        "promo_label": "62% OFF Directo",
                        "unit_measure": "u",
                        "unit_price": 30
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 399,
                        "precio_lista": 590,
                        "stock": 120,
                        "link": "https://www.mercadolibre.com.ar/p/MLA28911420",
                        "discount": 32,
                        "promo_label": "32% OFF · FULL",
                        "seller_name": "Tienda Oficial Trash",
                        "is_full": True,
                        "unit_measure": "u",
                        "unit_price": 40
                    },
                    {
                        "supermercado": "Dia",
                        "precio": 450,
                        "precio_lista": 450,
                        "stock": 75,
                        "link": "https://diaonline.supermercadosdia.com.ar/bolsas-de-residuos-trash-45x60-10-uni-18491/p",
                        "unit_measure": "u",
                        "unit_price": 45
                    },
                    {
                        "supermercado": "Coto",
                        "precio": 550,
                        "precio_lista": 550,
                        "stock": 50,
                        "link": "https://www.cotodigital3.com.ar/sitios/cdigi/producto/-bolsas-residuos-trash-45x60/_/A-00512890-00512890-200/p",
                        "unit_measure": "u",
                        "unit_price": 55
                    }
                ]
            },
            {
                "ean": "7790520023027",
                "nombre": "Insecticida Raid Mata Moscas y Mosquitos 370 ml",
                "marca": "Raid",
                "imagen": "https://carrefourar.vteximg.com.br/arquivos/ids/891977/7790520997623_01.jpg",
                "offers": [
                    {
                        "supermercado": "Dia",
                        "precio": 2100,
                        "precio_lista": 3500,
                        "stock": 80,
                        "link": "https://diaonline.supermercadosdia.com.ar/insecticida-raid-mata-moscas-y-mosquitos-370-ml-12903/p",
                        "discount": 40,
                        "promo_label": "40% OFF Directo",
                        "unit_measure": "lt",
                        "unit_price": 5675
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 2490,
                        "precio_lista": 3990,
                        "stock": 100,
                        "link": "https://www.mercadolibre.com.ar/p/MLA21345678",
                        "discount": 38,
                        "promo_label": "38% OFF · FULL",
                        "seller_name": "Tienda Oficial SC Johnson",
                        "is_full": True,
                        "unit_measure": "lt",
                        "unit_price": 6729
                    },
                    {
                        "supermercado": "Coto",
                        "precio": 2823,
                        "precio_lista": 3764,
                        "stock": 65,
                        "link": "https://www.cotodigital3.com.ar/sitios/cdigi/producto/-insecticida-raid-aerosol-370-ml/_/A-00481234-00481234-200/p",
                        "discount": 25,
                        "promo_label": "25% OFF Directo",
                        "unit_measure": "lt",
                        "unit_price": 7630
                    },
                    {
                        "supermercado": "Carrefour",
                        "precio": 3119,
                        "precio_lista": 7409,
                        "stock": 45,
                        "link": "https://www.carrefour.com.ar/insecticida-raid-mata-moscas-y-mosquitos-nueva-formula-x2-mas-rapido-en-aerosol-370-ml-703700/p",
                        "discount": 58,
                        "promo_label": "58% OFF Directo",
                        "unit_measure": "lt",
                        "unit_price": 8430
                    },
                    {
                        "supermercado": "Farmaonline",
                        "precio": 3328,
                        "precio_lista": 4160,
                        "stock": 40,
                        "link": "https://www.farmaonline.com/insecticida-raid-moscas-mosquitos-370-ml/p",
                        "discount": 20,
                        "promo_label": "20% OFF Directo",
                        "unit_measure": "lt",
                        "unit_price": 8994
                    }
                ]
            },
            {
                "ean": "7794450000781",
                "nombre": "Vino Tinto Álamos Malbec 750 Ml",
                "marca": "Álamos",
                "imagen": "https://ardiaprod.vteximg.com.br/arquivos/ids/314458/Vino-Tinto-Alamos-Malbec-750-Ml-_1.jpg?v=638599428555500000",
                "offers": [
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 9999,
                        "precio_lista": 14500,
                        "stock": 110,
                        "link": "https://www.mercadolibre.com.ar/p/MLA14389201",
                        "discount": 31,
                        "promo_label": "31% OFF · FULL",
                        "seller_name": "Tienda Oficial Catena Zapata",
                        "is_full": True,
                        "unit_measure": "lt",
                        "unit_price": 13332
                    },
                    {
                        "supermercado": "Carrefour",
                        "precio": 11265,
                        "precio_lista": 16900,
                        "stock": 60,
                        "link": "https://www.carrefour.com.ar/vino-tinto-malbec-alamos-750-cc-20275/p",
                        "discount": 33,
                        "promo_label": "3x2 ($11.265 c/u x3)",
                        "promo_min_qty": 3,
                        "unit_measure": "lt",
                        "unit_price": 15020
                    },
                    {
                        "supermercado": "Masonline",
                        "precio": 12500,
                        "precio_lista": 15600,
                        "stock": 40,
                        "link": "https://www.masonline.com.ar/vino-tinto-alamos-malbec-750-ml-18923/p",
                        "discount": 20,
                        "promo_label": "20% OFF",
                        "unit_measure": "lt",
                        "unit_price": 16666
                    },
                    {
                        "supermercado": "Coto",
                        "precio": 13200,
                        "precio_lista": 13200,
                        "stock": 50,
                        "link": "https://www.cotodigital3.com.ar/sitios/cdigi/producto/-vino-fino-tinto-alamos-malbec-750-ml/_/A-00123984-00123984-200/p",
                        "unit_measure": "lt",
                        "unit_price": 17600
                    }
                ]
            }
        ]
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
                "offers": []
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
                "unit_price": 53850
            }
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
                        "unit_price": 2100
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 1290,
                        "precio_lista": 1750,
                        "stock": 90,
                        "link": "https://www.mercadolibre.com.ar/p/MLA19348911",
                        "discount": 26,
                        "promo_label": "26% OFF · FULL",
                        "seller_name": "Mercado Libre Supermercado",
                        "is_full": True,
                        "unit_measure": "kg",
                        "unit_price": 2580
                    },
                    {
                        "supermercado": "Carrefour",
                        "precio": 1450,
                        "precio_lista": 1450,
                        "stock": 70,
                        "link": "https://www.carrefour.com.ar/fideos-tirabuzon-lucchetti-500-g-15491/p",
                        "unit_measure": "kg",
                        "unit_price": 2900
                    },
                    {
                        "supermercado": "Coto",
                        "precio": 1520,
                        "precio_lista": 1520,
                        "stock": 60,
                        "link": "https://www.cotodigital3.com.ar/sitios/cdigi/producto/-fideos-secos-tirabuzon-lucchetti-500-gr/_/A-00389123-00389123-200/p",
                        "unit_measure": "kg",
                        "unit_price": 3040
                    }
                ]
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
                        "unit_price": 3572
                    },
                    {
                        "supermercado": "Carrefour",
                        "precio": 1884,
                        "precio_lista": 3140,
                        "stock": 45,
                        "link": "https://www.carrefour.com.ar/cerveza-honey-lazybee-bierhaus-473-ml-720914/p",
                        "discount": 40,
                        "promo_label": "40% OFF Directo",
                        "unit_measure": "lt",
                        "unit_price": 3983
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 2190,
                        "precio_lista": 3200,
                        "stock": 80,
                        "link": "https://www.mercadolibre.com.ar/p/MLA25678912",
                        "discount": 32,
                        "promo_label": "32% OFF · FULL",
                        "seller_name": "Tienda Oficial Bierhaus",
                        "is_full": True,
                        "unit_measure": "lt",
                        "unit_price": 4629
                    },
                    {
                        "supermercado": "Vea",
                        "precio": 2400,
                        "precio_lista": 3000,
                        "stock": 30,
                        "link": "https://www.vea.com.ar/cerveza-bierhaus-honey-473-ml/p",
                        "discount": 20,
                        "unit_measure": "lt",
                        "unit_price": 5073
                    },
                    {
                        "supermercado": "Coto",
                        "precio": 3395,
                        "precio_lista": 3395,
                        "stock": 50,
                        "link": "https://www.cotodigital3.com.ar/sitios/cdigi/producto/-cerveza-artesanal-honey-bierhaus-473-ml/_/A-00523456-00523456-200/p",
                        "unit_measure": "lt",
                        "unit_price": 7177
                    }
                ]
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
                        "unit_price": 21995
                    }
                ]
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
                        "unit_price": 64
                    }
                ]
            }
        ]
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
                "offers": []
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
                "unit_price": 4866
            }
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
                        "unit_price": 2269
                    }
                ]
            },
            {
                "ean": "7790310985571",
                "nombre": "Nachos Sabor a Queso Doritos 200 G",
                "marca": "Doritos",
                "imagen": "https://carrefourar.vteximg.com.br/arquivos/ids/904460/7790310985571_E01.jpg",
                "offers": [
                    {
                        "supermercado": "Dia",
                        "precio": 1500,
                        "precio_lista": 2500,
                        "stock": 75,
                        "link": "https://diaonline.supermercadosdia.com.ar/snack-nachos-queso-doritos-200-gr-18491/p",
                        "discount": 40,
                        "promo_label": "40% OFF Directo",
                        "unit_measure": "kg",
                        "unit_price": 7500
                    },
                    {
                        "supermercado": "Coto",
                        "precio": 2150,
                        "precio_lista": 2500,
                        "stock": 50,
                        "link": "https://www.cotodigital3.com.ar/sitios/cdigi/producto/-nachos-doritos-queso-200-gr/_/A-00456123-00456123-200/p",
                        "discount": 14,
                        "unit_measure": "kg",
                        "unit_price": 10750
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 2890,
                        "precio_lista": 3800,
                        "stock": 85,
                        "link": "https://www.mercadolibre.com.ar/p/MLA16789432",
                        "discount": 24,
                        "promo_label": "24% OFF · FULL",
                        "seller_name": "Mercado Libre Supermercado",
                        "is_full": True,
                        "unit_measure": "kg",
                        "unit_price": 14450
                    },
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
                        "unit_price": 28495
                    }
                ]
            },
            {
                "ean": "7790310985793",
                "nombre": "Chizitos de Maíz Queso Cheetos Original 140 G",
                "marca": "Cheetos",
                "imagen": "https://carrefourar.vteximg.com.br/arquivos/ids/904233/7790310985793_E01.jpg",
                "offers": [
                    {
                        "supermercado": "Dia",
                        "precio": 2500,
                        "precio_lista": 3500,
                        "stock": 60,
                        "link": "https://diaonline.supermercadosdia.com.ar/chizitos-queso-cheetos-140-gr-19234/p",
                        "discount": 29,
                        "unit_measure": "kg",
                        "unit_price": 17857
                    },
                    {
                        "supermercado": "Coto",
                        "precio": 2500,
                        "precio_lista": 3200,
                        "stock": 55,
                        "link": "https://www.cotodigital3.com.ar/sitios/cdigi/producto/-chizitos-cheetos-140-gr/_/A-00478123-00478123-200/p",
                        "discount": 22,
                        "unit_measure": "kg",
                        "unit_price": 17857
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 2690,
                        "precio_lista": 3500,
                        "stock": 90,
                        "link": "https://www.mercadolibre.com.ar/p/MLA17894561",
                        "discount": 23,
                        "promo_label": "23% OFF · FULL",
                        "seller_name": "Mercado Libre Supermercado",
                        "is_full": True,
                        "unit_measure": "kg",
                        "unit_price": 19214
                    },
                    {
                        "supermercado": "Carrefour",
                        "precio": 3509,
                        "precio_lista": 5849,
                        "stock": 50,
                        "link": "https://www.carrefour.com.ar/chizitos-de-maiz-sabor-a-queso-cheetos-original-140-g-729770-/p",
                        "discount": 40,
                        "promo_label": "40% OFF Directo",
                        "unit_measure": "kg",
                        "unit_price": 25064
                    }
                ]
            },
            {
                "ean": "7790310985588",
                "nombre": "Papas Fritas Lays Clásicas 330 G",
                "marca": "Lays",
                "imagen": "https://carrefourar.vteximg.com.br/arquivos/ids/904216/7790310985588_E01.jpg",
                "offers": [
                    {
                        "supermercado": "Dia",
                        "precio": 2500,
                        "precio_lista": 4200,
                        "stock": 70,
                        "link": "https://diaonline.supermercadosdia.com.ar/papas-fritas-lays-clasicas-330-gr-12904/p",
                        "discount": 40,
                        "promo_label": "40% OFF Directo",
                        "unit_measure": "kg",
                        "unit_price": 7575
                    },
                    {
                        "supermercado": "Coto",
                        "precio": 2500,
                        "precio_lista": 3800,
                        "stock": 65,
                        "link": "https://www.cotodigital3.com.ar/sitios/cdigi/producto/-papas-fritas-lays-clasicas-330-gr/_/A-00490123-00490123-200/p",
                        "discount": 34,
                        "unit_measure": "kg",
                        "unit_price": 7575
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 3490,
                        "precio_lista": 4800,
                        "stock": 80,
                        "link": "https://www.mercadolibre.com.ar/p/MLA18904512",
                        "discount": 27,
                        "promo_label": "27% OFF · FULL",
                        "seller_name": "Mercado Libre Supermercado",
                        "is_full": True,
                        "unit_measure": "kg",
                        "unit_price": 10575
                    },
                    {
                        "supermercado": "Carrefour",
                        "precio": 6299,
                        "precio_lista": 10499,
                        "stock": 40,
                        "link": "https://www.carrefour.com.ar/papas-fritas-lays-clasicas-330-g-721964/p",
                        "discount": 40,
                        "promo_label": "40% OFF Directo",
                        "unit_measure": "kg",
                        "unit_price": 19087
                    }
                ]
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
                        "unit_price": 3079
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 1490,
                        "precio_lista": 2100,
                        "stock": 100,
                        "link": "https://www.mercadolibre.com.ar/p/MLA15678901",
                        "discount": 29,
                        "promo_label": "29% OFF · FULL",
                        "seller_name": "Tienda Oficial Quilmes",
                        "is_full": True,
                        "unit_measure": "lt",
                        "unit_price": 4209
                    },
                    {
                        "supermercado": "Masonline",
                        "precio": 1724,
                        "precio_lista": 2200,
                        "stock": 45,
                        "link": "https://www.masonline.com.ar/cerveza-quilmes-1890-lata-354-ml-19234/p",
                        "discount": 22,
                        "unit_measure": "lt",
                        "unit_price": 4870
                    },
                    {
                        "supermercado": "Carrefour",
                        "precio": 1885,
                        "precio_lista": 2350,
                        "stock": 60,
                        "link": "https://www.carrefour.com.ar/cerveza-quilmes-1890-354-ml-18901/p",
                        "discount": 20,
                        "unit_measure": "lt",
                        "unit_price": 5324
                    },
                    {
                        "supermercado": "Josimar",
                        "precio": 1955,
                        "precio_lista": 2300,
                        "stock": 30,
                        "link": "https://www.josimar.com.ar/cerveza-rubia-quilmes-1890-lata-354-cc/p",
                        "discount": 15,
                        "unit_measure": "lt",
                        "unit_price": 5522
                    },
                    {
                        "supermercado": "Coto",
                        "precio": 2300,
                        "precio_lista": 2300,
                        "stock": 50,
                        "link": "https://www.cotodigital3.com.ar/sitios/cdigi/producto/-cerveza-1890-quilmes-354-ml/_/A-00349012-00349012-200/p",
                        "unit_measure": "lt",
                        "unit_price": 6497
                    }
                ]
            }
        ]
    }
]


BASELINE_MARKETPLACE_TIERS = [
    {
        "id": "tier-mp-electro",
        "title": "Electrodomésticos y Tecnología — Hasta 40% OFF y Cuotas",
        "subtitle": "Smart TVs, celulares, notebooks, lavarropas y heladeras con financiación",
        "badge": "Electro & Tech",
        "percentLabel": "Hasta 40% OFF + Cuotas",
        "icon": "zap",
        "vertical": "electro",
        "products": [
            {
                "id": "8806097622369",
                "ean": "8806097622369",
                "primary_ean": "8806097622369",
                "nombre": "Smart TV Samsung 55'' Qled 4K Q6F QN55Q6FAAGCZB Tizen",
                "marca": "Samsung",
                "modelo": "QN55Q6FAA",
                "tipo": "electro",
                "vertical": "electro",
                "categoria_normalizada": "televisores",
                "imagen": "https://carrefourar.vteximg.com.br/arquivos/ids/878516/image-d4fd1a3579af41af8df13fa091239900.jpg?v=639149656309630000",
                "offers": [
                    {
                        "supermercado": "Coppel",
                        "precio": 699999,
                        "precio_lista": 799999,
                        "stock": 45,
                        "disponible": True,
                        "discount": 13,
                        "promo_label": "13% OFF",
                        "seller_name": "Coppel",
                        "seller_id": "1",
                        "store_type": "electro",
                        "link": "https://www.coppel.com.ar/smart-qled-tv-4k-55--samsung-55q60aa-231525/p"
                    },
                    {
                        "supermercado": "Frávega",
                        "precio": 763635,
                        "precio_lista": 923999,
                        "stock": 80,
                        "disponible": True,
                        "discount": 17,
                        "promo_label": "17% OFF",
                        "seller_name": "Frávega",
                        "seller_id": "1",
                        "store_type": "electro",
                        "link": "https://www.fravega.com/smart-tv-samsung-55-uhd-4k-cu7000-990062277/p"
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 799999,
                        "precio_lista": 1099999,
                        "stock": 50,
                        "disponible": True,
                        "discount": 27,
                        "promo_label": "27% OFF · FULL",
                        "seller_name": "Tienda Oficial Samsung",
                        "is_full": True,
                        "free_shipping": True,
                        "link": "https://listado.mercadolibre.com.ar/smart-tv-samsung-55-qled"
                    },
                    {
                        "supermercado": "Samsung",
                        "precio": 819999,
                        "precio_lista": 1099999,
                        "stock": 99999,
                        "disponible": True,
                        "discount": 25,
                        "promo_label": "25% OFF",
                        "seller_name": "Samsung",
                        "seller_id": "1",
                        "store_type": "electro",
                        "link": "https://www.samsung.com/ar/search/?searchvalue=Smart%20TV%2055%20QLED"
                    },
                    {
                        "supermercado": "Carrefour",
                        "precio": 1193000,
                        "precio_lista": 1193000,
                        "stock": 20,
                        "disponible": True,
                        "discount": 0,
                        "seller_name": "Carrefour",
                        "link": "https://www.carrefour.com.ar/smart-tv-samsung-55-4k-un55au7000gczb-gris/p"
                    },
                    {
                        "supermercado": "Naldo",
                        "precio": 1399999,
                        "precio_lista": 1999999,
                        "stock": 30,
                        "disponible": True,
                        "discount": 30,
                        "promo_label": "30% OFF",
                        "seller_name": "Naldo",
                        "link": "https://www.naldo.com.ar/smart-tv-samsung-55-4k-qled-505680/p"
                    }
                ]
            },
            {
                "id": "8806099122164",
                "ean": "8806099122164",
                "primary_ean": "8806099122164",
                "nombre": "Galaxy A07 Black 64GB",
                "marca": "Samsung",
                "modelo": "A07",
                "tipo": "electro",
                "vertical": "electro",
                "categoria_normalizada": "celulares",
                "imagen": "https://samsungar.vteximg.com.br/arquivos/ids/220508/SM-A075MZKEARO.png?v=639112765534100000",
                "offers": [
                    {
                        "supermercado": "Frávega",
                        "precio": 194048,
                        "precio_lista": 293499,
                        "stock": 80,
                        "disponible": True,
                        "discount": 34,
                        "promo_label": "34% OFF",
                        "seller_name": "Frávega",
                        "link": "https://www.fravega.com/celular-samsung-a07-4-gb-ram-64-gb-memoriia-interna-liberado-verde-990680781/p"
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 229999,
                        "precio_lista": 299999,
                        "stock": 120,
                        "disponible": True,
                        "discount": 23,
                        "promo_label": "23% OFF · FULL",
                        "seller_name": "Tienda Oficial Samsung",
                        "is_full": True,
                        "free_shipping": True,
                        "link": "https://listado.mercadolibre.com.ar/samsung-galaxy-a07"
                    },
                    {
                        "supermercado": "Provincia Compras",
                        "precio": 236099,
                        "precio_lista": 299999,
                        "stock": 50,
                        "disponible": True,
                        "discount": 21,
                        "promo_label": "21% OFF",
                        "seller_name": "Provincia Compras",
                        "link": "https://www.provinciacompras.com.ar/celular-samsung-galaxy-a07-64gb-279466/p"
                    },
                    {
                        "supermercado": "Naldo",
                        "precio": 299999,
                        "precio_lista": 699999,
                        "stock": 100,
                        "disponible": True,
                        "discount": 57,
                        "promo_label": "57% OFF",
                        "seller_name": "Naldo",
                        "seller_id": "1",
                        "store_type": "electro",
                        "link": "https://www.naldo.com.ar/galaxy-a07-black-4-64gb-6-7--407140/p"
                    },
                    {
                        "supermercado": "Masonline",
                        "precio": 299999,
                        "precio_lista": 349999,
                        "stock": 40,
                        "disponible": True,
                        "discount": 14,
                        "promo_label": "14% OFF",
                        "seller_name": "Más Online",
                        "link": "https://www.masonline.com.ar/celular-samsung-galaxy-a07-64gb-sm-a075m-ds-violeta/p"
                    }
                ]
            },
            {
                "id": "7790894902162",
                "ean": "7790894902162",
                "primary_ean": "7790894902162",
                "nombre": "Celular Moto Edge70 Fusion 5g Azul 12/256gb",
                "marca": "MOTOROLA",
                "modelo": "Edge70",
                "tipo": "electro",
                "vertical": "electro",
                "categoria_normalizada": "celulares",
                "imagen": "https://naldoar.vteximg.com.br/arquivos/ids/243342/Copy-of-2025_AVENGER_BASICPACK_SILHOUETTE_PDP-HERO-copia.jpg?v=639293952450330000",
                "offers": [
                    {
                        "supermercado": "Frávega",
                        "precio": 778468,
                        "precio_lista": 1066395,
                        "stock": 45,
                        "disponible": True,
                        "discount": 27,
                        "promo_label": "27% OFF",
                        "seller_name": "Frávega",
                        "link": "https://www.fravega.com/reacondicionado-motorola-edge-60-fusion-256gb-color-gris-23140529/p"
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 849999,
                        "precio_lista": 1099999,
                        "stock": 80,
                        "disponible": True,
                        "discount": 23,
                        "promo_label": "23% OFF · FULL",
                        "seller_name": "Tienda Oficial Motorola",
                        "is_full": True,
                        "free_shipping": True,
                        "link": "https://listado.mercadolibre.com.ar/moto-edge-fusion-5g"
                    },
                    {
                        "supermercado": "Naldo",
                        "precio": 899999,
                        "precio_lista": 2099999,
                        "stock": 99999,
                        "disponible": True,
                        "discount": 57,
                        "promo_label": "57% OFF",
                        "seller_name": "Naldo",
                        "seller_id": "1",
                        "store_type": "electro",
                        "link": "https://www.naldo.com.ar/moto-edge70-fusion-5g-azul-12-256gb-407209/p"
                    },
                    {
                        "supermercado": "Carrefour",
                        "precio": 999999,
                        "precio_lista": 1199999,
                        "stock": 25,
                        "disponible": True,
                        "discount": 17,
                        "promo_label": "17% OFF",
                        "seller_name": "Carrefour",
                        "link": "https://www.carrefour.com.ar/celular-libre-motorola-edge-fusion-256gb/p"
                    }
                ]
            },
            {
                "id": "6932554444792",
                "ean": "6932554444792",
                "primary_ean": "6932554444792",
                "nombre": "Celular Xiaomi Redmi A5 Ocean Blue 4/128gb 6.88'' REDMI A5 OCEAN BLUE 4/128GB 6.88''",
                "marca": "XIAOMI",
                "modelo": "",
                "tipo": "electro",
                "vertical": "electro",
                "categoria_normalizada": "celulares",
                "imagen": "https://naldoar.vteximg.com.br/arquivos/ids/230318/WhatsApp-Image-2026-07-16-at-09.29.58--1-.jpg?v=639210133117930000",
                "offers": [
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 289999,
                        "precio_lista": 429000,
                        "stock": 100,
                        "disponible": True,
                        "discount": 32,
                        "promo_label": "32% OFF · FULL",
                        "seller_name": "Tienda Oficial Xiaomi",
                        "is_full": True,
                        "free_shipping": True,
                        "link": "https://listado.mercadolibre.com.ar/xiaomi-redmi-ocean-blue"
                    },
                    {
                        "supermercado": "Carrefour",
                        "precio": 299900,
                        "precio_lista": 429000,
                        "stock": 45,
                        "disponible": True,
                        "discount": 30,
                        "promo_label": "30% OFF",
                        "seller_name": "Carrefour",
                        "link": "https://www.carrefour.com.ar/celular-libre-xiaomi-redmi-note-13-6gb-128-gb-verde/p"
                    },
                    {
                        "supermercado": "Naldo",
                        "precio": 299999,
                        "precio_lista": 699999,
                        "stock": 100,
                        "disponible": True,
                        "discount": 57,
                        "promo_label": "57% OFF",
                        "seller_name": "Naldo",
                        "seller_id": "1",
                        "store_type": "electro",
                        "link": "https://www.naldo.com.ar/redmi-a5-ocean-blue-4-128gb-6-88--407150/p"
                    },
                    {
                        "supermercado": "Coppel",
                        "precio": 349999,
                        "precio_lista": 349999,
                        "stock": 30,
                        "disponible": True,
                        "discount": 0,
                        "seller_name": "Coppel",
                        "link": "https://www.coppel.com.ar/celular-xiaomi-redmi-note-11-star-blue-4gb-128gb-4g-725021/p"
                    }
                ]
            },
            {
                "id": "NALDO-44923",
                "ean": "NALDO-44923",
                "primary_ean": "NALDO-44923",
                "nombre": "Notebook Hp 15-Fc0251la R5-7520u Amd15\" 8/512 Gb NOTE 15-FC0251LA R5-7520U AMD15\" 8/512GB",
                "marca": "HP",
                "modelo": "15-Fc0251la",
                "tipo": "electro",
                "vertical": "electro",
                "categoria_normalizada": "notebooks_tablets",
                "imagen": "https://naldoar.vteximg.com.br/arquivos/ids/244332/B9TP2LA_01ImagenPrincipalConTexto_b.jpg?v=639292293941600000",
                "offers": [
                    {
                        "supermercado": "Naldo",
                        "precio": 1299999,
                        "precio_lista": 2696198,
                        "stock": 99999,
                        "disponible": True,
                        "discount": 51,
                        "promo_label": "51% OFF",
                        "seller_name": "Naldo",
                        "seller_id": "1",
                        "store_type": "electro",
                        "link": "https://www.naldo.com.ar/note-15-fc0251la-r5-7520u-amd15-8-512gb-406750-1/p"
                    },
                    {
                        "supermercado": "Provincia Compras",
                        "precio": 1299999,
                        "precio_lista": 2696198,
                        "stock": 40,
                        "disponible": True,
                        "discount": 51,
                        "promo_label": "51% OFF",
                        "seller_name": "Provincia Compras",
                        "link": "https://www.provinciacompras.com.ar/notebook-hp-15-fc0251la-r5-7520u-amd15--8-512-gb-310639/p"
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 1349999,
                        "precio_lista": 2499999,
                        "stock": 35,
                        "disponible": True,
                        "discount": 46,
                        "promo_label": "46% OFF · FULL",
                        "seller_name": "Tienda Oficial HP",
                        "is_full": True,
                        "free_shipping": True,
                        "link": "https://listado.mercadolibre.com.ar/notebook-hp-15-ryzen-5"
                    },
                    {
                        "supermercado": "Cetrogar",
                        "precio": 1549999,
                        "precio_lista": 2499999,
                        "stock": 25,
                        "disponible": True,
                        "discount": 38,
                        "promo_label": "38% OFF",
                        "seller_name": "Cetrogar",
                        "link": "https://www.cetrogar.com.ar/notebook-hp-15-fc0251la-15-6-ryzen-5-7520u-8-gb-512-gb-mochila-cm4799/p"
                    },
                    {
                        "supermercado": "Carrefour",
                        "precio": 1699000,
                        "precio_lista": 2099000,
                        "stock": 15,
                        "disponible": True,
                        "discount": 19,
                        "promo_label": "19% OFF",
                        "seller_name": "Carrefour",
                        "link": "https://www.carrefour.com.ar/notebook-hp-15--amd-r5-7520u-8gb-ram-512gb-ssd-fc02/p"
                    }
                ]
            }
        ]
    },
    {
        "id": "tier-mp-hogar",
        "title": "Hogar, Herramientas y Climatización — Gran Ahorro",
        "subtitle": "Sommiers, colchones de espuma y resortes con hasta 75% OFF",
        "badge": "Hogar & Descanso",
        "percentLabel": "Hasta 70% OFF",
        "icon": "tag",
        "vertical": "marketplace",
        "products": [
            {
                "id": "CAR10170208140190-VDT",
                "ean": "CAR10170208140190-VDT",
                "primary_ean": "CAR10170208140190-VDT",
                "nombre": "Combo 2230 NORCEE 140x190 Sommier + Colchón + Respaldo y 2 almohadas de regalo Espuma Alta Densidad",
                "marca": "Veintidostreinta",
                "modelo": "",
                "tipo": "supermarket",
                "vertical": "hogar",
                "categoria_normalizada": "muebles_racks",
                "imagen": "https://carrefourar.vteximg.com.br/arquivos/ids/958490/image-4687f98ab08c4443805b161d4ffe342d.jpg?v=639281067992030000",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 948999,
                        "precio_lista": 3552337,
                        "stock": 100,
                        "disponible": True,
                        "discount": 73,
                        "promo_label": "73% OFF",
                        "seller_name": "Carrefour",
                        "seller_id": "1",
                        "store_type": "supermarket",
                        "link": "https://www.carrefour.com.ar/combo-2230-norcee-140x190-sommier---colchon---respaldo-y-2-almohadas-de-regalo-espuma-alta-densidad-1777715/p"
                    },
                    {
                        "supermercado": "Provincia Compras",
                        "precio": 989000,
                        "precio_lista": 1980000,
                        "stock": 50,
                        "disponible": True,
                        "discount": 50,
                        "promo_label": "50% OFF · 24 cuotas sin interés",
                        "seller_name": "Tienda Oficial Norcee",
                        "seller_id": "1",
                        "store_type": "marketplace",
                        "cuotas": 24,
                        "sin_interes": True,
                        "link": "https://www.provinciacompras.com.ar/combo-2230-norcee-140x190-sommier/p"
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 999000,
                        "precio_lista": 1890000,
                        "stock": 60,
                        "disponible": True,
                        "discount": 47,
                        "promo_label": "47% OFF · FULL",
                        "seller_name": "Tienda Oficial Norcee",
                        "seller_id": "1",
                        "store_type": "marketplace",
                        "is_full": True,
                        "link": "https://listado.mercadolibre.com.ar/sommier-norcee-140x190"
                    }
                ]
            },
            {
                "id": "7796448064287",
                "ean": "7796448064287",
                "primary_ean": "7796448064287",
                "nombre": "Colchón de espuma Zafiro Express Light de 1 plaza 80x190 cm",
                "marca": "Zafiro",
                "modelo": "80x190",
                "tipo": "supermarket",
                "vertical": "hogar",
                "categoria_normalizada": "muebles_racks",
                "imagen": "https://cetrogar.vteximg.com.br/arquivos/ids/171839/image-fd3cf063c8a94a2db2de1a8a7fc41253.jpg?v=639148756004970000",
                "offers": [
                    {
                        "supermercado": "Cetrogar",
                        "precio": 189999,
                        "precio_lista": 499999,
                        "stock": 80,
                        "disponible": True,
                        "discount": 62,
                        "promo_label": "62% OFF",
                        "seller_name": "Cetrogar",
                        "seller_id": "1",
                        "store_type": "electro",
                        "link": "https://www.cetrogar.com.ar/colchon-zafiro-express-80x190.html"
                    },
                    {
                        "supermercado": "Carrefour",
                        "precio": 199999,
                        "precio_lista": 689998,
                        "stock": 100,
                        "disponible": True,
                        "discount": 71,
                        "promo_label": "71% OFF",
                        "seller_name": "Carrefour",
                        "seller_id": "1",
                        "store_type": "supermarket",
                        "link": "https://www.carrefour.com.ar/colchon-de-espuma-1-plaza-zafiro-express-light-80x190-1657924/p"
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 219000,
                        "precio_lista": 450000,
                        "stock": 50,
                        "disponible": True,
                        "discount": 51,
                        "promo_label": "51% OFF · FULL",
                        "seller_name": "Zafiro Colchones",
                        "seller_id": "1",
                        "store_type": "marketplace",
                        "is_full": True,
                        "link": "https://listado.mercadolibre.com.ar/colchon-zafiro-express-80x190"
                    }
                ]
            },
            {
                "id": "CAR10150203140190-VDT",
                "ean": "CAR10150203140190-VDT",
                "primary_ean": "CAR10150203140190-VDT",
                "nombre": "Combo 2230 ZETA PILLOW 140x190 Sommier + Colchón + Respaldo y 2 almohadas de regalo",
                "marca": "Veintidostreinta",
                "modelo": "",
                "tipo": "supermarket",
                "vertical": "hogar",
                "categoria_normalizada": "muebles_racks",
                "imagen": "https://carrefourar.vteximg.com.br/arquivos/ids/958509/image-0630a2dd2b6d439380aef1a3c95da0cb.jpg?v=639281069239100000",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 998999,
                        "precio_lista": 3356524,
                        "stock": 100,
                        "disponible": True,
                        "discount": 70,
                        "promo_label": "70% OFF",
                        "seller_name": "Carrefour",
                        "seller_id": "1",
                        "store_type": "supermarket",
                        "link": "https://www.carrefour.com.ar/combo-2230-zeta-pillow-140x190-sommier---colchon---respaldo-y-2-almohadas-de-regalo-1777717/p"
                    }
                ]
            },
            {
                "id": "7796448067400",
                "ean": "7796448067400",
                "primary_ean": "7796448067400",
                "nombre": "Colchón de resortes Serta Joplin de 2 plazas 140x190 cm",
                "marca": "Serta",
                "modelo": "140x190",
                "tipo": "supermarket",
                "vertical": "hogar",
                "categoria_normalizada": "muebles_racks",
                "imagen": "https://cetrogar.vteximg.com.br/arquivos/ids/170830/image-74b2bb333f18489e8d2670dbd2d19090.jpg?v=639141034319000000",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 369999,
                        "precio_lista": 1219998,
                        "stock": 100,
                        "disponible": True,
                        "discount": 69,
                        "promo_label": "69% OFF",
                        "seller_name": "Carrefour",
                        "seller_id": "1",
                        "store_type": "supermarket",
                        "link": "https://www.carrefour.com.ar/colchon-de-resortes-2-plazas-joplin-140x190-1747841/p"
                    }
                ]
            },
            {
                "id": "CAR10150208140190-VDT",
                "ean": "CAR10150208140190-VDT",
                "primary_ean": "CAR10150208140190-VDT",
                "nombre": "Combo 2230 MALMOK140x190 Sommier + Colchón + Respaldo y 2 almohadas de regalo",
                "marca": "Veintidostreinta",
                "modelo": "",
                "tipo": "supermarket",
                "vertical": "hogar",
                "categoria_normalizada": "muebles_racks",
                "imagen": "https://carrefourar.vteximg.com.br/arquivos/ids/958502/image-984124586aa44679a6027b7b0d287b4e.jpg?v=639281068642670000",
                "offers": [
                    {
                        "supermercado": "Carrefour",
                        "precio": 1148999,
                        "precio_lista": 3510199,
                        "stock": 100,
                        "disponible": True,
                        "discount": 67,
                        "promo_label": "67% OFF",
                        "seller_name": "Carrefour",
                        "seller_id": "1",
                        "store_type": "supermarket",
                        "link": "https://www.carrefour.com.ar/combo-2230-malmok140x190-sommier---colchon---respaldo-y-2-almohadas-de-regalo-1777716/p"
                    }
                ]
            }
        ]
    },
    {
        "id": "tier-mp-destacadas",
        "title": "Ofertas Destacadas de Marketplaces — Precios Bomba",
        "subtitle": "Oportunidades de Naldo, Sony Store, Samsung Oficial con financiación",
        "badge": "Marketplaces",
        "percentLabel": "Financiación y Rebajas",
        "icon": "flame",
        "vertical": "marketplace",
        "products": [
            {
                "id": "SONYSTORE-2939",
                "ean": "SONYSTORE-2939",
                "primary_ean": "SONYSTORE-2939",
                "nombre": "Parlantes para Auto de 4 pulgadas XS-GTF1039 | XS-GTF1039/Z E",
                "marca": "Sony",
                "modelo": "XS-GTF1039",
                "tipo": "supermarket",
                "vertical": "electro",
                "categoria_normalizada": "audio_video",
                "imagen": "https://arsonyb2c.vteximg.com.br/arquivos/ids/362959/01-GENBA-XS-GTF1039-Main-SSO.jpg?v=638303827341900000",
                "offers": [
                    {
                        "supermercado": "Sony Store",
                        "precio": 59996.14,
                        "precio_lista": 129999,
                        "stock": 51,
                        "disponible": True,
                        "discount": 53,
                        "promo_label": "53% OFF",
                        "seller_name": "Sony Store",
                        "seller_id": "1",
                        "store_type": "supermarket",
                        "link": "https://store.sony.com.ar/xs-gtf1039/p"
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 64990,
                        "precio_lista": 129999,
                        "stock": 60,
                        "disponible": True,
                        "discount": 50,
                        "promo_label": "50% OFF · FULL",
                        "seller_name": "Tienda Oficial Sony",
                        "is_full": True,
                        "free_shipping": True,
                        "link": "https://listado.mercadolibre.com.ar/parlantes-sony-xs-gtf1039"
                    },
                    {
                        "supermercado": "Provincia Compras",
                        "precio": 67999,
                        "precio_lista": 78198,
                        "stock": 30,
                        "disponible": True,
                        "discount": 13,
                        "promo_label": "13% OFF",
                        "seller_name": "Provincia Compras",
                        "link": "https://www.provinciacompras.com.ar/parlantes-para-auto-sony-de-4-pulgadas-xs-gtf1039--302800/p"
                    },
                    {
                        "supermercado": "On City",
                        "precio": 79999,
                        "precio_lista": 91998,
                        "stock": 25,
                        "disponible": True,
                        "discount": 13,
                        "promo_label": "13% OFF",
                        "seller_name": "On City",
                        "link": "https://www.oncity.com/parlantes-para-auto-sony-de-4-pulgadas-xs-gtf1039--98930/p"
                    }
                ]
            },
            {
                "id": "SONYSTORE-2936",
                "ean": "SONYSTORE-2936",
                "primary_ean": "SONYSTORE-2936",
                "nombre": "Parlantes para Auto de 6,5 pulgadas XS-GTF1639 | XS-GTF1639/Z E",
                "marca": "Sony",
                "modelo": "XS-GTF1639",
                "tipo": "supermarket",
                "vertical": "electro",
                "categoria_normalizada": "audio_video",
                "imagen": "https://arsonyb2c.vteximg.com.br/arquivos/ids/362960/01-GENBA-XS-GTF1639-Main-SSO.jpg?v=638303852910500000",
                "offers": [
                    {
                        "supermercado": "Sony Store",
                        "precio": 89999.1,
                        "precio_lista": 189999,
                        "stock": 19,
                        "disponible": True,
                        "discount": 52,
                        "promo_label": "52% OFF",
                        "seller_name": "Sony Store",
                        "seller_id": "1",
                        "store_type": "supermarket",
                        "link": "https://store.sony.com.ar/xs-gtf1639/p"
                    }
                ]
            },
            {
                "id": "6932554402822",
                "ean": "6932554402822",
                "primary_ean": "6932554402822",
                "nombre": "Celular Xiaomi Redmi 15 8/256gb Midnight Black REDMI 15 8/256GB MIDNIGHT BLACK",
                "marca": "XIAOMI",
                "modelo": "",
                "tipo": "electro",
                "vertical": "electro",
                "categoria_normalizada": "celulares",
                "imagen": "https://naldoar.vteximg.com.br/arquivos/ids/227908/407138.jpg?v=639196513477100000",
                "offers": [
                    {
                        "supermercado": "Naldo",
                        "precio": 499999,
                        "precio_lista": 1019999,
                        "stock": 100,
                        "disponible": True,
                        "discount": 50,
                        "promo_label": "50% OFF",
                        "seller_name": "Naldo",
                        "seller_id": "1",
                        "store_type": "electro",
                        "link": "https://www.naldo.com.ar/redmi-15-8-256gb-midnight-black-407138/p"
                    }
                ]
            },
            {
                "id": "8806095658322",
                "ean": "8806095658322",
                "primary_ean": "8806095658322",
                "nombre": "Galaxy Buds3 Pro White",
                "marca": "Samsung",
                "modelo": "",
                "tipo": "electro",
                "vertical": "electro",
                "categoria_normalizada": "pequenos_electro",
                "imagen": "https://samsungar.vteximg.com.br/arquivos/ids/197129/SM-R630_009_Case-Opened_White.png?v=638629616126170000",
                "offers": [
                    {
                        "supermercado": "Frávega",
                        "precio": 245453,
                        "precio_lista": 479999,
                        "stock": 35,
                        "disponible": True,
                        "discount": 49,
                        "promo_label": "49% OFF",
                        "seller_name": "Frávega",
                        "link": "https://www.fravega.com/auriculares-audifonos-samsung-galaxy-buds3-pro-sm-r630-white-990847757/p"
                    },
                    {
                        "supermercado": "MercadoLibre",
                        "precio": 289999,
                        "precio_lista": 609999,
                        "stock": 40,
                        "disponible": True,
                        "discount": 52,
                        "promo_label": "52% OFF · FULL",
                        "seller_name": "Tienda Oficial Samsung",
                        "is_full": True,
                        "free_shipping": True,
                        "link": "https://listado.mercadolibre.com.ar/galaxy-buds3-pro"
                    },
                    {
                        "supermercado": "Samsung",
                        "precio": 299999,
                        "precio_lista": 609999,
                        "stock": 50,
                        "disponible": True,
                        "discount": 50,
                        "promo_label": "50% OFF",
                        "seller_name": "Samsung",
                        "seller_id": "1",
                        "store_type": "electro",
                        "link": "https://www.samsung.com/ar/search/?searchvalue=Galaxy%20Buds3%20Pro"
                    },
                    {
                        "supermercado": "StyleStore",
                        "precio": 440999,
                        "precio_lista": 440999,
                        "stock": 20,
                        "disponible": True,
                        "discount": 0,
                        "seller_name": "StyleStore",
                        "link": "https://www.stylestore.com.ar/auriculares-samsung-smr630nzwaaro/p"
                    },
                    {
                        "supermercado": "Cetrogar",
                        "precio": 609999,
                        "precio_lista": 609999,
                        "stock": 15,
                        "disponible": True,
                        "discount": 0,
                        "seller_name": "Cetrogar",
                        "link": "https://www.cetrogar.com.ar/auriculares-samsung-galaxy-buds3-pro-white-au3285/p"
                    }
                ]
            },
            {
                "id": "8806095658346",
                "ean": "8806095658346",
                "primary_ean": "8806095658346",
                "nombre": "Galaxy Buds3 Pro Gray",
                "marca": "Samsung",
                "modelo": "",
                "tipo": "electro",
                "vertical": "electro",
                "categoria_normalizada": "pequenos_electro",
                "imagen": "https://samsungar.vteximg.com.br/arquivos/ids/197136/SM-R630_009_Case-Opened_Silver.png?v=638629793193000000",
                "offers": [
                    {
                        "supermercado": "Samsung",
                        "precio": 299999,
                        "precio_lista": 609999,
                        "stock": 1,
                        "disponible": True,
                        "discount": 50,
                        "promo_label": "50% OFF",
                        "seller_name": "Samsung",
                        "seller_id": "1",
                        "store_type": "electro",
                        "link": "https://shop.samsung.com.ar/galaxy-buds3-pro/p"
                    }
                ]
            }
        ]
    }
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


def fetch_db_deals_sync(db_path: str = "supervmarket.db") -> Dict[str, List[Dict[str, Any]]]:
    """Recupera ofertas y descuentos reales y verificados directamente desde la base de datos canónica."""
    abs_path = os.path.abspath(db_path)
    if not os.path.exists(abs_path):
        return {}

    try:
        conn = sqlite3.connect(abs_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        base_sql = """
            SELECT 
                p.ean, pr.nombre, pr.marca, pr.modelo, pr.tipo, pr.imagen, pr.categoria_normalizada,
                p.supermercado, p.precio_venta, p.precio_lista, p.stock, p.link, p.descuento,
                p.promo_etiqueta, p.promo_min_qty, p.precio_promo_unit, p.precio_por_unidad, p.unidad_medida,
                p.seller_id, p.store_type
            FROM precios p
            JOIN productos pr ON p.ean = pr.ean
            WHERE p.stock > 0 AND p.precio_venta > 0
              AND pr.imagen IS NOT NULL AND pr.imagen != '' AND pr.imagen NOT LIKE '%placeholder%'
              AND pr.imagen NOT LIKE '%ids/676579%'
              AND pr.imagen NOT LIKE '%ids/607590%'
        """

        tier_queries = {
            "tier-70-80": base_sql + """
                AND (p.promo_etiqueta LIKE '%70%' OR p.promo_etiqueta LIKE '%80%' 
                     OR (p.promo_min_qty = 2 AND p.descuento >= 35.0 AND p.descuento <= 45.0))
                ORDER BY p.descuento DESC, p.stock DESC LIMIT 30
            """,
            "tier-clearance": base_sql + """
                AND p.descuento >= 50.0 AND p.descuento <= 75.0 AND p.store_type = 'supermarket'
                ORDER BY p.descuento DESC, p.stock DESC LIMIT 30
            """,
            "tier-50": base_sql + """
                AND (p.promo_etiqueta LIKE '%2x1%' OR (p.descuento >= 48.0 AND p.descuento <= 52.0))
                AND p.store_type = 'supermarket'
                ORDER BY p.descuento DESC, p.stock DESC LIMIT 30
            """,
            "tier-basket": base_sql + """
                AND pr.categoria_normalizada IN ('almacen', 'lacteos_frescos', 'bebidas', 'limpieza', 'perfumeria_farmacia', 'carnes_verduleria')
                AND p.descuento >= 20.0 AND p.descuento <= 45.0 AND p.store_type = 'supermarket'
                ORDER BY p.descuento DESC, p.stock DESC LIMIT 30
            """,
            "tier-mp-tech": base_sql + """
                AND pr.categoria_normalizada IN ('televisores', 'celulares', 'notebooks_tablets', 'audio_video', 'pequenos_electro')
                AND p.descuento >= 15.0 AND p.descuento <= 75.0
                ORDER BY p.descuento DESC, p.stock DESC LIMIT 30
            """,
            "tier-mp-home": base_sql + """
                AND pr.categoria_normalizada IN ('heladeras_freezers', 'lavado', 'cocina_hornos', 'climatizacion', 'muebles_racks', 'herramientas_construccion')
                AND p.descuento >= 15.0 AND p.descuento <= 75.0
                ORDER BY p.descuento DESC, p.stock DESC LIMIT 30
            """,
            "tier-mp-destacadas": base_sql + """
                AND p.supermercado IN ('Frávega', 'Musimundo', 'Naldo', 'Sony Store', 'Megatone', 'Coppel', 'Provincia Compras', 'Samsung', 'Philips', 'Whirlpool')
                AND p.descuento >= 20.0 AND p.descuento <= 75.0
                ORDER BY p.descuento DESC, p.stock DESC LIMIT 30
            """
        }

        formatted_tiers: Dict[str, List[Dict[str, Any]]] = {}
        for tid, q in tier_queries.items():
            cur.execute(q)
            rows = [dict(r) for r in cur.fetchall()]
            prod_map: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                formatted = _format_live_product(r)
                ean = formatted.get("ean") or formatted.get("id")
                if ean not in prod_map:
                    prod_map[ean] = formatted
                else:
                    existing_offers = prod_map[ean]["offers"]
                    new_offer = formatted["offers"][0]
                    if not any(o.get("supermercado") == new_offer.get("supermercado") for o in existing_offers):
                        existing_offers.append(new_offer)
                        existing_offers.sort(key=lambda o: (o.get("unit_price") or o["precio"]))
                        prod_map[ean]["best_offer"] = existing_offers[0]

            prod_list = list(prod_map.values())[:15]

            # Enriquecer cada producto con todas las ofertas de tiendas competidoras en la BD
            eans_to_enrich = [p["ean"] for p in prod_list if p.get("ean")]
            if eans_to_enrich:
                try:
                    placeholders = ",".join("?" for _ in eans_to_enrich)
                    enrich_sql = f"""
                        SELECT 
                            p.ean, p.supermercado, p.precio_venta, p.precio_lista, p.stock, p.link, p.descuento,
                            p.promo_etiqueta, p.promo_min_qty, p.precio_promo_unit, p.precio_por_unidad, p.unidad_medida,
                            p.seller_id, p.store_type
                        FROM precios p
                        WHERE p.ean IN ({placeholders}) AND p.stock > 0 AND p.precio_venta > 0
                    """
                    cur.execute(enrich_sql, eans_to_enrich)
                    for extra_row in cur.fetchall():
                        r_dict = dict(extra_row)
                        r_ean = r_dict.get("ean")
                        if r_ean and r_ean in prod_map:
                            ext_prod = _format_live_product(r_dict)
                            ext_off = ext_prod["offers"][0]
                            target_offers = prod_map[r_ean]["offers"]
                            if not any(o.get("supermercado") == ext_off.get("supermercado") for o in target_offers):
                                target_offers.append(ext_off)
                except Exception:
                    pass

            for p in prod_list:
                if p.get("offers"):
                    p["offers"].sort(key=lambda o: (o.get("unit_price") or o.get("precio", 0)))
                    p["best_offer"] = p["offers"][0]
            formatted_tiers[tid] = prod_list

        # Mapear tanto los IDs canonicos como los aliases
        alias_map = {
            "tier-clearance": "tier-60",
            "tier-basket": "tier-40",
            "tier-mp-tech": "tier-mp-electro",
            "tier-mp-home": "tier-mp-hogar",
        }
        for old_id, new_id in alias_map.items():
            if old_id in formatted_tiers:
                formatted_tiers[new_id] = formatted_tiers[old_id]

        conn.close()
        return formatted_tiers
    except Exception:
        return {}


async def get_live_discount_tiers(
    cp: Optional[str] = None,
    force: bool = False,
    vertical: Optional[str] = "all",
) -> dict:
    """Devuelve los niveles de ofertas con productos en vivo y caché inteligente."""
    cache_key = f"{cp or 'global'}:{vertical or 'all'}"
    now = time.time()

    if not force and cache_key in _DEALS_CACHE:
        cached_ts, cached_data = _DEALS_CACHE[cache_key]
        if now - cached_ts < _CACHE_TTL_SECONDS:
            return cached_data

    # 1. Recuperar ofertas verificadas desde SQLite en thread worker (o fallback a snapshot en Vercel)
    db_tiers = await asyncio.to_thread(fetch_db_deals_sync, "supervmarket.db")
    if not db_tiers:
        snapshot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verified_offers_snapshot.json")
        if os.path.exists(snapshot_path):
            try:
                with open(snapshot_path, "r", encoding="utf-8") as sf:
                    snap_data = json.load(sf)
                    for t in snap_data.get("tiers", []):
                        if t.get("id") and t.get("products"):
                            db_tiers[t["id"]] = t["products"]
                    for t in snap_data.get("marketplace_tiers", []):
                        if t.get("id") and t.get("products"):
                            db_tiers[t["id"]] = t["products"]
            except Exception:
                pass

    # 2. Concurrencia con sponsored de MercadoLibre (timeout 2s)
    live_sponsored: dict[str, dict] = {}
    try:
        async with httpx.AsyncClient(timeout=2.0, follow_redirects=True) as client:
            spons_res = await mercadolibre.fetch_live_sponsored_tiers(client)
            if isinstance(spons_res, dict):
                live_sponsored = spons_res
    except Exception:
        pass

    # Helper para fusionar productos de DB con el baseline asegurando multitienda y >= 4 productos
    def _merge_tier(db_items: list[dict], baseline_products: list[dict]) -> list[dict]:
        merged = []
        map_by_key = {}
        for it in db_items:
            key = it.get("ean") or it["nombre"].strip().lower()
            item_copy = dict(it)
            item_copy["offers"] = list(it.get("offers", []))
            map_by_key[key] = item_copy
            merged.append(item_copy)

        for it in baseline_products:
            key = it.get("ean") or it["nombre"].strip().lower()
            if key not in map_by_key:
                item_copy = dict(it)
                item_copy["offers"] = list(it.get("offers", []))
                map_by_key[key] = item_copy
                merged.append(item_copy)
            else:
                existing = map_by_key[key]
                existing_stores = {o.get("supermercado") for o in existing.get("offers", [])}
                for b_off in it.get("offers", []):
                    if b_off.get("supermercado") not in existing_stores:
                        existing.setdefault("offers", []).append(b_off)
                        existing_stores.add(b_off.get("supermercado"))
                existing["offers"].sort(key=lambda o: (o.get("unit_price") or o.get("precio", 0)))
                existing["best_offer"] = existing["offers"][0]

        valid_disc = [p for p in merged if _has_real_discount_or_promo(p)]
        if len(valid_disc) >= 4:
            return valid_disc
        return merged

    final_tiers = []
    for b_tier in BASELINE_TIERS:
        t_id = b_tier["id"]
        db_items = db_tiers.get(t_id, [])
        prods = _merge_tier(db_items, b_tier["products"])
        for p in prods:
            if "best_offer" not in p and p.get("offers"):
                p["best_offer"] = p["offers"][0]
        sponsored = live_sponsored.get(t_id) or b_tier.get("meliSponsored")

        final_tiers.append({
            **b_tier,
            "meliSponsored": sponsored,
            "products": prods,
        })

    final_marketplace_tiers = []
    for mp_t in BASELINE_MARKETPLACE_TIERS:
        t_id = mp_t["id"]
        db_items = db_tiers.get(t_id, [])
        prods = _merge_tier(db_items, mp_t["products"])
        for p in prods:
            if "best_offer" not in p and p.get("offers"):
                p["best_offer"] = p["offers"][0]
        final_marketplace_tiers.append({
            **mp_t,
            "products": prods,
        })

    # 3. Enriquecimiento dinámico con ofertas en vivo de Mercado Libre para electro y canasta
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            meli_queries = [
                ("tier-mp-electro", "Smart TV 50", "electro"),
                ("tier-mp-electro", "Motorola Moto", "electro"),
                ("tier-mp-hogar", "Lavarropas Samsung", "electro"),
                ("tier-basket", "Aceite Girasol Cocinero", "supermarket"),
                ("tier-70-80", "Skip Jabon Liquido", "supermarket"),
            ]
            async def _fetch_meli_candidate(tid: str, q: str, vert: str):
                try:
                    res = await mercadolibre.fetch_mercadolibre_live(client, q, limit=2, vertical=vert)
                    return tid, res
                except Exception:
                    return tid, []

            meli_batch = await asyncio.gather(*[_fetch_meli_candidate(t, q, v) for t, q, v in meli_queries], return_exceptions=True)
            for res_item in meli_batch:
                if isinstance(res_item, tuple) and len(res_item) == 2:
                    tid, meli_offers = res_item
                    if not meli_offers:
                        continue
                    target_tiers = final_marketplace_tiers if tid.startswith("tier-mp-") else final_tiers
                    for t in target_tiers:
                        if t["id"] == tid and t.get("products"):
                            for m_off in meli_offers:
                                m_price = float(m_off.get("precio") or m_off.get("precio_venta") or 0)
                                if m_price <= 0:
                                    continue
                                first_p = t["products"][0]
                                if not any(o.get("supermercado") == "MercadoLibre" for o in first_p.get("offers", [])):
                                    first_p.setdefault("offers", []).append({
                                        "supermercado": "MercadoLibre",
                                        "precio": m_price,
                                        "precio_lista": float(m_off.get("precio_lista") or m_price),
                                        "stock": int(m_off.get("stock") or 50),
                                        "disponible": True,
                                        "link": m_off.get("link") or m_off.get("url") or "",
                                        "discount": float(m_off.get("discount") or 0),
                                        "promo_label": m_off.get("promo_label") or "⚡ FULL",
                                        "seller_name": m_off.get("seller_name") or "Mercado Libre",
                                        "is_full": m_off.get("is_full", True),
                                        "free_shipping": m_off.get("free_shipping", True),
                                        "unit_measure": m_off.get("unit_measure") or "u",
                                        "unit_price": m_off.get("unit_price") or m_price,
                                    })
                                    first_p["offers"].sort(key=lambda o: o.get("unit_price") or o["precio"])
                                    first_p["best_offer"] = first_p["offers"][0]
    except Exception:
        pass

    is_live_fetch = bool(db_tiers) or bool(live_sponsored)

    # Selección según vertical
    if vertical == "marketplace":
        selected_tiers = final_marketplace_tiers
    elif vertical == "supermarket":
        selected_tiers = final_tiers
    else:
        selected_tiers = final_tiers

    data_payload = {
        "tiers": selected_tiers,
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
