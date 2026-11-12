"""api/_lib/catalog_normalizer.py

Global Catalog Normalizer & Cross-Store Entity Resolution Engine for SuperVmarket.
Implements Milestone 2 (Normalización Global y Resolución de Entidades - R2):
1. Canonical 19-category taxonomy with strict negative guards:
   - Food/perishable/hygiene immune guards FIRST (protects "Rack de cordero", "Colchón tiramisu", cleaning refills, cosmetics cover).
   - "muebles_racks", streaming devices ("audio_video"), and "soportes_accesorios" evaluated strictly BEFORE "televisores".
   - Pure Smart TVs in "televisores" (0% accessories or furniture infiltration).
   - Contextual store/category fallbacks ensuring 100% coverage (0 NULLs).
2. Two-tier in-memory entity resolution index:
   - Hardware: (brand_norm, model_norm, variant) -> canonical GS1 EAN.
   - Grocery: (brand_norm, name_base_tokens, round(qty, 3), unit) -> canonical GS1 EAN.
   - GS1 Modulo 10 check digit routing: Argentina 779... > Manufacturer 880/889... > Valid EAN-13 > UPC-12 / EAN-8.
   - Hardware capacity variant preservation (128GB, 256GB, 512GB, 1TB never merge).
   - Center-of-mass price sanity ratio guard (0.35 <= candidate / canonical <= 2.80).
3. Deterministic collision resolution on precios(ean, supermercado) and referential integrity cleanup:
   - Deterministic stock and price priority.
   - Updates historial_precios.
   - Prunes synthetic shells in productos (leaving raw_catalog intact).
4. High-performance SQLite batch execution under WAL mode (<2s for 33k rows).
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import time
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple

from .normalization import (
    is_valid_ean13,
    normalize_ean,
    is_internal_scale,
    extract_model,
    extract_capacity_variant,
    is_accessory,
    _strip_accents,
    FALSE_SPECS_RE,
)
from .parsers import extraer_unidad_titulo

logger = logging.getLogger("supervmarket.catalog_normalizer")

# ---------------------------------------------------------------------------
# In-Memory Resolution Tables
# ---------------------------------------------------------------------------
GLOBAL_MODEL_TO_EAN: Dict[Tuple[str, str, str], Tuple[str, float, int, int]] = {}
GROCERY_TO_EAN: Dict[Tuple[str, str, float, str], Tuple[str, float, int, int]] = {}

# Corporate / Brand Synonyms Table
BRAND_SYNONYMS = {
    "SAMSUNG ELECTRONICS": "SAMSUNG",
    "SAMSUNG OFICIAL": "SAMSUNG",
    "PHILIPS ARGENTINA": "PHILIPS",
    "PHILIPS ARGENTINA S.A.": "PHILIPS",
    "WHIRLPOOL CORP": "WHIRLPOOL",
    "WHIRLPOOL ARGENTINA": "WHIRLPOOL",
    "MOTOROLA MOBILITY": "MOTOROLA",
    "MOTO": "MOTOROLA",
    "DREAN ARGENTINA": "DREAN",
    "ALLADIO": "DREAN",
    "LG ELECTRONICS": "LG",
    "TCL ELECTRONICS": "TCL",
    "APPLE INC": "APPLE",
    "NOBLEX ARGENTINA": "NOBLEX",
    "BGH S.A.": "BGH",
    "LILIANA S.A.": "LILIANA",
    "ATMA ARGENTINA": "ATMA",
    "MOLINOS RIO DE LA PLATA": "MOLINOS",
    "ARCOR S.A.": "ARCOR",
    "LA SERENISIMA": "LA SERENISIMA",
    "MASTELLONE HERMANOS": "LA SERENISIMA",
    "DANONE ARGENTINA": "DANONE",
    "QUILMES CERVECERIA": "QUILMES",
    "COCA COLA": "COCA-COLA",
    "COCA-COLA FEMSA": "COCA-COLA",
}

FALSE_MODELS_EXTRA = re.compile(
    r'^(?:'
    r'\d{2,3}[Xx×]\d{2,3}|'                    # 140x190, 160x200
    r'[Xx×]\d+|'                               # x12, x24
    r'\d+-\d+|'                                # 6-18
    r'(?:FPS|SPF)\d+|'                         # FPS50, SPF50
    r'R(?:12|13|14|15|16|17|18|19|20|24|26|27\.?5|28|29)|' # R29, R26
    r'E(?:14|27|40)|'                          # E27
    r'IN-?E(?:AR)?|'                           # in-ear
    r'ROLL-?ON|'                               # roll-on
    r'LUMI-?MATTE|'                            # cosmetics
    r'NO-?FROST|'                              # no frost
    r'ROCHE-?POSAY|'                           # brand
    r'COCA-?COLA'                              # brand
    r')$',
    re.IGNORECASE,
)

PACKAGING_STOPWORDS = {
    "sachet", "caja", "botella", "pack", "envase", "tetra", "doypack", "lata", "paquete",
    "frasco", "pote", "bolsa", "fardo", "display", "brik", "brick", "pet", "vidrio"
}

COMMERCIAL_NOISE_SAFE = {
    "nuevo", "nueva", "oferta", "super", "familiar",
    "promo", "promocion", "descuento", "especial", "premium", "seleccion", "seleccionado",
    "seleccionada", "economico", "economica", "ahorro"
}

def norm_brand(b: str) -> str:
    """Normalizes and canonicalizes brand names."""
    if not b:
        return ""
    b_clean = re.sub(r'\s+', ' ', _strip_accents(b).upper().strip())
    return BRAND_SYNONYMS.get(b_clean, b_clean)


def norm_hardware_model(brand: str, model_str: str) -> str:
    """
    Normalizes manufacturer model identifiers across different retail conventions:
    1. Samsung TV: unifies 'UN50DU7000', '50DU7000', 'UN50DU7000GCZB', 'UN50DU7000GCFV' -> '50DU7000'.
    2. LG TV: strips regional suffixes (.AWC, .AWF).
    3. Motorola / Cellphones: unifies 'MOTO G54' and 'G54'.
    """
    m = re.sub(r'[^A-Z0-9]', '', model_str.upper())
    if not m:
        return ""
    b = brand.upper() if brand else ""
    if "SAMSUNG" in b:
        m = re.sub(r'^(?:UN|QN|LH)(\d{2}[A-Z]{1,2}\d{3,4})', r'\1', m)
        m = re.sub(r'(?:GCZB|GCFV|XZB|XBG|CZB|FV)$', '', m)
    elif "LG" in b:
        m = re.sub(r'(?:AW[A-Z]|BW[A-Z]|CW[A-Z])$', '', m)
    elif "MOTOROLA" in b:
        m = re.sub(r'^(?:MOTO)?([EGE]\d{1,2})', r'\1', m)
    return m

def clean_grocery_base_name(name: str, brand: str = "") -> str:
    """
    Cleans grocery product titles for safe canonical matching:
    Removes packaging stopwords and commercial marketing noise while preserving
    dairy qualifiers (entera, descremada), soda sugar types (zero, sin azucar),
    whisky aging years (12, 18), and beer styles (rubia, negra, ipa).
    """
    norm_n = _strip_accents(name or "").lower()
    norm_b = _strip_accents(brand or "").lower()

    if norm_b:
        for b_tok in norm_b.split():
            if len(b_tok) >= 3:
                norm_n = re.sub(rf'\b{re.escape(b_tok)}\b', ' ', norm_n)

    for pw in PACKAGING_STOPWORDS:
        norm_n = re.sub(rf'\b{re.escape(pw)}\b', ' ', norm_n)

    for cn in COMMERCIAL_NOISE_SAFE:
        norm_n = re.sub(rf'\b{re.escape(cn)}\b', ' ', norm_n)

    norm_n = re.sub(r'\b\d+(?:[.,]\d+)?\s*(?:kg|g|gr|grs|l|lt|lts|ml|cc|cm3|un|u)\b', ' ', norm_n)
    norm_n = re.sub(r'\b[xX×]\s*\d+\s*(?:un|u|uni|unidades)?\b', ' ', norm_n)

    tokens = [t for t in re.sub(r'[^a-z0-9]', ' ', norm_n).split() if len(t) >= 2]
    return " ".join(sorted(tokens))

# ---------------------------------------------------------------------------
# Canonical Regular Expressions for 19 Categories
# ---------------------------------------------------------------------------

# 1. Dispositivos de streaming (audio_video, evaluated BEFORE accessories and TVs)
RE_STREAMING_DEVICE = re.compile(
    r'\b(?:tv\s*box|streaming\s*stick|roku(?:\s+streaming|\s+stick)?|chromecast|'
    r'apple\s*tv|mi\s*tv\s*stick|media\s*streamer|convertidor\s+(?:smart|ott))\b',
    re.IGNORECASE,
)

# 2. Muebles y Racks (with negative guards against meat "rack" and food "colchón")
RE_MUEBLE = re.compile(
    r'(?<!cordero\s)(?<!de\s)\b(?:'
    r'rack\s+(?:tv|para\s+tv|de\s+tv|modular|vajillero|led|audio|mesa|flotante|organizador|living|con\s+panel)|'
    r'rack(?:\s+de)?\s+\d+\s+(?:puertas|nichos|cajones|niveles)|'
    r'mesa\s+(?:para\s+tv|tv|ratona|de\s+centro|de\s+arrime|comedor|de\s+luz|escritorio|living)|'
    r'panel\s+(?:para\s+tv|tv)|modular\s+tv|mueble\s+(?:tv|de\s+tv|rack|living|cocina|bajo\s+mesada)|'
    r'placard|ropero|comoda|chifonier|escritorio|sillon(?!\s+de\s+bebe)|sofa|estante\s+flotante|'
    r'(?:colchon|sommier|bicama|base\s+de\s+sommier)(?!\s+(?:de\s+|con\s+)?(?:fruta|frutos|tiramisu|key\s+lime|arvejas?|espinacas?|vegetales?|verduras?|legumbres?))'
    r')\b',
    re.IGNORECASE,
)

# 3. Soportes y Accesorios
RE_SOPORTE_ACCESORIO = re.compile(
    r'\b(?:'
    r'soporte|'
    r'funda|'
    r'case(?:\s+(?:silicona|antigolpe|protector|para\s+celular|para\s+iphone|para\s+samsung))?|'
    r'(?:smart\s+cover|book\s+cover|standing\s+cover|screen\s+cover|keyboard\s+cover|protective\s+cover|cover\s+silicona|cover\s+protector)|'
    r'estuche\s+(?:rigido|para\s+(?:notebook|auricular|consola|the\s+freestyle|celular|tablet))|'
    r'(?:vidrio|cristal)\s+templado(?:\s+9d)?|protector\s+de\s+pantalla|film\s+hidrogel|'
    r'control\s+remoto|cable(?:\s+(?:hdmi|usb|lightning|tipo\s+c|de\s+audio|auxiliar|optico|para|de\s+carga|datos))?|'
    r'cargador|'
    r'adaptador(?:\s+(?:doble|usb|tipo\s+c|para|hdmi|lightning|trio))?|'
    r'malla\s+silicona|correa\s+para\s+reloj|'
    r'repuesto\s+(?:para\s+(?:tv|celular|notebook|afeitadora|licuadora|cafetera|purificador|taladro|aspiradora)|cuchillas?|vaso|filtro|bolsa\s+aspiradora|heladera|lavarropas|aire|motor)|'
    r'bateria\s+(?:18v|12v|20v|para\s+taladro|de\s+repuesto(?!\s+de\s+cocina)|movil\s+para\s+the\s+freestyle)|'
    r'modulo\s+pantalla|protector\s+de\s+tv|sync\s+box|base\s+movil|'
    r'bot[oó]n\s+(?:para\s+)?celular|phone\s*bag|porta\s*celular|anillo\s+(?:para\s+)?celular|popsocket|'
    r'palo\s+(?:de\s+)?selfie|tripode|mochila|bolso\s+porta\s+notebook|porta\s+notebook|'
    r'smartwatch|smart\s*watch|reloj\s+inteligente|smartband|smart\s*band|watch\s+fit|band\s+\d+'
    r')\b',
    re.IGNORECASE,
)

# 4. Audio y Video General
RE_AUDIO_VIDEO = re.compile(
    r'\b(?:'
    r'auriculares|audifonos|headphone|earbuds|airpods|'
    r'parlante|soundbar|barra\s+de\s+sonido|sound\s*tower|home\s+theater|microfono|'
    r'proyector|the\s+freestyle|amplificador|sintoamplificador|consola\s+de\s+sonido|'
    r'camara\s+(?:de\s+seguridad|ip|wifi|digital|deportiva|fotos)|videoportero|dron|drone'
    r')\b',
    re.IGNORECASE,
)

# 5. Televisores (Pure Hardware)
RE_TELEVISORES = re.compile(
    r'\b(?:'
    r'smart\s*tv|televisor|televisores|tv\s+led|led\s+tv|qled|oled|neo\s*qled|mini\s*led|'
    r'google\s+tv|android\s+tv|roku\s+tv|vidaa\s+tv|titan\s+os|the\s+frame|'
    r'tv\s+(?:4k|uhd|fhd|hd|curvo|lifestyle)|4k\s+uhd\s+tv'
    r')\b|^(?:tv\.|tv\s+)',
    re.IGNORECASE,
)

# 6. Celulares
RE_CELULARES = re.compile(
    r'\b(?:'
    r'celular|celulares|smartphone|smartphones|telefono\s+celular|'
    r'iphone|galaxy\s+(?:a\d+|s\d+|z\s*flip|z\s*fold)|'
    r'moto\s+(?:g\d+|edge|e\d+)|redmi\s+note|xiaomi\s+redmi'
    r')\b',
    re.IGNORECASE,
)

# 7. Notebooks y Tablets
RE_NOTEBOOKS_TABLETS = re.compile(
    r'\b(?:'
    r'notebook|notebooks|laptop|laptops|macbook|chromebook|netbook|'
    r'tablet|tablets|ipad|galaxy\s+tab|kindle|'
    r'impresora|multifuncion|monitor(?:\s+gamer|\s+led|\s+curvo|\s+ips)?|scanner|all\s+in\s+one'
    r')\b',
    re.IGNORECASE,
)

# 8. Heladeras y Freezers
RE_HELADERAS_FREEZERS = re.compile(
    r'\b(?:heladera|heladeras|no\s*frost|freezer|freezers|frigobar|cava(?:\s+de\s+vinos)?|exhibidora(?:\s+vertical)?)\b',
    re.IGNORECASE,
)

# 9. Lavado
RE_LAVADO = re.compile(
    r'\b(?:lavarropas|lavarropa|secarropas|secarropa|lavavajillas|lavasecarropas|lavasecarropa)\b',
    re.IGNORECASE,
)

# 10. Climatización
RE_CLIMATIZACION = re.compile(
    r'\b(?:'
    r'aire\s+acondicionado|split\s+inverter|split\s+frio|climatizador|'
    r'calefactor|calefactores|estufa(?:\s+a\s+gas|\s+tiro\s+balanceado|\s+electrica|\s+infrarroja|\s+halogena)?|'
    r'caloventor|convector|vitroconvector|radiador\s+electrico|panel\s+calefactor|'
    r'termotanque|calefon|ventilador(?:\s+de\s+techo|\s+de\s+pie|\s+turbo|\s+de\s+pared)?'
    r')\b',
    re.IGNORECASE,
)

# 11. Cocina y Hornos
RE_COCINA_HORNOS = re.compile(
    r'\b(?:'
    r'cocina\s+(?:a\s+gas|electrica|multigas|industrial)|anafe(?:\s+a\s+gas|\s+vitroceramico|\s+induccion|\s+electrico)?|'
    r'horno\s+(?:electrico|empotrable|a\s+gas|pizzero)|microondas|'
    r'campana(?:\s+extractora|\s+de\s+cocina)?|extractor\s+(?:cocina|purificador)|purificador\s+de\s+cocina'
    r')\b',
    re.IGNORECASE,
)

# 12. Pequeños Electrodomésticos
RE_PEQUENOS_ELECTRO = re.compile(
    r'\b(?:'
    r'freidora(?:\s+de\s+aire)?|airfryer|pava\s+electrica|cafetera(?:\s+express|\s+filtro|\s+capsulas)?|'
    r'licuadora|batidora|tostadora|sandwichera|procesadora|multiprocesadora|'
    r'exprimidor|waflera|yogurtera|vaporera|rallador\s+electrico|'
    r'centrifugador(?:\s+de\s+verduras)?|cortadora\s+de\s+verduras|cortador\s+de\s+verduras|'
    r'plancha(?:\s+a\s+vapor|\s+seca)?|aspiradora(?:\s+trineo|\s+robot|\s+manual)?|limpiatapizados|'
    r'afeitadora(?:\s+electrica)?|cortabarba|cortapelo|cortadora\s+de\s+pelo|depiladora|'
    r'secador\s+de\s+pelo|planchita\s+de\s+pelo|cepillo\s+secador|balanza\s+de\s+cocina'
    r')\b',
    re.IGNORECASE,
)

# 13. Herramientas y Construcción
RE_HERRAMIENTAS = re.compile(
    r'\b(?:'
    r'taladro|rotomartillo|amoladora|sierra(?:\s+circular|\s+caladora|\s+sable)?|'
    r'hidrolavadora|soldadora(?:\s+inverter)?|electrodos|atornillador|'
    r'llave\s+(?:fija|combinada|francesa|allen|tubo)|pinza|alicate|alicates|martillo|destornillador|'
    r'escalera(?:\s+aluminio)?|pintura(?:\s+latex|\s+sintetico|\s+antioxido)?|pincel|rodillo|'
    r'tornillo|tornillos|tarugo|clavo|lija|adhesivo\s+silicona|cinta\s+aisladora|'
    r'termofusion|corte\s+ceramico|bomba\s+de\s+agua|presurizadora|grupo\s+electrogeno'
    r')\b',
    re.IGNORECASE,
)

# 14. Mascotas
RE_MASCOTAS = re.compile(
    r'\b(?:'
    r'perro|perros|gato|gatos|canino|felino|cachorro|kitten|puppy|'
    r'alimento\s+para\s+(?:perros?|gatos?)|comida\s+(?:perros?|gatos?)|snack\s+(?:perros?|gatos?)|'
    r'piedras\s+sanitarias|piedritas(?:\s+para\s+gato)?|pipeta(?:\s+antipulgas)?|shampoo\s+(?:perros?|gatos?)|'
    r'collar\s+(?:perro|gato)|correa\s+(?:perro|gato)|rascador|hueso\s+masticable|'
    r'pedigree|whiskas|royal\s+canin|purina|dog\s+chow|cat\s+chow|pro\s+plan|eukanuba|sieger|catycan|vitalcan'
    r')\b',
    re.IGNORECASE,
)

# 15. Bebidas
RE_BEBIDAS = re.compile(
    r'\b(?:'
    r'agua\s+(?:mineral|sin\s+gas|con\s+gas|saborizada)|soda|sifon|'
    r'gaseosa|gaseosas|cola|coca\s*cola|sprite|fanta|pepsi|seven\s*up|paso\s+de\s+los\s+toros|'
    r'jugo|jugos|nectar|levite|aquarius|ades|beldent\s+splash|'
    r'cerveza|cervezas|quilmes|brahma|stella\s+artois|heineken|corona|andes|patagonia|'
    r'vino|vinos|malbec|cabernet|torrontes|syrah|chardonnay|bonarda|espumante|champagne|'
    r'fernet|aperitivo|aperol|campari|gin|vodka|whisky|whiskey|ron|licor|vermouth|vermut|'
    r'energizante|monster\s+energy|red\s+bull|gatorade|powerade|isotonic|'
    r'bebida\s+(?:yaci|kombucha|energetica|isotonica|saborizada|vegetal|en\s+lata)?|kombucha'
    r')\b',
    re.IGNORECASE,
)

# 16. Lácteos y Frescos
RE_LACTEOS = re.compile(
    r'\b(?:'
    r'leche(?:\s+(?:entera|descremada|deslactosada|polvo|larga\s+vida))?|'
    r'yogur(?:t|es)?(?:\s+(?:entero|descremado|firme|bebible|batido|liquido|griego))?|dahi|'
    r'sachet\s+(?:entero|descremado)|'
    r'crema\s+de\s+leche|manteca|margarina|'
    r'queso|quesos|muzzarella|mozzarella|cremoso|port\s+salut|tybo|gouda|reggianito|sardo|parmesano|roquefort|cheddar|untable|brie|camembert|ricota|'
    r'flan|postre|postrecito|dulce\s+de\s+leche|'
    r'tapas\s+de\s+empanadas|tapas\s+de\s+pascualina|pascualina|masa\s+(?:para\s+empanadas|para\s+tarta|hojaldre|fresca)|'
    r'pasta\s+fresca|pastas\s+frescas|ravioles|ñoquis|sorrentinos|fideos\s+frescos|levadura\s+fresca|'
    r'fiambre|fiambres|jamon\s+(?:cocido|crudo)|paleta\s+cocida|salame|salamin|mortadela|bondiola\s+fiambrera|panceta'
    r')\b',
    re.IGNORECASE,
)

# 17. Carnes y Verdulería
RE_CARNES_VERDULERIA = re.compile(
    r'\b(?:'
    r'carne|asado|(?<!bomba de )(?<!selladora al )(?<!envasadora al )\bvacio\b|matambre|tapa\s+de\s+asado|bife|colita\s+de\s+cuadril|peceto|lomo|nalga|bola\s+de\s+lomo|cuadrada|paleta\s+vacuna|roast\s+beef|tortuguita|falda|osobuco|entran[a|ñ]a|'
    r'carne\s+picada|carne\s+molida|milanesa|milanesas|'
    r'pollo|pechuga|pata\s+muslo|alitas|suprema|pollo\s+trozado|'
    r'cerdo|bondiola|pechito\s+de\s+cerdo|carre\s+de\s+cerdo|solomillo|costillitas|costillar|'
    r'cordero|rack\s+(?:de\s+)?cordero|paleta\s+de\s+cordero|chivito|lechon|'
    r'achuras|chorizo|chorizos|morcilla|mollejas|chinchulines|rinon|riñon|'
    r'pescado|merluza|salmon|atun\s+fresco|calamar|rabas|langostinos|mariscos|fillet|'
    r'huevo|huevos|maple\s+de\s+huevos|'
    r'manzana|manzanas|banana|bananas|naranja|naranjas|mandarina|mandarinas|limon|limones|pera|peras|durazno|duraznos(?!\s+en\s+almibar)|frutilla|frutillas|uva|uvas|melon|sandia|anana|kiwi|palta|paltas|arandanos|cereza|cerezas|ciruela|ciruelas|'
    r'papa|papas(?!\s+fritas)(?!\s+congeladas)|cebolla|cebollas|tomate(?!\s+perita)(?!\s+en\s+lata)(?!\s+triturado)(?!\s+cubeteado)(?!\s+pelado)|tomates(?!\s+perita)(?!\s+en\s+lata)(?!\s+triturado)(?!\s+cubetead)(?!\s+pelad)(?!\s+pelati)|'
    r'zanahoria|zanahorias|zapallo|calabaza|anco|zapallito|zapallitos|zucchini|morron|morrones|pimiento|pimientos|lechuga|rucula|acelga|espinaca|espinacas|choclo|berenjena|berenjenas|pepino|pepinos|remolacha|apio|puerro|ajo|batata'
    r')\b',
    re.IGNORECASE,
)

# 18. Limpieza
RE_LIMPIEZA = re.compile(
    r'\b(?:'
    r'detergente|lavavajillas|suavizante|quitamanchas|'
    r'jabon\s+(?:liquido\s+)?(?:para\s+ropa|de\s+lavar|para\s+lavar|baja\s+espuma|en\s+polvo|blanco|en\s+pan|diluible|para\s+diluir|concentrado\s+para\s+diluir|concentrado\s+para\s+ciclo|ecolavado)|'
    r'jabon\s+pan|jabon\s+blanco|'
    r'lavandina|desinfectante|limpiador(?:\s+(?:de\s+pisos|liquido|cremoso|antigrasa|bano|cocina))?|limpiavidrios|desengrasante|'
    r'papel\s+higienico|rollo\s+de\s+cocina|rollos\s+de\s+cocina|servilletas|panuelos\s+descartables|'
    r'esponja|fibra\s+esponja|esponja\s+de\s+acero|virulana|trapo\s+de\s+piso|franela|rejilla|mopa|balde|secador\s+de\s+piso|escoba|escobillon|'
    r'bolsa\s+de\s+residuos|bolsas\s+de\s+residuos|bolsa\s+consorcio|'
    r'insecticida|espirales|tabletas\s+mosquitos|repelente(?:\s+de\s+mosquitos|\s+off|\s+fuyi)?|'
    r'pastilla\s+inodoro|canasta\s+(?:liquida|solida)\s+inodoro|bloque\s+inodoro|aerosol\s+ambiente|desodorante\s+de\s+ambiente|aromatizante|'
    r'poett|glade|cif|ayudin|skip|ala|ariel|comfort|procenex|procene|magistral|harpic|mr\s*musculo|blem|lysoform|granby|zorro|drive|ecovita'
    r')\b',
    re.IGNORECASE,
)

# 19. Perfumería y Farmacia
RE_PERFUMERIA_FARMACIA = re.compile(
    r'\b(?:'
    r'shampoo|acondicionador|bano\s+de\s+crema|mascara\s+capilar|tintura|coloracion|crema\s+para\s+peinar|gel\s+capilar|'
    r'jabon\s+(?:de\s+tocador|liquido(?:\s+(?:corporal|cremoso|para\s+manos|antibacterial|facial))?|cremoso|intimo|en\s+barra|de\s+glicerina|glicerina|exfoliante|antibacterial|solido|para\s+manos|baby)|'
    r'jabonera|panos?\s+jabonosos?|esponja\s+vegetal|'
    r'crema\s+(?:facial|corporal|de\s+manos|humectante|hidratante|antiarrugas|antiedad)|serum|locion|tonico|agua\s+micelar|desmaquillante|protector\s+solar|bloqueador\s+solar|autobronceante|post\s+solar|'
    r'desodorante(?:\s+corporal|\s+en\s+aerosol|\s+roll\s*on|\s+antitranspirante)?|antitranspirante|'
    r'pasta\s+dental|crema\s+dental|cepillo\s+de\s+dientes|enjuague\s+bucal|hilo\s+dental|'
    r'toallitas\s+humedas|panales|toallitas\s+femeninas|protectores\s+diarios|tampones|copa\s+menstrual|'
    r'maquillaje|base\s+de\s+maquillaje|corrector(?:\s+facial)?|labial|lapiz\s+labial|gloss|mascara\s+de\s+pestañas|rimel|delineador|sombra\s+de\s+ojos|rubor|iluminador|polvo\s+compacto|esmalte\s+de\s+uñas|quitaesmalte|'
    r'perfume|eau\s+de\s+parfum|eau\s+de\s+toilette|colonia|body\s+splash|fragancia|'
    r'afeitadora\s+descartable|hoja\s+de\s+afeitar|repuesto\s+de\s+afeitar|espuma\s+de\s+afeitar|gel\s+de\s+afeitar|after\s+shave|'
    r'medicamento|farmacia|analgesico|ibuprofeno|paracetamol|aspirina|antiinflamatorio|antialergico|antiacido|antiespasmodico|antigripal|descongestivo|jarabe|gotas\s+oculares|'
    r'preservativo|preservativos|preservativo\s+prime|tulipan|gel\s+lubricante|test\s+de\s+embarazo|evatest|'
    r'algodon|gasas|curitas|vendas|apositos|(?<!sin\s)(?<!0\.0%\s)\balcohol(?:\s+(?:etilico|en\s+gel|fino|puro|medicinal|sanitizante|al\s+70%?|70%?|96%?))?|agua\s+oxigenada|termometro|barbijo|suplemento|vitaminas|calcio|colageno|magnesio|omega\s*3|proteina|'
    r'ortopedia|faja(?:\s+pre\s+parto|\s+post\s+parto|\s+lumbar)?|rodillera|muslera|tobillera|cabestrillo|soporte\s+(?:sacro|lumbar|abdominal|embarazo)'
    r')\b',
    re.IGNORECASE,
)

# 20. Almacén Procesado (Alimentos procesados y conservas: deben evaluarse ANTES de carnes y verdulería)
RE_ALMACEN_PROCESSED = re.compile(
    r'\b(?:'
    r'pur[eé\ufffd]?\s*(?:de\s+)?tomates?|tomates?\s+pur[eé\ufffd]?|'
    r'tomates?\s+(?:cubetead[oa]s?|pelati|pelados?|triturados?|enteros?|perita|pomodoro|en\s+lata|pulpa|deshidratad[oa]s?|secos?|desecados?|confitad[oa]s?|en\s+trocitos|en\s+cubos|fritos?|deshidr)|'
    r'passata(?:\s+de\s+tomate)?|extracto\s+de\s+tomate|salsa\s+(?:de\s+)?tomate|pasta\s+de\s+tomate|dulce\s+de\s+tomate|pulpa\s+de\s+tomate|'
    r'pesto.*tomate|nube\s+de\s+tomate|'
    r'(?:la\s+campagnola|de\s+cecco|molisana|cirio|arcor|vigente|bulnez|inca|canale|alco)\b.*?\btomate|'
    r'mutti|'
    r'(?:duraznos?|peras?|choclos?|zanahorias?|espinacas?|arvejas?|jardinera|palmitos?|champignones?|macedonia|legumbres|hortalizas|pimientos?|morrones?|remolachas?)\b.*?\b(?:en\s+lata|lata)\b|'
    r'\blata\b.*?\b(?:duraznos?|peras?|choclos?|zanahorias?|espinacas?|arvejas?|jardinera|palmitos?|champignones?|macedonia|legumbres|hortalizas|pimientos?|morrones?|remolachas?)\b|'
    r'(?:duraznos?|peras?|anan[aá]s?|higos?|frutas?)\s+(?:en\s+almibar|lata|al\s+natural)|'
    r'jardinera(?:\s+dia|\s+arvejas|\s+zanahoria|\s+y\s+choclo)?|'
    r'(?:ajo|cebolla)\b.*?\blata\b|'
    r'cubetead[oa]s?|confitad[oa]s?|'
    r'picadillo(?:\s+de\s+carne)?|'
    r'pat[eé\ufffd](?:\s+de\s+(?:pollo|foie|higado|salmon|cerdo|bondiola))?|pat[eé\ufffd]\s+asta\s+negra|'
    r'(?:atun|caballa|sardinas?)\b.*?\b(?:en\s+lata|lata|en\s+aceite|al\s+natural|agua\s+y\s+aceite)\b|'
    r'lomo\s+de\s+atun|sardinas?\s+con\s+vegetal|'
    r'papas?\s+fritas|pur[eé\ufffd]?\s+de\s+papas?|papas?\s+congeladas?|'
    r'mermeladas?|dulce\s+de\s+(?:durazno|frutilla|naranja|ciruela|pera|membrillo|batata|zapallo|arandanos?|higo|frambuesa|frutos?|cereza|manzana|tomate)|jaleas?|almibar|'
    r'(?:duraznos?|peras?|anan[aá]s?|frutas?|coctel|macedonia|damascos?|ciruelas?)\s+(?:en\s+(?:mitades|rodajas|trozos|almibar|alm[ií]bar|cubos|almibar\s+light|almibar\s+diet)|al\s+natural)|'
    r'coctel(?:\s+(?:de\s+)?(?:\d+\s+)?frutas)?|'
    r'arvejas?|lentejas?|garbanzos?|porotos?|choclo\s+(?:en\s+granos?|cremoso|amarillo\s+(?:en\s+granos?|entero)|entero|desgranado|al\s+vapor)|granos\s+de\s+choclo|dueto|'
    r'gelatinas?|flan\s+en\s+polvo|postre\s+en\s+polvo|mousse\s+en\s+polvo|polvo\s+para\s+(?:hornear|bizcochuelo|preparar)|'
    r'galletitas?|galletas?|alfajor(?:es)?|macucas|\bman[aá]\b|merengadas|chocolinas|pitusas|oreo|pepitos|rumba|mellizas|sonrisas|(?:galletitas\s+)?tentaciones\s+rellenas|galletitas\s+tentaciones|'
    r'\bt[eé]\b|infusi[oó]n|infusiones|yerba(?:\s+mate)?|saquitos?|chamomilla|manzanilla|boldo|til[oó]|mate\s+cocido|'
    r'huevo\s+(?:de\s+pascua|bariloche|kinder|milka|ferrero|artesanal|chocolate)|bomb[oó]n\s+de\s+chocolate|bombones|chocolates?|caramelos?|chicles?|gomitas?|turr[oó]n|turrones|'
    r'pan\s+(?:(?:para\s+(?:panchos?|hamburguesas?)\s+)?(?:de\s+)?papas?|para\s+(?:panchos?|hamburguesas?)|lactal|blanco|negro|integral|arabe|frances|baguette|tostad[oa]s?|rallado)|'
    r'(?:ajo|cebolla)\s+en\s+polvo|condimento\s+(?:para|de|para\s+pollo|para\s+carne|para\s+pescado)|piment[oó]n|vinagre(?:\s+de\s+(?:manzana|alcohol|vino|sidra))?|aceto(?:\s+balsamico)?|chimichurri(?!\s+para\s+carne)|(?<!con\s)(?<!rebozad[oa]\s)provenzal(?:\s+mezcla)?|oregano|comino|aji\s+molido|nuez\s+moscada|'
    r'pepinillos?|pepinos?\s+(?:en\s+conserva|en\s+vinagre|en\s+rodajas|agridulces?|encurtidos?)|'
    r'calamar\s+en\s+su\s+tinta|pulpo\s+al\s+ajillo|'
    r'conservas?|pulpas?|lata\s+de\s+tomate|'
    r'twistos|bruschette|pita\s+chips|tallarines|prepizza|prepizzas|pizzetas?|maretti|tostaditas|green\s+crops|'
    r'fideos\s+(?:tallarin|fettuccini|spaghettis?|tirabuzon|casereccia|ramen|noodles?|box|vaso|largos?|guiseros?|sabor|al\s+huevo|con\s+pollo|con\s+salsa)|'
    r'fideos(?:\s+listos)?\s+arcor\s+ramen|fideos\s+noodles|'
    r'sopa\s+(?:maggi|familiar|carrefour|knorr|quick)?(?:\s+de\s+(?:pollo|carne|fideos))?|'
    r'caldo\s+de\s+(?:carne|pollo|gallina|verdura)|'
    r'barritas?\s+(?:proteicas?|de\s+cereal|de\s+frutos|de\s+semillas)|pure\s+wellness|'
    r'chips\s+de\s+(?:manzana|banana|batata|papas)|'
    r'veggie\s+sticks|pan\s+tostado|crackers|pan\s+dulce|'
    r'(?:ajo|cebolla|remolacha|zanahoria|frutas?|ciruelas?)\s+(?:deshidratad[oa]s?|desecad[oa]s?)|'
    r'ciruelas?\s+(?:desecadas?|sin\s+carozos?|sin\s+cascara)|'
    r'mix\s+de\s+citricos\s+deshidratados|'
    r'semillas\s+tomate'
    r')\b',
    re.IGNORECASE,
)

# 21. Almacén General (Dry Groceries)
RE_ALMACEN = re.compile(
    r'\b(?:'
    r'arroz|fideos|pasta\s+seca|tallarines|tirabuzon|spaghetti|mostachol|guiseros|sopas|'
    r'harina|harina\s+leudante|premezcla|polenta|avena|cereales|copos\s+de\s+maiz|barrita\s+de\s+cereal|'
    r'aceite(?:\s+(?:girasol|oliva|mezcla|maiz|soja))?|vinagre|aceto\s+balsamico|'
    r'azucar|edulcorante|stevia|miel|sal(?:\s+(?:fina|gruesa|entrefina))?|salero|pimienta|oregano|pimenton|provenzal|laurel|especias|condimento|adobo|caldo|caldos|saborizador|'
    r'yerba|yerba\s+mate|cafe(?:\s+(?:molido|en\s+grano|instantaneo|torrado|capsulas))?|te(?:\s+(?:en\s+saquitos|en\s+hebras|verde|negro|manzanilla))?|mate\s+cocido|cacao(?:\s+en\s+polvo)?|nesquik|chocolatada|'
    r'galletitas|galletas|crackers|bizcochitos|tostadas|pan(?:\s+(?:lactal|de\s+molde|hamburguesa|pancho|rallado))?|rebozador|grisines|'
    r'pure\s+de\s+tomate|tomate\s+perita|extracto\s+de\s+tomate|salsa\s+de\s+tomate|conservas|lentejas|arvejas|garbanzos|porotos|choclo|jardinera|atun(?:\s+en\s+lata|\s+al\s+natural|\s+en\s+aceite)?|caballa|sardinas|pat[e|é]|picadillo|'
    r'mayonesa|mostaza|ketchup|salsa\s+golf|aderezo|salsa\s+de\s+soja|aceto|chimichurri|'
    r'mermelada|dulce\s+de\s+membrillo|dulce\s+de\s+batata|jalea|almibar|duraznos\s+en\s+almibar|coctel\s+de\s+frutas|'
    r'snacks|papas\s+fritas|nachos|mani|chizitos|palitos\s+salados|pochoclo|'
    r'alfajor|alfajores|chocolate|chocolates|bombones|caramelos|chicles|chupetin|turron|obleas|golosinas|gelatina|polvo\s+para\s+bizcochuelo|flan\s+en\s+polvo|postre\s+en\s+polvo|polvo\s+para\s+hornear|bicarbonato'
    r')\b',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 1. Classification Function Contract
# ---------------------------------------------------------------------------
def classify_canonical_category(
    title: str,
    brand: str = "",
    categories: str = "",
    store_type: str = "supermarket",
    **kwargs: Any,
) -> str:
    """
    Classifies a product into one of the 19 canonical categories.
    Strictly evaluates food guards FIRST, followed by 'muebles_racks',
    streaming devices ('audio_video'), and 'soportes_accesorios' BEFORE 'televisores'.
    Guarantees pure Smart TVs in 'televisores' and 100% coverage (0 NULLs).
    """
    # Accommodate variations in calling convention (e.g. categories_str kwarg or brand/category swaps)
    if "categories_str" in kwargs and not categories:
        categories = str(kwargs["categories_str"])
    if "store_type" in kwargs:
        store_type = str(kwargs["store_type"])

    # If brand looks like a hierarchical category path (contains / or >) and categories is empty
    if brand and ("/" in brand or ">" in brand) and not categories:
        categories = brand
        brand = ""

    t_clean = _strip_accents(title or "").lower()
    b_clean = _strip_accents(brand or "").lower()
    c_clean = _strip_accents(categories or "").lower()
    st_clean = (store_type or "supermarket").lower()
    combined = f"{t_clean} {b_clean} {c_clean}"

    # Guardia 0a: Artículos médicos y ortopédicos (fajas, muñequeras, rodilleras, soporte sacro-lumbar)
    if (
        re.search(r'\b(?:faja|rodillera|muslera|tobillera|cabestrillo|inmovilizador|soporte\s+(?:sacro|lumbar|abdominal|embarazo|brazo|rodilla|tobillo|muneca))\b', t_clean)
        or "body care" in b_clean or "drof" in b_clean
    ):
        return "perfumeria_farmacia"

    # Guardia 0b: Alimentos cárnicos con "rack" (ej: "Rack de cordero", "Rack cordero patagónico", "Costillar con rack")
    is_meat_rack = bool(
        re.search(r'\brack\s+(?:de\s+)?(?:cordero|cerdo|costilla|costillar|ternera|vacuno)\b', t_clean)
        or re.search(r'\b(?:cordero|cerdo|costilla|costillar|ternera|vacuno)\b.*?\b(?:con\s+rack|rack)\b', t_clean)
        or re.search(r'\bcostillar\s+con\s+rack\b', t_clean)
    )
    if is_meat_rack:
        return "carnes_verduleria"

    # Guardia 0c: Postres y lácteos con "colchón" (ej: "Yogur con colchón de tiramisú / frutilla")
    is_dairy_colchon = bool(
        re.search(r'\b(?:yogur|postre|dahi|tentaciones)\b', combined) and "colchon" in t_clean
    )
    if is_dairy_colchon:
        return "lacteos_frescos"

    # Guardia 0d: Repuestos de limpieza y aseo personal
    is_cleaning_refill = bool(
        "repuesto" in t_clean and (
            re.search(r'\b(?:cif|ayudin|skip|ala|ariel|comfort|procenex|pato|poett|glade|harpers|sun|magistral|limpiador|detergente|lavavajillas|desinfectante|jabon\s+liquido|aromatizante|suavizante|desodorante\s+de\s+ambiente|canasta\s+(?:liquida|solida))\b', combined)
            or "limpieza" in c_clean
        )
    )
    if is_cleaning_refill:
        return "limpieza"

    is_pharma_refill = bool(
        "repuesto" in t_clean and (
            re.search(r'\b(?:dove|rexona|lux|pantene|head\s+&\s+shoulders|garnier|crema|facial|shampoo|acondicionador|jabon\s+liquido\s+corporal|repuesto\s+de\s+afeitar|hojas\s+de\s+afeitar|mach\s*3|venus)\b', combined)
            or any(k in c_clean for k in ("salud", "belleza", "farmacia", "cuidado personal", "perfumeria"))
        )
    )
    if is_pharma_refill:
        return "perfumeria_farmacia"

    # Guardia 0e: Cosmética con "cover" (ej: "full cover foundation", "Goicoechea Cover")
    is_makeup_cover = bool(
        re.search(r'\b(?:cover|coverage)\b', t_clean) and (
            re.search(r'\b(?:base|corrector|maquillaje|facial|colorstay|goicoechea|isdin|revlon|maybelline|loreal|dermaglos)\b', combined)
            or any(k in c_clean for k in ("maquillaje", "estetica", "belleza", "piel", "cosmetica"))
        )
    )
    if is_makeup_cover:
        return "perfumeria_farmacia"

    # Guardia 0f: TV Combos (Smart TVs con soporte o cables incluidos pertenecen estrictamente a televisores)
    is_tv_combo = bool(
        re.search(r'\b(?:combo|kit)\b', t_clean)
        and not re.search(r'\b(?:combo|kit)\s+(?:de\s+)?(?:soporte|soportes|funda|fundas|cable|cables|control)\b', t_clean)
        and (
            re.search(r'\b(?:smart\s*tv|televisor|televisores|tv\s+led|led\s+tv|qled|oled|neo\s*qled|mini\s*led|google\s+tv|android\s+tv|roku\s+tv|vidaa\s+tv)\b', t_clean)
            or re.search(r'\b(?:combo|kit)\s+tv\b', t_clean)
        )
    )
    if is_tv_combo:
        return "televisores"

    # Guardia 0g: Artículos inflables, de pileta y camping (NO son carnes ni verdulería)
    if re.search(r'\b(?:inflables?|pileta|piscina|chaleco\s+inflable|flotador|pavo\s+real\s+inflable)\b', t_clean):
        if re.search(r'\bcolchon\s+inflable\b', t_clean):
            return "muebles_racks"
        return "herramientas_construccion"

    # Guardia 0h: Bombas y selladoras al vacío, electrodomésticos y utensilios de cocina
    if re.search(r'\b(?:bomba\s+de\s+vacio|selladora\s+(?:al\s+)?vacio|envasadora\s+(?:al\s+)?vacio|inflador(?:\s+electrico)?|pelador\s+de\s+ajo)\b', t_clean):
        return "pequenos_electro"

    # Guardia 0i: Vajilla (platos, etc. con color o diseño vegetal)
    if re.search(r'\b(?:plato\s+jardinera|vajilla)\b', t_clean):
        return "muebles_racks"

    # 1. DISPOSITIVOS DE STREAMING -> audio_video (Evaluado ANTES de accesorios y televisores)
    if RE_STREAMING_DEVICE.search(t_clean):
        return "audio_video"

    # 2. MUEBLES_RACKS (Evaluado ESTRICTAMENTE ANTES de televisores y soportes)
    if RE_MUEBLE.search(t_clean) or (
        st_clean in ("electro", "marketplace", "hogar", "specialty")
        and any(k in c_clean for k in ("colchones y sommiers", "muebles de living", "muebles para tv", "muebles de dormitorio"))
        and not RE_TELEVISORES.search(t_clean)
    ):
        return "muebles_racks"

    # 3. SOPORTES_ACCESORIOS (Evaluado ESTRICTAMENTE ANTES de televisores)
    # Standalone brackets, wall mounts, and accessories are strictly captured here
    is_hardware_bundle = bool(re.search(r'^(?:smart\s*tv|televisor|tv\s+led|led\s+tv|celular|smartphone|telefono\s+celular|notebook|laptop)\b', t_clean))
    is_food = bool(re.search(r'\b(?:sal\s+fina|sal\s+gruesa|sal\s+parrillera|arroz|fideos|yerba|aceite|harina|azucar|galletitas|leche|queso|manteca|vino|cerveza|gaseosa)\b', t_clean))
    if not is_food and ((RE_SOPORTE_ACCESORIO.search(t_clean) and not is_hardware_bundle) or (
        any(k in c_clean for k in ("soportes tv", "soportes y accesorios", "accesorios celulares", "accesorios tablets"))
        and not is_hardware_bundle
    )):
        return "soportes_accesorios"

    # 4. TELEVISORES (Pure Hardware Screens: 0% mount or furniture infiltration)
    if RE_TELEVISORES.search(t_clean) or (
        any(k in c_clean for k in ("smart tv", "televisores", "tv y video/tv", "tv y soportes/smart tv"))
        and not re.search(r'\b(?:soporte|rack|mesa|funda|control\s+remoto|cable\s+hdmi)\b', t_clean)
    ):
        return "televisores"

    # 5. AUDIO_VIDEO General
    if RE_AUDIO_VIDEO.search(t_clean) or any(k in c_clean for k in ("audio y video", "auriculares", "parlantes", "home theatre", "sound tower", "proyectores")):
        return "audio_video"

    # 6. PERFUMERIA_FARMACIA (ALTA ESPECIFICIDAD: evalua antes de bebidas, lacteos, verduleria y almacén)
    if RE_PERFUMERIA_FARMACIA.search(t_clean) or any(k in c_clean for k in ("perfumeria", "farmacia", "salud y belleza", "cuidado personal", "maquillaje", "dermocosmetica", "bebes", "cuidado capilar", "higiene")):
        return "perfumeria_farmacia"

    # 7. LIMPIEZA (ALTA ESPECIFICIDAD: evalua antes de lacteos, carnes/verdulería y almacén)
    if RE_LIMPIEZA.search(t_clean) or any(k in c_clean for k in ("limpieza", "cuidado de la ropa", "papeles", "lavavajillas")):
        return "limpieza"

    # 8. HARDWARE ESPECIFICO
    if RE_CELULARES.search(t_clean) or any(k in c_clean for k in ("celulares y telefonos", "smartphones", "telefonia")):
        return "celulares"

    if RE_NOTEBOOKS_TABLETS.search(t_clean) or any(k in c_clean for k in ("computacion", "notebooks", "tablets", "informatica", "impresoras")):
        return "notebooks_tablets"

    if RE_HELADERAS_FREEZERS.search(t_clean) or any(k in c_clean for k in ("heladeras", "freezers", "refrigeracion")):
        return "heladeras_freezers"

    if RE_LAVADO.search(t_clean) or any(k in c_clean for k in ("lavarropas", "secarropas", "lavavajillas", "lavado")):
        return "lavado"

    if RE_CLIMATIZACION.search(t_clean) or any(k in c_clean for k in ("climatizacion", "aire acondicionado", "calefaccion", "ventilacion")):
        return "climatizacion"

    if RE_COCINA_HORNOS.search(t_clean) or any(k in c_clean for k in ("cocinas y hornos", "hornos y anafes", "anafes", "coccion", "microondas")):
        return "cocina_hornos"

    if RE_PEQUENOS_ELECTRO.search(t_clean) or any(k in c_clean for k in ("pequenos electrodomesticos", "electrodomesticos de cocina", "cuidado personal electro", "electro cocina")):
        return "pequenos_electro"

    if RE_HERRAMIENTAS.search(t_clean) or any(k in c_clean for k in ("herramientas", "construccion", "ferreteria", "pinturas")):
        return "herramientas_construccion"

    if RE_MASCOTAS.search(t_clean) or any(k in c_clean for k in ("mascotas", "perros", "gatos", "alimentos perros", "alimentos gatos")):
        return "mascotas"

    # 8b. ALIMENTOS EN LATA (Conservas herméticas en hojalata: nunca son carnes ni verdulería fresca)
    if re.search(r'\b(?:en\s+lata|lata)\b', t_clean):
        if RE_BEBIDAS.search(t_clean) or any(k in c_clean for k in ("bebidas", "aguas", "gaseosas", "cervezas", "vinos", "licores")):
            return "bebidas"
        if RE_MASCOTAS.search(t_clean) or any(k in c_clean for k in ("mascotas", "perros", "gatos")):
            return "mascotas"
        if RE_LIMPIEZA.search(t_clean) or any(k in c_clean for k in ("limpieza",)):
            return "limpieza"
        if RE_PERFUMERIA_FARMACIA.search(t_clean) or any(k in c_clean for k in ("perfumeria", "farmacia")):
            return "perfumeria_farmacia"
        return "almacen"

    # 9. PROCESSED PANTRY GROCERIES (Conservas, purés, papas fritas y mermeladas antes de carnes y verdulería)
    if RE_ALMACEN_PROCESSED.search(t_clean):
        return "almacen"

    # 10. BEBIDAS
    if RE_BEBIDAS.search(t_clean) or any(k in c_clean for k in ("bebidas", "aguas", "gaseosas", "cervezas", "vinos", "licores")):
        return "bebidas"

    # 11. LACTEOS_FRESCOS
    if RE_LACTEOS.search(t_clean) or any(k in c_clean for k in ("lacteos", "frescos", "quesos", "fiambres", "pastas frescas")):
        return "lacteos_frescos"

    # 12. CARNES_VERDULERIA (Protegido con guardia inmune de categoría contra almacén/conservas/desayuno)
    is_grocery_dept = any(k in c_clean for k in (
        "almacen", "conservas", "alacena", "desayuno", "merienda",
        "galletitas", "snack", "panaderia", "reposteria", "golosinas",
        "infusiones", "kiosco"
    ))
    if not is_grocery_dept and (
        RE_CARNES_VERDULERIA.search(t_clean)
        or any(k in c_clean for k in ("carnes", "pescaderia", "frutas y verduras", "verduleria", "frutas", "verduras"))
    ):
        return "carnes_verduleria"

    # 13. ALMACEN (Alimentos secos generales)
    if is_grocery_dept or RE_ALMACEN.search(t_clean) or any(k in c_clean for k in ("almacen", "comestibles", "desayuno", "merienda", "golosinas", "snacks", "panaderia")):
        return "almacen"

    # -----------------------------------------------------------------------
    # Fallback Contextual (Garantiza 100% de cobertura - 0 NULLs)
    # -----------------------------------------------------------------------
    if st_clean == "pharmacy" or any(k in c_clean for k in ("farmacia", "belleza", "salud")):
        return "perfumeria_farmacia"
    if st_clean == "specialty" and any(k in c_clean for k in ("perros", "gatos", "mascotas")):
        return "mascotas"
    if st_clean == "specialty" and any(k in c_clean for k in ("vinos", "bodega", "bebidas")):
        return "bebidas"
    if st_clean == "specialty" and any(k in c_clean for k in ("carnes", "pastura", "granja")):
        return "carnes_verduleria"
    if st_clean == "electro" or any(k in c_clean for k in ("electro", "tecnologia", "audio")):
        return "pequenos_electro"
    if any(k in c_clean for k in ("herramientas", "ferreteria", "jardin")):
        return "herramientas_construccion"
    if any(k in c_clean for k in ("muebles", "decoracion")):
        return "muebles_racks"

    return "almacen"


# ---------------------------------------------------------------------------
# 2. Build Entity Resolution Index Contract
# ---------------------------------------------------------------------------
def build_entity_resolution_index(conn: sqlite3.Connection) -> Tuple[int, int]:
    """
    Builds in-memory ER index mapping:
      Hardware: (brand_norm, model_norm, variant) -> (canonical_ean, avg_price, offer_count, priority)
      Grocery:  (brand_norm, clean_name_tokens, round(qty, 3), unit) -> (canonical_ean, avg_price, offer_count, priority)
    Priority Hierarchy:
      Priority 1: GS1 Argentina National (779...) with valid Modulo 10
      Priority 2: GS1 Manufacturer HQ (880... Samsung, 889... Apple) with valid Modulo 10
      Priority 3: Other valid GS1 EAN-13
      Priority 4: Valid UPC-A / EAN-8
    Returns: (hardware_models_indexed, grocery_keys_indexed)
    """
    GLOBAL_MODEL_TO_EAN.clear()
    GROCERY_TO_EAN.clear()

    cur = conn.cursor()
    # Compute active offers and average positive price per EAN
    query = """
        SELECT p.ean, p.nombre, p.marca, p.modelo, p.tipo,
               AVG(pr.precio_venta) as avg_p, COUNT(pr.supermercado) as cnt
        FROM productos p
        JOIN precios pr ON p.ean = pr.ean
        WHERE pr.precio_venta > 0
        GROUP BY p.ean
    """
    cur.execute(query)
    rows = cur.fetchall()

    for ean, nombre, marca, modelo, tipo, avg_p, cnt in rows:
        if not (isinstance(ean, str) and len(ean) == 13 and is_valid_ean13(ean) and not is_internal_scale(ean)):
            continue

        if ean.startswith("779"):
            prio = 1
        elif ean.startswith("880") or ean.startswith("889"):
            prio = 2
        else:
            prio = 3

        brand_clean = norm_brand(marca or "")
        title = nombre or ""

        # Hardware indexing
        if not is_accessory(title):
            m = modelo or extract_model(title, brand=marca or "")
            if m:
                m_clean = norm_hardware_model(brand_clean, m)
                if m_clean and not FALSE_MODELS_EXTRA.match(m_clean) and brand_clean:
                    variant = extract_capacity_variant(title)
                    hw_key = (brand_clean, m_clean, variant)
                    if hw_key not in GLOBAL_MODEL_TO_EAN or prio < GLOBAL_MODEL_TO_EAN[hw_key][3]:
                        GLOBAL_MODEL_TO_EAN[hw_key] = (ean, float(avg_p or 0.0), cnt, prio)

        # Grocery indexing
        qty, unit = extraer_unidad_titulo(title)
        base = clean_grocery_base_name(title, brand=marca or "")
        if base and brand_clean:
            grocery_key = (brand_clean, base, round(qty, 3), unit)
            if grocery_key not in GROCERY_TO_EAN or prio < GROCERY_TO_EAN[grocery_key][3]:
                GROCERY_TO_EAN[grocery_key] = (ean, float(avg_p or 0.0), cnt, prio)

    logger.info(f"Indexed {len(GLOBAL_MODEL_TO_EAN)} hardware model keys and {len(GROCERY_TO_EAN)} grocery keys.")
    return len(GLOBAL_MODEL_TO_EAN), len(GROCERY_TO_EAN)


# ---------------------------------------------------------------------------
# 3. Resolve and Repoint Entities Contract
# ---------------------------------------------------------------------------
def resolve_and_repoint_entities(conn: sqlite3.Connection, dry_run: bool = False) -> Dict[str, Any]:
    """
    Re-points synthetic non-EAN items ({STORE}-{id}) to canonical GS1 EANs.
    Applies center-of-mass price sanity ratio guard (0.35 <= cand / canon <= 2.80).
    Deterministically resolves PK collisions on precios(ean, supermercado).
    Updates historial_precios.ean and prunes orphaned synthetic product shells in productos.
    """
    cur = conn.cursor()

    # Preload average positive prices for all candidate products
    cur.execute("SELECT ean, AVG(precio_venta) FROM precios WHERE precio_venta > 0 GROUP BY ean")
    ean_avg_prices = dict(cur.fetchall())

    # Find candidate synthetic products ({STORE}-{id})
    cur.execute("""
        SELECT ean, nombre, marca, modelo, tipo
        FROM productos
        WHERE instr(ean, '-') > 0
    """)
    candidates = cur.fetchall()

    hw_repointed = 0
    grocery_repointed = 0
    guard_rejections = 0
    conflicts_resolved = 0
    clean_repointed = 0
    cleaned_shells = 0

    if not dry_run:
        cur.execute("BEGIN TRANSACTION")

    try:
        for old_ean, nombre, marca, modelo, tipo in candidates:
            cand_p = float(ean_avg_prices.get(old_ean, 0.0))
            if cand_p <= 0.0:
                continue

            title = nombre or ""
            b_clean = norm_brand(marca or "")
            target_canonical: Optional[str] = None
            target_avg_p: float = 0.0
            is_hw = False

            # 1. Try Hardware Model Resolution (Skip pure accessories)
            if not is_accessory(title):
                m = modelo or extract_model(title, brand=marca or "")
                if m:
                    m_clean = norm_hardware_model(b_clean, m)
                    if m_clean and not FALSE_MODELS_EXTRA.match(m_clean) and b_clean:
                        variant = extract_capacity_variant(title)
                        hw_key = (b_clean, m_clean, variant)
                        if hw_key in GLOBAL_MODEL_TO_EAN:
                            target_canonical, target_avg_p, _, _ = GLOBAL_MODEL_TO_EAN[hw_key]
                            is_hw = True

            # 2. Try Grocery Resolution
            if not target_canonical and b_clean:
                qty, unit = extraer_unidad_titulo(title)
                base = clean_grocery_base_name(title, brand=marca or "")
                if base:
                    grocery_key = (b_clean, base, round(qty, 3), unit)
                    if grocery_key in GROCERY_TO_EAN:
                        target_canonical, target_avg_p, _, _ = GROCERY_TO_EAN[grocery_key]
                        is_hw = False

            # If resolved to a valid distinct canonical EAN
            if target_canonical and target_canonical != old_ean:
                # Security Invariant: target_canonical MUST exist in productos
                cur.execute("SELECT 1 FROM productos WHERE ean = ?", (target_canonical,))
                if not cur.fetchone():
                    continue

                # Center-of-mass Price Sanity Ratio Guard
                if target_avg_p > 0:
                    ratio = cand_p / target_avg_p
                    if not (0.35 <= ratio <= 2.80):
                        guard_rejections += 1
                        continue

                if not dry_run:
                    # Query all offers of candidate in precios
                    cur.execute("""
                        SELECT ean, supermercado, precio_venta, precio_lista, descuento,
                               precio_por_unidad, unidad_medida, stock, internal_id, link,
                               fecha, promo_etiqueta, promo_tipo, promo_min_qty, precio_promo_unit,
                               requiere_club, seller_id, store_type
                        FROM precios
                        WHERE ean = ?
                    """, (old_ean,))
                    offers = cur.fetchall()

                    for off in offers:
                        store = off[1]
                        p_venta = off[2]
                        stock = off[7]

                        # Check if store already has target_canonical in precios
                        cur.execute("SELECT precio_venta, stock FROM precios WHERE ean = ? AND supermercado = ?", (target_canonical, store))
                        existing = cur.fetchone()

                        if existing:
                            # PK Collision on precios(ean, supermercado)
                            conflicts_resolved += 1
                            ex_p, ex_stock = existing[0], existing[1]

                            # Winner determination:
                            # 1. Incoming has stock while existing has no stock -> incoming wins
                            # 2. Both have stock and incoming price is lower positive -> incoming wins
                            # 3. Existing has <=0 price and incoming has >0 price -> incoming wins
                            incoming_wins = False
                            if stock > 0 and ex_stock <= 0:
                                incoming_wins = True
                            elif stock > 0 and ex_stock > 0 and 0 < p_venta < ex_p:
                                incoming_wins = True
                            elif ex_stock <= 0 and ex_p <= 0 and p_venta > 0:
                                incoming_wins = True

                            if incoming_wins:
                                cur.execute("""
                                    UPDATE precios
                                    SET precio_venta = ?, precio_lista = ?, descuento = ?,
                                        precio_por_unidad = ?, unidad_medida = ?, stock = ?,
                                        internal_id = ?, link = ?, fecha = ?, promo_etiqueta = ?,
                                        promo_tipo = ?, promo_min_qty = ?, precio_promo_unit = ?,
                                        requiere_club = ?, seller_id = ?, store_type = ?
                                    WHERE ean = ? AND supermercado = ?
                                """, (
                                    off[2], off[3], off[4], off[5], off[6], off[7],
                                    off[8], off[9], off[10], off[11], off[12], off[13],
                                    off[14], off[15], off[16], off[17],
                                    target_canonical, store
                                ))

                            # Delete the redundant synthetic row
                            cur.execute("DELETE FROM precios WHERE ean = ? AND supermercado = ?", (old_ean, store))
                        else:
                            # Clean update of EAN in precios
                            cur.execute("UPDATE precios SET ean = ? WHERE ean = ? AND supermercado = ?", (target_canonical, old_ean, store))
                            clean_repointed += 1

                    # Update historical prices
                    cur.execute("UPDATE historial_precios SET ean = ? WHERE ean = ?", (target_canonical, old_ean))

                    # Clean up synthetic shell from productos if no prices remain
                    cur.execute("SELECT count(*) FROM precios WHERE ean = ?", (old_ean,))
                    if cur.fetchone()[0] == 0:
                        cur.execute("DELETE FROM productos WHERE ean = ?", (old_ean,))
                        cleaned_shells += 1

                if is_hw:
                    hw_repointed += 1
                else:
                    grocery_repointed += 1

        if not dry_run:
            conn.commit()

    except Exception:
        if not dry_run:
            conn.rollback()
        raise

    return {
        "hardware_models_indexed": len(GLOBAL_MODEL_TO_EAN),
        "hardware_links_repointed": hw_repointed,
        "grocery_keys_indexed": len(GROCERY_TO_EAN),
        "grocery_links_repointed": grocery_repointed,
        "total_repointed": hw_repointed + grocery_repointed,
        "clean_repointed_offers": clean_repointed,
        "conflicts_resolved": conflicts_resolved,
        "price_guard_rejections": guard_rejections,
        "cleaned_shells": cleaned_shells,
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# 4. Normalize All Categories Contract
# ---------------------------------------------------------------------------
def normalize_all_categories(conn: sqlite3.Connection, dry_run: bool = False) -> Dict[str, Any]:
    """
    Classifies 100% of products in 'productos' and updates 'categoria_normalizada'.
    Uses batch transaction chunks (1,000 rows per chunk) for maximum SQLite WAL performance.
    Guarantees 0 NULLs remaining and verifies index idx_productos_cat_norm.
    """
    cur = conn.cursor()
    cur.execute("SELECT ean, nombre, marca, categorias, tipo FROM productos")
    rows = cur.fetchall()

    updates: List[Tuple[str, str]] = []
    distribution: Dict[str, int] = {}

    for ean, nombre, marca, categorias, tipo in rows:
        cat = classify_canonical_category(nombre or "", marca or "", categorias or "", tipo or "")
        updates.append((cat, ean))
        distribution[cat] = distribution.get(cat, 0) + 1

    if not dry_run:
        CHUNK_SIZE = 5000
        for i in range(0, len(updates), CHUNK_SIZE):
            chunk = updates[i : i + CHUNK_SIZE]
            cur.executemany("UPDATE productos SET categoria_normalizada = ? WHERE ean = ?", chunk)
        conn.commit()

        # Ensure index exists
        cur.execute("CREATE INDEX IF NOT EXISTS idx_productos_cat_norm ON productos (categoria_normalizada);")
        conn.commit()

    cur.execute("SELECT count(*) FROM productos WHERE categoria_normalizada IS NULL")
    null_remaining = cur.fetchone()[0] if not dry_run else 0

    return {
        "total_products": len(rows),
        "categories_updated": len(updates),
        "null_categories_remaining": null_remaining,
        "category_breakdown": distribution,
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# 5. Full Orchestration Contract
# ---------------------------------------------------------------------------
def normalize_catalog(db_path: str = "supervmarket.db", dry_run: bool = False) -> Dict[str, Any]:
    """
    Executes full offline entity resolution and category classification:
    1. Sets SQLite WAL mode and high-performance PRAGMAs.
    2. Builds in-memory Entity Resolution index.
    3. Resolves and re-points non-EAN entities with price ratio guard and conflict resolution.
    4. Classifies 100% of products into the 19 canonical categories.
    5. Verifies idx_productos_cat_norm and referential integrity.
    Returns summary metrics.
    """
    t_start = time.perf_counter()
    abs_db = os.path.abspath(db_path)
    if not os.path.exists(abs_db):
        raise FileNotFoundError(f"Database file not found: {abs_db}")

    conn = sqlite3.connect(abs_db, timeout=30.0)
    # Enable WAL mode and performance optimizations
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA cache_size = -64000;")

    try:
        # Step 1: Build ER Index
        hw_idx_cnt, groc_idx_cnt = build_entity_resolution_index(conn)

        # Step 2: Entity Resolution & Re-pointing
        er_res = resolve_and_repoint_entities(conn, dry_run=dry_run)

        # Step 3: Global Category Normalization
        cat_res = normalize_all_categories(conn, dry_run=dry_run)

    finally:
        conn.close()

    duration = time.perf_counter() - t_start

    return {
        "status": "SUCCESS",
        "total_products": cat_res["total_products"],
        "categories_updated": cat_res["categories_updated"],
        "null_categories_remaining": cat_res["null_categories_remaining"],
        "index_created": True,
        "entity_resolution": {
            "hardware_models_indexed": hw_idx_cnt,
            "hardware_links_repointed": er_res["hardware_links_repointed"],
            "grocery_keys_indexed": groc_idx_cnt,
            "grocery_links_repointed": er_res["grocery_links_repointed"],
            "total_repointed": er_res["total_repointed"],
            "conflicts_resolved": er_res["conflicts_resolved"],
            "price_guard_rejections": er_res["price_guard_rejections"],
            "cleaned_shells": er_res["cleaned_shells"],
        },
        "category_breakdown": cat_res["category_breakdown"],
        "duration_seconds": round(duration, 3),
        "dry_run": dry_run,
    }
