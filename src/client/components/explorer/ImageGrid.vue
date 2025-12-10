<template>
  <div class="image-grid" v-if="explorer.imagesOnly.value.length">
    <div
      v-for="img in explorer.imagesOnly.value"
      :key="img.path"
      class="image-card"
      @click="imageModal.openImageModal(img)"
    >
      <div v-if="explorer.thumbLoading.value" class="thumb-loading-overlay">
        <div class="spinner-border text-primary spinner-border-sm" role="status"></div>
      </div>
      <div class="thumb-wrapper">
        <img
          :src="explorer.thumbnailCache.value[img.thumbnailPath || img.path] || explorer.placeholderThumb"
          :alt="img.name"
        />
      </div>
      <div class="small text-truncate mt-2" :title="img.name">{{ img.name }}</div>
    </div>
  </div>

  <div v-else class="text-muted small text-center py-3">
    Nessuna immagine in questa cartella.
  </div>
</template>

<script setup>
import { inject } from 'vue'

const explorer = inject('explorer')
const imageModal = inject('imageModal')
</script>

<style scoped>
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem;
}

.image-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 0.75rem;
  background: #ffffff;
  box-shadow: 0 2px 6px rgba(0,0,0,0.04);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}

.image-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 14px rgba(0,0,0,0.08);
}

.thumb-wrapper {
  background: linear-gradient(135deg, #f5f7fb, #eef2f7);
  border-radius: 10px;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 140px;
  position: relative;
}

.thumb-wrapper img {
  max-height: 120px;
  max-width: 100%;
  object-fit: contain;
  border-radius: 8px;
  border: 1px solid #e0e3e8;
}

.thumb-loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.75);
  border-radius: 12px;
  z-index: 2;
}
</style>
