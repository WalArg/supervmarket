import json
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT_DIR, "scratch", "verified_real_gondolas.json")

with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

tiers_meta = [
    {
        "id": "tier-mp-electro",
        "title": "Electrodomésticos y Tecnología — Hasta 40% OFF y Cuotas",
        "subtitle": "Smart TVs, celulares, notebooks, lavarropas y heladeras con financiación",
        "badge": "Electro & Tech",
        "percentLabel": "Hasta 40% OFF + Cuotas",
        "icon": "zap",
        "vertical": "electro",
    },
    {
        "id": "tier-mp-hogar",
        "title": "Hogar, Herramientas y Climatización — Gran Ahorro",
        "subtitle": "Sommiers, colchones de espuma y resortes con hasta 75% OFF",
        "badge": "Hogar & Descanso",
        "percentLabel": "Hasta 70% OFF",
        "icon": "tag",
        "vertical": "marketplace",
    },
    {
        "id": "tier-mp-destacadas",
        "title": "Ofertas Destacadas de Marketplaces — Precios Bomba",
        "subtitle": "Oportunidades de Naldo, Sony Store, Samsung Oficial con financiación",
        "badge": "Marketplaces",
        "percentLabel": "Financiación y Rebajas",
        "icon": "flame",
        "vertical": "marketplace",
    },
]

# Generate TypeScript
ts_lines = ["export const MARKETPLACE_DISCOUNT_TIERS: DiscountTier[] = ["]
for tm in tiers_meta:
    tid = tm["id"]
    prods = data[tid]
    ts_lines.append("  {")
    ts_lines.append(f"    id: '{tid}',")
    ts_lines.append(f"    title: '{tm['title']}',")
    ts_lines.append(f"    subtitle: '{tm['subtitle']}',")
    ts_lines.append(f"    badge: '{tm['badge']}',")
    ts_lines.append(f"    percentLabel: '{tm['percentLabel']}',")
    ts_lines.append(f"    icon: '{tm['icon']}',")
    ts_lines.append(f"    vertical: '{tm['vertical']}',")
    ts_lines.append("    products: [")
    for p in prods:
        ts_lines.append("      {")
        ts_lines.append(f"        id: '{p['id']}',")
        ts_lines.append(f"        ean: '{p['ean']}',")
        ts_lines.append(f"        primary_ean: '{p.get('primary_ean', p['ean'])}',")
        nom = p['nombre'].replace("'", "\\'")
        marca = p['marca'].replace("'", "\\'")
        mod = p.get('modelo', '').replace("'", "\\'")
        ts_lines.append(f"        nombre: '{nom}',")
        ts_lines.append(f"        marca: '{marca}',")
        ts_lines.append(f"        modelo: '{mod}',")
        ts_lines.append(f"        tipo: '{p.get('tipo', 'electro')}',")
        ts_lines.append(f"        vertical: '{p.get('vertical', 'electro')}',")
        ts_lines.append(f"        categoria_normalizada: '{p.get('categoria_normalizada', '')}',")
        ts_lines.append(f"        imagen: '{p['imagen']}',")
        ts_lines.append("        offers: [")
        for o in p["offers"]:
            ts_lines.append("          {")
            ts_lines.append(f"            supermercado: '{o['supermercado']}',")
            ts_lines.append(f"            precio: {o['precio']},")
            ts_lines.append(f"            precio_lista: {o['precio_lista']},")
            ts_lines.append(f"            stock: {o['stock']},")
            disp = "true" if o["disponible"] else "false"
            ts_lines.append(f"            disponible: {disp},")
            ts_lines.append(f"            discount: {o['discount']},")
            pl = f"'{o['promo_label']}'" if o["promo_label"] else "null"
            ts_lines.append(f"            promo_label: {pl},")
            ts_lines.append(f"            seller_name: '{o['seller_name']}',")
            ts_lines.append(f"            seller_id: '{o['seller_id']}',")
            ts_lines.append(f"            store_type: '{o['store_type']}',")
            ts_lines.append(f"            link: '{o['link']}',")
            ts_lines.append("          },")
        ts_lines.append("        ],")
        ts_lines.append("      },")
    ts_lines.append("    ],")
    ts_lines.append("  },")
ts_lines.append("]")
ts_lines.append("")

out_ts_path = os.path.join(ROOT_DIR, "scratch", "marketplace_tiers.ts")
with open(out_ts_path, "w", encoding="utf-8") as f:
    f.write("\n".join(ts_lines))

# Generate Python
py_lines = ["BASELINE_MARKETPLACE_TIERS = ["]
for tm in tiers_meta:
    tid = tm["id"]
    prods = data[tid]
    py_lines.append("    {")
    py_lines.append(f'        "id": "{tid}",')
    py_lines.append(f'        "title": "{tm["title"]}",')
    py_lines.append(f'        "subtitle": "{tm["subtitle"]}",')
    py_lines.append(f'        "badge": "{tm["badge"]}",')
    py_lines.append(f'        "percentLabel": "{tm["percentLabel"]}",')
    py_lines.append(f'        "icon": "{tm["icon"]}",')
    py_lines.append(f'        "vertical": "{tm["vertical"]}",')
    py_lines.append('        "products": [')
    for p in prods:
        py_lines.append("            {")
        py_lines.append(f'                "id": "{p["id"]}",')
        py_lines.append(f'                "ean": "{p["ean"]}",')
        py_lines.append(f'                "primary_ean": "{p.get("primary_ean", p["ean"])}",')
        nom = p['nombre'].replace('"', '\\"')
        marca = p['marca'].replace('"', '\\"')
        mod = p.get('modelo', '').replace('"', '\\"')
        py_lines.append(f'                "nombre": "{nom}",')
        py_lines.append(f'                "marca": "{marca}",')
        py_lines.append(f'                "modelo": "{mod}",')
        py_lines.append(f'                "tipo": "{p.get("tipo", "electro")}",')
        py_lines.append(f'                "vertical": "{p.get("vertical", "electro")}",')
        py_lines.append(f'                "categoria_normalizada": "{p.get("categoria_normalizada", "")}",')
        py_lines.append(f'                "imagen": "{p["imagen"]}",')
        py_lines.append('                "offers": [')
        for o in p["offers"]:
            py_lines.append("                    {")
            py_lines.append(f'                        "supermercado": "{o["supermercado"]}",')
            py_lines.append(f'                        "precio": {o["precio"]},')
            py_lines.append(f'                        "precio_lista": {o["precio_lista"]},')
            py_lines.append(f'                        "stock": {o["stock"]},')
            disp = "True" if o["disponible"] else "False"
            py_lines.append(f'                        "disponible": {disp},')
            py_lines.append(f'                        "discount": {o["discount"]},')
            pl = f'"{o["promo_label"]}"' if o["promo_label"] else "None"
            py_lines.append(f'                        "promo_label": {pl},')
            py_lines.append(f'                        "seller_name": "{o["seller_name"]}",')
            py_lines.append(f'                        "seller_id": "{o["seller_id"]}",')
            py_lines.append(f'                        "store_type": "{o["store_type"]}",')
            py_lines.append(f'                        "link": "{o["link"]}",')
            py_lines.append("                    },")
        py_lines.append("                ],")
        py_lines.append("            },")
    py_lines.append("        ],")
    py_lines.append("    },")
py_lines.append("]")
py_lines.append("")

out_py_path = os.path.join(ROOT_DIR, "scratch", "marketplace_tiers.py")
with open(out_py_path, "w", encoding="utf-8") as f:
    f.write("\n".join(py_lines))

print("Both TS and Python formats written successfully!")
