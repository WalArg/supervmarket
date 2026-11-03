"""
Normalization Engine for SuperVmarket.
Provides GS1 EAN-13 Modulo 10 check digit validation, UPC-A / GTIN-14 universal conversion,
GS1 prefix routing (internal scale vs global), prioritized regex model extraction across categories,
regional suffix stripping, hardware capacity variant preservation, and accessory isolation guards.
"""

import re
import unicodedata
from typing import Optional, Tuple, Literal, TypedDict

BarcodeStatus = Literal[
    "VALID_EAN13",          # Valid GS1 EAN-13 with correct Modulo 10 check digit
    "INTERNAL_STORE_CODE",  # Prefixes 20-29 (in-store scale variable-weight code)
    "INVALID_CHECKSUM",     # 13 numeric digits but failed Modulo 10 check digit
    "NON_STANDARD",         # Length != 13 or contains non-standard attributes
    "NON_NUMERIC",          # Contains non-numeric characters
    "EMPTY",                # Empty or null barcode
]

IdentityClassification = Literal[
    "GLOBAL_GTIN",          # Verified universal commercial barcode
    "CANONICAL_MODEL",      # Verified electro/appliance/tech brand + model
    "ACCESSORY",            # Quarantined accessory or replacement part
    "INTERNAL_SCALE",       # Variable-weight supermarket item
    "FALLBACK_ITEM",        # Unidentified item grouped by store/title
]


def _strip_accents(text: str) -> str:
    """Removes diacritics/accents from a string."""
    if not text:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", str(text))
        if unicodedata.category(c) != "Mn"
    )


# ---------------------------------------------------------------------------
# 1. GS1 EAN-13 Modulo 10 Check Digit & Barcode Conversion
# ---------------------------------------------------------------------------

def ean13_check_digit(digits12: str) -> int:
    """Calculates GS1 Modulo 10 check digit for 12 numeric digits."""
    if not (isinstance(digits12, str) and len(digits12) == 12 and digits12.isdigit()):
        raise ValueError(f"Expected 12 numeric digits, got '{digits12}'")
    odd_sum = sum(int(digits12[i]) for i in range(0, 12, 2))
    even_sum = sum(int(digits12[i]) for i in range(1, 12, 2))
    total = odd_sum + (even_sum * 3)
    return (10 - (total % 10)) % 10


def is_valid_ean13(ean: str) -> bool:
    """Validates whether a string is a valid GS1 EAN-13 code with correct Modulo 10 check digit."""
    if not (isinstance(ean, str) and len(ean) == 13 and ean.isdigit()):
        return False
    return int(ean[12]) == ean13_check_digit(ean[:12])


def validate_ean13(ean: str) -> bool:
    """Alias for is_valid_ean13."""
    return is_valid_ean13(ean)


def is_internal_scale(ean: str) -> bool:
    """Checks whether an EAN barcode belongs to GS1 internal scale variable-weight range (prefixes 20-29)."""
    if not ean or not isinstance(ean, str):
        return False
    clean = re.sub(r'[\s~\-_]+', '', ean)
    if len(clean) == 13 and clean.isdigit():
        return clean[:2] in ("20", "21", "22", "23", "24", "25", "26", "27", "28", "29")
    return False


def normalize_ean(raw_ean: str) -> str:
    """
    Cleans raw barcode string, removes whitespace/tildes/hyphens,
    and converts 12-digit UPC-A (prepends '0') or 14-digit GTIN-14 with leading '0' (strips '0').
    Returns 13-digit EAN if valid/converted, or sanitized string.
    """
    if not raw_ean:
        return ""
    cleaned = re.sub(r'[\s~\-_]+', '', str(raw_ean))
    if not cleaned.isdigit():
        return cleaned

    # Case A: 12-digit UPC-A -> Prepend '0'
    if len(cleaned) == 12:
        cleaned = "0" + cleaned
    # Case B: 14-digit GTIN-14 with leading '0' -> Strip leading '0'
    elif len(cleaned) == 14 and cleaned.startswith("0"):
        cleaned = cleaned[1:]

    return cleaned


def normalize_barcode(raw_barcode: str) -> Tuple[str, BarcodeStatus]:
    """
    Sanitizes raw barcode and classifies it.
    Returns (normalized_code, status_classification).
    """
    if not raw_barcode:
        return ("", "EMPTY")

    cleaned = re.sub(r'[\s~\-_]+', '', str(raw_barcode))
    if not cleaned.isdigit():
        return (cleaned, "NON_NUMERIC")

    if len(cleaned) == 12:
        cleaned = "0" + cleaned
    elif len(cleaned) == 14 and cleaned.startswith("0"):
        cleaned = cleaned[1:]

    if len(cleaned) == 13:
        if cleaned[:2] in ("20", "21", "22", "23", "24", "25", "26", "27", "28", "29"):
            return (cleaned, "INTERNAL_STORE_CODE")
        if is_valid_ean13(cleaned):
            return (cleaned, "VALID_EAN13")
        else:
            return (cleaned, "INVALID_CHECKSUM")

    return (cleaned, "NON_STANDARD")


# ---------------------------------------------------------------------------
# 2. False Specifications & Regional Suffix Regexes
# ---------------------------------------------------------------------------

FALSE_SPECS_RE = re.compile(
    r'^(?:\d+(?:[.,]\d+)?|\d+/\d+)?\s*'
    r'(?:W|WATTS?|V|VOLTS?|VLT|HZ|GHZ|MHZ|KG|KGS|KILOS?|G|GR|GRS|L|LT|LTS|LITROS?|CC|CM3|ML|'
    r'RPM|PA|KPA|BAR|BTU|FRIG|FRIGORIAS?|CAL|KCAL|'
    r'GB|TB|MB|RAM|ROM|SSD|HDD|MAH|AMP|AH|A|'
    r'CUOTAS?|PAGOS?|MESES?|FPS|DPI|MP|MPX|MEGAPIXELES?|'
    r'CM|MM|MTS?|METROS?|PULGADAS?|PULG|PLG|\"|\'\'|CV|HP|'
    r'K|4K|8K|FHD|UHD|HD|OLED|QLED|LED|(?:SMART|GOOGLE|ANDROID|ROKU|APPLE)?\s*TV|SMART|TV|PRO|MAX|PLUS|MINI|LITE|ECO|INVERTER|FRIO|CALOR)$',
    re.IGNORECASE,
)

REGIONAL_SUFFIX_RE = re.compile(
    r'(?:/77|/10|/15|/00|/90|/01|/DS|-DS|GCZB|PSA|PSB|SRA|-KA1AR|-KB1AR|AR)$',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# 3. Storage & RAM Variant Extractor
# ---------------------------------------------------------------------------

STORAGE_VARIANT_RE = re.compile(
    r'\b(32|64|128|256|512)\s*(?:GB|GIGABYTES?|GIGAS?)\b',
    re.IGNORECASE,
)
TERABYTE_VARIANT_RE = re.compile(
    r'\b(1|2)\s*(?:TB|TERABYTES?|TERAS?)\b',
    re.IGNORECASE,
)


def extract_capacity_variant(title: str) -> str:
    """Extracts hardware storage or memory variant (_128GB, _256GB, _512GB, _1TB)."""
    if not title:
        return ""
    m = STORAGE_VARIANT_RE.search(title)
    if m:
        return f"{m.group(1)}GB"
    m_tb = TERABYTE_VARIANT_RE.search(title)
    if m_tb:
        return f"{m_tb.group(1)}TB"
    return ""


# ---------------------------------------------------------------------------
# 4. Accessory Isolation Filter
# ---------------------------------------------------------------------------

ACCESSORY_KEYWORDS = (
    # Covers, cases & sleeves
    "funda", "fundas", "funda para", "funda protectora", "funda silicona", "funda antigolpe",
    "case", "cases", "case para", "case silicona", "case protector", "case antigolpe", "hard case",
    "cover", "covers", "cover para", "smart cover",
    "estuche", "estuches", "estuche para", "estuche rigido", "estuche protector", "estuche silicona",
    # Screen protection
    "vidrio", "vidrios", "vidrio templado", "vidrio 9d", "vidrio protector", "cristal templado", "templado 9d",
    "protector de pantalla", "protector pantalla", "protector para pantalla",
    "film protector", "film hidrogel", "hidrogel para", "lamina protectora",
    # Mounts and stands
    "soporte", "soportes", "soporte de pared", "soporte para tv", "soporte tv",
    "soporte fijo", "soporte movil", "soporte articulado", "soporte inclinable",
    "soporte de mesa", "soporte brazo", "soporte para celular", "soporte auto",
    # Remotes & controllers
    "control remoto",
    # Cables
    "cable", "cables", "cable hdmi", "cable usb", "cable tipo c", "cable lightning", "cable de datos",
    "cable de carga", "cable cargador", "cable auxiliar", "cable optico",
    # Chargers & power supplies
    "cargador", "cargadores", "cargador para", "cargador carga rapida", "cargador rapido",
    "cargador turbo", "cargador original", "cargador de pared", "cargador de auto",
    "cargador portatil", "cargador usb", "cargador inalambrico", "cargador wireless",
    "cargador 25w", "cargador 45w", "cargador 67w", "fuente de alimentacion",
    # Parts, filters, bags, straps
    "repuesto para", "repuesto de", "repuesto", "repuestos",
    "filtro", "filtros", "filtro para", "filtro de repuesto",
    "bolsa", "bolsas", "bolsa para", "bolsa de aspiradora", "bolsa aspiradora", "bolsas aspiradora",
    "adaptador", "adaptadores",
    "correa", "correas", "correa para", "malla", "mallas", "malla para", "malla silicona",
    "bateria para", "bateria de repuesto", "bateria taladro", "modulo pantalla"
)

BUNDLE_INCLUSION_RE = re.compile(
    r'(?:c/\s*|\b(?:con|incluye|incluyen|incluido|incluida|incl|mas|y)\b|\+)\s*'
    r'(?:un\s+|una\s+|el\s+|la\s+|\d+\s+)?'
    r'(?:cargador(?:es)?|funda(?:s)?|estuche(?:s)?|case(?:s)?|cable(?:s)?|'
    r'control(?:\s+remoto)?|soporte(?:\s+(?:de\s+mesa|de\s+pared|fijo|incluido))?|'
    r'vidrio(?:\s+templado)?|film(?:\s+protector)?|adaptador(?:es)?|'
    r'baterias?|baterías?|bolsas?)\b',
    re.IGNORECASE,
)

ACCESSORY_PREFIX_RE = re.compile(
    r'^(?:funda|fundas|case|cases|cover|covers|estuche|estuches|vidrio|vidrios|cristal|film|'
    r'protector(?:\s+de\s+pantalla|\s+pantalla)?|soporte|soportes|'
    r'control\s+remoto|cable|cables|cargador|cargadores|repuesto|repuestos|'
    r'filtro|filtros|bolsa|bolsas|malla|mallas|correa|correas|'
    r'adaptador|adaptadores|modulo\s+pantalla|pantalla\s+modulo|bateria\s+(?!de\s+cocina))\b',
    re.IGNORECASE,
)

ACC_INTERLEAVED_BRAND_RE = re.compile(
    r'\b(?:funda|case|cover|estuche|vidrio|cristal|film|soporte|cable|cargador|repuesto|filtro|bolsa|malla|correa|adaptador|bateria\s+(?!de\s+cocina))\s+(?:de\s+)?(?:samsung|apple|motorola|xiaomi|philips|bosch|dewalt|lenovo|hp|lg|oster|moulinex|sony)\b',
    re.IGNORECASE,
)


def is_accessory(title: str) -> bool:
    """Detects whether product is an accessory or replacement part to isolate from main hardware."""
    if not title:
        return False
    norm = _strip_accents(title)
    cleaned_for_check = BUNDLE_INCLUSION_RE.sub(" ", norm)
    norm_clean = re.sub(r'[^a-z0-9]+', ' ', cleaned_for_check.lower()).strip()
    t_lower = f" {norm_clean} "

    if ACCESSORY_PREFIX_RE.match(norm_clean):
        return True

    if ACC_INTERLEAVED_BRAND_RE.search(norm_clean):
        return True

    for kw in ACCESSORY_KEYWORDS:
        kw_clean = f" {kw.strip()} "
        if kw_clean in t_lower:
            return True
        if re.search(rf"\b{re.escape(kw)}\b", cleaned_for_check, re.IGNORECASE):
            return True
    return False


# ---------------------------------------------------------------------------
# 5. Prioritized Model Extractor Patterns
# ---------------------------------------------------------------------------

MODEL_PATTERNS = [
    # 1. Special named series (Drean Next, Drean QV, Bosch GSB, Motorola Edge)
    re.compile(r'\b(NEXT\s+\d+\.\d+(?:\s*[A-Z])?)\b', re.IGNORECASE),
    re.compile(r'\b(QV\s+\d+\.\d+)\b', re.IGNORECASE),
    re.compile(r'\b(GSB\s+\d+[- ]?[A-Z0-9]+)\b', re.IGNORECASE),
    re.compile(r'\b(EDGE\s+\d{2}(?:\s+(?:NEO|PRO|ULTRA|FUSION|LITE|PLUS))?)\b', re.IGNORECASE),

    # 2. Hyphenated technical models (e.g. SM-A546E, 15-fc0001la, MSAGFC-09CRDN8)
    re.compile(r'\b([A-Z0-9]{1,6}-[A-Z0-9]{2,8}(?:/[A-Z0-9]{2,4})?)\b', re.IGNORECASE),

    # 3. TV models: screen size (2-3 digits) + letters (1-5) + series (2-5 alphanumeric) + optional suffix
    # 55PUD7408/77, 50UR7800PSB, 55QNED80SRA, 50P735, DK50X7500, PLD50US22, 553EPQ0901F
    re.compile(r'\b([0-9]{2,3}[A-Z]{1,5}[0-9]{2,5}(?:/[0-9]{2,3}|[A-Z0-9]+)?)\b', re.IGNORECASE),

    # 4. Alphanumeric appliances / tech models: letters + digits + alphanumeric
    # UN50CU7000, WRM57K2, WFB57DW, WZC12A, ATVC1521P, HDR400F11S, BSI35WCG, PHIN32HA4BN, EZ401858, HD9200/90, QP1424/10, DWE4010, NP960QFG
    re.compile(r'\b([A-Z]{1,5}\d{2,5}[A-Z0-9]*(?:/\d{2,3})?)\b', re.IGNORECASE),

    # 5. Number followed by letters & numbers (e.g. Lenovo 15AMN7, 14IGL05)
    re.compile(r'\b(\d{2}[A-Z]{3,4}\d{1,2})\b', re.IGNORECASE),

    # 6. Mobile series shorthand (A04, A14, A34, A54, G54, G84)
    re.compile(r'\b([AG]\d{2}[A-Z]?)\b', re.IGNORECASE),

    # 7. 7-digit numeric item / model reference (e.g. Robust 1450277)
    re.compile(r'\b(\d{7})\b'),
]


def _is_numeric_or_decimal(tok: str) -> bool:
    return bool(re.match(r'^\d+(?:[.,]\d+)?$', tok)) and len(tok) < 7


def _clean_candidate_model(raw: str, brand: str = "") -> str:
    """Cleans, normalizes, and validates candidate model code."""
    if not raw or not isinstance(raw, str):
        return ""
    raw_s = raw.strip().strip("[] ")
    if not raw_s:
        return ""
    if FALSE_SPECS_RE.fullmatch(raw_s):
        return ""
    cand = raw_s.strip("'\" ")
    if len(cand) < 2 or len(cand) > 35:
        return ""
    if (cand.isdigit() or _is_numeric_or_decimal(cand)) and len(cand) < 7:
        return ""
    if brand and cand.upper() == brand.strip().upper():
        return ""
    if FALSE_SPECS_RE.fullmatch(cand):
        return ""
    tokens = cand.split()
    if len(tokens) > 1 and all(FALSE_SPECS_RE.fullmatch(t) or _is_numeric_or_decimal(t) for t in tokens):
        return ""
    cand_low = cand.lower()
    if cand_low in ("blanco", "negro", "gris", "silver", "inox", "azul", "rojo", "generico", "sin marca", "n/a"):
        return ""
    cand_clean = REGIONAL_SUFFIX_RE.sub("", cand).strip()
    return cand_clean


def extract_model_from_metadata(prod: dict, sku: dict = None, brand: str = "") -> str:
    """Extracts manufacturer model from structured VTEX or retail attributes."""
    if not isinstance(prod, dict):
        return ""
    candidates: list[str] = []

    for key in ("productReference", "productReferenceCode"):
        val = prod.get(key)
        if val and isinstance(val, str):
            candidates.append(val)

    if isinstance(sku, dict):
        ref_ids = sku.get("referenceId")
        if isinstance(ref_ids, list):
            for r in ref_ids:
                if isinstance(r, dict) and r.get("Value"):
                    candidates.append(str(r["Value"]))
                elif isinstance(r, str):
                    candidates.append(r)
        elif isinstance(ref_ids, str):
            candidates.append(ref_ids)

    for obj in (prod, sku):
        if not isinstance(obj, dict):
            continue
        for m_key in ("Modelo", "modelo", "Model", "model"):
            m_val = obj.get(m_key)
            if isinstance(m_val, list) and m_val:
                candidates.extend(str(x) for x in m_val if x)
            elif isinstance(m_val, str) and m_val:
                candidates.append(m_val)

    all_specs = prod.get("allSpecifications") or []
    if isinstance(all_specs, list):
        for spec_name in all_specs:
            if isinstance(spec_name, str):
                sn_low = spec_name.lower()
                if any(k in sn_low for k in ("modelo", "model", "referencia", "part number", "codigo de modelo")):
                    spec_vals = prod.get(spec_name)
                    if isinstance(spec_vals, list) and spec_vals:
                        candidates.extend(str(x) for x in spec_vals if x)
                    elif isinstance(spec_vals, str) and spec_vals:
                        candidates.append(spec_vals)

    spec_groups = prod.get("specificationGroups") or []
    if isinstance(spec_groups, list):
        for sg in spec_groups:
            if isinstance(sg, dict):
                specs = sg.get("specifications") or []
                if isinstance(specs, list):
                    for s in specs:
                        if isinstance(s, dict):
                            s_name = str(s.get("name") or "").lower()
                            if any(k in s_name for k in ("modelo", "model", "referencia")):
                                s_vals = s.get("values") or []
                                if isinstance(s_vals, list):
                                    candidates.extend(str(x) for x in s_vals if x)

    for cand in candidates:
        cleaned = _clean_candidate_model(cand, brand=brand)
        if cleaned:
            if cleaned.isdigit() and len(cleaned) < 7:
                continue
            return cleaned
    return ""


def extract_model_from_title(title: str, brand: str = "") -> str:
    """Extracts manufacturer model from title using prioritized patterns."""
    if not title:
        return ""
    for pat in MODEL_PATTERNS:
        matches = pat.findall(title)
        for m in matches:
            m_clean = m.strip() if isinstance(m, str) else m[0].strip()
            if FALSE_SPECS_RE.fullmatch(m_clean):
                continue
            if brand and m_clean.upper() == brand.upper():
                continue
            base_m = REGIONAL_SUFFIX_RE.sub('', m_clean).strip()
            if base_m:
                return base_m
    return ""


def extract_model(
    title: str,
    brand: str = "",
    specs: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> str:
    """
    Extracts manufacturer model string using metadata first, then prioritized title regex.
    """
    if metadata and isinstance(metadata, dict):
        m = extract_model_from_metadata(metadata, sku=specs, brand=brand)
        if m:
            return m
    return extract_model_from_title(title, brand=brand)


def canonical_model_key(brand: str, model: str, variant: str = "") -> str:
    """
    Formulates canonical brand + model identity key:
    MODEL_{BRAND}_{MODEL}[_{VARIANT}]
    """
    if not model:
        return ""
    b_norm = re.sub(r'[^A-Z0-9]', '', brand.upper()) if brand else "GENERIC"
    m_norm = re.sub(r'[^A-Z0-9]', '', model.upper())
    key = f"MODEL_{b_norm}_{m_norm}"
    if variant:
        v_norm = re.sub(r'[^A-Z0-9]', '', variant.upper())
        if v_norm:
            key += f"_{v_norm}"
    return key


def extract_canonical_model(
    prod: dict,
    sku: dict,
    title: str,
    brand: str = "",
) -> Tuple[str, str]:
    """
    Returns (base_model, canonical_model_key) with capacity variant and accessory quarantine.
    """
    if is_accessory(title):
        clean_title = re.sub(r'[^A-Z0-9]', '', title.upper())[:30]
        return "", f"ACC_{clean_title}"

    model = extract_model_from_metadata(prod, sku, brand=brand)
    if not model:
        model = extract_model_from_title(title, brand=brand)

    if not model:
        return "", ""

    variant = extract_capacity_variant(title)
    canon_key = canonical_model_key(brand, model, variant)
    return model, canon_key


def canonical_identity(
    title: str,
    brand: str = "",
    store: str = "Store",
    raw_ean: str = "",
) -> Tuple[str, bool, str]:
    """
    Formulates canonical product identity key.
    Returns: (canonical_key, is_accessory, classification)
    """
    # Guard 1: Accessory isolation
    if is_accessory(title):
        clean_toks = re.sub(r'[^A-Z0-9]', '', title.upper())[:30]
        st_clean = re.sub(r'[^A-Z0-9]', '', store.upper())
        acc_key = f"ACC_{clean_toks}_{st_clean}"
        return (acc_key, True, "ACCESSORY")

    # Guard 2: EAN-13 validation and prefix routing
    norm_ean, ean_status = normalize_barcode(raw_ean)
    if ean_status == "VALID_EAN13":
        return (f"EAN_{norm_ean}", False, "GLOBAL_GTIN")

    # Model extraction for tech/appliances/home
    raw_m = extract_model(title, brand)
    var = extract_capacity_variant(title)

    b_norm = re.sub(r'[^A-Z0-9]', '', brand.upper()) if brand else "GENERIC"
    m_norm = re.sub(r'[^A-Z0-9]', '', raw_m.upper()) if raw_m else ""

    if m_norm:
        key = f"MODEL_{b_norm}_{m_norm}"
        if var:
            key += f"_{var}"
        return (key, False, "CANONICAL_MODEL")

    # Fallback when neither valid EAN nor model can be extracted
    clean_title = re.sub(r'[^A-Z0-9]', '', title.upper())[:20]
    return (f"ITEM_{b_norm}_{clean_title}", False, "FALLBACK_ITEM")


def classify_product_type(cats_str: str, store_type: str = "supermarket") -> str:
    """Classifies product vertical or type from category hierarchy and store context."""
    cats_low = _strip_accents(cats_str or "").lower()
    if any(k in cats_low for k in ("tecnologia", "electro", "informatica", "celular", "audio", "video", "tv", "climatizacion")):
        return "electro"
    if any(k in cats_low for k in ("herramientas", "construccion", "ferreteria", "pintura")):
        return "ferreteria"
    if any(k in cats_low for k in ("muebles", "colchones", "hogar", "bazar", "decoracion", "jardin")):
        return "hogar"
    if any(k in cats_low for k in ("perfumeria", "farmacia", "belleza", "cuidado personal", "dermocosmetica")):
        return "pharmacy"
    if any(k in cats_low for k in ("mascotas", "perros", "gatos")):
        return "specialty"
    if store_type in ("electro", "marketplace", "specialty", "pharmacy"):
        return store_type
    return "supermarket"
