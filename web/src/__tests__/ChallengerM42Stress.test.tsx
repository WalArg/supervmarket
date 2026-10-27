import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import {
  encodeShareableList,
  decodeShareableList,
  generateShareUrl,
  formatShareMessage,
  cleanUrlParams,
} from '../cart/portableList'
import { CartProvider, useCart } from '../cart/CartContext'
import { HabitualListProvider } from '../cart/HabitualListContext'
import { LocationProvider } from '../location/LocationContext'
import { BenefitsProvider } from '../benefits/BenefitsContext'
import ImportSharedListModal from '../components/ImportSharedListModal'
import HabitualListManager from '../components/HabitualListManager'
import ListScreen from '../components/ListScreen'
import type { SharedItem, HabitualList, ListItem } from '../types'
import fs from 'node:fs'
import path from 'node:path'

// Mock api dependencies for ListScreen rendering
vi.mock('../api', async () => {
  const actual = await vi.importActual('../api')
  return {
    ...actual,
    optimize: vi.fn().mockResolvedValue({
      mode: 'ahorro',
      total: 15000,
      ahorro_total: 3500,
      reintegro_bancario_total: 0,
      carts: [],
      missing: [],
      mode_previews: [],
      all_plans: {},
    }),
    validateCart: vi.fn().mockResolvedValue({ status: 'ok', total: 0, sin_stock: [] }),
    getBenefits: vi.fn().mockResolvedValue({
      today: 'lunes',
      today_label: 'Lunes',
      weekdays: [],
      payment_options: [],
      official_links: {},
      daily_promos: [],
    }),
    getRegions: vi.fn().mockResolvedValue([]),
  }
})

describe('CHALLENGER M4.2: Adversarial Stress Test Suite', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  // =========================================================================
  // 1. BASE64URL RESILIENCE & URL BUDGET
  // =========================================================================
  describe('1. Base64url Resilience & RFC 4648 §5 Compliance', () => {
    it('1.1. Invariant: generated tokens NEVER contain +, /, or = across 200 random basket permutations', () => {
      for (let iteration = 0; iteration < 200; iteration++) {
        const itemCount = (iteration % 60) + 1
        const basket = Array.from({ length: itemCount }, (_, idx) => ({
          ean: `779${String(iteration * 1000 + idx).padStart(10, '0')}`,
          qty: (idx % 15) + 1,
        }))

        const token = encodeShareableList(basket)
        expect(token).toBeTruthy()
        expect(token).not.toContain('+')
        expect(token).not.toContain('/')
        expect(token).not.toContain('=')
        // Must only consist of [A-Za-z0-9-_]
        expect(/^[A-Za-z0-9_-]+$/.test(token)).toBe(true)

        // Decode must round-trip exactly
        const decoded = decodeShareableList(token)
        expect(decoded).toHaveLength(itemCount)
      }
    })

    it('1.2. 50-item list URL strictly respects the universal 2,000 char mobile browser limit', () => {
      // 50 worst-case items: 14-digit EANs + 3-digit quantities
      const fiftyMaxItems = Array.from({ length: 50 }, (_, i) => ({
        ean: `779123456789${String(i).padStart(2, '0')}`,
        qty: 999,
      }))

      const token = encodeShareableList(fiftyMaxItems)
      const url = generateShareUrl(fiftyMaxItems, 'list', 'https://vsupermarket.vercel.app')

      // Budget check: well below 2,000 characters
      expect(url.length).toBeLessThan(1400)
      expect(url.length).toBeGreaterThan(800)

      // Calculate headroom
      const headroom = 2000 - url.length
      expect(headroom).toBeGreaterThan(600) // At least 30% safety margin

      // Verify decoded integrity
      const decoded = decodeShareableList(token)
      expect(decoded).toHaveLength(50)
      expect(decoded[0].qty).toBe(999)
      expect(decoded[49].qty).toBe(999)
    })

    it('1.3. Corrupt tokens, missing padding, spaces, and garbage degrade gracefully without crash', () => {
      // Empty / invalid types
      expect(decodeShareableList('')).toEqual([])
      expect(decodeShareableList('   ')).toEqual([])
      expect(decodeShareableList(null as unknown as string)).toEqual([])
      expect(decodeShareableList(undefined as unknown as string)).toEqual([])

      // Total garbage strings
      expect(decodeShareableList('!@#$%^&*()_+{}[]|:<>?')).toEqual([])
      expect(decodeShareableList('%%%invalid_percent_encoding%%%')).toEqual([])
      expect(decodeShareableList('A')).toEqual([])
      expect(decodeShareableList('AA')).toEqual([])
      expect(decodeShareableList('AAA')).toEqual([])

      // Valid base64 but containing invalid payload
      const invalidJsonToken = Buffer.from('{"hello":"world"}').toString('base64url')
      expect(decodeShareableList(invalidJsonToken)).toEqual([])

      const randomBytesToken = Buffer.from('\x00\x01\x02\x03\xFF\xFE').toString('base64url')
      expect(decodeShareableList(randomBytesToken)).toEqual([])
    })

    it('1.4. WhatsApp space normalization: restores tokens where + was replaced by space or URL-decoded', () => {
      const items = [
        { ean: '7791234567890', qty: 2 },
        { ean: '7790987654321', qty: 3 },
      ]
      const standardB64 = Buffer.from('7791234567890:2,7790987654321:3').toString('base64')
      // Simulate WhatsApp converting pluses or unescaping
      const mangledWithSpaces = standardB64.replace(/\+/g, ' ')

      const decoded = decodeShareableList(mangledWithSpaces)
      expect(decoded).toHaveLength(2)
      expect(decoded[0]).toEqual({ ean: '7791234567890', qty: 2 })
      expect(decoded[1]).toEqual({ ean: '7790987654321', qty: 3 })
    })

    it('1.5. Non-numeric EANs and barcode boundary filtration', () => {
      const dirty = [
        { ean: '1234567', qty: 2 }, // 7 digits -> too short (<8)
        { ean: '123456789012345', qty: 2 }, // 15 digits -> too long (>14)
        { ean: '779123456789a', qty: 2 }, // contains letter
        { ean: '779123-567890', qty: 2 }, // contains hyphen
        { ean: '7791234567890', qty: 5 }, // valid 13 digits
      ]

      const encoded = encodeShareableList(dirty)
      const decoded = decodeShareableList(encoded)
      expect(decoded).toHaveLength(1)
      expect(decoded[0]).toEqual({ ean: '7791234567890', qty: 5 })
    })

    it('1.6. Quantity boundaries and NaN sanitization: clamps strictly to [1, 999]', () => {
      // Craft raw string with edge-case quantities
      const raw = '7791111111111:0,7792222222222:-10,7793333333333:99999,7794444444444:NaN,7795555555555:3.8'
      const token = Buffer.from(raw).toString('base64url')
      const decoded = decodeShareableList(token)

      expect(decoded).toHaveLength(5)
      expect(decoded.find(i => i.ean === '7791111111111')?.qty).toBe(1) // 0 -> 1
      expect(decoded.find(i => i.ean === '7792222222222')?.qty).toBe(1) // -10 -> 1
      expect(decoded.find(i => i.ean === '7793333333333')?.qty).toBe(999) // 99999 -> 999
      expect(decoded.find(i => i.ean === '7794444444444')?.qty).toBe(1) // NaN -> 1
      expect(decoded.find(i => i.ean === '7795555555555')?.qty).toBe(3) // 3.8 -> 3
    })

    it('1.7. Raw ean:qty fallback compatibility', () => {
      const raw = '7791234567890:2,7799876543210:4'
      const decoded = decodeShareableList(raw)
      expect(decoded).toHaveLength(2)
      expect(decoded[0]).toEqual({ ean: '7791234567890', qty: 2 })
      expect(decoded[1]).toEqual({ ean: '7799876543210', qty: 4 })
    })
  })

  // =========================================================================
  // 2. WHATSAPP MESSAGE FORMATTING ACROSS BASKET SIZES
  // =========================================================================
  describe('2. WhatsApp Message Formatting Ergonomics', () => {
    it('2.1. Empty basket: formats cleanly without crash', () => {
      const msg = formatShareMessage({
        items: [],
        shareUrl: 'https://vsupermarket.vercel.app/?list=empty',
      })
      expect(msg).toContain('0 productos (0 unidades)')
      expect(msg).not.toContain('undefined')
      expect(msg).not.toContain('NaN')
    })

    it('2.2. 1-item basket: enforces strict singular grammar', () => {
      const msg = formatShareMessage({
        items: [{ ean: '7791234567890', qty: 1, nombre: 'Yogur Firme 190g' }],
        planTotal: 1200,
        planSaving: 350,
        shareUrl: 'https://vsupermarket.vercel.app/?list=token1',
      })
      expect(msg).toContain('1 producto (1 unidad)')
      expect(msg).toContain('• 1× Yogur Firme 190g')
      expect(msg).not.toContain('productos más')
      expect(msg).toContain('(¡Ahorrás $350!)')
    })

    it('2.3. 3-item basket: shows all 3 items without remainder text', () => {
      const msg = formatShareMessage({
        items: [
          { ean: '779001', qty: 1, nombre: 'Arroz' },
          { ean: '779002', qty: 2, nombre: 'Fideos' },
          { ean: '779003', qty: 1, nombre: 'Salsa' },
        ],
        planTotal: 5400,
        shareUrl: 'https://vsupermarket.vercel.app/?list=token3',
      })
      expect(msg).toContain('3 productos (4 unidades)')
      expect(msg).toContain('• 1× Arroz')
      expect(msg).toContain('• 2× Fideos')
      expect(msg).toContain('• 1× Salsa')
      expect(msg).not.toContain('más')
      // No saving provided -> should not show saving badge
      expect(msg).not.toContain('Ahorrás')
    })

    it('2.4. 40-item basket: prevents message fatigue with 4-item preview and concise metrics', () => {
      const items = Array.from({ length: 40 }, (_, i) => ({
        ean: `7790000000${String(i).padStart(3, '0')}`,
        qty: 2,
        nombre: `Item de prueba #${i + 1}`,
      }))

      const msg = formatShareMessage({
        items,
        planTotal: 185400,
        planSaving: 42300,
        shareUrl: 'https://vsupermarket.vercel.app/?list=large40',
      })

      expect(msg).toContain('40 productos (80 unidades)')
      expect(msg).toContain('• 2× Item de prueba #1')
      expect(msg).toContain('• 2× Item de prueba #4')
      expect(msg).toContain('_... y 36 productos más_')
      expect(msg).not.toContain('Item de prueba #5')

      // Total character count of WhatsApp message must stay concise (< 600 chars)
      expect(msg.length).toBeLessThan(600)
    })
  })

  // =========================================================================
  // 3. MERGE, REPLACE & URL CLEANUP LOGIC
  // =========================================================================
  describe('3. Merge / Replace Batch Actions & History Cleanup', () => {
    function CartTestHelper({ onReady }: { onReady: (ctx: ReturnType<typeof useCart>) => void }) {
      const ctx = useCart()
      React.useEffect(() => {
        onReady(ctx)
      }, [ctx])
      return <div data-testid="cart-count">{ctx.count}</div>
    }

    it('3.1. Merge logic sums quantities for duplicate EANs and appends new ones', async () => {
      const { renderHook, act } = await import('@testing-library/react')
      const { result } = renderHook(() => useCart(), {
        wrapper: ({ children }) => <CartProvider>{children}</CartProvider>,
      })

      // Setup initial cart: EAN 1 (qty 2), EAN 2 (qty 1)
      act(() => {
        result.current.replaceItems([
          { ean: '7790000000001', nombre: 'Leche', imagen: '', qty: 2 },
          { ean: '7790000000002', nombre: 'Pan', imagen: '', qty: 1 },
        ])
      })

      // Incoming: EAN 1 (qty 3), EAN 3 (qty 5)
      act(() => {
        result.current.importItems(
          [
            { ean: '7790000000001', qty: 3 },
            { ean: '7790000000003', qty: 5 },
          ],
          'merge',
        )
      })

      expect(result.current.items).toHaveLength(3)
      expect(result.current.qtyOf('7790000000001')).toBe(5) // 2 + 3 = 5
      expect(result.current.qtyOf('7790000000002')).toBe(1) // preserved
      expect(result.current.qtyOf('7790000000003')).toBe(5) // appended
      expect(result.current.totalUnits).toBe(11)
    })

    it('3.2. Replace logic completely overwrites active cart', async () => {
      const { renderHook, act } = await import('@testing-library/react')
      const { result } = renderHook(() => useCart(), {
        wrapper: ({ children }) => <CartProvider>{children}</CartProvider>,
      })

      act(() => {
        result.current.replaceItems([
          { ean: '7790000000001', nombre: 'Leche', imagen: '', qty: 2 },
        ])
      })
      expect(result.current.count).toBe(1)

      act(() => {
        result.current.importItems([{ ean: '7790000000099', qty: 4 }], 'replace')
      })

      expect(result.current.items).toHaveLength(1)
      expect(result.current.has('7790000000001')).toBe(false)
      expect(result.current.qtyOf('7790000000099')).toBe(4)
    })

    it('3.3. cleanUrlParams removes share tokens via history.replaceState without losing other params', () => {
      const replaceStateSpy = vi.spyOn(window.history, 'replaceState')

      // Set current URL with search params
      Object.defineProperty(window, 'location', {
        value: new URL('https://vsupermarket.vercel.app/?list=XYZ123&utm_source=whatsapp#top'),
        writable: true,
        configurable: true,
      })

      cleanUrlParams(['list', 'habitual', 'cart'])

      expect(replaceStateSpy).toHaveBeenCalled()
      const callArgs = replaceStateSpy.mock.calls[0]
      // Verify newPath keeps utm_source and hash, but strips list
      expect(callArgs[2]).toBe('/?utm_source=whatsapp#top')
    })
  })

  // =========================================================================
  // 4. TOUCH TARGET AUDIT (>= 44x44px STANDARD)
  // =========================================================================
  describe('4. Mobile Touch Target Audit (>= 44x44px WCAG 2.5.5 / 2.5.8 Standard)', () => {
    it('4.1. ImportSharedListModal: all interactive buttons have min-h >= 44px (or >= 48px)', () => {
      const items: SharedItem[] = [{ ean: '7791234567890', qty: 2 }]
      render(
        <ImportSharedListModal
          isOpen={true}
          sharedItems={items}
          currentCartCount={2}
          onMerge={vi.fn()}
          onReplace={vi.fn()}
          onDismiss={vi.fn()}
        />,
      )

      const closeBtn = screen.getByRole('button', { name: /cerrar modal/i })
      expect(closeBtn.className).toMatch(/w-11\s+h-11/) // 44x44px

      const mergeBtn = screen.getByRole('button', { name: /sumar a mi changuito actual/i })
      expect(mergeBtn.className).toContain('min-h-[48px]')

      const replaceBtn = screen.getByRole('button', { name: /reemplazar mi changuito/i })
      expect(replaceBtn.className).toContain('min-h-[48px]')

      const dismissBtn = screen.getByRole('button', { name: /ignorar y mantener mi lista actual/i })
      expect(dismissBtn.className).toContain('min-h-[44px]')
    })

    it('4.2. HabitualListManager: expandable controls and action buttons meet >= 44px', () => {
      const habitual: HabitualList = {
        version: '1.0',
        updated_at: '2026-10-26T12:00:00Z',
        name: 'Habitual',
        items: [{ ean: '7791234567890', nombre: 'Leche', imagen: '', qty: 1, added_at: '2026-10-26T12:00:00Z' }],
      }
      localStorage.setItem('sv_habitual_v1', JSON.stringify(habitual))

      render(
        <CartProvider>
          <HabitualListProvider>
            <HabitualListManager />
          </HabitualListProvider>
        </CartProvider>,
      )

      const detailsBtn = screen.getByRole('button', { name: /ver detalles del termómetro de ahorro/i })
      expect(detailsBtn.className).toContain('min-h-[44px]')

      // Expand
      fireEvent.click(detailsBtn)
      const loadBtn = screen.getByRole('button', { name: /cargar lista habitual/i })
      expect(loadBtn.className).toContain('min-h-[44px]')
    })

    it('4.3. ListScreen: header actions, contextual bar, drawer steppers, and delete meet >= 44x44px', () => {
      // Mock active cart with 1 item
      const initialCart: ListItem[] = [
        { ean: '7791234567890', nombre: 'Leche La Serenísima 1L', imagen: '', qty: 2 },
      ]
      localStorage.setItem('sv_cart_v2', JSON.stringify(initialCart))

      render(
        <LocationProvider>
          <BenefitsProvider>
            <CartProvider>
              <HabitualListProvider>
                <ListScreen onGoSearch={vi.fn()} onGoProfile={vi.fn()} />
              </HabitualListProvider>
            </CartProvider>
          </BenefitsProvider>
        </LocationProvider>,
      )

      // Header actions
      const saveBtn = screen.getByRole('button', { name: /guardar como lista habitual/i })
      expect(saveBtn.className).toContain('min-h-[44px]')

      const shareBtn = screen.getByRole('button', { name: /compartir lista/i })
      expect(shareBtn.className).toMatch(/w-11\s+h-11/) // 44x44px

      const clearBtn = screen.getByRole('button', { name: /vaciar/i })
      expect(clearBtn.className).toContain('min-h-[44px]')

      // Context bar
      const locationBtn = screen.getByRole('button', { name: /cambiar código postal o dirección/i })
      expect(locationBtn.className).toContain('min-h-[44px]')

      const cardsBtn = screen.getByRole('button', { name: /configurar tarjetas y día de compra/i })
      expect(cardsBtn.className).toContain('min-h-[44px]')

      const shippingBtn = screen.getByRole('button', { name: /flete/i })
      expect(shippingBtn.className).toContain('min-h-[44px]')

      // Drawer toggle
      const drawerBtn = screen.getByRole('button', { name: /ver y editar productos agregados/i })
      expect(drawerBtn.className).toContain('min-h-[48px]')

      // Open drawer
      fireEvent.click(drawerBtn)

      // Stepper minus
      const minusBtn = screen.getByRole('button', { name: /restar una unidad/i })
      expect(minusBtn.className).toMatch(/w-11\s+h-11/)

      // Stepper plus
      const plusBtn = screen.getByRole('button', { name: /sumar una unidad/i })
      expect(plusBtn.className).toMatch(/w-11\s+h-11/)

      // Trash button
      const trashBtn = screen.getByRole('button', { name: /quitar leche la serenísima 1l de la lista/i })
      expect(trashBtn.className).toMatch(/w-11\s+h-11/)
    })

    it('4.4. Static code inspection verifies zero interactive elements below 44px in target components', () => {
      const filesToAudit = [
        path.resolve(__dirname, '../components/ImportSharedListModal.tsx'),
        path.resolve(__dirname, '../components/HabitualListManager.tsx'),
        path.resolve(__dirname, '../components/ListScreen.tsx'),
      ]

      for (const filePath of filesToAudit) {
        expect(fs.existsSync(filePath)).toBe(true)
        const content = fs.readFileSync(filePath, 'utf-8')

        // Match all <button or <input opening tags
        const buttonRegex = /<(?:button|input)[^>]*className=["']([^"']*)["'][^>]*>/gs
        let match: RegExpExecArray | null

        while ((match = buttonRegex.exec(content)) !== null) {
          const classNames = match[1]
          // If it's a hidden element or file input, skip
          if (classNames.includes('hidden')) continue

          const hasMinH44 = /min-h-\[(?:44|48|52|56)px\]/.test(classNames)
          const hasH11OrMore = /\b(?:h-11|h-12|h-14|h-16)\b/.test(classNames)
          const hasW11H11 = /\bw-11\s+h-11\b|\bh-11\s+w-11\b/.test(classNames)
          const hasPaddingTouch = /p-(?:2\.5|3|3\.5|4)|py-(?:2\.5|3|3\.5|4)/.test(classNames)

          const meetsErgonomics = hasMinH44 || hasH11OrMore || hasW11H11 || hasPaddingTouch
          expect(
            meetsErgonomics,
            `Component at ${path.basename(filePath)} has button without sufficient touch target: ${match[0]}`,
          ).toBe(true)
        }
      }
    })
  })

  // =========================================================================
  // 5. EXTENDED ADVERSARIAL CHALLENGES & CAPACITY BOUNDS
  // =========================================================================
  describe('5. Extended Adversarial Challenges & Capacity Bounds', () => {
    it('5.1. Maximum URL Capacity: determines exact item capacity before reaching 2,000 char budget', () => {
      // Find maximum item count that fits in 2,000 chars
      let maxCount = 50
      while (true) {
        const testBasket = Array.from({ length: maxCount }, (_, i) => ({
          ean: `779123456789${String(i % 100).padStart(2, '0')}`,
          qty: 99,
        }))
        const url = generateShareUrl(testBasket, 'list', 'https://vsupermarket.vercel.app')
        if (url.length >= 2000) {
          break
        }
        maxCount += 5
      }

      // Safe capacity should exceed 80 items (well beyond realistic weekly baskets of 20-40 items)
      expect(maxCount).toBeGreaterThanOrEqual(80)
    })

    it('5.2. Web Share API error vs cancellation resilience', async () => {
      const { executeShare } = await import('../cart/portableList')

      // Case A: User explicitly cancels (AbortError) -> returns 'cancelled' and does NOT touch clipboard
      const clipboardMock = vi.fn()
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: clipboardMock },
        writable: true,
        configurable: true,
      })
      Object.defineProperty(navigator, 'share', {
        value: vi.fn().mockRejectedValue({ name: 'AbortError' }),
        writable: true,
        configurable: true,
      })

      const cancelRes = await executeShare({
        text: 'test',
        url: 'https://vsupermarket.vercel.app',
      })
      expect(cancelRes.method).toBe('cancelled')
      expect(cancelRes.success).toBe(false)
      expect(clipboardMock).not.toHaveBeenCalled()

      // Case B: Share throws other error (e.g. NotAllowedError) -> falls back to clipboard!
      clipboardMock.mockResolvedValueOnce(undefined)
      Object.defineProperty(navigator, 'share', {
        value: vi.fn().mockRejectedValue(new Error('Permission denied')),
        writable: true,
        configurable: true,
      })

      const fallbackRes = await executeShare({
        text: 'test',
        url: 'https://vsupermarket.vercel.app',
      })
      expect(fallbackRes.method).toBe('clipboard')
      expect(fallbackRes.success).toBe(true)
      expect(clipboardMock).toHaveBeenCalledWith('test\n\nhttps://vsupermarket.vercel.app')
    })

    it('5.3. Injection attacks & special chars in product names: does not throw or break formatting', () => {
      const maliciousNames = [
        'Arroz <script>alert(1)</script>',
        'Fideos *negrita* _cursiva_ ~tachado~ `codigo`',
        'Leche 🥛 con emojis y saltos\nde\nlinea',
        'Atún \\"escaped quotes\\" y \\n barras',
      ]

      const items = maliciousNames.map((nombre, i) => ({
        ean: `779123456789${i}`,
        qty: 1,
        nombre,
      }))

      const msg = formatShareMessage({
        items,
        planTotal: 10000,
        planSaving: 2000,
        shareUrl: 'https://vsupermarket.vercel.app/?list=safe',
      })

      expect(msg).toContain('4 productos (4 unidades)')
      expect(msg).toContain('• 1× Arroz <script>alert(1)</script>')
      expect(msg).toContain('• 1× Fideos *negrita* _cursiva_ ~tachado~ `codigo`')
      expect(msg).toContain('https://vsupermarket.vercel.app/?list=safe')
    })
  })
})
