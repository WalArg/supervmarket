import type { ListItem } from '../types'

/**
 * Canasta básica mensual de ejemplo con productos reales argentinos
 * disponibles en múltiples cadenas (Carrefour, Coto, Día, Jumbo, MasOnline).
 * Permite al usuario probar instantáneamente el Smart Cart y guardar su Lista Habitual en 1 toque.
 */
export const SAMPLE_HABITUAL_BASKET: ListItem[] = [
  {
    ean: '7790742333605',
    nombre: 'Leche La Serenisima Zero Lactosa 0% x 1000 ml',
    imagen:
      'https://thefoodmarketar.vteximg.com.br/arquivos/ids/163963/243126_leche-la-serenisima-parcialmente-descremada-zero-lactosa-x-1-l_imagen-1.jpg?v=638696098331230000',
    qty: 3,
  },
  {
    ean: '7793704000928',
    nombre: 'Yerba Mate Playadito Suave 1 Kg.',
    imagen:
      'https://ardiaprod.vteximg.com.br/arquivos/ids/320684/Yerba-Mate-Playadito-Suave-1-Kg-_1.jpg?v=638949374251000000',
    qty: 2,
  },
  {
    ean: '7790070336026',
    nombre: 'Fideos Lucchetti Tirabuzón 500 G',
    imagen:
      'https://masonlineprod.vteximg.com.br/arquivos/ids/334621/Fideos-Lucchetti-Tirabuzon-500-G-1-49865.jpg?v=638623893699570000',
    qty: 4,
  },
  {
    ean: '7790060023684',
    nombre: 'Aceite de Girasol Cocinero 1,5 Lt.',
    imagen:
      'https://ardiaprod.vteximg.com.br/arquivos/ids/339766/Aceite-de-Girasol-Cocinero-15-Lt-_1.jpg?v=638840609090200000',
    qty: 2,
  },
  {
    ean: '7791120031557',
    nombre: 'Arroz Molinos Ala Largo Fino x 1 kg',
    imagen:
      'https://thefoodmarketar.vteximg.com.br/arquivos/ids/163711/242205_arroz-molinos-ala-largo-fino-x-1-kg_imagen-1.jpg?v=638647951330230000',
    qty: 2,
  },
  {
    ean: '7891150046481',
    nombre: 'Jabon De Tocador DOVE Original Multipack 3x90 G',
    imagen:
      'https://static.cotodigital3.com.ar/sitios/fotos/large/00462600/00462665.jpg',
    qty: 2,
  },
]
