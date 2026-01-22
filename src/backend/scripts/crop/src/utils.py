"""
utils.py

Funzioni di utilità per il processing delle immagini.
"""

import cv2
import numpy as np


def resize_width_hd(img, target_width=1920):
    """Ridimensiona l'immagine mantenendo il rapporto d'aspetto, dato un target_width."""
    h, w = img.shape[:2]
    scale = target_width / w
    new_h = int(h * scale)
    resized = cv2.resize(img, (target_width, new_h), interpolation=cv2.INTER_AREA)
    return resized


def parabola(x, a, b, c):
    """Funzione parabolica per fit."""
    return a*x**2 + b*x + c
