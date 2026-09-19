from pathlib import Path


def preprocess_image(image):
    import cv2
    import numpy as np
    if image is None or image.size == 0:
        raise ValueError("The image appears to be empty.")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    contrast = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(denoised)
    thresholded = cv2.adaptiveThreshold(contrast, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)
    coordinates = np.column_stack(np.where(thresholded < 255))
    if len(coordinates) < 20:
        return thresholded
    angle = cv2.minAreaRect(coordinates)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 0.5 or abs(angle) > 15:
        return thresholded
    height, width = thresholded.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(thresholded, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def load_pages(path: Path):
    if path.suffix.lower() == ".pdf":
        from pdf2image import convert_from_path
        return [__import__("numpy").array(page) for page in convert_from_path(path, dpi=250)]
    import cv2
    image = cv2.imread(str(path))
    return [image]
