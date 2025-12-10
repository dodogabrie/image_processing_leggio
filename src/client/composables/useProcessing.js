import { ref, computed, onMounted } from 'vue'

/**
 * Composable for managing image/video processing workflow
 *
 * Handles the complete processing lifecycle including:
 * - User folder selection (input/output)
 * - Processing options (optimization, crop, video encoding)
 * - Progress tracking via IPC events from Electron backend
 * - Result handling and preview mode
 *
 * @param {Object} csvMapping - The useCsvMapping composable instance
 * @param {Object} csvMapping.unflattenMap - Function to convert flat CSV mapping to nested structure
 * @param {Object} csvMapping.resolvedFlat - Resolved CSV field mappings
 *
 * @returns {Object} Processing state and control functions
 *
 * @example
 * const csvMapping = useCsvMapping()
 * const processing = useProcessing(csvMapping)
 *
 * // Select folders and start processing
 * await processing.selectFolder()
 * await processing.selectOutput()
 * await processing.startProcess()
 */
export function useProcessing(csvMapping) {
  // ============================================================================
  // PROCESSING CONTROLS STATE
  // User-configurable options for the processing workflow
  // ============================================================================

  /** @type {Ref<string|null>} Input folder path selected by user */
  const selectedFolder = ref(null)

  /** @type {Ref<string|null>} Output folder path for processed files */
  const selectedOutput = ref(null)

  /** @type {Ref<boolean>} Enable/disable image optimization (WebP conversion, thumbnails) */
  const optimizeImages = ref(true)

  /** @type {Ref<boolean>} Preview mode: process only 4 images, auto-delete after 60s */
  const previewMode = ref(false)

  /** @type {Ref<string>} Compression level: 'low' | 'standard' | 'high' */
  const aggressivity = ref('standard')

  /** @type {Ref<boolean>} Enable automatic book fold detection and cropping */
  const crop = ref(false)

  /** @type {Ref<boolean>} Enable FFmpeg video optimization (H.264/H.265 encoding) */
  const optimizeVideos = ref(false)

  /** @type {Ref<number|null>} Limit CSV processing to first N rows (for testing) */
  const maxCsvLine = ref(null)

  // ============================================================================
  // PROCESSING STATUS STATE
  // Real-time status updates during processing
  // ============================================================================

  /** @type {Ref<boolean>} Whether processing is currently running */
  const processing = ref(false)

  /** @type {Ref<number>} Overall progress percentage (0-100) */
  const percent = ref(0)

  /** @type {Ref<string>} Loading message (e.g., "Conteggio cartelle in corso...") */
  const loadingText = ref('')

  /** @type {Ref<string>} Detailed progress text (current file/folder info) */
  const progressText = ref('')

  /** @type {Ref<string>} CSV organization progress text */
  const csvText = ref('')

  /** @type {Ref<boolean>} Whether to show CSV line limit input */
  const showCsvInput = ref(false)

  // ============================================================================
  // PROGRESS TRACKING STATE
  // Detailed progress information from backend worker processes
  // ============================================================================

  /** @type {Ref<Array>} Status of each folder being processed (for grid display) */
  const foldersStatus = ref([])

  /** @type {Ref<boolean>} Whether to show folder-by-folder progress grid */
  const showFolderProgress = ref(false)

  /** @type {Ref<number>} Total number of images across all folders */
  const globalImagesTotal = ref(0)

  /** @type {Ref<number>} Number of images processed so far */
  const globalImagesProcessed = ref(0)

  /** @type {Ref<string>} Video processing status message (FFmpeg operations) */
  const videoProcessingMessage = ref('')

  /** @type {Ref<string>} Path to current thumbnail being generated (for live preview) */
  const currentThumbnail = ref('')

  // ============================================================================
  // RESULT MODAL STATE
  // Success/error notification after processing completes
  // ============================================================================

  /** @type {Ref<boolean>} Whether to show the result modal */
  const showResultModal = ref(false)

  /** @type {Ref<boolean>} Whether processing completed successfully */
  const resultSuccess = ref(false)

  /** @type {Ref<string>} Result message (success or error details) */
  const resultMessage = ref('')

  // ============================================================================
  // PREVIEW MODE STATE
  // Preview mode processes only 4 images for quick testing
  // ============================================================================

  /** @type {Ref<Array|null>} File sizes of preview images (for display) */
  const previewFileSizes = ref(null)

  /** @type {Ref<number|null>} Timer ID for auto-cleanup after 60 seconds */
  const previewCleanupTimer = ref(null)

  // ============================================================================
  // COMPUTED PROPERTIES
  // ============================================================================

  /**
   * Unmapped CSV fields (fields defined in mapping but not resolved)
   * Used to warn users about missing mappings
   * @type {ComputedRef<Array<string>>}
   */
  const unmapped = computed(() => {
    if (!csvMapping) return []
    const { resolvedFlat } = csvMapping
    const missing = []
    for (const sec of ['document', 'image']) {
      Object.entries(resolvedFlat[sec] || {}).forEach(([key, val]) => {
        if (!val) missing.push(`${sec}.${key}`)
      })
    }
    return missing
  })

  // ============================================================================
  // USER INTERACTION FUNCTIONS
  // ============================================================================

  /**
   * Opens native folder picker dialog for input folder selection
   * @async
   * @returns {Promise<void>}
   */
  const selectFolder = async () => {
    const f = await window.electronAPI.selectFolder()
    if (f) selectedFolder.value = f
  }

  /**
   * Opens native folder picker dialog for output folder selection
   * @async
   * @returns {Promise<void>}
   */
  const selectOutput = async () => {
    const f = await window.electronAPI.selectOutputFolder()
    if (f) selectedOutput.value = f
  }

  /**
   * Closes the result notification modal
   */
  const closeResultModal = () => {
    showResultModal.value = false
  }

  /**
   * Starts the image/video processing workflow
   *
   * Processing stages:
   * 1. Convert images to WebP + generate thumbnails
   * 2. Optionally crop images (Python OpenCV)
   * 3. Optionally optimize videos (FFmpeg)
   * 4. Organize files by CSV metadata (if CSV exists)
   * 5. Create ZIP archive
   *
   * In preview mode:
   * - Processes only 4 images
   * - Shows file sizes
   * - Auto-deletes results after 60 seconds
   *
   * @async
   * @returns {Promise<Object>} Result object with success status and output paths
   * @throws {Error} If processing fails in backend
   */
  const startProcess = async () => {
    // Clear any existing preview cleanup timer
    if (previewCleanupTimer.value) {
      clearTimeout(previewCleanupTimer.value)
      previewCleanupTimer.value = null
    }

    // Reset all progress state
    processing.value = true
    loadingText.value = 'Conteggio cartelle in corso...'
    progressText.value = ''
    csvText.value = ''
    percent.value = 0
    foldersStatus.value = []
    showFolderProgress.value = false
    currentThumbnail.value = ''

    // Prepare CSV mapping for backend (nested structure)
    const { unflattenMap, resolvedFlat } = csvMapping
    const finalMap = unflattenMap(resolvedFlat)

    const res = await window.electronAPI.processImages(
      selectedFolder.value,
      selectedOutput.value,
      maxCsvLine.value,
      crop.value,
      finalMap,
      optimizeVideos.value,
      optimizeImages.value,
      previewMode.value,
      aggressivity.value
    )

    processing.value = false
    loadingText.value = ''
    showFolderProgress.value = false

    // Handle preview mode results
    if (previewMode.value && res.success && res.previewFileSizes && res.previewFileSizes.length > 0) {
      previewFileSizes.value = res.previewFileSizes
      const totalSize = res.previewFileSizes.reduce((sum, f) => sum + f.size, 0)
      const avgSize = totalSize / res.previewFileSizes.length

      // Sort files by size for better readability
      const sortedFiles = [...res.previewFileSizes].sort((a, b) => a.size - b.size)

      resultMessage.value = `ANTEPRIMA COMPLETATA\n\n` +
        `File elaborati: ${res.previewFileSizes.length}\n\n` +
        `Dimensioni file:\n` +
        sortedFiles.map(f => `  ${f.name}: ${(f.size / 1024).toFixed(1)} KB`).join('\n') +
        `\n\n` +
        `STATISTICHE:\n` +
        `  Dimensione minima: ${(sortedFiles[0].size / 1024).toFixed(1)} KB\n` +
        `  Dimensione massima: ${(sortedFiles[sortedFiles.length - 1].size / 1024).toFixed(1)} KB\n` +
        `  Dimensione media: ${(avgSize / 1024).toFixed(1)} KB\n` +
        `  Dimensione totale: ${(totalSize / 1024).toFixed(1)} KB\n\n` +
        'I file verranno automaticamente eliminati tra 60 secondi.'

      // Auto-cleanup after 60 seconds
      previewCleanupTimer.value = setTimeout(async () => {
        await window.electronAPI.cleanupPreview(res.outputDir)
        previewFileSizes.value = null
        resultMessage.value += '\n\nFile di anteprima eliminati.'
      }, 60000)
    } else if (previewMode.value && res.success && (!res.previewFileSizes || res.previewFileSizes.length === 0)) {
      resultMessage.value = 'Anteprima completata, ma nessuna immagine trovata. Verifica che la cartella contenga file immagine (TIF, JPG, PNG).'
    } else {
      resultMessage.value = res.success ? 'Processamento completato con successo!' : 'Errore: ' + (res.error || '')
    }

    resultSuccess.value = res.success
    showResultModal.value = true

    return res
  }

  /**
   * Stops the currently running processing workflow
   * Sends stop signal to Electron backend
   */
  const stopProcess = () => {
    if (processing.value) window.electronAPI.stopProcessing()
  }

  // ============================================================================
  // ELECTRON IPC EVENT LISTENERS
  // Listen for progress updates from backend worker processes
  // ============================================================================

  onMounted(() => {
    /**
     * Main progress update handler
     * Receives updates from image/video processing workers
     * Updates: percentage, folder status, current file, thumbnails
     */
    window.electronAPI.onProgressUpdate(progress => {
      if (progress.type === 'video_processing') {
        videoProcessingMessage.value = progress.message || 'Attendere, processamento video in corso...'
      } else {
        videoProcessingMessage.value = ''
      }

      loadingText.value = ''

      if (progress.foldersStatus && progress.foldersStatus.length > 0) {
        foldersStatus.value = progress.foldersStatus
        showFolderProgress.value = true
      } else {
        showFolderProgress.value = false
      }

      const { current, total, currentFile, folderIdx, folderTotal, currentFolder } = progress
      if (total) percent.value = Math.floor((current / total) * 100)
      let t = ''
      if (folderIdx && folderTotal && currentFolder) t += `Cartella ${folderIdx} di ${folderTotal}: ${currentFolder}\n`
      if (current != null && total != null && currentFile) t += `File ${current} di ${total}: ${currentFile}`
      progressText.value = t

      if (typeof progress.globalImagesTotal === 'number') globalImagesTotal.value = progress.globalImagesTotal
      if (typeof progress.globalImagesProcessed === 'number') globalImagesProcessed.value = progress.globalImagesProcessed

      // Update current thumbnail for live preview
      if (progress.currentThumbnail) {
        currentThumbnail.value = progress.currentThumbnail
      }
    })

    /**
     * CSV organization progress handler
     * Called during CSV-based file organization phase
     * Shows which CSV rows are being processed
     */
    window.electronAPI.onCsvProgress(p => {
      showFolderProgress.value = false
      percent.value = 100
      const { current, total, codice } = p
      let t = `Organizzazione CSV: ${current} di ${total}`
      if (codice) t += `\nUltimo: ${codice}`
      csvText.value = t
    })
  })

  // ============================================================================
  // PUBLIC API
  // All state and functions exposed to components
  // ============================================================================

  return {
    // State
    selectedFolder,
    selectedOutput,
    optimizeImages,
    previewMode,
    aggressivity,
    crop,
    optimizeVideos,
    maxCsvLine,
    processing,
    percent,
    loadingText,
    progressText,
    csvText,
    showCsvInput,
    foldersStatus,
    showFolderProgress,
    globalImagesTotal,
    globalImagesProcessed,
    videoProcessingMessage,
    currentThumbnail,
    showResultModal,
    resultSuccess,
    resultMessage,
    previewFileSizes,
    previewCleanupTimer,

    // Computed
    unmapped,

    // Functions
    selectFolder,
    selectOutput,
    closeResultModal,
    startProcess,
    stopProcess
  }
}
