<!-- File: src/components/MapCSV.vue -->
<template>
  <div class="mt-4">
    <!-- Vista di riepilogo: mostra solo i campi mappati che corrispondono effettivamente agli header CSV -->
    <div v-if="!editing && confirmedMapping" class="alert alert-info">
      <h5 class="mb-3">Mappatura campi CSV</h5>

      <div class="mb-3">
        <h6>Campi documento digitale</h6>
        <ul>
          <li v-for="(col, field) in filteredDocumentMapping" :key="field">
            <strong>{{ field }}:</strong> {{ col }}
          </li>
        </ul>
      </div>

      <div class="mb-3">
        <h6>Campi File Multimediale</h6>
        <ul>
          <li v-for="(col, field) in filteredImageMapping" :key="field">
            <strong>{{ field }}:</strong> {{ col }}
          </li>
        </ul>
      </div>

      <button class="btn btn-sm btn-secondary" @click="startEditing">
        <i class="bi bi-pencil"></i> Modifica mappatura
      </button>
    </div>

    <!-- Vista di editing: mostra tutti i campi disponibili per la mappatura (flat) -->
    <div v-else>
      <h5 class="mb-3">Modifica mappatura</h5>

      <div v-for="section in sections" :key="section" class="mb-4">
        <h6 class="text-uppercase text-secondary">
          {{ section === 'document' ? 'Campi documento digitale' : 'Campi immagine' }}
        </h6>

        <!-- Usa flatMappingFields per iterare su chiavi piatte -->
        <div
          v-for="(desc, key) in flatMappingFields[section]"
          :key="section + '-' + key"
          class="mb-2"
        >
          <label class="form-label d-block">
            {{ key }} <small class="text-muted">({{ desc }})</small>
          </label>
          <select v-model="localMapping[section][key]" class="form-select">
            <option value="">-- Nessuna --</option>
            <option v-for="header in headers" :key="header" :value="header">
              {{ header }}
            </option>
          </select>
        </div>
      </div>

      <div class="d-flex gap-2">
        <button class="btn btn-primary" @click="confirm">Conferma</button>
        <button class="btn btn-link" @click="cancel">Annulla</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue';

const props = defineProps({
  /**
   * @type {string[]}
   * Array di header letti dal CSV, usati per validare le mappature
   */
  headers: Array,

  /**
   * @type {{ document: Record<string, any>, image: Record<string, any> }}
   * Oggetto di mapping iniziale (piatto) passato dal componente padre
   */
  initialMapping: Object
});
const emit = defineEmits(['mappingConfirmed']);

// Stati reattivi interni
const mappingFields = ref({ document: {}, image: {} }); // descrizioni nested
const localMapping = ref({ document: {}, image: {} });  // mapping flat
const confirmedMapping = ref(null);
const editing = ref(false);
const sections = ['document', 'image'];

/**
 * Flatten delle descrizioni nested in chiavi piatte:
 * es. { format: { name: 'JPEG' } } -> { 'format.name': 'JPEG' }
 */
const flatMappingFields = computed(() => {
  const out = { document: {}, image: {} };
  for (const section of sections) {
    const secObj = mappingFields.value[section] || {};
    Object.entries(secObj).forEach(([key, val]) => {
      if (val != null && typeof val === 'object') {
        // per ogni sotto-campo
        Object.entries(val).forEach(([subKey, subDesc]) => {
          out[section][`${key}.${subKey}`] = subDesc;
        });
      } else {
        out[section][key] = val;
      }
    });
  }
  return out;
});

/**
 * Computed: filtra il mapping documento (piatto) mantenendo solo:
 * - valori di tipo stringa non vuoti
 * - che matchano (startsWith, case-insensitive) un header CSV
 */
const filteredDocumentMapping = computed(() => {
  if (!confirmedMapping.value?.document) return {};
  return Object.fromEntries(
    Object.entries(confirmedMapping.value.document)
      .filter(([field, col]) =>
        typeof col === 'string' &&
        col.trim() !== '' &&
        props.headers.some(h =>
          typeof h === 'string' &&
          h.toLowerCase().startsWith(col.toLowerCase())
        )
      )
  );
});

/**
 * Computed: filtra il mapping immagine (piatto) con la stessa logica
 */
const filteredImageMapping = computed(() => {
  if (!confirmedMapping.value?.image) return {};
  return Object.fromEntries(
    Object.entries(confirmedMapping.value.image)
      .filter(([field, col]) =>
        typeof col === 'string' &&
        col.trim() !== '' &&
        props.headers.some(h =>
          typeof h === 'string' &&
          h.toLowerCase().startsWith(col.toLowerCase())
        )
      )
  );
});

// Al montaggio, carica descrizioni (nested) per flatMappingFields
onMounted(async () => {
  try {
    const raw = await window.electronAPI.readPublicFile('database_bridge.json');
    mappingFields.value = JSON.parse(raw);
  } catch {
    mappingFields.value = { document: {}, image: {} };
  }
  if (props.initialMapping?.document) {
    localMapping.value = JSON.parse(JSON.stringify(props.initialMapping));
    confirmedMapping.value = JSON.parse(JSON.stringify(props.initialMapping));
  }
});

/**
 * Sincronizza flat mapping quando cambia initialMapping nel padre
 */
watch(
  () => props.initialMapping,
  val => {
    if (val?.document) {
      localMapping.value = JSON.parse(JSON.stringify(val));
      confirmedMapping.value = JSON.parse(JSON.stringify(val));
    }
  }
);

/** Attiva editing */
function startEditing() {
  editing.value = true;
}

/** Conferma e invia mapping (flat) al componente padre */
function confirm() {
  confirmedMapping.value = JSON.parse(JSON.stringify(localMapping.value));
  editing.value = false;
  emit('mappingConfirmed', confirmedMapping.value);
}

/** Annulla modifiche in corso */
function cancel() {
  localMapping.value = JSON.parse(JSON.stringify(confirmedMapping.value));
  editing.value = false;
}
</script>

<style>
/* Stili specifici di MapCSV */
</style>
