"""Configuración de tiendas: dominios VTEX, canales de venta (sc), soporte de carrito y mínimos."""

# Tiendas VTEX -> dominio público (para guest-link y simulación de carrito).
VTEX_DOMAINS = {
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
}

# Canal de venta (Sales Channel `sc`) real verificado en los payloads de cada tienda VTEX.
# Crítico: Jumbo=32, Disco=33, Vea=34, Farmacity=4. Sin el sc correcto, VTEX devuelve ORD027.
VTEX_SALES_CHANNELS = {
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
}

# Coto NO es VTEX -> es "solo comparar" (abre los productos pero no tiene guest-link VTEX).
COMPARE_ONLY = {"Coto"}

# Umbrales de envío gratis (ARS).
FREE_SHIPPING = {
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
    "MercadoLibre": 33000,
    "TheFoodMarket": 28000,
    "LaBarraCCU": 25000,
}

# Costo estimado de envío a domicilio (ARS) cuando no se alcanza el umbral de envío gratis.
SHIPPING_COST = {
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
    "MercadoLibre": 4900,
    "TheFoodMarket": 4500,
    "LaBarraCCU": 4500,
}


def supports_cart(store: str) -> bool:
    return store in VTEX_DOMAINS


def sales_channel(store: str) -> str:
    return VTEX_SALES_CHANNELS.get(store, "1")


def free_shipping_threshold(store: str) -> int:
    return FREE_SHIPPING.get(store, 0)


def estimated_shipping_cost(store: str) -> float:
    return float(SHIPPING_COST.get(store, 4900))
