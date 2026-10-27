# E2E Test Infra: SuperVmarket

## Test Philosophy
- Opaque-box, requirement-driven. No dependency on implementation internals.
- Methodology: Category-Partition + Boundary Value Analysis (BVA) + Pairwise Combinatorial Testing + Real-World Workload Testing.
- Focus: Verification of R1 (Diagnóstico), R2 (Smart Cart 3 Escenarios, Faltantes, Promos, Flete), R3 (Recurrencia & Mi lista habitual), R4 (Monetización no invasiva), R5 (TypeScript/Vite clean build, Mobile Touch, Zero regressions).

## Feature Inventory & Test Coverage Goals
| # | Feature | Source (requirement) | Tier 1 (Coverage) | Tier 2 (Boundary) | Tier 3 (Pairwise) | Tier 4 (Scenario) |
|---|---------|---------------------|:-----------------:|:-----------------:|:-----------------:|:-----------------:|
| 1 | Opción Más Barata (2-3 súper split) | R2.1 | ≥5 | ≥5 | ✓ | ✓ |
| 2 | Opción Equilibrada (Pareto balance) | R2.2 | ≥5 | ≥5 | ✓ | ✓ |
| 3 | Opción Cómoda (1 solo súper) | R2.3 | ≥5 | ≥5 | ✓ | ✓ |
| 4 | Desglose de Faltantes & Alternativas | R2 | ≥5 | ≥5 | ✓ | ✓ |
| 5 | Desglose de Promos & Beneficios | R2 | ≥5 | ≥5 | ✓ | ✓ |
| 6 | Cotización y Progreso de Flete | R2 | ≥5 | ≥5 | ✓ | ✓ |
| 7 | "Mi lista habitual" (localStorage/PWA) | R3 | ≥5 | ≥5 | ✓ | ✓ |
| 8 | Monitor de Precio de Canasta & Delta | R3 | ≥5 | ≥5 | ✓ | ✓ |
| 9 | Afiliación / CPA y Ofertas Patrocinadas | R4 | ≥5 | ≥5 | ✓ | ✓ |
| 10 | Matriz de Clasificación Integral | R1 | ≥5 | ≥5 | ✓ | ✓ |
| 11 | Build Limpio & Mobile Touch UI | R5 | ≥5 | ≥5 | ✓ | ✓ |
| 12 | Integración Oficial Mercado Libre & IA | R1, R5 | ≥5 | ≥5 | ✓ | ✓ |

## Test Architecture
- Test runner: Vitest / Node test runner for frontend tests (`web/`) + Pytest / unittest for backend optimizer (`api/`).
- Build verification: `npm run build` in `web/` (strict TypeScript, zero errors, production bundle).
- Backend verification: Python test execution of `optimizer.py` verifying all 3 scenarios, missing items contract, shipping fees, and Pareto thresholds.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Compra mensual familiar (18 productos, varios súper, promos por volumen, reintegro Santander) | F1, F2, F3, F4, F5, F6, F7 | Alta |
| 2 | Compra rápida de reposición (3 productos, preferencia comodidad 1 súper) | F3, F6, F7 | Media |
| 3 | Compra con faltante crítico en comercio principal y alternativa en Mercado Libre | F1, F4, F12 | Media |
| 4 | Guardado y recuperación de Lista Habitual con comparación de inflación semanal | F7, F8 | Media |
| 5 | Navegación mobile pura con selector de escenarios y checkout 1-click VTEX | F1, F2, F3, F11 | Media |

## Coverage Thresholds
- Tier 1: ≥5 per feature
- Tier 2: ≥5 per feature (where boundaries exist)
- Tier 3: Pairwise coverage of major feature interactions
- Tier 4: ≥5 realistic application scenarios
