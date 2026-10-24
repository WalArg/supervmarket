# 🛒 SuperVmarket

Comparador de precios de supermercados de Argentina + **Smart Cart** que arma
carritos por súper y te redirige a comprar con el carrito ya cargado.

- **Comparar**: buscás un producto y ves el precio en todos los súper, unificado
  por código de barras (EAN), con precio por kg/l para comparar de verdad.
- **Armar lista**: agregás productos a tu lista.
- **Optimizar**: el Smart Cart calcula dónde comprar en 3 modos:
  - **Ahorro** — cada producto en el más barato (varias paradas).
  - **Comodidad** — todo en un solo súper (el más conveniente).
  - **Balanceada** — hasta 2 súper, equilibrio entre ahorro y comodidad.
- **Comprar**: botón que te lleva al súper con el carrito armado (guest-link VTEX),
  validando stock y mínimo de compra en vivo.

## 🧱 Arquitectura

```
Scraper (Python, GitHub Actions cron c/8h) ──► Postgres (Neon) ◄── API (FastAPI serverless en Vercel)
                                                                          ▲
                                                          Frontend (Vite + React) en Vercel
```

- **Scraper**: Python. Crawlea VTEX (Jumbo, Disco, Vea, Carrefour, Dia) + Coto
  (Endeca). Corre en GitHub Actions y escribe en Postgres. No vive en Vercel
  (es un proceso largo).
- **DB**: Postgres gestionado (Neon free tier). Catálogo unificado por EAN +
  historial de precios + búsqueda fuzzy (`pg_trgm` + `unaccent`).
- **API**: FastAPI como **función serverless de Python en Vercel** (`/api/*`).
- **Frontend**: tu SPA Vite + React (conservada y extendida con el Smart Cart).

## 📂 Estructura

```
supervmarket/
├── vercel.json              # build del front + ruteo de /api a la función Python
├── .env.example
├── db/
│   └── schema.sql           # esquema Postgres (lo aplica el scraper solo)
├── scraper/                 # corre en GitHub Actions
│   ├── run.py               # orquestador (python run.py [--limit N])
│   ├── db.py                # escritura a Postgres (asyncpg, upsert)
│   ├── utils.py             # normalización de unidades/categorías
│   └── scrapers/
│       ├── base.py
│       ├── vtex.py          # Jumbo, Disco, Vea, Carrefour, Dia
│       └── coto.py          # Coto (no-VTEX, solo comparar en v1)
├── api/                     # función serverless en Vercel
│   ├── index.py             # FastAPI: /search /suggest /optimize /cart/validate
│   ├── requirements.txt
│   └── _lib/
│       ├── db.py            # pool asyncpg + queries
│       ├── optimizer.py     # 3 modos del Smart Cart
│       ├── carts.py         # validación en vivo + guest-link VTEX
│       └── stores.py        # config de tiendas, dominios, mínimos
├── web/                     # frontend Vite + React
│   └── src/
│       ├── App.tsx
│       ├── api.ts
│       ├── cart/CartContext.tsx
│       └── components/  (ProductRow, OfferCard, SmartCart, StoreCart)
└── .github/workflows/
    └── scraper.yml          # cron del scraper
```

## 🚀 Puesta en marcha

### 1. Base de datos (Neon)
1. Creá un proyecto gratis en https://neon.tech y copiá la connection string.
2. Usá la variante **pooled** (host con `-pooler`) para la API.

### 2. Cargar datos (scraper)
```bash
cd scraper
pip install -r requirements.txt
export DATABASE_URL="postgresql://...:.../db?sslmode=require"
python run.py --limit 200      # prueba rápida; sacá --limit para todo
```
El scraper crea las tablas solo (`db/schema.sql`) y carga productos/precios.

### 3. Desarrollo local
**¿Solo querés probarlo en tu máquina?** Mirá **[LOCAL.md](LOCAL.md)**: corre con
SQLite (sin instalar Postgres) y datos reales, en 3 pasos. Resumen:
```bash
# 1) Datos reales (crea ./supervmarket.db en la raíz)
cd scraper && pip install -r requirements.txt && python run.py --limit 150
# 2) API (terminal 1)
cd api && pip install -r requirements.txt && uvicorn index:app --reload --port 8000
# 3) Frontend (terminal 2)
cd web && npm install && npm run dev   # http://localhost:5173 (proxy /api -> :8000)
```
Por defecto usa `DATABASE_URL=sqlite:///./supervmarket.db`. Para apuntar a Postgres,
exportá `DATABASE_URL` con la cadena de Neon.

### 4. Deploy en Vercel
1. Subí el repo a GitHub.
2. Importá el repo en Vercel (framework: *Other*; `vercel.json` ya define todo).
3. En **Settings → Environment Variables** agregá `DATABASE_URL` (la pooled de Neon).
4. Deploy. El front queda en `/` y la API en `/api/*` (mismo origen, sin CORS).

### 5. Scraper automático (GitHub Actions)
1. En el repo: **Settings → Secrets → Actions** → agregá `DATABASE_URL`.
2. El workflow `.github/workflows/scraper.yml` corre cada 8 h (o a mano desde Actions).

## ⚙️ Endpoints de la API
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/search?q=&sort=price_asc\|unit_price_asc` | Búsqueda agrupada por EAN |
| GET | `/api/suggest?q=` | Autocompletado |
| GET | `/api/regions?cp=` | Qué supermercados entregan en ese código postal |
| POST | `/api/optimize` | `{items:[{ean,qty}], mode}` → plan Smart Cart |
| POST | `/api/cart/validate` | `{supermercado, items, cp}` → stock/precio/mínimo **regionalizado** |

## 📍 Ubicación primero (regionalización)
El flujo arranca pidiendo el **código postal** (selector arriba de todo, se guarda
en el navegador). Con eso:
1. **Cobertura** (`/api/regions`): consulta la *Regions API* de VTEX por cada súper
   y muestra cuáles **entregan en tu zona** (y cuáles no).
2. **Comparación**: la búsqueda usa precios de referencia de la base; los súper que
   no llegan a tu CP se marcan.
3. **Verificación antes de comprar**: al revisar un carrito, `/api/cart/validate`
   corre la **simulación de VTEX con tu CP** → stock real, precio regionalizado,
   envío y mínimo de compra **para tu ubicación**.

## 📝 Notas y límites conocidos (para tunear)
- **Coto** es "solo comparar" en v1: entra en la comparación y el Smart Cart, pero
  no genera carrito automático (su checkout no es VTEX). Próximo paso: link de carrito propio.
- **Normalización de unidades**: queda todo en kg/l/un con un clamp de seguridad.
  Aún así conviene sumar tests por tienda (es la parte más delicada).
- **Seller / región**: el guest-link usa `seller=1` (funciona en general). Mejora
  futura: resolver seller por código postal con `GET /api/checkout/pub/regions`.
- **Sin Jumbo/Disco/Vea en carrito todavía**: están en `VTEX_DOMAINS`, listos para
  habilitar; solo falta validar SKUs reales en producción.

## 🗺️ Roadmap sugerido
1. Habilitar carrito en Jumbo/Disco/Vea (ya están casi listos).
2. Autocompletado en el buscador (endpoint `/api/suggest` ya existe).
3. Gráfico de historial de precios (tabla `historial_precios` ya se llena).
4. Carrito de Coto (reverse del checkout).
5. Seller dinámico por región.
