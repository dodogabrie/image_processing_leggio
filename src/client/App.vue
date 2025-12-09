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
      <input class="form-check-input" type="checkbox" id="optimizeImagesCheckbox" v-model="optimizeImages" />
      <label class="form-check-label" for="optimizeImagesCheckbox">
        Ottimizza Immagini
        <small class="text-muted d-block">
          Se disabilitato, verrà eseguita solo l'organizzazione CSV (richiede immagini già processate in output)
        </small>
      </label>
    </div>

    <div class="form-check mb-3" v-if="optimizeImages">
      <input class="form-check-input" type="checkbox" id="previewModeCheckbox" v-model="previewMode" />
      <label class="form-check-label" for="previewModeCheckbox">
        Modalità Anteprima
        <small class="text-muted d-block">
          Elabora solo 4 immagini per testare le dimensioni finali. I risultati verranno eliminati automaticamente dopo 60 secondi.
        </small>
      </label>
    </div>

    <div class="mb-3" v-if="optimizeImages">
      <label class="form-label">Aggressività elaborazione:</label>
      <div class="d-flex gap-3">
        <div class="form-check">
          <input class="form-check-input" type="radio" name="aggressivity" id="aggressivityLow" value="low" v-model="aggressivity" />
          <label class="form-check-label" for="aggressivityLow">
            Bassa
            <small class="text-muted d-block">Alta qualità, dimensioni maggiori</small>
          </label>
        </div>
        <div class="form-check">
          <input class="form-check-input" type="radio" name="aggressivity" id="aggressivityStandard" value="standard" v-model="aggressivity" />
          <label class="form-check-label" for="aggressivityStandard">
            Standard
            <small class="text-muted d-block">Bilanciamento qualità/dimensioni</small>
          </label>
        </div>
        <div class="form-check">
          <input class="form-check-input" type="radio" name="aggressivity" id="aggressivityHigh" value="high" v-model="aggressivity" />
          <label class="form-check-label" for="aggressivityHigh">
            Alta
            <small class="text-muted d-block">File più piccoli, qualità ridotta</small>
          </label>
        </div>
      </div>
    </div>

    <div class="form-check mb-3" v-if="optimizeImages">
      <input class="form-check-input" type="checkbox" id="cropCheckbox" v-model="crop" />
      <label class="form-check-label" for="cropCheckbox">Abilita crop immagini</label>
    </div>

    <div class="form-check mb-3" v-if="optimizeImages">
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
    <FolderProgress v-if="showFolderProgress" :foldersStatus="foldersStatus" :currentThumbnail="currentThumbnail" />

    <!-- Preview mode file sizes -->
    <div v-if="previewFileSizes" class="alert alert-info mt-3">
      <h6 class="fw-bold">Dimensioni file anteprima:</h6>
      <ul class="mb-0">
        <li v-for="file in previewFileSizes" :key="file.name">
          <strong>{{ file.name }}</strong>: {{ (file.size / 1024).toFixed(1) }} KB
        </li>
      </ul>
      <small class="text-muted d-block mt-2">I file verranno eliminati automaticamente tra 60 secondi</small>
    </div>

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

    <!-- Sezione di esplorazione output -->
    <section class="mt-5">
      <div class="d-flex align-items-center justify-content-between mb-3 flex-wrap gap-2">
        <div>
          <h4 class="mb-1">Esplora elaborazione</h4>
          <p class="text-muted small mb-0">Apri cartelle e miniature direttamente dall'app, senza file system esterno.</p>
        </div>
        <div class="d-flex gap-2">
          <button class="btn btn-outline-secondary btn-sm" @click="selectOriginalRoot">
            Cartella originali (opzionale)
          </button>
          <button class="btn btn-outline-primary btn-sm" @click="pickProcessedFolder">
            Scegli cartella
          </button>
          <button class="btn btn-outline-secondary btn-sm" :disabled="!explorerRoot" @click="refreshExplorer">
            Aggiorna
          </button>
        </div>
      </div>

      <div v-if="originalRoot" class="alert alert-secondary py-2 mb-3 small d-flex align-items-center gap-2">
        <i class="bi bi-link-45deg"></i>
        Confronto con originali attivo su: <strong class="ms-1">{{ originalRoot }}</strong>
      </div>

      <div class="alert alert-light border small" role="alert">
        Per il confronto, seleziona cartelle allo stesso livello (es. input originale e output elaborato della stessa lavorazione). La cartella originale è facoltativa: se avvii un'elaborazione da qui, useremo automaticamente la cartella di input.
      </div>

      <div v-if="!explorerRoot" class="alert alert-info">
        Elabora un set di immagini o seleziona manualmente una cartella di output per visualizzarne il contenuto.
      </div>

      <div v-else class="card shadow-sm">
        <div class="card-body">
          <div v-if="explorerBreadcrumbs.length" class="d-flex align-items-center flex-wrap gap-2 mb-3">
            <span class="fw-semibold small me-1">Percorso:</span>
            <template v-for="(crumb, idx) in explorerBreadcrumbs" :key="crumb.path">
              <button
                class="btn btn-link btn-sm px-1"
                :class="{ 'text-decoration-underline': idx !== explorerBreadcrumbs.length - 1 }"
                :disabled="idx === explorerBreadcrumbs.length - 1"
                @click="goToBreadcrumb(crumb.path)"
              >
                {{ crumb.name || '/' }}
              </button>
              <span v-if="idx < explorerBreadcrumbs.length - 1" class="text-muted">/</span>
            </template>
          </div>

          <div v-if="explorerError" class="alert alert-danger mb-0">
            {{ explorerError }}
          </div>

          <div v-else-if="explorerLoading" class="text-center py-4">
            <div class="spinner-border text-primary" role="status"></div>
            <div class="small text-muted mt-2">Caricamento contenuto cartella...</div>
          </div>

          <div v-else>
            <div v-if="folderDocument || folderMetadataStatus" class="card folder-meta-card mb-3">
              <div class="card-body p-3">
                <div class="d-flex align-items-center justify-content-between gap-2 flex-wrap">
                  <div>
                    <h6 class="mb-1">Metadati cartella</h6>
                    <p class="text-muted small mb-0 text-truncate">{{ folderMetadataStatus || 'Metadati disponibili' }}</p>
                  </div>
                  <span v-if="folderDocument?.title" class="badge bg-primary-subtle text-primary border">
                    {{ folderDocument.title }}
                  </span>
                </div>
                <dl class="row folder-meta-list mb-0 mt-3" v-if="folderDocumentEntries.length">
                  <template v-for="entry in folderDocumentEntries" :key="entry.key">
                    <dt class="col-sm-4 text-muted small text-uppercase">{{ entry.label }}</dt>
                    <dd class="col-sm-8 mb-2">{{ entry.value || '—' }}</dd>
                  </template>
                </dl>
                <div v-else class="text-muted small">Nessun dettaglio documento trovato.</div>
              </div>
            </div>

            <div v-if="foldersOnly.length" class="d-flex flex-wrap gap-2 mb-3">
              <div
                v-for="folder in foldersOnly"
                :key="folder.path"
                class="folder-chip"
                @click="openFolder(folder.path)"
              >
                <i class="bi bi-folder-fill me-2"></i>
                <span class="text-truncate">{{ folder.name }}</span>
              </div>
            </div>

            <div class="image-grid" v-if="imagesOnly.length">
              <div
                v-for="img in imagesOnly"
                :key="img.path"
              class="image-card"
              @click="openImageModal(img)"
            >
              <div v-if="thumbLoading" class="thumb-loading-overlay">
                <div class="spinner-border text-primary spinner-border-sm" role="status"></div>
              </div>
              <div class="thumb-wrapper">
                <img
                  :src="thumbnailCache[img.thumbnailPath || img.path] || placeholderThumb"
                  :alt="img.name"
                />
                </div>
                <div class="small text-truncate mt-2" :title="img.name">{{ img.name }}</div>
              </div>
            </div>

            <div v-else class="text-muted small text-center py-3">
              Nessuna immagine in questa cartella.
            </div>
          </div>
        </div>
      </div>
    </section>
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
          <p class="result-message">{{ resultMessage }}</p>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" @click="closeResultModal">Chiudi</button>
        </div>
      </div>
    </div>
  </div>
  <div class="modal-backdrop fade show" v-if="showResultModal"></div>

  <!-- Modal anteprima immagine -->
  <div v-if="fullImage.src" class="modal fade show d-block full-image-modal" tabindex="-1">
    <div class="modal-dialog modal-xl modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">{{ fullImage.name }}</h5>
          <button type="button" class="btn-close" @click="closeImageModal"></button>
          </div>
          <div class="modal-body">
            <div class="modal-body-grid">
              <div class="image-area">
                <div class="pane-header">
                  <span class="pane-title">Elaborato</span>
                  <small class="text-muted ms-2 text-truncate d-inline-block" style="max-width: 240px;">{{ fullImage.name }}</small>
                </div>
                <button v-if="modalIndex > 0" class="nav-arrow left" @click="showPrevImage">
                  <span aria-hidden="true">‹</span>
                </button>
              <button class="zoom-toggle" @click="toggleZoom">
                {{ isZoomed ? 'Ripristina' : 'Zoom' }}
              </button>
              <div class="pane-body">
                <img
                  :src="fullImage.src"
                  :alt="fullImage.name"
                  class="full-image"
                  :class="{ zoomed: isZoomed }"
                  :style="{
                    transform: zoomLevel > 1
                      ? `translate(${pan.x}px, ${pan.y}px) scale(${zoomLevel})`
                      : null
                  }"
                  @mousedown.prevent="startDrag"
                  @mousemove.prevent="onDrag"
                  @mouseup.prevent="endDrag"
                  @mouseleave.prevent="endDrag"
                  @wheel="handleWheelZoom"
                />
              </div>
              <button v-if="modalIndex < imagesOnly.length - 1" class="nav-arrow right" @click="showNextImage">
                <span aria-hidden="true">›</span>
              </button>
              </div>
              <div class="side-panel">
                <div class="original-box">
                  <div class="d-flex align-items-center justify-content-between mb-2">
                    <h6 class="mb-0">Originale</h6>
                    <small class="text-muted text-truncate" v-if="originalImage.path">{{ originalImage.name }}</small>
                    <small class="text-muted" v-else-if="originalImage.status">{{ originalImage.status }}</small>
                    <small class="text-muted" v-else>Seleziona cartella originali</small>
                  </div>
                  <div class="original-preview">
                    <template v-if="originalImage.src">
                      <div class="pane-body">
                        <img
                          :src="originalImage.src"
                          :alt="originalImage.name"
                          :class="{ zoomed: isZoomed }"
                          :style="{
                            transform: zoomLevel > 1
                              ? `translate(${pan.x}px, ${pan.y}px) scale(${zoomLevel})`
                              : null
                          }"
                          @mousedown.prevent="startDrag"
                          @mousemove.prevent="onDrag"
                          @mouseup.prevent="endDrag"
                    @mouseleave.prevent="endDrag"
                    @wheel="handleWheelZoom"
                  />
                </div>
              </template>
              <div class="alert alert-light py-2 small mb-0" v-else>
                {{ originalImage.status || 'Nessuna immagine originale trovata per il confronto.' }}
              </div>
            </div>
                </div>

                <div class="meta-area" v-if="modalMetadata">
                  <div class="d-flex align-items-center justify-content-between mb-2">
                    <h6 class="mb-0">Metadati</h6>
                    <button class="btn btn-sm btn-outline-secondary" @click="showMetadata = !showMetadata">
                      {{ showMetadata ? 'Nascondi' : 'Mostra' }}
                    </button>
                  </div>
                  <pre class="metadata-pre" v-if="showMetadata">{{ formatMetadata(modalMetadata) }}</pre>
                </div>
              </div>
              <div v-if="zoomLoading" class="zoom-loading-overlay">
                <div class="spinner-border text-light" role="status"></div>
                <div class="small text-light mt-2">Preparazione zoom...</div>
              </div>
            </div>
            <div v-if="showFolderMetadata" class="card folder-meta-modal mt-3">
              <div class="card-body p-3">
                <div class="d-flex align-items-center justify-content-between gap-2 flex-wrap mb-2">
                  <h6 class="mb-0">Metadati cartella</h6>
                  <small class="text-muted">{{ folderMetadataStatus || 'Dettagli cartella' }}</small>
                </div>
                <dl v-if="folderDocumentEntries.length" class="row folder-meta-list mb-0">
                  <template v-for="entry in folderDocumentEntries" :key="entry.key">
                    <dt class="col-sm-4 text-muted small text-uppercase">{{ entry.label }}</dt>
                    <dd class="col-sm-8 mb-2">{{ entry.value || '—' }}</dd>
                  </template>
                </dl>
                <div v-else class="alert alert-light py-2 mb-0 small">
                  Metadati non disponibili per questa cartella.
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <div class="me-auto text-muted small" v-if="imagesOnly.length > 1">
              {{ modalIndex + 1 }} / {{ imagesOnly.length }}
            </div>
            <button
              type="button"
              class="btn btn-outline-secondary"
              :disabled="!folderDocument && !folderMetadataStatus"
              @click="showFolderMetadata = !showFolderMetadata"
            >
              {{ showFolderMetadata ? 'Nascondi metadati' : 'Metadati cartella' }}
            </button>
            <button type="button" class="btn btn-secondary" @click="closeImageModal">Chiudi</button>
          </div>
        </div>
      </div>
    </div>
  <!-- </div> -->
  <div class="modal-backdrop fade show" v-if="fullImage.src"></div>
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
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue';

// Riferimenti reattivi per stato dell'interfaccia
const selectedFolder = ref(null)
const selectedOutput = ref(null)
const optimizeImages = ref(true)
const previewMode = ref(false)
const aggressivity = ref('standard')
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
const currentThumbnail = ref('')

// Path del file CSV per l’anteprima
const csvMappingFile = ref('')

// Stato per il modal di risultato
const showResultModal = ref(false)
const resultSuccess = ref(false)
const resultMessage = ref('')
const closeResultModal = () => { showResultModal.value = false }

// Stato per preview mode
const previewFileSizes = ref(null)
const previewCleanupTimer = ref(null)

// Stato explorer output
const lastOutputDir = ref('')
const organizedRoot = ref('')
const thumbnailsRoot = ref('')
const currentExplorerDir = ref('')
const explorerEntries = ref([])
const explorerBreadcrumbs = ref([])
const explorerLoading = ref(false)
const explorerError = ref('')
const thumbnailCache = ref({})
const folderMetadata = ref(null)
const folderMetadataStatus = ref('')
const thumbLoading = ref(false)
const placeholderThumb = 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22240%22 height=%22160%22 viewBox=%220 0 240 160%22%3E%3Cdefs%3E%3ClinearGradient id=%22g%22 x1=%220%25%22 y1=%220%25%22 x2=%22100%25%22 y2=%220%25%22%3E%3Cstop offset=%220%25%22 stop-color=%22%23eef1f6%22/%3E%3Cstop offset=%2250%25%22 stop-color=%22%23f6f8fb%22/%3E%3Cstop offset=%22100%25%22 stop-color=%22%23eef1f6%22/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width=%22240%22 height=%22160%22 fill=%22url(%23g)%22/%3E%3Crect x=%2236%22 y=%2232%22 width=%22168%22 height=%2296%22 rx=%2212%22 fill=%22%23e3e7ef%22/%3E%3C/svg%3E'
const fullImage = reactive({ src: '', name: '', path: '' })
const modalIndex = ref(-1)
const modalMetadata = ref(null)
const originalRoot = ref('')
const originalImage = reactive({ src: '', name: '', path: '', status: '' })
const isZoomed = ref(false)
const zoomLevel = ref(1)
const zoomLoading = ref(false)
const showFolderMetadata = ref(false)
const showMetadata = ref(false)
const pan = reactive({ x: 0, y: 0 })
const dragState = reactive({ dragging: false, startX: 0, startY: 0, originX: 0, originY: 0 })
let zoomLoaderTimer = null

// Computed per explorer
const explorerRoot = computed(() => organizedRoot.value || lastOutputDir.value)
const foldersOnly = computed(() => explorerEntries.value.filter(e => e.type === 'directory'))
const imagesOnly = computed(() => explorerEntries.value.filter(e => e.isImage))
const currentModalImage = computed(() => {
  if (modalIndex.value < 0 || modalIndex.value >= imagesOnly.value.length) return null
  return imagesOnly.value[modalIndex.value]
})
const folderDocument = computed(() => folderMetadata.value?.document || null)
const formatDocKey = (key = '') => key
  .replace(/_/g, ' ')
  .replace(/\b\w/g, c => c.toUpperCase())
const folderDocumentEntries = computed(() => {
  if (!folderDocument.value) return []
  return Object.entries(folderDocument.value).map(([key, value]) => ({
    key,
    label: formatDocKey(key),
    value
  }))
})

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

// Utility semplice per concatenare path cross-platform
const joinPath = (base, segment) => {
  if (!base) return segment
  if (base.endsWith('/') || base.endsWith('\\')) return `${base}${segment}`
  return `${base}/${segment}`
}

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

    // Update current thumbnail for live preview
    if (progress.currentThumbnail) {
      currentThumbnail.value = progress.currentThumbnail
    }
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

// Gestione navigazione tastiera per la modal immagini
const handleKeyNavigation = async (event) => {
  if (modalIndex.value < 0) return
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    await showPrevImage()
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    await showNextImage()
  } else if (event.key === 'Escape') {
    event.preventDefault()
    closeImageModal()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyNavigation)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeyNavigation)
  clearZoomLoader()
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

// Aggiorna cache thumbnails ogni volta che cambia la lista di file
watch(explorerEntries, async (entries) => {
  if (!entries || !entries.length) return
  thumbLoading.value = true
  const images = entries.filter(e => e.isImage)
  const updatedCache = { ...thumbnailCache.value }

  try {
    await Promise.all(images.map(async img => {
      const key = img.thumbnailPath || img.path
      if (!key || updatedCache[key]) return

      try {
        const dataUrl = await window.electronAPI.readThumbnailAsDataUrl(key)
        updatedCache[key] = dataUrl || placeholderThumb
      } catch (err) {
        console.error('Errore caricando thumbnail', err)
        updatedCache[key] = placeholderThumb
      }
    }))
    thumbnailCache.value = updatedCache
  } finally {
    thumbLoading.value = false
  }
}, { deep: true })

function openFfmpegGuide() {
  window.electronAPI.openExternal('https://www.wikihow.it/Installare-FFmpeg-in-Windows')
}

const loadFolderMetadata = async (dir) => {
  folderMetadata.value = null
  folderMetadataStatus.value = ''
  if (!dir) return

  const candidates = ['medatata.json', 'metadata.json']
  for (const candidate of candidates) {
    const metaPath = joinPath(dir, candidate)
    try {
      const data = await window.electronAPI.readJsonFile(metaPath)
      if (data) {
        folderMetadata.value = data
        folderMetadataStatus.value = `Fonte: ${candidate}`
        return
      }
    } catch (err) {
      const isMissing = err?.message?.toLowerCase().includes('enoent') || err?.code === 'ENOENT'
      if (!isMissing) {
        folderMetadataStatus.value = 'Errore caricando metadati cartella'
        console.warn('Errore metadati cartella', err)
        return
      }
    }
  }
  folderMetadataStatus.value = 'Metadati cartella non disponibili'
}

// Gestione explorer output elaborati
const loadExplorer = async (dirToLoad, allowFallback = true) => {
  if (!dirToLoad) return
  explorerLoading.value = true
  explorerError.value = ''
  showFolderMetadata.value = false

  try {
    const res = await window.electronAPI.listEntriesDetailed(
      dirToLoad,
      organizedRoot.value,
      thumbnailsRoot.value
    )
    if (res.error) throw new Error(res.error)

    explorerEntries.value = res.entries || []
    explorerBreadcrumbs.value = res.breadcrumbs || []
    currentExplorerDir.value = dirToLoad
    await loadFolderMetadata(dirToLoad)
  } catch (err) {
    const isMissingOrganized = err?.message?.includes('ENOENT') && dirToLoad.includes('organized')
    if (allowFallback && lastOutputDir.value && dirToLoad !== lastOutputDir.value) {
      await loadExplorer(lastOutputDir.value, false)
      return
    }
    if (isMissingOrganized && lastOutputDir.value) {
      explorerError.value = ''
    } else {
      explorerError.value = err?.message || 'Impossibile leggere la cartella selezionata.'
    }
    console.warn('Errore caricando contenuto cartella', err?.message || err)
    explorerEntries.value = []
  } finally {
    explorerLoading.value = false
  }
}

const initializeExplorer = async (baseDir, organizedDir = null, thumbsDir = null) => {
  if (!baseDir) return
  lastOutputDir.value = baseDir
  organizedRoot.value = organizedDir || joinPath(baseDir, 'organized')
  thumbnailsRoot.value = thumbsDir || joinPath(baseDir, 'organized_thumbnails')

  const initialDir = organizedDir || organizedRoot.value || baseDir
  await loadExplorer(initialDir, true)
}

const refreshExplorer = async () => {
  const target = currentExplorerDir.value || organizedRoot.value || lastOutputDir.value
  if (target) await loadExplorer(target)
}

const openFolder = async (folderPath) => {
  await loadExplorer(folderPath)
}

const goToBreadcrumb = async (path) => {
  await loadExplorer(path)
}

const pickProcessedFolder = async () => {
  const dir = await window.electronAPI.selectOutputFolder()
  if (dir) {
    await initializeExplorer(dir)
  }
}

const selectOriginalRoot = async () => {
  const dir = await window.electronAPI.selectFolder()
  if (dir) {
    originalRoot.value = dir
  }
}

const openImageModal = async (img) => {
  try {
    const dataUrl = await window.electronAPI.readImageAsDataUrl(img.path)
    if (dataUrl) {
      fullImage.src = dataUrl
      fullImage.name = img.name
      fullImage.path = img.path
      modalIndex.value = imagesOnly.value.findIndex(i => i.path === img.path)
      isZoomed.value = false
      zoomLevel.value = 1
      pan.x = 0
      pan.y = 0
      clearZoomLoader()
      showFolderMetadata.value = false
      showMetadata.value = false
      await loadMetadataForImage(img)
      await loadOriginalForImage(img)
    } else {
      explorerError.value = 'Impossibile aprire questa immagine.'
    }
  } catch (err) {
    explorerError.value = err?.message || 'Impossibile aprire questa immagine.'
  }
}

const closeImageModal = () => {
  fullImage.src = ''
  fullImage.name = ''
  fullImage.path = ''
  modalIndex.value = -1
  modalMetadata.value = null
  isZoomed.value = false
  zoomLevel.value = 1
  pan.x = 0
  pan.y = 0
  clearZoomLoader()
  showFolderMetadata.value = false
}

const loadMetadataForImage = async (img) => {
  if (!img || !img.path) {
    modalMetadata.value = null
    return
  }
  const base = img.path.replace(/\.[^.]+$/, '')
  const jsonPath = `${base}.json`
  try {
    const data = await window.electronAPI.readJsonFile(jsonPath)
    modalMetadata.value = data || null
  } catch (err) {
    console.warn('Errore leggendo metadata json', err)
    modalMetadata.value = null
  }
}

const showPrevImage = async () => {
  if (modalIndex.value <= 0) return
  modalIndex.value -= 1
  const img = currentModalImage.value
  if (img) {
    await openImageModal(img)
  }
}

const showNextImage = async () => {
  if (modalIndex.value < 0 || modalIndex.value >= imagesOnly.value.length - 1) return
  modalIndex.value += 1
  const img = currentModalImage.value
  if (img) {
    await openImageModal(img)
  }
}

const formatMetadata = (data) => {
  if (!data) return ''
  try {
    return JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}

const loadOriginalForImage = async (img) => {
  originalImage.src = ''
  originalImage.name = ''
  originalImage.path = ''
  originalImage.status = ''
  if (!originalRoot.value || !img?.path) return

  originalImage.status = 'Caricamento originale...'
  try {
    const match = await window.electronAPI.findOriginalMatch(img.path, originalRoot.value)
    if (!match) {
      originalImage.status = 'Non trovato nella cartella originale'
      return
    }
    const dataUrl = await window.electronAPI.readImageAsDataUrl(match)
    if (!dataUrl) {
      originalImage.status = 'Impossibile leggere immagine originale'
      return
    }
    originalImage.src = dataUrl
    originalImage.name = pathBasename(match)
    originalImage.path = match
    originalImage.status = ''
  } catch (err) {
    console.warn('Errore caricando originale', err)
    originalImage.status = err?.message || 'Errore caricando originale'
  }
}

const pathBasename = (fullPath) => {
  if (!fullPath) return ''
  return fullPath.split(/[\\/]/).pop()
}

const clearZoomLoader = () => {
  zoomLoading.value = false
  if (zoomLoaderTimer) {
    clearTimeout(zoomLoaderTimer)
    zoomLoaderTimer = null
  }
}

const startZoomLoader = () => {
  zoomLoading.value = true
  if (zoomLoaderTimer) clearTimeout(zoomLoaderTimer)
  zoomLoaderTimer = setTimeout(() => {
    clearZoomLoader()
  }, 1200)
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      clearZoomLoader()
    })
  })
}

const toggleZoom = () => {
  if (zoomLevel.value > 1) {
    zoomLevel.value = 1
    isZoomed.value = false
    pan.x = 0
    pan.y = 0
    clearZoomLoader()
  } else {
    startZoomLoader()
    zoomLevel.value = 2
    isZoomed.value = true
  }
}

const startDrag = (event) => {
  if (zoomLevel.value <= 1) return
  dragState.dragging = true
  dragState.startX = event.clientX
  dragState.startY = event.clientY
  dragState.originX = pan.x
  dragState.originY = pan.y
}

const onDrag = (event) => {
  if (!dragState.dragging || zoomLevel.value <= 1) return
  const dx = event.clientX - dragState.startX
  const dy = event.clientY - dragState.startY
  pan.x = dragState.originX + dx
  pan.y = dragState.originY + dy
}

const endDrag = () => {
  dragState.dragging = false
}

const handleWheelZoom = (event) => {
  if (!fullImage.src) return
  event.preventDefault()
  const delta = event.deltaY < 0 ? 0.2 : -0.2
  const next = Math.min(4, Math.max(1, zoomLevel.value + delta))
  if (next > zoomLevel.value && next > 1) {
    startZoomLoader()
  }
  zoomLevel.value = next
  isZoomed.value = zoomLevel.value > 1
  if (zoomLevel.value === 1) {
    pan.x = 0
    pan.y = 0
    clearZoomLoader()
  }
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
  if (previewCleanupTimer.value) {
    clearTimeout(previewCleanupTimer.value)
    previewCleanupTimer.value = null
  }

  processing.value = true
  loadingText.value = 'Conteggio cartelle in corso...'
  progressText.value = ''
  csvText.value = ''
  percent.value = 0
  foldersStatus.value = []
  showFolderProgress.value = false
  currentThumbnail.value = '' // Clear previous thumbnail
  
  const finalMap = unflattenMap(resolvedFlat)
  const res = await window.electronAPI.processImages(
    selectedFolder.value,
    selectedOutput.value,
    maxCsvLine.value,
    crop.value,
    finalMap,
    optimizeVideos.value,
    optimizeImages.value,
    previewMode.value,
    aggressivity.value
  )

  processing.value = false
  loadingText.value = ''
  showFolderProgress.value = false

  // Handle preview mode results
  if (previewMode.value && res.success && res.previewFileSizes && res.previewFileSizes.length > 0) {
    previewFileSizes.value = res.previewFileSizes
    const totalSize = res.previewFileSizes.reduce((sum, f) => sum + f.size, 0)
    const avgSize = totalSize / res.previewFileSizes.length

    // Sort files by size for better readability
    const sortedFiles = [...res.previewFileSizes].sort((a, b) => a.size - b.size)

    resultMessage.value = `ANTEPRIMA COMPLETATA\n\n` +
      `File elaborati: ${res.previewFileSizes.length}\n\n` +
      `Dimensioni file:\n` +
      sortedFiles.map(f => `  ${f.name}: ${(f.size / 1024).toFixed(1)} KB`).join('\n') +
      `\n\n` +
      `STATISTICHE:\n` +
      `  Dimensione minima: ${(sortedFiles[0].size / 1024).toFixed(1)} KB\n` +
      `  Dimensione massima: ${(sortedFiles[sortedFiles.length - 1].size / 1024).toFixed(1)} KB\n` +
      `  Dimensione media: ${(avgSize / 1024).toFixed(1)} KB\n` +
      `  Dimensione totale: ${(totalSize / 1024).toFixed(1)} KB\n\n` +
      'I file verranno automaticamente eliminati tra 60 secondi.'

    // Auto-cleanup after 60 seconds
    previewCleanupTimer.value = setTimeout(async () => {
      await window.electronAPI.cleanupPreview(res.outputDir)
      previewFileSizes.value = null
      resultMessage.value += '\n\nFile di anteprima eliminati.'
    }, 60000)
  } else if (previewMode.value && res.success && (!res.previewFileSizes || res.previewFileSizes.length === 0)) {
    resultMessage.value = 'Anteprima completata, ma nessuna immagine trovata. Verifica che la cartella contenga file immagine (TIF, JPG, PNG).'
  } else {
    resultMessage.value = res.success ? 'Processamento completato con successo!' : 'Errore: ' + (res.error || '')
  }

  if (res.success) {
    const outputDir = res.outputDir || selectedOutput.value || selectedFolder.value
    // Imposta automaticamente la cartella originale per il confronto
    originalRoot.value = selectedFolder.value || originalRoot.value
    await initializeExplorer(outputDir, res.organizedDir, res.organizedThumbsDir)
  }

  resultSuccess.value = res.success
  showResultModal.value = true
}
const stopProcess = () => {
  if (processing.value) window.electronAPI.stopProcessing()
}
</script>

<style scoped>
.result-message {
  white-space: pre-line;
  margin-bottom: 0;
}

.folder-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.45rem 0.75rem;
  background: #f4f6f9;
  border: 1px solid #dee2e6;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  max-width: 240px;
}

.folder-chip:hover {
  background: #e9f1ff;
  border-color: #bcd0ff;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem;
}

.image-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 0.75rem;
  background: #ffffff;
  box-shadow: 0 2px 6px rgba(0,0,0,0.04);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}

.image-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 14px rgba(0,0,0,0.08);
}

.folder-meta-card {
  border: 1px solid #e2e8f0;
}

.folder-meta-list dt {
  font-weight: 600;
  letter-spacing: 0.4px;
}

.folder-meta-list dd {
  word-break: break-word;
}

.thumb-wrapper {
  background: linear-gradient(135deg, #f5f7fb, #eef2f7);
  border-radius: 10px;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 140px;
  position: relative;
}

.thumb-wrapper img {
  max-height: 120px;
  max-width: 100%;
  object-fit: contain;
  border-radius: 8px;
  border: 1px solid #e0e3e8;
}

.full-image-modal .modal-dialog {
  max-width: 90vw;
}

.full-image-modal .modal-body {
  background: #0f172a;
}

.full-image {
  max-height: 70vh;
  max-width: 100%;
  object-fit: contain;
  transition: transform 0.15s ease;
  will-change: transform;
}

.full-image.zoomed {
  cursor: grab;
}

.full-image.zoomed:active {
  cursor: grabbing;
}

.thumb-loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.75);
  border-radius: 12px;
  z-index: 2;
}

.modal-body-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.5rem;
  align-items: center;
  position: relative;
  --pane-height: 70vh;
}

.image-area {
  position: relative;
  min-width: 0;
  text-align: center;
  overflow: hidden;
  background: #0b1224;
  border-radius: 12px;
  padding: 0.75rem;
  min-height: var(--pane-height);
  display: flex;
  align-items: center;
  justify-content: center;
}

.pane-header {
  position: absolute;
  top: 10px;
  left: 12px;
  z-index: 7;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.6rem;
  background: rgba(15, 23, 42, 0.85);
  color: #e2e8f0;
  border-radius: 10px;
  border: 1px solid #1e293b;
}

.pane-title {
  font-weight: 700;
  letter-spacing: 0.3px;
}

.nav-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.4);
  background: rgba(37, 99, 235, 0.9);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 5;
  box-shadow: 0 6px 18px rgba(0,0,0,0.25);
}

.nav-arrow.left { left: 10px; }
.nav-arrow.right { right: 10px; }

.nav-arrow:hover {
  background: rgba(59, 130, 246, 0.85);
}

.zoom-toggle {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 6;
  border: none;
  padding: 0.45rem 0.75rem;
  border-radius: 10px;
  background: rgba(59, 130, 246, 0.95);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}

.zoom-toggle:hover {
  background: rgba(37, 99, 235, 0.95);
}

.zoom-loading-overlay {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 0.5rem;
  border-radius: 12px;
  z-index: 12;
  pointer-events: all;
  cursor: progress;
}

.zoom-loading-overlay .spinner-border {
  width: 2.75rem;
  height: 2.75rem;
}

.side-panel {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.75rem;
  min-width: 0;
  min-height: var(--pane-height);
}

.original-box {
  background: #0b1224;
  border-radius: 12px;
  padding: 0.75rem;
  border: 1px solid #1e293b;
  min-height: calc(var(--pane-height) - 1rem);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.original-preview {
  background: #0f172a;
  border-radius: 10px;
  padding: 0.5rem;
  text-align: center;
  border: 1px solid #1e293b;
  overflow: hidden;
  flex: 1;
  height: var(--pane-height);
  display: flex;
  align-items: center;
  justify-content: center;
}

.pane-body {
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 12px;
  padding: 0.25rem;
  width: 100%;
  height: var(--pane-height);
  min-height: var(--pane-height);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.pane-body img,
.original-preview img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 8px;
  background: #0b1224;
  transition: transform 0.15s ease;
  will-change: transform;
}

.meta-area {
  background: #fff;
  border-radius: 12px;
  padding: 1rem;
  border: 1px solid #e5e7eb;
  max-height: calc(var(--pane-height) / 2);
  overflow: auto;
}

.folder-meta-modal {
  border: 1px solid #e2e8f0;
}

.metadata-pre {
  white-space: pre-wrap;
  background: #f8fafc;
  border-radius: 8px;
  padding: 0.75rem;
  border: 1px solid #e2e8f0;
  font-size: 0.85rem;
  max-height: 60vh;
  overflow: auto;
}

@media (max-width: 992px) {
  .modal-body-grid {
    grid-template-columns: 1fr;
  }
}
</style>
