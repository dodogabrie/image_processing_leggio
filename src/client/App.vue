<template>
  <div class="container py-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
      <h1 class="mb-0">Elaborazione immagini per Leggio</h1>
      <button
        class="btn btn-sm btn-outline-secondary"
        @click="downloadLog"
        title="Download log file"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"/>
          <path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z"/>
        </svg>
        Log
      </button>
    </div>

    <!-- Processing section -->
    <ProcessingForm />
    <ProcessingProgress />

    <!-- CSV section -->
    <CsvSection />

    <!-- Explorer section -->
    <FileExplorer />

    <!-- Modals -->
    <ResultModal />
    <ImageModal />
  </div>
</template>

<script setup>
import { provide } from 'vue'

// Component imports
import ProcessingForm from './components/processing/ProcessingForm.vue'
import ProcessingProgress from './components/processing/ProcessingProgress.vue'
import ResultModal from './components/processing/ResultModal.vue'
import CsvSection from './components/csv/CsvSection.vue'
import FileExplorer from './components/explorer/FileExplorer.vue'
import ImageModal from './components/explorer/ImageModal.vue'

// Composable imports
import { useCsvMapping } from './composables/useCsvMapping.js'
import { useProcessing } from './composables/useProcessing.js'
import { useExplorer } from './composables/useExplorer.js'
import { useImageModal } from './composables/useImageModal.js'
import { useKeyboardNavigation } from './composables/useKeyboardNavigation.js'

// Setup composables (singleton instances)
const csvMapping = useCsvMapping()
const processing = useProcessing(csvMapping)
const explorer = useExplorer()
const imageModal = useImageModal(explorer)
useKeyboardNavigation(imageModal)

// Provide composables to all child components
provide('csvMapping', csvMapping)
provide('processing', processing)
provide('explorer', explorer)
provide('imageModal', imageModal)

// Log download function
async function downloadLog() {
  try {
    const result = await window.electronAPI.saveLogAs()
    if (result.success) {
      console.log('Log saved to:', result.savedTo)
    } else if (result.error) {
      console.error('Failed to save log:', result.error)
      alert('Failed to save log: ' + result.error)
    }
  } catch (err) {
    console.error('Log download error:', err)
    alert('Error downloading log file')
  }
}
</script>
