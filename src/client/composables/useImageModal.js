import { ref, reactive, computed, onBeforeUnmount } from 'vue'

export function useImageModal(explorer) {
  // Image modal state
  const fullImage = reactive({ src: '', name: '', path: '' })
  const modalIndex = ref(-1)
  const modalMetadata = ref(null)
  const originalImage = reactive({ src: '', name: '', path: '', status: '' })
  const isZoomed = ref(false)
  const zoomLevel = ref(1)
  const zoomLoading = ref(false)
  const showFolderMetadata = ref(false)
  const showMetadata = ref(false)
  const pan = reactive({ x: 0, y: 0 })
  const dragState = reactive({ dragging: false, startX: 0, startY: 0, originX: 0, originY: 0 })
  let zoomLoaderTimer = null

  // Computed properties
  const currentModalImage = computed(() => {
    const { imagesOnly } = explorer
    if (modalIndex.value < 0 || modalIndex.value >= imagesOnly.value.length) return null
    return imagesOnly.value[modalIndex.value]
  })

  // Utility functions
  const pathBasename = (fullPath) => {
    if (!fullPath) return ''
    return fullPath.split(/[\\/]/).pop()
  }

  const formatMetadata = (data) => {
    if (!data) return ''
    try {
      return JSON.stringify(data, null, 2)
    } catch {
      return String(data)
    }
  }

  const clearZoomLoader = () => {
    zoomLoading.value = false
    if (zoomLoaderTimer) {
      clearTimeout(zoomLoaderTimer)
      zoomLoaderTimer = null
    }
  }

  const startZoomLoader = () => {
    zoomLoading.value = true
    if (zoomLoaderTimer) clearTimeout(zoomLoaderTimer)
    zoomLoaderTimer = setTimeout(() => {
      clearZoomLoader()
    }, 1200)
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        clearZoomLoader()
      })
    })
  }

  // Image modal functions
  const loadMetadataForImage = async (img) => {
    if (!img || !img.path) {
      modalMetadata.value = null
      return
    }
    const base = img.path.replace(/\.[^.]+$/, '')
    const jsonPath = `${base}.json`
    try {
      const data = await window.electronAPI.readJsonFile(jsonPath)
      modalMetadata.value = data || null
    } catch (err) {
      console.warn('Errore leggendo metadata json', err)
      modalMetadata.value = null
    }
  }

  const loadOriginalForImage = async (img) => {
    const { originalRoot } = explorer
    originalImage.src = ''
    originalImage.name = ''
    originalImage.path = ''
    originalImage.status = ''
    if (!originalRoot.value || !img?.path) return

    originalImage.status = 'Caricamento originale...'
    try {
      const match = await window.electronAPI.findOriginalMatch(img.path, originalRoot.value)
      if (!match) {
        originalImage.status = 'Non trovato nella cartella originale'
        return
      }
      // Use custom media-file:// protocol for efficient loading
      originalImage.src = `media-file://${encodeURIComponent(match)}`
      originalImage.name = pathBasename(match)
      originalImage.path = match
      originalImage.status = ''
    } catch (err) {
      console.warn('Errore caricando originale', err)
      originalImage.status = err?.message || 'Errore caricando originale'
    }
  }

  const openImageModal = async (img) => {
    const { imagesOnly, explorerError } = explorer
    try {
      // Use custom media-file:// protocol for efficient loading (no base64 conversion)
      fullImage.src = `media-file://${encodeURIComponent(img.path)}`
      fullImage.name = img.name
      fullImage.path = img.path
      modalIndex.value = imagesOnly.value.findIndex(i => i.path === img.path)
      isZoomed.value = false
      zoomLevel.value = 1
      pan.x = 0
      pan.y = 0
      clearZoomLoader()
      showFolderMetadata.value = false
      showMetadata.value = false
      await loadMetadataForImage(img)
      await loadOriginalForImage(img)
    } catch (err) {
      explorerError.value = err?.message || 'Impossibile aprire questa immagine.'
    }
  }

  const closeImageModal = () => {
    fullImage.src = ''
    fullImage.name = ''
    fullImage.path = ''
    modalIndex.value = -1
    modalMetadata.value = null
    isZoomed.value = false
    zoomLevel.value = 1
    pan.x = 0
    pan.y = 0
    clearZoomLoader()
    showFolderMetadata.value = false
  }

  const showPrevImage = async () => {
    if (modalIndex.value <= 0) return
    modalIndex.value -= 1
    const img = currentModalImage.value
    if (img) {
      await openImageModal(img)
    }
  }

  const showNextImage = async () => {
    const { imagesOnly } = explorer
    if (modalIndex.value < 0 || modalIndex.value >= imagesOnly.value.length - 1) return
    modalIndex.value += 1
    const img = currentModalImage.value
    if (img) {
      await openImageModal(img)
    }
  }

  // Zoom and pan functions
  const toggleZoom = () => {
    if (zoomLevel.value > 1) {
      zoomLevel.value = 1
      isZoomed.value = false
      pan.x = 0
      pan.y = 0
      clearZoomLoader()
    } else {
      startZoomLoader()
      zoomLevel.value = 2
      isZoomed.value = true
    }
  }

  const startDrag = (event) => {
    if (zoomLevel.value <= 1) return
    dragState.dragging = true
    dragState.startX = event.clientX
    dragState.startY = event.clientY
    dragState.originX = pan.x
    dragState.originY = pan.y
  }

  const onDrag = (event) => {
    if (!dragState.dragging || zoomLevel.value <= 1) return
    const dx = event.clientX - dragState.startX
    const dy = event.clientY - dragState.startY
    pan.x = dragState.originX + dx
    pan.y = dragState.originY + dy
  }

  const endDrag = () => {
    dragState.dragging = false
  }

  const handleWheelZoom = (event) => {
    if (!fullImage.src) return
    event.preventDefault()
    const delta = event.deltaY < 0 ? 0.2 : -0.2
    const next = Math.min(4, Math.max(1, zoomLevel.value + delta))
    if (next > zoomLevel.value && next > 1) {
      startZoomLoader()
    }
    zoomLevel.value = next
    isZoomed.value = zoomLevel.value > 1
    if (zoomLevel.value === 1) {
      pan.x = 0
      pan.y = 0
      clearZoomLoader()
    }
  }

  // Cleanup on unmount
  onBeforeUnmount(() => {
    clearZoomLoader()
  })

  return {
    // State
    fullImage,
    modalIndex,
    modalMetadata,
    originalImage,
    isZoomed,
    zoomLevel,
    zoomLoading,
    showFolderMetadata,
    showMetadata,
    pan,
    dragState,

    // Computed
    currentModalImage,

    // Functions
    openImageModal,
    closeImageModal,
    loadMetadataForImage,
    loadOriginalForImage,
    showPrevImage,
    showNextImage,
    toggleZoom,
    startDrag,
    onDrag,
    endDrag,
    handleWheelZoom,
    formatMetadata,
    pathBasename
  }
}
