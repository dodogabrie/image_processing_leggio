<template>
  <div>
    <div class="mb-3">
      <div v-if="!processing.showFolderProgress.value" class="progress" style="height:24px;">
        <div
          class="progress-bar"
          role="progressbar"
          :style="{ width: processing.percent.value + '%' }"
          :aria-valuenow="processing.percent.value"
          aria-valuemin="0"
          aria-valuemax="100"
        >
          {{ processing.percent.value }}%
        </div>
      </div>
      <div v-if="processing.globalImagesTotal.value > 0" class="mt-2 text-center text-secondary small">
        Immagini totali: {{ processing.globalImagesProcessed.value }} / {{ processing.globalImagesTotal.value }}
      </div>
      <div v-if="processing.videoProcessingMessage.value" class="alert alert-info mt-2 text-center">
        {{ processing.videoProcessingMessage.value }}
      </div>
    </div>

    <!-- Componente progresso cartelle -->
    <FolderProgress
      v-if="processing.showFolderProgress.value"
      :foldersStatus="processing.foldersStatus.value"
      :currentThumbnail="processing.currentThumbnail.value"
    />

    <pre class="font-monospace text-primary">{{ processing.csvText.value }}</pre>
  </div>
</template>

<script setup>
import { inject } from 'vue'
import FolderProgress from '../shared/FolderProgress.vue'

const processing = inject('processing')
</script>
