import { onMounted, onBeforeUnmount } from 'vue'

export function useKeyboardNavigation(imageModal) {
  const { modalIndex, showPrevImage, showNextImage, closeImageModal } = imageModal

  const handleKeyNavigation = async (event) => {
    if (modalIndex.value < 0) return
    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      await showPrevImage()
    } else if (event.key === 'ArrowRight') {
      event.preventDefault()
      await showNextImage()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      closeImageModal()
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', handleKeyNavigation)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('keydown', handleKeyNavigation)
  })
}
