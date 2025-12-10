<template>
  <div class="card">
    <div class="card-header p-0">
      <button
        class="btn btn-link w-100 text-start py-2 px-3"
        @click="$emit('update:expanded', !expanded)"
      >
        <strong>Mappa campi Database - Colonne CSV</strong>
        <span class="float-end">{{ expanded ? '▲' : '▼' }}</span>
      </button>
    </div>
    <div v-show="expanded" class="card-body p-3">
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
                
                <!-- Visualizzazione lingue rilevate -->
                <div v-if="detectedLanguages[section][key] && detectedLanguages[section][key].length > 0" class="d-flex flex-wrap gap-1">
                  <span class="badge bg-info" v-for="lang in detectedLanguages[section][key]" :key="lang">
                    <i class="fas fa-language me-1"></i>{{ lang }}
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
defineProps({
  resolvedFlat: {
    type: Object,
    required: true
  },
  detectedLanguages: {
    type: Object,
    required: true
  },
  expanded: {
    type: Boolean,
    default: false
  },
  getFieldDescription: {
    type: Function,
    required: true
  }
})

defineEmits(['update:expanded'])
</script>
