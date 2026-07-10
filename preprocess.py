"""
Image preprocessing before OCR.

WhatsApp/Telegram compress forwarded screenshots hard. Raw OCR on a
compressed image regularly confuses I/1, O/0, and drops thin strokes.
Grayscale + adaptive thresholding recovers most of that accuracy for
almost no cost. Keep this step even if it feels too simple to matter --
it consistently does.
"""

import cv2
import numpy as np
from PIL import Image
import io


def preprocess_for_ocr(image_bytes: bytes) -> np.ndarray:
    """
    Take raw image bytes (as received from a Telegram photo download)
    and return a cleaned-up OpenCV image array ready for OCR.
    """
    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    # Upscale small screenshots -- OCR engines do noticeably worse
    # below ~1000px on the long edge, and compressed forwards are
    # often smaller than that.
    h, w = img.shape[:2]
    long_edge = max(h, w)
    if long_edge < 1000:
        scale = 1000 / long_edge
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Adaptive thresholding handles uneven screenshot backgrounds
    # (chat bubbles, dark mode, watermarks) far better than a single
    # global threshold would.
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=15,
    )

    # Light denoise to clean up JPEG compression artifacts without
    # eroding character strokes.
    denoised = cv2.fastNlMeansDenoising(thresh, h=10)

    return denoised
