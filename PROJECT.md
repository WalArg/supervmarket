# Project: SuperVmarket — Evolución de Producto y Smart Cart (Fase 1)

## Architecture
SuperVmarket es un comparador y optimizador de changuito de supermercado masivo en tiempo real para Argentina.
- **Frontend (`web/`)**: React 19, TypeScript strict mode, Vite 7, Tailwind CSS, Framer Motion, Lucide React.
  - `web/src/components/ListScreen.tsx`: Eje central mobile de Smart Cart. Jerarquía invertida con selector hero de 3 escenarios en viewport superior, drawer colapsable de productos y barra compacta de contexto (CP, medios de pago, flete).
  - `web/src/components/StoreCart.tsx`: Tarjetas de supermercado individuales con desglose de productos, promociones por volumen (2x1, 2do al X%), reintegros bancarios, costo de flete cotizado y barra de progreso a envío gratis. Checkout 1-click para VTEX y guía de compra para Coto.
  - `web/src/cart/CartContext.tsx`: Estado reactivo del carrito en memoria y sincronizado en `localStorage` (`sv_cart_v2`).
  - `web/src/cart/HabitualListContext.tsx`: Gestión sin fricción de "Mi lista habitual" en `localStorage` (`sv_habitual_v1`) y seguimiento de histórico de precios (`sv_basket_history_v1`).
- **Backend (`api/`)**: Python 3.12 Serverless sobre FastAPI en Vercel.
  - `api/_lib/optimizer.py`: Motor de optimización combinatoria. Genera en 1 pasada los 3 escenarios: Más Barata (split óptimo 2-3 supermercados con ahorro $ respecto a súper único), Equilibrada (frontera de Pareto: umbral de indiferencia $\ge \$3.500$ ARS y $\ge 5\%$ para evitar fricción logística innecesaria), y Cómoda (1 solo supermercado con máxima cobertura).
  - `api/_lib/vtex_mcp.py`: Motor concurrente asíncrono (`asyncio.gather`) para consulta en vivo a 11 cadenas VTEX, Coto Endeca y Mercado Libre.
  - `api/_lib/mercadolibre.py`: Integración oficial con Mercado Libre (OAuth Client Credentials, catálogo MLA, envíos FULL, reputación y cotización dinámica de flete por CP).
  - `api/_lib/stores.py`: Gestión de metadatos de cadenas y atributos de afiliación/CPA.
  - `api/_lib/benefits.py`: Catálogo y cálculo de promociones bancarias, billeteras (MODO, Mercado Pago, Cuenta DNI) y membresías.

---

## Feature Inventory
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

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|--------------|--------|
| M1 | Diagnóstico y Plan de Evolución de Producto | Entrega de matriz formal de clasificación (MANTENER, MEJORAR, SIMPLIFICAR, ELIMINAR, AGREGAR), justificación de impacto, y simplificación de fricciones | none | DONE (`docs/PRODUCT_DIAGNOSIS_AND_EVOLUTION.md`) |
| M2 | Backend Optimizer Multi-Escenario | Algoritmo en `api/_lib/optimizer.py` para los 3 escenarios (Más Barata 2-3 supers, Equilibrada Pareto, Cómoda 1 super), faltantes enriquecidos con alternativas y costos de envío | none | DONE (`api/_lib/optimizer.py`) |
| M3 | Frontend Smart Cart como Eje Central Mobile | Rediseño de `web/src/components/ListScreen.tsx` y `StoreCart.tsx`: Héroe comparativo 3 escenarios, desgloses (faltantes, promos, bancos, flete), touch targets $\ge 44$px | M2 | PLANNED |
| M4 | Arquitectura de Recurrencia sin Cuenta | Implementación de "Mi lista habitual" en `localStorage`/PWA, guardado/carga 1-toque, y monitor histórico de precio de canasta | M3 | PLANNED |
| M5 | Modelo de Monetización sin Suscripción | Especificación y arquitectura de Afiliación/CPA en checkouts, cashback con marcas y ofertas patrocinadas nativas | M1, M3 | PLANNED |
| M6 | QA, Rendimiento y Verificación E2E | Verificación integral de build (`npm run build`), pruebas E2E de los 3 escenarios, validación mobile touch y auditoría forense | M1..M5 | PLANNED |

---

## Interface Contracts

### 1. Backend Optimization Response (`api/_lib/optimizer.py` -> `web/src/`)
```typescript
export interface ScenarioPreview {
  mode: 'ahorro' | 'balanceada' | 'comodidad'
  title: string // "Opción más barata", "Opción equilibrada", "Opción cómoda"
  tagline: string // "Split óptimo 2-3 súper", "Ahorro vs conveniencia", "Todo en 1 solo súper"
  total: number
  ahorro_vs_comoda: number // Pesos ahorrados respecto a comprar todo en 1 súper
  ahorro_vs_regular: number // Pesos ahorrados respecto al precio de lista
  ahorro_pct: number
  supermercados_count: number
  covered_items: number
  total_items: number
  badge?: string // e.g. "MÁXIMO AHORRO", "RECOMENDADA", "MÁS RÁPIDA"
  logistics_warning?: string
}

export interface MissingItemDetail {
  ean: string
  nombre: string
  missing_in_assigned_stores: string[]
  available_in_other_stores?: {
    supermercado: string
    precio: number
    promo_badge?: string
  }[]
}

export interface StoreCartBreakdown {
  supermercado: string
  items: CartItemDetail[]
  subtotal_merch: number
  volume_discounts_total: number
  bank_discount_amount: number
  bank_card_applied?: string
  shipping_fee: number
  free_shipping_threshold: number
  is_free_shipping: boolean
  amount_for_free_shipping: number
  final_store_total: number
  checkout_url?: string
  is_vtex: boolean
}
```

### 2. Recurrence Data Contract (`web/src/cart/HabitualListContext.tsx`)
```typescript
export interface HabitualItem {
  ean: string
  nombre: string
  imagen: string
  qty: number
}

export interface HabitualList {
  updated_at: string
  items: HabitualItem[]
}

export interface BasketSnapshot {
  timestamp: string // ISO
  total_comodidad: number
  total_ahorro: number
  ahorro_ars: number
  items_count: number
}
```

---

## Code Layout
- Frontend: `web/src/`
  - `web/src/components/ListScreen.tsx`
  - `web/src/components/StoreCart.tsx`
  - `web/src/components/SmartCartHero.tsx` (Nuevo componente modular para el selector de los 3 escenarios)
  - `web/src/components/MissingItemsBreakdown.tsx` (Nuevo componente para productos faltantes y alternativas)
  - `web/src/components/HabitualListManager.tsx` (Nuevo componente para gestionar lista habitual y monitor de ahorro)
  - `web/src/cart/HabitualListContext.tsx` (Contexto de persistencia y seguimiento histórico)
  - `web/src/types.ts`
- Backend: `api/`
  - `api/_lib/optimizer.py`
  - `api/_lib/stores.py`
  - `api/_lib/mercadolibre.py`
- Documentación de Producto & Monetización:
  - `docs/PRODUCT_DIAGNOSIS_AND_EVOLUTION.md` (Entregable formal de R1, R3 y R4)
