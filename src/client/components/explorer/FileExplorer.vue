<template>
  <section class="mt-5">
    <div class="d-flex align-items-center justify-content-between mb-3 flex-wrap gap-2">
      <div>
        <h4 class="mb-1">Esplora elaborazione</h4>
        <p class="text-muted small mb-0">Apri cartelle e miniature direttamente dall'app, senza file system esterno.</p>
      </div>
      <div class="d-flex gap-2">
        <button class="btn btn-outline-secondary btn-sm" @click="explorer.selectOriginalRoot">
          Cartella originali (opzionale)
        </button>
        <button class="btn btn-outline-primary btn-sm" @click="explorer.pickProcessedFolder">
          Scegli cartella
        </button>
        <button class="btn btn-outline-secondary btn-sm" :disabled="!explorer.explorerRoot" @click="explorer.refreshExplorer">
          Aggiorna
        </button>
      </div>
    </div>

    <div v-if="explorer.originalRoot.value" class="alert alert-secondary py-2 mb-3 small d-flex align-items-center gap-2">
      <i class="bi bi-link-45deg"></i>
      Confronto con originali attivo su: <strong class="ms-1">{{ explorer.originalRoot.value }}</strong>
    </div>

    <div class="alert alert-light border small" role="alert">
      Per il confronto, seleziona cartelle allo stesso livello (es. input originale e output elaborato della stessa lavorazione). La cartella originale è facoltativa: se avvii un'elaborazione da qui, useremo automaticamente la cartella di input.
    </div>

    <div v-if="!explorer.explorerRoot.value" class="alert alert-info">
      Elabora un set di immagini o seleziona manualmente una cartella di output per visualizzarne il contenuto.
    </div>

    <div v-else class="card shadow-sm">
      <div class="card-body">
        <div v-if="explorer.explorerBreadcrumbs.value.length" class="d-flex align-items-center flex-wrap gap-2 mb-3">
          <span class="fw-semibold small me-1">Percorso:</span>
          <template v-for="(crumb, idx) in explorer.explorerBreadcrumbs.value" :key="crumb.path">
            <button
              class="btn btn-link btn-sm px-1"
              :class="{ 'text-decoration-underline': idx !== explorer.explorerBreadcrumbs.value.length - 1 }"
              :disabled="idx === explorer.explorerBreadcrumbs.value.length - 1"
              @click="explorer.goToBreadcrumb(crumb.path)"
            >
              {{ crumb.name || '/' }}
            </button>
            <span v-if="idx < explorer.explorerBreadcrumbs.value.length - 1" class="text-muted">/</span>
          </template>
        </div>

        <div v-if="explorer.explorerError.value" class="alert alert-danger mb-0">
          {{ explorer.explorerError.value }}
        </div>

        <div v-else-if="explorer.explorerLoading.value" class="text-center py-4">
          <div class="spinner-border text-primary" role="status"></div>
          <div class="small text-muted mt-2">Caricamento contenuto cartella...</div>
        </div>

        <div v-else>
          <FolderMetadata />

          <div v-if="explorer.foldersOnly.value.length" class="d-flex flex-wrap gap-2 mb-3">
            <div
              v-for="folder in explorer.foldersOnly.value"
              :key="folder.path"
              class="folder-chip"
              @click="explorer.openFolder(folder.path)"
            >
              <i class="bi bi-folder-fill me-2"></i>
              <span class="text-truncate">{{ folder.name }}</span>
            </div>
          </div>

          <ImageGrid />
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { inject } from 'vue'
import FolderMetadata from './FolderMetadata.vue'
import ImageGrid from './ImageGrid.vue'

const explorer = inject('explorer')
</script>

<style scoped>
.folder-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.45rem 0.75rem;
  background: #f4f6f9;
  border: 1px solid #dee2e6;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  max-width: 240px;
}

.folder-chip:hover {
  background: #e9f1ff;
  border-color: #bcd0ff;
}
</style>
