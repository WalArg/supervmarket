"""Configuración de tiendas: dominios VTEX, canales de venta (sc), soporte de carrito y mínimos."""

import os
import unicodedata
import urllib.parse
from typing import TypedDict, Literal, Optional

StorePlatform = Literal["vtex", "shopify", "custom"]
StoreVertical = Literal["supermarket", "marketplace", "electro", "specialty", "pharmacy"]


class StoreMeta(TypedDict):
    id: str
    nombre: str
    dominio: str
    plataforma: StorePlatform
    sales_channel: int
    vertical: StoreVertical
    is_marketplace: bool
    supports_cart: bool
    color: str


# Registro canónico unificado de tiendas (Supermercados, Marketplaces, Electro, Tiendas Oficiales, Especializadas)
STORE_REGISTRY: dict[str, StoreMeta] = {
    # --- Supermercados tradicionales ---
    "Jumbo": {
        "id": "jumbo",
        "nombre": "Jumbo",
        "dominio": "https://www.jumbo.com.ar",
        "plataforma": "vtex",
        "sales_channel": 32,
        "vertical": "supermarket",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#16a34a",
    },
    "Disco": {
        "id": "disco",
        "nombre": "Disco",
        "dominio": "https://www.disco.com.ar",
        "plataforma": "vtex",
        "sales_channel": 33,
        "vertical": "supermarket",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#db2777",
    },
    "Vea": {
        "id": "vea",
        "nombre": "Vea",
        "dominio": "https://www.vea.com.ar",
        "plataforma": "vtex",
        "sales_channel": 34,
        "vertical": "supermarket",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#15803d",
    },
    "Carrefour": {
        "id": "carrefour",
        "nombre": "Carrefour",
        "dominio": "https://www.carrefour.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "supermarket",
        "is_marketplace": True,
        "supports_cart": True,
        "color": "#1d4ed8",
    },
    "Dia": {
        "id": "dia",
        "nombre": "Día",
        "dominio": "https://diaonline.supermercadosdia.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "supermarket",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#e11d48",
    },
    "Masonline": {
        "id": "masonline",
        "nombre": "Más Online",
        "dominio": "https://www.masonline.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "supermarket",
        "is_marketplace": True,
        "supports_cart": True,
        "color": "#0d9488",
    },
    "Coto": {
        "id": "coto",
        "nombre": "Coto",
        "dominio": "https://www.cotodigital3.com.ar",
        "plataforma": "custom",
        "sales_channel": 1,
        "vertical": "supermarket",
        "is_marketplace": False,
        "supports_cart": False,
        "color": "#dc2626",
    },
    "Josimar": {
        "id": "josimar",
        "nombre": "Josimar",
        "dominio": "https://www.josimar.com.ar",
        "plataforma": "vtex",
        "sales_channel": 5,
        "vertical": "supermarket",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#007a3d",
    },
    "Toledo": {
        "id": "toledo",
        "nombre": "Toledo Digital",
        "dominio": "https://www.toledodigital.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "supermarket",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#005ba4",
    },
    "Cordiez": {
        "id": "cordiez",
        "nombre": "Cordiez",
        "dominio": "https://www.cordiez.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "supermarket",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#ed1c24",
    },
    "TheFoodMarket": {
        "id": "thefoodmarket",
        "nombre": "Food Market",
        "dominio": "https://www.thefoodmarket.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "supermarket",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#d97706",
    },
    "LaBarata": {
        "id": "labarata",
        "nombre": "La Barata",
        "dominio": "https://labarata.ar",
        "plataforma": "custom",
        "sales_channel": 1,
        "vertical": "supermarket",
        "is_marketplace": False,
        "supports_cart": False,
        "color": "#16a34a",
    },
    "ArcorEnCasa": {
        "id": "arcorencasa",
        "nombre": "Arcor en Casa",
        "dominio": "https://arcorencasa.com",
        "plataforma": "custom",
        "sales_channel": 1,
        "vertical": "supermarket",
        "is_marketplace": False,
        "supports_cart": False,
        "color": "#0284c7",
    },

    # --- Marketplaces Generales ---
    "Provincia Compras": {
        "id": "provinciacompras",
        "nombre": "Provincia Compras",
        "dominio": "https://www.provinciacompras.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "marketplace",
        "is_marketplace": True,
        "supports_cart": True,
        "color": "#008859",
    },
    "On City": {
        "id": "oncity",
        "nombre": "On City",
        "dominio": "https://www.oncity.com",
        "plataforma": "vtex",
        "sales_channel": 2,
        "vertical": "marketplace",
        "is_marketplace": True,
        "supports_cart": True,
        "color": "#001489",
    },
    "MercadoLibre": {
        "id": "mercadolibre",
        "nombre": "Mercado Libre",
        "dominio": "https://www.mercadolibre.com.ar",
        "plataforma": "custom",
        "sales_channel": 1,
        "vertical": "marketplace",
        "is_marketplace": True,
        "supports_cart": False,
        "color": "#eab308",
    },

    # --- Cadenas de Electro y Tecnología ---
    "Fravega": {
        "id": "fravega",
        "nombre": "Frávega",
        "dominio": "https://www.fravega.com",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "electro",
        "is_marketplace": True,
        "supports_cart": True,
        "color": "#4a154b",
    },
    "Cetrogar": {
        "id": "cetrogar",
        "nombre": "Cetrogar",
        "dominio": "https://www.cetrogar.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "electro",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#004b93",
    },
    "Naldo": {
        "id": "naldo",
        "nombre": "Naldo",
        "dominio": "https://www.naldo.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "electro",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#e30613",
    },
    "Pardo": {
        "id": "pardo",
        "nombre": "Pardo",
        "dominio": "https://www.pardo.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "electro",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#e20613",
    },
    "Coppel": {
        "id": "coppel",
        "nombre": "Coppel",
        "dominio": "https://www.coppel.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "electro",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#ffd000",
    },
    "Musimundo": {
        "id": "musimundo",
        "nombre": "Musimundo",
        "dominio": "https://www.musimundo.com",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "electro",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#e30613",
    },

    # --- Tiendas Oficiales de Marca ---
    "Samsung": {
        "id": "samsung",
        "nombre": "Samsung",
        "dominio": "https://shop.samsung.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "electro",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#1249ff",
    },
    "Philips": {
        "id": "philips",
        "nombre": "Philips",
        "dominio": "https://www.tienda.philips.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "electro",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#0b5ed7",
    },
    "Whirlpool": {
        "id": "whirlpool",
        "nombre": "Whirlpool",
        "dominio": "https://www.whirlpool.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "electro",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#f0b400",
    },
    "Moulinex": {
        "id": "moulinex",
        "nombre": "Moulinex / Tefal",
        "dominio": "https://tienda.moulinex.com.ar",
        "plataforma": "vtex",
        "sales_channel": 3,
        "vertical": "electro",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#da291c",
    },
    "Sony": {
        "id": "sony",
        "nombre": "Sony Store",
        "dominio": "https://store.sony.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "electro",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#000000",
    },
    "Oster": {
        "id": "oster",
        "nombre": "Oster",
        "dominio": "https://www.osterargentina.com",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "electro",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#b22222",
    },

    # --- Hogar, Farmacia, Perfumería, Mascotas y Especialidad ---
    "Easy": {
        "id": "easy",
        "nombre": "Easy",
        "dominio": "https://www.easy.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "specialty",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#d6001c",
    },
    "Pigmento": {
        "id": "pigmento",
        "nombre": "Perfumerías Pigmento",
        "dominio": "https://www.perfumeriaspigmento.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "pharmacy",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#e5007e",
    },
    "Farmacity": {
        "id": "farmacity",
        "nombre": "Farmacity",
        "dominio": "https://www.farmacity.com",
        "plataforma": "vtex",
        "sales_channel": 4,
        "vertical": "pharmacy",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#f97316",
    },
    "Simplicity": {
        "id": "simplicity",
        "nombre": "Simplicity",
        "dominio": "https://www.simplicity.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "pharmacy",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#c026d3",
    },
    "Farmaonline": {
        "id": "farmaonline",
        "nombre": "Farmaonline",
        "dominio": "https://www.farmaonline.com",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "pharmacy",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#0891b2",
    },
    "Farmaplus": {
        "id": "farmaplus",
        "nombre": "Farmaplus",
        "dominio": "https://www.farmaplus.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "pharmacy",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#0284c7",
    },
    "Puppis": {
        "id": "puppis",
        "nombre": "Puppis",
        "dominio": "https://www.puppis.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "specialty",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#ff6b00",
    },
    "Catycan": {
        "id": "catycan",
        "nombre": "Catycan",
        "dominio": "https://www.catycan.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "specialty",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#ff5500",
    },
    "Natural Life": {
        "id": "naturallife",
        "nombre": "Natural Life",
        "dominio": "https://www.natural-life.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "specialty",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#16a34a",
    },
    "StyleStore": {
        "id": "stylestore",
        "nombre": "StyleStore",
        "dominio": "https://www.stylestore.com.ar",
        "plataforma": "vtex",
        "sales_channel": 1,
        "vertical": "specialty",
        "is_marketplace": False,
        "supports_cart": True,
        "color": "#1a1a1a",
    },
    "Bodegas Bianchi": {
        "id": "bodegasbianchi",
        "nombre": "Bodegas Bianchi",
        "dominio": "https://www.bodegasbianchi.com.ar",
        "plataforma": "shopify",
        "sales_channel": 1,
        "vertical": "specialty",
        "is_marketplace": False,
        "supports_cart": False,
        "color": "#581845",
    },
    "LaBarraCCU": {
        "id": "labarraccu",
        "nombre": "La Barra CCU",
        "dominio": "https://labarraccu.com.ar",
        "plataforma": "shopify",
        "sales_channel": 1,
        "vertical": "specialty",
        "is_marketplace": False,
        "supports_cart": False,
        "color": "#475569",
    },
    "TonelPrivado": {
        "id": "tonelprivado",
        "nombre": "Tonel Privado",
        "dominio": "https://www.tonelprivado.com",
        "plataforma": "custom",
        "sales_channel": 1,
        "vertical": "specialty",
        "is_marketplace": False,
        "supports_cart": False,
        "color": "#7c2d12",
    },
    "DePastura": {
        "id": "depastura",
        "nombre": "De Pastura",
        "dominio": "https://tienda.depastura.com.ar",
        "plataforma": "custom",
        "sales_channel": 1,
        "vertical": "specialty",
        "is_marketplace": False,
        "supports_cart": False,
        "color": "#b91c1c",
    },
}

# Tiendas VTEX -> dominio público (para guest-link y simulación de carrito).
# Mapea claves canónicas y alias comunes para evitar KeyErrors.
VTEX_DOMAINS: dict[str, str] = {
    # Supermercados & farmacias clásicas
    "Jumbo": "https://www.jumbo.com.ar",
    "Disco": "https://www.disco.com.ar",
    "Vea": "https://www.vea.com.ar",
    "Carrefour": "https://www.carrefour.com.ar",
    "Dia": "https://diaonline.supermercadosdia.com.ar",
    "Masonline": "https://www.masonline.com.ar",
    "Farmacity": "https://www.farmacity.com",
    "Simplicity": "https://www.simplicity.com.ar",
    "Farmaonline": "https://www.farmaonline.com",
    "Farmaplus": "https://www.farmaplus.com.ar",
    "TheFoodMarket": "https://www.thefoodmarket.com.ar",
    "Josimar": "https://www.josimar.com.ar",
    "Toledo": "https://www.toledodigital.com.ar",
    "Cordiez": "https://www.cordiez.com.ar",

    # Marketplaces
    "Provincia Compras": "https://www.provinciacompras.com.ar",
    "On City": "https://www.oncity.com",

    # Electro y Tecnología
    "Fravega": "https://www.fravega.com",
    "Cetrogar": "https://www.cetrogar.com.ar",
    "Naldo": "https://www.naldo.com.ar",
    "Pardo": "https://www.pardo.com.ar",
    "Coppel": "https://www.coppel.com.ar",
    "Musimundo": "https://www.musimundo.com",

    # Tiendas Oficiales
    "Samsung": "https://shop.samsung.com.ar",
    "Philips": "https://www.tienda.philips.com.ar",
    "Whirlpool": "https://www.whirlpool.com.ar",
    "Moulinex": "https://tienda.moulinex.com.ar",
    "Sony": "https://store.sony.com.ar",
    "Oster": "https://www.osterargentina.com",

    # Hogar, Perfumería, Mascotas, Niche
    "Easy": "https://www.easy.com.ar",
    "Pigmento": "https://www.perfumeriaspigmento.com.ar",
    "Puppis": "https://www.puppis.com.ar",
    "StyleStore": "https://www.stylestore.com.ar",
    "Catycan": "https://www.catycan.com.ar",
    "Natural Life": "https://www.natural-life.com.ar",
    "NaturalLife": "https://www.natural-life.com.ar",

    # Alias comunes (espaciado y acentos)
    "ProvinciaCompras": "https://www.provinciacompras.com.ar",
    "OnCity": "https://www.oncity.com",
    "Frávega": "https://www.fravega.com",
    "Moulinex / Tefal": "https://tienda.moulinex.com.ar",
    "Moulinex/Tefal": "https://tienda.moulinex.com.ar",
    "Sony Store": "https://store.sony.com.ar",
    "SonyStore": "https://store.sony.com.ar",
    "Perfumerías Pigmento": "https://www.perfumeriaspigmento.com.ar",
    "Perfumerias Pigmento": "https://www.perfumeriaspigmento.com.ar",
    "Toledo Digital": "https://www.toledodigital.com.ar",
    "ToledoDigital": "https://www.toledodigital.com.ar",
    "Food Market": "https://www.thefoodmarket.com.ar",
}

# Canal de venta (Sales Channel `sc`) real verificado en los payloads de cada tienda VTEX.
# Crítico: Jumbo=32, Disco=33, Vea=34, Farmacity=4, On City=2, Moulinex=3, Josimar=5.
VTEX_SALES_CHANNELS: dict[str, str] = {
    "Jumbo": "32",
    "Disco": "33",
    "Vea": "34",
    "Carrefour": "1",
    "Dia": "1",
    "Masonline": "1",
    "Farmacity": "4",
    "Simplicity": "1",
    "Farmaonline": "1",
    "Farmaplus": "1",
    "TheFoodMarket": "1",
    "Josimar": "5",
    "Toledo": "1",
    "Cordiez": "1",
    "Provincia Compras": "1",
    "ProvinciaCompras": "1",
    "On City": "2",
    "OnCity": "2",
    "Fravega": "1",
    "Frávega": "1",
    "Cetrogar": "1",
    "Naldo": "1",
    "Pardo": "1",
    "Coppel": "1",
    "Musimundo": "1",
    "Samsung": "1",
    "Philips": "1",
    "Whirlpool": "1",
    "Moulinex": "3",
    "Moulinex / Tefal": "3",
    "Moulinex/Tefal": "3",
    "Sony": "1",
    "Sony Store": "1",
    "SonyStore": "1",
    "Oster": "1",
    "Easy": "1",
    "Pigmento": "1",
    "Perfumerías Pigmento": "1",
    "Perfumerias Pigmento": "1",
    "Puppis": "1",
    "StyleStore": "1",
    "Catycan": "1",
    "Natural Life": "1",
    "NaturalLife": "1",
    "Toledo Digital": "1",
    "ToledoDigital": "1",
}

# Tiendas sin carrito automatizado VTEX ("solo comparar" o checkout externo)
COMPARE_ONLY = {
    "Coto",
    "MercadoLibre",
    "LaBarraCCU",
    "Bodegas Bianchi",
    "BodegasBianchi",
    "LaBarata",
    "TonelPrivado",
    "DePastura",
    "ArcorEnCasa",
}

# Umbrales de envío gratis (ARS)
FREE_SHIPPING: dict[str, int] = {
    "Jumbo": 35000,
    "Disco": 35000,
    "Vea": 30000,
    "Carrefour": 30000,
    "Dia": 25000,
    "Masonline": 30000,
    "Coto": 30000,
    "Farmacity": 25000,
    "Simplicity": 25000,
    "Farmaonline": 25000,
    "Farmaplus": 25000,
    "MercadoLibre": 65000,
    "TheFoodMarket": 28000,
    "LaBarraCCU": 25000,
    "LaBarata": 35000,
    "TonelPrivado": 40000,
    "DePastura": 45000,
    "ArcorEnCasa": 35000,
    "Provincia Compras": 0,
    "On City": 50000,
    "Fravega": 50000,
    "Cetrogar": 50000,
    "Naldo": 50000,
    "Pardo": 50000,
    "Coppel": 50000,
    "Samsung": 50000,
    "Philips": 45000,
    "Whirlpool": 60000,
    "Moulinex": 40000,
    "Sony": 50000,
    "Easy": 45000,
    "Pigmento": 30000,
    "Puppis": 30000,
    "Josimar": 35000,
    "Toledo": 35000,
    "Cordiez": 35000,
    "Bodegas Bianchi": 35000,
    "Musimundo": 50000,
    "Oster": 45000,
    "StyleStore": 50000,
    "Catycan": 30000,
    "Natural Life": 30000,
}

# Costo estimado de envío a domicilio (ARS) cuando no se alcanza el umbral
SHIPPING_COST: dict[str, float] = {
    "Jumbo": 5500,
    "Disco": 5500,
    "Vea": 4900,
    "Carrefour": 4800,
    "Dia": 4599,
    "Masonline": 4900,
    "Coto": 5200,
    "Farmacity": 3900,
    "Simplicity": 3900,
    "Farmaonline": 3900,
    "Farmaplus": 3900,
    "MercadoLibre": 4999,
    "TheFoodMarket": 4500,
    "LaBarraCCU": 4500,
    "LaBarata": 4500,
    "TonelPrivado": 4900,
    "DePastura": 5200,
    "ArcorEnCasa": 4500,
    "Provincia Compras": 5500,
    "On City": 5500,
    "Fravega": 5500,
    "Cetrogar": 5500,
    "Naldo": 5500,
    "Pardo": 5500,
    "Coppel": 5500,
    "Samsung": 4900,
    "Philips": 4900,
    "Whirlpool": 6500,
    "Moulinex": 4900,
    "Sony": 4900,
    "Easy": 5500,
    "Pigmento": 4200,
    "Puppis": 4500,
    "Josimar": 4900,
    "Toledo": 4900,
    "Cordiez": 4900,
    "Bodegas Bianchi": 4900,
    "Musimundo": 5500,
    "Oster": 4900,
    "StyleStore": 4900,
    "Catycan": 4500,
    "Natural Life": 4500,
}

MELI_AFFILIATE_TOOL = os.getenv("MELI_AFFILIATE_TOOL", "43872651")
DEFAULT_AFFILIATE_SOURCE = os.getenv("AFFILIATE_UTM_SOURCE", "supervmarket")
DEFAULT_AFFILIATE_MEDIUM = os.getenv("AFFILIATE_UTM_MEDIUM", "affiliate")
VTEX_AFILIADO_ID = os.getenv("VTEX_AFILIADO_ID", "supervmarket")

RETAILER_AFFILIATE_CONFIG = {
    "Carrefour": {
        "network": "direct",
        "cpa_rate": 0.025,
        "cookie_days": 30,
        "campaign": "smart_cart_carrefour",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_carrefour",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Dia": {
        "network": "soicos",
        "cpa_rate": 0.030,
        "cookie_days": 30,
        "campaign": "smart_cart_dia",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_dia",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Jumbo": {
        "network": "cencosud_direct",
        "cpa_rate": 0.020,
        "cookie_days": 15,
        "campaign": "smart_cart_jumbo",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_jumbo",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Disco": {
        "network": "cencosud_direct",
        "cpa_rate": 0.020,
        "cookie_days": 15,
        "campaign": "smart_cart_disco",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_disco",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Vea": {
        "network": "cencosud_direct",
        "cpa_rate": 0.020,
        "cookie_days": 15,
        "campaign": "smart_cart_vea",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_vea",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Masonline": {
        "network": "direct",
        "cpa_rate": 0.025,
        "cookie_days": 30,
        "campaign": "smart_cart_masonline",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_masonline",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Farmacity": {
        "network": "direct",
        "cpa_rate": 0.035,
        "cookie_days": 30,
        "campaign": "smart_cart_farmacity",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_farmacity",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Simplicity": {
        "network": "direct",
        "cpa_rate": 0.035,
        "cookie_days": 30,
        "campaign": "smart_cart_simplicity",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_simplicity",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Farmaonline": {
        "network": "direct",
        "cpa_rate": 0.030,
        "cookie_days": 30,
        "campaign": "smart_cart_farmaonline",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_farmaonline",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Farmaplus": {
        "network": "direct",
        "cpa_rate": 0.030,
        "cookie_days": 30,
        "campaign": "smart_cart_farmaplus",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_farmaplus",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "MercadoLibre": {
        "network": "meli_partners",
        "cpa_rate": 0.040,
        "cookie_days": 1,
        "campaign": "meli_smart_cart",
        "params": {
            "matt_tool": MELI_AFFILIATE_TOOL,
            "matt_word": "sv_smart_cart",
            "matt_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "meli_smart_cart",
        },
    },
    "Coto": {
        "network": "coto_direct",
        "cpa_rate": 0.015,
        "cookie_days": 7,
        "campaign": "coto_smart_cart",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "coto_smart_cart",
            "utm_term": "copiar_lista",
        },
    },
}


def _strip_accents(text: str) -> str:
    if not text:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", str(text))
        if unicodedata.category(c) != "Mn"
    )


def get_store_meta(store: str) -> Optional[StoreMeta]:
    """Obtiene los metadatos de la tienda realizando resolución exacta o insensible a mayúsculas/espacios/acentos."""
    if not store:
        return None
    if store in STORE_REGISTRY:
        return STORE_REGISTRY[store]
    cleaned = _strip_accents(store).strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    for k, v in STORE_REGISTRY.items():
        k_clean = _strip_accents(k).strip().lower().replace(" ", "").replace("_", "").replace("-", "")
        v_id_clean = _strip_accents(v["id"]).strip().lower().replace(" ", "").replace("_", "").replace("-", "")
        v_nom_clean = _strip_accents(v.get("nombre", "")).strip().lower().replace(" ", "").replace("_", "").replace("-", "")
        if cleaned in (k_clean, v_id_clean, v_nom_clean):
            return v
    return None


def supports_cart(store: str) -> bool:
    meta = get_store_meta(store)
    if meta is not None:
        return bool(meta.get("supports_cart", False))
    return store in VTEX_DOMAINS


def sales_channel(store: str) -> str:
    meta = get_store_meta(store)
    if meta is not None:
        return str(meta.get("sales_channel", 1))
    return VTEX_SALES_CHANNELS.get(store, "1")


def is_marketplace(store: str) -> bool:
    meta = get_store_meta(store)
    return bool(meta.get("is_marketplace", False)) if meta else False


def store_vertical(store: str) -> str:
    meta = get_store_meta(store)
    return str(meta.get("vertical", "supermarket")) if meta else "supermarket"


def free_shipping_threshold(store: str) -> int:
    return FREE_SHIPPING.get(store, 0)


def estimated_shipping_cost(store: str) -> float:
    return float(SHIPPING_COST.get(store, 4900))


def decorate_store_url(
    url: str | None,
    store_key: str,
    link_type: str = "checkout",
    click_id: str | None = None,
    extra_params: dict | None = None,
) -> str:
    """Decora URLs salientes hacia tiendas o Mercado Libre con parámetros oficiales de afiliación y UTM.

    Garantiza:
    1. Preservación estricta del orden y repetición de tuplas query de VTEX (sku=..&qty=..&seller=..&sc=..).
    2. Idempotencia: si los parámetros ya están presentes, no los duplica.
    3. Preservación de fragmentos hash (#).
    4. Cero perturbación del catálogo oficial ni disponibilidad de ítems.
    """
    if not url:
        return ""
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        return clean_url

    parsed = urllib.parse.urlsplit(clean_url)
    existing_qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    normalized_store = (store_key or "").strip()
    store_lower = normalized_store.lower().replace(" ", "").replace("_", "")
    is_meli = "mercadolibre" in store_lower or "mercadolibre.com" in parsed.netloc
    is_coto = "coto" in store_lower or "cotodigital" in parsed.netloc

    injected: dict[str, str] = {}
    matched_config = RETAILER_AFFILIATE_CONFIG.get(normalized_store)

    if not matched_config:
        for k, v in RETAILER_AFFILIATE_CONFIG.items():
            if k.lower() == normalized_store.lower():
                matched_config = v
                break

    if is_meli:
        sub_word = "sv_item" if link_type == "item" else "sv_smart_cart"
        injected["matt_tool"] = MELI_AFFILIATE_TOOL
        injected["matt_word"] = sub_word
        injected["matt_source"] = DEFAULT_AFFILIATE_SOURCE
        injected["utm_source"] = DEFAULT_AFFILIATE_SOURCE
        injected["utm_medium"] = DEFAULT_AFFILIATE_MEDIUM
        injected["utm_campaign"] = "meli_item" if link_type == "item" else "meli_smart_cart"
    elif is_coto:
        injected["utm_source"] = DEFAULT_AFFILIATE_SOURCE
        injected["utm_medium"] = DEFAULT_AFFILIATE_MEDIUM
        injected["utm_campaign"] = "coto_item" if link_type == "item" else "coto_smart_cart"
        injected["utm_term"] = "item" if link_type == "item" else "copiar_lista"
    elif matched_config and "params" in matched_config:
        injected = dict(matched_config["params"])
        if link_type == "item":
            store_slug = normalized_store.lower()
            injected["utm_campaign"] = f"item_{store_slug}"
            injected["utm_term"] = "item"
    else:
        store_slug = normalized_store.lower() if normalized_store else "store"
        injected["utm_source"] = DEFAULT_AFFILIATE_SOURCE
        injected["utm_medium"] = DEFAULT_AFFILIATE_MEDIUM
        injected["utm_campaign"] = f"smart_cart_{store_slug}" if link_type != "item" else f"item_{store_slug}"
        injected["utm_term"] = "optimizado" if link_type != "item" else "item"
        if VTEX_AFILIADO_ID:
            injected["afiliado_id"] = VTEX_AFILIADO_ID

    if click_id:
        injected["subid"] = click_id

    if extra_params:
        for k, v in extra_params.items():
            if v is not None:
                injected[k] = str(v)

    params_to_add = {k: v for k, v in injected.items() if k not in existing_qs}
    if not params_to_add:
        return clean_url

    encoded_add = urllib.parse.urlencode(params_to_add)
    new_query = f"{parsed.query}&{encoded_add}" if parsed.query else encoded_add
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))
