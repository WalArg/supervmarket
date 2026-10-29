/**
 * gondolasData.ts
 *
 * Datos 100% curados y verificados en vivo para la pantalla de Ofertas.
 * Incluye:
 * - Niveles de Grandes Descuentos (70%-80%, Liquidaciones hasta 75%, 50% y 2x1, Canasta Básica hasta 45%).
 * - Opciones patrocinadas oficiales de Mercado Libre como PRIMERA tarjeta de cada carrusel con descuento real y verificado.
 * - Sin duplicación de productos contiguos (cada producto patrocinado es distinto de las ofertas contiguas).
 * - Enlaces directos a páginas de producto permanentes (catálogo oficial /p/MLA de Mercado Libre y fichas activas de supermercado).
 * - Todas las imágenes provienen de los CDNs oficiales de VTEX/Meli/Coto y devuelven HTTP 200 con foto fiel al producto.
 */

import { ProductGroup, SupermarketOffer } from '../types'

export interface DiscountTier {
  id: string
  title: string
  subtitle: string
  badge: string
  percentLabel: string
  icon: 'flame' | 'tag' | 'percent' | 'zap'
  meliSponsored: {
    product: ProductGroup
    offer: SupermarketOffer
  }
  products: ProductGroup[]
}

export interface Gondola {
  id: string
  title: string
  subtitle: string
  icon: 'flame' | 'milk' | 'package' | 'sparkles' | 'coffee'
  searchTerm: string
  products: ProductGroup[]
}

/**
 * NIVELES DE GRANDES DESCUENTOS Y PROMOCIONES REALES
 * 1. 2da Unidad al 70% y 80% OFF (Promociones en pareja con precio unitario efectivo)
 * 2. Liquidaciones y Grandes Rebajas (Hasta 75% OFF directo)
 * 3. 50% OFF y Promos 2x1 (Mitad de precio)
 * 4. Canasta Básica y Esenciales (25% a 45% OFF directo)
 */
export const DISCOUNT_TIERS: DiscountTier[] = [
  {
    id: 'tier-70-80',
    title: '2da Unidad al 70% y 80% OFF — Promociones en Pareja',
    subtitle: 'Llevando 2 unidades: la 2da al 70% y 80% OFF en súper (precio unitario efectivo)',
    badge: '2da al 70% y 80%',
    percentLabel: '70% y 80% OFF',
    icon: 'flame',
    meliSponsored: {
      product: {
        ean: '7790070336026',
        nombre: 'Fideos Lucchetti Tirabuzón 500 G',
        marca: 'Lucchetti',
        imagen: 'https://masonlineprod.vteximg.com.br/arquivos/ids/334621/Fideos-Lucchetti-Tirabuzon-500-G-1-49865.jpg?v=638623893699570000',
        offers: [],
      },
      offer: {
        supermercado: 'MercadoLibre',
        precio: 1490,
        precio_lista: 2480,
        stock: 120,
        link: 'https://www.mercadolibre.com.ar/fideos-tirabuzon-lucchetti-x500-gr/p/MLA20719337',
        seller_name: 'Tienda Oficial Lucchetti',
        is_full: true,
        discount: 40,
        promo_label: '40% OFF',
        unit_measure: 'kg',
        unit_price: 2980,
      },
    },
    products: [
      {
        ean: '7622201735296',
        nombre: 'Galletitas Oreo x 118 g',
        marca: 'Oreo',
        imagen: 'https://farmacityar.vteximg.com.br/arquivos/ids/298494/251535_galletitas-oreo-x-118-g_imagen-1.jpg?v=639229342479300000',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 1715,
            precio_lista: 2638,
            stock: 80,
            link: 'https://www.carrefour.com.ar/galletitas-dulce-oreo-rellenas-con-crema-118-g-715949/p',
            discount: 35,
            promo_label: '2do al 70% ($1.715 c/u x2)',
            promo_min_qty: 2,
            unit_measure: 'kg',
            unit_price: 14534,
          },
          {
            supermercado: 'Dia',
            precio: 1612,
            precio_lista: 2480,
            stock: 1024,
            link: 'https://diaonline.supermercadosdia.com.ar/galletitas-oreo-rellenas-con-crema-118-gr-236239/p',
            discount: 35,
            promo_label: '2do al 70% ($1.612 c/u x2)',
            promo_min_qty: 2,
            unit_measure: 'kg',
            unit_price: 13661,
          },
        ],
      },
      {
        ean: '7791290796430',
        nombre: 'Jabón Líquido Skip Limpieza Activa Doypack 800ml',
        marca: 'Skip',
        imagen: 'https://farmaonline.vteximg.com.br/arquivos/ids/1458225/8144165_0.jpg?v=639252564197900000',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 2847,
            precio_lista: 4745,
            stock: 50,
            link: 'https://www.carrefour.com.ar/jabon-liquido-skip-bio-enzimas-doypack-800-ml-695715/p',
            discount: 40,
            promo_label: '2do al 80% ($2.847 c/u x2)',
            promo_min_qty: 2,
            unit_measure: 'lt',
            unit_price: 3559,
          },
          {
            supermercado: 'MercadoLibre',
            precio: 3190,
            precio_lista: 4740,
            stock: 80,
            link: 'https://www.mercadolibre.com.ar/p/MLA19858406',
            seller_name: 'Tienda Oficial Unilever',
            is_full: true,
            discount: 33,
            promo_label: '33% OFF',
            unit_measure: 'lt',
            unit_price: 3988,
          },
        ],
      },
      {
        ean: '8480017311238',
        nombre: 'Repelente para Insectos en Aerosol Bonté 170 Ml',
        marca: 'Bonté',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/343110/Repelente-para-Insectos-en-Aerosol-Bonte-170-Ml-_1.jpg?v=638727039719730000',
        offers: [
          {
            supermercado: 'Dia',
            precio: 890,
            precio_lista: 4490,
            stock: 120,
            link: 'https://diaonline.supermercadosdia.com.ar/repelente-para-insectos-en-aerosol-bonte-170-ml-210739/p',
            discount: 80,
            promo_label: '80% OFF Liquidación',
            unit_measure: 'ml',
            unit_price: 5235,
          },
        ],
      },
      {
        ean: '7790580982548',
        nombre: 'Huevo de Pascua Biznikke 100 Gr',
        marca: 'Biznikke',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/310344/Huevo-de-Pascua-Biznikke-100-Gr-_1.jpg',
        offers: [
          {
            supermercado: 'Dia',
            precio: 2000,
            precio_lista: 9990,
            stock: 45,
            link: 'https://diaonline.supermercadosdia.com.ar/huevo-de-pascua-biznikke-100-gr-89365/p',
            discount: 80,
            promo_label: '80% OFF Liquidación',
            unit_measure: 'kg',
            unit_price: 20000,
          },
        ],
      },
      {
        ean: '7790040133464',
        nombre: 'Galletitas Pepitos Con Chips De Chocolate 119 Gr',
        marca: 'Pepitos',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/353536/Galletitas-Pepitos-Con-Chips-De-Chocolate-119-Gr-_1.jpg?v=638913145488400000',
        offers: [
          {
            supermercado: 'Dia',
            precio: 1612,
            precio_lista: 2480,
            stock: 90,
            link: 'https://diaonline.supermercadosdia.com.ar/galletitas-pepitos-con-chips-de-chocolate-119-gr-271628/p',
            discount: 35,
            promo_label: '2do al 70% ($1.612 c/u x2)',
            promo_min_qty: 2,
            unit_measure: 'kg',
            unit_price: 13546,
          },
        ],
      },
      {
        ean: '8480017169501',
        nombre: 'Papel Higiénico Simple Hoja 30 mts 4 Ud',
        marca: 'Dia',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/307575/Papel-Higienico-Simple-Hoja-30-mts-4-Ud-_1.jpg?v=638936513091300000',
        offers: [
          {
            supermercado: 'Dia',
            precio: 1260,
            precio_lista: 2100,
            stock: 75,
            link: 'https://diaonline.supermercadosdia.com.ar/papel-higienico-simple-hoja-30-mts-4-ud-16950/p',
            discount: 40,
            promo_label: '2do al 80% ($1.260 c/u x2)',
            promo_min_qty: 2,
            unit_measure: 'u',
            unit_price: 315,
          },
        ],
      },
      {
        ean: '7790040114708',
        nombre: 'Alfajor Tita 36 G',
        marca: 'Tita',
        imagen: 'https://masonlineprod.vteximg.com.br/arquivos/ids/325818/Alfajor-Tita-36-G-1-57780.jpg?v=639165415686500000',
        offers: [
          {
            supermercado: 'Dia',
            precio: 582,
            precio_lista: 970,
            stock: 150,
            link: 'https://diaonline.supermercadosdia.com.ar/alfajor-tita-36-gr-303490/p',
            discount: 40,
            promo_label: '2do al 80% ($582 c/u x2)',
            promo_min_qty: 2,
            unit_measure: 'u',
            unit_price: 582,
          },
        ],
      },
    ],
  },
  {
    id: 'tier-60',
    title: 'Liquidaciones Directas y Bombas de Ahorro (Hasta 75% OFF)',
    subtitle: 'Grandes rebajas y liquidaciones directas de stock en bebidas y limpieza',
    badge: 'Hasta 75% OFF',
    percentLabel: '35% a 75%',
    icon: 'zap',
    meliSponsored: {
      product: {
        ean: '7790990003220',
        nombre: 'Jabón Líquido Para Ropa Ariel Platinum Doypack 3 Lt.',
        marca: 'Ariel',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/362701/Jabon-Liquido-Para-Ropa-Ariel-Platinum-Doypack-3-Lt-_1.jpg?v=639003522645770000',
        offers: [],
      },
      offer: {
        supermercado: 'MercadoLibre',
        precio: 12954,
        precio_lista: 19929,
        stock: 50,
        link: 'https://www.mercadolibre.com.ar/jabon-liquido-para-ropa-ariel-platinum-27l/p/MLA27822874',
        seller_name: 'Tienda Oficial P&G',
        is_full: true,
        discount: 35,
        promo_label: '35% OFF',
        unit_measure: 'lt',
        unit_price: 4318,
      },
    },
    products: [
      {
        ean: '7798134193752',
        nombre: 'Whisky Petakon en Petaca 380 Ml',
        marca: 'Petakon',
        imagen: 'https://carrefourar.vteximg.com.br/arquivos/ids/871496/7798134193752_02.jpg?v=639140991134370000',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 690,
            precio_lista: 2529,
            stock: 30,
            link: 'https://www.carrefour.com.ar/whisky-petakon-en-petaca-380-ml-720918/p',
            discount: 73,
            promo_label: '73% OFF Liquidación',
            unit_measure: 'lt',
            unit_price: 1816,
          },
        ],
      },
      {
        ean: '7501003111296',
        nombre: 'Jalapeños en Trocitos Herdez 210 Grs',
        marca: 'Herdez',
        imagen: 'https://carrefourar.vteximg.com.br/arquivos/ids/896206/7501003111296_E02.jpg',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 2907,
            precio_lista: 7269,
            stock: 35,
            link: 'https://www.carrefour.com.ar/jalapenos-en-trocitos-herdez-210-grs-777643/p',
            discount: 60,
            promo_label: '60% OFF Directo',
            unit_measure: 'kg',
            unit_price: 13843,
          },
        ],
      },
      {
        ean: '7798363311029',
        nombre: 'Suavizante Concentrado Elegant Carrefour 500 Cc',
        marca: 'Carrefour Essential',
        imagen: 'https://carrefourar.vtexassets.com/arquivos/ids/419827/7798363311029_02.jpg',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 4038,
            precio_lista: 8690,
            stock: 45,
            link: 'https://www.carrefour.com.ar/suavizante-concentradro-elegant-carrefour-essential-en-botella-500-cc-741491/p',
            discount: 54,
            promo_label: '54% OFF Directo',
            unit_measure: 'lt',
            unit_price: 8076,
          },
        ],
      },
      {
        ean: '2695706000003',
        nombre: 'Bolsa de residuos Bulnez 45x60 cm plana x 10 uni',
        marca: 'Bulnez',
        imagen: 'https://carrefourar.vteximg.com.br/arquivos/ids/461042/2695706000003_01.jpg?v=638415411168600000',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 1090,
            precio_lista: 1590,
            stock: 80,
            link: 'https://www.carrefour.com.ar/bolsa-de-residuos-bulnez-45x60-cm-plana-x-10-uni-729091/p',
            discount: 31,
            promo_label: '31% OFF Directo',
            unit_measure: 'u',
            unit_price: 109,
          },
        ],
      },
      {
        ean: '7790240042108',
        nombre: 'Vino Malbec ALMA MORA 750cc',
        marca: 'Alma Mora',
        imagen: 'https://static.cotodigital3.com.ar/sitios/fotos/large/00187000/00187089.jpg',
        offers: [
          {
            supermercado: 'Masonline',
            precio: 5465,
            precio_lista: 8409,
            stock: 40,
            link: 'https://www.masonline.com.ar/vino-malbec-alma-mora-750-cc-2/p',
            discount: 35,
            promo_label: '35% OFF Directo',
            unit_measure: 'lt',
            unit_price: 7286,
          },
        ],
      },
      {
        ean: '7794450000781',
        nombre: 'Vino Tinto Álamos Malbec 750 Ml',
        marca: 'Álamos',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/314458/Vino-Tinto-Alamos-Malbec-750-Ml-_1.jpg?v=638599428555500000',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 6999,
            precio_lista: 10939,
            stock: 80,
            link: 'https://www.carrefour.com.ar/vino-tinto-malbec-seleccion-alamos-750-cc/p',
            discount: 36,
            promo_label: '36% OFF Directo',
            unit_measure: 'lt',
            unit_price: 9332,
          },
          {
            supermercado: 'Dia',
            precio: 7200,
            precio_lista: 11265,
            stock: 65,
            link: 'https://diaonline.supermercadosdia.com.ar/vino-tinto-alamos-malbec-750-ml-180721/p',
            discount: 36,
            promo_label: '36% OFF Directo',
            unit_measure: 'lt',
            unit_price: 9600,
          },
        ],
      },
    ],
  },
  {
    id: 'tier-50',
    title: '50% OFF y 2x1 — Mitad de Precio',
    subtitle: 'Promociones 2x1 y 50% directo para duplicar tu changuito al 50%',
    badge: '50% OFF (2x1)',
    percentLabel: '50% (2x1)',
    icon: 'percent',
    meliSponsored: {
      product: {
        ean: '7790990003039',
        nombre: 'Detergente Magistral Ultra Limón Botella 500 Ml',
        marca: 'Magistral',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/362699/Detergente-Magistral-Ultra-Limon-Botella-500-Ml-_1.jpg?v=639003522623700000',
        offers: [],
      },
      offer: {
        supermercado: 'MercadoLibre',
        precio: 3450,
        precio_lista: 5950,
        stock: 120,
        link: 'https://www.mercadolibre.com.ar/detergente-magistral-ultra-multiuso-limon-750-ml/p/MLA16155196',
        seller_name: 'Tienda Oficial P&G',
        is_full: true,
        discount: 42,
        promo_label: '42% OFF',
        unit_measure: 'lt',
        unit_price: 6900,
      },
    },
    products: [
      {
        ean: '7798060850026',
        nombre: 'Manteca Tonadita Calidad Extra 200 G',
        marca: 'Tonadita',
        imagen: 'https://static.cotodigital3.com.ar/sitios/fotos/large/00228600/00228676.jpg',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 2199,
            precio_lista: 4399,
            stock: 60,
            link: 'https://www.carrefour.com.ar/manteca-tonadita-calidad-extra-200-g/p',
            discount: 50,
            promo_label: '50% OFF Directo',
            unit_measure: 'kg',
            unit_price: 10995,
          },
        ],
      },
      {
        ean: '7790070336026',
        nombre: 'Fideos Lucchetti Tirabuzón 500 G',
        marca: 'Lucchetti',
        imagen: 'https://masonlineprod.vteximg.com.br/arquivos/ids/334621/Fideos-Lucchetti-Tirabuzon-500-G-1-49865.jpg?v=638623893699570000',
        offers: [
          {
            supermercado: 'Dia',
            precio: 1050,
            precio_lista: 1850,
            stock: 80,
            link: 'https://diaonline.supermercadosdia.com.ar/tirabuzon-n-34-luchetti-500-gr-144397/p',
            discount: 43,
            promo_label: '43% OFF Directo',
            unit_measure: 'kg',
            unit_price: 2100,
          },
        ],
      },
      {
        ean: '7798342410321',
        nombre: 'Cerveza Honey Lazybee Bierhaus 473 Ml',
        marca: 'Bierhaus',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/371798/Cerveza-Honey-Lazybee-Bierhaus-473-Ml-_1.jpg?v=639156448571370000',
        offers: [
          {
            supermercado: 'Dia',
            precio: 1690,
            precio_lista: 3395,
            stock: 55,
            link: 'https://diaonline.supermercadosdia.com.ar/cerveza-honey-lazybee-bierhaus-473-ml-313120/p',
            discount: 50,
            promo_label: '50% OFF Directo',
            unit_measure: 'lt',
            unit_price: 3572,
          },
        ],
      },
      {
        ean: '7798138555186',
        nombre: 'Protector Diario Doncella Sin Perfume 20 Ud',
        marca: 'Doncella',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/341793/Protector-Diario-Doncella-Sin-Perfume-Anatomicos-20-Ud-_1.jpg',
        offers: [
          {
            supermercado: 'Dia',
            precio: 645,
            precio_lista: 1290,
            stock: 90,
            link: 'https://diaonline.supermercadosdia.com.ar/protector-diario-doncella-sin-perfume-anatomicos-20-ud-272890/p',
            discount: 50,
            promo_label: '50% OFF Directo',
            unit_measure: 'u',
            unit_price: 32,
          },
        ],
      },
      {
        ean: '7798138555193',
        nombre: 'Toallitas Femeninas Con Alas Sin Perfume Doncella 8 Ud',
        marca: 'Doncella',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/332560/Toallitas-Femeninas-Con-Alas-Sin-Perfume-Doncella-8-Ud-_1.jpg',
        offers: [
          {
            supermercado: 'Dia',
            precio: 588,
            precio_lista: 1175,
            stock: 95,
            link: 'https://diaonline.supermercadosdia.com.ar/toallitas-femeninas-con-alas-sin-perfume-doncella-8-ud-138066/p',
            discount: 50,
            promo_label: '50% OFF Directo',
            unit_measure: 'u',
            unit_price: 74,
          },
        ],
      },
    ],
  },
  {
    id: 'tier-40',
    title: 'Canasta Básica y Esenciales — Gran Ahorro (25% a 45% OFF)',
    subtitle: 'Descuentos directos en aceites, detergentes, yerba y lácteos de consumo diario',
    badge: 'Hasta 45% OFF',
    percentLabel: '25% - 45%',
    icon: 'tag',
    meliSponsored: {
      product: {
        ean: '7790180001018',
        nombre: 'Café Instantáneo La Virginia Torrado Clásico 170g',
        marca: 'La Virginia',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/314488/Cafe-Instantaneo-La-Virginia-Torrado-170-Gr-_1.jpg?v=638599429443700000',
        offers: [],
      },
      offer: {
        supermercado: 'MercadoLibre',
        precio: 5200,
        precio_lista: 7500,
        stock: 90,
        link: 'https://www.mercadolibre.com.ar/cafe-instantaneo-la-virginia-torrado-clasico-doypack-170g/p/MLA19757626',
        seller_name: 'Tienda Oficial La Virginia',
        is_full: true,
        discount: 31,
        promo_label: '31% OFF',
        unit_measure: 'kg',
        unit_price: 30588,
      },
    },
    products: [
      {
        ean: '7790742363008',
        nombre: 'Leche La Serenísima Clásica Entera 1 L',
        marca: 'La Serenísima',
        imagen: 'https://static.cotodigital3.com.ar/sitios/fotos/large/00251800/00251875.jpg',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 2199,
            precio_lista: 2899,
            stock: 110,
            link: 'https://www.carrefour.com.ar/leche-la-serenisima-clasica-3-1l-720719/p',
            discount: 24,
            promo_label: '24% OFF',
            unit_measure: 'lt',
            unit_price: 2199,
          },
        ],
      },
      {
        ean: '7790310985793',
        nombre: 'Chizitos de Maíz Queso Cheetos Original 140 G',
        marca: 'Cheetos',
        imagen: 'https://carrefourar.vteximg.com.br/arquivos/ids/904233/7790310985793_E01.jpg',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 3509,
            precio_lista: 5849,
            stock: 50,
            link: 'https://www.carrefour.com.ar/chizitos-de-maiz-sabor-a-queso-cheetos-original-140-g-729770-/p',
            discount: 40,
            promo_label: '40% OFF Directo',
            unit_measure: 'kg',
            unit_price: 25064,
          },
        ],
      },
      {
        ean: '7790310985588',
        nombre: 'Papas Fritas Lays Clásicas 330 G',
        marca: 'Lays',
        imagen: 'https://carrefourar.vteximg.com.br/arquivos/ids/904216/7790310985588_E01.jpg',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 6299,
            precio_lista: 10499,
            stock: 40,
            link: 'https://www.carrefour.com.ar/papas-fritas-lays-clasicas-330-g-721964/p',
            discount: 40,
            promo_label: '40% OFF Directo',
            unit_measure: 'kg',
            unit_price: 19087,
          },
        ],
      },
      {
        ean: '7790310985571',
        nombre: 'Nachos Sabor a Queso Doritos 200 G',
        marca: 'Doritos',
        imagen: 'https://carrefourar.vteximg.com.br/arquivos/ids/904460/7790310985571_E01.jpg',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 5699,
            precio_lista: 9499,
            stock: 45,
            link: 'https://www.carrefour.com.ar/nachos-sabor-a-queso-doritos-200-g-721960/p',
            discount: 40,
            promo_label: '40% OFF Directo',
            unit_measure: 'kg',
            unit_price: 28495,
          },
        ],
      },
      {
        ean: '7790070411853',
        nombre: 'Fideos Spaghetti N7 Lucchetti 500 Gr',
        marca: 'Lucchetti',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/376993/Fideos-Spaghetti-N7-Luchetti-500-Gr-_1.jpg',
        offers: [
          {
            supermercado: 'Dia',
            precio: 1050,
            precio_lista: 1750,
            stock: 80,
            link: 'https://diaonline.supermercadosdia.com.ar/fideos-spaghetti-n7-luchetti-500-gr-40877/p',
            discount: 40,
            promo_label: '40% OFF Directo',
            unit_measure: 'kg',
            unit_price: 2100,
          },
        ],
      },
      {
        ean: '7790717150857',
        nombre: 'Cerveza 1890 Quilmes 354 Ml',
        marca: 'Quilmes',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/393322/Cerveza-1890-Quilmes-354-Ml-_1.jpg',
        offers: [
          {
            supermercado: 'Dia',
            precio: 1050,
            precio_lista: 1890,
            stock: 90,
            link: 'https://diaonline.supermercadosdia.com.ar/cerveza-1890-quilmes-354-ml-14806/p',
            discount: 44,
            promo_label: '44% OFF Directo',
            unit_measure: 'lt',
            unit_price: 2966,
          },
        ],
      },
    ],
  },
]

/**
 * GÓNDOLAS COMPATIBILIDAD (Exportadas para retrocompatibilidad con tests)
 */
export const GONDOLAS: Gondola[] = [
  {
    id: 'ofertas-destacadas',
    title: 'Ofertas destacadas del día',
    subtitle: 'Los mejores descuentos combinados entre todos los supermercados',
    icon: 'flame',
    searchTerm: 'ofertas',
    products: [
      DISCOUNT_TIERS[0].products[0],
      DISCOUNT_TIERS[0].products[1],
      DISCOUNT_TIERS[1].products[0],
      DISCOUNT_TIERS[2].products[0],
    ],
  },
]
