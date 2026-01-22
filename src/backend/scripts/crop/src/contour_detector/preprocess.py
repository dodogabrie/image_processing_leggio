import cv2
import numpy as np

from .utils import show_image


def rgb_to_gray_from_tuple(bgr):
    """
    Converte una tripla (B, G, R) in valore scala di grigi usando la formula BT.601.

    Args:
        bgr (tuple[float, float, float]): Valori medi BGR.

    Returns:
        float: Valore di grigio corrispondente.
    """
    b, g, r = bgr
    return 0.114 * b + 0.587 * g + 0.299 * r


def estimate_threshold_and_border_rgb(image, gray_blurred):
    """
    Calcola una soglia binaria dinamica e il valore medio RGB dei bordi dell'immagine.

    Args:
        image (np.ndarray): Immagine BGR originale (uint8).
        gray_blurred (np.ndarray): Immagine sfocata in scala di grigi (uint8).

    Returns:
        int: Valore di soglia stimato per la binarizzazione (0–255).
        tuple[float, float, float]: Valore medio (B, G, R) dei bordi in float32.
    """
    h, w = gray_blurred.shape
    min_dim = min(h, w)
    center = int(min_dim * 0.3) // 2  # 10% per il centro

    # Calcola media RGB dei 4 angoli (patch 3x3)
    patches = []

    # Top-left
    patches.append(image[0:3, 0:3])

    # Top-right
    patches.append(image[0:3, -3:])

    # Bottom-left
    patches.append(image[-3:, 0:3])

    # Bottom-right
    patches.append(image[-3:, -3:])

    # Concatena e calcola la media RGB
    border_pixels = np.concatenate([p.reshape(-1, 3) for p in patches], axis=0).astype(
        np.float32
    )
    border_rgb = tuple(border_pixels.mean(axis=0))  # B, G, R

    # Converti media RGB in grigio
    border_gray = rgb_to_gray_from_tuple(border_rgb)

    # Calcola media nel centro dell'immagine grigia
    cx, cy = w // 2, h // 2
    center_patch = gray_blurred[cy - center : cy + center, cx - center : cx + center]
    center_mean = center_patch.mean(dtype=np.float32)

    # Interpolazione pesata
    alpha = 0.6
    threshold_val = int(
        np.clip(border_gray + (center_mean - border_gray) * alpha, 0, 255)
    )

    border_val = tuple(int(round(c)) for c in border_rgb)
    return threshold_val, border_val


def smooth_edges(thresh, show_step_by_step=False):
    """
    Esegue erosione seguita da dilatazione (opening) per eliminare piccole irregolarità.

    Args:
        thresh (np.ndarray): Immagine binaria (uint8).
        show_step_by_step (bool): Se True, mostra i passaggi.

    Returns:
        np.ndarray: Immagine con bordi più lisci.
    """
    kernel = np.ones((20, 20), np.uint8)
    eroded = cv2.erode(thresh, kernel, iterations=5)
    dilated = cv2.dilate(eroded, kernel, iterations=5)

    if show_step_by_step:
        show_image(eroded, "Eroded")
        show_image(dilated, "Dilated after Erosion")

    return dilated


def refine_mask_morphology(thresh, show_step_by_step=False):
    """
    Applica chiusura e apertura morfologica per rendere i bordi più regolari.

    Args:
        thresh (np.ndarray): Immagine binaria (uint8).
        show_step_by_step (bool): Se True, mostra i passaggi.

    Returns:
        np.ndarray: Maschera binaria raffinata.
    """
    kernel_close = np.ones((15, 15), np.uint8)
    kernel_open = np.ones((5, 5), np.uint8)

    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel_close)
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel_open)

    if show_step_by_step:
        show_image(closed, "After Morphological Close")
        show_image(opened, "After Morphological Open")

    return opened


def fill_internal_holes(thresh, show_step_by_step=False):
    """
    Riempie i buchi interni nell'immagine binaria per migliorare la detection del contorno esterno.

    Args:
        thresh (np.ndarray): Immagine binaria (uint8).
        show_step_by_step (bool): Se True, mostra i passaggi.

    Returns:
        np.ndarray: Immagine con buchi interni riempiti.
    """
    h, w = thresh.shape

    # Check if document is too close to edges (would break flood fill)
    # Sample a thin border region (5 pixels) on all sides
    border_width = 5
    top_border = thresh[0:border_width, :]
    bottom_border = thresh[h-border_width:h, :]
    left_border = thresh[:, 0:border_width]
    right_border = thresh[:, w-border_width:w]

    # Calculate percentage of white pixels in border regions
    top_white_pct = np.sum(top_border == 255) / top_border.size
    bottom_white_pct = np.sum(bottom_border == 255) / bottom_border.size
    left_white_pct = np.sum(left_border == 255) / left_border.size
    right_white_pct = np.sum(right_border == 255) / right_border.size

    # If any edge has >50% white pixels, document is touching edges
    edge_threshold = 0.5
    document_touches_edges = (
        top_white_pct > edge_threshold or
        bottom_white_pct > edge_threshold or
        left_white_pct > edge_threshold or
        right_white_pct > edge_threshold
    )

    if document_touches_edges:
        if show_step_by_step:
            print(f"[SKIP FLOOD FILL] Document touches image edges:")
            print(f"  Top: {top_white_pct*100:.1f}%, Bottom: {bottom_white_pct*100:.1f}%")
            print(f"  Left: {left_white_pct*100:.1f}%, Right: {right_white_pct*100:.1f}%")
            print(f"  Skipping flood fill to avoid breaking the mask")

        # Skip flood fill method 1, only use morphological closing
        morph_result = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, np.ones((50, 50), np.uint8))

        if show_step_by_step:
            show_image(morph_result, "Morphological closing (flood fill skipped)")

        return morph_result

    # Helper function to check if mask is broken (all white or all black)
    def is_mask_broken(mask_img, name="mask"):
        """Check if mask is completely white or black (broken)."""
        total_pixels = mask_img.size
        white_pixels = np.sum(mask_img == 255)
        black_pixels = np.sum(mask_img == 0)

        white_pct = white_pixels / total_pixels
        black_pct = black_pixels / total_pixels

        # Consider broken if >98% all white or all black
        is_broken = white_pct > 0.98 or black_pct > 0.98

        if is_broken and show_step_by_step:
            print(f"[WARNING] {name} is broken: {white_pct*100:.1f}% white, {black_pct*100:.1f}% black")

        return is_broken

    # Metodo 1: Flood fill dai bordi per identificare il background
    filled = thresh.copy()

    # Crea una maschera leggermente più grande per flood fill
    mask = np.zeros((h + 2, w + 2), np.uint8)

    # Flood fill da tutti i 4 angoli (riempie tutto il background connesso ai bordi)
    cv2.floodFill(filled, mask, (0, 0), 255)
    cv2.floodFill(filled, mask, (w - 1, 0), 255)
    cv2.floodFill(filled, mask, (0, h - 1), 255)
    cv2.floodFill(filled, mask, (w - 1, h - 1), 255)

    # Check if flood fill broke the mask
    filled_broken = is_mask_broken(filled, "Flood filled mask")

    # Inverti per ottenere solo le aree che non sono background
    filled_inverted = cv2.bitwise_not(filled)

    # Combina con l'originale: mantieni tutto ciò che era già bianco + aree interne isolate
    flood_result = cv2.bitwise_or(thresh, filled_inverted)

    # Check if flood result is broken
    flood_broken = is_mask_broken(flood_result, "Flood result")

    # Metodo 2: Morphological closing aggressivo per riempire buchi
    kernel_large = np.ones((50, 50), np.uint8)
    morph_result = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel_large)

    # Check if morph result is broken
    morph_broken = is_mask_broken(morph_result, "Morph result")

    # Metodo 3: Combinazione dei due approcci
    # Only use valid (non-broken) results in the combined approach
    if flood_broken and morph_broken:
        # Both methods failed - return original thresh
        if show_step_by_step:
            print("[FALLBACK] Both flood fill and morph failed - returning original thresh")
        combined = thresh
    elif flood_broken:
        # Flood fill failed - use only morph result
        if show_step_by_step:
            print("[FALLBACK] Flood fill failed - using only morph result")
        combined = morph_result
    elif morph_broken:
        # Morph failed - use only flood result
        if show_step_by_step:
            print("[FALLBACK] Morph failed - using only flood result")
        combined = flood_result
    else:
        # Both methods valid - combine them
        combined = cv2.morphologyEx(
            flood_result, cv2.MORPH_CLOSE, np.ones((50, 50), np.uint8)
        )

    if show_step_by_step:
        show_image(filled, "After flood fill from borders")
        show_image(flood_result, "After hole filling with flood fill")
        show_image(morph_result, "After morphological closing")
        show_image(combined, "Combined approach")

    return combined


def preprocess_image(image, show_step_by_step=False):
    """
    Converte l'immagine in scala di grigi, la sfoca, calcola soglia dinamica
    basata sui valori medi dei bordi e binarizza. Restituisce anche il valore RGB medio dei bordi.

    Args:
        image (np.ndarray): Immagine BGR originale (uint8).
        show_step_by_step (bool): Se True, mostra i passaggi.

    Returns:
        np.ndarray: Immagine binarizzata (uint8, 0 o 255).
        tuple[float, float, float]: Media (B, G, R) dei bordi in float32.
    """
    # Converte in scala di grigi
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if show_step_by_step:
        show_image(gray, "Grayscale")

    # Applica blur adattivo in base alla dimensione minima
    min_dim = min(gray.shape[:2])
    k = max(3, int((min_dim / 50) // 2 * 2 + 1))  # Kernel dispari, minimo 3
    k = min(k, 51)  # Massimo 51
    print(f"Kernel size: {k}x{k}")
    blurred = cv2.GaussianBlur(gray, (k, k), 0)
    if show_step_by_step:
        show_image(blurred, f"Blurred (kernel={k}x{k})")

    # Calcola soglia e valore RGB del bordo
    threshold_val, border_rgb = estimate_threshold_and_border_rgb(image, blurred)

    _, thresh = cv2.threshold(blurred, threshold_val, 255, cv2.THRESH_BINARY)

    thresh = refine_mask_morphology(thresh, False)

    thresh = smooth_edges(thresh, False)

    # Riempi i buchi interni per migliorare la detection del contorno esterno
    thresh = fill_internal_holes(thresh, show_step_by_step)

    if show_step_by_step:
        show_image(thresh, f"Final processed (th={threshold_val})")

    return thresh, border_rgb
