/**
 * Configuración centralizada de Partners y Marcas Patrocinadas en SuperVMarket.
 * Permite setear dinámicamente qué cadenas o marcas comerciales se muestran
 * en el recuadro exclusivo de [PATROCINADO].
 *
 * Configuración actual:
 * - Tienda patrocinada exclusiva: 'MercadoLibre'
 */
export const SPONSORED_CONFIG = {
  // Lista de supermercados o plataformas patrocinadas activas
  enabledStores: ['MercadoLibre'] as string[],

  // Lista de marcas patrocinadas activas (vacío por ahora, configurable en el futuro)
  enabledBrands: [] as string[],

  /** Verifica si una tienda dada está configurada como patrocinada */
  isStoreSponsored: (storeName?: string | null): boolean => {
    if (!storeName) return false
    return SPONSORED_CONFIG.enabledStores.some(
      s => s.toLowerCase() === storeName.toLowerCase(),
    )
  },

  /** Verifica si una marca dada está configurada como patrocinada */
  isBrandSponsored: (brandName?: string | null): boolean => {
    if (!brandName) return false
    return SPONSORED_CONFIG.enabledBrands.some(
      b => b.toLowerCase() === brandName.toLowerCase(),
    )
  },
}
