# Dead Ends Log

| Iteration | Approach Tried | Why It Failed | Files Touched |
|-----------|---------------|---------------|---------------|
| M2 Iter 1 | Basic evaluation order (carnes_verduleria before limpieza/perfumeria) | Fragrant cleaning and shampoo items with lemon/apple words misclassified as produce | `api/_lib/catalog_normalizer.py` |
| M2 Iter 2 | Narrow regex blacklist on pure and canned items (`RE_ALMACEN_PROCESSED`) | Missed plural forms (`pure de tomates`), pates, and specialty canned formats | `api/_lib/catalog_normalizer.py` |
| M2 Iter 3 | Title-only keyword matching for canned/pureed goods (`lata`, `pure`, etc.) | Failed on 202 dry groceries, teas, cookies, and canned fruits whose titles lack literal word "lata" (e.g., `Durazno en Mitades`, `Arvejas Cuisine & Co`, `Té Limón`) even though their category path is clearly `Almacén/Conservas` or `Desayuno/Merienda` | `api/_lib/catalog_normalizer.py`, `scripts/verify_normalization_m2.py` |
