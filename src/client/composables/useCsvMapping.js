import { ref, reactive } from 'vue'

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

    // Funzioni
    getFieldDescription,
    flattenMap,
    unflattenMap,
    loadCsvMapping,
    loadDatabaseBridge
  }
}
