# 🖥️ Correr SuperVmarket en localhost (datos reales)

Modo desarrollo: **sin instalar Postgres**. Usa SQLite (un archivo) y datos
**reales** bajados por el scraper. La migración a Postgres/Neon se hace después.

## Requisitos
- Python 3.10+  ·  Node 18+
- Conexión a internet (el scraper baja precios reales; la verificación de
  carrito/zona consulta VTEX en vivo).

No hace falta configurar nada: por defecto se usa `sqlite:///./supervmarket.db`
en la raíz del repo (el scraper y la API comparten ese mismo archivo).

---

## Paso 1 · Cargar datos reales (scraper)
```bash
cd scraper
pip install -r requirements.txt
python run.py --limit 150      # ~150 productos por súper (rápido para probar)
```
- Tarda unos minutos. Sacá `--limit` para bajar el catálogo completo.
- Crea `supervmarket.db` en la raíz del repo con productos y precios reales
  de Jumbo, Disco, Vea, Carrefour, Dia y Coto.

## Paso 2 · Levantar la API
```bash
cd api
pip install -r requirements.txt
uvicorn index:app --reload --port 8000
```
Probala: http://localhost:8000/api/search?q=yerba

## Paso 3 · Levantar el frontend
```bash
cd web
npm install
npm run dev
```
Abrí http://localhost:5173 — Vite redirige `/api` al backend en el 8000.

---

## Qué probar
1. Buscá **"yerba"**, **"leche"**, **"coca"** → ves precios de varios súper, ordenados.
2. Cambiá el orden **Precio total ↔ Precio x unidad**.
3. **Agregá a mi lista** un par de productos → abrí **Mi lista** → **Optimizar**
   en los 3 modos (Ahorro / Comodidad / Balanceada).
4. Cargá tu **código postal** arriba → ves qué súper **entregan en tu zona** y,
   al **Verificar stock**, el stock/precio real de tu CP.

## Notas
- La búsqueda ignora acentos (busca "azucar" y encuentra "Azúcar").
- El botón **Comprar** abre el súper con el carrito armado (guest-link VTEX).
- Si un `python`/`pip` te da problemas en Windows, usá `py -m pip` y `py run.py`.
- Para reiniciar los datos, borrá `supervmarket.db` y volvé a correr el scraper.

## Cuando quieras migrar a producción
Cambiás `DATABASE_URL` a tu Postgres (Neon) y listo: el mismo código corre con
asyncpg. Ver `README.md` → Deploy en Vercel.
