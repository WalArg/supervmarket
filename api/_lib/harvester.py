"""api/_lib/harvester.py

Harvester Masivo Multitienda para SuperVmarket.
Soporta:
1. VTEX Category Tree Crawler (árbol jerárquico vía /pub/category/tree/2 down to leaf IDs)
2. VTEX Paged Category Search (fq=C:{cat_id}) evitando el límite de 2500 ítems
3. Semillero departamental canónico de 100 consultas (60 súper/farmacia/mascotas + 40 electro/tech)
4. Coto Digital (Oracle Endeca JSON API con unión de atributos externos e internos)
5. Shopify REST API (/products.json?limit=250&page={page})
6. Tiendanube microdata (JSON-LD Schema.org Product)
7. Rate limiting per-domain (asyncio.Semaphore(2)), domain delay (200ms) y 3x backoff exponencial
8. Zero-Drop Invariant: preservación de 100% de productos y generación determinística
   de claves sintéticas {STORE_SLUG}-{external_id} para ítems sin EAN-13 GS1.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
import html
import json
import logging
import re
import time
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, AsyncIterator, Dict, List, Optional, Set, Tuple, TypedDict

import httpx

from .normalization import is_internal_scale, is_valid_ean13, normalize_ean
from .stores import (
    STORE_REGISTRY,
    VTEX_DOMAINS,
    VTEX_SALES_CHANNELS,
    StoreMeta,
    get_store_meta,
    sales_channel,
    store_vertical,
)

logger = logging.getLogger("supervmarket.harvester")

# ---------------------------------------------------------------------------
# TypedDicts & Constants
# ---------------------------------------------------------------------------

class HarvesterItem(TypedDict):
    store_name: str
    external_id: str
    ean_raw: str
    title_raw: str
    brand_raw: str
    categories_raw: str
    link_raw: str
    image_raw: str
    price_raw: float
    list_price_raw: float
    stock_raw: int
    seller_id_raw: str
    raw_json: str


# 100 Canonical Departmental Seeds (60 Grocery/Pharmacy/Pets + 40 Electro/Tech/Home)
DEPARTMENTAL_SEEDS: list[str] = [
    # Groceries & Food (20)
    "leche", "cafe", "yerba", "azucar", "fideos", "arroz", "aceite", "harina", "atun", "galletitas",
    "queso", "yogur", "manteca", "dulce de leche", "te", "cacao", "mayonesa", "mostaza", "mermelada", "pure de tomate",
    # Beverages & Alcohol (10)
    "gaseosa", "cerveza", "vino", "agua mineral", "jugo", "fernet", "aperitivo", "whisky", "gin", "vodka",
    # Cleaning & Home (10)
    "detergente", "lavandina", "suavizante", "jabon para la ropa", "papel higienico", "rollos de cocina",
    "limpiador piso", "desinfectante", "esponja", "bolsas de residuo",
    # Pharmacy & Personal Care (10)
    "shampoo", "acondicionador", "jabon", "pasta dental", "desodorante", "panales", "toallitas humedas",
    "toallitas femeninas", "protector solar", "repelente",
    # Pets (10)
    "alimento para perros", "alimento para gatos", "piedras sanitarias", "snacks para perros", "snacks para gatos",
    "antiparasitario", "pipeta", "colchoneta perro", "rascador", "shampoo perro",
    # Televisions & Audio (10)
    "smart tv", "televisor", "tv 43", "tv 50", "tv 55", "tv 65", "soundbar", "auriculares bluetooth",
    "parlante bluetooth", "microcomponente",
    # Smartphones & Computing (10)
    "celular", "smartphone", "samsung galaxy", "motorola", "iphone", "notebook", "laptop", "tablet", "monitor", "impresora",
    # Large Appliances (10)
    "heladera", "heladera no frost", "lavarropas", "lavarropas automatico", "secarropas", "lavavajillas",
    "freezer", "cocina a gas", "horno empotrable", "termotanque",
    # Small Appliances (5)
    "microondas", "freidora de aire", "cafetera", "pava electrica", "licuadora",
    # Climate & Tools (5)
    "aire acondicionado", "ventilador", "estufa", "taladro", "hidrolavadora",
]

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Rate Limiting & Networking State
# ---------------------------------------------------------------------------

_HOST_SEMAPHORES: dict[str, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(2))
_LAST_REQUEST_TIME: dict[str, float] = defaultdict(float)
_MIN_DOMAIN_INTERVAL: float = 0.20  # 200ms per domain

def _strip_accents(text: str) -> str:
    if not text:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", str(text))
        if unicodedata.category(c) != "Mn"
    )

def make_store_slug(store_name: str) -> str:
    clean = re.sub(r"[^A-Z0-9]", "", _strip_accents(store_name).upper())
    return clean or "STORE"

def resolve_product_ean(store_name: str, external_id: str, ean_raw: str) -> str:
    """
    Zero-drop invariant barcode resolver:
    1. Returns normalized EAN if valid GS1 EAN-13, EAN-8, or converted 12-digit UPC.
    2. Otherwise, returns a deterministic synthetic key `{STORE_SLUG}-{external_id}`.
    """
    cleaned_ean = normalize_ean(ean_raw) if ean_raw else ""
    if cleaned_ean:
        if len(cleaned_ean) == 13 and is_valid_ean13(cleaned_ean) and not is_internal_scale(cleaned_ean):
            return cleaned_ean
        if len(cleaned_ean) == 8 and cleaned_ean.isdigit():
            return cleaned_ean

    # Generate synthetic key
    slug = make_store_slug(store_name)
    clean_ext = re.sub(r"[^A-Za-z0-9_-]", "", str(external_id).strip())
    if not clean_ext:
        clean_ext = str(int(time.time() * 1000))
    return f"{slug}-{clean_ext}"


async def _rate_limited_request(
    client: httpx.AsyncClient,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 20.0,
    max_retries: int = 3,
) -> Optional[httpx.Response]:
    """
    Executes an HTTP GET with per-domain semaphore, mandatory 200ms domain delay,
    and 3-step exponential backoff on HTTP 429 / 5xx.
    """
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc or "default"

    req_headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
    }
    if headers:
        req_headers.update(headers)

    for attempt in range(max_retries + 1):
        async with _HOST_SEMAPHORES[host]:
            # Enforce minimum domain interval
            now = time.time()
            elapsed = now - _LAST_REQUEST_TIME[host]
            if elapsed < _MIN_DOMAIN_INTERVAL:
                await asyncio.sleep(_MIN_DOMAIN_INTERVAL - elapsed)
            _LAST_REQUEST_TIME[host] = time.time()

            try:
                resp = await client.get(url, headers=req_headers, params=params, timeout=timeout)
                if resp.status_code in (200, 206):
                    return resp
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt < max_retries:
                        backoff = 1.0 * (2 ** attempt)
                        logger.warning(
                            "HTTP %s for %s (attempt %d/%d). Backing off %.1fs",
                            resp.status_code, url, attempt + 1, max_retries, backoff
                        )
                        await asyncio.sleep(backoff)
                        continue
                if resp.status_code == 404:
                    return None
                logger.debug("Request to %s returned unexpected HTTP %s", url, resp.status_code)
                return resp
            except (httpx.TimeoutException, httpx.NetworkError) as err:
                if attempt < max_retries:
                    backoff = 1.0 * (2 ** attempt)
                    logger.warning("Network error on %s: %s. Retrying in %.1fs", url, err, backoff)
                    await asyncio.sleep(backoff)
                    continue
                logger.warning("Failed all retries for %s: %s", url, err)
                return None
    return None


# ---------------------------------------------------------------------------
# VTEX Connector
# ---------------------------------------------------------------------------

def _extract_vtex_leaf_ids(
    category_nodes: list[dict],
    max_depth: int = 3,
) -> list[tuple[str, str]]:
    """Traverses VTEX category tree down to max_depth (depth 3),
    returning (f"/{dept}/{cat}/{subcat}/", category_name) tuples for each leaf node."""
    leaves: list[tuple[str, str]] = []

    def walk(node: dict, current_path: str, depth: int):
        cid = node.get("id")
        if cid is None:
            return
        cname = str(node.get("name") or "")
        new_path = f"{current_path}{cid}/"
        children = node.get("children") or []

        if children and depth < max_depth:
            for child in children:
                walk(child, new_path, depth + 1)
        else:
            leaves.append((new_path, cname))

    for root in category_nodes:
        walk(root, "/", 1)

    # Deduplicate while preserving insertion order
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for path, name in leaves:
        if path not in seen:
            seen.add(path)
            deduped.append((path, name))
    return deduped


def _parse_vtex_product(
    product: dict,
    store_name: str,
    domain: str,
) -> list[HarvesterItem]:
    """Extracts all SKUs from a VTEX product payload into HarvesterItem records."""
    items_out: list[HarvesterItem] = []
    product_name = product.get("productName") or product.get("name") or "Producto"
    brand = product.get("brand") or "Genérico"
    categories_list = product.get("categories") or []
    categories_raw = ", ".join(c.strip("/") for c in categories_list if isinstance(c, str))
    product_link = product.get("link") or ""
    if not product_link:
        link_text = product.get("linkText")
        if link_text and domain:
            product_link = f"{domain.rstrip('/')}/{link_text}/p"
    elif not product_link.startswith("http"):
        product_link = f"{domain.rstrip('/')}/{product_link.lstrip('/')}"

    raw_json_str = json.dumps(product)

    skus = product.get("items") or []
    for sku in skus:
        item_id = str(sku.get("itemId") or product.get("productId") or "")
        if not item_id:
            continue

        title_raw = sku.get("nameComplete") or sku.get("name") or product_name
        image_raw = ""
        images = sku.get("images") or []
        if images and isinstance(images[0], dict):
            image_raw = images[0].get("imageUrl") or ""

        # Extract barcode (EAN)
        ean_raw = str(sku.get("ean") or "")
        if not ean_raw:
            ref_ids = sku.get("referenceId") or []
            for r in ref_ids:
                if isinstance(r, dict) and r.get("Key") in ("EAN", "RefId"):
                    ean_raw = str(r.get("Value") or "")
                    break

        # Extract sellers / pricing
        sellers = sku.get("sellers") or []
        if not sellers:
            sellers = [{
                "sellerId": "1",
                "commertialOffer": {
                    "Price": 0.0,
                    "ListPrice": 0.0,
                    "AvailableQuantity": 0,
                }
            }]

        for seller in sellers:
            seller_id = str(seller.get("sellerId") or "1")
            offer = seller.get("commertialOffer") or {}

            try:
                price = float(offer.get("Price") or 0.0)
            except (ValueError, TypeError):
                price = 0.0

            try:
                list_price = float(offer.get("ListPrice") or price)
            except (ValueError, TypeError):
                list_price = price

            if list_price <= 0:
                list_price = price

            try:
                stock = int(offer.get("AvailableQuantity") or 0)
            except (ValueError, TypeError):
                stock = 0

            # Guard price sanity: items with non-positive prices must have stock = 0
            if price <= 0:
                stock = 0

            items_out.append({
                "store_name": store_name,
                "external_id": item_id,
                "ean_raw": ean_raw,
                "title_raw": title_raw,
                "brand_raw": brand,
                "categories_raw": categories_raw,
                "link_raw": product_link,
                "image_raw": image_raw,
                "price_raw": price,
                "list_price_raw": list_price,
                "stock_raw": stock,
                "seller_id_raw": seller_id,
                "raw_json": raw_json_str,
            })

    return items_out


async def fetch_vtex_sitemap_slugs(
    domain: str,
    client: httpx.AsyncClient,
    max_sub_sitemaps: int = 50,
) -> set[str]:
    """
    Parses {domain}/sitemap.xml -> extracts product sub-sitemaps (e.g. sitemap/product-*.xml)
    -> extracts product slugs (/{slug}/p).
    """
    slugs: set[str] = set()
    sitemap_url = f"{domain.rstrip('/')}/sitemap.xml"
    resp = await _rate_limited_request(client, sitemap_url)
    if not resp or resp.status_code != 200:
        return slugs

    sub_sitemaps: list[str] = []
    try:
        root = ET.fromstring(resp.content)
        for elem in root.iter():
            if elem.tag.endswith("loc") and elem.text and "product" in elem.text:
                sub_sitemaps.append(elem.text.strip())
    except Exception:
        # Fallback to regex if XML parse error
        matches = re.findall(r"<loc>\s*(https?://[^<\s]+product[^<\s]*\.xml[^<\s]*)\s*</loc>", resp.text, re.IGNORECASE)
        sub_sitemaps.extend(matches)

    if not sub_sitemaps:
        return slugs

    logger.info("%s: Discovered %d product sub-sitemaps in sitemap.xml", domain, len(sub_sitemaps))

    for sub_url in sub_sitemaps[:max_sub_sitemaps]:
        sub_resp = await _rate_limited_request(client, sub_url)
        if not sub_resp or sub_resp.status_code != 200:
            continue
        try:
            found_slugs = re.findall(r"/([^/\"'<>\s]+)/p(?:$|[?\"'<>\s])", sub_resp.text)
            for s in found_slugs:
                if s and not s.isdigit() and len(s) > 2:
                    slugs.add(s)
        except Exception as e:
            logger.debug("%s: Error parsing sub-sitemap %s: %s", domain, sub_url, e)

    logger.info("%s: Extracted %d total product slugs from sitemaps", domain, len(slugs))
    return slugs


async def harvest_vtex_store(
    store_key: str,
    domain: str,
    sc: str = "1",
    categories_or_seeds: Optional[List[str]] = None,
    max_items: Optional[int] = None,
    seeds_only: bool = False,
    categories_only: bool = False,
    include_sitemap: bool = True,
    max_orphan_slugs: int = 300,
) -> AsyncIterator[HarvesterItem]:
    """Harvests a VTEX store using hierarchical category tree/3 traversal,
    sitemap orphan discovery, and departmental query seeds."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        yielded_keys: Set[Tuple[str, str]] = set()
        seen_slugs: Set[str] = set()
        count = 0

        # Step 1: Deep Category Tree/3 Crawling (unless seeds_only is True)
        if not seeds_only:
            tree_url = f"{domain.rstrip('/')}/api/catalog_system/pub/category/tree/3"
            tree_resp = await _rate_limited_request(client, tree_url)
            leaf_categories: list[tuple[str, str]] = []
            if tree_resp and tree_resp.status_code == 200:
                try:
                    tree_data = tree_resp.json()
                    if isinstance(tree_data, list):
                        leaf_categories = _extract_vtex_leaf_ids(tree_data, max_depth=3)
                        logger.info("%s: Discovered %d category leaf paths via tree/3", store_key, len(leaf_categories))
                except Exception as e:
                    logger.warning("%s: Failed parsing category tree: %s", store_key, e)

            # Crawl each leaf category
            page_size = 50
            for cat_path, cat_name in leaf_categories:
                if max_items and count >= max_items:
                    return

                offset = 0
                while offset <= 2500:
                    to_idx = offset + page_size - 1
                    url = f"{domain.rstrip('/')}/api/catalog_system/pub/products/search"
                    params = {
                        "fq": f"C:{cat_path}",
                        "_from": offset,
                        "_to": to_idx,
                    }
                    if sc and sc != "none" and "natural-life" not in domain:
                        params["sc"] = sc
                    resp = await _rate_limited_request(client, url, params=params)
                    if not resp or resp.status_code not in (200, 206):
                        break

                    try:
                        products = resp.json()
                    except Exception:
                        break

                    if not isinstance(products, list) or not products:
                        break

                    for prod in products:
                        link_text = prod.get("linkText")
                        if link_text:
                            seen_slugs.add(str(link_text).strip())

                        for item in _parse_vtex_product(prod, store_key, domain):
                            key = (item["external_id"], item["seller_id_raw"])
                            if key not in yielded_keys:
                                yielded_keys.add(key)
                                yield item
                                count += 1
                                if max_items and count >= max_items:
                                    return

                    # Parse 'resources: 0-49/340' header to see if more pages exist
                    res_header = resp.headers.get("resources", "")
                    total_available = 0
                    if "/" in res_header:
                        try:
                            total_available = int(res_header.split("/")[-1])
                        except ValueError:
                            pass

                    offset += page_size
                    if total_available > 0 and offset >= total_available:
                        break
                    if len(products) < page_size:
                        break

        # Step 2: Sitemap Gap Filler (unless seeds_only is True)
        if not seeds_only and include_sitemap:
            try:
                sitemap_slugs = await fetch_vtex_sitemap_slugs(domain, client)
                orphan_slugs = [s for s in sitemap_slugs if s not in seen_slugs]
                if orphan_slugs:
                    logger.info("%s: Discovered %d orphan slugs in sitemap; enriching up to %d",
                                store_key, len(orphan_slugs), min(len(orphan_slugs), max_orphan_slugs))
                    for slug in orphan_slugs[:max_orphan_slugs]:
                        if max_items and count >= max_items:
                            return
                        slug_url = f"{domain.rstrip('/')}/api/catalog_system/pub/products/search/{slug}/p"
                        slug_resp = await _rate_limited_request(client, slug_url)
                        if not slug_resp or slug_resp.status_code != 200:
                            continue
                        try:
                            slug_products = slug_resp.json()
                        except Exception:
                            continue
                        if not isinstance(slug_products, list):
                            continue
                        for prod in slug_products:
                            for item in _parse_vtex_product(prod, store_key, domain):
                                key = (item["external_id"], item["seller_id_raw"])
                                if key not in yielded_keys:
                                    yielded_keys.add(key)
                                    yield item
                                    count += 1
                                    if max_items and count >= max_items:
                                        return
            except Exception as e:
                logger.warning("%s: Error during sitemap gap filler: %s", store_key, e)

        # Step 3: Departmental Seeds Fallback (if categories_only is False)
        if not categories_only:
            seeds = categories_or_seeds if categories_or_seeds else DEPARTMENTAL_SEEDS
            logger.info("%s: Sweeping %d departmental query seeds", store_key, len(seeds))

            for seed in seeds:
                if max_items and count >= max_items:
                    return

                url = f"{domain.rstrip('/')}/api/catalog_system/pub/products/search"
                params = {
                    "ft": seed,
                    "_from": 0,
                    "_to": 49,
                    "O": "OrderByTopSaleDESC",
                }
                if sc and sc != "none" and "natural-life" not in domain:
                    params["sc"] = sc
                resp = await _rate_limited_request(client, url, params=params)
                if not resp or resp.status_code not in (200, 206):
                    continue

                try:
                    products = resp.json()
                except Exception:
                    continue

                if not isinstance(products, list):
                    continue

                for prod in products:
                    for item in _parse_vtex_product(prod, store_key, domain):
                        key = (item["external_id"], item["seller_id_raw"])
                        if key not in yielded_keys:
                            yielded_keys.add(key)
                            yield item
                            count += 1
                            if max_items and count >= max_items:
                                return


# ---------------------------------------------------------------------------
# Coto Digital Connector (Oracle Endeca JSON API)
# ---------------------------------------------------------------------------

def _find_coto_records(obj: Any) -> list[dict]:
    """Recursively traverses Endeca JSON tree to locate product records."""
    if isinstance(obj, dict):
        if "records" in obj and isinstance(obj["records"], list) and obj["records"]:
            return obj["records"]
        for v in obj.values():
            found = _find_coto_records(v)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_coto_records(item)
            if found:
                return found
    return []


async def harvest_coto_store(
    store_key: str = "Coto",
    max_items: Optional[int] = None,
    seeds: Optional[List[str]] = None,
) -> AsyncIterator[HarvesterItem]:
    """Harvests Coto Digital via Oracle Endeca category and seed JSON endpoints."""
    base_url = "https://www.coto.com.ar"
    endpoint = f"{base_url}/sitios/cdigi/categoria"
    yielded_ext_ids: Set[str] = set()
    count = 0

    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as client:
        # Pass 1: Catalog Category Sweep (Nrpp=50, No=0, 50, 100...)
        offset = 0
        page_size = 50
        while True:
            if max_items and count >= max_items:
                return

            params = {
                "format": "json",
                "Nrpp": page_size,
                "No": offset,
            }
            resp = await _rate_limited_request(client, endpoint, params=params)
            if not resp or resp.status_code != 200:
                break

            try:
                data = resp.json()
            except Exception:
                break

            records = _find_coto_records(data)
            if not records:
                break

            for rec in records:
                outer_attrs = rec.get("attributes") or {}
                inner_records = rec.get("records") or [{}]
                inner_attrs = inner_records[0].get("attributes") or {} if inner_records else {}

                merged_attrs: dict[str, list[str]] = {}
                merged_attrs.update(outer_attrs)
                merged_attrs.update(inner_attrs)

                def get_attr(key: str, default: str = "") -> str:
                    val = merged_attrs.get(key)
                    if isinstance(val, list) and val:
                        return str(val[0])
                    if isinstance(val, str):
                        return val
                    return default

                ext_id = get_attr("record.id") or get_attr("product.repositoryId") or get_attr("sku.repositoryId")
                if not ext_id or ext_id in yielded_ext_ids:
                    continue

                yielded_ext_ids.add(ext_id)
                title = get_attr("product.displayName") or get_attr("sku.displayName") or "Producto Coto"
                brand = get_attr("product.brand") or get_attr("product.MARCA") or "Coto"
                ean = get_attr("product.eanPrincipal") or get_attr("sku.ean") or ""
                categories = get_attr("product.category") or get_attr("ancestorCategories") or ""

                try:
                    price = float(get_attr("sku.activePrice", "0.0").replace(",", "."))
                except ValueError:
                    price = 0.0

                try:
                    list_price = float(get_attr("sku.regularPrice", str(price)).replace(",", "."))
                except ValueError:
                    list_price = price

                if list_price <= 0:
                    list_price = price

                img_url = get_attr("product.largeImage.url") or get_attr("product.smallImage.url") or ""
                if img_url and not img_url.startswith("http"):
                    img_url = f"{base_url}{img_url}"

                link_raw = f"{base_url}/sitios/cdigi/producto?id={ext_id}"

                item: HarvesterItem = {
                    "store_name": store_key,
                    "external_id": ext_id,
                    "ean_raw": ean,
                    "title_raw": title,
                    "brand_raw": brand,
                    "categories_raw": categories,
                    "link_raw": link_raw,
                    "image_raw": img_url,
                    "price_raw": price,
                    "list_price_raw": list_price,
                    "stock_raw": 1 if price > 0 else 0,
                    "seller_id_raw": "1",
                    "raw_json": json.dumps(rec),
                }
                yield item
                count += 1
                if max_items and count >= max_items:
                    return

            offset += page_size
            if len(records) < page_size:
                break


# ---------------------------------------------------------------------------
# Shopify Connector (Bodegas Bianchi, CCU, etc.)
# ---------------------------------------------------------------------------

async def harvest_shopify_sitemap(
    store_key: str,
    domain: str,
    client: httpx.AsyncClient,
    max_items: Optional[int] = None,
) -> AsyncIterator[HarvesterItem]:
    """Discovers Shopify products via /sitemap.xml -> /sitemap_products_*.xml
    and extracts full JSON-LD Product schemas from HTML with pacing."""
    sitemap_url = f"{domain.rstrip('/')}/sitemap.xml"
    resp = await _rate_limited_request(client, sitemap_url)
    product_sitemaps: list[str] = []
    if resp and resp.status_code == 200:
        matches = re.findall(r"<loc>\s*(https?://[^<\s]+sitemap_products[^<\s]*\.xml[^<\s]*)\s*</loc>", resp.text, re.IGNORECASE)
        product_sitemaps.extend(matches)

    if not product_sitemaps:
        product_sitemaps.append(f"{domain.rstrip('/')}/sitemap_products_1.xml")

    product_urls: list[str] = []
    for p_map in product_sitemaps:
        sm_resp = await _rate_limited_request(client, p_map)
        if not sm_resp or sm_resp.status_code != 200:
            continue
        locs = re.findall(r"<loc>\s*(https?://[^<\s]+/products/[^<\s]+)\s*</loc>", sm_resp.text, re.IGNORECASE)
        for loc in locs:
            if loc not in product_urls:
                product_urls.append(loc)

    logger.info("%s: Discovered %d product URLs via Shopify sitemap", store_key, len(product_urls))

    yielded_ext_ids: set[str] = set()
    count = 0
    for p_url in product_urls:
        if max_items and count >= max_items:
            return

        p_resp = await _rate_limited_request(client, p_url)
        if not p_resp or p_resp.status_code != 200:
            continue

        html_text = p_resp.text
        json_ld_matches = re.findall(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html_text,
            re.DOTALL | re.IGNORECASE,
        )

        for raw_script in json_ld_matches:
            try:
                payload = json.loads(raw_script.strip())
            except Exception:
                continue

            items_to_check = payload if isinstance(payload, list) else [payload]
            for node in items_to_check:
                if not isinstance(node, dict) or node.get("@type") != "Product":
                    continue

                title = html.unescape(node.get("name") or "Producto")
                offers = node.get("offers") or {}
                if isinstance(offers, list) and offers:
                    offers = offers[0]

                price_str = str(offers.get("price") or "0").replace(",", ".")
                try:
                    price = float(price_str)
                except ValueError:
                    price = 0.0

                brand_info = node.get("brand") or {}
                brand_name = brand_info.get("name") if isinstance(brand_info, dict) else store_key

                sku_val = str(offers.get("sku") or node.get("sku") or node.get("gtin13") or node.get("gtin") or "")
                ext_id = sku_val if sku_val else re.sub(r"[^A-Za-z0-9_-]", "", p_url.split("/")[-1])
                if ext_id in yielded_ext_ids:
                    continue
                yielded_ext_ids.add(ext_id)

                image_raw = node.get("image") or ""
                if isinstance(image_raw, list) and image_raw:
                    image_raw = image_raw[0]
                elif isinstance(image_raw, dict):
                    image_raw = image_raw.get("contentUrl") or image_raw.get("url") or ""

                stock = 1 if "InStock" in str(offers.get("availability") or "InStock") else 0
                if price <= 0:
                    stock = 0

                item: HarvesterItem = {
                    "store_name": store_key,
                    "external_id": ext_id,
                    "ean_raw": sku_val if len(sku_val) == 13 and sku_val.isdigit() else "",
                    "title_raw": title,
                    "brand_raw": brand_name or store_key,
                    "categories_raw": str(node.get("category") or "Bebidas"),
                    "link_raw": p_url,
                    "image_raw": str(image_raw),
                    "price_raw": price,
                    "list_price_raw": price,
                    "stock_raw": stock,
                    "seller_id_raw": "1",
                    "raw_json": json.dumps(node),
                }
                yield item
                count += 1
                if max_items and count >= max_items:
                    return


async def harvest_shopify_store(
    store_key: str,
    domain: str,
    max_items: Optional[int] = None,
) -> AsyncIterator[HarvesterItem]:
    """Harvests a Shopify store via /products.json REST endpoint,
    falling back to /sitemap.xml and JSON-LD microdata on HTTP 429."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        page = 1
        count = 0
        yielded_ext_ids: Set[str] = set()
        hit_error = False

        while True:
            if max_items and count >= max_items:
                return

            url = f"{domain.rstrip('/')}/products.json"
            params = {"limit": 250, "page": page}
            resp = await _rate_limited_request(client, url, params=params)
            if not resp or resp.status_code != 200:
                hit_error = True
                break

            try:
                data = resp.json()
            except Exception:
                hit_error = True
                break

            products = data.get("products")
            if not isinstance(products, list) or not products:
                break

            for prod in products:
                prod_id = str(prod.get("id") or "")
                prod_title = prod.get("title") or "Producto"
                vendor = prod.get("vendor") or store_key
                handle = prod.get("handle") or ""
                product_type = prod.get("product_type") or ", ".join(prod.get("tags") or [])
                link_raw = f"{domain.rstrip('/')}/products/{handle}" if handle else domain

                image_raw = ""
                images = prod.get("images") or []
                if images and isinstance(images[0], dict):
                    image_raw = images[0].get("src") or ""

                raw_json = json.dumps(prod)
                variants = prod.get("variants") or []
                if not variants:
                    variants = [{
                        "id": prod_id,
                        "title": "Default Title",
                        "price": "0.0",
                        "compare_at_price": "0.0",
                        "available": True,
                    }]

                for var in variants:
                    var_id = str(var.get("id") or "")
                    ext_id = f"{prod_id}_{var_id}" if var_id and var_id != prod_id else prod_id
                    if ext_id in yielded_ext_ids:
                        continue
                    yielded_ext_ids.add(ext_id)

                    var_title = var.get("title") or ""
                    full_title = prod_title if var_title in ("Default Title", "") else f"{prod_title} - {var_title}"

                    try:
                        price = float(var.get("price") or 0.0)
                    except (ValueError, TypeError):
                        price = 0.0

                    try:
                        list_price = float(var.get("compare_at_price") or price)
                    except (ValueError, TypeError):
                        list_price = price

                    if list_price <= 0:
                        list_price = price

                    ean_raw = str(var.get("barcode") or var.get("sku") or "")
                    stock = 1 if var.get("available") else 0
                    if price <= 0:
                        stock = 0

                    item: HarvesterItem = {
                        "store_name": store_key,
                        "external_id": ext_id,
                        "ean_raw": ean_raw,
                        "title_raw": full_title,
                        "brand_raw": vendor,
                        "categories_raw": product_type,
                        "link_raw": link_raw,
                        "image_raw": image_raw,
                        "price_raw": price,
                        "list_price_raw": list_price,
                        "stock_raw": stock,
                        "seller_id_raw": "1",
                        "raw_json": raw_json,
                    }
                    yield item
                    count += 1
                    if max_items and count >= max_items:
                        return

            page += 1

        # Fallback to sitemap + JSON-LD if /products.json was blocked (e.g. HTTP 429) and yielded nothing
        if count == 0 and hit_error:
            logger.info("%s: /products.json blocked or unavailable. Falling back to sitemap discovery.", store_key)
            async for item in harvest_shopify_sitemap(store_key, domain, client, max_items=max_items):
                yield item


# ---------------------------------------------------------------------------
# Tiendanube Connector (Microdata JSON-LD / HTML)
# ---------------------------------------------------------------------------

async def harvest_tiendanube_store(
    store_key: str,
    domain: str,
    max_items: Optional[int] = None,
) -> AsyncIterator[HarvesterItem]:
    """Harvests a Tiendanube store via /productos?page={page} extracting JSON-LD Product schemas."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        page = 1
        count = 0
        yielded_ext_ids: Set[str] = set()

        while True:
            if max_items and count >= max_items:
                return

            url = f"{domain.rstrip('/')}/productos"
            params = {"page": page}
            resp = await _rate_limited_request(client, url, params=params)
            if not resp or resp.status_code != 200:
                break

            text = resp.text
            # Extract JSON-LD scripts
            json_ld_matches = re.findall(
                r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                text,
                re.DOTALL | re.IGNORECASE,
            )

            found_products = 0
            for raw_script in json_ld_matches:
                try:
                    payload = json.loads(raw_script.strip())
                except Exception:
                    continue

                items_to_check = payload if isinstance(payload, list) else [payload]
                for node in items_to_check:
                    if not isinstance(node, dict):
                        continue
                    if node.get("@type") != "Product":
                        continue

                    title = html.unescape(node.get("name") or "Producto")
                    offers = node.get("offers") or {}
                    if isinstance(offers, list) and offers:
                        offers = offers[0]

                    price_str = str(offers.get("price") or "0").replace(",", ".")
                    try:
                        price = float(price_str)
                    except ValueError:
                        price = 0.0

                    link_raw = offers.get("url") or node.get("@id") or f"{domain}/p"
                    image_raw = node.get("image") or ""
                    if isinstance(image_raw, list) and image_raw:
                        image_raw = image_raw[0]

                    brand_info = node.get("brand") or {}
                    brand_name = brand_info.get("name") if isinstance(brand_info, dict) else store_key

                    ext_id = str(node.get("sku") or re.sub(r"[^A-Za-z0-9_-]", "", link_raw.split("/")[-1]) or f"tn_{count}")
                    if ext_id in yielded_ext_ids:
                        continue
                    yielded_ext_ids.add(ext_id)

                    stock = 1 if "InStock" in str(offers.get("availability") or "InStock") else 0
                    if price <= 0:
                        stock = 0

                    item: HarvesterItem = {
                        "store_name": store_key,
                        "external_id": ext_id,
                        "ean_raw": str(node.get("gtin13") or node.get("gtin") or ""),
                        "title_raw": title,
                        "brand_raw": brand_name or store_key,
                        "categories_raw": node.get("category") or "",
                        "link_raw": link_raw,
                        "image_raw": str(image_raw),
                        "price_raw": price,
                        "list_price_raw": price,
                        "stock_raw": stock,
                        "seller_id_raw": "1",
                        "raw_json": json.dumps(node),
                    }
                    yield item
                    count += 1
                    found_products += 1
                    if max_items and count >= max_items:
                        return

            if found_products == 0:
                break
            page += 1


# ---------------------------------------------------------------------------
# Master Store Dispatcher
# ---------------------------------------------------------------------------

async def harvest_store(
    store_key: str,
    categories_or_seeds: Optional[List[str]] = None,
    max_items: Optional[int] = None,
    seeds_only: bool = False,
    categories_only: bool = False,
    include_sitemap: bool = True,
) -> AsyncIterator[HarvesterItem]:
    """
    Asynchronously yields harvested raw items from any registered store in STORE_REGISTRY
    with rate limiting, exponential backoff, pagination handling, and complete raw payload preservation.
    """
    meta = get_store_meta(store_key)
    if not meta:
        logger.error("Store '%s' is not registered in STORE_REGISTRY.", store_key)
        return

    domain = meta.get("dominio", "")
    platform = meta.get("plataforma", "vtex")
    store_name = meta.get("nombre", store_key)

    if platform == "vtex":
        sc = sales_channel(store_key)
        async for item in harvest_vtex_store(
            store_key=store_name,
            domain=domain,
            sc=sc,
            categories_or_seeds=categories_or_seeds,
            max_items=max_items,
            seeds_only=seeds_only,
            categories_only=categories_only,
            include_sitemap=include_sitemap,
        ):
            yield item

    elif platform == "shopify":
        async for item in harvest_shopify_store(
            store_key=store_name,
            domain=domain,
            max_items=max_items,
        ):
            yield item

    elif platform == "custom":
        if "coto" in store_key.lower():
            async for item in harvest_coto_store(
                store_key=store_name,
                max_items=max_items,
                seeds=categories_or_seeds,
            ):
                yield item
        else:
            # Check if domain behaves as Tiendanube
            async for item in harvest_tiendanube_store(
                store_key=store_name,
                domain=domain,
                max_items=max_items,
            ):
                yield item
    else:
        logger.warning("Unsupported platform '%s' for store '%s'", platform, store_key)
