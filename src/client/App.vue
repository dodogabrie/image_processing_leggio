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

    <div class="form-check mb-3">
      <input class="form-check-input" type="checkbox" id="optimizeVideosCheckbox" v-model="optimizeVideos" />
      <label class="form-check-label" for="optimizeVideosCheckbox">
        Ottimizza video (richiede FFmpeg)
        <small class="text-muted d-block">
          Se disabilitato, i video verranno solo copiati<br>
          <a
            href="#"
            @click.prevent="openFfmpegGuide"
            class="text-decoration-underline"
            style="cursor:pointer"
          >
            Come installare FFmpeg su Windows (WikiHow)
          </a>
        </small>
      </label>
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
      <div v-if="globalImagesTotal > 0" class="mt-2 text-center text-secondary small">
        Immagini totali: {{ globalImagesProcessed }} / {{ globalImagesTotal }}
      </div>
      <div v-if="videoProcessingMessage" class="alert alert-info mt-2 text-center">
        {{ videoProcessingMessage }}
      </div>
    </div>

    <!-- Componente progresso cartelle -->
    <FolderProgress v-if="showFolderProgress" :foldersStatus="foldersStatus" />

    <pre class="font-monospace text-primary">{{ csvText }}</pre>

    <!-- Mostra warning se ci sono colonne CSV senza mapping nel JSON -->
    <div v-if="missingCsvColumns.length" class="alert alert-warning mt-4">
      <strong>Attenzione:</strong> le seguenti colonne non saranno importate perché non è stato possibile associarle a un campo del database:
      <ul class="mb-0">
        <li v-for="col in missingCsvColumns" :key="col">{{ col }}</li>
      </ul>
      Nel caso le colonne elencate presentino campi rilevanti, contattare l'assistenza tecnica.
    </div>

    <!-- Collapsible mapping panel -->
    <div v-if="showMapping" class="mt-4">
      <!-- Custom CSV Map Loader -->
      <CustomCsvMapLoader @mapChanged="handleCustomMapChange" class="mb-3" />
      
      <!-- CSV Mapping Display Component -->
      <CsvMappingDisplay 
        :resolved-flat="resolvedFlat"
        :detected-languages="detectedLanguages"
        :get-field-description="getFieldDescription"
        v-model:expanded="mappingExpanded"
      />
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

  <!-- Modal di risultato -->
  <div v-if="showResultModal" class="modal fade show d-block" tabindex="-1">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">{{ resultSuccess ? 'Successo' : 'Errore' }}</h5>
          <button type="button" class="btn-close" @click="closeResultModal"></button>
        </div>
        <div class="modal-body">
          <p>{{ resultMessage }}</p>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" @click="closeResultModal">Chiudi</button>
        </div>
      </div>
    </div>
  </div>
  <div class="modal-backdrop fade show" v-if="showResultModal"></div>
</template>

<script setup>
// Component imports
import CsvPreview from './components/CsvPreview.vue';
import FolderProgress from './components/FolderProgress.vue';
import CustomCsvMapLoader from './components/CustomCsvMapLoader.vue';
import CsvMappingDisplay from './components/CsvMappingDisplay.vue';

// Composable imports
import { useCsvMapping } from './composables/useCsvMapping.js';

// Framework imports
import { ref, reactive, computed, watch, onMounted } from 'vue';

// Riferimenti reattivi per stato dell’interfaccia
const selectedFolder = ref(null)
const selectedOutput = ref(null)
const crop = ref(false)
const optimizeVideos = ref(false)
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

// Stato per il progresso delle cartelle
const foldersStatus = ref([])
const showFolderProgress = ref(false)
const globalImagesTotal = ref(0)
const globalImagesProcessed = ref(0)
const videoProcessingMessage = ref('')

// Path del file CSV per l’anteprima
const csvMappingFile = ref('')

// Stato per il modal di risultato
const showResultModal = ref(false)
const resultSuccess = ref(false)
const resultMessage = ref('')
const closeResultModal = () => { showResultModal.value = false }

// Usa il composable per la gestione CSV
const { 
  resolvedFlat, 
  detectedLanguages,
  getFieldDescription, 
  unflattenMap, 
  loadCsvMapping, 
  loadDatabaseBridge,
  filteredHeaders
} = useCsvMapping()

// Colonne CSV senza mapping
const missingCsvColumns = computed(() => {
  return filteredHeaders.value.filter(header => {
    const mapped = [
      ...Object.values(resolvedFlat.document), 
      ...Object.values(resolvedFlat.image)
    ]
    return header && !mapped.includes(header)
  })
})

// Gestione eventi di progresso inviate da Electron
onMounted(() => {
  window.electronAPI.onProgressUpdate(progress => {
    if (progress.type === 'video_processing') {
      videoProcessingMessage.value = progress.message || 'Attendere, processamento video in corso...'
    } else {
      videoProcessingMessage.value = ''
    }

    loadingText.value = ''

    if (progress.foldersStatus && progress.foldersStatus.length > 0) {
      foldersStatus.value = progress.foldersStatus
      showFolderProgress.value = true
    } else {
      showFolderProgress.value = false
    }

    const { current, total, currentFile, folderIdx, folderTotal, currentFolder } = progress
    if (total) percent.value = Math.floor((current / total) * 100)
    let t = ''
    if (folderIdx && folderTotal && currentFolder) t += `Cartella ${folderIdx} di ${folderTotal}: ${currentFolder}\n`
    if (current != null && total != null && currentFile) t += `File ${current} di ${total}: ${currentFile}`
    progressText.value = t

    if (typeof progress.globalImagesTotal === 'number') globalImagesTotal.value = progress.globalImagesTotal
    if (typeof progress.globalImagesProcessed === 'number') globalImagesProcessed.value = progress.globalImagesProcessed
  })

  window.electronAPI.onCsvProgress(p => {
    showFolderProgress.value = false
    percent.value = 100
    const { current, total, codice } = p
    let t = `Organizzazione CSV: ${current} di ${total}`
    if (codice) t += `\nUltimo: ${codice}`
    csvText.value = t
  })
})

// Watcher cartella CSV
watch(selectedFolder, async folder => {
  if (!folder) {
    csvMappingFile.value = ''
    return
  }

  await loadDatabaseBridge()

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

  csvMappingFile.value = `${folder}/${csvFile}`
  csvHeaders.value = await window.electronAPI.getCsvHeaders(`${folder}/${csvFile}`)

  // Ora il composable fa parsing degli headers
  await loadCsvMapping(csvHeaders.value)
  showMapping.value = true
})

// Handle custom map change
async function handleCustomMapChange() {
  if (csvHeaders.value.length > 0) {
    await loadCsvMapping(csvHeaders.value)
  }
}

function openFfmpegGuide() {
  window.electronAPI.openExternal('https://www.wikihow.it/Installare-FFmpeg-in-Windows')
}

// Computed unmapped mapping fields
const unmapped = computed(() => {
  const missing = []
  for (const sec of ['document', 'image']) {
    Object.entries(resolvedFlat[sec] || {}).forEach(([key, val]) => {
      if (!val) missing.push(`${sec}.${key}`)
    })
  }
  return missing
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
    finalMap,
    optimizeVideos.value
  )

  processing.value = false
  loadingText.value = ''
  showFolderProgress.value = false

  resultSuccess.value = res.success
  resultMessage.value = res.success ? 'Processamento completato con successo!' : 'Errore: ' + (res.error || '')
  showResultModal.value = true
}
const stopProcess = () => {
  if (processing.value) window.electronAPI.stopProcessing()
}
</script>
