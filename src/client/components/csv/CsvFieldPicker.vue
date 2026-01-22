<template>
  <div class="csv-field-picker">
    <div class="d-flex flex-wrap gap-1 mb-1">
      <span v-if="!modelValue.length" class="text-muted small">Non mappato</span>
      <span
        v-for="fieldId in modelValue"
        :key="fieldId"
        class="badge bg-secondary d-inline-flex align-items-center"
      >
        {{ fieldId }}
        <button type="button" class="btn btn-link btn-sm text-white ms-1 p-0" @click="remove(fieldId)">
          ×
        </button>
      </span>
    </div>

    <details class="mb-1">
      <summary class="small">Seleziona campi</summary>
      <div class="border rounded p-2 mt-2">
        <input
          v-model="filterText"
          type="text"
          class="form-control form-control-sm mb-2"
          placeholder="Filtra campi..."
        />

        <div v-for="section in ['document', 'image']" :key="section" class="mb-2">
          <div class="fw-bold small text-uppercase mb-1">{{ section }}</div>
          <div v-if="!filteredOptions[section].length" class="text-muted small">Nessun risultato</div>
          <div v-else class="d-flex flex-column gap-1">
            <label
              v-for="opt in filteredOptions[section]"
              :key="`${section}.${opt.key}`"
              class="form-check small d-flex align-items-start gap-2"
              :title="opt.description"
            >
              <input
                class="form-check-input mt-1"
                type="checkbox"
                :value="`${section}.${opt.key}`"
                :checked="modelValue.includes(`${section}.${opt.key}`)"
                @change="toggle(`${section}.${opt.key}`)"
              />
              <span>
                {{ opt.key }}<span v-if="opt.required"> (obbligatorio)</span>
                <span class="text-muted d-block">{{ opt.description }}</span>
              </span>
            </label>
          </div>
        </div>

        <button type="button" class="btn btn-outline-secondary btn-sm" @click="clearAll">
          Svuota selezione
        </button>
      </div>
    </details>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  options: {
    type: Object,
    required: true
  },
  modelValue: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['update:modelValue'])

const filterText = ref('')

const filteredOptions = computed(() => {
  const term = filterText.value.trim().toLowerCase()
  const filterList = list => {
    if (!term) return list
    return list.filter(opt => {
      const hay = `${opt.key} ${opt.description}`.toLowerCase()
      return hay.includes(term)
    })
  }
  return {
    document: filterList(props.options.document || []),
    image: filterList(props.options.image || [])
  }
})

function toggle(fieldId) {
  const next = props.modelValue.slice()
  const index = next.indexOf(fieldId)
  if (index >= 0) {
    next.splice(index, 1)
  } else {
    next.push(fieldId)
  }
  emit('update:modelValue', next)
}

function remove(fieldId) {
  const next = props.modelValue.filter(item => item !== fieldId)
  emit('update:modelValue', next)
}

function clearAll() {
  emit('update:modelValue', [])
}
</script>

<style scoped>
.csv-field-picker summary {
  cursor: pointer;
}
.csv-field-picker summary::marker {
  color: var(--bs-secondary);
}
</style>
