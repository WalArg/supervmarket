"""Normalización inteligente de unidades (kg, l, un) y categorías para supermercados argentinos.

Reglas de negocio:
1. Productos que se compran y comparan **por unidad (`un`)** aunque informen gramos por pieza:
   - Jabones en barra / de tocador (`Jabón Dove 90g` -> 1 un; `Multipack 3x90g` -> 3 un).
   - Pañales, toallitas húmedas, papel higiénico, rollos de cocina, saquitos de té/mate cocido,
     cápsulas de café, comprimidos, maquinitas/cartuchos de afeitar, esponjas, bolsas, huevos.
2. Productos que se comparan **por litro (`l`)**:
   - Bebidas, leches líquidas, aceites, productos de limpieza líquidos, shampoo, acondicionador,
     desodorantes en aerosol/roll-on, cremas corporales líquidas (`ml`, `cc`, `l`, `lt`).
3. Productos que se comparan **por kilo (`kg`)**:
   - Alimentos secos/frescos (arroz, fideos, yerba, azúcar, harina, galletitas, quesos, carnes,
     frutas, verduras, leche en polvo, cacao, jabón en polvo, alimento para mascotas) (`g`, `gr`, `kg`).
"""
import re
import unicodedata

CATEGORY_MAPPING = {
    "Almacén": "Supermercado", "Bebidas": "Supermercado", "Frescos": "Supermercado",
    "Limpieza": "Supermercado", "Congelados": "Supermercado", "Alimentos": "Supermercado",
    "Lácteos": "Supermercado", "Desayuno y merienda": "Supermercado",
    "Frutas y Verduras": "Supermercado", "Frutas y verduras": "Supermercado",
    "Carnes": "Supermercado", "Snacks": "Supermercado", "Panadería": "Supermercado",
    "Quesos y Fiambres": "Supermercado", "Pastas": "Supermercado",
    "Perfumería": "Salud y Belleza", "Cuidado Personal": "Salud y Belleza",
    "Farmacia": "Salud y Belleza", "Dermocosmética": "Salud y Belleza",
    "Maquillaje": "Salud y Belleza", "Bebés": "Bebés y Niños", "Mascotas": "Mascotas",
}

# Palabras clave de productos cuyo precio unitario real es POR PIEZA / UNIDAD ('un'),
# incluso si el título menciona el peso de cada pieza (ej: "Jabón en barra 3x90g" -> 3 un).
COUNTABLE_ITEM_KEYWORDS = (
    "jabon en barra", "jabon de tocador", "jabon tocador", "jabon corporal", "jabon en pan",
    "panal", "panales", "toallitas", "toalla femenina", "toallas femeninas", "protectores diarios",
    "tampon", "tampones", "papel higienico", "rollo de cocina", "rollos de cocina", "servilleta",
    "panuelo", "panuelos", "saquito", "saquitos", "capsula", "capsulas", "comprimido",
    "comprimidos", "pastilla", "pastillas", "preservativo", "preservativos", "afeitadora",
    "cartucho", "repuesto filo", "cepillo", "esponja", "bolsa de residuo", "bolsas de residuo",
    "huevo", "huevos", "vela", "velas", "pila", "pilas", "lampara",
)

# Detecta multipacks del estilo "6 x 330 ml", "Pack 4x1 L", "12 x 500 cc", "3x90 G"
MULTIPACK_REGEX = re.compile(
    r'(\d+)\s*[xX×]\s*(\d+(?:[.,]\d+)?)\s*'
    r'(l|lt|lts|litro|litros|ml|cc|cm3|g|gr|grs|gramo|gramos|grm|kg|kgs|kilogramo|un|u|unid|unidades|m|mts|metros)\b',
    re.IGNORECASE,
)

# Detecta multipacks invertidos del estilo "90 g. x 3 uni.", "500 ml x 6 u"
MULTIPACK_REV_REGEX = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*'
    r'(l|lt|lts|litro|litros|ml|cc|cm3|g|gr|grs|gramo|gramos|grm|kg|kgs|kilogramo)\s*\.?\s*'
    r'[xX×]\s*(\d+)\s*(?:un|u|uni|unid|unidades|pack|paq)?\b',
    re.IGNORECASE,
)

# Detecta cantidad explícita de unidades ("x 3 un", "pack x 4", "48 pañales", "20 saquitos")
EXPLICIT_UNITS_REGEX = re.compile(
    r'(?:[xX×]\s*(\d+)\s*(?:un|u|ud|uds|uni|unid|unidades)\b)|'
    r'(?:\b(\d+)\s*(?:un|u|ud|uds|uni|unid|unidades|rollos?|paños?|saquitos?|capsulas?|cápsulas?|tiras?|pañales?|comp|comprimidos?)\b)',
    re.IGNORECASE,
)

UNIT_REGEX = re.compile(
    r'(\d+(?:[.,]\d+)?|\d+/\d+)\s*'
    r'(l|lt|lts|litro|litros|ml|cc|cm3|g|gr|grs|gramo|gramos|grm|kg|kgs|kilogramo|kilo|'
    r'un|u|ud|uds|uni|unid|unidades|rollos?|paños?|saquitos?|capsulas?|cápsulas?|tiras?|pañales?|comp|comprimidos?)\b',
    re.IGNORECASE,
)


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


def normalizar_categoria(cat: str) -> str:
    if not cat:
        return "Otros"
    first = cat.split(",")[0].strip().strip("/").split("/")[0].strip()
    return CATEGORY_MAPPING.get(first, first or "Otros")


def normalizar_unidad(precio, unidad):
    """(precio_por_unidad, unidad) -> normalizado a kg / l / un."""
    if not unidad or not precio:
        return precio, unidad or "un"
    u = str(unidad).lower().strip().rstrip(".")
    p = float(precio)
    if u in ("lt", "lts", "litro", "litros"):
        u = "l"
    elif u in ("gr", "grs", "gramo", "gramos", "grm"):
        u = "g"
    elif u in ("kilogramo", "kilogramos", "kilo", "kgs"):
        u = "kg"
    elif u in ("cc", "cm3", "ml"):
        u = "ml"
    elif u in ("u", "ud", "uds", "uni", "unid", "unidades", "rollo", "rollos", "saquito", "saquitos",
               "capsula", "capsulas", "cápsula", "cápsulas", "tira", "tiras", "pañal", "pañales",
               "comp", "comprimido", "comprimidos"):
        u = "un"

    if u == "ml":
        return round(p * 1000, 2), "l"
    if u == "g":
        return round(p * 1000, 2), "kg"
    return round(p, 2), u


def extraer_unidad_titulo(titulo: str):
    """Extrae (cantidad_en_kg/l/un, unidad) desde el nombre.
    - Si es un artículo discreto/contable (ej: 'Jabón de Tocador Dove Multipack 3x90 G' o 'Jabón en barra 90 g'),
      devuelve `(3.0, 'un')` o `(1.0, 'un')` para comparar precio por jabón/unidad.
    - Si es líquido o alimento por peso (ej: 'Coca 2.25 L', 'Pack 6 x 330 ml', 'Arroz 500 g'),
      devuelve litros (`l`) o kilos (`kg`).
    """
    if not titulo:
        return 1.0, "un"

    norm_title = _strip_accents(titulo)
    is_countable = any(k in norm_title for k in COUNTABLE_ITEM_KEYWORDS)

    # 1. Evaluar multipacks tipo "3 x 90 g" o "6 x 330 ml"
    mp = MULTIPACK_REGEX.search(titulo)
    if mp:
        try:
            mult = float(mp.group(1))
            val = float(mp.group(2).replace(",", "."))
            unidad = mp.group(3).lower()
            if is_countable and 1 <= mult <= 100:
                return mult, "un"
            total = mult * val
            if unidad in ("l", "lt", "lts", "litro", "litros"):
                return total, "l"
            if unidad in ("ml", "cc", "cm3"):
                return total / 1000.0, "l"
            if unidad in ("kg", "kgs", "kilogramo"):
                return total, "kg"
            if unidad in ("g", "gr", "grs", "gramo", "gramos", "grm"):
                return total / 1000.0, "kg"
            if unidad in ("m", "mts", "metros"):
                return mult, "un"
            return total, "un"
        except Exception:
            pass

    # 1b. Evaluar multipacks invertidos tipo "90 g. x 3 uni."
    mp_rev = MULTIPACK_REV_REGEX.search(titulo)
    if mp_rev:
        try:
            val = float(mp_rev.group(1).replace(",", "."))
            unidad = mp_rev.group(2).lower()
            mult = float(mp_rev.group(3))
            if is_countable and 1 <= mult <= 100:
                return mult, "un"
            total = mult * val
            if unidad in ("l", "lt", "lts", "litro", "litros"):
                return total, "l"
            if unidad in ("ml", "cc", "cm3"):
                return total / 1000.0, "l"
            if unidad in ("kg", "kgs", "kilogramo"):
                return total, "kg"
            if unidad in ("g", "gr", "grs", "gramo", "gramos", "grm"):
                return total / 1000.0, "kg"
        except Exception:
            pass

    # 1c. Si es un producto contable por unidad (jabón en barra, pañales, saquitos, cápsulas, rollos):
    if is_countable:
        m_u = EXPLICIT_UNITS_REGEX.search(titulo)
        if m_u:
            try:
                qty_u = float(m_u.group(1) or m_u.group(2))
                if 1 <= qty_u <= 300:
                    return qty_u, "un"
            except Exception:
                pass
        return 1.0, "un"

    # 2. Evaluar unidad simple (ej: "Yerba 500 g", "Leche 1 L", "x kg")
    if re.search(r'\bx\s*kg\b|\bpor\s*kg\b', titulo, re.IGNORECASE):
        return 1.0, "kg"

    m = UNIT_REGEX.search(titulo)
    if not m:
        return 1.0, "un"
    cant_str = m.group(1).replace(",", ".")
    unidad = m.group(2).lower()
    try:
        if "/" in cant_str:
            num, den = cant_str.split("/")
            cantidad = float(num) / float(den)
        else:
            cantidad = float(cant_str)
        if cantidad <= 0:
            return 1.0, "un"
        if unidad in ("l", "lt", "lts", "litro", "litros"):
            return cantidad, "l"
        if unidad in ("ml", "cc", "cm3"):
            return cantidad / 1000.0, "l"
        if unidad in ("kg", "kgs", "kilogramo", "kilo"):
            return cantidad, "kg"
        if unidad in ("g", "gr", "grs", "gramo", "gramos", "grm"):
            return cantidad / 1000.0, "kg"
        return cantidad, "un"
    except Exception:
        pass
    return 1.0, "un"


def sanity_precio_unidad(precio_total: float, precio_unidad: float, unidad: str):
    """Corrige outliers groseros en kg/l (típicamente precio por gramo sin convertir)."""
    if unidad not in ("kg", "l") or not precio_unidad or not precio_total:
        return round(precio_unidad, 2) if precio_unidad else precio_total
    if precio_unidad < precio_total / 100:
        return round(precio_unidad * 1000, 2)
    return round(precio_unidad, 2)
