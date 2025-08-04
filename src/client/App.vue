<template>
  <div class="container py-4">
    <h1 class="mb-4">Elaborazione immagini per Leggio</h1>

    <div class="mb-3">
      <button class="btn btn-primary me-2" @click="selectFolder">Seleziona cartella</button>
      <span v-if="selectedFolder" class="fst-italic text-secondary">
        Cartella selezionata: {{ selectedFolder }}
      </span>
    </div>

    <div class="mb-3">
      <button class="btn btn-secondary me-2" @click="selectOutput">Seleziona cartella output</button>
      <span v-if="selectedOutput" class="fst-italic text-secondary">
        Output: {{ selectedOutput }}
      </span>
    </div>

    <div class="form-check mb-3">
      <input class="form-check-input" type="checkbox" id="cropCheckbox" v-model="crop" />
      <label class="form-check-label" for="cropCheckbox">Abilita crop immagini</label>
    </div>

    <div class="mb-3" v-if="showCsvInput">
      <label class="form-label">
        Fermati alla riga CSV n°:
        <input
          type="number"
          v-model.number="maxCsvLine"
          min="1"
          class="form-control d-inline-block"
          style="width:100px;"
          placeholder="(tutte)"
        />
      </label>
    </div>

    <div class="mb-3">
      <button class="btn btn-success me-2" :disabled="!selectedFolder || processing" @click="startProcess">
        Processa
      </button>
      <button class="btn btn-danger" :disabled="!processing" @click="stopProcess">Ferma</button>
    </div>

    <div class="mb-3">
      <div v-if="!showFolderProgress" class="progress" style="height:24px;">
        <div
          class="progress-bar"
          role="progressbar"
          :style="{ width: percent + '%' }"
          :aria-valuenow="percent"
          aria-valuemin="0"
          aria-valuemax="100"
        >
          {{ percent }}%
        </div>
      </div>
    </div>

    <!-- Componente progresso cartelle -->
    <FolderProgress v-if="showFolderProgress" :foldersStatus="foldersStatus" />

    <pre class="font-monospace text-primary">{{ csvText }}</pre>

    <!-- Collapsible mapping panel -->
    <div v-if="showMapping" class="mt-4">
      <div class="card">
        <div class="card-header p-0">
          <button
            class="btn btn-link w-100 text-start py-2 px-3"
            @click="mappingExpanded = !mappingExpanded"
          >
            <strong>Mappa campi Database - Colonne CSV</strong>
            <span class="float-end">{{ mappingExpanded ? '▲' : '▼' }}</span>
          </button>
        </div>
        <div v-show="mappingExpanded" class="card-body p-3">
          <div class="row">
            <div class="col-md-6" v-for="section in ['document','image']" :key="section">
              <h6 class="text-capitalize">{{ section }}</h6>
              <div v-if="!Object.keys(resolvedFlat[section]).length" class="text-muted fst-italic">
                Nessuna mappatura configurata
              </div>
              <div v-else>
                <div v-for="(value,key) in resolvedFlat[section]" :key="key" class="mb-3">
                  <div v-if="value" class="d-flex flex-column flex-sm-row flex-wrap align-items-start align-items-sm-center gap-2">
                    <span class="fw-bold text-primary" :title="getFieldDescription(section,key) || ''" style="cursor: help;">
                      {{ key }}:
                    </span>
                    <span
                      v-if="value"
                      class="badge bg-success text-wrap"
                      style="white-space: normal; max-width: 100%;"
                    >
                      {{ value }}
                    </span>
                    <span v-else class="badge bg-warning">Non mappato</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Sezione anteprima CSV -->
    <div v-if="csvMappingFile" class="mt-4">
      <div class="card">
        <div class="card-body p-3">
          <CsvPreview :csvPath="csvMappingFile" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// Component imports
import MapCSV from './components/MapCSV.vue';
import CsvPreview from './components/CsvPreview.vue';
import FolderProgress from './components/FolderProgress.vue';

// Framework imports
import { ref, reactive, computed, watch, onMounted, toRaw } from 'vue';

// Riferimenti reattivi per stato dell'interfaccia
const selectedFolder = ref(null)
const selectedOutput = ref(null)
const crop = ref(true)
const maxCsvLine = ref(null)
const processing = ref(false)
const percent = ref(0)
const loadingText = ref('')
const progressText = ref('')
const csvText = ref('')
const showCsvInput = ref(false)
const csvHeaders = ref([])
const showMapping = ref(false)
const mappingExpanded = ref(false)
const csvMappingSectionExpanded = ref(false)
const csvPreviewSectionExpanded = ref(false)

// Stato per il progresso delle cartelle
const foldersStatus = ref([])
const showFolderProgress = ref(false)

// Path del file CSV per l'anteprima
const csvMappingFile = ref('')

// Mappature: originale (flat) e risolta per visualizzazione
const csvMapping = ref({ document: {}, image: {} })
const resolvedFlat = reactive({ document: {}, image: {} })
const databaseBridge = ref({ document: {}, image: {} })

    /**
     * Restituisce la descrizione di un campo dal bridge JSON
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
          parts.slice(0, -1).forEach(p => { cur[p] = cur[p] || {};
            cur = cur[p]
          })
          cur[parts[parts.length - 1]] = val
        })
        out[sec] = obj
      }
      return out
    }

    // Gestione eventi di progresso inviate da Electron
    onMounted(() => {
      window.electronAPI.onProgressUpdate(progress => {
        loadingText.value = ''
        
        if (progress.type === 'folders_init') {
          // Inizializzazione: mostra sempre il componente (anche senza sottocartelle)
          foldersStatus.value = progress.foldersStatus
          showFolderProgress.value = true
        } else if (progress.type === 'file_progress' || progress.type === 'main_folder_progress') {
          // Aggiornamento progresso: aggiorna stato cartelle
          foldersStatus.value = progress.foldersStatus
        } else {
          // Vecchio formato: usa barra di progresso classica
          showFolderProgress.value = false
        }
        
        const { current, total, currentFile, folderIdx, folderTotal, currentFolder } = progress
        if (total) percent.value = Math.floor((current / total) * 100)
        let t = ''
        if (folderIdx && folderTotal && currentFolder) t += `Cartella ${folderIdx} di ${folderTotal}: ${currentFolder}\n`
        if (current != null && total != null && currentFile) t += `File ${current} di ${total}: ${currentFile}`
        progressText.value = t
      })
      window.electronAPI.onCsvProgress(p => {
        const { current, total, codice } = p
        let t = `Organizzazione CSV: ${current} di ${total}`
        if (codice) t += `\nUltimo: ${codice}`
        csvText.value = t
      })
    })

// Watcher per quando viene selezionata la cartella CSV
watch(selectedFolder, async folder => {
  if (!folder) {
    csvMappingFile.value = ''
    return
  }
  // Carica bridge JSON e controlla presenza CSV
  try {
    databaseBridge.value = JSON.parse(await window.electronAPI.readPublicFile('database_bridge.json'))
  } catch {
    databaseBridge.value = { document: {}, image: {} }
  }

  const hasCsv = await window.electronAPI.hasCsvInFolder(folder)
  showCsvInput.value = hasCsv
  if (!hasCsv) { 
    showMapping.value = false
    csvMappingFile.value = ''
    return 
  }

  const files = await window.electronAPI.readDir(folder)
  const csvFile = files.find(f => f.toLowerCase().endsWith('.csv'))
  if (!csvFile) { 
    showMapping.value = false
    csvMappingFile.value = ''
    return 
  }

  // Imposta il path completo del file CSV
  csvMappingFile.value = `${folder}/${csvFile}`  // Ottieni intestazioni CSV
  csvHeaders.value = await window.electronAPI.getCsvHeaders(`${folder}/${csvFile}`)

  // Filtra colonne con suffisso [lang], mantenendo solo la prima occorrenza per base
  const filteredHeaders = []
  const seenBases = new Set()
  csvHeaders.value.forEach(header => {
    const match = header.match(/^(.*)\[[^\]]+\]$/)
    const base = match ? match[1] : header
    if (!seenBases.has(base)) {
      seenBases.add(base)
      filteredHeaders.push(header)
    }
  })

  // Carica mappa utente di default e appiattiscila
  let userMap = {}
  try {
    userMap = JSON.parse(await window.electronAPI.readPublicFile('default_csv_map.json'))
  } catch {
    userMap = { document: {}, image: {} }
  }
  csvMapping.value = flattenMap(userMap)

  // Risolvi mapping utilizzando solo filteredHeaders per evitare duplicati [lang]
  ;['document', 'image'].forEach(sec => {
    resolvedFlat[sec] = {}
    Object.entries(csvMapping.value[sec]).forEach(([key, descriptor]) => {
      let matchHeader = ''
      if (typeof descriptor === 'string' && descriptor.trim()) {
        // trova la prima intestazione filtrata che inizia con il descriptor
        const lowerDesc = descriptor.trim().toLowerCase()
        matchHeader = filteredHeaders.find(h => h.toLowerCase().startsWith(lowerDesc)) || ''
      }
      resolvedFlat[sec][key] = matchHeader
    })
  })

  showMapping.value = true
})

    // Selezione cartelle e process
    const selectFolder = async () => {
      const f = await window.electronAPI.selectFolder()
      if (f) selectedFolder.value = f
    }
    const selectOutput = async () => {
      const f = await window.electronAPI.selectOutputFolder()
      if (f) selectedOutput.value = f
    }
    const startProcess = async () => {
      processing.value = true
      loadingText.value = 'Conteggio cartelle in corso...'
      progressText.value = ''
      csvText.value = ''
      percent.value = 0
      foldersStatus.value = []
      showFolderProgress.value = false
      
      const finalMap = unflattenMap(resolvedFlat)
      const res = await window.electronAPI.processImages(
        selectedFolder.value,
        selectedOutput.value,
        maxCsvLine.value,
        crop.value,
        finalMap
      )
      processing.value = false
      loadingText.value = ''
      showFolderProgress.value = false
      alert(res.success ? 'Finito!' : 'Errore: ' + (res.error || ''))
    }
    const stopProcess = () => {
    if (processing.value) window.electronAPI.stopProcessing()
}
</script><style>
body { margin: 0; }
pre { white-space: pre-wrap; }
</style>
