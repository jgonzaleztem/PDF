"""
Utilidades para OCR (Optical Character Recognition) en imágenes.

Este módulo proporciona funciones para extraer texto de imágenes,
evaluar la calidad del OCR, y generar texto alternativo adecuado
para cumplir con los requisitos de accesibilidad PDF/UA.

Relacionado con:
- Matterhorn: 08-001 (OCR con errores), 13-004 (Alt para imágenes), 13-008 (ActualText para imágenes con texto)
- Tagged PDF: 5.5.3 (ActualText), 5.5.2 (Alt)
"""

import os
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import cv2
import numpy as np
import io
import re
import sys
from loguru import logger
from typing import Dict, List, Optional, Tuple, Union, Any
import concurrent.futures

# Verificar disponibilidad de Tesseract al importar el módulo
def _check_tesseract_available():
    """Verifica si Tesseract OCR está disponible en el sistema."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except (ImportError, pytesseract.TesseractNotFoundError):
        logger.warning("Tesseract OCR no está disponible: tesseract is not installed or it's not in your PATH. See README file for more information.")
        logger.warning("El OCR no funcionará correctamente sin Tesseract instalado.")
        return False

# Constante global para verificar si Tesseract está disponible
TESSERACT_AVAILABLE = _check_tesseract_available()

# Idiomas soportados comunes
SUPPORTED_LANGUAGES = {
    'spa': 'Español',
    'eng': 'English',
    'fra': 'Français',
    'deu': 'Deutsch',
    'ita': 'Italiano',
    'por': 'Português',
    'cat': 'Català',
    'jpn': 'Japanese',
    'chi_sim': 'Chinese Simplified',
    'chi_tra': 'Chinese Traditional',
    'ara': 'Arabic',
    'rus': 'Russian'
}

def extract_text_from_image_data(image_bytes, lang='spa', config=''):
    """
    Extrae texto de datos binarios de imagen usando Tesseract OCR.
    
    Args:
        image_bytes (bytes): Datos binarios de la imagen
        lang (str): Idioma para OCR (spa, eng, fra, deu, etc.)
        config (str): Configuración adicional para Tesseract
        
    Returns:
        str: Texto extraído
    """
    if not _check_tesseract_available():
        return "OCR no disponible: Tesseract no instalado"
        
    try:
        # Convertir bytes a imagen PIL
        img = Image.open(io.BytesIO(image_bytes))
        
        # Verificar si la imagen necesita preprocesamiento
        # Convertir a escala de grises si es color
        if img.mode != 'L':
            img = img.convert('L')
        
        # Mejor resolución para OCR
        if img.width < 1000 and img.height < 1000:
            img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
            
        # Procesar con Tesseract
        text = pytesseract.image_to_string(img, lang=lang, config=config)
        
        # Limpiar resultado
        text = text.strip()
        
        return text
    except Exception as e:
        logger.error(f"Error en OCR: {str(e)}")
        return ""

def extract_text_from_cv_image(cv_image: np.ndarray, lang: str = 'spa', config: str = '', preprocess: bool = True) -> str:
    """
    Extrae texto de una imagen OpenCV usando Tesseract OCR.
    
    Args:
        cv_image: Imagen OpenCV
        lang: Idioma para OCR (spa, eng, fra, deu, etc.)
        config: Configuración adicional para Tesseract
        preprocess: Si se debe preprocesar la imagen para mejorar el OCR
        
    Returns:
        str: Texto extraído
    """
    if not TESSERACT_AVAILABLE:
        return ""
        
    try:
        # Aplicar preprocesamiento si se solicita
        if preprocess:
            cv_image = preprocess_image_for_ocr(cv_image)
            
        # Asegurar que la imagen está en RGB
        if len(cv_image.shape) == 2 or cv_image.shape[2] == 1:
            # Convertir a RGB si es grayscale
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_GRAY2RGB)
        elif cv_image.shape[2] == 3:
            # Asegurar que está en RGB, no BGR
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
            
        # Procesar con Tesseract usando configuración optimizada
        custom_config = f'-l {lang} --oem 1 --psm 3'
        if config:
            custom_config += f' {config}'
            
        text = pytesseract.image_to_string(cv_image, config=custom_config)
        
        # Limpiar resultado
        text = text.strip()
        
        return text
    except Exception as e:
        logger.error(f"Error en OCR con CV image: {str(e)}")
        return ""

def preprocess_image_for_ocr(cv_image: np.ndarray) -> np.ndarray:
    """
    Preprocesa una imagen para mejorar resultados de OCR.
    Aplica técnicas como umbralización adaptativa, reducción de ruido,
    y mejora de contraste.
    
    Args:
        cv_image: Imagen OpenCV
        
    Returns:
        np.ndarray: Imagen preprocesada
    """
    try:
        # Convertir a escala de grises si no lo está
        if len(cv_image.shape) == 3:
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = cv_image.copy()
        
        # Aplicar desenfoque bilateral para reducir ruido pero preservar bordes
        blur = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Aplicar umbral adaptativo
        thresh = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Aplicar operaciones morfológicas para limpiar la imagen
        kernel = np.ones((1, 1), np.uint8)
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel)
        
        # Aplicar filtro de mediana para reducir ruido
        processed = cv2.medianBlur(closing, 3)
        
        return processed
    except Exception as e:
        logger.error(f"Error en preprocesamiento de imagen: {str(e)}")
        return cv_image

def detect_if_image_has_text(cv_image: np.ndarray, confidence_threshold: float = 0.5) -> Dict[str, Any]:
    """
    Detecta si una imagen contiene texto y proporciona información detallada.
    
    Args:
        cv_image: Imagen OpenCV
        confidence_threshold: Umbral de confianza (0-1)
        
    Returns:
        Dict: {
            'has_text': bool,
            'confidence': float,
            'word_count': int,
            'text_type': str  # 'printed', 'handwritten', 'mixed', or 'unknown'
        }
    """
    if not TESSERACT_AVAILABLE:
        return {'has_text': False, 'confidence': 0.0, 'word_count': 0, 'text_type': 'unknown'}
        
    try:
        # Preprocesar imagen para mejorar detección
        processed_image = preprocess_image_for_ocr(cv_image)
        
        # Procesar con Tesseract a nivel de análisis de página
        data = pytesseract.image_to_data(processed_image, output_type=pytesseract.Output.DICT)
        
        # Contar palabras con confianza alta y calcular confianza promedio
        n_boxes = len(data['text'])
        confident_words = 0
        confidence_sum = 0
        confident_conf_sum = 0
        
        # Palabras no vacías
        non_empty_words = [i for i in range(n_boxes) if data['text'][i].strip()]
        
        for i in non_empty_words:
            word_conf = float(data['conf'][i])
            confidence_sum += word_conf
            
            if word_conf >= confidence_threshold * 100:
                confident_words += 1
                confident_conf_sum += word_conf
        
        # Calcular confianza promedio
        avg_confidence = confidence_sum / max(len(non_empty_words), 1) / 100
        
        # Determinar tipo de texto (impreso vs manuscrito)
        # Este es un heurístico básico; podría mejorarse con un modelo específico
        text_type = 'unknown'
        if confident_words > 0:
            # Si la confianza es muy alta, probablemente sea texto impreso
            if avg_confidence > 0.85:
                text_type = 'printed'
            # Si es moderada, podría ser manuscrito o mixto
            elif avg_confidence > 0.6:
                text_type = 'printed'  # Por defecto asumimos impreso
            else:
                text_type = 'handwritten'
        
        return {
            'has_text': confident_words > 0,
            'confidence': avg_confidence,
            'word_count': confident_words,
            'text_type': text_type
        }
    except Exception as e:
        logger.error(f"Error detectando texto en imagen: {str(e)}")
        return {'has_text': False, 'confidence': 0.0, 'word_count': 0, 'text_type': 'unknown'}

def estimate_ocr_quality(ocr_text: str, min_length: int = 10, lang: str = 'es') -> Dict[str, Any]:
    """
    Estima la calidad del texto OCR obtenido mediante análisis lingüístico
    y detección de errores comunes.
    
    Args:
        ocr_text: Texto extraído por OCR
        min_length: Longitud mínima para considerar texto válido
        lang: Idioma del texto para validación lingüística
        
    Returns:
        dict: {
            'valid': bool,
            'confidence': float (0-1),
            'reason': str,
            'errors': List[str],
            'length': int
        }
    """
    if not ocr_text or len(ocr_text) < min_length:
        return {
            'valid': False,
            'confidence': 0.0,
            'reason': "Texto demasiado corto o vacío",
            'errors': ["Texto demasiado corto"],
            'length': len(ocr_text) if ocr_text else 0
        }
    
    errors = []
    
    # Contar caracteres no alfabéticos ni espacios
    total_chars = len(ocr_text)
    non_alpha_count = sum(1 for c in ocr_text if not (c.isalpha() or c.isspace() or c.isdigit() or c in '.,-:;?!()[]{}"\'/'))
    
    # Calcular proporción de caracteres no alfabéticos
    non_alpha_ratio = non_alpha_count / total_chars if total_chars > 0 else 1.0
    
    # Si hay demasiados caracteres extraños, probablemente sea un error de OCR
    if non_alpha_ratio > 0.3:
        errors.append("Demasiados caracteres extraños")
    
    # Detectar líneas repetidas (error común en OCR)
    lines = ocr_text.split('\n')
    repeated_lines = len(lines) - len(set(lines))
    if repeated_lines > 0 and repeated_lines / len(lines) > 0.2:
        errors.append(f"{repeated_lines} líneas repetidas")
    
    # Detectar palabras sin sentido
    words = re.findall(r'\b\w+\b', ocr_text.lower())
    gibberish_words = 0
    
    # Palabras muy cortas o largas, o con patrones inusuales
    for word in words:
        if (len(word) > 2 and 
            (all(c == word[0] for c in word) or  # Toda la palabra es la misma letra
             re.match(r'^[^a-záéíóúüñ]{3,}$', word))):  # Palabra sin vocales
            gibberish_words += 1
    
    if words and gibberish_words / len(words) > 0.3:
        errors.append(f"{gibberish_words} palabras aparentemente sin sentido")
    
    # Calcular confianza basada en todos los factores
    confidence_factors = [
        1.0 - non_alpha_ratio,
        1.0 - (repeated_lines / len(lines) if lines else 0),
        1.0 - (gibberish_words / len(words) if words else 0)
    ]
    
    confidence = sum(confidence_factors) / len(confidence_factors)
    # Ajustar confianza por longitud de texto
    if len(ocr_text) < 50:
        confidence *= 0.8  # Textos muy cortos tienden a ser menos confiables
    
    return {
        'valid': confidence > 0.6 and len(errors) < 2,
        'confidence': max(0.0, min(1.0, confidence)),
        'reason': "Texto válido" if confidence > 0.6 and len(errors) < 2 else "Problemas detectados en el texto",
        'errors': errors,
        'length': len(ocr_text)
    }

def detect_text_language(text: str) -> str:
    """
    Detecta el idioma del texto basado en frecuencias de caracteres y patrones.
    Esta es una implementación simple que podría reemplazarse por una biblioteca 
    más avanzada como langdetect o fasttext.
    
    Args:
        text: Texto para detectar idioma
        
    Returns:
        str: Código de idioma ('spa', 'eng', etc.)
    """
    if not text or len(text) < 20:
        return 'eng'  # Por defecto inglés para textos muy cortos
    
    # Diccionario de patrones comunes en diferentes idiomas
    lang_patterns = {
        'spa': ['de la', 'el ', 'la ', 'que ', 'en ', 'y ', 'por ', 'con ', 'para ', 'es ', 'ñ', 'á', 'é', 'í', 'ó', 'ú', 'ü'],
        'eng': ['the ', 'and ', 'of ', 'to ', 'in ', 'is ', 'that ', 'for ', 'it ', 'with ', 'th', 'wh'],
        'fra': ['le ', 'la ', 'les ', 'de ', 'et ', 'en ', 'que ', 'une ', 'pour ', 'dans ', 'ç', 'à', 'è', 'ê', 'ë', 'î', 'ï', 'ô', 'ù', 'û', 'ÿ'],
        'deu': ['der ', 'die ', 'und ', 'den ', 'in ', 'von ', 'zu ', 'das ', 'mit ', 'dem ', 'ä', 'ö', 'ü', 'ß'],
        'ita': ['il ', 'la ', 'di ', 'e ', 'che ', 'in ', 'per ', 'un ', 'del ', 'con ', 'è', 'à', 'ò', 'ù']
    }
    
    # Contar ocurrencias de cada patrón
    scores = {lang: 0 for lang in lang_patterns}
    
    for lang, patterns in lang_patterns.items():
        for pattern in patterns:
            pattern_count = text.lower().count(pattern)
            # Ponderamos por longitud para evitar sesgos
            scores[lang] += pattern_count * len(pattern)
    
    # Normalizar por cantidad de patrones
    for lang in scores:
        if lang_patterns[lang]:
            scores[lang] /= len(lang_patterns[lang])
    
    # Determinar el idioma con mayor puntuación
    best_lang = max(scores, key=scores.get)
    
    # Convertir a código Tesseract
    lang_map = {'spa': 'spa', 'eng': 'eng', 'fra': 'fra', 'deu': 'deu', 'ita': 'ita'}
    return lang_map.get(best_lang, 'eng')

def determine_best_alt_text(ocr_text: str, file_name: str = '', 
                           confidence_threshold: float = 0.6,
                           image_info: Dict = None) -> Dict[str, Any]:
    """
    Determina el mejor texto alternativo basado en OCR o nombre de archivo.
    Decide si usar Alt o ActualText según el contenido de la imagen,
    de acuerdo con las mejores prácticas de PDF/UA.
    
    Args:
        ocr_text: Texto extraído por OCR
        file_name: Nombre del archivo de imagen
        confidence_threshold: Umbral de confianza para usar OCR
        image_info: Información adicional sobre la imagen (opcional)
        
    Returns:
        dict: {
            'text': str,         # Texto alternativo sugerido
            'attribute_type': str,  # 'Alt' o 'ActualText'
            'source': str,       # 'ocr', 'filename', 'default'
            'confidence': float, # Confianza en el resultado
            'language': str      # Idioma detectado del texto
        }
    """
    # Evaluar calidad del OCR
    ocr_quality = estimate_ocr_quality(ocr_text)
    
    # Determinar tipo de imagen y si contiene principalmente texto
    is_text_image = False
    if image_info:
        is_text_image = image_info.get('text_type', '') == 'printed' and image_info.get('has_text', False)
    
    # Si el OCR es bueno, usarlo
    if ocr_quality['valid'] and ocr_quality['confidence'] >= confidence_threshold:
        # Detectar idioma
        lang = detect_text_language(ocr_text)
        
        # Determinar si usar Alt o ActualText
        # PDF/UA recomienda ActualText para imágenes que son principalmente texto
        # (Checkpoint 13-008)
        attribute_type = 'ActualText' if is_text_image else 'Alt'
        
        return {
            'text': ocr_text,
            'attribute_type': attribute_type,
            'source': 'ocr',
            'confidence': ocr_quality['confidence'],
            'language': lang
        }
    
    # Si hay nombre de archivo, tratar de extraer información útil
    if file_name:
        # Eliminar extensión
        name_without_ext = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
        
        # Reemplazar guiones y guiones bajos por espacios
        clean_name = name_without_ext.replace('-', ' ').replace('_', ' ')
        
        # Convertir a título para legibilidad
        clean_name = ' '.join(word.capitalize() for word in clean_name.split())
        
        return {
            'text': clean_name,
            'attribute_type': 'Alt',  # Siempre Alt para nombres de archivo
            'source': 'filename',
            'confidence': 0.5,  # Confianza media
            'language': 'eng'  # Por defecto inglés para nombres de archivo
        }
    
    # Si no hay buena información, devolver mensaje genérico
    return {
        'text': "Imagen sin descripción disponible",
        'attribute_type': 'Alt',
        'source': 'default',
        'confidence': 0.0,
        'language': 'eng'
    }

def batch_process_images(image_list: List[Dict[str, Any]], 
                       max_workers: int = 4) -> List[Dict[str, Any]]:
    """
    Procesa un lote de imágenes en paralelo para extraer texto y generar
    texto alternativo apropiado.
    
    Args:
        image_list: Lista de diccionarios con {'image_data': bytes, 'filename': str}
        max_workers: Número máximo de trabajadores en paralelo
        
    Returns:
        List[Dict]: Lista de resultados con texto alternativo y metadatos
    """
    results = []
    
    def process_single_image(image_item):
        """Procesa una sola imagen del lote."""
        image_data = image_item.get('image_data')
        filename = image_item.get('filename', '')
        
        # Convertir a imagen OpenCV para análisis
        try:
            nparr = np.frombuffer(image_data, np.uint8)
            cv_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Detectar si tiene texto
            text_info = detect_if_image_has_text(cv_image)
            
            # Extraer texto si es probable que lo tenga
            ocr_text = ""
            if text_info['has_text'] and text_info['confidence'] > 0.4:
                # Detectar idioma para mejor OCR
                lang = 'eng'  # Por defecto inglés
                ocr_text = extract_text_from_cv_image(cv_image, lang=lang, preprocess=True)
            
            # Determinar mejor texto alternativo
            alt_info = determine_best_alt_text(ocr_text, filename, image_info=text_info)
            
            # Devolver resultado completo
            return {
                'filename': filename,
                'text_detected': text_info['has_text'],
                'text_type': text_info['text_type'],
                'text_confidence': text_info['confidence'],
                'ocr_text': ocr_text,
                'alt_text': alt_info['text'],
                'attribute_type': alt_info['attribute_type'],
                'confidence': alt_info['confidence'],
                'language': alt_info['language']
            }
        except Exception as e:
            logger.error(f"Error procesando imagen {filename}: {str(e)}")
            return {
                'filename': filename,
                'error': str(e),
                'text_detected': False,
                'alt_text': f"Imagen {filename}",
                'attribute_type': 'Alt',
                'confidence': 0.0
            }
    
    # Procesar imágenes en paralelo
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_image = {executor.submit(process_single_image, img): img for img in image_list}
        for future in concurrent.futures.as_completed(future_to_image):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Error en procesamiento paralelo: {str(e)}")
    
    return results