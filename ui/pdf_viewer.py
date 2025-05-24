import sys
import fitz  # PyMuPDF
from PySide6.QtWidgets import (QWidget, QGraphicsView, QGraphicsScene, 
                             QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QComboBox, QScrollBar, QFrame)
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QImage, QFont
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QTimer

from loguru import logger

class PDFHighlightItem:
    """Representa un elemento destacado en el PDF (nodo estructural, error, etc.)."""
    def __init__(self, rect, element_id, element_type=None, color=QColor(255, 165, 0, 100), text=""):
        self.rect = rect  # QRectF
        self.element_id = element_id
        self.element_type = element_type
        self.color = color
        self.text = text  # Texto asociado al elemento

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
        self.pdf_loader = None  # Referencia al PDF loader para acceso a estructura
        self.current_page = 0
        self.total_pages = 0
        self.zoom_level = 1.0
        self.zoom_levels = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0]
        
        self.page_pixmap = None
        self.highlighted_elements = []  # Lista de PDFHighlightItem
        self.selected_element_id = None
        self.show_structure_overlay = True  # Mostrar superposición de estructura
        
        # Timer para renderizado diferido
        self.render_timer = QTimer()
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self._render_current_page)
        
        self._init_ui()
    
    def _init_ui(self):
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Controles de navegación
        nav_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("◀ Anterior")
        self.prev_btn.clicked.connect(self._on_prev_page)
        self.prev_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_btn)
        
        self.page_label = QLabel("Página 0 de 0")
        self.page_label.setMinimumWidth(100)
        self.page_label.setAlignment(Qt.AlignCenter)
        nav_layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("Siguiente ▶")
        self.next_btn.clicked.connect(self._on_next_page)
        self.next_btn.setEnabled(False)
        nav_layout.addWidget(self.next_btn)
        
        nav_layout.addStretch()
        
        # Controles de visualización
        self.structure_toggle = QPushButton("Estructura: ON")
        self.structure_toggle.setCheckable(True)
        self.structure_toggle.setChecked(True)
        self.structure_toggle.clicked.connect(self._on_structure_toggle)
        self.structure_toggle.setToolTip("Mostrar/ocultar superposición de estructura")
        nav_layout.addWidget(self.structure_toggle)
        
        nav_layout.addWidget(QFrame())  # Separador visual
        
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
        self.zoom_in_btn.setMaximumWidth(30)
        nav_layout.addWidget(self.zoom_in_btn)
        
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.zoom_out_btn.setMaximumWidth(30)
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
        
        # Barra de información
        info_layout = QHBoxLayout()
        self.info_label = QLabel("Ningún documento cargado")
        self.info_label.setStyleSheet("QLabel { color: #666; font-size: 10px; }")
        info_layout.addWidget(self.info_label)
        info_layout.addStretch()
        
        main_layout.addLayout(info_layout)
    
    def load_document(self, fitz_document):
        """Carga un documento PDF desde un objeto PyMuPDF Document."""
        try:
            self.doc = fitz_document
            if self.doc:
                self.total_pages = len(self.doc)
                self.current_page = 0
                self._update_page_display()
                self._render_current_page()
                
                # Actualizar información del documento
                self.info_label.setText(f"Documento cargado: {self.total_pages} páginas")
                
                # Habilitar controles
                self.prev_btn.setEnabled(self.total_pages > 1)
                self.next_btn.setEnabled(self.total_pages > 1)
                
                logger.info(f"Documento cargado en visor: {self.total_pages} páginas")
            else:
                self._clear_document()
                
        except Exception as e:
            logger.error(f"Error al cargar documento en visor: {e}")
            self._clear_document()
    
    def _clear_document(self):
        """Limpia el documento actual."""
        self.doc = None
        self.total_pages = 0
        self.current_page = 0
        self.scene.clear()
        self.highlighted_elements.clear()
        self.selected_element_id = None
        
        self.page_label.setText("Página 0 de 0")
        self.info_label.setText("Ningún documento cargado")
        
        # Deshabilitar controles
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
    
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
                zoom = view_width / (pixmap_width / self.zoom_level)
                self.set_zoom_level(zoom)
    
    def select_element(self, element_id):
        """
        Selecciona y resalta un elemento estructural por su ID.
    
        Args:
            element_id: ID del elemento a resaltar
        """
        try:
            # Si el ID de elemento es None o vacío, ignorar
            if not element_id:
                self.selected_element_id = None
                self._render_current_page()
                return
            
            # Actualizar ID seleccionado
            self.selected_element_id = str(element_id)
        
            # Si tenemos estructura cargada y el documento está disponible, 
            # intentar encontrar el elemento y navegar a su página
            if (self.pdf_loader and 
                self.pdf_loader.structure_tree and 
                self.doc):
                
                element = self._find_element_in_structure(self.selected_element_id)
                if element:
                    # Si el elemento tiene página asociada, ir a esa página
                    page_num = element.get("page")
                    if page_num is not None and isinstance(page_num, int) and page_num != self.current_page:
                        self.go_to_page(page_num)
                        return  # _render_current_page será llamado por go_to_page
        
            # Re-renderizar para mostrar selección
            self._render_current_page()
            
        except Exception as e:
            logger.error(f"Error al seleccionar elemento {element_id}: {e}")
    
    def _find_element_in_structure(self, element_id):
        """Busca un elemento en la estructura por su ID."""
        if not self.pdf_loader or not self.pdf_loader.structure_tree:
            return None
        
        try:
            element_id_int = int(element_id) if isinstance(element_id, str) else element_id
        except (ValueError, TypeError):
            element_id_int = element_id
        
        def search_recursive(node):
            if isinstance(node, dict):
                # Verificar si este nodo tiene el ID buscado
                if "element" in node and node["element"]:
                    node_id = id(node["element"])
                    if node_id == element_id_int:
                        return node
                else:
                    # Para nodos sin elemento, usar ID del nodo mismo
                    node_id = id(node)
                    if node_id == element_id_int:
                        return node
                
                # Buscar en hijos
                if "children" in node:
                    for child in node["children"]:
                        result = search_recursive(child)
                        if result:
                            return result
            
            return None
        
        return search_recursive(self.pdf_loader.structure_tree)
    
    def highlight_elements(self, elements):
        """
        Resalta múltiples elementos en la página.
        
        Args:
            elements: Lista de dict con keys {id, rect, type, page}
            rect debe ser en coordenadas de la página
        """
        try:
            self.highlighted_elements = []
            
            if not self.doc:
                logger.warning("No se pueden resaltar elementos: documento no disponible")
                return
            
            # Filtrar elementos de la página actual
            current_page_elements = [e for e in elements 
                                   if e.get('page') == self.current_page or e.get('page') is None]
            
            if not current_page_elements:
                self._render_current_page()
                return
            
            page = self.doc[self.current_page]
            page_rect = page.rect
            
            for elem in current_page_elements:
                # Procesar rectángulo
                rect_data = elem.get('rect', [0, 0, 0, 0])
                
                # Si rect está en formato relativo (0-1), convertir a absoluto
                if all(0 <= coord <= 1 for coord in rect_data):
                    abs_rect = QRectF(
                        rect_data[0] * page_rect.width,
                        rect_data[1] * page_rect.height,
                        (rect_data[2] - rect_data[0]) * page_rect.width,
                        (rect_data[3] - rect_data[1]) * page_rect.height
                    )
                else:
                    # Ya está en coordenadas absolutas
                    abs_rect = QRectF(rect_data[0], rect_data[1], 
                                    rect_data[2] - rect_data[0], 
                                    rect_data[3] - rect_data[1])
                
                # Determinar color según tipo de elemento
                elem_type = elem.get('type', '')
                severity = elem.get('severity', 'info')
                
                if severity == 'error':
                    color = QColor(255, 0, 0, 100)  # Rojo para errores
                elif severity == 'warning':
                    color = QColor(255, 165, 0, 100)  # Naranja para advertencias
                elif elem_type.startswith('H'):
                    color = QColor(0, 128, 255, 100)  # Azul para encabezados
                elif elem_type == 'Figure':
                    color = QColor(0, 200, 0, 100)  # Verde para figuras
                elif elem_type == 'Table':
                    color = QColor(255, 0, 255, 100)  # Magenta para tablas
                elif elem_type == 'Link':
                    color = QColor(128, 0, 128, 100)  # Púrpura para enlaces
                else:
                    color = QColor(255, 165, 0, 100)  # Naranja por defecto
                
                # Crear objeto de resaltado
                highlight = PDFHighlightItem(
                    abs_rect, 
                    elem.get('id', ''), 
                    elem_type, 
                    color,
                    elem.get('text', '')
                )
                self.highlighted_elements.append(highlight)
            
            self._render_current_page()  # Re-renderizar con elementos resaltados
            
        except Exception as e:
            logger.error(f"Error al resaltar elementos: {e}")
    
    def _load_structure_elements_for_page(self, page_num):
        """Carga elementos de estructura para la página actual si está disponible."""
        if not self.pdf_loader or not self.pdf_loader.structure_tree:
            return
        
        try:
            # Extraer elementos de la página actual de la estructura
            page_elements = []
            
            def extract_page_elements(node, path=""):
                if isinstance(node, dict):
                    node_page = node.get("page")
                    
                    # Si el nodo pertenece a la página actual
                    if node_page == page_num:
                        element_type = node.get("type", "Unknown")
                        element_text = node.get("text", "").strip()
                        element_id = id(node.get("element")) if node.get("element") else id(node)
                        
                        # Intentar obtener coordenadas del elemento
                        # (esto requeriría implementación adicional para mapear elementos a coordenadas)
                        rect = [0, 0, 100, 20]  # Placeholder - necesitaría implementación real
                        
                        page_elements.append({
                            'id': element_id,
                            'type': element_type,
                            'rect': rect,
                            'text': element_text,
                            'page': page_num
                        })
                    
                    # Procesar hijos
                    if "children" in node:
                        for child in node["children"]:
                            extract_page_elements(child, f"{path}/{element_type}")
            
            if self.show_structure_overlay:
                extract_page_elements(self.pdf_loader.structure_tree)
                
                # Agregar elementos de estructura a los resaltados
                if page_elements:
                    self.highlight_elements(page_elements)
            
        except Exception as e:
            logger.error(f"Error al cargar elementos de estructura: {e}")
    
    def _update_page_display(self):
        """Actualiza la etiqueta de navegación con la página actual."""
        if self.doc and self.total_pages > 0:
            self.page_label.setText(f"Página {self.current_page + 1} de {self.total_pages}")
            self.pageChanged.emit(self.current_page + 1, self.total_pages)
            
            # Actualizar estado de botones de navegación
            self.prev_btn.setEnabled(self.current_page > 0)
            self.next_btn.setEnabled(self.current_page < self.total_pages - 1)
        else:
            self.page_label.setText("Página 0 de 0")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
    
    def _render_current_page(self):
        """Renderiza la página actual con resaltados."""
        if not self.doc:
            # Si el documento no está disponible, mostrar un mensaje
            self.scene.clear()
            text_item = self.scene.addText("No hay documento cargado", QFont("Arial", 14))
            text_item.setDefaultTextColor(QColor(128, 128, 128))
            self.scene.setSceneRect(text_item.boundingRect())
            return
    
        try:
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
        
            # Cargar elementos de estructura para esta página si está habilitado
            if self.show_structure_overlay:
                self._load_structure_elements_for_page(self.current_page)
        
            # Añadir resaltados
            self._render_highlights()
        
            # Actualizar la vista
            self.view.resetTransform()
            self.view.setSceneRect(self.scene.sceneRect())
            
            # Centrar vista si es la primera renderización
            if not hasattr(self, '_first_render_done'):
                self.view.centerOn(self.scene.sceneRect().center())
                self._first_render_done = True
            
        except Exception as e:
            logger.error(f"Error al renderizar página: {e}")
            self.scene.clear()
            error_text = self.scene.addText(f"Error al renderizar: {str(e)}", QFont("Arial", 12))
            error_text.setDefaultTextColor(QColor(255, 0, 0))
            self.scene.setSceneRect(error_text.boundingRect())
    
    def _render_highlights(self):
        """Renderiza los elementos resaltados en la escena."""
        try:
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
                    pen = QPen(QColor(255, 0, 0), 3)  # Borde rojo, 3px de grosor
                    brush = QBrush(QColor(255, 0, 0, 120))  # Rojo semitransparente más visible
                else:
                    # Elemento normal: borde suave con color según tipo
                    pen = QPen(highlight.color.darker(150), 1)
                    brush = QBrush(highlight.color)
            
                # Añadir rectángulo a la escena
                rect_item = self.scene.addRect(rect, pen, brush)
                
                # Configurar z-order para que los elementos seleccionados estén encima
                if is_selected:
                    rect_item.setZValue(10)
                else:
                    rect_item.setZValue(5)
            
                # Añadir etiqueta de tipo si está disponible y es un elemento seleccionado
                if highlight.element_type and is_selected:
                    # Crear texto descriptivo
                    display_text = highlight.element_type
                    if highlight.text and len(highlight.text) < 30:
                        display_text += f": {highlight.text}"
                    
                    text_item = self.scene.addText(display_text, QFont("Arial", 10))
                    text_item.setDefaultTextColor(QColor(255, 255, 255))
                    
                    # Posicionar texto en la parte superior del rectángulo
                    text_pos = QPointF(rect.x(), rect.y() - text_item.boundingRect().height())
                    # Asegurar que el texto no se salga de la escena
                    if text_pos.y() < 0:
                        text_pos.setY(rect.y() + 2)
                    text_item.setPos(text_pos)
                    
                    # Añadir fondo al texto para mejor legibilidad
                    text_bg = self.scene.addRect(
                        text_item.boundingRect().translated(text_pos),
                        QPen(Qt.NoPen),
                        QBrush(QColor(0, 0, 0, 180))
                    )
                    text_bg.setZValue(text_item.zValue() - 1)
                    text_item.setZValue(15)  # Texto encima de todo
            
        except Exception as e:
            logger.error(f"Error al renderizar resaltados: {e}")
    
    def _on_prev_page(self):
        """Maneja el clic en el botón de página anterior."""
        if self.doc and self.current_page > 0:
            self.current_page -= 1
            self._update_page_display()
            # Usar timer para renderizado diferido
            self.render_timer.start(100)
    
    def _on_next_page(self):
        """Maneja el clic en el botón de página siguiente."""
        if self.doc and self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_page_display()
            # Usar timer para renderizado diferido
            self.render_timer.start(100)
    
    def _on_zoom_changed(self, index):
        """Maneja el cambio en el nivel de zoom."""
        if index >= 0 and index < len(self.zoom_levels):
            old_zoom = self.zoom_level
            self.zoom_level = self.zoom_levels[index]
            
            if old_zoom != self.zoom_level:
                # Usar timer para renderizado diferido
                self.render_timer.start(200)
                self.zoomChanged.emit(self.zoom_level)
    
    def _on_structure_toggle(self, checked):
        """Maneja el toggle de la superposición de estructura."""
        self.show_structure_overlay = checked
        self.structure_toggle.setText(f"Estructura: {'ON' if checked else 'OFF'}")
        
        if not checked:
            # Limpiar elementos de estructura resaltados
            self.highlighted_elements = [h for h in self.highlighted_elements 
                                       if h.element_type not in ['P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'Figure', 'Table']]
        
        # Re-renderizar
        self._render_current_page()
    
    def _on_mouse_press(self, event):
        """Maneja clics de ratón para selección de elementos."""
        if event.button() == Qt.LeftButton and self.doc:
            try:
                # Convertir coordenadas de vista a coordenadas de escena
                scene_pos = self.view.mapToScene(event.pos())
                
                # Buscar si hay un elemento en esa posición
                clicked_element = None
                min_area = float('inf')
                
                for highlight in self.highlighted_elements:
                    rect = QRectF(
                        highlight.rect.x() * self.zoom_level,
                        highlight.rect.y() * self.zoom_level,
                        highlight.rect.width() * self.zoom_level,
                        highlight.rect.height() * self.zoom_level
                    )
                
                    if rect.contains(scene_pos):
                        # Si hay múltiples elementos superpuestos, elegir el más pequeño
                        area = rect.width() * rect.height()
                        if area < min_area:
                            clicked_element = highlight
                            min_area = area
                
                if clicked_element:
                    # Emitir señal de elemento seleccionado
                    self.elementSelected.emit(clicked_element.element_id)
                    self.selected_element_id = clicked_element.element_id
                    self._render_current_page()  # Re-renderizar para resaltar selección
                    
                    logger.debug(f"Elemento seleccionado: {clicked_element.element_type} (ID: {clicked_element.element_id})")
                    return
            
                # Si no se seleccionó ningún elemento, limpiar selección
                if self.selected_element_id:
                    self.selected_element_id = None
                    self._render_current_page()
                
                # Pasar evento al comportamiento predeterminado para drag/scroll
                QGraphicsView.mousePressEvent(self.view, event)
                
            except Exception as e:
                logger.error(f"Error en selección de elemento: {e}")
                # Pasar evento al comportamiento predeterminado
                QGraphicsView.mousePressEvent(self.view, event)
        else:
            # Pasar el evento al comportamiento predeterminado
            QGraphicsView.mousePressEvent(self.view, event)
    
    def clear_highlights(self):
        """Limpia todos los elementos resaltados."""
        self.highlighted_elements.clear()
        self.selected_element_id = None
        if self.doc:
            self._render_current_page()
    
    def get_page_info(self):
        """Obtiene información de la página actual."""
        if not self.doc:
            return {}
        
        try:
            page = self.doc[self.current_page]
            return {
                "page_number": self.current_page,
                "page_size": (page.rect.width, page.rect.height),
                "zoom_level": self.zoom_level,
                "total_pages": self.total_pages,
                "highlights_count": len(self.highlighted_elements),
                "selected_element": self.selected_element_id
            }
        except Exception as e:
            logger.error(f"Error al obtener información de página: {e}")
            return {}
    
    def export_page_image(self, output_path, dpi=150):
        """
        Exporta la página actual como imagen.
        
        Args:
            output_path: Ruta donde guardar la imagen
            dpi: Resolución de la imagen
        """
        if not self.doc:
            return False
        
        try:
            page = self.doc[self.current_page]
            zoom = dpi / 72  # Convertir DPI a factor de zoom
            matrix = fitz.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            
            # Guardar imagen
            pixmap.save(output_path)
            logger.info(f"Página exportada como imagen: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error al exportar página como imagen: {e}")
            return False