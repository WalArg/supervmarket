import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

interface ParsedFeature {
  id: number
  name: string
  classification: 'MANTENER' | 'MEJORAR' | 'SIMPLIFICAR' | 'ELIMINAR' | 'AGREGAR'
  milestone: string
}

function parseProjectMdFeatures(filePath: string): ParsedFeature[] {
  const content = fs.readFileSync(filePath, 'utf-8')
  const lines = content.split('\n')
  const features: ParsedFeature[] = []

  let inTable = false
  for (const line of lines) {
    if (line.includes('| # | Feature | Descripción | Clasificación | Milestone | Fuente |')) {
      inTable = true
      continue
    }
    if (inTable) {
      if (!line.trim().startsWith('|')) {
        if (features.length > 0) break
        continue
      }
      if (line.includes('|---|') || line.includes('|:---|')) {
        continue
      }

      const cols = line.split('|').map(c => c.trim()).filter(Boolean)
      if (cols.length >= 5) {
        const id = parseInt(cols[0], 10)
        if (!isNaN(id)) {
          const rawClassification = cols[3] // e.g. MANTENER, MEJORAR
          // Clean any markdown formatting like * or bold
          const cleanClassification = rawClassification.replace(/[*_]/g, '').trim()
          features.push({
            id,
            name: cols[1],
            classification: cleanClassification as ParsedFeature['classification'],
            milestone: cols[4],
          })
        }
      }
    }
  }

  return features
}

function parseDocFeatures(filePath: string): ParsedFeature[] {
  const content = fs.readFileSync(filePath, 'utf-8')
  const lines = content.split('\n')
  const features: ParsedFeature[] = []

  let inTable = false
  for (const line of lines) {
    if (line.includes('| # | Funcionalidad / Componente |')) {
      inTable = true
      continue
    }
    if (inTable) {
      if (!line.trim().startsWith('|')) {
        if (features.length > 0) break
        continue
      }
      if (line.includes('|---|') || line.includes('|:---|')) {
        continue
      }

      const cols = line.split('|').map(c => c.trim()).filter(Boolean)
      if (cols.length >= 6) {
        const id = parseInt(cols[0], 10)
        if (!isNaN(id)) {
          const rawCat = cols[4] // e.g. `MANTENER` *(Mandatorio)*
          // Extract base category
          let category = 'MANTENER'
          for (const validCat of ['MANTENER', 'MEJORAR', 'SIMPLIFICAR', 'ELIMINAR', 'AGREGAR']) {
            if (rawCat.includes(validCat)) {
              category = validCat
              break
            }
          }

          features.push({
            id,
            name: cols[1],
            classification: category as ParsedFeature['classification'],
            milestone: cols[5],
          })
        }
      }
    }
  }

  return features
}

describe('Feature 10: Matriz de Clasificación Integral (R1 Product Evolution)', () => {
  // Resolve paths robustly from cwd (web directory)
  const rootDir = path.resolve(process.cwd(), '..')
  const projectMdPath = path.resolve(rootDir, 'PROJECT.md')
  const docMdPath = path.resolve(rootDir, 'docs', 'PRODUCT_DIAGNOSIS_AND_EVOLUTION.md')

  it('verifies that PROJECT.md and PRODUCT_DIAGNOSIS_AND_EVOLUTION.md exist', () => {
    expect(fs.existsSync(projectMdPath)).toBe(true)
    expect(fs.existsSync(docMdPath)).toBe(true)
  })

  const projectFeatures = parseProjectMdFeatures(projectMdPath)
  const docFeatures = parseDocFeatures(docMdPath)

  describe('Tier 1: Feature Coverage (F10-T1.1 - F10-T1.5)', () => {
    it('F10-T1.1: Complete 24-Feature Inventory Audit in PROJECT.md', () => {
      expect(projectFeatures.length).toBe(24)
    })

    it('F10-T1.2: Valid Classification Enums across all 24 features', () => {
      const validEnums = new Set(['MANTENER', 'MEJORAR', 'SIMPLIFICAR', 'ELIMINAR', 'AGREGAR'])
      projectFeatures.forEach(feat => {
        expect(validEnums.has(feat.classification)).toBe(true)
      })
    })

    it('F10-T1.3: Milestone Assignment maps each feature to valid milestones (M1-M6)', () => {
      projectFeatures.forEach(feat => {
        const milestones = feat.milestone.split(',').map(m => m.trim())
        expect(milestones.length).toBeGreaterThan(0)
        milestones.forEach(m => {
          expect(['M1', 'M2', 'M3', 'M4', 'M5', 'M6']).toContain(m)
        })
      })
    })

    it('F10-T1.4: Mandatory R1 Restriction (Mercado Libre) is classified as MANTENER and NEVER ELIMINAR', () => {
      const meliFeature = projectFeatures.find(f => f.id === 3)
      expect(meliFeature).toBeDefined()
      expect(meliFeature?.name.toLowerCase()).toContain('mercado libre')
      expect(meliFeature?.classification).toBe('MANTENER')
      expect(meliFeature?.classification).not.toBe('ELIMINAR')

      // Also verify in docs
      const docMeli = docFeatures.find(f => f.id === 3)
      expect(docMeli?.classification).toBe('MANTENER')
      expect(docMeli?.classification).not.toBe('ELIMINAR')
    })

    it('F10-T1.5: Mandatory R1 Restriction (AI Assistant) is classified as MANTENER and NEVER ELIMINAR', () => {
      const aiFeature = projectFeatures.find(f => f.id === 4)
      expect(aiFeature).toBeDefined()
      expect(aiFeature?.name.toLowerCase()).toContain('ia')
      expect(aiFeature?.classification).toBe('MANTENER')
      expect(aiFeature?.classification).not.toBe('ELIMINAR')

      // Also verify in docs
      const docAi = docFeatures.find(f => f.id === 4)
      expect(docAi?.classification).toBe('MANTENER')
      expect(docAi?.classification).not.toBe('ELIMINAR')
    })
  })

  describe('Tier 2: Boundary & Corner Cases (F10-T2.1 - F10-T2.5)', () => {
    it('F10-T2.1: Mandatory R1 restriction compliance explicit negative check for Feature 3', () => {
      const meli = projectFeatures.find(f => f.id === 3)!
      expect(meli.classification).not.toBe('ELIMINAR')
      expect(meli.classification).not.toBe('SIMPLIFICAR')
    })

    it('F10-T2.2: Mandatory R1 restriction compliance explicit negative check for Feature 4', () => {
      const ai = projectFeatures.find(f => f.id === 4)!
      expect(ai.classification).not.toBe('ELIMINAR')
      expect(ai.classification).not.toBe('SIMPLIFICAR')
    })

    it('F10-T2.3: 24 Unique Feature IDs from 1 to 24 with 0 gaps and 0 duplicates', () => {
      const ids = projectFeatures.map(f => f.id)
      expect(new Set(ids).size).toBe(24)
      for (let i = 1; i <= 24; i++) {
        expect(ids).toContain(i)
      }
    })

    it('F10-T2.4: Classification Distribution Counts match canonical specification', () => {
      const counts = projectFeatures.reduce<Record<string, number>>((acc, f) => {
        acc[f.classification] = (acc[f.classification] || 0) + 1
        return acc
      }, {})

      expect(counts['MANTENER']).toBe(6)
      expect(counts['MEJORAR']).toBe(9)
      expect(counts['SIMPLIFICAR']).toBe(4)
      expect(counts['ELIMINAR']).toBe(1)
      expect(counts['AGREGAR']).toBe(4)
      expect(counts['MANTENER'] + counts['MEJORAR'] + counts['SIMPLIFICAR'] + counts['ELIMINAR'] + counts['AGREGAR']).toBe(24)
    })

    it('F10-T2.5: Milestone Alignment populates all milestones M1 through M6 across the 24 features', () => {
      const allAssignedMilestones = new Set(
        projectFeatures.flatMap(f => f.milestone.split(',').map(m => m.trim()))
      )
      expect(allAssignedMilestones.has('M1')).toBe(true)
      expect(allAssignedMilestones.has('M2')).toBe(true)
      expect(allAssignedMilestones.has('M3')).toBe(true)
      expect(allAssignedMilestones.has('M4')).toBe(true)
      expect(allAssignedMilestones.has('M5')).toBe(true)
      expect(allAssignedMilestones.has('M6')).toBe(true)
    })
  })
})
