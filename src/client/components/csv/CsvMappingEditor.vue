<template>
  <div class="card mt-3">
    <div class="card-header p-0">
      <button
        class="btn btn-link w-100 text-start py-2 px-3"
        @click="$emit('update:expanded', !expanded)"
      >
        <strong>Editor mappatura CSV/XLSX</strong>
        <span class="float-end">{{ expanded ? '▲' : '▼' }}</span>
      </button>
    </div>
    <div v-show="expanded" class="card-body p-3">
      <div class="alert alert-info small">
        Seleziona uno o piu' campi del database per ogni colonna del file. Il testo di aiuto
        appare al passaggio del mouse sulle opzioni e sotto la selezione attiva.
        <div class="mt-1">
          Obbligatori minimi (CSV): <strong>document.identifier</strong>, <strong>document.groupBy</strong>
        </div>
      </div>

      <div v-if="!headers.length" class="text-muted fst-italic">
        Nessuna intestazione disponibile.
      </div>

      <div v-else class="table-responsive">
        <table class="table table-sm table-bordered align-middle mb-2">
          <thead class="table-light">
            <tr>
              <th style="min-width: 200px;">Colonna CSV/XLSX</th>
              <th style="min-width: 240px;">Campo database</th>
              <th>Helper</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="header in headers" :key="header">
              <td class="small text-nowrap">{{ header }}</td>
              <td>
                <CsvFieldPicker
                  v-model="localMapping[header]"
                  :options="fieldOptions"
                />
              </td>
              <td class="small text-muted">
                <div v-if="getDescriptions(localMapping[header]).length">
                  {{ getDescriptions(localMapping[header]).join('; ') }}
                </div>
                <div v-else>—</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="d-flex flex-wrap gap-2 align-items-center mt-3">
        <button class="btn btn-primary btn-sm" @click="saveMapping" :disabled="saving">
          <span v-if="saving" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
          Salva mappa personalizzata
        </button>
        <button class="btn btn-outline-secondary btn-sm" @click="resetMapping" :disabled="saving">
          Ripristina da mappa corrente
        </button>
        <span v-if="message" class="small" :class="messageTypeClass">{{ message }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import CsvFieldPicker from './CsvFieldPicker.vue'

const props = defineProps({
  headers: {
    type: Array,
    required: true
  },
  fieldOptions: {
    type: Object,
    required: true
  },
  initialMapping: {
    type: Object,
    required: true
  },
  saveMapping: {
    type: Function,
    required: true
  },
  expanded: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:expanded'])

const localMapping = ref({})
const saving = ref(false)
const message = ref('')
const messageType = ref('success')

const descriptionByField = computed(() => {
  const out = {}
  for (const section of ['document', 'image']) {
    for (const opt of props.fieldOptions[section] || []) {
      out[`${section}.${opt.key}`] = opt.description
    }
  }
  return out
})

const messageTypeClass = computed(() => (
  messageType.value === 'success' ? 'text-success' : 'text-danger'
))

function syncLocalMapping() {
  const next = {}
  props.headers.forEach(header => {
    next[header] = props.initialMapping[header] || []
  })
  localMapping.value = next
}

function getDescriptions(fieldIds) {
  const list = Array.isArray(fieldIds) ? fieldIds : [fieldIds]
  return list.filter(Boolean).map(fieldId => descriptionByField.value[fieldId]).filter(Boolean)
}

async function saveMapping() {
  saving.value = true
  message.value = ''
  try {
    await props.saveMapping({ ...localMapping.value })
    messageType.value = 'success'
    message.value = 'Mappa personalizzata salvata.'
  } catch (error) {
    messageType.value = 'error'
    message.value = error?.message || 'Errore nel salvataggio.'
  } finally {
    saving.value = false
  }
}

function resetMapping() {
  syncLocalMapping()
  message.value = ''
}

watch(() => [props.headers, props.initialMapping], syncLocalMapping, { immediate: true })
</script>
