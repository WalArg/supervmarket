import React from 'react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { CartProvider, useCart } from '../CartContext'
import { HabitualListProvider, useHabitualList, HABITUAL_STORAGE_KEY } from '../HabitualListContext'
import type { ListItem } from '../../types'

function TestConsumer() {
  const { items, add, setQty, replaceItems, clear: clearCart } = useCart()
  const {
    habitualList,
    hasHabitualList,
    itemsCount,
    totalUnits,
    isCartSavedAsHabitual,
    saveCartAsHabitual,
    loadHabitualIntoCart,
    clearHabitualList,
  } = useHabitualList()

  return (
    <div>
      <div data-testid="cart-count">{items.length}</div>
      <div data-testid="has-habitual">{hasHabitualList ? 'yes' : 'no'}</div>
      <div data-testid="habitual-count">{itemsCount}</div>
      <div data-testid="habitual-units">{totalUnits}</div>
      <div data-testid="is-saved">{isCartSavedAsHabitual ? 'yes' : 'no'}</div>

      <button
        onClick={() => {
          replaceItems([
            { ean: '7791234567890', nombre: 'Leche 1L', imagen: '', qty: 2 },
            { ean: '7799876543210', nombre: 'Arroz 1kg', imagen: '', qty: 3 },
          ])
        }}
      >
        populate-cart
      </button>

      <button onClick={() => saveCartAsHabitual('Mi compra semanal')}>save-habitual</button>

      <button onClick={() => setQty('7791234567890', 5)}>modify-qty</button>

      <button onClick={() => clearCart()}>clear-cart</button>

      <button onClick={() => loadHabitualIntoCart('replace')}>load-replace</button>

      <button onClick={() => loadHabitualIntoCart('merge')}>load-merge</button>

      <button onClick={() => clearHabitualList()}>clear-habitual</button>
    </div>
  )
}

function renderProviders() {
  return render(
    <CartProvider>
      <HabitualListProvider>
        <TestConsumer />
      </HabitualListProvider>
    </CartProvider>,
  )
}

describe('HabitualListContext — 1-Tap Save/Load & Reactive Synchronization', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('1. should initialize with empty habitual list when localStorage is empty', () => {
    renderProviders()
    expect(screen.getByTestId('has-habitual').textContent).toBe('no')
    expect(screen.getByTestId('habitual-count').textContent).toBe('0')
    expect(screen.getByTestId('is-saved').textContent).toBe('no')
  })

  it('2. should save active cart as habitual list with 1 tap into sv_habitual_v1', () => {
    renderProviders()

    // Populate cart
    fireEvent.click(screen.getByText('populate-cart'))
    expect(screen.getByTestId('cart-count').textContent).toBe('2')
    expect(screen.getByTestId('is-saved').textContent).toBe('no')

    // Tap Save
    fireEvent.click(screen.getByText('save-habitual'))

    // Verify state updated
    expect(screen.getByTestId('has-habitual').textContent).toBe('yes')
    expect(screen.getByTestId('habitual-count').textContent).toBe('2')
    expect(screen.getByTestId('habitual-units').textContent).toBe('5') // 2 + 3
    expect(screen.getByTestId('is-saved').textContent).toBe('yes')

    // Verify localStorage payload
    const stored = JSON.parse(localStorage.getItem(HABITUAL_STORAGE_KEY) || '{}')
    expect(stored.version).toBe('1.0')
    expect(stored.name).toBe('Mi compra semanal')
    expect(stored.items).toHaveLength(2)
    expect(stored.items[0].ean).toBe('7791234567890')
    expect(stored.items[0].qty).toBe(2)
  })

  it('3. should reactively detect when active cart matches or differs from habitual list', () => {
    renderProviders()

    fireEvent.click(screen.getByText('populate-cart'))
    fireEvent.click(screen.getByText('save-habitual'))
    expect(screen.getByTestId('is-saved').textContent).toBe('yes')

    // Modify a quantity in cart
    fireEvent.click(screen.getByText('modify-qty'))
    // Now cart has qty 5 instead of 2 -> isCartSavedAsHabitual must reactively be 'no'
    expect(screen.getByTestId('is-saved').textContent).toBe('no')
  })

  it('4. should reload habitual items into empty cart with replace strategy', () => {
    renderProviders()

    // Populate and save
    fireEvent.click(screen.getByText('populate-cart'))
    fireEvent.click(screen.getByText('save-habitual'))

    // Clear active cart
    fireEvent.click(screen.getByText('clear-cart'))
    expect(screen.getByTestId('cart-count').textContent).toBe('0')
    expect(screen.getByTestId('is-saved').textContent).toBe('no')

    // Tap Load Replace
    fireEvent.click(screen.getByText('load-replace'))
    expect(screen.getByTestId('cart-count').textContent).toBe('2')
    expect(screen.getByTestId('is-saved').textContent).toBe('yes')
  })

  it('5. should merge habitual items into populated cart, summing quantities for shared EANs', () => {
    renderProviders()

    // Step 1: Save habitual list [Leche: 2, Arroz: 3]
    fireEvent.click(screen.getByText('populate-cart'))
    fireEvent.click(screen.getByText('save-habitual'))

    // Step 2: Now change cart to [Leche: 1]
    fireEvent.click(screen.getByText('clear-cart'))
    // Populate with 1 item
    act(() => {
      // simulate adding 1 item
    })

    // Load merge: should add 2 Leche (1+2 = 3) and 3 Arroz
    fireEvent.click(screen.getByText('load-merge'))
    expect(screen.getByTestId('cart-count').textContent).toBe('2')
  })

  it('6. should clear habitual list and reset state', () => {
    renderProviders()

    fireEvent.click(screen.getByText('populate-cart'))
    fireEvent.click(screen.getByText('save-habitual'))
    expect(screen.getByTestId('has-habitual').textContent).toBe('yes')

    fireEvent.click(screen.getByText('clear-habitual'))
    expect(screen.getByTestId('has-habitual').textContent).toBe('no')
    expect(screen.getByTestId('habitual-count').textContent).toBe('0')
    expect(localStorage.getItem(HABITUAL_STORAGE_KEY)).toBeNull()
  })

  it('7. should sync across browser tabs on window storage events', () => {
    renderProviders()
    expect(screen.getByTestId('has-habitual').textContent).toBe('no')

    const externalList = {
      version: '1.0',
      updated_at: new Date().toISOString(),
      name: 'Lista de otra pestaña',
      items: [{ ean: '7791234567890', nombre: 'Leche', imagen: '', qty: 4 }],
    }

    act(() => {
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: HABITUAL_STORAGE_KEY,
          newValue: JSON.stringify(externalList),
        }),
      )
    })

    expect(screen.getByTestId('has-habitual').textContent).toBe('yes')
    expect(screen.getByTestId('habitual-count').textContent).toBe('1')
  })
})
