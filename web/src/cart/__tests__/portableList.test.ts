import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  encodeShareableList,
  decodeShareableList,
  generateShareUrl,
  formatShareMessage,
  executeShare,
  cleanUrlParams,
} from '../portableList'

describe('portableList — RFC 4648 Base64url Sharing & WhatsApp Formatter', () => {
  const sampleItems = [
    { ean: '7791234567890', qty: 2, nombre: 'Leche La Serenísima 1L' },
    { ean: '7790987654321', qty: 1, nombre: 'Aceite Cocinero 1.5L' },
    { ean: '7795556667778', qty: 4, nombre: 'Arroz Lucchetti 1kg' },
  ]

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('1. should encode and decode bi-directionally without data loss', () => {
    const encoded = encodeShareableList(sampleItems)
    expect(encoded).toBeTruthy()
    // RFC 4648 §5 guarantees no +, / or =
    expect(encoded).not.toContain('+')
    expect(encoded).not.toContain('/')
    expect(encoded).not.toContain('=')

    const decoded = decodeShareableList(encoded)
    expect(decoded).toHaveLength(3)
    expect(decoded[0]).toEqual({ ean: '7791234567890', qty: 2 })
    expect(decoded[1]).toEqual({ ean: '7790987654321', qty: 1 })
    expect(decoded[2]).toEqual({ ean: '7795556667778', qty: 4 })
  })

  it('2. should handle up to 50 items well within safe 2,000 char URL budget', () => {
    const fiftyItems = Array.from({ length: 50 }, (_, i) => ({
      ean: `77900000000${String(i).padStart(2, '0')}`,
      qty: (i % 5) + 1,
    }))

    const token = encodeShareableList(fiftyItems)
    const url = generateShareUrl(fiftyItems, 'list', 'https://vsupermarket.vercel.app')

    // Expect URL length to be around ~1,100 chars, well below 2,000 chars limit
    expect(url.length).toBeLessThan(1400)
    expect(url.length).toBeGreaterThan(600)

    const decoded = decodeShareableList(token)
    expect(decoded).toHaveLength(50)
    expect(decoded[0].ean).toBe('7790000000000')
    expect(decoded[49].ean).toBe('7790000000049')
  })

  it('3. should gracefully tolerate raw ean:qty format and malformed tokens', () => {
    expect(decodeShareableList('')).toEqual([])
    expect(decodeShareableList('random_corrupted_token_!@#$')).toEqual([])

    // Direct raw format fallback "ean:qty,ean:qty"
    const raw = '7791234567890:2,7790987654321:3'
    const decodedRaw = decodeShareableList(raw)
    expect(decodedRaw).toHaveLength(2)
    expect(decodedRaw[0]).toEqual({ ean: '7791234567890', qty: 2 })
    expect(decodedRaw[1]).toEqual({ ean: '7790987654321', qty: 3 })
  })

  it('4. should filter out invalid EAN barcodes and clamp quantities between 1 and 999', () => {
    const invalidItems = [
      { ean: '123', qty: 1 }, // too short (<8)
      { ean: 'abcdefgh', qty: 1 }, // non-numeric
      { ean: '7791234567890', qty: 0 }, // 0 qty -> clamped to 1
      { ean: '7799876543210', qty: 5000 }, // >999 qty -> clamped to 999
    ]

    const encoded = encodeShareableList(invalidItems)
    const decoded = decodeShareableList(encoded)

    expect(decoded).toHaveLength(2)
    expect(decoded[0]).toEqual({ ean: '7791234567890', qty: 1 })
    expect(decoded[1]).toEqual({ ean: '7799876543210', qty: 999 })
  })

  it('5. should merge duplicate EAN barcodes in incoming encoded tokens', () => {
    // String with duplicate EAN 7791234567890 (qty 2 + qty 3)
    const rawWithDuplicates = '7791234567890:2,7791234567890:3'
    const decoded = decodeShareableList(rawWithDuplicates)
    expect(decoded).toHaveLength(1)
    expect(decoded[0]).toEqual({ ean: '7791234567890', qty: 5 })
  })

  it('6. should format friendly WhatsApp message with 4-item preview and savings metrics', () => {
    const msg = formatShareMessage({
      items: [
        ...sampleItems,
        { ean: '7791112223334', qty: 2, nombre: 'Fideos Matarazzo' },
        { ean: '7799998887776', qty: 1, nombre: 'Yogur Ilolay' },
      ],
      planTotal: 28500,
      planSaving: 6200,
      shareUrl: 'https://vsupermarket.vercel.app/?list=XYZ123',
    })

    expect(msg).toContain('🛒 *Te comparto mi lista de supermercado en SuperVmarket*')
    expect(msg).toContain('5 productos (10 unidades)')
    expect(msg).toContain('💰 Total optimizado: *$28.500* (¡Ahorrás $6.200!)')
    expect(msg).toContain('• 2× Leche La Serenísima 1L')
    expect(msg).toContain('• 1× Aceite Cocinero 1.5L')
    expect(msg).toContain('• 4× Arroz Lucchetti 1kg')
    expect(msg).toContain('• 2× Fideos Matarazzo')
    expect(msg).toContain('_... y 1 producto más_')
    expect(msg).toContain('https://vsupermarket.vercel.app/?list=XYZ123')
  })

  it('7. should generate canonical share URLs for both list and habitual params', () => {
    const listUrl = generateShareUrl(sampleItems, 'list', 'https://vsupermarket.vercel.app')
    expect(listUrl).toContain('https://vsupermarket.vercel.app/?list=')

    const habitualUrl = generateShareUrl(sampleItems, 'habitual', 'https://vsupermarket.vercel.app')
    expect(habitualUrl).toContain('https://vsupermarket.vercel.app/?habitual=')
  })

  it('8. should execute share via navigator.share or fallback to clipboard', async () => {
    // Mock navigator.share
    const shareMock = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'share', {
      value: shareMock,
      writable: true,
      configurable: true,
    })

    const res1 = await executeShare({
      title: 'Lista',
      text: 'Texto de prueba',
      url: 'https://vsupermarket.vercel.app',
    })
    expect(res1.method).toBe('share')
    expect(res1.success).toBe(true)

    // Test clipboard fallback when navigator.share is absent
    Object.defineProperty(navigator, 'share', {
      value: undefined,
      writable: true,
      configurable: true,
    })
    const clipboardMock = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: clipboardMock },
      writable: true,
      configurable: true,
    })

    const res2 = await executeShare({
      title: 'Lista',
      text: 'Texto de prueba',
      url: 'https://vsupermarket.vercel.app',
    })
    expect(res2.method).toBe('clipboard')
    expect(res2.success).toBe(true)
    expect(clipboardMock).toHaveBeenCalledWith('Texto de prueba\n\nhttps://vsupermarket.vercel.app')
  })
})
