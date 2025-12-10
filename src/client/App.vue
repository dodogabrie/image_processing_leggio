<template>
  <div class="container py-4">
    <h1 class="mb-4">Elaborazione immagini per Leggio</h1>

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
</script>
