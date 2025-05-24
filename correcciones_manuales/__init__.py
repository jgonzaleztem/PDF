# pdfua_editor/correcciones_manuales/__init__.py
"""
Herramientas para la edición manual de la estructura y propiedades PDF/UA.
"""

from .structure_manager import StructureManager
from .structure_view import StructureView
from .tag_properties import TagPropertiesEditor

__all__ = [
    "StructureManager",
    "StructureView",
    "TagPropertiesEditor",
]