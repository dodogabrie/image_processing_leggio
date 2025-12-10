<template>
  <!-- Modal di risultato -->
  <div v-if="processing.showResultModal.value" class="modal fade show d-block" tabindex="-1">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">{{ processing.resultSuccess.value ? 'Successo' : 'Errore' }}</h5>
          <button type="button" class="btn-close" @click="processing.closeResultModal"></button>
        </div>
        <div class="modal-body">
          <p class="result-message">{{ processing.resultMessage.value }}</p>
          <!-- Preview mode file sizes -->
          <div v-if="processing.previewFileSizes.value" class="mt-3">
            <h6 class="fw-bold">Dimensioni file anteprima:</h6>
            <ul class="mb-0">
              <li v-for="file in processing.previewFileSizes.value" :key="file.name">
                <strong>{{ file.name }}</strong>: {{ (file.size / 1024).toFixed(1) }} KB
              </li>
            </ul>
            <small class="text-muted d-block mt-2">I file verranno eliminati automaticamente tra 60 secondi</small>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" @click="processing.closeResultModal">Chiudi</button>
        </div>
      </div>
    </div>
  </div>
  <div class="modal-backdrop fade show" v-if="processing.showResultModal.value"></div>
</template>

<script setup>
import { inject } from 'vue'

const processing = inject('processing')
</script>

<style scoped>
.result-message {
  white-space: pre-line;
  margin-bottom: 0;
}
</style>
