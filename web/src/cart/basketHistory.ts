import type {
  BasketSnapshot,
  BasketDeltaComparison,
  BasketHistoryStats,
  OptimizePlan,
} from '../types'

export const BASKET_HISTORY_STORAGE_KEY = 'sv_basket_history_v1'
export const MAX_SNAPSHOTS_LIMIT = 52
export const COOLDOWN_HOURS_SAME_DAY = 18

/**
 * Carga de forma segura el historial desde localStorage con saneamiento estricto
 */
export function loadBasketHistory(): BasketSnapshot[] {
  try {
    const raw = localStorage.getItem(BASKET_HISTORY_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []

    // Sanitizar y validar tipos mínimos obligatorios
    const valid = parsed.filter((item): item is BasketSnapshot => {
      return (
        item &&
        typeof item.id === 'string' &&
        typeof item.timestamp === 'string' &&
        !isNaN(new Date(item.timestamp).getTime()) &&
        typeof item.total_comodidad === 'number' &&
        isFinite(item.total_comodidad) &&
        typeof item.total_ahorro === 'number' &&
        isFinite(item.total_ahorro) &&
        typeof item.ahorro_ars === 'number' &&
        isFinite(item.ahorro_ars) &&
        typeof item.items_count === 'number'
      )
    })

    // Ordenar cronológicamente ascendente (el más viejo primero, el más nuevo al final)
    valid.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())

    // Garantizar que no exceda 52 elementos
    return valid.length > MAX_SNAPSHOTS_LIMIT ? valid.slice(-MAX_SNAPSHOTS_LIMIT) : valid
  } catch {
    return []
  }
}

/**
 * Persiste el búfer circular en localStorage con política FIFO y recuperación de cuota
 */
export function saveBasketHistory(history: BasketSnapshot[]): boolean {
  try {
    // Aplicar FIFO estricto (últimos 52)
    const trimmed = history.slice(-MAX_SNAPSHOTS_LIMIT)
    localStorage.setItem(BASKET_HISTORY_STORAGE_KEY, JSON.stringify(trimmed))
    return true
  } catch {
    // Si la cuota está llena, degradar a los últimos 26 registros (6 meses)
    try {
      const halved = history.slice(-Math.floor(MAX_SNAPSHOTS_LIMIT / 2))
      localStorage.setItem(BASKET_HISTORY_STORAGE_KEY, JSON.stringify(halved))
      return true
    } catch {
      return false
    }
  }
}

/**
 * Limpia el historial almacenado
 */
export function clearBasketHistory(): void {
  try {
    localStorage.removeItem(BASKET_HISTORY_STORAGE_KEY)
  } catch {
    // ignore
  }
}

/**
 * Extrae un BasketSnapshot tipado a partir de un OptimizePlan activo
 */
export function createSnapshotFromPlan(
  plan: OptimizePlan,
  itemsCount: number,
  totalUnits: number,
  source: 'checkout' | 'optimization_view' | 'manual' = 'optimization_view',
): BasketSnapshot | null {
  if (!plan || plan.total <= 0 || itemsCount <= 0) return null

  const previews = plan.mode_previews
  const comodaTotal =
    previews?.comodidad?.total ??
    plan.all_plans?.comodidad?.total ??
    (plan.mode === 'comodidad' ? plan.total : plan.total + (plan.ahorro_total || 0))
  const ahorroTotal =
    previews?.ahorro?.total ?? plan.all_plans?.ahorro?.total ?? (plan.mode === 'ahorro' ? plan.total : plan.total)
  const balanceadaTotal =
    previews?.balanceada?.total ?? plan.all_plans?.balanceada?.total

  // Ahorro neto en pesos respecto a comodidad
  const ahorroArs = Math.max(0, comodaTotal - ahorroTotal)
  const savingsPct = comodaTotal > 0 ? Number(((ahorroArs / comodaTotal) * 100).toFixed(1)) : 0

  // Desglose de gasto por comercio
  const storeSplit: Record<string, number> = {}
  if (plan.carts && Array.isArray(plan.carts)) {
    plan.carts.forEach(c => {
      storeSplit[c.supermercado] = c.final_store_total ?? c.subtotal ?? 0
    })
  }

  const now = new Date()
  return {
    id: `snap_${now.getTime()}`,
    timestamp: now.toISOString(),
    cp: plan.cp || null,
    items_count: itemsCount,
    total_units: totalUnits,
    total_comodidad: Math.round(comodaTotal),
    total_ahorro: Math.round(ahorroTotal),
    total_balanceada: balanceadaTotal ? Math.round(balanceadaTotal) : undefined,
    ahorro_ars: Math.round(ahorroArs),
    savings_pct: savingsPct,
    store_split: storeSplit,
    source,
  }
}

/**
 * Agrega o actualiza un snapshot en el búfer circular respetando la ventana de cooldown
 */
export function pushSnapshotToHistory(
  existingHistory: BasketSnapshot[],
  newSnapshot: BasketSnapshot,
  force: boolean = false,
): { updatedHistory: BasketSnapshot[]; actionTaken: 'appended' | 'updated' | 'skipped' } {
  if (!existingHistory.length) {
    const updated = [newSnapshot]
    saveBasketHistory(updated)
    return { updatedHistory: updated, actionTaken: 'appended' }
  }

  const latest = existingHistory[existingHistory.length - 1]
  const latestDate = new Date(latest.timestamp)
  const currentDate = new Date(newSnapshot.timestamp)
  const diffHours = (currentDate.getTime() - latestDate.getTime()) / (1000 * 60 * 60)

  // Mismo día civil o dentro de la ventana de cooldown de 18h
  const isSameDay =
    latestDate.toDateString() === currentDate.toDateString() || diffHours < COOLDOWN_HOURS_SAME_DAY

  if (isSameDay && !force) {
    if (newSnapshot.source === 'checkout') {
      // Un checkout explícito tiene precedencia: actualiza la cotización del día con la compra confirmada
      const updated = [...existingHistory.slice(0, -1), newSnapshot]
      saveBasketHistory(updated)
      return { updatedHistory: updated, actionTaken: 'updated' }
    } else {
      // Si fue solo una visualización en el mismo día, omitir para no saturar el historial
      return { updatedHistory: existingHistory, actionTaken: 'skipped' }
    }
  }

  // Ha pasado más de un día o se forza: agregar nuevo registro y podar al límite de 52
  const updated = [...existingHistory, newSnapshot].slice(-MAX_SNAPSHOTS_LIMIT)
  saveBasketHistory(updated)
  return { updatedHistory: updated, actionTaken: 'appended' }
}

/**
 * Calcula las métricas de variación de inflación personal y delta de ahorro
 */
export function calculateBasketDelta(
  currentSnapshot: BasketSnapshot,
  history: BasketSnapshot[],
): BasketDeltaComparison {
  if (!history.length) {
    return {
      has_history: false,
      current_total: currentSnapshot.total_ahorro,
      delta_ars: 0,
      percentage_delta: 0,
      current_savings: currentSnapshot.ahorro_ars,
      savings_delta_ars: 0,
      items_count_diff: 0,
      is_basket_size_different: false,
    }
  }

  // Tomar el snapshot previo más reciente (distinto al actual si el actual ya estuviese al final)
  let prev = history[history.length - 1]
  if (prev.id === currentSnapshot.id && history.length > 1) {
    prev = history[history.length - 2]
  }

  const daysElapsed = Math.max(
    0,
    Math.round(
      (new Date(currentSnapshot.timestamp).getTime() - new Date(prev.timestamp).getTime()) /
        (1000 * 60 * 60 * 24),
    ),
  )

  const currentTotal = currentSnapshot.total_ahorro
  const previousTotal = prev.total_ahorro
  const deltaArs = currentTotal - previousTotal

  // Inflación personal (%)
  const percentageDelta =
    previousTotal > 0
      ? Number((((currentTotal - previousTotal) / previousTotal) * 100).toFixed(1))
      : 0

  // Variación del ahorro
  const currentSavings = currentSnapshot.ahorro_ars
  const previousSavings = prev.ahorro_ars
  const savingsDeltaArs = currentSavings - previousSavings

  // Control de deriva de tamaño de canasta
  const itemsCountDiff = currentSnapshot.items_count - prev.items_count
  const isBasketSizeDifferent = itemsCountDiff !== 0

  let normalizedUnitDeltaPct: number | undefined
  if (isBasketSizeDifferent && currentSnapshot.total_units > 0 && prev.total_units > 0) {
    const curUnitCost = currentTotal / currentSnapshot.total_units
    const prevUnitCost = previousTotal / prev.total_units
    normalizedUnitDeltaPct = Number(
      (((curUnitCost - prevUnitCost) / prevUnitCost) * 100).toFixed(1),
    )
  }

  return {
    has_history: true,
    previous_date: prev.timestamp,
    days_elapsed: daysElapsed,
    current_total: currentTotal,
    previous_total: previousTotal,
    delta_ars: deltaArs,
    percentage_delta: percentageDelta,
    current_savings: currentSavings,
    previous_savings: previousSavings,
    savings_delta_ars: savingsDeltaArs,
    items_count_diff: itemsCountDiff,
    is_basket_size_different: isBasketSizeDifferent,
    normalized_unit_delta_pct: normalizedUnitDeltaPct,
  }
}

/**
 * Calcula estadísticas acumuladas para todo el historial
 */
export function calculateHistoryStats(history: BasketSnapshot[]): BasketHistoryStats {
  if (!history.length) {
    return {
      total_snapshots: 0,
      cumulative_savings_ars: 0,
      average_savings_ars: 0,
    }
  }

  const cumulativeSavings = history.reduce((acc, s) => acc + s.ahorro_ars, 0)
  const avgSavings = Math.round(cumulativeSavings / history.length)
  const totals = history.map(s => s.total_ahorro)
  const minTotal = Math.min(...totals)
  const maxTotal = Math.max(...totals)

  let overallInflationPct: number | undefined
  if (history.length >= 2) {
    const firstTotal = history[0].total_ahorro
    const lastTotal = history[history.length - 1].total_ahorro
    if (firstTotal > 0) {
      overallInflationPct = Number((((lastTotal - firstTotal) / firstTotal) * 100).toFixed(1))
    }
  }

  return {
    total_snapshots: history.length,
    cumulative_savings_ars: cumulativeSavings,
    average_savings_ars: avgSavings,
    first_snapshot_date: history[0].timestamp,
    latest_snapshot_date: history[history.length - 1].timestamp,
    min_basket_total: minTotal,
    max_basket_total: maxTotal,
    overall_period_inflation_pct: overallInflationPct,
  }
}
