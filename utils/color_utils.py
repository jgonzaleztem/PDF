"""
Utilidades para cálculo de contraste y manipulación de colores.

Relacionado con:
- Matterhorn: 04-001 (Color y contraste)
- Tagged PDF: 5.1.1 (Color, BackgroundColor)
"""

import math
import re
from loguru import logger

def hex_to_rgb(hex_color):
    """
    Convierte un color hexadecimal a RGB.
    
    Args:
        hex_color (str): Color en formato '#RRGGBB' o '#RGB'
        
    Returns:
        tuple: (R, G, B) como enteros 0-255
    """
    hex_color = hex_color.lstrip('#')
    
    if len(hex_color) == 3:
        # Formato abreviado #RGB
        hex_color = ''.join([c * 2 for c in hex_color])
        
    if len(hex_color) != 6:
        logger.warning(f"Formato de color hexadecimal inválido: {hex_color}")
        return (0, 0, 0)
        
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    """
    Convierte un color RGB a hexadecimal.
    
    Args:
        rgb (tuple): (R, G, B) como enteros 0-255
        
    Returns:
        str: Color en formato '#RRGGBB'
    """
    return '#{:02x}{:02x}{:02x}'.format(*rgb)

def rgb_to_hsl(rgb):
    """
    Convierte un color RGB a HSL.
    
    Args:
        rgb (tuple): (R, G, B) como enteros 0-255
        
    Returns:
        tuple: (H, S, L) como (0-360, 0-100, 0-100)
    """
    r, g, b = [x / 255.0 for x in rgb]
    
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    delta = max_val - min_val
    
    # Luminance
    l = (max_val + min_val) / 2.0
    
    # Saturation
    s = 0
    if delta != 0 and l != 0 and l != 1:
        s = delta / (1 - abs(2 * l - 1))
        
    # Hue
    h = 0
    if delta != 0:
        if max_val == r:
            h = ((g - b) / delta) % 6
        elif max_val == g:
            h = (b - r) / delta + 2
        else:  # max_val == b
            h = (r - g) / delta + 4
            
    h = round(h * 60)
    if h < 0:
        h += 360
        
    return (h, round(s * 100), round(l * 100))

def hsl_to_rgb(hsl):
    """
    Convierte un color HSL a RGB.
    
    Args:
        hsl (tuple): (H, S, L) como (0-360, 0-100, 0-100)
        
    Returns:
        tuple: (R, G, B) como enteros 0-255
    """
    h, s, l = hsl
    
    h = h / 360.0
    s = s / 100.0
    l = l / 100.0
    
    if s == 0:
        # Escala de grises
        r = g = b = l
    else:
        def hue_to_rgb(p, q, t):
            if t < 0:
                t += 1
            if t > 1:
                t -= 1
            if t < 1/6:
                return p + (q - p) * 6 * t
            if t < 1/2:
                return q
            if t < 2/3:
                return p + (q - p) * (2/3 - t) * 6
            return p
            
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        
        r = hue_to_rgb(p, q, h + 1/3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1/3)
        
    return (round(r * 255), round(g * 255), round(b * 255))

def extract_color(color_str):
    """
    Extrae un color de una cadena que podría ser:
    - Hexadecimal: #RRGGBB, #RGB
    - RGB: rgb(r, g, b), rgba(r, g, b, a)
    - Nombre de color: 'red', 'blue', etc.
    
    Args:
        color_str (str): Cadena de color
        
    Returns:
        tuple: (R, G, B) como enteros 0-255, o None si no se pudo extraer
    """
    # Diccionario de colores básicos
    color_names = {
        'black': (0, 0, 0),
        'white': (255, 255, 255),
        'red': (255, 0, 0),
        'green': (0, 128, 0),
        'blue': (0, 0, 255),
        'yellow': (255, 255, 0),
        'cyan': (0, 255, 255),
        'magenta': (255, 0, 255),
        'gray': (128, 128, 128),
        'grey': (128, 128, 128),
        'silver': (192, 192, 192),
        'maroon': (128, 0, 0),
        'olive': (128, 128, 0),
        'navy': (0, 0, 128),
        'purple': (128, 0, 128),
        'teal': (0, 128, 128)
    }
    
    if not color_str:
        return None
        
    # Eliminar espacios
    color_str = color_str.strip().lower()
    
    # Verificar si es un nombre de color
    if color_str in color_names:
        return color_names[color_str]
        
    # Verificar si es un color hexadecimal
    if color_str.startswith('#'):
        try:
            return hex_to_rgb(color_str)
        except ValueError:
            logger.warning(f"Color hexadecimal inválido: {color_str}")
            return None
            
    # Verificar si es RGB o RGBA
    rgb_pattern = r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)'
    match = re.match(rgb_pattern, color_str)
    
    if match:
        try:
            return tuple(int(match.group(i)) for i in range(1, 4))
        except ValueError:
            logger.warning(f"Color RGB inválido: {color_str}")
            return None
            
    logger.warning(f"Formato de color no reconocido: {color_str}")
    return None

def calculate_contrast_ratio(color1, color2):
    """
    Calcula el ratio de contraste entre dos colores según WCAG.
    
    Args:
        color1: Color en formato RGB (tuple), hex (str) o nombre (str)
        color2: Color en formato RGB (tuple), hex (str) o nombre (str)
        
    Returns:
        float: Ratio de contraste (1-21)
    """
    # Convertir a RGB si no lo están
    if not isinstance(color1, tuple):
        color1 = extract_color(color1)
    
    if not isinstance(color2, tuple):
        color2 = extract_color(color2)
        
    if color1 is None or color2 is None:
        logger.error("No se pudo calcular contraste con colores inválidos")
        return 1.0
    
    # Calcular luminosidad relativa (L) para cada color según fórmula WCAG
    def get_luminance(rgb):
        r, g, b = [c/255 for c in rgb]
        
        # Convertir RGB a valores lineales
        r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
        g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
        b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
        
        # Calcular luminosidad
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    
    # Calcular luminosidades
    L1 = get_luminance(color1)
    L2 = get_luminance(color2)
    
    # Calcular ratio de contraste
    if L1 > L2:
        return (L1 + 0.05) / (L2 + 0.05)
    else:
        return (L2 + 0.05) / (L1 + 0.05)

def is_wcag_aa_compliant(ratio, is_large_text=False):
    """
    Verifica si un ratio de contraste cumple con WCAG AA.
    
    Args:
        ratio (float): Ratio de contraste
        is_large_text (bool): True si es texto grande (18pt+ o 14pt+ bold)
        
    Returns:
        bool: True si cumple WCAG AA
    """
    if is_large_text:
        return ratio >= 3.0  # AA para texto grande
    return ratio >= 4.5      # AA para texto normal

def is_wcag_aaa_compliant(ratio, is_large_text=False):
    """
    Verifica si un ratio de contraste cumple con WCAG AAA.
    
    Args:
        ratio (float): Ratio de contraste
        is_large_text (bool): True si es texto grande (18pt+ o 14pt+ bold)
        
    Returns:
        bool: True si cumple WCAG AAA
    """
    if is_large_text:
        return ratio >= 4.5  # AAA para texto grande
    return ratio >= 7.0      # AAA para texto normal

def suggest_accessible_colors(text_color, bg_color, target_ratio=4.5):
    """
    Sugiere colores alternativos para cumplir con el ratio de contraste objetivo.
    
    Args:
        text_color: Color del texto (RGB, hex o nombre)
        bg_color: Color del fondo (RGB, hex o nombre)
        target_ratio: Ratio de contraste objetivo (4.5 para AA, 7.0 para AAA)
        
    Returns:
        dict: {
            'original_ratio': float,
            'is_compliant': bool,
            'suggestions': [
                {'text': (r,g,b), 'background': (r,g,b), 'ratio': float, 'text_hex': str, 'bg_hex': str},
                ...
            ]
        }
    """
    # Convertir a RGB si no lo están
    if not isinstance(text_color, tuple):
        text_color = extract_color(text_color)
    
    if not isinstance(bg_color, tuple):
        bg_color = extract_color(bg_color)
        
    if text_color is None or bg_color is None:
        logger.error("Colores inválidos para sugerencias")
        return {
            'original_ratio': 1.0,
            'is_compliant': False,
            'suggestions': []
        }
        
    # Calcular ratio original
    original_ratio = calculate_contrast_ratio(text_color, bg_color)
    is_compliant = original_ratio >= target_ratio
    
    # Si ya cumple, no hacemos sugerencias
    if is_compliant:
        return {
            'original_ratio': original_ratio,
            'is_compliant': True,
            'suggestions': []
        }
        
    # Convertir a HSL para manipular
    text_hsl = rgb_to_hsl(text_color)
    bg_hsl = rgb_to_hsl(bg_color)
    
    suggestions = []
    
    # Estrategia 1: Oscurecer texto si es claro
    if text_hsl[2] > 50:
        darker_text_hsl = (text_hsl[0], text_hsl[1], max(0, text_hsl[2] - 30))
        darker_text_rgb = hsl_to_rgb(darker_text_hsl)
        ratio = calculate_contrast_ratio(darker_text_rgb, bg_color)
        
        if ratio >= target_ratio:
            suggestions.append({
                'text': darker_text_rgb,
                'background': bg_color,
                'ratio': ratio,
                'text_hex': rgb_to_hex(darker_text_rgb),
                'bg_hex': rgb_to_hex(bg_color)
            })
            
    # Estrategia 2: Aclarar texto si es oscuro
    if text_hsl[2] < 50:
        lighter_text_hsl = (text_hsl[0], text_hsl[1], min(100, text_hsl[2] + 30))
        lighter_text_rgb = hsl_to_rgb(lighter_text_hsl)
        ratio = calculate_contrast_ratio(lighter_text_rgb, bg_color)
        
        if ratio >= target_ratio:
            suggestions.append({
                'text': lighter_text_rgb,
                'background': bg_color,
                'ratio': ratio,
                'text_hex': rgb_to_hex(lighter_text_rgb),
                'bg_hex': rgb_to_hex(bg_color)
            })
            
    # Estrategia 3: Oscurecer fondo si es claro
    if bg_hsl[2] > 50:
        darker_bg_hsl = (bg_hsl[0], bg_hsl[1], max(0, bg_hsl[2] - 30))
        darker_bg_rgb = hsl_to_rgb(darker_bg_hsl)
        ratio = calculate_contrast_ratio(text_color, darker_bg_rgb)
        
        if ratio >= target_ratio:
            suggestions.append({
                'text': text_color,
                'background': darker_bg_rgb,
                'ratio': ratio,
                'text_hex': rgb_to_hex(text_color),
                'bg_hex': rgb_to_hex(darker_bg_rgb)
            })
            
    # Estrategia 4: Aclarar fondo si es oscuro
    if bg_hsl[2] < 50:
        lighter_bg_hsl = (bg_hsl[0], bg_hsl[1], min(100, bg_hsl[2] + 30))
        lighter_bg_rgb = hsl_to_rgb(lighter_bg_hsl)
        ratio = calculate_contrast_ratio(text_color, lighter_bg_rgb)
        
        if ratio >= target_ratio:
            suggestions.append({
                'text': text_color,
                'background': lighter_bg_rgb,
                'ratio': ratio,
                'text_hex': rgb_to_hex(text_color),
                'bg_hex': rgb_to_hex(lighter_bg_rgb)
            })
            
    # Estrategia 5: Negro sobre blanco (último recurso)
    if len(suggestions) == 0:
        black = (0, 0, 0)
        white = (255, 255, 255)
        
        suggestions.append({
            'text': black,
            'background': white,
            'ratio': 21.0,
            'text_hex': '#000000',
            'bg_hex': '#FFFFFF'
        })
        
        suggestions.append({
            'text': white,
            'background': black,
            'ratio': 21.0,
            'text_hex': '#FFFFFF',
            'bg_hex': '#000000'
        })
        
    # Ordenar por ratio de contraste
    suggestions.sort(key=lambda x: x['ratio'], reverse=True)
    
    return {
        'original_ratio': original_ratio,
        'is_compliant': is_compliant,
        'suggestions': suggestions
    }

def get_contrast_level_description(ratio):
    """
    Obtiene una descripción del nivel de contraste según WCAG.
    
    Args:
        ratio (float): Ratio de contraste
        
    Returns:
        str: Descripción del nivel de contraste
    """
    if ratio >= 7.0:
        return "Excelente (AAA)"
    elif ratio >= 4.5:
        return "Bueno (AA)"
    elif ratio >= 3.0:
        return "Regular (AA para texto grande)"
    else:
        return "Insuficiente"
        
def get_color_visibility(color):
    """
    Determina si un color es claro u oscuro, útil para determinar
    si aplicar texto blanco o negro sobre él.
    
    Args:
        color: Color en formato RGB (tuple), hex (str) o nombre (str)
        
    Returns:
        str: 'light' o 'dark'
    """
    if not isinstance(color, tuple):
        color = extract_color(color)
        
    if color is None:
        return 'light'
        
    # Fórmula de luminosidad perceptual
    # https://www.w3.org/TR/WCAG20-TECHS/G18.html
    luminance = (0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]) / 255
    
    return 'light' if luminance > 0.5 else 'dark'