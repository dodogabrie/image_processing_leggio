import { ref, reactive, computed, watch } from 'vue'

/**
 * Composable for managing file explorer functionality
 *
 * Provides a file browser interface for navigating processed image output folders.
 * Features include:
 * - Folder/file tree navigation with breadcrumbs
 * - Thumbnail preview caching
 * - Metadata loading (folder-level JSON files)
 * - Original vs processed image comparison support
 * - Integration with Electron file system APIs
 *
 * Directory Structure Expected:
 * - organized/        - Final organized files (by CSV groupBy field)
 * - organized_thumbnails/ - Thumbnail versions
 * - metadata.json     - Folder metadata files
 *
 * @returns {Object} Explorer state and navigation functions
 *
 * @example
 * const explorer = useExplorer()
 *
 * // Initialize after processing
 * await explorer.initializeExplorer(outputDir, organizedDir, thumbsDir)
 *
 * // Navigate folders
 * await explorer.openFolder(folderPath)
 * await explorer.goToBreadcrumb(breadcrumbPath)
 */
export function useExplorer() {
  // ============================================================================
  // EXPLORER STATE
  // Tracks current directory, entries, and navigation history
  // ============================================================================

  /** @type {Ref<string>} Base output directory (fallback if organized doesn't exist) */
  const lastOutputDir = ref('')

  /** @type {Ref<string>} Path to organized/ folder (CSV-organized structure) */
  const organizedRoot = ref('')

  /** @type {Ref<string>} Path to organized_thumbnails/ folder */
  const thumbnailsRoot = ref('')

  /** @type {Ref<string>} Currently displayed directory path */
  const currentExplorerDir = ref('')

  /** @type {Ref<Array>} Files and folders in current directory */
  const explorerEntries = ref([])

  /** @type {Ref<Array>} Breadcrumb navigation trail [{name, path}, ...] */
  const explorerBreadcrumbs = ref([])

  /** @type {Ref<boolean>} Whether directory contents are being loaded */
  const explorerLoading = ref(false)

  /** @type {Ref<string>} Error message if directory loading fails */
  const explorerError = ref('')

  /** @type {Ref<Object>} Cache of thumbnail data URLs {path: dataUrl} */
  const thumbnailCache = ref({})

  /** @type {Ref<Object|null>} Folder metadata from metadata.json */
  const folderMetadata = ref(null)

  /** @type {Ref<string>} Status message for folder metadata loading */
  const folderMetadataStatus = ref('')

  /** @type {Ref<boolean>} Whether thumbnails are currently loading */
  const thumbLoading = ref(false)

  /** @type {Ref<string>} Path to original images folder (for comparison) */
  const originalRoot = ref('')

  // ============================================================================
  // CONSTANTS
  // ============================================================================

  /**
   * Placeholder thumbnail shown while images load
   * SVG data URL with gradient background
   * @const {string}
   */
  const placeholderThumb = 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22240%22 height=%22160%22 viewBox=%220 0 240 160%22%3E%3Cdefs%3E%3ClinearGradient id=%22g%22 x1=%220%25%22 y1=%220%25%22 x2=%22100%25%22 y2=%220%25%22%3E%3Cstop offset=%220%25%22 stop-color=%22%23eef1f6%22/%3E%3Cstop offset=%2250%25%22 stop-color=%22%23f6f8fb%22/%3E%3Cstop offset=%22100%25%22 stop-color=%22%23eef1f6%22/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width=%22240%22 height=%22160%22 fill=%22url(%23g)%22/%3E%3Crect x=%2236%22 y=%2232%22 width=%22168%22 height=%2296%22 rx=%2212%22 fill=%22%23e3e7ef%22/%3E%3C/svg%3E'

  // Computed properties
  const explorerRoot = computed(() => organizedRoot.value || lastOutputDir.value)
  const foldersOnly = computed(() => explorerEntries.value.filter(e => e.type === 'directory'))
  const imagesOnly = computed(() => explorerEntries.value.filter(e => e.isImage))
  const folderDocument = computed(() => folderMetadata.value?.document || null)

  const formatDocKey = (key = '') => key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())

  const folderDocumentEntries = computed(() => {
    if (!folderDocument.value) return []
    return Object.entries(folderDocument.value).map(([key, value]) => ({
      key,
      label: formatDocKey(key),
      value
    }))
  })

  // Utility function
  const joinPath = (base, segment) => {
    if (!base) return segment
    if (base.endsWith('/') || base.endsWith('\\')) return `${base}${segment}`
    return `${base}/${segment}`
  }

  // Functions
  const loadFolderMetadata = async (dir) => {
    folderMetadata.value = null
    folderMetadataStatus.value = ''
    if (!dir) return

    const candidates = ['medatata.json', 'metadata.json']
    for (const candidate of candidates) {
      const metaPath = joinPath(dir, candidate)
      try {
        const data = await window.electronAPI.readJsonFile(metaPath)
        if (data) {
          folderMetadata.value = data
          folderMetadataStatus.value = `Fonte: ${candidate}`
          return
        }
      } catch (err) {
        const isMissing = err?.message?.toLowerCase().includes('enoent') || err?.code === 'ENOENT'
        if (!isMissing) {
          folderMetadataStatus.value = 'Errore caricando metadati cartella'
          console.warn('Errore metadati cartella', err)
          return
        }
      }
    }
    folderMetadataStatus.value = 'Metadati cartella non disponibili'
  }

  const loadExplorer = async (dirToLoad, allowFallback = true) => {
    if (!dirToLoad) return
    explorerLoading.value = true
    explorerError.value = ''

    try {
      const res = await window.electronAPI.listEntriesDetailed(
        dirToLoad,
        organizedRoot.value,
        thumbnailsRoot.value
      )
      if (res.error) throw new Error(res.error)

      explorerEntries.value = res.entries || []
      explorerBreadcrumbs.value = res.breadcrumbs || []
      currentExplorerDir.value = dirToLoad
      await loadFolderMetadata(dirToLoad)
    } catch (err) {
      const isMissingOrganized = err?.message?.includes('ENOENT') && dirToLoad.includes('organized')
      if (allowFallback && lastOutputDir.value && dirToLoad !== lastOutputDir.value) {
        await loadExplorer(lastOutputDir.value, false)
        return
      }
      if (isMissingOrganized && lastOutputDir.value) {
        explorerError.value = ''
      } else {
        explorerError.value = err?.message || 'Impossibile leggere la cartella selezionata.'
      }
      console.warn('Errore caricando contenuto cartella', err?.message || err)
      explorerEntries.value = []
    } finally {
      explorerLoading.value = false
    }
  }

  const initializeExplorer = async (baseDir, organizedDir = null, thumbsDir = null) => {
    if (!baseDir) return
    lastOutputDir.value = baseDir
    organizedRoot.value = organizedDir || joinPath(baseDir, 'organized')
    thumbnailsRoot.value = thumbsDir || joinPath(baseDir, 'organized_thumbnails')

    const initialDir = organizedDir || organizedRoot.value || baseDir
    await loadExplorer(initialDir, true)
  }

  const refreshExplorer = async () => {
    const target = currentExplorerDir.value || organizedRoot.value || lastOutputDir.value
    if (target) await loadExplorer(target)
  }

  const openFolder = async (folderPath) => {
    await loadExplorer(folderPath)
  }

  const goToBreadcrumb = async (path) => {
    await loadExplorer(path)
  }

  const pickProcessedFolder = async () => {
    const dir = await window.electronAPI.selectOutputFolder()
    if (dir) {
      await initializeExplorer(dir)
    }
  }

  const selectOriginalRoot = async () => {
    const dir = await window.electronAPI.selectFolder()
    if (dir) {
      originalRoot.value = dir
    }
  }

  /**
   * Watcher to preload thumbnails when explorer entries change
   * Loads all image thumbnails in parallel and caches them as data URLs
   * Handles errors gracefully by using placeholder thumbnail
   */
  watch(explorerEntries, async (entries) => {
    if (!entries || !entries.length) return
    thumbLoading.value = true
    const images = entries.filter(e => e.isImage)
    const updatedCache = { ...thumbnailCache.value }

    try {
      await Promise.all(images.map(async img => {
        // Extract thumbnail path, ensure it's a string not a ref
        const key = (img.thumbnailPath || img.path)

        // Skip if no valid path or already cached
        if (!key || typeof key !== 'string' || !key.trim() || updatedCache[key]) return

        try {
          const dataUrl = await window.electronAPI.readThumbnailAsDataUrl(key)
          updatedCache[key] = dataUrl || placeholderThumb
        } catch (err) {
          console.error('Errore caricando thumbnail', key, err)
          updatedCache[key] = placeholderThumb
        }
      }))
      thumbnailCache.value = updatedCache
    } finally {
      thumbLoading.value = false
    }
  }, { deep: true })

  return {
    // State
    lastOutputDir,
    organizedRoot,
    thumbnailsRoot,
    currentExplorerDir,
    explorerEntries,
    explorerBreadcrumbs,
    explorerLoading,
    explorerError,
    thumbnailCache,
    folderMetadata,
    folderMetadataStatus,
    thumbLoading,
    originalRoot,
    placeholderThumb,

    // Computed
    explorerRoot,
    foldersOnly,
    imagesOnly,
    folderDocument,
    folderDocumentEntries,

    // Functions
    loadFolderMetadata,
    loadExplorer,
    initializeExplorer,
    refreshExplorer,
    openFolder,
    goToBreadcrumb,
    pickProcessedFolder,
    selectOriginalRoot,
    joinPath
  }
}
