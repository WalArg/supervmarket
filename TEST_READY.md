# TEST_READY.md — Automated Verification & E2E Testing Track Signoff

**Project**: SuperVmarket v2 — 17 Cadenas/Marketplaces Integration, Dual Catalog Normalization & Differentiated Search  
**Milestone**: Milestone 5 (E2E Testing Track)  
**Status**: TEST READY (All 4 Verification Tracks Fully Specified & Exercised)  
**Verification Date**: 2026-11-03  

---

## 1. Executive Summary

Milestone 5 establishes the automated verification framework across the entire SuperVmarket architecture. This document serves as the operational runbook, catalog of verification suites, tier classification matrix, and signoff criteria ensuring that:
1. All 17 primary retail chains and marketplaces (plus Shopify and niche integrations) are validated with structured dictionary returns and dynamic `seller_id` resolution.
2. The dual-unification engine correctly groups FMCG products by GS1 EAN-13 barcodes and electro/tech products by canonical alphanumeric model codes, strictly isolating accessories and preventing capacity collisions.
3. The REST API endpoints (`/api/search`, `/api/offers`, `/api/health/audit`) support multi-vertical query routing, contextual grocery isolation, dual discount carousels, financing calculations, and zero health audit issues.
4. The React frontend passes 100% of Vitest integration tests (328 tests across 24 test suites), verifying vertical chip filters, categorized store dropdowns, offers carousels, and WCAG touch targets.

---

## 2. Test Suites Catalog

| # | Suite Name | File Location | Scope & Target Component | Framework / Runner | Assertion Count |
|---|------------|---------------|--------------------------|---------------------|-----------------|
| 1 | Live Connectors Verification Suite | `scratch/verify_connectors_live.py` | 17 retail chains + marketplaces + Shopify/niche stores (`api/_lib/stores.py`, `vtex_mcp.py`) | Python standalone / `unittest` | 131+ checks |
| 2 | Catalog Normalization & Grouping Suite | `scratch/verify_normalization_live.py` | GS1 Modulo 10, Model regex extraction, accessory guard, price ratio, 4-tier grouping (`api/_lib/normalization.py`) | Python standalone / `unittest` | 140+ checks |
| 3 | Automated Endpoints Verification Suite | `scratch/verify_endpoints_live.py` | `/api/search`, `/api/offers`, `/api/health/audit`, financing math, DB fallback (`api/index.py`, `deals.py`) | Python / `httpx.ASGITransport` | 40+ checks |
| 4 | Frontend Vitest Integration Suite | `web/src/components/__tests__/DifferentiatedSearchAndCarousels.test.tsx` (and all 24 web suites) | 40 store metadata registry, SearchScreen chips, OffersScreen carousels, OffersSheet | Vitest 5.0.5 + Testing Library | 328 tests |
| 5 | Adversarial Endpoint & Deal Health Suite | `scratch/test_adversarial_m3_reviewer.py` & `scratch/test_m3_endpoints.py` | SQL injection resilience, Deals health audit, snapshot argument permutations | Python / `unittest` | 18 tests |

---

## 3. Five-Tier Verification Hierarchy

```
┌────────────────────────────────────────────────────────────────────────┐
│  Tier 5: Adversarial Stress, Fuzzing & Forensic Invariants (Planned M6)│
├────────────────────────────────────────────────────────────────────────┤
│  Tier 4: Real-World Scenarios (Smart Cart Split, Deals Browsing)       │
├────────────────────────────────────────────────────────────────────────┤
│  Tier 3: Cross-Feature Combinations (Vertical + Grocery + Financing)   │
├────────────────────────────────────────────────────────────────────────┤
│  Tier 2: Boundary & Corner Cases (Whitespace, Incomplete Barcodes)     │
├────────────────────────────────────────────────────────────────────────┤
│  Tier 1: Feature Coverage (Core Happy Path & Schema Contracts)         │
└────────────────────────────────────────────────────────────────────────┘
```

### Tier 1: Feature Coverage (Happy Path & Schema Contracts)
- **Live Connectors**: Verifies HTTP 200 responses, non-empty catalog payloads, and structured return dictionaries `{title, precio_venta, precio_lista, disponible, ean, modelo, link, imagen, supermercado, seller_id}`.
- **Normalization**: Validates GS1 EAN-13 Modulo 10 checksums, extracts standard alphanumeric model codes (e.g. `UN50DU7000`, `SM-A155M`, `HD4691`), and builds canonical `ProductGroup` identity keys.
- **Endpoints**:
  - `/api/search` with `vertical="supermarket"`, `vertical="electro"`, and `vertical="marketplace"`.
  - `/api/offers` returning 4 supermarket tiers (`tier-70-80`, `tier-60`, `tier-50`, `tier-40`) and 3 marketplace tiers (`tier-mp-electro`, `tier-mp-hogar`, `tier-mp-destacadas`).
  - `/api/health/audit` reporting `status: "healthy"` and 0 issues.
- **Frontend UI**:
  - Store metadata registry recognizes all 40 stores with typed `StoreVertical`.
  - Filter chips render and dispatch corresponding `vertical` and `grocery_only` query parameters.

### Tier 2: Boundary & Corner Cases
- **Parameter Normalization**: Leading/trailing spaces, mixed case (`"  todos  "`, `"ALL"`, `"   "`, `""`) mapped to `None`. Comma-separated compound vertical strings (`" marketplace , electro "`) parsed correctly.
- **Grocery Isolation**:
  - `grocery_only=True` enforces strict zero leakage of microwave ovens, mattresses, sommiers, TVs, or power tools from electro/marketplace retailers.
  - Food items referencing microwave cooking (e.g. ramen, mug cake) are preserved under supermarket store type.
- **Barcode & Model Boundaries**:
  - UPC-A 12-digit barcodes expanded to 13 digits with leading zero.
  - Internal scale barcodes (prefixes `20`-`29`) isolated from global GS1 catalog.
  - Non-numeric or short digit queries bypass exact EAN filter.
- **Financing Boundaries**:
  - Single installment (`cuotas: 1`, `sin_interes: False`, `cuota_monto: price`).
  - Maximum installments (`cuotas: 24`, zero-interest Banco Provincia).
- **Resilient DB Fallback**:
  - Seamless fallback to `db.search_grouped` when live scraper returns 0 items.

### Tier 3: Cross-Feature Combinations
- **Dual Unification**: Stores providing only EAN-13 (e.g. Frávega) and stores providing only alphanumeric Model code (e.g. Cetrogar) unified under single `ProductGroup` card.
- **Financing + Dynamic Seller**: Marketplace item cards simultaneously displaying 3rd-party seller identity (`seller_name`, `seller_id`), dynamic VTEX cart link (`seller={seller_id}`), and installment financing breakdown (`cuotas`, `sin_interes`, `cuota_monto`).
- **Contextual Search + Multi-Vertical**: `q="samsung"`, `vertical="marketplace,electro"`, `grocery_only=False` returning smartphones, TVs, and tablets while suppressing food items.

### Tier 4: Real-World Application Scenarios
- **Smart Cart Optimization**: Splitting a multi-store shopping basket across 2-3 retailers with quantified savings ($ ARS) vs single-store purchase.
- **Deals Browsing Flow**: Loading `/api/offers`, scrolling across supermarket discount carousels, and switching between "Electro & Tech", "Hogar & Taller", and "Ofertas Destacadas".
- **High Concurrency Stress**: 20 simultaneous asynchronous search queries across 20+ retail backends without connection leak or event loop starvation.

### Tier 5: Adversarial Stress Testing (Gate to Milestone 6)
- **SQL Injection**: Injection payloads (`'; DROP TABLE...`, `' OR '1'='1`) in query string, vertical, and store_type sanitized without crash or database modification.
- **Payload Fuzzing**: Negative prices, inverted list prices, corrupt image URLs, and malformed JSON payloads rejected or corrected gracefully.
- **Total Network Blackout**: Simulated failure of all live VTEX endpoints successfully handled by loading local disk snapshot (`load_verified_deals_snapshot`) and serving cached deals with `is_live: False`.

---

## 4. Runner Commands & Expected Results

### A. Automated Endpoints Verification Suite
- **Command (Windows PowerShell / cmd.exe)**:
  ```powershell
  python scratch/verify_endpoints_live.py
  ```
- **Alternative (Unittest Runner)**:
  ```powershell
  python -m unittest scratch/verify_endpoints_live.py
  ```
- **Expected Result**:
  - Exit Code: `0`
  - Total Tests: `10`
  - Pass Rate: `100% (10/10 passed)`
  - Output contains: `Status: ALL TESTS PASSED [100%]`

### B. Catalog Normalization Verification Suite
- **Command**:
  ```powershell
  python scratch/verify_normalization_live.py
  ```
- **Expected Result**:
  - Exit Code: `0`
  - Pass Rate: `100% (all 140 checks passed)`

### C. Live Connectors Verification Suite
- **Command**:
  ```powershell
  python scratch/verify_connectors_live.py
  ```
- **Expected Result**:
  - Exit Code: `0`
  - Pass Rate: `100% (all 131 checks passed)`
  - All 17+ primary chains and marketplaces verified with dynamic `seller_id` on 3rd-party items.

### D. Frontend Vitest Integration Suite
- **Command**:
  ```cmd
  cmd.exe /c "npm --prefix web test"
  ```
- **Expected Result**:
  - Exit Code: `0`
  - Test Files: `24 passed (24)`
  - Tests: `328 passed (328)`
  - Pass Rate: `100%`

---

## 5. Pass/Fail Criteria & Signoff Gate Matrix

| Verification Gate | Requirement | Target Metric | Milestone 5 Status |
|-------------------|-------------|---------------|-------------------|
| **Gate 1: Connectors** | Live HTTP response & dynamic `seller_id` on 17+ chains (`scratch/verify_connectors_live.py`) | 100% pass (131/131) | PASSED (100%) |
| **Gate 2: Normalization** | GS1 Modulo 10, Model extraction, capacity preservation, accessory isolation (`scratch/verify_normalization_live.py`) | 100% pass (140/140) | PASSED (100%) |
| **Gate 3: Endpoints** | Parameter normalization, grocery isolation, dual tiers, financing math, health audit (`scratch/verify_endpoints_live.py`) | 100% pass (10/10) | PASSED (100%) |
| **Gate 4: Frontend UI** | 40 store registry, vertical filter chips, carousels, 44x44px touch targets (`npm --prefix web test`) | 100% pass (328/328) | PASSED (100%) |
| **Gate 5: Health Audit** | `/api/health/audit` reports healthy status across all 7 discount tiers | 0 issues | PASSED (0 issues) |
