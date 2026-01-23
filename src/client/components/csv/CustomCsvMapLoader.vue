<template>
  <div class="custom-csv-map-loader">
    <div class="alert alert-primary d-flex align-items-center" role="alert">
      <i class="bi bi-info-circle-fill me-2"></i>
      <div class="flex-grow-1">
        <strong>Mappa CSV Personalizzata</strong>
        <p class="mb-0 small">
          Carica un file JSON personalizzato per modificare la mappatura dei campi CSV.
          <span v-if="hasCustomMap" class="text-success fw-bold">
            ✓ Mappa personalizzata attiva
          </span>
          <span v-else class="text-muted">
            (Attualmente in uso: mappa di default)
          </span>
        </p>
      </div>
      <div class="ms-3">
        <input
          ref="fileInput"
          type="file"
          accept=".json"
          @change="handleFileSelect"
          class="d-none"
        />
        <button
          class="btn btn-outline-primary btn-sm me-2"
          @click="$refs.fileInput.click()"
          :disabled="loading"
        >
          <i class="bi bi-upload me-1"></i>
          Carica Mappa
        </button>
        <button
          v-if="hasCustomMap"
          class="btn btn-outline-danger btn-sm me-2"
          @click="removeCustomMap"
          :disabled="loading"
        >
          <i class="bi bi-trash me-1"></i>
          Rimuovi
        </button>
        <button
          class="btn btn-outline-secondary btn-sm"
          @click="downloadCurrentMap"
          :disabled="loading"
        >
          <i class="bi bi-download me-1"></i>
          Scarica Attuale
        </button>
      </div>
    </div>

    <!-- Loading indicator -->
    <div v-if="loading" class="text-center py-2">
      <div class="spinner-border spinner-border-sm text-primary" role="status">
        <span class="visually-hidden">Caricamento...</span>
      </div>
      <span class="ms-2">{{ loadingMessage }}</span>
    </div>

    <!-- Success/Error messages -->
    <div v-if="message" class="alert mt-2" :class="messageType === 'success' ? 'alert-success' : 'alert-danger'">
      <i class="bi" :class="messageType === 'success' ? 'bi-check-circle' : 'bi-exclamation-circle'"></i>
      {{ message }}
    </div>

    <!-- Preview della mappa caricata -->
    <div v-if="hasCustomMap && previewMap" class="mt-3">
      <div class="card">
        <div class="card-header bg-light">
          <h6 class="mb-0">
            <i class="bi bi-eye me-1"></i>
            Anteprima Mappa Personalizzata
          </h6>
        </div>
        <div class="card-body">
          <div class="row">
            <div class="col-md-6" v-for="section in ['document', 'image']" :key="section">
              <h6 class="text-capitalize border-bottom pb-1">{{ section }}</h6>
              <div v-if="!Object.keys(previewMap[section] || {}).length" class="text-muted fst-italic">
                Nessuna mappatura configurata
              </div>
              <div v-else class="small">
                <div v-for="(value, key) in previewMap[section]" :key="key" class="mb-1">
                  <span class="fw-bold text-primary">{{ key }}:</span>
                  <span class="ms-1 text-secondary">
                    {{ typeof value === 'object' ? JSON.stringify(value) : value }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, defineEmits, defineExpose } from 'vue'

// Emits
const emit = defineEmits(['mapChanged'])

// Reactive state
const hasCustomMap = ref(false)
const loading = ref(false)
const loadingMessage = ref('')
const message = ref('')
const messageType = ref('success')
const previewMap = ref(null)

// Check if custom map exists on mount
onMounted(async () => {
  await checkCustomMapExists()
})

// Check if custom_csv_map.json exists
async function checkCustomMapExists() {
  try {
    const customMap = await window.electronAPI.readPublicFile('custom_csv_map.json')
    if (customMap) {
      hasCustomMap.value = true
      previewMap.value = JSON.parse(customMap)
    }
  } catch (error) {
    hasCustomMap.value = false
    previewMap.value = null
  }
}

// Handle file selection
async function handleFileSelect(event) {
  const file = event.target.files[0]
  if (!file) return

  if (!file.name.endsWith('.json')) {
    showMessage('Seleziona un file JSON valido', 'error')
    return
  }

  loading.value = true
  loadingMessage.value = 'Caricamento mappa personalizzata...'

  try {
    const fileContent = await readFileAsText(file)
    const jsonData = JSON.parse(fileContent)

    // Validate JSON structure
    if (!isValidCsvMap(jsonData)) {
      throw new Error('Struttura JSON non valida. Deve contenere oggetti "document" e "image".')
    }

    // Save as custom_csv_map.json
    await window.electronAPI.writePublicFile('custom_csv_map.json', JSON.stringify(jsonData, null, 2))

    hasCustomMap.value = true
    previewMap.value = jsonData
    showMessage('Mappa personalizzata caricata con successo!', 'success')
    
    // Emit event to parent component
    emit('mapChanged', jsonData)

  } catch (error) {
    showMessage(`Errore durante il caricamento: ${error.message}`, 'error')
  } finally {
    loading.value = false
    // Reset file input
    event.target.value = ''
  }
}

// Remove custom map
async function removeCustomMap() {
  if (!confirm('Sei sicuro di voler rimuovere la mappa personalizzata? Verrà utilizzata la mappa di default.')) {
    return
  }

  loading.value = true
  loadingMessage.value = 'Rimozione mappa personalizzata...'

  try {
    await window.electronAPI.deletePublicFile('custom_csv_map.json')
    hasCustomMap.value = false
    previewMap.value = null
    showMessage('Mappa personalizzata rimossa. Ripristinata mappa di default.', 'success')
    
    // Emit event to parent component
    emit('mapChanged', null)

  } catch (error) {
    showMessage(`Errore durante la rimozione: ${error.message}`, 'error')
  } finally {
    loading.value = false
  }
}

// Download current map
async function downloadCurrentMap() {
  loading.value = true
  loadingMessage.value = 'Preparazione download...'

  try {
    let mapToDownload
    
    if (hasCustomMap.value) {
      // Download custom map
      mapToDownload = await window.electronAPI.readPublicFile('custom_csv_map.json')
    } else {
      // Download default map
      mapToDownload = await window.electronAPI.readPublicFile('default_csv_map.json')
    }

    // Create and trigger download
    const blob = new Blob([mapToDownload], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = hasCustomMap.value ? 'custom_csv_map.json' : 'default_csv_map.json'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    showMessage('Download completato!', 'success')

  } catch (error) {
    showMessage(`Errore durante il download: ${error.message}`, 'error')
  } finally {
    loading.value = false
  }
}

// Utility functions
function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = e => resolve(e.target.result)
    reader.onerror = reject
    reader.readAsText(file)
  })
}

function isValidCsvMap(data) {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof data.document === 'object' &&
    typeof data.image === 'object'
  )
}

function showMessage(text, type) {
  message.value = text
  messageType.value = type
  setTimeout(() => {
    message.value = ''
  }, 5000)
}

defineExpose({
  refreshCustomMap: checkCustomMapExists,
  downloadCurrentMap
})
</script>

<style scoped>
.custom-csv-map-loader {
  margin-bottom: 1rem;
}

.alert-primary {
  background-color: #e7f3ff;
  border-color: #b3d9ff;
  color: #0056b3;
}

.card-header {
  border-bottom: 1px solid #dee2e6;
}

.btn-outline-primary:hover {
  background-color: #0056b3;
  border-color: #0056b3;
}

.btn-outline-danger:hover {
  background-color: #dc3545;
  border-color: #dc3545;
}

.btn-outline-secondary:hover {
  background-color: #6c757d;
  border-color: #6c757d;
}
</style>
