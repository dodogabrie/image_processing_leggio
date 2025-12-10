<template>
  <div>
    <!-- Warning for unmapped columns -->
    <div v-if="csvMapping.missingCsvColumns.value.length" class="alert alert-warning mt-4">
      <strong>Attenzione:</strong> le seguenti colonne non saranno importate perché non è stato possibile associarle a un campo del database:
      <ul class="mb-0">
        <li v-for="col in csvMapping.missingCsvColumns.value" :key="col">{{ col }}</li>
      </ul>
      Nel caso le colonne elencate presentino campi rilevanti, contattare l'assistenza tecnica.
    </div>

    <!-- Collapsible mapping panel -->
    <div v-if="csvMapping.showMapping.value" class="mt-4">
      <!-- Custom CSV Map Loader -->
      <CustomCsvMapLoader @mapChanged="handleCustomMapChange" class="mb-3" />

      <!-- CSV Mapping Display Component -->
      <CsvMappingDisplay
        :resolved-flat="csvMapping.resolvedFlat"
        :detected-languages="csvMapping.detectedLanguages"
        :get-field-description="csvMapping.getFieldDescription"
        v-model:expanded="csvMapping.mappingExpanded.value"
      />
    </div>

    <!-- CSV preview section -->
    <div v-if="csvMapping.csvMappingFile.value" class="mt-4">
      <div class="card">
        <div class="card-body p-3">
          <CsvPreview :csvPath="csvMapping.csvMappingFile.value" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, watch } from 'vue'
import CustomCsvMapLoader from './CustomCsvMapLoader.vue'
import CsvMappingDisplay from './CsvMappingDisplay.vue'
import CsvPreview from './CsvPreview.vue'

const csvMapping = inject('csvMapping')
const processing = inject('processing')

// Watch for selected folder changes to load CSV
// IMPORTANT: Watch the .value of the ref, not the ref itself
watch(() => processing.selectedFolder.value, async (folder) => {
  if (!folder) {
    csvMapping.csvMappingFile.value = ''
    csvMapping.showMapping.value = false
    return
  }

  await csvMapping.loadDatabaseBridge()

  const hasCsv = await window.electronAPI.hasCsvInFolder(folder)
  processing.showCsvInput.value = hasCsv
  if (!hasCsv) {
    csvMapping.showMapping.value = false
    csvMapping.csvMappingFile.value = ''
    return
  }

  const files = await window.electronAPI.readDir(folder)
  const csvFile = files.find(f => f.toLowerCase().endsWith('.csv'))
  if (!csvFile) {
    csvMapping.showMapping.value = false
    csvMapping.csvMappingFile.value = ''
    return
  }

  csvMapping.csvMappingFile.value = `${folder}/${csvFile}`
  csvMapping.csvHeaders.value = await window.electronAPI.getCsvHeaders(`${folder}/${csvFile}`)

  // Parse headers and load mapping
  await csvMapping.loadCsvMapping(csvMapping.csvHeaders.value)
  csvMapping.showMapping.value = true
})

// Handle custom map change
async function handleCustomMapChange() {
  if (csvMapping.csvHeaders.value.length > 0) {
    await csvMapping.loadCsvMapping(csvMapping.csvHeaders.value)
  }
}
</script>
