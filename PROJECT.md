# Project: SuperVmarket — Integración de 17 Cadenas/Marketplaces, Normalización de Catálogo y Búsqueda Diferenciada

## Architecture
SuperVmarket integra supermercados tradicionales, cadenas de electro y tecnología, tiendas oficiales y marketplaces generales en tiempo real para Argentina.
- **Backend (`api/`)**:
  - `api/_lib/stores.py`: Registro centralizado de cadenas, dominios VTEX/Shopify, canales de venta (`sc`), verticales (`supermarket`, `marketplace`, `electro`, `specialty`, `pharmacy`) y metadatos de afiliados.
  - `api/_lib/vtex_mcp.py`: Motor de consulta concurrente asíncrona (`asyncio.gather`), agrupación jerárquica de 4 niveles (EAN-13, Modelo Alfanumérico Canónico, Taxonomía Perecederos, Prefijo GS1), aliasing bidireccional EAN <-> Modelo, y resolución dinámica de `seller_id`.
  - `api/_lib/parsers.py`: Deserialización y limpieza de payloads VTEX y Coto, desbloqueo contextual de `NON_GROCERY_MARKETPLACE_KEYWORDS` y `NON_GROCERY_CATEGORY_KEYWORDS` condicionado a `grocery_only=True`, extractor de modelo y variantes.
  - `api/_lib/deals.py`: Curaduría y caching de góndolas de ofertas: niveles tradicionales de supermercados más carruseles dedicados de marketplaces y electro.
  - `api/index.py`: Endpoints REST `/api/search` (con soporte para `vertical`, `store_type`, `grocery_only`) y `/api/offers` (retornando `tiers` y `marketplace_tiers`).
- **Frontend (`web/src/`)**:
  - `web/src/lib/stores.ts`: Registro tipado de metadatos de tiendas con clasificación vertical (`StoreVertical`), colores y badges.
  - `web/src/components/SearchScreen.tsx`: Búsqueda diferenciada con selector por chips (`Todos`, `Supermercados`, `Marketplaces / Electro`), agrupación por categorías de tienda y badges de vertical en tarjetas.
  - `web/src/components/OffersScreen.tsx`: Góndolas de ofertas con carruseles dedicados para Marketplaces, Electro & TV, y Hogar, junto a los 4 niveles de ofertas de supermercados.
  - `web/src/components/OffersSheet.tsx`: Comparador concurrentes de ofertas unificadas por EAN o Modelo con desglose de vendedor y link de carrito.
- **Verification & E2E Testing Track (`scratch/` & `web/src/__tests__/`)**:
  - `scratch/verify_connectors_live.py`: Validación programática de llamadas en vivo y dynamic seller en las 17+ tiendas.
  - `scratch/verify_normalization_live.py`: Verificación de algoritmos EAN-13 Modulo 10, extracción de modelo alfanumérico, guardas de accesorios y aliasing.
  - `scratch/verify_endpoints_live.py`: Pruebas de integración de endpoints `/api/search` y `/api/offers`.
  - `web/src/components/__tests__/DifferentiatedSearchAndCarousels.test.tsx`: Pruebas unitarias/UI en Vitest.

---

## Feature Inventory (Fase 1: Smart Cart)
Todas las funcionalidades relevadas en la auditoría técnica y su asignación de hito:

| # | Feature | Descripción | Clasificación | Milestone | Fuente |
|---|---------|-------------|---------------|-----------|--------|
| 1 | Buscador Multitienda en Vivo | Consulta simultánea por EAN/término en 12 cadenas | MANTENER | M6 | Survey E1, E3 |
| 2 | Escáner de Código de Barras Góndola | Detección 60 FPS con BarcodeDetector y @zxing | MANTENER | M6 | Survey E1 |
| 3 | Integración Oficial Mercado Libre | Catálogo MLA, seller reputation, envíos FULL, flete dinámico | MANTENER | M2, M6 | R1, Survey E1, E3 |
| 4 | Asistente IA (Tickets y Recetas) | OCR Vision Gemini Flash y Prompt-to-Cart | MANTENER | M6 | R1, Survey E1 |
| 5 | Hoja de Ofertas (OffersSheet) | Bottom sheet con detalles por supermercado y ML | MANTENER | M6 | Survey E1 |
| 6 | Geolocalización GPS y CP | Cobertura regional de entrega y geocodificación inversa | MANTENER | M2, M3 | Survey E1 |
| 7 | Opción Más Barata (Smart Cart) | Split óptimo 2-3 súper con ahorro $ cuantificado vs súper único | MEJORAR | M2, M3 | R2, Survey E2, E3 |
| 8 | Opción Equilibrada (Smart Cart) | Balance Pareto de ahorro vs cantidad de comercios | MEJORAR | M2, M3 | R2, Survey E2, E3 |
| 9 | Opción Cómoda (Smart Cart) | Todo en 1 solo supermercado de máxima cobertura | MEJORAR | M2, M3 | R2, Survey E2, E3 |
| 10 | Desglose de Productos Faltantes | Detalle estructurado de faltantes y alternativas en otros súper | MEJORAR | M2, M3 | R2, Survey E2, E3 |
| 11 | Desglose de Promos y Beneficios | Descuentos por volumen (2x1, 2do %) y reintegros bancarios | MEJORAR | M2, M3 | R2, Survey E2, E3 |
| 12 | Cotización y Progreso de Flete | Costo de envío real y barra de progreso hacia envío gratis | MEJORAR | M2, M3 | R2, Survey E2, E3 |
| 13 | Tarjetas de Supermercado (StoreCart) | Rediseño de tarjeta por súper con actions 1-click limpias | MEJORAR | M3 | R2, Survey E2 |
| 14 | Jerarquía Mobile en ListScreen | Héroe de escenarios arriba; productos en drawer colapsable | MEJORAR | M3 | R2, Survey E1, E2 |
| 15 | Touch Targets en Mobile | Botones y steppers ampliados a mínimo 44x44px | MEJORAR | M3 | R5, Survey E1, E2 |
| 16 | Barra de Configuración Compacta | Agrupación de CP, día/tarjeta y envío en barra contextual | SIMPLIFICAR | M3 | Survey E1, E2 |
| 17 | Flujo de Coto Digital en StoreCart | Acción simplificada de copiado y apertura web | SIMPLIFICAR | M3 | Survey E1, E2 |
| 18 | Limpieza de Alertas y Gradientes | Reducción de fatiga visual y estandarización cromática | SIMPLIFICAR | M3 | Survey E1, E2 |
| 19 | Modal de Anuncio Recompensado | Reducción de fricción y timer en accesos IA | SIMPLIFICAR | M1 | Survey E1 |
| 20 | Limpieza Callback OAuth en App.tsx | Remoción de alerta bloqueante en componente raíz | ELIMINAR | M3 | Survey E1 |
| 21 | Mi Lista Habitual sin Fricción | Guardado 1-tap en localStorage/PWA sin login previo | AGREGAR | M4 | R3, Survey E1, E2 |
| 22 | Seguimiento de Precio de Canasta | Monitor histórico de compra mensual con delta de ahorro | AGREGAR | M4 | R3, Survey E1, E2 |
| 23 | Monetización por Afiliación / CPA | Parámetros de tracking oficiales en links VTEX y Mercado Libre | AGREGAR | M5 | R4, Survey E1, E2 |
| 24 | Cupones de Marca y Ofertas Patrocinadas | Especificación de cashback FMCG y sponsored ads transparentes | AGREGAR | M5 | R4, Survey E1 |

---

## Feature Inventory (Fase 2: Marketplaces & Dual Unification)
Todas las funcionalidades identificadas en el relevamiento técnico de marketplaces y su asignación de hito:

| # | Feature | Descripción | Milestone | Fuente |
|---|---------|-------------|-----------|--------|
| 1 | Conectores Marketplaces Generales | Conexión y consulta en vivo a Provincia Compras y On City (`sc=2`) con parsing estructurado | M1 | Survey E1, R1 |
| 2 | Conectores Cadenas Electro y Tecnología | Conexión en vivo a Frávega, Cetrogar, Naldo, Pardo y Coppel | M1 | Survey E1, R1 |
| 3 | Conectores Tiendas Oficiales de Marca | Conexión a Samsung, Philips, Whirlpool, Moulinex/Tefal (`sc=3`) y Sony Store AR | M1 | Survey E1, R1 |
| 4 | Conectores Hogar, Perfumería, Mascotas y Súper | Conexión a Easy, Perfumerías Pigmento, Puppis, Josimar (`sc=5`) y Toledo Digital / Cordiez | M1 | Survey E1, R1 |
| 5 | Conectores Niche y Shopify Adicionales | Conexión a Bodegas Bianchi (Shopify), Musimundo (VTEX), Oster (VTEX) y StyleStore (VTEX) | M1 | Survey E1, R1 |
| 6 | Resolución Dinámica de `seller_id` | Extracción de seller en marketplaces (`sellers[].sellerId`) y propagación a enlaces de carrito `seller={seller_id}` | M1 | Survey E1, R1 |
| 7 | Normalización de Respuesta en Vivo de Conectores | Generación consistente de dict `{title, precio_venta, precio_lista, disponible, ean, modelo, link, imagen, supermercado, seller_id}` | M1 | Survey E1, R1 |
| 8 | Validación EAN-13 Checksum Modulo 10 | Validación de códigos GS1 EAN-13 mediante suma ponderada impar/par*3 mod 10 | M2 | Survey E2, R2 |
| 9 | Limpieza y Conversión Universal de Códigos de Barra | Conversión de UPC-A (12 dígitos a 13) y GTIN-14 con cero inicial, sanitización de caracteres | M2 | Survey E2, R2 |
| 10 | Ruteo de Prefijos GS1 (Nacional vs Balanza) | Detección de prefijos `20`-`29` de balanza interna para aislamiento de EANs globales | M2 | Survey E2, R2 |
| 11 | Extractor de Modelo desde Metadatos | Extracción de modelo de fabricante desde `productReference`, `referenceId`, `Modelo` y `allSpecifications` | M2 | Survey E2, R2 |
| 12 | Extractor de Modelo por Regex de Título | Extracción de código alfanumérico priorizado (Smart TVs, línea blanca, celulares, audio, herramientas) | M2 | Survey E2, R2 |
| 13 | Limpieza de Sufijos Regionales y Formato | Eliminación de sufijos `/77`, `GCZB`, `/DS`, `-KA1AR`, etc., y estandarización alfanumérica | M2 | Survey E2, R2 |
| 14 | Generación de Clave Canónica de Identidad | Formulación de `MODEL_{BRAND}_{CANONICAL_MODEL}[_{VARIANT}]` para electro/hogar sin EAN | M2 | Survey E2, R2 |
| 15 | Discriminación de Variantes de Capacidad | Preservación de sufijo de almacenamiento (`128GB`, `256GB`, `512GB`) para no fusionar memorias distintas | M2 | Survey E2, R2 |
| 16 | Guarda de Aislamiento de Accesorios | Detección de accesorios (`funda`, `soporte`, `vidrio`, `cargador`, `repuesto`) para no contaminar aparatos | M2 | Survey E2, R2 |
| 17 | Guarda de Razón de Precio en Agrupación | Rechazo de fusión si precio del candidato es `< 0.35` o `> 2.8` veces el precio promedio | M2 | Survey E2, R2 |
| 18 | Agrupación Jerárquica Multitienda de 4 Niveles | Agrupación en `ProductGroup`: Nivel 1 EAN-13, Nivel 2 Modelo Canónico, Nivel 3 Perecederos, Nivel 4 Firma GS1 | M2 | Survey E2, R2 |
| 19 | Aliasing Bidireccional EAN <-> Modelo | Unificación de comercios que envían EAN con comercios que envían solo Modelo bajo la misma tarjeta | M2 | Survey E2, R2 |
| 20 | Poblado y Migración de Esquema de Base de Datos | Poblado de columnas `modelo` y `tipo` en `productos`, y registro de `seller_id` y `store_type` en `precios` | M2 | Survey E2, R2 |
| 21 | Desbloqueo Contextual `NON_GROCERY_MARKETPLACE_KEYWORDS` | Parámetro `grocery_only: bool = False` para habilitar productos de tecnología y hogar en búsqueda general | M2 | Survey E2, R3 |
| 22 | Desbloqueo Contextual `NON_GROCERY_CATEGORY_KEYWORDS` | Filtrado de categorías no comestibles condicionado estrictamente a `grocery_only=True` | M2 | Survey E2, R3 |
| 23 | Actualización de Firma de Pipeline en Parsers | Extensión de `parse_vtex_product` y `parse_coto_record` con soporte `grocery_only` y fallback sin EAN | M2 | Survey E2, R3 |
| 24 | Clasificación y Metadatos de Tiendas por Vertical | Extensión de `web/src/lib/stores.ts` y `api/_lib/stores.py` con tipado `StoreVertical` (`supermarket`, `marketplace`, `electro`, etc.) | M4 | Survey E3, R4 |
| 25 | UI de Búsqueda Diferenciada por Vertical | Selector por chips (`Todos`, `Supermercados`, `Marketplaces / Electro`) y dropdown categorizado en `SearchScreen.tsx` | M4 | Survey E3, R4 |
| 26 | Endpoint `/api/search` con Filtro por Vertical | Soporte de parámetros `vertical`, `store_type` y `grocery_only` en backend FastAPI | M3 | Survey E3, R4 |
| 27 | Carruseles Dedicados de Ofertas de Marketplaces | Carruseles independientes para Marketplaces, Electro y Hogar en `OffersScreen.tsx` con badges de cuotas | M4 | Survey E3, R4 |
| 28 | Endpoint `/api/offers` con `marketplace_tiers` | Soporte de ofertas curadas para marketplaces y electrodomésticos en backend | M3 | Survey E3, R4 |
| 29 | Suite Automatizada de Verificación de Conectores en Vivo | Script `scratch/verify_connectors_live.py` comprobando HTTP 200, precios, stock y seller_id dinámico | M5 | Survey E1, E3 |
| 30 | Suite Automatizada de Normalización y Unificación | Script `scratch/verify_normalization_live.py` comprobando Modulo 10, extracción de modelos, guardas y aliasing | M5 | Survey E2, E3 |
| 31 | Suite Automatizada de Endpoints Diferenciados | Script `scratch/verify_endpoints_live.py` comprobando `/api/search` por vertical y `/api/offers` carruseles | M5 | Survey E3 |
| 32 | Suite Frontend Vitest para Búsqueda y Carruseles | Pruebas de integración React en `web/src/components/__tests__/DifferentiatedSearchAndCarousels.test.tsx` | M5 | Survey E3 |
| 33 | Aceptación Final E2E y Blindaje Adversarial (Tier 5) | Validación del 100% de pruebas E2E, auditoría forense de integridad, estrés de concurrencia y build limpio | M6 | Survey Master |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|--------------|--------|
| M1 | Conectores e Integración de Tiendas y Marketplaces (R1) | Registro e implementación de llamadas y scrapers para las 17 tiendas + tiendas adicionales viables, resolución de `sc` y `seller_id` dinámico para carrito VTEX | none | DONE |
| M2 | Normalización de Catálogo, Dual Unification y Desbloqueo de Filtros (R2, R3) | Implementación de `grocery_only=False` en `parsers.py`, validación EAN-13, extracción de Modelo Alfanumérico Canónico, aliasing EAN <-> Modelo, guardas y actualización de schema | M1 | DONE |
| M3 | Endpoints Backend de Búsqueda y Ofertas Diferenciadas (R3, R4) | Parámetros `vertical` y `grocery_only` en `/api/search`, generación de `marketplace_tiers` en `/api/offers` (`deals.py`) y optimización con `asyncio.gather` y cache | M1, M2 | DONE |
| M4 | Frontend: Búsqueda Diferenciada y Carruseles de Ofertas (R4) | Chips de filtrado por vertical en `SearchScreen.tsx`, clasificación en `stores.ts`, carruseles dedicados de marketplaces en `OffersScreen.tsx` | M3 | DONE |
| M5 | E2E Testing Track: Suites de Verificación Automatizada | Suites `verify_connectors_live.py`, `verify_normalization_live.py`, `verify_endpoints_live.py` y pruebas Vitest en frontend; publicación de `TEST_READY.md` | none (Parallel) | DONE |
| M6 | Aceptación E2E 100%, Blindaje Adversarial y Auditoría Forense | Ejecución de todas las suites E2E Tiers 1-4, generación adversarial de casos límite (Tier 5), build productivo y auditoría forense | M4, M5 | DONE |

---

## Interface Contracts

### 1. Store Connector & Live Offer Dict Contract (`api/_lib/stores.py` & `vtex_mcp.py`)
```python
class StoreMeta(TypedDict):
    id: str
    nombre: str
    dominio: str
    plataforma: Literal["vtex", "shopify", "custom"]
    sales_channel: int
    vertical: Literal["supermarket", "marketplace", "electro", "specialty", "pharmacy"]
    is_marketplace: bool
    supports_cart: bool
    color: str

class LiveOffer(TypedDict):
    ean: str
    nombre: str
    marca: str
    modelo: str  # Alphanumeric canonical model (or empty for pure grocery)
    tipo: str    # Product vertical or category
    precio_venta: float
    precio_lista: float
    descuento: float
    disponible: bool
    supermercado: str
    seller_id: str  # Dynamic seller identifier (e.g. "1", "diggit632", "fravegasellerprod346")
    link: str       # Purchase link with seller={seller_id}
    imagen: str
```

### 2. Contextual Parsing Contract (`api/_lib/parsers.py`)
```python
def parse_vtex_product(
    prod: dict,
    store_name: str,
    fallback_url: str = "",
    grocery_only: bool = False,
    store_type: str = "supermarket"
) -> Optional[dict]:
    """
    Parses a raw VTEX product payload into a standardized product dictionary.
    If grocery_only is True, applies NON_GROCERY_MARKETPLACE_KEYWORDS and NON_GROCERY_CATEGORY_KEYWORDS.
    If grocery_only is False, preserves technology, electro, and home products.
    Extracts dynamic sellerId from sellers[].sellerId and embeds into cart link.
    Extracts canonical model code if EAN is absent.
    """
```

### 3. Frontend Store Metadata Contract (`web/src/lib/stores.ts`)
```typescript
export type StoreVertical = 'supermarket' | 'marketplace' | 'electro' | 'specialty' | 'pharmacy'

export interface StoreMeta {
  label: string
  color: string
  vertical: StoreVertical
  isMarketplace?: boolean
  supportsCart?: boolean
}

export type StoreMap = Record<string, StoreMeta>
```

### 4. Search API Request / Response Contract (`api/index.py` <-> `web/src/api.ts`)
```typescript
// Query params: /api/search?q={query}&sort={sort}&vertical={vertical}&only_offers={bool}&cp={cp}
export interface ProductGroup {
  id: string // EAN or MODEL_BRAND_CODE
  ean: string
  nombre: string
  marca: string
  modelo?: string
  tipo?: string
  imagen: string
  categoria_normalizada?: string
  vertical?: 'supermarket' | 'marketplace' | 'electro' | 'specialty'
  best_offer: Offer
  offers: Offer[]
}
```

---

## Code Layout
- Backend Store Integrations:
  - `api/_lib/stores.py` (Exclusively owned by M1)
  - `api/_lib/vtex_mcp.py` (Store querying exclusively owned by M1; grouping owned by M2)
- Backend Normalization & Parsers:
  - `api/_lib/parsers.py` (Exclusively owned by M2)
  - `api/_lib/normalization.py` (New normalization module owned by M2)
  - `api/_lib/db.py` (Schema & migrations owned by M2)
- Backend Search & Deals Endpoints:
  - `api/index.py` (Exclusively owned by M3)
  - `api/_lib/deals.py` (Exclusively owned by M3)
- Frontend Store Config, Search & Carousels:
  - `web/src/lib/stores.ts` (Exclusively owned by M4)
  - `web/src/types.ts` (Exclusively owned by M4)
  - `web/src/api.ts` (Exclusively owned by M4)
  - `web/src/components/SearchScreen.tsx` (Exclusively owned by M4)
  - `web/src/components/OffersScreen.tsx` (Exclusively owned by M4)
  - `web/src/components/OffersSheet.tsx` (Exclusively owned by M4)
- Verification & E2E Testing Track:
  - `scratch/verify_connectors_live.py` (Exclusively owned by M5)
  - `scratch/verify_normalization_live.py` (Exclusively owned by M5)
  - `scratch/verify_endpoints_live.py` (Exclusively owned by M5)
  - `web/src/components/__tests__/DifferentiatedSearchAndCarousels.test.tsx` (Exclusively owned by M5)
  - `TEST_INFRA.md`, `TEST_READY.md` (Exclusively owned by M5)
