# util.py
import re
import os
import cv2
import numpy as np
from collections import Counter
from rapidfuzz import fuzz
import easyocr

# =====================================
# 🔧 INICIALIZACIÓN DE EASYOCR GLOBAL
# =====================================

print("🧠 Inicializando EasyOCR... (puede tardar unos segundos)")
try:
    reader = easyocr.Reader(['es', 'en'], gpu=True)
    print("✅ EasyOCR inicializado con GPU")
except Exception:
    reader = easyocr.Reader(['es', 'en'], gpu=False)
    print("⚠️ EasyOCR inicializado en CPU (sin GPU disponible)")

# =====================================
# 🔠 MAPEOS Y FORMATOS DE PLACAS
# =====================================

DICT_CHAR_TO_INT = {'O': '0', 'Q': '0', 'D': '0', 'I': '1', 'L': '1', 'B': '8', 'S': '5', 'G': '6', 'Z': '2'}
DICT_INT_TO_CHAR = {'0': 'O', '1': 'I', '2': 'Z', '3': 'B', '4': 'A', '5': 'S', '6': 'G', '8': 'B'}

PLATE_PATTERNS = [
    r'^[A-Z]{3}[0-9]{3}$',       # Autos (ABC123)
    r'^[A-Z]{3}[0-9]{2}[A-Z]$',  # Motos (ABC12D)
    r'^[0-9]{3}[A-Z]{3}$',       # Mototaxi (123ABC)
    r'^[A-Z]{2}[0-9]{4}$',       # Variantes nuevas
    r'^[A-Z]{3}[0-9]{2}$',       # Placas incompletas
]

MIN_PLATE_LEN = 3


# =====================================
# 🔤 FORMATO Y LIMPIEZA DE TEXTO
# =====================================

def format_license(text):
    """Normaliza el texto de la placa (corrige letras/números comunes)."""
    if not text:
        return ""
    text = text.upper().replace(' ', '').replace('-', '').replace('.', '').replace('·', '')
    chars = list(text)
    for i in range(min(3, len(chars))):
        if chars[i] in DICT_INT_TO_CHAR:
            chars[i] = DICT_INT_TO_CHAR[chars[i]]
    for i in range(3, min(6, len(chars))):
        if chars[i] in DICT_CHAR_TO_INT:
            chars[i] = DICT_CHAR_TO_INT[chars[i]]
    return ''.join(chars)


def license_complies_format(text):
    """Valida si el texto cumple formato de placa."""
    if not text:
        return False
    for pattern in PLATE_PATTERNS:
        if re.fullmatch(pattern, text):
            return True
    return False


def extra_clean_license(text):
    """Limpieza adicional: elimina duplicados y símbolos no válidos."""
    text = text.upper()
    text = re.sub(r'[^A-Z0-9]', '', text)
    text = re.sub(r'(.)\1+', r'\1', text)
    return format_license(text)


# =====================================
# 🧠 PREPROCESAMIENTO DE IMAGEN DE PLACA
# =====================================

def preprocess_plate(plate_img):
    """Mejora la imagen para OCR."""
    if plate_img is None or plate_img.size == 0:
        return None

    h, w = plate_img.shape[:2]
    if h < 40 or w < 100:
        scale = max(40 / h, 100 / w)
        plate_img = cv2.resize(plate_img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    enhanced = cv2.GaussianBlur(enhanced, (3, 3), 1.2)
    kernel = np.ones((2, 2), np.uint8)
    enhanced = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, kernel)

    return enhanced


# =====================================
# 🔍 LECTURA DE PLACA
# =====================================

def read_license_plate(license_crop):
    """
    Devuelve (texto_normalizado, score)
    usando EasyOCR global (reader).
    """
    if license_crop is None or license_crop.size == 0:
        return None, 0.0

    # Intento 1 — imagen original
    try:
        detections = reader.readtext(license_crop)
    except Exception:
        detections = []

    for _, text, score in detections:
        clean = extra_clean_license(text)
        if len(clean) < MIN_PLATE_LEN:
            continue
        if license_complies_format(clean) and score > 0.45:
            return clean, float(score)

    # Intento 2 — imagen mejorada
    processed = preprocess_plate(license_crop)
    if processed is not None:
        try:
            detections2 = reader.readtext(processed)
        except Exception:
            detections2 = []
        for _, text, score in detections2:
            clean = extra_clean_license(text)
            if len(clean) < MIN_PLATE_LEN:
                continue
            if license_complies_format(clean) and score > 0.4:
                return clean, float(score) * 0.95

    return None, 0.0


# =====================================
# 🧮 CONSOLIDAR BUFFER DE LECTURAS
# =====================================

def consolidar_buffer(buffer):
    """Agrupa lecturas similares ponderando por score y frecuencia."""
    if not buffer:
        return None, 0.0

    normalized = [(format_license(t), float(s)) for t, s in buffer if t and len(t) >= MIN_PLATE_LEN]
    if not normalized:
        return None, 0.0

    clusters = []
    for text, score in normalized:
        added = False
        for cluster in clusters:
            rep = cluster[0][0]
            if fuzz.ratio(text, rep) > 88:
                cluster.append((text, score))
                added = True
                break
        if not added:
            clusters.append([(text, score)])

    best_cluster = max(clusters, key=lambda c: sum(x[1] for x in c) + len(c) * 0.2)
    texts = [t for t, _ in best_cluster]
    freq = Counter(texts)
    best_text = max(freq.items(), key=lambda x: (x[1], x[0]))[0]
    best_score = np.mean([s for t, s in best_cluster if t == best_text])

    if freq[best_text] >= 3 and best_score > 0.6:
        return best_text, best_score

    return best_text, best_score


# =====================================
# 🚗 VEHÍCULO MÁS CERCANO Y DIRECCIÓN
# =====================================

def seleccionar_mas_cercano(tracks):
    """Devuelve el track con mayor área (vehículo más cercano)."""
    if tracks is None or (hasattr(tracks, "__len__") and len(tracks) == 0):
        return None

    max_area = 0
    best_track = None
    for t in tracks:
        tx1, ty1, tx2, ty2, sort_id = t
        area = (tx2 - tx1) * (ty2 - ty1)
        if area > max_area:
            max_area = area
            best_track = (tx1, ty1, tx2, ty2, int(sort_id), area)
    return best_track


def infer_direction_from_history(history_deque, sign=1, min_samples=6, motion_threshold_px=10):
    """Infere si el vehículo entra o sale."""
    if not history_deque or len(history_deque) < min_samples:
        return "indeterminado"

    first = history_deque[0]
    last = history_deque[-1]
    _, area_first, cy_first, _ = first
    _, area_last, cy_last, _ = last

    dy = (cy_last - cy_first) * sign
    darea = area_last - area_first

    if abs(dy) < motion_threshold_px and abs(darea) < 1:
        return "indeterminado"
    if dy < 0 and darea > -1:
        return "entrada"
    elif dy > 0 and darea < 1:
        return "salida"
    else:
        if darea > 500:
            return "entrada"
        if darea < -500:
            return "salida"
    return "indeterminado"
