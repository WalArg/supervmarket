import type { ProductGroup, Offer } from '../types'

export interface Gondola {
  id: string
  title: string
  subtitle: string
  icon: 'flame' | 'milk' | 'package' | 'sparkles' | 'coffee' | 'zap' | 'percent'
  searchTerm: string
  products: ProductGroup[]
}

export interface DiscountTier {
  id: string
  title: string
  subtitle: string
  badge: string
  percentLabel: string
  icon: 'flame' | 'zap' | 'percent' | 'tag'
  meliSponsored: {
    product: ProductGroup
    offer: Offer
  }
  products: ProductGroup[]
}

/**
 * NIVELES DE MEGADECUENTOS (70%-80%, 60%, 50%, 40%)
 * Cada nivel cuenta con su propia opción patrocinada de Mercado Libre con descuento acorde.
 */
export const DISCOUNT_TIERS: DiscountTier[] = [
  {
    id: 'tier-70-80',
    title: '70% y 80% OFF — Mega Liquidación & 2do al 80%',
    subtitle: 'Las mayores rebajas históricas: liquidaciones de bodega y 2das unidades al 80%',
    badge: 'Hasta 73% y 80% OFF',
    percentLabel: '70% - 80%',
    icon: 'flame',
    meliSponsored: {
      product: {
        ean: '7790123000789',
        nombre: 'Vino Tinto Malbec Reserva Bodega Norton 750 Ml (Caja x6)',
        marca: 'Norton',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/282210/Cerveza-Quilmes-Clasica-Rubia-473-Ml-_1.jpg?v=638647900000000000',
        offers: [],
      },
      offer: {
        supermercado: 'MercadoLibre',
        precio: 14990,
        precio_lista: 49990,
        stock: 80,
        link: 'https://mercadolibre.com.ar',
        seller_name: 'Tienda Oficial Bodega Norton',
        is_full: true,
        discount: 70,
        promo_label: '70% OFF Liquidación',
        unit_measure: 'lt',
        unit_price: 3331,
      },
    },
    products: [
      {
        ean: '7798134193752',
        nombre: 'Whisky Petakon en petaca 380 ml',
        marca: 'Petakon',
        imagen: 'https://carrefourar.vteximg.com.br/arquivos/ids/871496/7798134193752_02.jpg?v=639140991134370000',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 690,
            precio_lista: 2529,
            stock: 35,
            link: 'https://carrefour.com.ar',
            discount: 73,
            promo_label: '73% OFF',
            unit_measure: 'lt',
            unit_price: 1815,
          },
          {
            supermercado: 'Coto',
            precio: 790,
            precio_lista: 2529,
            stock: 20,
            link: 'https://coto.com.ar',
            discount: 69,
            unit_measure: 'lt',
            unit_price: 2078,
          },
          {
            supermercado: 'MercadoLibre',
            precio: 750,
            precio_lista: 2529,
            stock: 50,
            link: 'https://mercadolibre.com.ar',
            seller_name: '01Mercado',
            is_full: true,
            discount: 70,
            promo_label: '70% OFF',
            unit_measure: 'lt',
            unit_price: 1973,
          },
        ],
      },
      {
        ean: '7790047779281',
        nombre: 'Chocolate Milk Belgium 100g',
        marca: 'BELGIAM',
        imagen: 'https://static.cotodigital3.com.ar/sitios/fotos/large/00477900/00477928.jpg',
        offers: [
          {
            supermercado: 'Coto',
            precio: 3742,
            precio_lista: 12475,
            stock: 40,
            link: 'https://coto.com.ar',
            discount: 70,
            promo_label: '70% OFF Bomba',
            unit_measure: 'kg',
            unit_price: 37420,
          },
          {
            supermercado: 'Carrefour',
            precio: 4490,
            precio_lista: 12475,
            stock: 25,
            link: 'https://carrefour.com.ar',
            discount: 64,
            unit_measure: 'kg',
            unit_price: 44900,
          },
          {
            supermercado: 'MercadoLibre',
            precio: 3990,
            precio_lista: 12475,
            stock: 60,
            link: 'https://mercadolibre.com.ar',
            seller_name: 'Tienda Oficial Chocolates',
            is_full: true,
            discount: 68,
            unit_measure: 'kg',
            unit_price: 39900,
          },
        ],
      },
      {
        ean: '7622300861032',
        nombre: 'Galletitas Rellenas Oreo 118 G',
        marca: 'Oreo',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/282218/Galletitas-Rellenas-Oreo-118-G-_1.jpg?v=638647900000000000',
        offers: [
          {
            supermercado: 'Dia',
            precio: 310,
            precio_lista: 1550,
            stock: 80,
            link: 'https://diaonline.supermercadosdia.com.ar',
            discount: 80,
            promo_label: '2do al 80% (80% OFF)',
            unit_measure: 'kg',
            unit_price: 2627,
          },
          {
            supermercado: 'Coto',
            precio: 465,
            precio_lista: 1550,
            stock: 60,
            link: 'https://coto.com.ar',
            discount: 70,
            promo_label: '2do al 70%',
            unit_measure: 'kg',
            unit_price: 3940,
          },
          {
            supermercado: 'Carrefour',
            precio: 620,
            precio_lista: 1550,
            stock: 50,
            link: 'https://carrefour.com.ar',
            discount: 60,
            unit_measure: 'kg',
            unit_price: 5254,
          },
          {
            supermercado: 'MercadoLibre',
            precio: 387,
            precio_lista: 1550,
            stock: 120,
            link: 'https://mercadolibre.com.ar',
            seller_name: 'Tienda Oficial Mondelez',
            is_full: true,
            discount: 75,
            promo_label: '2do al 75%',
            unit_measure: 'kg',
            unit_price: 3279,
          },
        ],
      },
      {
        ean: '7790057268012',
        nombre: 'Individual Rectangular Foila Liso Beige',
        marca: 'HOME DESIGN',
        imagen: 'https://static.cotodigital3.com.ar/sitios/fotos/large/00572600/00572680.jpg',
        offers: [
          {
            supermercado: 'Coto',
            precio: 1199,
            precio_lista: 3495,
            stock: 30,
            link: 'https://coto.com.ar',
            discount: 66,
            promo_label: '66% OFF Bazar',
            unit_measure: 'un',
            unit_price: 1199,
          },
          {
            supermercado: 'Carrefour',
            precio: 1390,
            precio_lista: 3495,
            stock: 20,
            link: 'https://carrefour.com.ar',
            discount: 60,
            unit_measure: 'un',
            unit_price: 1390,
          },
        ],
      },
    ],
  },
  {
    id: 'tier-60',
    title: '60% OFF — Súper Rebajas Bombas',
    subtitle: 'Descuentos masivos en perfumería, limpieza y bebidas seleccionadas',
    badge: 'Hasta 60% OFF',
    percentLabel: '60%',
    icon: 'zap',
    meliSponsored: {
      product: {
        ean: '7791234000321',
        nombre: 'Jabón Líquido para Ropa Ariel Poder y Cuidado 3 Lt',
        marca: 'Ariel',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/263595/Jabon-Liquido-para-Ropa-Ariel-Clasico-3-Lt-_1.jpg?v=638363700000000000',
        offers: [],
      },
      offer: {
        supermercado: 'MercadoLibre',
        precio: 6390,
        precio_lista: 15990,
        stock: 90,
        link: 'https://mercadolibre.com.ar',
        seller_name: 'Tienda Oficial P&G',
        is_full: true,
        discount: 60,
        promo_label: '60% OFF en 2da un.',
        unit_measure: 'lt',
        unit_price: 2130,
      },
    },
    products: [
      {
        ean: '7798134190012',
        nombre: 'Vodka Lima Shooter 473 Ml',
        marca: 'SHOOTER',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/282210/Cerveza-Quilmes-Clasica-Rubia-473-Ml-_1.jpg?v=638647900000000000',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 999,
            precio_lista: 2499,
            stock: 45,
            link: 'https://carrefour.com.ar',
            discount: 60,
            promo_label: '60% OFF',
            unit_measure: 'lt',
            unit_price: 2112,
          },
          {
            supermercado: 'Coto',
            precio: 1100,
            precio_lista: 2499,
            stock: 30,
            link: 'https://coto.com.ar',
            discount: 56,
            unit_measure: 'lt',
            unit_price: 2325,
          },
        ],
      },
      {
        ean: '7790057956412',
        nombre: 'Repasador Toalla Gris Oscuro 40x60 Cm',
        marca: 'HOME DESIGN',
        imagen: 'https://static.cotodigital3.com.ar/sitios/fotos/large/00579500/00579564.jpg',
        offers: [
          {
            supermercado: 'Coto',
            precio: 2199,
            precio_lista: 5499,
            stock: 35,
            link: 'https://coto.com.ar',
            discount: 60,
            promo_label: '60% OFF',
            unit_measure: 'un',
            unit_price: 2199,
          },
        ],
      },
      {
        ean: '7790077002013',
        nombre: 'Toallas Húmedas Farmacity Bebé Cuidado Diario x 2 un (96 un)',
        marca: 'Farmacity Bebé',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/319918/Detergente-Magistral-Limon-500-Ml-_1.jpg?v=638840428904570000',
        offers: [
          {
            supermercado: 'Farmacity',
            precio: 4050,
            precio_lista: 9000,
            stock: 50,
            link: 'https://farmacity.com',
            discount: 55,
            promo_label: '55% OFF Combo',
            unit_measure: 'un',
            unit_price: 42,
          },
          {
            supermercado: 'Simplicity',
            precio: 4200,
            precio_lista: 9000,
            stock: 30,
            link: 'https://simplicity.com.ar',
            discount: 53,
            unit_measure: 'un',
            unit_price: 43,
          },
          {
            supermercado: 'MercadoLibre',
            precio: 3990,
            precio_lista: 9000,
            stock: 70,
            link: 'https://mercadolibre.com.ar',
            seller_name: 'Farmacity Oficial',
            is_full: true,
            discount: 56,
            unit_measure: 'un',
            unit_price: 41,
          },
        ],
      },
      {
        ean: '7798001112223',
        nombre: 'IbuMejoral Rápida Acción 400mg x10 cápsulas',
        marca: 'IbuMejoral',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/319918/Detergente-Magistral-Limon-500-Ml-_1.jpg?v=638840428904570000',
        offers: [
          {
            supermercado: 'Farmaplus',
            precio: 1865,
            precio_lista: 4144,
            stock: 60,
            link: 'https://farmaplus.com.ar',
            discount: 55,
            promo_label: '55% OFF',
            unit_measure: 'un',
            unit_price: 186,
          },
          {
            supermercado: 'Farmacity',
            precio: 2072,
            precio_lista: 4144,
            stock: 40,
            link: 'https://farmacity.com',
            discount: 50,
            unit_measure: 'un',
            unit_price: 207,
          },
        ],
      },
    ],
  },
  {
    id: 'tier-50',
    title: '50% OFF — 2x1 y Mitad de Precio',
    subtitle: 'Las promociones 2x1 más populares para duplicar tu changuito al 50%',
    badge: '50% OFF (2x1)',
    percentLabel: '50%',
    icon: 'percent',
    meliSponsored: {
      product: {
        ean: '7790060000555',
        nombre: 'Aceite de Oliva Extra Virgen Cocinero 500 Ml',
        marca: 'Cocinero',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/339766/Aceite-de-Girasol-Cocinero-15-Lt-_1.jpg?v=638840609090200000',
        offers: [],
      },
      offer: {
        supermercado: 'MercadoLibre',
        precio: 4990,
        precio_lista: 9980,
        stock: 100,
        link: 'https://mercadolibre.com.ar',
        seller_name: 'Tienda Oficial Molinos',
        is_full: true,
        discount: 50,
        promo_label: '2x1 Llevando 2 (50% OFF)',
        unit_measure: 'lt',
        unit_price: 9980,
      },
    },
    products: [
      {
        ean: '7790070336026',
        nombre: 'Fideos Lucchetti Tirabuzón 500 G',
        marca: 'Lucchetti',
        imagen: 'https://masonlineprod.vteximg.com.br/arquivos/ids/334621/Fideos-Lucchetti-Tirabuzon-500-G-1-49865.jpg?v=638623893699570000',
        offers: [
          {
            supermercado: 'Coto',
            precio: 795,
            precio_lista: 1590,
            stock: 70,
            link: 'https://coto.com.ar',
            discount: 50,
            promo_label: '2x1 Llevando 2',
            unit_measure: 'kg',
            unit_price: 1590,
          },
          {
            supermercado: 'Carrefour',
            precio: 850,
            precio_lista: 1590,
            stock: 50,
            link: 'https://carrefour.com.ar',
            discount: 47,
            unit_measure: 'kg',
            unit_price: 1700,
          },
          {
            supermercado: 'MercadoLibre',
            precio: 790,
            precio_lista: 1590,
            stock: 100,
            link: 'https://mercadolibre.com.ar',
            seller_name: 'Tienda Oficial Molinos',
            is_full: true,
            discount: 50,
            promo_label: '2x1 Llevando 2',
            unit_measure: 'kg',
            unit_price: 1580,
          },
        ],
      },
      {
        ean: '7790080004399',
        nombre: 'Manteca TONADITA 200g',
        marca: 'TONADITA',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/282218/Galletitas-Rellenas-Oreo-118-G-_1.jpg?v=638647900000000000',
        offers: [
          {
            supermercado: 'Carrefour',
            precio: 2199,
            precio_lista: 4399,
            stock: 40,
            link: 'https://carrefour.com.ar',
            discount: 50,
            promo_label: '50% OFF',
            unit_measure: 'kg',
            unit_price: 10995,
          },
          {
            supermercado: 'Coto',
            precio: 2399,
            precio_lista: 4399,
            stock: 30,
            link: 'https://coto.com.ar',
            discount: 45,
            unit_measure: 'kg',
            unit_price: 11995,
          },
        ],
      },
      {
        ean: '7613035675012',
        nombre: 'Leche Condensada Descremada Nestle x 395 Gr.',
        marca: 'NESTLE',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/339766/Aceite-de-Girasol-Cocinero-15-Lt-_1.jpg?v=638840609090200000',
        offers: [
          {
            supermercado: 'Dia',
            precio: 2830,
            precio_lista: 5675,
            stock: 35,
            link: 'https://diaonline.supermercadosdia.com.ar',
            discount: 50,
            promo_label: '50% OFF',
            unit_measure: 'kg',
            unit_price: 7164,
          },
          {
            supermercado: 'Carrefour',
            precio: 3100,
            precio_lista: 5675,
            stock: 25,
            link: 'https://carrefour.com.ar',
            discount: 45,
            unit_measure: 'kg',
            unit_price: 7848,
          },
        ],
      },
      {
        ean: '7790895000430',
        nombre: 'Cerveza Quilmes Clásica Rubia Lata 473 Ml',
        marca: 'Quilmes',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/282210/Cerveza-Quilmes-Clasica-Rubia-473-Ml-_1.jpg?v=638647900000000000',
        offers: [
          {
            supermercado: 'Coto',
            precio: 925,
            precio_lista: 1850,
            stock: 80,
            link: 'https://coto.com.ar',
            discount: 50,
            promo_label: '2x1 en Cervezas',
            unit_measure: 'lt',
            unit_price: 1955,
          },
          {
            supermercado: 'Carrefour',
            precio: 990,
            precio_lista: 1850,
            stock: 60,
            link: 'https://carrefour.com.ar',
            discount: 46,
            unit_measure: 'lt',
            unit_price: 2093,
          },
          {
            supermercado: 'MercadoLibre',
            precio: 950,
            precio_lista: 1850,
            stock: 120,
            link: 'https://mercadolibre.com.ar',
            seller_name: 'Cervecería Quilmes Oficial',
            is_full: true,
            discount: 49,
            promo_label: '2x1 en Cervezas',
            unit_measure: 'lt',
            unit_price: 2008,
          },
        ],
      },
    ],
  },
  {
    id: 'tier-40',
    title: '40% OFF — Gran Ahorro de Canasta',
    subtitle: 'Descuentos de hasta 40% en aceites, yerbas, lácteos y productos esenciales',
    badge: '40% OFF',
    percentLabel: '40%',
    icon: 'tag',
    meliSponsored: {
      product: {
        ean: '7792798000021',
        nombre: 'Detergente Magistral Limón Concentrado 500 Ml',
        marca: 'Magistral',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/319918/Detergente-Magistral-Limon-500-Ml-_1.jpg?v=638840428904570000',
        offers: [],
      },
      offer: {
        supermercado: 'MercadoLibre',
        precio: 1590,
        precio_lista: 2650,
        stock: 100,
        link: 'https://mercadolibre.com.ar',
        seller_name: 'Tienda Oficial P&G',
        is_full: true,
        discount: 40,
        promo_label: '40% OFF',
        unit_measure: 'lt',
        unit_price: 3180,
      },
    },
    products: [
      {
        ean: '7790060023684',
        nombre: 'Aceite de Girasol Cocinero 1,5 Lt.',
        marca: 'Cocinero',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/339766/Aceite-de-Girasol-Cocinero-15-Lt-_1.jpg?v=638840609090200000',
        offers: [
          {
            supermercado: 'Dia',
            precio: 1860,
            precio_lista: 3100,
            stock: 45,
            link: 'https://diaonline.supermercadosdia.com.ar',
            discount: 40,
            promo_label: 'Precio Bomba 40%',
            unit_measure: 'lt',
            unit_price: 1240,
          },
          {
            supermercado: 'Carrefour',
            precio: 2170,
            precio_lista: 3100,
            stock: 40,
            link: 'https://carrefour.com.ar',
            discount: 30,
            unit_measure: 'lt',
            unit_price: 1446,
          },
          {
            supermercado: 'MercadoLibre',
            precio: 1890,
            precio_lista: 3100,
            stock: 70,
            link: 'https://mercadolibre.com.ar',
            seller_name: '01Mercado',
            is_full: true,
            discount: 39,
            unit_measure: 'lt',
            unit_price: 1260,
          },
        ],
      },
      {
        ean: '7793940400030',
        nombre: 'Leche La Serenísima Clásica Entera 1 L',
        marca: 'La Serenísima',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/282200/Leche-La-Serenisima-1-L-_1.jpg?v=638647900000000000',
        offers: [
          {
            supermercado: 'Dia',
            precio: 990,
            precio_lista: 1650,
            stock: 50,
            link: 'https://diaonline.supermercadosdia.com.ar',
            discount: 40,
            promo_label: '2do al 80%',
            unit_measure: 'lt',
            unit_price: 990,
          },
          {
            supermercado: 'Carrefour',
            precio: 1090,
            precio_lista: 1650,
            stock: 40,
            link: 'https://carrefour.com.ar',
            discount: 34,
            unit_measure: 'lt',
            unit_price: 1090,
          },
          {
            supermercado: 'MercadoLibre',
            precio: 1050,
            precio_lista: 1650,
            stock: 120,
            link: 'https://mercadolibre.com.ar',
            seller_name: 'Tienda Mastellone',
            is_full: true,
            discount: 36,
            unit_measure: 'lt',
            unit_price: 1050,
          },
        ],
      },
      {
        ean: '7790387013214',
        nombre: 'Yerba Mate Playadito 1 Kg',
        marca: 'Playadito',
        imagen: 'https://ardiaprod.vteximg.com.br/arquivos/ids/282205/Yerba-Mate-Playadito-1-Kg-_1.jpg?v=638647900000000000',
        offers: [
          {
            supermercado: 'Dia',
            precio: 2970,
            precio_lista: 4950,
            stock: 60,
            link: 'https://diaonline.supermercadosdia.com.ar',
            discount: 40,
            promo_label: '40% OFF',
            unit_measure: 'kg',
            unit_price: 2970,
          },
          {
            supermercado: 'Carrefour',
            precio: 3465,
            precio_lista: 4950,
            stock: 40,
            link: 'https://carrefour.com.ar',
            discount: 30,
            unit_measure: 'kg',
            unit_price: 3465,
          },
          {
            supermercado: 'MercadoLibre',
            precio: 3290,
            precio_lista: 4950,
            stock: 90,
            link: 'https://mercadolibre.com.ar',
            seller_name: 'Liebig Oficial',
            is_full: true,
            discount: 34,
            unit_measure: 'kg',
            unit_price: 3290,
          },
        ],
      },
    ],
  },
]

/**
 * Góndolas temáticas por categoría con los mayores descuentos reales de supermercados.
 */
export const GONDOLAS: Gondola[] = [
  {
    id: 'ofertas',
    title: 'Ofertas destacadas del día',
    subtitle: 'Los mayores descuentos verificados entre supermercados (hasta 80% OFF)',
    icon: 'flame',
    searchTerm: 'ofertas',
    products: [
      DISCOUNT_TIERS[0].products[0], // Whisky Petakon 73% OFF
      DISCOUNT_TIERS[0].products[1], // Chocolate Belgium 70% OFF
      DISCOUNT_TIERS[0].products[2], // Oreo 80% OFF
      DISCOUNT_TIERS[1].products[0], // Vodka Shooter 60% OFF
      DISCOUNT_TIERS[2].products[0], // Lucchetti 50% OFF (2x1)
      DISCOUNT_TIERS[2].products[3], // Quilmes 50% OFF (2x1)
    ],
  },
  {
    id: 'lacteos',
    title: 'Lácteos y Frescos',
    subtitle: 'Leches, mantecas y yogures con hasta 50% y 2do al 80%',
    icon: 'milk',
    searchTerm: 'lacteos',
    products: [
      DISCOUNT_TIERS[2].products[1], // Manteca Tonadita 50% OFF
      DISCOUNT_TIERS[2].products[2], // Leche Condensada Nestle 50% OFF
      DISCOUNT_TIERS[3].products[1], // Leche La Serenísima 40% OFF
    ],
  },
  {
    id: 'almacen',
    title: 'Almacén y Canasta Básica',
    subtitle: 'Fideos, aceites, yerba y básicos de despensa con hasta 70% OFF',
    icon: 'package',
    searchTerm: 'almacen',
    products: [
      DISCOUNT_TIERS[0].products[1], // Chocolate Belgium 70% OFF
      DISCOUNT_TIERS[2].products[0], // Lucchetti 50% OFF
      DISCOUNT_TIERS[3].products[0], // Aceite Cocinero 40% OFF
      DISCOUNT_TIERS[3].products[2], // Yerba Playadito 40% OFF
    ],
  },
  {
    id: 'limpieza',
    title: 'Limpieza y Hogar',
    subtitle: 'Jabones, detergentes y desinfectantes con hasta 60% OFF',
    icon: 'sparkles',
    searchTerm: 'limpieza',
    products: [
      DISCOUNT_TIERS[1].products[2], // Toallas Farmacity 55% OFF
      DISCOUNT_TIERS[1].products[3], // IbuMejoral 55% OFF
      DISCOUNT_TIERS[3].products[0], // Magistral 40% OFF
    ],
  },
  {
    id: 'bebidas',
    title: 'Bebidas y Desayuno',
    subtitle: 'Cervezas, licores y aperitivos con hasta 73% OFF',
    icon: 'coffee',
    searchTerm: 'bebidas',
    products: [
      DISCOUNT_TIERS[0].products[0], // Whisky Petakon 73% OFF
      DISCOUNT_TIERS[1].products[0], // Vodka Shooter 60% OFF
      DISCOUNT_TIERS[2].products[3], // Quilmes 50% OFF (2x1)
    ],
  },
]
