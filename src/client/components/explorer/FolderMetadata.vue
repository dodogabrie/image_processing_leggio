<template>
  <div v-if="explorer.folderDocument.value || explorer.folderMetadataStatus.value" class="card folder-meta-card mb-3">
    <div class="card-body p-3">
      <div class="d-flex align-items-center justify-content-between gap-2 flex-wrap">
        <div>
          <h6 class="mb-1">Metadati cartella</h6>
          <p class="text-muted small mb-0 text-truncate">{{ explorer.folderMetadataStatus.value || 'Metadati disponibili' }}</p>
        </div>
        <span v-if="explorer.folderDocument.value?.title" class="badge bg-primary-subtle text-primary border">
          {{ explorer.folderDocument.value.title }}
        </span>
      </div>
      <dl class="row folder-meta-list mb-0 mt-3" v-if="explorer.folderDocumentEntries.value.length">
        <template v-for="entry in explorer.folderDocumentEntries.value" :key="entry.key">
          <dt class="col-sm-4 text-muted small text-uppercase">{{ entry.label }}</dt>
          <dd class="col-sm-8 mb-2">{{ entry.value || '—' }}</dd>
        </template>
      </dl>
      <div v-else class="text-muted small">Nessun dettaglio documento trovato.</div>
    </div>
  </div>
</template>

<script setup>
import { inject } from 'vue'

const explorer = inject('explorer')
</script>

<style scoped>
.folder-meta-card {
  border: 1px solid #e2e8f0;
}

.folder-meta-list dt {
  font-weight: 600;
  letter-spacing: 0.4px;
}

.folder-meta-list dd {
  word-break: break-word;
}
</style>
