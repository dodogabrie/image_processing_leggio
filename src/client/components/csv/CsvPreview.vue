<template>
  <div class="card mt-3">
    <div class="card-header p-0">
      <button
        class="btn btn-link w-100 text-start py-2 px-3"
        @click="expanded = !expanded"
      >
        <strong>Anteprima CSV/XLSX (prime {{ maxRows }} righe)</strong>
        <span class="float-end">{{ expanded ? '▲' : '▼' }}</span>
      </button>
    </div>
    <div v-show="expanded" class="card-body p-0">
      <div class="table-responsive" style="max-height: 400px; overflow-y: auto;">
        <table class="table table-sm table-bordered mb-0">
          <thead class="table-light sticky-top">
            <tr>
              <th v-for="header in headers" :key="header" class="text-nowrap small">
                {{ header }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in previewData" :key="idx">
              <td v-for="header in headers" :key="header" class="small">
                <span 
                  v-if="row[header] && row[header].length > maxCellLength"
                  :title="row[header]"
                  class="text-truncate d-inline-block"
                  style="max-width: 150px;"
                >
                  {{ row[header] }}
                </span>
                <span v-else>{{ row[header] || '' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card-footer text-muted small">
        Mostrando {{ previewData.length }} di {{ totalRows }} righe totali
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch } from 'vue'

export default {
  name: 'CsvPreview',
  props: {
    csvPath: {
      type: String,
      required: true
    },
    maxRows: {
      type: Number,
      default: 10
    },
    maxCellLength: {
      type: Number,
      default: 50
    }
  },
  setup(props) {
    const expanded = ref(false)
    const headers = ref([])
    const previewData = ref([])
    const totalRows = ref(0)
    const loading = ref(false)

    const loadCsvPreview = async () => {
      if (!props.csvPath) return
      
      loading.value = true
      try {
        // Carica headers
        headers.value = await window.electronAPI.getCsvHeaders(props.csvPath)
        
        // Carica preview dati
        const result = await window.electronAPI.getCsvPreview(props.csvPath, props.maxRows)
        previewData.value = result.data || []
        totalRows.value = result.totalRows || 0
      } catch (error) {
        console.error('Error loading CSV preview:', error)
        headers.value = []
        previewData.value = []
        totalRows.value = 0
      } finally {
        loading.value = false
      }
    }

    // Carica quando cambia il path del CSV
    watch(() => props.csvPath, loadCsvPreview, { immediate: true })

    return {
      expanded,
      headers,
      previewData,
      totalRows,
      loading
    }
  }
}
</script>

<style scoped>
.table th {
  background-color: var(--bs-light);
  position: sticky;
  top: 0;
  z-index: 10;
}

.text-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
