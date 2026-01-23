import { ref, reactive, computed } from 'vue'

/**
 * Composable per gestire la logica di mappatura CSV → Database
 * - Carica mappa custom o default
 * - Interpreta intestazioni CSV (base + lingue disponibili)
 * - Risolve i campi del mapping contro le intestazioni effettive
 * - Espone descrizioni campo dal database bridge
 */
export function useCsvMapping() {
  // Stato reattivo principale
  const csvMapping = ref({ document: {}, image: {} })            // Mappa appiattita da JSON
  const resolvedFlat = reactive({ document: {}, image: {} })     // Mappa risolta con intestazioni effettive
  const detectedLanguages = reactive({ document: {}, image: {} })// Lingue disponibili per ciascun campo
  const databaseBridge = ref({ document: {}, image: {} })        // Schema descrittivo del DB
  const filteredHeaders = ref([])                                // Una intestazione rappresentativa per base

  // Additional CSV UI state
  const csvHeaders = ref([])
  const csvMappingFile = ref('')
  const showMapping = ref(false)
  const mappingExpanded = ref(false)
  const mappingEditorExpanded = ref(false)
  const requiredFieldIds = new Set(['document.identifier', 'document.groupBy'])

  // Computed: missing CSV columns
  const missingCsvColumns = computed(() => {
    return filteredHeaders.value.filter(header => {
      const mapped = [
        ...Object.values(resolvedFlat.document),
        ...Object.values(resolvedFlat.image)
      ]
      return header && !mapped.includes(header)
    })
  })

  /**
   * Restituisce la descrizione di un campo dal bridge JSON
   * es: getFieldDescription('document', 'author.name')
   */
  function getFieldDescription(section, key) {
    const parts = key.split('.')
    let desc = databaseBridge.value[section]
    for (const p of parts) {
      desc = desc && typeof desc === 'object' ? desc[p] : null
    }
    return typeof desc === 'string' ? desc : null
  }

  /**
   * Appiattisce oggetti annidati di mappatura
   * es: { document: { author: { name: "author_name" } } }
   * → { document: { "author.name": "author_name" } }
   */
  function flattenMap(map) {
    const out = { document: {}, image: {} }
    for (const sec of ['document', 'image']) {
      Object.entries(map[sec] || {}).forEach(([k, v]) => {
        if (v && typeof v === 'object') {
          Object.entries(v).forEach(([sk, sv]) => {
            out[sec][`${k}.${sk}`] = sv
          })
        } else {
          out[sec][k] = v
        }
      })
    }
    return out
  }

  /**
   * Ricostruisce la mappa annidata da quella appiattita
   */
  function unflattenMap(flat) {
    const out = { document: {}, image: {} }
    for (const sec of ['document', 'image']) {
      const obj = {}
      Object.entries(flat[sec] || {}).forEach(([fk, val]) => {
        const parts = fk.split('.')
        let cur = obj
        parts.slice(0, -1).forEach(p => { 
          cur[p] = cur[p] || {}
          cur = cur[p]
        })
        cur[parts[parts.length - 1]] = val
      })
      out[sec] = obj
    }
    return out
  }

  /**
   * Analizza le intestazioni CSV e costruisce:
   * - filteredHeaders: uno per base
   * - languagesByBase: lingue disponibili per ciascun prefisso
   */
  function parseCsvHeaders(csvHeaders) {
    const seenBases = new Set()
    const langsByBase = {}
    filteredHeaders.value = []

    csvHeaders.forEach(header => {
      const m = header.match(/^(.*)\[([^\]]+)\]$/)
      if (m) {
        const [ , base, lang ] = m
        langsByBase[base] ??= new Set()
        langsByBase[base].add(lang)

        if (!seenBases.has(base)) {
          seenBases.add(base)
          filteredHeaders.value.push(header) // prima occorrenza per base
        }
      } else {
        langsByBase[header] = new Set(['default'])
        if (!seenBases.has(header)) {
          seenBases.add(header)
          filteredHeaders.value.push(header)
        }
      }
    })

    // converto i Set in array ordinati
    return Object.fromEntries(
      Object.entries(langsByBase).map(([base, langs]) => [base, [...langs].sort()])
    )
  }

  /**
   * Carica la mappa CSV (custom → default → vuota)
   * Risolve subito i campi contro intestazioni CSV (e lingue rilevate)
   */
  async function loadCsvMapping(csvHeaders) {
    let userMap = { document: {}, image: {} }

    // Carica custom o default
    for (const file of ['custom_csv_map.json', 'default_csv_map.json']) {
      try {
        const content = await window.electronAPI.readPublicFile(file)
        if (content && content.trim()) {
          userMap = JSON.parse(content)
          break
        }
      } catch {
        // ignora e passa al prossimo
      }
    }

    // Normalizza struttura
    userMap.document ??= {}
    userMap.image ??= {}

    // Appiattisci
    csvMapping.value = flattenMap(userMap)

    // Analizza intestazioni CSV
    const langsByBase = parseCsvHeaders(csvHeaders)

    // Risolvi mapping
    for (const sec of ['document', 'image']) {
      resolvedFlat[sec] = {}
      detectedLanguages[sec] = {}

      Object.entries(csvMapping.value[sec]).forEach(([key, descriptor]) => {
        let matchHeader = ''
        let langs = []

        if (typeof descriptor === 'string' && descriptor.trim()) {
          const lowerDesc = descriptor.trim().toLowerCase()

          // cerca intestazione che contiene la descrizione (non solo inizia!)
          matchHeader = filteredHeaders.value.find(
            h => h.toLowerCase().includes(lowerDesc)
          ) || ''

          if (matchHeader) {
            const basePrefix = matchHeader.replace(/\[[^\]]+\]$/, '')
            langs = langsByBase[basePrefix] || []
          }
        }

        resolvedFlat[sec][key] = matchHeader
        detectedLanguages[sec][key] = langs
      })
    }
  }

  function flattenBridgeSection(sectionObj, prefix = '') {
    const out = []
    Object.entries(sectionObj || {}).forEach(([key, value]) => {
      const nextKey = prefix ? `${prefix}.${key}` : key
      if (typeof value === 'string') {
        out.push({
          key: nextKey,
          description: value,
          required: requiredFieldIds.has(nextKey)
        })
      } else if (value && typeof value === 'object' && !Array.isArray(value)) {
        out.push(...flattenBridgeSection(value, nextKey))
      }
    })
    return out
  }

  const databaseFieldOptions = computed(() => {
    const doc = flattenBridgeSection(databaseBridge.value.document)
    const img = flattenBridgeSection(databaseBridge.value.image)
    return {
      document: doc.sort((a, b) => a.key.localeCompare(b.key)),
      image: img.sort((a, b) => a.key.localeCompare(b.key))
    }
  })

  const headerFieldMap = computed(() => {
    const map = {}
    for (const section of ['document', 'image']) {
      Object.entries(resolvedFlat[section] || {}).forEach(([key, header]) => {
        if (!header) return
        map[header] = map[header] || []
        map[header].push(`${section}.${key}`)
      })
    }
    return map
  })

  function buildFlatMapFromHeaderSelection(headerToField) {
    const out = { document: {}, image: {} }
    Object.entries(headerToField || {}).forEach(([header, fieldIds]) => {
      const list = Array.isArray(fieldIds) ? fieldIds : [fieldIds]
      list.filter(Boolean).forEach(fieldId => {
        const [section, ...rest] = fieldId.split('.')
        const key = rest.join('.')
        if (!section || !key || !out[section]) return
        out[section][key] = header
      })
    })
    return out
  }

  async function saveCustomMappingFromHeaderSelection(headerToField) {
    const flat = buildFlatMapFromHeaderSelection(headerToField)
    const nested = unflattenMap(flat)
    await window.electronAPI.writePublicFile('custom_csv_map.json', JSON.stringify(nested, null, 2))
    if (csvHeaders.value.length > 0) {
      await loadCsvMapping(csvHeaders.value)
    }
    return flat
  }

  /**
   * Carica il database bridge (descrizioni dei campi DB)
   */
  async function loadDatabaseBridge() {
    try {
      const content = await window.electronAPI.readPublicFile('database_bridge.json')
      databaseBridge.value = JSON.parse(content)
    } catch {
      databaseBridge.value = { document: {}, image: {} }
    }
  }

  return {
    // Stato reattivo
    csvMapping,
    resolvedFlat,
    detectedLanguages,
    databaseBridge,
    filteredHeaders,
    csvHeaders,
    csvMappingFile,
    showMapping,
    mappingExpanded,
    mappingEditorExpanded,
    databaseFieldOptions,
    headerFieldMap,

    // Computed
    missingCsvColumns,

    // Funzioni
    getFieldDescription,
    flattenMap,
    unflattenMap,
    loadCsvMapping,
    loadDatabaseBridge,
    saveCustomMappingFromHeaderSelection
  }
}
