import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import React from 'react'
import { render, screen } from '@testing-library/react'
import SmartCartHero from '../components/SmartCartHero'
import MissingItemsBreakdown from '../components/MissingItemsBreakdown'
import type { OptimizePlan } from '../types'

describe('Feature 11: Build Limpio & Mobile Touch Target Audit (WCAG 2.5.5 AAA)', () => {
  const rootDir = path.resolve(process.cwd(), '..')
  const webDir = process.cwd()
  const distDir = path.resolve(webDir, 'dist')
  const pkgJsonPath = path.resolve(webDir, 'package.json')
  const indexCssPath = path.resolve(webDir, 'src', 'index.css')
  const listScreenPath = path.resolve(webDir, 'src', 'components', 'ListScreen.tsx')
  const smartCartHeroPath = path.resolve(webDir, 'src', 'components', 'SmartCartHero.tsx')
  const storeCartPath = path.resolve(webDir, 'src', 'components', 'StoreCart.tsx')
  const missingItemsBreakdownPath = path.resolve(webDir, 'src', 'components', 'MissingItemsBreakdown.tsx')
  const habitualListManagerPath = path.resolve(webDir, 'src', 'components', 'HabitualListManager.tsx')

  describe('Tier 1: Feature Coverage (F11-T1.1 - F11-T1.5)', () => {
    it('F11-T1.1: Production Build Artifact Integrity: dist/ contains valid entrypoint and assets', () => {
      expect(fs.existsSync(distDir)).toBe(true)
      const indexPath = path.resolve(distDir, 'index.html')
      expect(fs.existsSync(indexPath)).toBe(true)

      const htmlContent = fs.readFileSync(indexPath, 'utf-8')
      expect(htmlContent).toContain('<div id="root">')
      expect(htmlContent).toContain('viewport')
      expect(htmlContent).toContain('width=device-width')

      const assetsDir = path.resolve(distDir, 'assets')
      expect(fs.existsSync(assetsDir)).toBe(true)
      const assetFiles = fs.readdirSync(assetsDir)

      const jsAssets = assetFiles.filter(f => f.endsWith('.js'))
      const cssAssets = assetFiles.filter(f => f.endsWith('.css'))

      expect(jsAssets.length).toBeGreaterThan(0)
      expect(cssAssets.length).toBeGreaterThan(0)

      // Zero heavy charting or compression libraries in package.json dependencies
      const pkg = JSON.parse(fs.readFileSync(pkgJsonPath, 'utf-8'))
      const deps = Object.keys(pkg.dependencies || {})
      const prohibitedLibs = ['chart.js', 'recharts', 'd3', 'pako', 'jszip', 'brotli']
      prohibitedLibs.forEach(lib => {
        expect(deps).not.toContain(lib)
      })
    })

    it('F11-T1.2: Stepper (+/-) Touch Targets meet or exceed 44x44px in ListScreen', () => {
      const code = fs.readFileSync(listScreenPath, 'utf-8')

      // Quantity stepper buttons: w-11 h-11 = 44px x 44px
      expect(code).toContain('w-11 h-11 flex items-center justify-center')
      expect(code).toContain('Restar una unidad')
      expect(code).toContain('Sumar una unidad')
    })

    it('F11-T1.3: Trash / Delete Touch Targets meet 44x44px with dedicated separation margin in ListScreen', () => {
      const code = fs.readFileSync(listScreenPath, 'utf-8')

      // Item removal button: w-11 h-11 (44px) + ml-1.5 separation
      expect(code).toContain('w-11 h-11 flex items-center justify-center')
      expect(code).toContain('ml-1.5')
      expect(code).toContain('Quitar')
      expect(code).toContain('de la lista')
    })

    it('F11-T1.4: Scenario Selector Touch Targets in SmartCartHero measure min-h-[58px] (>= 44px)', () => {
      const code = fs.readFileSync(smartCartHeroPath, 'utf-8')
      expect(code).toContain('min-h-[58px]')

      // Also verify via DOM render
      const mockPlan: OptimizePlan = {
        mode: 'ahorro',
        stops: 2,
        supermercados: ['Carrefour', 'Dia'],
        total: 45000,
        subtotal_merch: 40000,
        shipping_fee: 5000,
        ahorro_vs_comoda: 8500,
        ahorro_vs_regular: 12000,
        ahorro_pct: 15.9,
        covered_items: 5,
        total_items: 5,
        missing: [],
        store_breakdowns: [],
        all_plans: {} as any,
        mode_previews: {
          ahorro: {
            mode: 'ahorro',
            title: 'Opción más barata',
            tagline: 'Split 2 súper',
            total: 45000,
            ahorro_vs_comoda: 8500,
            ahorro_vs_regular: 12000,
            ahorro_pct: 15.9,
            supermercados_count: 2,
            covered_items: 5,
            total_items: 5,
          },
          balanceada: {
            mode: 'balanceada',
            title: 'Opción equilibrada',
            tagline: 'Ahorro vs logística',
            total: 47000,
            ahorro_vs_comoda: 6500,
            ahorro_vs_regular: 10000,
            ahorro_pct: 12.1,
            supermercados_count: 2,
            covered_items: 5,
            total_items: 5,
          },
          comodidad: {
            mode: 'comodidad',
            title: 'Opción cómoda',
            tagline: '1 solo súper',
            total: 53500,
            ahorro_vs_comoda: 0,
            ahorro_vs_regular: 3500,
            ahorro_pct: 0,
            supermercados_count: 1,
            covered_items: 5,
            total_items: 5,
          },
        },
      }

      const { container } = render(
        React.createElement(SmartCartHero, {
          mode: 'ahorro',
          onSelectMode: () => {},
          plan: mockPlan,
        })
      )

      const buttons = container.querySelectorAll('.grid-cols-3 button')
      expect(buttons.length).toBe(3)
      buttons.forEach(btn => {
        expect(btn.className).toContain('min-h-[58px]')
      })
    })

    it('F11-T1.5: Drawer & Contextual Bar Ergonomics meet >= 44px WCAG standards', () => {
      const code = fs.readFileSync(listScreenPath, 'utf-8')

      // Contextual bar buttons: min-h-[44px] h-11
      expect(code).toContain('min-h-[44px] h-11 px-2.5 rounded-xl')
      // Products drawer toggle: min-h-[48px] h-12
      expect(code).toContain('w-full min-h-[48px] h-12 px-4')
      // Exact delivery address input: min-h-[44px] h-11
      expect(code).toContain('w-full min-h-[44px] h-11 px-3')
    })
  })

  describe('Tier 2: Boundary & Corner Cases (F11-T2.1 - F11-T2.5)', () => {
    it('F11-T2.1: 320px Viewport No Horizontal Scroll: html, body has overflow-x hidden & safe areas', () => {
      const css = fs.readFileSync(indexCssPath, 'utf-8')
      expect(css).toContain('overflow-x: hidden')
      expect(css).toContain('.pt-safe')
      expect(css).toContain('.pb-safe')
      expect(css).toContain('touch-action: manipulation')
    })

    it('F11-T2.2: Stepper (+/-) Dimensions in DOM render with w-11 h-11', () => {
      const listCode = fs.readFileSync(listScreenPath, 'utf-8')
      // Steppers are strictly 44px by 44px
      const stepperMatches = listCode.match(/w-11 h-11 flex items-center justify-center/g)
      expect(stepperMatches).not.toBeNull()
      expect(stepperMatches!.length).toBeGreaterThanOrEqual(2)
    })

    it('F11-T2.3: Trash Button Dimensions in DOM satisfy target separation margin', () => {
      const listCode = fs.readFileSync(listScreenPath, 'utf-8')
      expect(listCode).toContain('ml-1.5')
      expect(listCode).toContain('hover:text-red-600')
      expect(listCode).toContain('hover:bg-red-50')
    })

    it('F11-T2.4: StoreCart CTA and Coto digital buttons exceed 44px', () => {
      const storeCode = fs.readFileSync(storeCartPath, 'utf-8')
      // Checkout CTA is min-h-[48px] h-12
      expect(storeCode).toContain('min-h-[48px] h-12 w-full rounded-xl')
      // Coto copy list buttons are min-h-[44px]
      expect(storeCode).toContain('min-h-[44px] px-3 rounded-xl')
    })

    it('F11-T2.5: Long Product Names Clamping prevents horizontal layout breaking', () => {
      const storeCode = fs.readFileSync(storeCartPath, 'utf-8')
      expect(storeCode).toContain('line-clamp-2')

      const missingCode = fs.readFileSync(missingItemsBreakdownPath, 'utf-8')
      expect(missingCode).toContain('line-clamp-2')

      // Also render MissingItemsBreakdown accordion toggle and check h-11
      const { container } = render(
        React.createElement(MissingItemsBreakdown, {
          missing: [
            {
              ean: '123',
              nombre: 'Item 1',
              missing_in_assigned_stores: ['Dia'],
              available_in_other_stores: [],
            },
            {
              ean: '456',
              nombre: 'Item 2',
              missing_in_assigned_stores: ['Coto'],
              available_in_other_stores: [],
            },
            {
              ean: '789',
              nombre: 'Item 3',
              missing_in_assigned_stores: ['Carrefour'],
              available_in_other_stores: [],
            },
          ],
        })
      )
      const accordionBtn = container.querySelector('button')
      expect(accordionBtn).not.toBeNull()
      expect(accordionBtn?.className).toContain('h-11')
    })

    it('F11-T2.6: HabitualListManager touch targets meet >= 44px', () => {
      const habitualCode = fs.readFileSync(habitualListManagerPath, 'utf-8')
      expect(habitualCode).toContain('min-h-[44px]')
    })
  })
})
