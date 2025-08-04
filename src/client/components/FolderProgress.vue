<template>
  <div class="folder-progress-container">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h5 class="mb-0">
        {{ getTitle() }}
      </h5>
      <div v-if="foldersStatus.length > 1" class="text-muted">
        {{ completedCount }} / {{ foldersStatus.length }} completate
      </div>
    </div>
    
    <!-- Loader globale per l'intero processo -->
    <div v-if="shouldShowGlobalProgress" class="global-progress mb-3">
      <div class="d-flex align-items-center">
        <div class="global-spinner me-3">
          <div class="spinner-border text-primary" role="status" style="width: 2rem; height: 2rem;">
            <span class="visually-hidden">Elaborazione in corso...</span>
          </div>
        </div>
        <div>
          <div class="fw-bold">
            {{ getGlobalProgressTitle() }}
          </div>
          <div class="text-muted small">
            {{ getGlobalProgressSubtitle() }}
          </div>
        </div>
      </div>
    </div>
    
    <!-- Griglia cartelle (solo se ci sono più cartelle) -->
    <div v-if="shouldShowFoldersGrid" class="folders-grid">
      <div 
        v-for="folder in foldersStatus" 
        :key="folder.path"
        class="folder-item"
        :class="{
          'folder-pending': folder.status === 'pending',
          'folder-processing': folder.status === 'processing', 
          'folder-completed': folder.status === 'completed',
          'folder-main': folder.isMainFolder
        }"
      >
        <!-- Icona cartella con overlay loader -->
        <div class="folder-icon-container">
          <i :class="folder.isMainFolder ? 'bi bi-house-fill' : 'bi bi-folder-fill'" class="folder-icon"></i>
          
          <!-- Loader circolare per cartelle in elaborazione -->
          <div 
            v-if="folder.status === 'processing'" 
            class="folder-loader"
          >
            <svg class="progress-ring" width="50" height="50" viewBox="0 0 50 50">
              <circle
                class="progress-ring-bg"
                stroke="rgba(255,255,255,0.2)"
                stroke-width="4"
                fill="transparent"
                r="20"
                cx="25"
                cy="25"
              />
              <circle
                class="progress-ring-circle"
                stroke="#0d6efd"
                stroke-width="4"
                fill="transparent"
                r="20"
                cx="25"
                cy="25"
                :style="{ strokeDashoffset: circleOffset(folder.progress) }"
              />
            </svg>
            <span class="progress-text">{{ folder.progress }}%</span>
          </div>
          
          <!-- Checkmark per cartelle completate -->
          <div v-if="folder.status === 'completed'" class="folder-check">
            <i class="bi bi-check-circle-fill"></i>
          </div>
        </div>
        
        <!-- Nome cartella -->
        <div class="folder-name" :title="folder.relativePath || folder.name">
          {{ folder.name }}
        </div>
        
        <!-- Dettagli progresso -->
        <div v-if="folder.status === 'processing' && folder.total > 0" class="folder-details">
          {{ folder.current }} / {{ folder.total }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  foldersStatus: {
    type: Array,
    default: () => []
  }
})

// Calcolo offset per progress ring
const circleOffset = (progress) => {
  const circumference = 2 * Math.PI * 20 // r=20
  return circumference - (progress / 100) * circumference
}

// Computed per statistiche
const hasSubfolders = computed(() => props.foldersStatus.length > 1)
const hasMainFolder = computed(() => props.foldersStatus.some(f => f.isMainFolder))

const completedCount = computed(() => 
  props.foldersStatus.filter(f => f.status === 'completed').length
)

const hasProcessing = computed(() => 
  props.foldersStatus.some(f => f.status === 'processing')
)

const hasCompleted = computed(() => 
  props.foldersStatus.some(f => f.status === 'completed')
)

const shouldShowGlobalProgress = computed(() => 
  hasProcessing.value || hasCompleted.value || props.foldersStatus.length === 1
)

const shouldShowFoldersGrid = computed(() => 
  props.foldersStatus.length > 1
)

// Metodi per i titoli dinamici
const getTitle = () => {
  if (props.foldersStatus.length === 0) return 'Elaborazione in corso'
  if (props.foldersStatus.length === 1) {
    const folder = props.foldersStatus[0]
    return folder.isMainFolder ? 'Elaborazione cartella principale' : 'Elaborazione cartella'
  }
  return hasMainFolder.value ? 'Elaborazione cartelle (principale + sottocartelle)' : 'Progresso Elaborazione Cartelle'
}

const getGlobalProgressTitle = () => {
  if (props.foldersStatus.length === 1) {
    return 'Elaborazione immagini in corso'
  }
  return 'Elaborazione globale in corso'
}

const getGlobalProgressSubtitle = () => {
  if (props.foldersStatus.length === 1) {
    return 'Processando le immagini...'
  }
  const percentage = Math.round((completedCount.value / props.foldersStatus.length) * 100)
  const mainText = `${percentage}% completato`
  if (hasMainFolder.value) {
    return `${mainText} • Cartella principale + ${props.foldersStatus.length - 1} sottocartelle`
  }
  return mainText
}
</script>

<style scoped>
.folder-progress-container {
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-radius: 12px;
  padding: 1.5rem;
  margin: 1rem 0;
  border: 1px solid #dee2e6;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.global-progress {
  background: white;
  border-radius: 8px;
  padding: 1rem;
  border: 1px solid #e9ecef;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.global-spinner .spinner-border {
  border-width: 3px;
}

.folders-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 1rem;
  max-height: 400px;
  overflow-y: auto;
  padding: 0.5rem;
}

.folder-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1rem;
  border-radius: 12px;
  transition: all 0.3s ease;
  text-align: center;
  min-height: 120px;
  justify-content: center;
  position: relative;
  border: 2px solid transparent;
}

.folder-pending {
  opacity: 0.5;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-color: #dee2e6;
}

.folder-processing {
  opacity: 1;
  background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
  border-color: #f0c14b;
  box-shadow: 0 4px 8px rgba(240, 193, 75, 0.3);
  transform: scale(1.02);
}

.folder-completed {
  opacity: 1;
  background: linear-gradient(135deg, #d1edff 0%, #a7d8f0 100%);
  border-color: #0d6efd;
  box-shadow: 0 4px 8px rgba(13, 110, 253, 0.3);
}

.folder-main {
  border-left: 4px solid #6f42c1;
}

.folder-main.folder-pending {
  background: linear-gradient(135deg, #f8f9fa 0%, #e6e4f0 100%);
  border-color: #6f42c1;
  opacity: 0.6;
}

.folder-main.folder-processing {
  background: linear-gradient(135deg, #f3e8ff 0%, #e0cffc 100%);
  border-color: #6f42c1;
}

.folder-main.folder-completed {
  background: linear-gradient(135deg, #e6d9ff 0%, #d1c2f0 100%);
  border-color: #6f42c1;
}

.folder-icon-container {
  position: relative;
  margin-bottom: 0.75rem;
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.folder-icon {
  font-size: 3rem;
  color: #6c757d;
  transition: color 0.3s ease;
}

.folder-processing .folder-icon {
  color: #f0c14b;
}

.folder-completed .folder-icon {
  color: #0d6efd;
}

.folder-main .folder-icon {
  color: #6f42c1;
}

.folder-main.folder-processing .folder-icon {
  color: #6f42c1;
}

.folder-main.folder-completed .folder-icon {
  color: #6f42c1;
}

.folder-loader {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 50px;
  height: 50px;
  z-index: 10;
}

.progress-ring {
  transform: rotate(-90deg);
  width: 100%;
  height: 100%;
}

.progress-ring-circle {
  stroke-dasharray: 125.66; /* 2π * 20 */
  stroke-dashoffset: 125.66;
  transition: stroke-dashoffset 0.5s ease;
  stroke-linecap: round;
}

.progress-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 0.7rem;
  font-weight: bold;
  color: #0d6efd;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 50%;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 11;
}

.folder-check {
  position: absolute;
  top: -8px;
  right: -8px;
  color: #198754;
  font-size: 1.5rem;
  background: white;
  border-radius: 50%;
  padding: 2px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.folder-name {
  font-size: 0.85rem;
  font-weight: 600;
  word-break: break-word;
  max-width: 100%;
  line-height: 1.2;
  color: #495057;
}

.folder-processing .folder-name {
  color: #856404;
}

.folder-completed .folder-name {
  color: #084298;
}

.folder-details {
  font-size: 0.75rem;
  color: #6c757d;
  margin-top: 0.5rem;
  background: rgba(255, 255, 255, 0.8);
  padding: 0.25rem 0.5rem;
  border-radius: 12px;
  font-weight: 500;
}

/* Animazioni */
.folder-processing {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { transform: scale(1.02); }
  50% { transform: scale(1.05); }
  100% { transform: scale(1.02); }
}

/* Scrollbar personalizzata */
.folders-grid::-webkit-scrollbar {
  width: 8px;
}

.folders-grid::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.folders-grid::-webkit-scrollbar-thumb {
  background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
  border-radius: 4px;
}

.folders-grid::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(135deg, #495057 0%, #343a40 100%);
}

/* Responsive */
@media (max-width: 768px) {
  .folders-grid {
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 0.75rem;
  }
  
  .folder-item {
    padding: 0.75rem;
    min-height: 100px;
  }
  
  .folder-icon {
    font-size: 2.5rem;
  }
}
</style>
