# pdfua_editor/utils/__init__.py
"""
Utilidades auxiliares para la aplicación.
"""

from .color_utils import (
    hex_to_rgb, rgb_to_hex, rgb_to_hsl, hsl_to_rgb,
    extract_color, calculate_contrast_ratio, is_wcag_aa_compliant,
    is_wcag_aaa_compliant, suggest_accessible_colors,
    get_contrast_level_description, get_color_visibility
)
from .ocr_utils import (
    extract_text_from_image_data, extract_text_from_cv_image,
    preprocess_image_for_ocr, detect_if_image_has_text,
    estimate_ocr_quality, determine_best_alt_text
)
from .pdf_utils import (
    extract_text_by_area, get_visual_elements, detect_reading_order,
    analyze_text_style, detect_tables, check_text_font_consistency,
    analyze_document_language
)
from .ui_utils import (
    setup_logger, set_application_style, get_icon,
    show_info_message, show_warning_message, show_error_message,
    show_question_message, create_dark_light_palette, get_theme_color
)

__all__ = [
    # color_utils
    "hex_to_rgb", "rgb_to_hex", "rgb_to_hsl", "hsl_to_rgb",
    "extract_color", "calculate_contrast_ratio", "is_wcag_aa_compliant",
    "is_wcag_aaa_compliant", "suggest_accessible_colors",
    "get_contrast_level_description", "get_color_visibility",
    # ocr_utils
    "extract_text_from_image_data", "extract_text_from_cv_image",
    "preprocess_image_for_ocr", "detect_if_image_has_text",
    "estimate_ocr_quality", "determine_best_alt_text",
    # pdf_utils
    "extract_text_by_area", "get_visual_elements", "detect_reading_order",
    "analyze_text_style", "detect_tables", "check_text_font_consistency",
    "analyze_document_language",
    # ui_utils
    "setup_logger", "set_application_style", "get_icon",
    "show_info_message", "show_warning_message", "show_error_message",
    "show_question_message", "create_dark_light_palette", "get_theme_color",
]