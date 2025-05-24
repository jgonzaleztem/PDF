# pdfua_editor/correcciones_automaticas/__init__.py
"""
Módulos para la remediación automática de problemas de accesibilidad PDF/UA.
"""

from .metadata_fixer import MetadataFixer
from .images_fixer import ImagesFixer
from .tables_fixer import TablesFixer
from .lists_fixer import ListsFixer
from .artifacts_fixer import ArtifactsFixer
from .tags_fixer import TagsFixer
from .link_fixer import LinkFixer
from .reading_order import ReadingOrderFixer
from .structure_generator import StructureGenerator
from .forms_fixer import FormsFixer
from .contrast_fixer import ContrastFixer
from .bounding_boxes import BoundingBoxes

__all__ = [
    "MetadataFixer",
    "ImagesFixer",
    "TablesFixer",
    "ListsFixer",
    "ArtifactsFixer",
    "TagsFixer",
    "LinkFixer",
    "ReadingOrderFixer",
    "StructureGenerator",
    "FormsFixer",
    "ContrastFixer",
    "BoundingBoxes",
]