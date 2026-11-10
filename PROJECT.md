# Project: SuperVmarket — Master Plan: Ingesta Masiva, Normalización Global, Búsqueda Híbrida y Auditoría de 100 Búsquedas

## Architecture
SuperVmarket integra supermercados tradicionales, cadenas de electro y tecnología, tiendas oficiales y marketplaces generales en tiempo real para Argentina con persistencia masiva en SQLite (`supervmarket.db`), normalización global cross-store offline y búsqueda híbrida (<15ms DB + live Mercado Libre).
- **Offline Ingestion & Raw Catalog (`api/_lib/harvester.py`, `scripts/harvest_all_stores.py`, `supervmarket.db`)**:
  - Tabla `raw_catalog`: Persistencia completa sin filtros ni descartes de payloads JSON crudos (`store_name`, `external_id`, `ean_raw`, `title_raw`, `brand_raw`, `categories_raw`, `link_raw`, `image_raw`, `price_raw`, `list_price_raw`, `stock_raw`, `seller_id_raw`, `raw_json`, `scraped_at`).
  - Dual-write con integridad referencial: Inserción simultánea en `raw_catalog` y `productos`/`precios` (usando clave sintética `{STORE_SLUG}-{external_id}` para productos de electro/marketplaces que no exponen EAN-13 público).
  - Barrido multitienda asíncrono con semáforos por dominio (`asyncio.Semaphore(2)`), backoff exponencial y SQLite WAL mode con batching transaccional.
- **Global Entity Resolution & Normalization (`api/_lib/catalog_normalizer.py`, `scripts/normalize_database.py`)**:
  - Índice en memoria `(marca_norm, modelo_norm, variante) -> ean_canonico` que re-vincula ofertas de tiendas sin EAN público (Frávega, Coppel, etc.) bajo el EAN-13 estándar de GS1.
  - Taxonomía canónica de 19 categorías en `categoria_normalizada` cubriendo el 100% de `productos` con lookahead negativo para 0 falsos positivos (segregando estrictamente `televisores` vs `muebles_racks` vs `soportes_accesorios`).
  - Creación del índice `idx_productos_cat_norm ON productos(categoria_normalizada)`.
- **Hybrid Search Engine & Verified Deals (`api/_lib/db.py`, `api/index.py`, `api/_lib/deals.py`, `api/_lib/mercadolibre.py`)**:
  - `db.search_grouped`: Clasificador de intención de consulta que prioriza coincidencia exacta de `categoria_normalizada` (`intent_score DESC, name_rel DESC, stores_cnt DESC, has_promo DESC, best ASC`), garantizando 0 accesorios en el Top 10 para equipamiento.
  - `/api/search`: Consulta concurrente asíncrona a `supervmarket.db` (<15ms) y a la API de Mercado Libre en vivo (`_is_supermarket_domain` flexibilizado), fusionando resultados por EAN o (marca, modelo).
  - Góndolas reales: Sustitución de baselines estáticos por ofertas reales de `supervmarket.db` con `descuento >= 15` verificadas con HTTP 200 para links e imágenes en `deals.py` y `web/src/data/gondolasData.ts`.
- **UI Shielding & 100 Search Audit Suite (`web/src/components/`, `scripts/audit_100_searches.py`)**:
  - Blindaje de botones "Ver" / "Ver web" en `OffersSheet.tsx`, `GondolaCard.tsx`, `ProductCard.tsx` con fallback automático al buscador de la tienda, `referrerPolicy="no-referrer"` en imágenes y decoración UTM/afiliados.
  - Arnés automatizado de 100 búsquedas comunes (60 supermercado/farmacia/mascotas + 40 electro/tecnología/hogar) validando 0 accesorios en Top 10, 100% HTTP 200 OK en links e imágenes, construcción de carrito y exportación a `api/_lib/audit_100_searches_report.json`.
  - Mantenimiento estricto del 100% de los 328+ tests de Vitest en verde.

---

## Feature Inventory & Classification Matrix (24 Components)

| # | Feature | Descripción | Clasificación | Milestone | Fuente |
|---|---------|-------------|---------------|-----------|--------|
| 1 | Buscador Multitienda en Vivo | Troncal fundacional: consulta concurrente por EAN o texto en 12 cadenas en tiempo real sin base de datos pesada. | MANTENER | M6 | R1 |
| 2 | Escáner Góndola 60 FPS + Beep | Alta retención física: permite chequear al instante en la sucursal física si el producto está más barato en otro súper. | MANTENER | M6 | R1 |
| 3 | Integración Oficial Mercado Libre | Stock garantizado por FULL, catálogo MLA oficial, reputación de vendedor y cotización dinámica de flete por CP. | MANTENER | M2, M6 | R1 |
| 4 | Asistente IA (Tickets y Recetas) | Ingesta masiva sin tipear: OCR Vision de tickets y Prompt-to-Cart de recetas con fallbacks locales en memoria. | MANTENER | M6 | R1 |
| 5 | Hoja de Ofertas (OffersSheet) | Patrón bottom sheet tipo Turismocity que permite explorar todas las alternativas por tienda sin perder el contexto. | MANTENER | M6 | R1 |
| 6 | Geolocalización GPS y CP | Imprescindible para filtrar tiendas que no tienen cobertura en el radio de entrega del usuario y cotizar envíos reales. | MANTENER | M2, M3 | R1 |
| 7 | Opción Más Barata (Smart Cart) | Algoritmo de split óptimo 2-3 supermercados con cuantificación explícita del ahorro en pesos ($) respecto al súper único. | MEJORAR | M2, M3 | R2 |
| 8 | Opción Equilibrada (Smart Cart) | Balance de frontera de Pareto (≥ $3.500 ARS y ≥ 5%) limitando a 2 comercios para evitar fricción logística innecesaria. | MEJORAR | M2, M3 | R2 |
| 9 | Opción Cómoda (Smart Cart) | Escenario de máxima comodidad: compra resuelta en 1 solo supermercado con máxima cobertura y menor costo posible. | MEJORAR | M2, M3 | R2 |
| 10 | Desglose de Faltantes y Alternativas | Reemplazo de alerta de texto plano por desglose estructurado con detección de tiendas alternativas y botón 1-tap. | MEJORAR | M2, M3 | R2 |
| 11 | Desglose de Promos y Bancos | Detalle transparente de promociones por volumen (2x1, 2do al X%) y reintegros bancarios (MODO, Cuenta DNI, Galicia). | MEJORAR | M2, M3 | R2 |
| 12 | Progreso de Flete a Envío Gratis | Cotización de flete real y barra de progreso hacia entrega gratuita ("Te faltan $X para envío gratis en Carrefour"). | MEJORAR | M2, M3 | R2 |
| 13 | Tarjetas de Tienda (StoreCart) | Rediseño ergonómico con botón de checkout 1-click directo para VTEX y guía limpia para Coto. | MEJORAR | M3 | R2 |
| 14 | Jerarquía Mobile en ListScreen | Inversión de jerarquía: Héroe comparativo arriba visible en 0ms; productos agregados en cajón colapsable (Drawer). | MEJORAR | M3 | R2 |
| 15 | Touch Targets en Mobile (≥ 44px) | Ampliación de todos los botones táctiles, steppers y chips a un mínimo de 44×44px bajo WCAG 2.5.5 AAA. | MEJORAR | M3 | R5 |
| 16 | Barra de Configuración Compacta | Fusión de 3 tarjetas dispersas (CP, tarjetas y flete) en una sola barra horizontal contextual de 44px de alto. | SIMPLIFICAR | M3 | R2 |
| 17 | Flujo de Coto Digital en StoreCart | Transformación del extenso párrafo de advertencia en una acción directa: "Copiar lista y abrir Coto Digital". | SIMPLIFICAR | M3 | R2 |
| 18 | Estandarización Cromática | Supresión de gradientes estridentes y reducción de señales de badges competitivos a 4 tonos semánticos limpios. | SIMPLIFICAR | M3 | R5 |
| 19 | Modal de Anuncio Recompensado IA | Reducción del temporizador forzoso de 15s a 5s con opción de cierre o patrocinio directo sin fricción. | SIMPLIFICAR | M1 | R4 |
| 20 | Callback OAuth en App.tsx | Eliminación del alert() modal síncrono del navegador en el componente raíz que bloquea el hilo de renderizado. | ELIMINAR | M3 | R5 |
| 21 | Controles de Audio Inerte en Ad Modal | Remoción de controles de audio inerte e implementación de audio dinámico | AGREGAR | M1 | R4 |
| 22 | Mi Lista Habitual sin Fricción | Guardado y recarga en 1 toque en localStorage / IndexedDB / PWA sin requerir creación previa de cuenta. | AGREGAR | M4 | R3 |
| 23 | Monitor Histórico y Delta de Inflación | Registro de 52 semanas y cálculo de variación: "Tu compra hoy cuesta $X, ahorrás $Y vs semana pasada". | AGREGAR | M4 | R3 |
| 24 | Motor de Afiliación / CPA y Cupones FMCG | Inyección transparente de parámetros de afiliación (MeLi y redes VTEX) y cupones de marcas FMCG con firewall ético. | AGREGAR | M5 | R4 |

---

## Feature Inventory (Master Plan: R1, R2, R3, R4)

| # | Feature | Descripción | Milestone | Fuente |
|---|---------|-------------|-----------|--------|
| 1 | DDL y Esquema `raw_catalog` | Tabla `raw_catalog` con columnas para todos los atributos crudos, payload `raw_json` y constraint UNIQUE | M1 | R1, Survey E1 |
| 2 | Ingesta Dual-Write Zero-Drop | Guardado simultáneo en `raw_catalog` y `productos`/`precios` sin descartar productos sin EAN ni no-equipamiento | M1 | R1, Survey E1 |
| 3 | Generador de Clave Sintética para No-EAN | Asignación de `{STORE_SLUG}-{external_id}` para productos de marketplaces/electro sin GTIN-13 | M1 | R1, Survey E1 |
| 4 | Barrido por Árbol de Categorías VTEX | Crawling jerárquico vía `/api/catalog_system/pub/category/tree/2` evitando el límite VTEX de 2500 ítems | M1 | R1, Survey E1 |
| 5 | Semillero Departamental de 100 Consultas | Barrido de semillas de alta demanda (Smart TVs, Celulares, Heladeras, Almacén, Lácteos, etc.) | M1 | R1, Survey E1 |
| 6 | Motor de Concurrencia y Rate-Limiting | Semáforos por dominio (`Semaphore(2)`), delay de 200ms y reintentos exponenciales contra HTTP 429 | M1 | R1, Survey E1 |
| 7 | Conectores No-VTEX (Coto, Shopify, Tiendanube) | Integración de endpoints JSON de Coto Digital, Shopify (Bianchi, CCU) y Tiendanube | M1 | R1, Survey E1 |
| 8 | Ejecutor CLI de Ingesta Masiva | Script `scripts/harvest_all_stores.py` con transacciones por lote (200-500 ítems) y modo WAL | M1 | R1, Survey E1 |
| 9 | Cobertura Total de las 35+ Tiendas | Ingesta de todas las tiendas de `STORE_REGISTRY` en `supervmarket.db` | M1 | R1, Survey E1 |
| 10 | Índice Global en Memoria para Entity Resolution | Mapeo `(marca_norm, modelo_norm, variante) -> ean_canonico` con prioridad para EAN-13 GS1 | M2 | R2, Survey E2 |
| 11 | Vinculación Cross-Store de Tiendas sin EAN | Re-apuntado automático de ofertas de Frávega, Coppel y tiendas oficiales al EAN canónico existente | M2 | R2, Survey E2 |
| 12 | Vinculación de Consumo Masivo sin EAN | Resolución de productos de almacén por `(marca_norm, nombre_base_norm, peso_volumen, unidad)` | M2 | R2, Survey E2 |
| 13 | Guarda de Razón de Precio ($0.35 - 2.80) | Aislamiento de combos o repuestos mal catalogados para evitar fusiones erróneas | M2 | R2, Survey E2 |
| 14 | Discriminación de Capacidad/Memoria | Preservación de variantes de almacenamiento (`128GB`, `256GB`, `512GB`) sin fusionar hardware distinto | M2 | R2, Survey E2 |
| 15 | Segregación Estricta de Muebles y Accesorios | Clasificación previa de `muebles_racks` y `soportes_accesorios` antes de `televisores` | M2 | R2, Survey E2 |
| 16 | Lookaheads Negativos Anti-Falsos Positivos | Prevención de falsos positivos en alimentos ("Rack de cordero", "Colchón de frutilla", "Repuesto CIF") | M2 | R2, Survey E2 |
| 17 | Cobertura 100% de `categoria_normalizada` | Clasificación canónica del 100% de filas en `productos` de `supervmarket.db` (0 NULLs) | M2 | R2, Survey E2 |
| 18 | Creación de Índice `idx_productos_cat_norm` | `CREATE INDEX IF NOT EXISTS idx_productos_cat_norm ON productos(categoria_normalizada)` | M2 | R2, Survey E2 |
| 19 | Módulo y Runner de Normalización | `api/_lib/catalog_normalizer.py` y script ejecutable `scripts/normalize_database.py` | M2 | R2, Survey E2 |
| 20 | Clasificador de Intención de Búsqueda | Detección de categoría objetivo en `api/_lib/db.py` (`tv` -> `televisores`, `rack tv` -> `muebles_racks`) | M3 | R3, Survey E3 |
| 21 | Ranking SQL Basado en Intención | Ordenamiento SQL priorizando coincidencia de categoría objetivo (`intent_score DESC`) sobre precio | M3 | R3, Survey E3 |
| 22 | Cero Accesorios en Top 10 de Equipos | Invariante estricto: ningún rack ni soporte en las primeras 10 posiciones de búsquedas de TV/celular | M3 | R3, Survey E3 |
| 23 | Búsqueda Híbrida Paralela (DB + ML en Vivo) | Consulta concurrente a `supervmarket.db` (<15ms) y a la API de Mercado Libre en `/api/search` | M3 | R3, Survey E3 |
| 24 | Flexibilización de Dominios en Mercado Libre | Desbloqueo de dominios de tecnología (`MLA-CELLPHONES`, etc.) en `mercadolibre.py` para búsqueda híbrida | M3 | R3, Survey E3 |
| 25 | Fusión Híbrida de Ofertas ML con DB | Unificación de resultados de Mercado Libre con grupos de la DB por EAN o `(marca, modelo)` | M3 | R3, Survey E3 |
| 26 | Sustitución de Góndolas por Productos Reales | Reemplazo de baselines estáticos en `deals.py` y `gondolasData.ts` con ofertas reales de `supervmarket.db` | M3 | R3, Survey E3 |
| 27 | Verificación HTTP 200 de Góndolas | Validación previa con `httpx` de que links e imágenes de ofertas respondan HTTP 200 OK | M3 | R3, Survey E3 |
| 28 | Curaduría de Góndolas en `audit_and_heal.py` | Extensión del script de sanación para refrescar góndolas de marketplace y electro desde la DB | M3 | R3, Survey E3 |
| 29 | Blindaje de Botones "Ver" con Fallback | Enlaces en `OffersSheet.tsx` y cards con resolución a dominio y fallback al buscador de la tienda | M4 | R4, Survey E3 |
| 30 | Blindaje Anti-Hotlink de Imágenes UI | Atributo `referrerPolicy="no-referrer"` en todas las etiquetas `<img>` de componentes UI | M4 | R4, Survey E3 |
| 31 | Decoración de Afiliados y UTM en UI | Invocación consistente de `decorateOutboundUrl` en todos los botones "Ver" / "Ver web" | M4 | R4, Survey E3 |
| 32 | Suite de 100 Búsquedas Comunes | Script `scripts/audit_100_searches.py` ejecutando las 60 consultas de súper + 40 de electro | M4 | R4, Survey E3 |
| 33 | Validación de 0 Accesorios en Top 10 | Verificación automatizada de 0 racks/accesorios en Top 10 para consultas de equipamiento | M4 | R4, Survey E3 |
| 34 | Validación 100% HTTP 200 Links e Imágenes | Verificación automatizada de salud HTTP 200 en links y fotos del Top 5 y góndolas | M4 | R4, Survey E3 |
| 35 | Verificación de Armado de Carrito | Comprobación de que `api/_lib/carts.py` arme carritos válidos para productos testeados | M4 | R4, Survey E3 |
| 36 | Reporte de Auditoría Exportable JSON | Generación del reporte `api/_lib/audit_100_searches_report.json` | M4 | R4, Survey E3 |
| 37 | Mantenimiento de Suite Vitest (328+ Tests) | Conservación de los 328+ tests existentes en verde, incluyendo `ProductDiagnosisMatrix.test.ts` | M4 | R4, Survey E3 |
| 38 | Aceptación Final E2E y Auditoría Forense | Validación integral del sistema, stress testing adversarial Tier 5 y auditoría forense CLEAN | M5 | Master |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|--------------|--------|
| M1 | Harvester Masivo Multitienda con Preservación de Base Cruda (R1) | DDL `raw_catalog`, dual-write zero-drop (`raw_catalog` + `productos`/`precios`), claves sintéticas no-EAN, crawler VTEX tree + query seeds, conectores no-VTEX, ejecutor `scripts/harvest_all_stores.py` y `api/_lib/harvester.py` | none | DONE |
| M2 | Normalización Global, Resolución de Entidades y Categorización (R2) | Índice global ER `(marca, modelo) -> ean_canonico`, re-apuntado de ofertas sin EAN, taxonomía canónica 19 categorías con lookahead negativo (100% productos sin NULLs), `idx_productos_cat_norm`, `api/_lib/catalog_normalizer.py` y `scripts/normalize_database.py` | M1 | DONE |
| M3 | Motor de Búsqueda Híbrido y Góndolas 100% Reales (R3) | Intent matching en `db.py` (0 accesorios en Top 10), ranking SQL por relevancia de intención, búsqueda híbrida paralela en `/api/search` (DB + Mercado Libre en vivo), flexibilización de dominios ML, sustitución de baselines por ofertas reales HTTP 200 en `deals.py` y `gondolasData.ts` | M2 | DONE |
| M4 | Blindaje de Botones "Ver" en UI y Suite de 100 Búsquedas (R4) | Fallback de botones "Ver" al buscador de la tienda, `referrerPolicy="no-referrer"`, decoración de afiliados, script `scripts/audit_100_searches.py` (60 súper + 40 electro, 0 accesorios, 100% HTTP 200, carritos), reporte JSON y 328+ Vitest en verde | M3 | DONE |
| M5 | Aceptación Final E2E, Blindaje Adversarial (Tier 5) y Auditoría Forense de Integridad | Verificación integral de todas las suites, stress tests de concurrencia y edge-cases, build limpio y auditoría forense con veredicto CLEAN | M1, M2, M3, M4 | DONE |

---

## Interface Contracts

### 1. Raw Catalog Table Schema Contract (`supervmarket.db`)
```sql
CREATE TABLE IF NOT EXISTS raw_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_name TEXT NOT NULL,
    external_id TEXT NOT NULL,
    ean_raw TEXT,
    title_raw TEXT NOT NULL,
    brand_raw TEXT,
    categories_raw TEXT,
    link_raw TEXT NOT NULL,
    image_raw TEXT,
    price_raw REAL NOT NULL,
    list_price_raw REAL,
    stock_raw INTEGER DEFAULT 1,
    seller_id_raw TEXT DEFAULT '1',
    raw_json TEXT NOT NULL,
    scraped_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (store_name, external_id, seller_id_raw)
);

CREATE INDEX IF NOT EXISTS idx_raw_catalog_store ON raw_catalog(store_name);
CREATE INDEX IF NOT EXISTS idx_raw_catalog_ean ON raw_catalog(ean_raw);
CREATE INDEX IF NOT EXISTS idx_raw_catalog_ext ON raw_catalog(external_id);
```

### 2. Harvester Engine Interface Contract (`api/_lib/harvester.py`)
```python
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

async def harvest_store(
    store_key: str,
    categories_or_seeds: Optional[List[str]] = None,
    max_items: Optional[int] = None
) -> AsyncIterator[HarvesterItem]:
    """
    Asynchronously yields harvested raw items from a designated store
    with automatic rate limiting, backoff, and pagination handling.
    """
```

### 3. Catalog Normalizer Contract (`api/_lib/catalog_normalizer.py`)
```python
def classify_canonical_category(title: str, categories: str = "", brand: str = "") -> str:
    """
    Classifies a product into one of the 19 canonical categories.
    Strictly evaluates 'muebles_racks' and 'soportes_accesorios' BEFORE 'televisores'.
    Applies negative lookaheads to protect groceries.
    """

def normalize_catalog(db_path: str = "supervmarket.db") -> dict:
    """
    Executes full offline entity resolution and category classification:
    1. Builds in-memory (brand, model, variant) -> canonical EAN index.
    2. Re-points prices for non-EAN items to canonical EANs where valid.
    3. Populates 100% of categoria_normalizada in productos.
    4. Ensures idx_productos_cat_norm exists.
    Returns summary statistics {total, classified, re_pointed, categories_distribution}.
    """
```

### 4. Hybrid Search Contract (`api/_lib/db.py` & `api/index.py`)
```python
def search_grouped(
    query: str,
    db_path: str = "supervmarket.db",
    vertical: Optional[str] = None,
    store_type: Optional[str] = None,
    limit: int = 50
) -> List[dict]:
    """
    Detects intent category from query.
    Executes SQL ranking with intent_score DESC to guarantee 0 accessories in Top 10 for equipment queries.
    """
```

### 5. 100 Search Audit Suite Contract (`scripts/audit_100_searches.py`)
```python
class AuditReport(TypedDict):
    timestamp: str
    total_searches: int
    passed_searches: int
    failed_searches: int
    accessory_infiltration_count: int  # Must be 0
    images_health_pct: float            # Must be 100.0%
    links_health_pct: float             # Must be 100.0%
    cart_health_pct: float              # Must be 100.0%
    details: List[dict]
```

---

## Code Layout
- Milestone 1 (Harvester & Raw Catalog):
  - `api/_lib/harvester.py`
  - `scripts/harvest_all_stores.py`
  - `scripts/migrate_raw_catalog.py`
- Milestone 2 (Global Normalization & Entity Resolution):
  - `api/_lib/catalog_normalizer.py`
  - `scripts/normalize_database.py`
  - `api/_lib/normalization.py`
- Milestone 3 (Hybrid Search & Real Deals):
  - `api/_lib/db.py`
  - `api/index.py`
  - `api/_lib/mercadolibre.py`
  - `api/_lib/deals.py`
  - `web/src/data/gondolasData.ts`
  - `scripts/audit_and_heal.py`
- Milestone 4 (UI "Ver" Shielding & 100 Search Audit Suite):
  - `web/src/components/OffersSheet.tsx`
  - `web/src/components/GondolaCard.tsx`
  - `web/src/components/ProductCard.tsx`
  - `web/src/components/SponsoredGondolaCard.tsx`
  - `scripts/audit_100_searches.py`
  - `api/_lib/audit_100_searches_report.json`
- Milestone 5 (Final Acceptance & Adversarial Hardening):
  - Automated test suites in `scratch/` and `web/src/__tests__/`
