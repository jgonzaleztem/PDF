import sys
import fitz  # PyMuPDF
from PySide6.QtWidgets import (QWidget, QGraphicsView, QGraphicsScene, 
                             QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QComboBox, QScrollBar)
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QImage
from PySide6.QtCore import Qt, Signal, QRectF, QPointF

from loguru import logger

class PDFHighlightItem:
    """Representa un elemento destacado en el PDF (nodo estructural, error, etc.)."""
    def __init__(self, rect, element_id, element_type=None, color=QColor(255, 165, 0, 100)):
        self.rect = rect  # QRectF
        self.element_id = element_id
        self.element_type = element_type
        self.color = color

class PDFViewer(QWidget):
    """
    Visor interactivo de PDF que permite visualizar etiquetas y problemas de estructura.
    
    Responsabilidades:
    - Renderizar páginas PDF con PyMuPDF (fitz)
    - Resaltar elementos estructurales (para verificar 01-006, 09-001)
    - Permitir selección de elementos para edición (utilizado en 01-006)
    - Visualizar problemas de tag mismatch (09-002, 09-003)
    - Mostrar orden de lectura (09-001)
    """
    pageChanged = Signal(int, int)  # Página actual (1-based), total páginas
    elementSelected = Signal(str)  # ID del elemento seleccionado
    zoomChanged = Signal(float)  # Nivel de zoom actual

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.doc = None
        self.current_page = 0
        self.total_pages = 0
        self.zoom_level = 1.0
        self.zoom_levels = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0]
        
        self.page_pixmap = None
        self.highlighted_elements = []  # Lista de PDFHighlightItem
        self.selected_element_id = None
        
        self._init_ui()
    
    def _init_ui(self):
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Controles de navegación
        nav_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("Anterior")
        self.prev_btn.clicked.connect(self._on_prev_page)
        nav_layout.addWidget(self.prev_btn)
        
        self.page_label = QLabel("Página 0 de 0")
        nav_layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("Siguiente")
        self.next_btn.clicked.connect(self._on_next_page)
        nav_layout.addWidget(self.next_btn)
        
        nav_layout.addStretch()
        
        # Controles de zoom
        zoom_label = QLabel("Zoom:")
        nav_layout.addWidget(zoom_label)
        
        self.zoom_combo = QComboBox()
        for level in self.zoom_levels:
            self.zoom_combo.addItem(f"{int(level * 100)}%", level)
        self.zoom_combo.setCurrentIndex(3)  # 100%
        self.zoom_combo.currentIndexChanged.connect(self._on_zoom_changed)
        nav_layout.addWidget(self.zoom_combo)
        
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        nav_layout.addWidget(self.zoom_in_btn)
        
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        nav_layout.addWidget(self.zoom_out_btn)
        
        main_layout.addLayout(nav_layout)
        
        # Vista PDF
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        
        # Habilitar selección de elementos
        self.view.mousePressEvent = self._on_mouse_press
        
        main_layout.addWidget(self.view)
    
    def load_document(self, fitz_document):
        """Carga un documento PDF desde un objeto PyMuPDF Document."""
        self.doc = fitz_document
        if self.doc:
            self.total_pages = len(self.doc)
            self.current_page = 0
            self._update_page_display()
            self._render_current_page()
    
    def go_to_page(self, page_num):
        """Navega a una página específica (0-based)."""
        if self.doc and 0 <= page_num < self.total_pages:
            self.current_page = page_num
            self._update_page_display()
            self._render_current_page()
    
    def get_current_page(self):
        """Devuelve el número de página actual (0-based)."""
        return self.current_page
    
    def get_total_pages(self):
        """Devuelve el número total de páginas."""
        return self.total_pages
    
    def zoom_in(self):
        """Aumenta el nivel de zoom."""
        idx = self.zoom_combo.currentIndex()
        if idx < len(self.zoom_levels) - 1:
            self.zoom_combo.setCurrentIndex(idx + 1)
    
    def zoom_out(self):
        """Reduce el nivel de zoom."""
        idx = self.zoom_combo.currentIndex()
        if idx > 0:
            self.zoom_combo.setCurrentIndex(idx - 1)
    
    def set_zoom_level(self, level):
        """Establece un nivel de zoom específico."""
        for i, zoom in enumerate(self.zoom_levels):
            if abs(zoom - level) < 0.01:
                self.zoom_combo.setCurrentIndex(i)
                break
    
    def get_zoom_level(self):
        """Devuelve el nivel de zoom actual."""
        return self.zoom_level
    
    def fit_to_width(self):
        """Ajusta el PDF al ancho de la vista."""
        if self.doc and self.page_pixmap:
            view_width = self.view.viewport().width() - 20
            pixmap_width = self.page_pixmap.width()
            if pixmap_width > 0:
                zoom = view_width / pixmap_width
                self.set_zoom_level(zoom)
    
    def select_element(self, element_id):
        """
        Selecciona y resalta un elemento estructural por su ID.
    
        Args:
            element_id: ID del elemento a resaltar
        """
        # Si el ID de elemento es None o vacío, ignorar
        if not element_id:
            return
        
        # Actualizar ID seleccionado
        self.selected_element_id = element_id
    
        # Si tenemos estructura cargada, intentar encontrar el elemento
        if hasattr(self, 'pdf_loader') and self.pdf_loader and self.pdf_loader.structure_tree:
            element = self.pdf_loader.find_structure_element_by_id(element_id)
            if element:
                # Si el elemento tiene página asociada, ir a esa página
                page_num = element.get("page")
                if page_num is not None and page_num != self.current_page:
                    self.go_to_page(page_num)
    
        # Re-renderizar para mostrar selección
        self._render_current_page()
    
    def highlight_elements(self, elements):
        """
        Resalta múltiples elementos en la página.
        
        Args:
            elements: Lista de dict con keys {id, rect, type}
            rect debe ser en coordenadas de la página (0..1, 0..1)
        """
        self.highlighted_elements = []
        
        if not self.doc:
            return
        
        page = self.doc[self.current_page]
        page_rect = page.rect
        
        for elem in elements:
            # Convertir rect relativo a coordenadas absolutas de página
            rel_rect = elem.get('rect', [0, 0, 0, 0])
            abs_rect = QRectF(
                rel_rect[0] * page_rect.width,
                rel_rect[1] * page_rect.height,
                (rel_rect[2] - rel_rect[0]) * page_rect.width,
                (rel_rect[3] - rel_rect[1]) * page_rect.height
            )
            
            # Determinar color según tipo de elemento
            color = QColor(255, 165, 0, 100)  # Naranja por defecto
            elem_type = elem.get('type', '')
            
            if elem_type.startswith('H'):
                color = QColor(0, 128, 255, 100)  # Azul para encabezados
            elif elem_type == 'Figure':
                color = QColor(0, 200, 0, 100)  # Verde para figuras
            elif elem_type == 'Table':
                color = QColor(255, 0, 0, 100)  # Rojo para tablas
            elif elem_type == 'Link':
                color = QColor(128, 0, 128, 100)  # Púrpura para enlaces
            
            # Crear objeto de resaltado
            highlight = PDFHighlightItem(abs_rect, elem.get('id', ''), elem_type, color)
            self.highlighted_elements.append(highlight)
        
        self._render_current_page()  # Re-renderizar con elementos resaltados
    
    def _update_page_display(self):
        """Actualiza la etiqueta de navegación con la página actual."""
        if self.doc:
            self.page_label.setText(f"Página {self.current_page + 1} de {self.total_pages}")
            self.pageChanged.emit(self.current_page + 1, self.total_pages)
    
    def _render_current_page(self):
        """Renderiza la página actual con resaltados."""
        if not self.doc:
            return
    
        # Limpiar la escena
        self.scene.clear()
    
        # Obtener y renderizar la página
        page = self.doc[self.current_page]
        zoom_matrix = fitz.Matrix(self.zoom_level, self.zoom_level)
        pixmap = page.get_pixmap(matrix=zoom_matrix, alpha=False)
    
        # Convertir pixmap a QImage y luego a QPixmap
        img = QImage(pixmap.samples, pixmap.width, pixmap.height,
                   pixmap.stride, QImage.Format_RGB888)
        qpixmap = QPixmap.fromImage(img)
        self.page_pixmap = qpixmap
    
        # Añadir pixmap a la escena
        self.scene.addPixmap(qpixmap)
        self.scene.setSceneRect(0, 0, qpixmap.width(), qpixmap.height())
    
        # Añadir resaltados
        for highlight in self.highlighted_elements:
            # Escalar el rectángulo según el zoom
            rect = QRectF(
                highlight.rect.x() * self.zoom_level,
                highlight.rect.y() * self.zoom_level,
                highlight.rect.width() * self.zoom_level,
                highlight.rect.height() * self.zoom_level
            )
        
            # Configuración mejorada para resaltado
            is_selected = highlight.element_id == self.selected_element_id
        
            if is_selected:
                # Elemento seleccionado: borde rojo con fondo semitransparente
                pen = QPen(QColor(255, 0, 0), 2) # Borde rojo, 2px de grosor
                brush = QBrush(QColor(255, 0, 0, 80)) # Rojo semitransparente
            else:
                # Elemento normal: solo fondo con color según tipo
                pen = QPen(Qt.NoPen)
                brush = QBrush(highlight.color)
        
            # Añadir rectángulo a la escena
            self.scene.addRect(rect, pen, brush)
        
            # Añadir etiqueta de tipo si está disponible
            if highlight.element_type and is_selected:
                text_item = self.scene.addText(highlight.element_type)
                text_item.setPos(rect.topLeft())
                # Mejorar visibilidad del texto
                text_item.setDefaultTextColor(QColor(255, 0, 0))
                # Añadir fondo blanco semitransparente para mejor legibilidad
                text_bg = self.scene.addRect(
                    text_item.boundingRect(),
                    QPen(Qt.NoPen),
                    QBrush(QColor(255, 255, 255, 180))
                )
                text_bg.setPos(rect.topLeft())
                text_bg.setZValue(text_item.zValue() - 1) # Colocar detrás del texto
    
        # Actualizar la vista
        self.view.resetTransform()
        self.view.setSceneRect(self.scene.sceneRect())
        self.view.centerOn(self.scene.sceneRect().center())
    
    def _on_prev_page(self):
        """Maneja el clic en el botón de página anterior."""
        if self.current_page > 0:
            self.current_page -= 1
            self._update_page_display()
            self._render_current_page()
    
    def _on_next_page(self):
        """Maneja el clic en el botón de página siguiente."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_page_display()
            self._render_current_page()
    
    def _on_zoom_changed(self, index):
        """Maneja el cambio en el nivel de zoom."""
        if index >= 0 and index < len(self.zoom_levels):
            self.zoom_level = self.zoom_levels[index]
            self._render_current_page()
            self.zoomChanged.emit(self.zoom_level)
    
    def _on_mouse_press(self, event):
        """Maneja clics de ratón para selección de elementos."""
        if event.button() == Qt.LeftButton:
            # Convertir coordenadas de vista a coordenadas de escena
            scene_pos = self.view.mapToScene(event.pos())
        
            # Buscar si hay un elemento en esa posición
            for highlight in self.highlighted_elements:
                rect = QRectF(
                    highlight.rect.x() * self.zoom_level,
                    highlight.rect.y() * self.zoom_level,
                    highlight.rect.width() * self.zoom_level,
                    highlight.rect.height() * self.zoom_level
                )
            
                if rect.contains(scene_pos):
                    # Emitir señal de elemento seleccionado
                    self.elementSelected.emit(highlight.element_id)
                    self.selected_element_id = highlight.element_id
                    self._render_current_page()  # Re-renderizar para resaltar selección
                    return
        
            # Si no se seleccionó ningún elemento, pasar evento al comportamiento predeterminado
            QGraphicsView.mousePressEvent(self.view, event)