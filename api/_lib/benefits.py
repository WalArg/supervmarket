"""Motor de Promociones por Día de la Semana, Tarjetas Propias, Bancos y Billeteras Virtuales.

Fuentes oficiales auditadas:
- Coto Digital: https://www.coto.com.ar/descuentos/index.asp
- Carrefour: https://www.carrefour.com.ar/descuentos-bancarios
- Jumbo / Disco / Vea (Cencosud): https://www.jumbo.com.ar/descuentos-del-dia?type=por-dia
- Día Online: https://diaonline.supermercadosdia.com.ar/promociones
- MásOnline: https://www.masonline.com.ar/promociones-bancarias
- Farmacity: https://www.farmacity.com/descuentos

Reglas de negocio:
1. Por defecto (sin tarjetas seleccionadas), NINGÚN descuento exclusivo de tarjeta o membresía
   rebaja el precio público del producto.
2. Si el usuario selecciona sus tarjetas/membresías/billeteras y un día de la semana (por defecto HOY),
   se calculan:
   - Qué descuentos de producto (ej. Comunidad Coto, Tarjeta Carrefour, Club DIA) se habilitan para él.
   - Qué reintegros o descuentos en caja (con su tope real en ARS o sin tope) aplican ese día sobre el carrito.
   - Cuál es el MEJOR DÍA DE LA SEMANA para hacer esa compra con las tarjetas seleccionadas.
"""
from datetime import datetime, timezone, timedelta

WEEKDAYS_ES = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
WEEKDAY_LABELS = {
    "lunes": "Lunes",
    "martes": "Martes",
    "miercoles": "Miércoles",
    "jueves": "Jueves",
    "viernes": "Viernes",
    "sabado": "Sábado",
    "domingo": "Domingo",
}

OFFICIAL_PROMO_LINKS = {
    "Carrefour": "https://www.carrefour.com.ar/descuentos-bancarios",
    "Coto": "https://www.coto.com.ar/descuentos/index.asp",
    "Jumbo": "https://www.jumbo.com.ar/descuentos-del-dia?type=por-dia",
    "Disco": "https://www.disco.com.ar/descuentos-del-dia?type=por-dia",
    "Vea": "https://www.vea.com.ar/descuentos-del-dia?type=por-dia",
    "Dia": "https://diaonline.supermercadosdia.com.ar/promociones",
    "Masonline": "https://www.masonline.com.ar/promociones-bancarias",
    "Farmacity": "https://www.farmacity.com/descuentos",
    "MercadoLibre": "https://www.mercadolibre.com.ar/supermercado",
    "MercadoPago": "https://www.mercadopago.com.ar/promociones",
}

PAYMENT_OPTIONS = [
    # Membresías y Tarjetas propias de Supermercados
    {"id": "comunidad_coto", "name": "Comunidad Coto", "category": "club", "store": "Coto"},
    {"id": "mi_carrefour", "name": "Mi Carrefour (Club)", "category": "club", "store": "Carrefour"},
    {"id": "tarjeta_carrefour", "name": "Tarjeta Mi Carrefour", "category": "club", "store": "Carrefour"},
    {"id": "club_dia", "name": "Club DIA", "category": "club", "store": "Dia"},
    {"id": "cencopay", "name": "Cencopay / Tarj. Cencosud", "category": "club", "store": "Jumbo/Disco/Vea"},
    {"id": "mas_club", "name": "Más Club (MásOnline)", "category": "club", "store": "Masonline"},
    {"id": "tu_farmacity", "name": "Tu Farmacity", "category": "club", "store": "Farmacity"},
    {"id": "meli_plus", "name": "Meli+ (Mercado Libre)", "category": "club", "store": "MercadoLibre"},

    # Billeteras Virtuales
    {"id": "modo", "name": "MODO", "category": "wallet"},
    {"id": "mercadopago", "name": "Mercado Pago", "category": "wallet"},
    {"id": "cuenta_dni", "name": "Cuenta DNI (Bapro)", "category": "wallet"},
    {"id": "bna_mas", "name": "BNA+ (Banco Nación)", "category": "wallet"},
    {"id": "personal_pay", "name": "Personal Pay", "category": "wallet"},

    # Bancos y Programas
    {"id": "bna", "name": "Banco Nación", "category": "bank"},
    {"id": "galicia", "name": "Banco Galicia", "category": "bank"},
    {"id": "santander", "name": "Santander", "category": "bank"},
    {"id": "bbva", "name": "BBVA", "category": "bank"},
    {"id": "macro", "name": "Banco Macro", "category": "bank"},
    {"id": "provincia", "name": "Banco Provincia", "category": "bank"},
    {"id": "ciudad", "name": "Banco Ciudad", "category": "bank"},
    {"id": "icbc", "name": "ICBC", "category": "bank"},
    {"id": "credicoop", "name": "Banco Credicoop", "category": "bank"},
    {"id": "anses", "name": "ANSES / Jubilados", "category": "bank"},
]

# Mapeo de qué tarjeta/club propio habilita las ofertas de producto (`requires_club == true`) de cada cadena
STORE_PRODUCT_CLUB_CARDS: dict[str, set[str]] = {
    "Carrefour": {"tarjeta_carrefour", "mi_carrefour"},
    "Coto": {"comunidad_coto"},
    "Dia": {"club_dia"},
    "Jumbo": {"cencopay"},
    "Disco": {"cencopay"},
    "Vea": {"cencopay"},
    "Masonline": {"mas_club"},
    "Farmacity": {"tu_farmacity"},
}

# Grilla estructurada de promociones semanales vigentes por supermercado, día y medio de pago
DAILY_PROMOS = [
    # --- COTO ---
    {
        "supermercado": "Coto",
        "days": ["martes", "jueves"],
        "payment_id": "comunidad_coto",
        "label": "15% Comunidad Coto (en un pago)",
        "pct": 15,
        "cap": None,
        "kind": "en_caja",
        "applies_online": True,
    },
    {
        "supermercado": "Coto",
        "days": ["lunes", "miercoles"],
        "payment_id": "anses",
        "label": "15% Jubilados y Pensionados ANSES",
        "pct": 15,
        "cap": None,
        "kind": "en_caja",
        "applies_online": False,
    },
    {
        "supermercado": "Coto",
        "days": ["miercoles"],
        "payment_id": "bna_mas",
        "label": "30% BNA+ MODO (Banco Nación)",
        "pct": 30,
        "cap": 12000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Coto",
        "days": ["miercoles"],
        "payment_id": "bna",
        "label": "30% Banco Nación c/ MODO",
        "pct": 30,
        "cap": 12000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Coto",
        "days": ["lunes"],
        "payment_id": "ciudad",
        "label": "20% Banco Ciudad c/ MODO",
        "pct": 20,
        "cap": 10000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Coto",
        "days": ["viernes"],
        "payment_id": "mercadopago",
        "label": "20% Mercado Pago (Sin tope en sucursal)",
        "pct": 20,
        "cap": None,
        "kind": "en_caja",
        "applies_online": False,
    },
    {
        "supermercado": "Coto",
        "days": ["viernes", "sabado"],
        "payment_id": "modo",
        "label": "25% MODO Bancos adheridos",
        "pct": 25,
        "cap": 10000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Coto",
        "days": ["martes"],
        "payment_id": "supervielle",
        "label": "25% Banco Supervielle / ICBC",
        "pct": 25,
        "cap": 10000,
        "kind": "reintegro",
        "applies_online": True,
    },

    # --- CARREFOUR ---
    {
        "supermercado": "Carrefour",
        "days": ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"],
        "payment_id": "tarjeta_carrefour",
        "label": "15% Tarjeta Mi Carrefour (productos selec. y días esp.)",
        "pct": 15,
        "cap": None,
        "kind": "en_caja",
        "applies_online": True,
    },
    {
        "supermercado": "Carrefour",
        "days": ["lunes", "martes", "miercoles", "jueves", "viernes"],
        "payment_id": "anses",
        "label": "10% Mi Carrefour Jubilados / ANSES",
        "pct": 10,
        "cap": 20000,
        "kind": "en_caja",
        "applies_online": False,
    },
    {
        "supermercado": "Carrefour",
        "days": ["miercoles"],
        "payment_id": "bna_mas",
        "label": "30% BNA+ MODO (Banco Nación)",
        "pct": 30,
        "cap": 12000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Carrefour",
        "days": ["miercoles"],
        "payment_id": "bna",
        "label": "30% Banco Nación c/ MODO",
        "pct": 30,
        "cap": 12000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Carrefour",
        "days": ["jueves"],
        "payment_id": "mercadopago",
        "label": "15% Mercado Pago QR (Sin tope)",
        "pct": 15,
        "cap": None,
        "kind": "en_caja",
        "applies_online": False,
    },
    {
        "supermercado": "Carrefour",
        "days": ["miercoles"],
        "payment_id": "macro",
        "label": "25% Banco Macro c/ MODO",
        "pct": 25,
        "cap": 10000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Carrefour",
        "days": ["viernes", "sabado"],
        "payment_id": "modo",
        "label": "25% MODO en Carrefour",
        "pct": 25,
        "cap": 10000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Carrefour",
        "days": ["lunes"],
        "payment_id": "ciudad",
        "label": "20% Banco Ciudad c/ MODO",
        "pct": 20,
        "cap": 10000,
        "kind": "reintegro",
        "applies_online": True,
    },

    # --- JUMBO / DISCO / VEA (Cencosud) ---
    *[
        {
            "supermercado": st,
            "days": ["martes"],
            "payment_id": "cencopay",
            "label": "25% Cencopay / Tarjeta Cencosud",
            "pct": 25,
            "cap": 10000,
            "kind": "en_caja",
            "applies_online": True,
        }
        for st in ("Jumbo", "Disco", "Vea")
    ],
    *[
        {
            "supermercado": st,
            "days": ["miercoles"],
            "payment_id": "bna_mas",
            "label": "30% BNA+ MODO (Banco Nación)",
            "pct": 30,
            "cap": 12000,
            "kind": "reintegro",
            "applies_online": True,
        }
        for st in ("Jumbo", "Disco", "Vea")
    ],
    *[
        {
            "supermercado": st,
            "days": ["miercoles"],
            "payment_id": "bna",
            "label": "30% Banco Nación c/ MODO",
            "pct": 30,
            "cap": 12000,
            "kind": "reintegro",
            "applies_online": True,
        }
        for st in ("Jumbo", "Disco", "Vea")
    ],
    *[
        {
            "supermercado": st,
            "days": ["jueves"],
            "payment_id": "galicia",
            "label": "25% Banco Galicia c/ MODO",
            "pct": 25,
            "cap": 15000,
            "kind": "reintegro",
            "applies_online": True,
        }
        for st in ("Jumbo", "Disco", "Vea")
    ],
    *[
        {
            "supermercado": st,
            "days": ["viernes"],
            "payment_id": "santander",
            "label": "25% Santander c/ MODO",
            "pct": 25,
            "cap": 15000,
            "kind": "reintegro",
            "applies_online": True,
        }
        for st in ("Jumbo", "Disco", "Vea")
    ],
    *[
        {
            "supermercado": st,
            "days": ["martes", "miercoles"],
            "payment_id": "cuenta_dni",
            "label": "20% Cuenta DNI (Banco Provincia)",
            "pct": 20,
            "cap": 8000,
            "kind": "reintegro",
            "applies_online": False,
        }
        for st in ("Jumbo", "Disco", "Vea")
    ],
    *[
        {
            "supermercado": st,
            "days": ["viernes", "sabado"],
            "payment_id": "modo",
            "label": "25% MODO Bancos adheridos",
            "pct": 25,
            "cap": 10000,
            "kind": "reintegro",
            "applies_online": True,
        }
        for st in ("Jumbo", "Disco", "Vea")
    ],

    # --- DIA ---
    {
        "supermercado": "Dia",
        "days": ["martes", "jueves"],
        "payment_id": "club_dia",
        "label": "20% Club DIA en productos seleccionados",
        "pct": 20,
        "cap": None,
        "kind": "en_caja",
        "applies_online": True,
    },
    {
        "supermercado": "Dia",
        "days": ["miercoles"],
        "payment_id": "mercadopago",
        "label": "15% Mercado Pago en DIA",
        "pct": 15,
        "cap": 10000,
        "kind": "en_caja",
        "applies_online": True,
    },
    {
        "supermercado": "Dia",
        "days": ["miercoles"],
        "payment_id": "bna_mas",
        "label": "30% BNA+ MODO (Banco Nación)",
        "pct": 30,
        "cap": 12000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Dia",
        "days": ["miercoles"],
        "payment_id": "bna",
        "label": "30% Banco Nación c/ MODO",
        "pct": 30,
        "cap": 12000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Dia",
        "days": ["viernes", "sabado"],
        "payment_id": "modo",
        "label": "25% MODO en DIA Online y tiendas",
        "pct": 25,
        "cap": 10000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Dia",
        "days": ["jueves"],
        "payment_id": "galicia",
        "label": "25% Banco Galicia c/ MODO",
        "pct": 25,
        "cap": 15000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Dia",
        "days": ["sabado"],
        "payment_id": "santander",
        "label": "25% Santander Women / MODO",
        "pct": 25,
        "cap": 12000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Dia",
        "days": ["lunes"],
        "payment_id": "personal_pay",
        "label": "25% Personal Pay en DIA",
        "pct": 25,
        "cap": 8000,
        "kind": "reintegro",
        "applies_online": True,
    },

    # --- MASONLINE ---
    {
        "supermercado": "Masonline",
        "days": ["miercoles"],
        "payment_id": "bna_mas",
        "label": "30% BNA+ MODO (Banco Nación)",
        "pct": 30,
        "cap": 12000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Masonline",
        "days": ["miercoles"],
        "payment_id": "bna",
        "label": "30% Banco Nación c/ MODO",
        "pct": 30,
        "cap": 12000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Masonline",
        "days": ["jueves"],
        "payment_id": "galicia",
        "label": "25% Banco Galicia c/ MODO",
        "pct": 25,
        "cap": 15000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Masonline",
        "days": ["viernes", "sabado"],
        "payment_id": "modo",
        "label": "25% MODO Bancos adheridos",
        "pct": 25,
        "cap": 10000,
        "kind": "reintegro",
        "applies_online": True,
    },
    {
        "supermercado": "Masonline",
        "days": ["martes"],
        "payment_id": "bbva",
        "label": "25% BBVA c/ MODO",
        "pct": 25,
        "cap": 12000,
        "kind": "reintegro",
        "applies_online": True,
    },
]


def today_weekday_ar() -> str:
    """Devuelve el día de la semana actual en Argentina (UTC-3)."""
    ar_tz = timezone(timedelta(hours=-3))
    idx = datetime.now(ar_tz).weekday()
    return WEEKDAYS_ES[idx]


def user_has_store_club(store: str, selected_cards: set[str], include_clubs_legacy: bool = False) -> bool:
    """Indica si el usuario posee la tarjeta/membresía que habilita precios exclusivos de producto en `store`."""
    if include_clubs_legacy:
        return True
    if not selected_cards:
        return False
    needed = STORE_PRODUCT_CLUB_CARDS.get(store, set())
    return bool(needed and not needed.isdisjoint(selected_cards))


def best_cart_benefit_for_store(
    store: str,
    subtotal: float,
    day: str,
    selected_cards: set[str],
) -> dict | None:
    """Calcula el mejor descuento/reintegro de banco o billetera aplicable al `subtotal` de `store` en `day`."""
    if subtotal <= 0 or not selected_cards:
        return None
    d_norm = (day or today_weekday_ar()).lower().strip()
    best = None
    for promo in DAILY_PROMOS:
        if promo["supermercado"] != store:
            continue
        if promo["payment_id"] not in selected_cards:
            continue
        if d_norm not in promo["days"]:
            continue
        # No duplicar descuentos por producto de tarjeta_carrefour / club_dia sobre todo el carrito si son solo en selec.
        if promo["payment_id"] in ("tarjeta_carrefour", "club_dia"):
            continue
        raw_saving = round(subtotal * (promo["pct"] / 100.0), 2)
        saving = min(raw_saving, float(promo["cap"])) if promo.get("cap") else raw_saving
        cand = {
            "payment_id": promo["payment_id"],
            "label": promo["label"],
            "pct": promo["pct"],
            "cap": promo["cap"],
            "kind": promo["kind"],
            "saving": round(saving, 2),
            "day": d_norm,
            "day_label": WEEKDAY_LABELS.get(d_norm, d_norm.capitalize()),
            "official_url": OFFICIAL_PROMO_LINKS.get(store, ""),
        }
        if best is None or cand["saving"] > best["saving"]:
            best = cand
    return best


def get_benefits_catalog() -> dict:
    today = today_weekday_ar()
    return {
        "today": today,
        "today_label": WEEKDAY_LABELS.get(today, today.capitalize()),
        "weekdays": [{"id": d, "label": WEEKDAY_LABELS[d]} for d in WEEKDAYS_ES],
        "payment_options": PAYMENT_OPTIONS,
        "official_links": OFFICIAL_PROMO_LINKS,
        "daily_promos": [
            {
                **p,
                "official_url": (
                    OFFICIAL_PROMO_LINKS.get(p["supermercado"])
                    or (OFFICIAL_PROMO_LINKS.get("MercadoPago", "") if "mercadopago" in p["payment_id"] else "")
                ),
            }
            for p in DAILY_PROMOS
        ],
    }
