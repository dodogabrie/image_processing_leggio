<template>
  <!-- Modal anteprima immagine -->
  <div v-if="imageModal.fullImage.src" class="modal fade show d-block full-image-modal" tabindex="-1">
    <div class="modal-dialog modal-xl modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">{{ imageModal.fullImage.name }}</h5>
          <button type="button" class="btn-close" @click="imageModal.closeImageModal"></button>
        </div>
        <div class="modal-body">
          <div class="modal-body-grid">
            <div class="image-area">
              <div class="pane-header">
                <span class="pane-title">Elaborato</span>
                <small class="text-muted ms-2 text-truncate d-inline-block" style="max-width: 240px;">{{ imageModal.fullImage.name }}</small>
              </div>
              <button v-if="imageModal.modalIndex.value > 0" class="nav-arrow left" @click="imageModal.showPrevImage">
                <span aria-hidden="true">‹</span>
              </button>
              <button class="zoom-toggle" @click="imageModal.toggleZoom">
                {{ imageModal.isZoomed.value ? 'Ripristina' : 'Zoom' }}
              </button>
              <div class="pane-body">
                <img
                  :src="imageModal.fullImage.src"
                  :alt="imageModal.fullImage.name"
                  class="full-image"
                  :class="{ zoomed: imageModal.isZoomed.value }"
                  :style="{
                    transform: imageModal.zoomLevel.value > 1
                      ? `translate(${imageModal.pan.x}px, ${imageModal.pan.y}px) scale(${imageModal.zoomLevel.value})`
                      : null
                  }"
                  @mousedown.prevent="imageModal.startDrag"
                  @mousemove.prevent="imageModal.onDrag"
                  @mouseup.prevent="imageModal.endDrag"
                  @mouseleave.prevent="imageModal.endDrag"
                  @wheel="imageModal.handleWheelZoom"
                />
              </div>
              <button v-if="imageModal.modalIndex.value < explorer.imagesOnly.value.length - 1" class="nav-arrow right" @click="imageModal.showNextImage">
                <span aria-hidden="true">›</span>
              </button>
            </div>
            <div class="side-panel">
              <div class="original-box">
                <div class="d-flex align-items-center justify-content-between mb-2">
                  <h6 class="mb-0">Originale</h6>
                  <small class="text-muted text-truncate" v-if="imageModal.originalImage.path">{{ imageModal.originalImage.name }}</small>
                  <small class="text-muted" v-else-if="imageModal.originalImage.status">{{ imageModal.originalImage.status }}</small>
                  <small class="text-muted" v-else>Seleziona cartella originali</small>
                </div>
                <div class="original-preview">
                  <template v-if="imageModal.originalImage.src">
                    <div class="pane-body">
                      <img
                        :src="imageModal.originalImage.src"
                        :alt="imageModal.originalImage.name"
                        :class="{ zoomed: imageModal.isZoomed.value }"
                        :style="{
                          transform: imageModal.zoomLevel.value > 1
                            ? `translate(${imageModal.pan.x}px, ${imageModal.pan.y}px) scale(${imageModal.zoomLevel.value})`
                            : null
                        }"
                        @mousedown.prevent="imageModal.startDrag"
                        @mousemove.prevent="imageModal.onDrag"
                        @mouseup.prevent="imageModal.endDrag"
                        @mouseleave.prevent="imageModal.endDrag"
                        @wheel="imageModal.handleWheelZoom"
                      />
                    </div>
                  </template>
                  <div class="alert alert-light py-2 small mb-0" v-else>
                    {{ imageModal.originalImage.status || 'Nessuna immagine originale trovata per il confronto.' }}
                  </div>
                </div>
              </div>

              <div class="meta-area" v-if="imageModal.modalMetadata.value">
                <div class="d-flex align-items-center justify-content-between mb-2">
                  <h6 class="mb-0">Metadati</h6>
                  <button class="btn btn-sm btn-outline-secondary" @click="imageModal.showMetadata.value = !imageModal.showMetadata.value">
                    {{ imageModal.showMetadata.value ? 'Nascondi' : 'Mostra' }}
                  </button>
                </div>
                <pre class="metadata-pre" v-if="imageModal.showMetadata.value">{{ imageModal.formatMetadata(imageModal.modalMetadata.value) }}</pre>
              </div>
            </div>
            <div v-if="imageModal.zoomLoading.value" class="zoom-loading-overlay">
              <div class="spinner-border text-light" role="status"></div>
              <div class="small text-light mt-2">Preparazione zoom...</div>
            </div>
          </div>
          <div v-if="imageModal.showFolderMetadata.value" class="card folder-meta-modal mt-3">
            <div class="card-body p-3">
              <div class="d-flex align-items-center justify-content-between gap-2 flex-wrap mb-2">
                <h6 class="mb-0">Metadati cartella</h6>
                <small class="text-muted">{{ explorer.folderMetadataStatus.value || 'Dettagli cartella' }}</small>
              </div>
              <dl v-if="explorer.folderDocumentEntries.value.length" class="row folder-meta-list mb-0">
                <template v-for="entry in explorer.folderDocumentEntries.value" :key="entry.key">
                  <dt class="col-sm-4 text-muted small text-uppercase">{{ entry.label }}</dt>
                  <dd class="col-sm-8 mb-2">{{ entry.value || '—' }}</dd>
                </template>
              </dl>
              <div v-else class="alert alert-light py-2 mb-0 small">
                Metadati non disponibili per questa cartella.
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <div class="me-auto text-muted small" v-if="explorer.imagesOnly.value.length > 1">
            {{ imageModal.modalIndex.value + 1 }} / {{ explorer.imagesOnly.value.length }}
          </div>
          <button
            type="button"
            class="btn btn-outline-secondary"
            :disabled="!explorer.folderDocument.value && !explorer.folderMetadataStatus.value"
            @click="imageModal.showFolderMetadata.value = !imageModal.showFolderMetadata.value"
          >
            {{ imageModal.showFolderMetadata.value ? 'Nascondi metadati' : 'Metadati cartella' }}
          </button>
          <button type="button" class="btn btn-secondary" @click="imageModal.closeImageModal">Chiudi</button>
        </div>
      </div>
    </div>
  </div>
  <div class="modal-backdrop fade show" v-if="imageModal.fullImage.src"></div>
</template>

<script setup>
import { inject } from 'vue'

const explorer = inject('explorer')
const imageModal = inject('imageModal')
</script>

<style scoped>
.full-image-modal .modal-dialog {
  max-width: 90vw;
}

.full-image-modal .modal-body {
  background: #0f172a;
}

.full-image {
  max-height: 70vh;
  max-width: 100%;
  object-fit: contain;
  transition: transform 0.15s ease;
  will-change: transform;
}

.full-image.zoomed {
  cursor: grab;
}

.full-image.zoomed:active {
  cursor: grabbing;
}

.modal-body-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.5rem;
  align-items: center;
  position: relative;
  --pane-height: 70vh;
}

.image-area {
  position: relative;
  min-width: 0;
  text-align: center;
  overflow: hidden;
  background: #0b1224;
  border-radius: 12px;
  padding: 0.75rem;
  min-height: var(--pane-height);
  display: flex;
  align-items: center;
  justify-content: center;
}

.pane-header {
  position: absolute;
  top: 10px;
  left: 12px;
  z-index: 7;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.6rem;
  background: rgba(15, 23, 42, 0.85);
  color: #e2e8f0;
  border-radius: 10px;
  border: 1px solid #1e293b;
}

.pane-title {
  font-weight: 700;
  letter-spacing: 0.3px;
}

.nav-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.4);
  background: rgba(37, 99, 235, 0.9);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 5;
  box-shadow: 0 6px 18px rgba(0,0,0,0.25);
}

.nav-arrow.left { left: 10px; }
.nav-arrow.right { right: 10px; }

.nav-arrow:hover {
  background: rgba(59, 130, 246, 0.85);
}

.zoom-toggle {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 6;
  border: none;
  padding: 0.45rem 0.75rem;
  border-radius: 10px;
  background: rgba(59, 130, 246, 0.95);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}

.zoom-toggle:hover {
  background: rgba(37, 99, 235, 0.95);
}

.zoom-loading-overlay {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 0.5rem;
  border-radius: 12px;
  z-index: 12;
  pointer-events: all;
  cursor: progress;
}

.zoom-loading-overlay .spinner-border {
  width: 2.75rem;
  height: 2.75rem;
}

.side-panel {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.75rem;
  min-width: 0;
  min-height: var(--pane-height);
}

.original-box {
  background: #0b1224;
  border-radius: 12px;
  padding: 0.75rem;
  border: 1px solid #1e293b;
  min-height: calc(var(--pane-height) - 1rem);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.original-preview {
  background: #0f172a;
  border-radius: 10px;
  padding: 0.5rem;
  text-align: center;
  border: 1px solid #1e293b;
  overflow: hidden;
  flex: 1;
  height: var(--pane-height);
  display: flex;
  align-items: center;
  justify-content: center;
}

.pane-body {
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 12px;
  padding: 0.25rem;
  width: 100%;
  height: var(--pane-height);
  min-height: var(--pane-height);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.pane-body img,
.original-preview img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 8px;
  background: #0b1224;
  transition: transform 0.15s ease;
  will-change: transform;
}

.meta-area {
  background: #fff;
  border-radius: 12px;
  padding: 1rem;
  border: 1px solid #e5e7eb;
  max-height: calc(var(--pane-height) / 2);
  overflow: auto;
}

.folder-meta-modal {
  border: 1px solid #e2e8f0;
}

.metadata-pre {
  white-space: pre-wrap;
  background: #f8fafc;
  border-radius: 8px;
  padding: 0.75rem;
  border: 1px solid #e2e8f0;
  font-size: 0.85rem;
  max-height: 60vh;
  overflow: auto;
}

.folder-meta-list dt {
  font-weight: 600;
  letter-spacing: 0.4px;
}

.folder-meta-list dd {
  word-break: break-word;
}

@media (max-width: 992px) {
  .modal-body-grid {
    grid-template-columns: 1fr;
  }
}
</style>
