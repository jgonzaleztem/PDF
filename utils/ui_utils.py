"""
Utilidades para la interfaz gráfica de usuario.

Este módulo proporciona funciones para configurar y personalizar la interfaz gráfica,
incluyendo funciones para logging, estilos visuales, mensajes, y funcionalidades
específicas para accesibilidad visual relacionadas con PDF/UA.
"""

import os
import sys
import platform
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

from loguru import logger
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QWidget, QLabel, QPushButton, QVBoxLayout, 
    QHBoxLayout, QFrame, QToolTip, QSplashScreen, QMainWindow, QDialog,
    QStyleFactory
)
from PySide6.QtGui import QIcon, QPixmap, QColor, QPalette, QFont, QFontDatabase
from PySide6.QtCore import Qt, QSettings, QSize

# Intentar importar los paquetes de estilo
try:
    import qdarkstyle
    HAVE_QDARKSTYLE = True
except ImportError:
    HAVE_QDARKSTYLE = False

try:
    import qdarktheme
    HAVE_QDARKTHEME = False
except ImportError:
    HAVE_QDARKTHEME = False

try:
    import qtawesome as qta
    HAVE_QTAWESOME = True
except ImportError:
    HAVE_QTAWESOME = False

# Constantes para colores de accesibilidad según WCAG
WCAG_AA_CONTRAST_RATIO = 4.5
WCAG_AAA_CONTRAST_RATIO = 7.0

def setup_logger(log_file_path=None):
    """
    Configura el logger para la aplicación.
    
    Args:
        log_file_path (str, optional): Ruta del archivo de log. 
                                     Por defecto, logs en directorio actual.
    """
    # Eliminar manejadores existentes
    logger.remove()
    
    # Configurar nivel de logging
    log_level = os.environ.get("PDFUA_LOG_LEVEL", "INFO")
    
    # Añadir manejador de consola
    logger.add(sys.stderr, level=log_level, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")
    
    # Añadir manejador de archivo si se proporciona ruta
    if log_file_path:
        logger.add(
            log_file_path, 
            level=log_level, 
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {file}:{line} | {message}",
            rotation="10 MB", 
            retention="30 days"
        )
    
    logger.info(f"Logger inicializado con nivel {log_level}")
    logger.info(f"Sistema: {platform.system()} {platform.release()}")
    logger.info(f"Python: {platform.python_version()}")

def set_application_style(app_instance: QApplication, style: str = 'system', is_dark: bool = False):
    """
    Configura el estilo visual de la aplicación.
    
    Args:
        app_instance: Instancia de QApplication
        style: Estilo a aplicar ('system', 'fusion', 'dark', 'qdarktheme')
        is_dark: Si se debe forzar el modo oscuro para 'fusion'
    """
    # Primero registramos las fuentes para asegurar consistencia en todas las plataformas
    _register_application_fonts()
    
    if style == 'system':
        # Utilizar estilo predeterminado del sistema
        logger.info(f"Usando estilo predeterminado del sistema: {app_instance.style().objectName()}")
    elif style == 'fusion':
        # Utilizar el estilo Fusion de Qt (moderno y plataforma-neutral)
        app_instance.setStyle('Fusion')
        
        # Si se solicita modo oscuro, crear una paleta oscura personalizada
        if is_dark:
            palette = _create_dark_fusion_palette()
            app_instance.setPalette(palette)
            logger.info("Usando estilo Fusion con paleta oscura")
        else:
            logger.info("Usando estilo Fusion")
    elif style == 'dark' and HAVE_QDARKSTYLE:
        # Aplicar tema oscuro usando qdarkstyle
        app_instance.setStyleSheet(qdarkstyle.load_stylesheet_pyside6())
        logger.info("Usando tema oscuro (qdarkstyle)")
    elif style == 'qdarktheme' and HAVE_QDARKTHEME:
        # Aplicar tema usando qdarktheme que tiene modos claro/oscuro
        theme = "dark" if is_dark else "light"
        app_instance.setStyleSheet(qdarktheme.load_stylesheet(theme))
        logger.info(f"Usando qdarktheme en modo {theme}")
    else:
        # Fallback a Fusion si no se puede aplicar el estilo solicitado
        app_instance.setStyle('Fusion')
        logger.warning(f"Estilo {style} no disponible. Usando Fusion como alternativa.")
    
    # Configurar el estilo de los tooltips para máxima legibilidad (importante para accesibilidad)
    _set_tooltip_style(app_instance)

def _register_application_fonts():
    """Registra las fuentes para la aplicación asegurando consistencia entre plataformas."""
    fonts_dir = Path(__file__).parent.parent / "resources" / "fonts"
    
    # Intentar cargar fuentes si el directorio existe
    if fonts_dir.exists():
        for font_file in fonts_dir.glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(font_file))
            logger.debug(f"Registrada fuente: {font_file.name}")

def _create_dark_fusion_palette():
    """Crea una paleta oscura para el estilo Fusion."""
    palette = QPalette()
    
    # Colores oscuros
    dark_color = QColor(45, 45, 45)
    disabled_color = QColor(70, 70, 70)
    text_color = QColor(240, 240, 240)
    
    # Configurar elementos de la paleta
    palette.setColor(QPalette.Window, dark_color)
    palette.setColor(QPalette.WindowText, text_color)
    palette.setColor(QPalette.Base, QColor(33, 33, 33))
    palette.setColor(QPalette.AlternateBase, dark_color)
    palette.setColor(QPalette.ToolTipBase, dark_color)
    palette.setColor(QPalette.ToolTipText, text_color)
    palette.setColor(QPalette.Text, text_color)
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(160, 160, 160))
    palette.setColor(QPalette.Button, dark_color)
    palette.setColor(QPalette.ButtonText, text_color)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(160, 160, 160))
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    palette.setColor(QPalette.Disabled, QPalette.HighlightedText, disabled_color)
    
    return palette

def _set_tooltip_style(app_instance):
    """Configura tooltips con alto contraste para mejor legibilidad."""
    # Definir estilos para los tooltips
    tooltip_style = """
    QToolTip {
        font-family: 'Segoe UI', 'Arial', sans-serif;
        font-size: 12px;
        color: #FFFFFF;
        background-color: #2C2C2C;
        border: 1px solid #3F3F3F;
        padding: 5px;
    }
    """
    
    # Obtener estilo actual y agregar estilos de tooltip
    current_style = app_instance.styleSheet()
    app_instance.setStyleSheet(current_style + tooltip_style)

def detect_system_theme() -> bool:
    """
    Detecta si el sistema está usando un tema oscuro.
    
    Returns:
        bool: True si se detecta un tema oscuro
    """
    # En Windows 10+
    if platform.system() == 'Windows':
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0  # 0 = modo oscuro
        except Exception:
            pass
    
    # En macOS 10.14+
    elif platform.system() == 'Darwin':
        try:
            import subprocess
            result = subprocess.run(
                ['defaults', 'read', '-g', 'AppleInterfaceStyle'],
                capture_output=True, text=True
            )
            return 'Dark' in result.stdout
        except Exception:
            pass
    
    # En sistemas Linux con variables de entorno GNOME
    elif platform.system() == 'Linux':
        try:
            import subprocess
            result = subprocess.run(
                ['gsettings', 'get', 'org.gnome.desktop.interface', 'gtk-theme'],
                capture_output=True, text=True
            )
            return 'dark' in result.stdout.lower()
        except Exception:
            pass
    
    # Por defecto, asumir que no es oscuro
    return False

def get_icon(name: str, color: Optional[str] = None, size: Optional[QSize] = None) -> QIcon:
    """
    Obtiene un icono de QtAwesome.
    
    Args:
        name: Nombre del icono (ej: 'fa5s.file-pdf')
        color: Color en formato CSS ('red', '#FF0000')
        size: Tamaño del icono
        
    Returns:
        QIcon: Icono para usar en widgets
    """
    if not HAVE_QTAWESOME:
        logger.warning("QtAwesome no está disponible. Devolviendo icono vacío.")
        return QIcon()
    
    options = {}
    if color:
        options['color'] = color
    
    try:
        icon = qta.icon(name, **options)
        if size:
            pixmap = icon.pixmap(size)
            icon = QIcon(pixmap)
        return icon
    except Exception as e:
        logger.error(f"Error al cargar icono {name}: {str(e)}")
        # Devolver icono vacío
        return QIcon()

def create_highlight_frame(parent: QWidget, margin: int = 10) -> QFrame:
    """
    Crea un frame de resaltado para elementos que necesitan atención.
    Útil para destacar problemas de accesibilidad.
    
    Args:
        parent: Widget padre
        margin: Margen del frame
        
    Returns:
        QFrame: Marco de resaltado
    """
    frame = QFrame(parent)
    frame.setFrameStyle(QFrame.Box | QFrame.Raised)
    frame.setLineWidth(2)
    frame.setMidLineWidth(1)
    
    # Configurar paleta para el frame
    palette = frame.palette()
    palette.setColor(QPalette.WindowText, QColor(255, 140, 0))  # Naranja para mayor visibilidad
    frame.setPalette(palette)
    
    # Añadir layout con margen
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(margin, margin, margin, margin)
    
    return frame

def create_accessibility_label(parent: QWidget, text: str, is_error: bool = False) -> QLabel:
    """
    Crea una etiqueta de aviso de accesibilidad.
    
    Args:
        parent: Widget padre
        text: Texto de la etiqueta
        is_error: True si es un error, False si es advertencia
        
    Returns:
        QLabel: Etiqueta de aviso
    """
    label = QLabel(text, parent)
    label.setWordWrap(True)
    label.setTextFormat(Qt.RichText)
    
    # Configurar estilo según el tipo de aviso
    if is_error:
        label.setStyleSheet("""
            QLabel {
                color: #FF0000;
                font-weight: bold;
                background-color: rgba(255, 200, 200, 0.3);
                padding: 5px;
                border-radius: 3px;
            }
        """)
    else:
        label.setStyleSheet("""
            QLabel {
                color: #FF8C00;
                font-weight: bold;
                background-color: rgba(255, 240, 200, 0.3);
                padding: 5px;
                border-radius: 3px;
            }
        """)
    
    return label

def show_info_message(parent, title, message):
    """
    Muestra un mensaje informativo.
    
    Args:
        parent (QWidget): Widget padre
        title (str): Título del mensaje
        message (str): Texto del mensaje
    """
    QMessageBox.information(parent, title, message)

def show_warning_message(parent, title, message):
    """
    Muestra un mensaje de advertencia.
    
    Args:
        parent (QWidget): Widget padre
        title (str): Título del mensaje
        message (str): Texto del mensaje
    """
    QMessageBox.warning(parent, title, message)

def show_error_message(parent, title, message):
    """
    Muestra un mensaje de error.
    
    Args:
        parent (QWidget): Widget padre
        title (str): Título del mensaje
        message (str): Texto del mensaje
    """
    QMessageBox.critical(parent, title, message)

def show_question_message(parent, title, message, detailed_text=None):
    """
    Muestra un mensaje de pregunta.
    
    Args:
        parent (QWidget): Widget padre
        title (str): Título del mensaje
        message (str): Texto del mensaje
        detailed_text (str, optional): Texto detallado adicional
        
    Returns:
        bool: True si el usuario hace clic en Sí, False en caso contrario
    """
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Question)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    
    if detailed_text:
        msg_box.setDetailedText(detailed_text)
    
    msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg_box.setDefaultButton(QMessageBox.No)
    
    return msg_box.exec() == QMessageBox.Yes

def show_matterhorn_help(parent, checkpoint_id, description=None):
    """
    Muestra ayuda contextual para un checkpoint de Matterhorn.
    
    Args:
        parent (QWidget): Widget padre
        checkpoint_id (str): ID del checkpoint (ej: '01-006')
        description (str, optional): Descripción personalizada
    """
    # Mapeo de checkpoints a descripciones (extracto)
    checkpoint_info = {
        '01-006': {
            'title': 'Tipos de estructura apropiados',
            'description': 'El tipo de estructura y atributos de un elemento de estructura ' +
                         'deben ser semánticamente apropiados para el elemento.',
            'section': 'UA1:7.1-2',
            'example': 'Un párrafo debe usar <P>, una tabla <Table>, etc.'
        },
        '13-004': {
            'title': 'Texto alternativo en figuras',
            'description': 'Etiqueta <Figure> sin texto alternativo o de reemplazo.',
            'section': 'UA1:7.3-3',
            'example': 'Todas las figuras deben tener un atributo Alt que describa su contenido.'
        },
        '15-003': {
            'title': 'Atributo Scope en celdas de cabecera',
            'description': 'En una tabla no organizada con atributos Headers e IDs, ' +
                         'una celda <TH> no contiene un atributo Scope.',
            'section': 'UA1:7.5-2',
            'example': 'Añadir Scope="Column" o Scope="Row" a las celdas de cabecera.'
        }
    }
    
    # Obtener información del checkpoint
    info = checkpoint_info.get(checkpoint_id, {
        'title': f'Checkpoint {checkpoint_id}',
        'description': description or f'Información no disponible para checkpoint {checkpoint_id}',
        'section': 'Desconocido',
        'example': 'No hay ejemplos disponibles.'
    })
    
    # Crear mensaje detallado
    detail_msg = (
        f"Checkpoint: {checkpoint_id}\n"
        f"Sección: {info['section']}\n\n"
        f"Descripción:\n{info['description']}\n\n"
        f"Ejemplo:\n{info['example']}"
    )
    
    # Mostrar cuadro de diálogo
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Information)
    msg_box.setWindowTitle(f"Ayuda PDF/UA - {info['title']}")
    msg_box.setText(f"<b>{info['title']}</b>")
    msg_box.setInformativeText(info['description'])
    msg_box.setDetailedText(detail_msg)
    
    # Añadir botón para documentación completa
    msg_box.addButton("Documentación completa", QMessageBox.ActionRole)
    msg_box.addButton("Cerrar", QMessageBox.AcceptRole)
    
    result = msg_box.exec()
    
    # Si se hace clic en "Documentación completa", abrir navegador
    if result == 0:  # Primer botón - "Documentación completa"
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        
        # URL ficticia - en implementación real, apuntaría a la documentación
        url = QUrl("https://www.pdfa.org/resource/matterhorn-protocol/")
        QDesktopServices.openUrl(url)

def create_dark_light_palette():
    """
    Crea una paleta de colores para temas claros y oscuros.
    
    Returns:
        dict: Paleta de colores
    """
    return {
        # Colores base
        'primary': {'dark': '#2979ff', 'light': '#1976d2'},
        'secondary': {'dark': '#ff5722', 'light': '#e64a19'},
        'success': {'dark': '#4caf50', 'light': '#388e3c'},
        'warning': {'dark': '#ffc107', 'light': '#f57c00'},
        'error': {'dark': '#f44336', 'light': '#d32f2f'},
        'info': {'dark': '#03a9f4', 'light': '#0288d1'},
        
        # Colores para elementos UI específicos
        'text': {'dark': '#ffffff', 'light': '#212121'},
        'background': {'dark': '#121212', 'light': '#f5f5f5'},
        'surface': {'dark': '#1e1e1e', 'light': '#ffffff'},
        'border': {'dark': '#333333', 'light': '#e0e0e0'},
        
        # Estados
        'hover': {'dark': 'rgba(255, 255, 255, 0.1)', 'light': 'rgba(0, 0, 0, 0.05)'},
        'active': {'dark': 'rgba(255, 255, 255, 0.2)', 'light': 'rgba(0, 0, 0, 0.1)'},
        'disabled': {'dark': 'rgba(255, 255, 255, 0.3)', 'light': 'rgba(0, 0, 0, 0.26)'},
        
        # Colores específicos para PDF/UA - contraste WCAG
        'checkpoint_error': {'dark': '#ff6b6b', 'light': '#d32f2f'},
        'checkpoint_warning': {'dark': '#ffd166', 'light': '#f57c00'},
        'checkpoint_info': {'dark': '#4dabf7', 'light': '#2196f3'},
        'highlight': {'dark': '#ffd369', 'light': '#fff176'},
    }

def get_theme_color(color_name, is_dark_theme=True):
    """
    Obtiene un color de la paleta según el tema.
    
    Args:
        color_name (str): Nombre del color en la paleta
        is_dark_theme (bool): Si es tema oscuro o claro
        
    Returns:
        str: Color en formato CSS
    """
    palette = create_dark_light_palette()
    theme = 'dark' if is_dark_theme else 'light'
    
    if color_name in palette:
        return palette[color_name][theme]
    else:
        logger.warning(f"Color {color_name} no encontrado en la paleta")
        return palette['primary'][theme]

def create_checkpoint_highlight_style(checkpoint_id, is_dark_theme=True):
    """
    Crea un estilo CSS para resaltar elementos según el checkpoint de Matterhorn.
    
    Args:
        checkpoint_id (str): ID del checkpoint (ej: '01-006')
        is_dark_theme (bool): Si es tema oscuro o claro
        
    Returns:
        str: Estilo CSS para usar en setStyleSheet()
    """
    # Determinar tipo de problema basado en el checkpoint
    checkpoint_group = checkpoint_id.split('-')[0] if '-' in checkpoint_id else '00'
    
    # Asignar colores según el grupo de checkpoint
    color_map = {
        # Estructura (rojo)
        '01': 'checkpoint_error',
        '09': 'checkpoint_error',
        
        # Metadatos (amarillo)
        '06': 'checkpoint_warning',
        '07': 'checkpoint_warning',
        '11': 'checkpoint_warning',
        
        # Contenido visual (azul)
        '13': 'checkpoint_info',
        '15': 'checkpoint_info',
        '16': 'checkpoint_info',
        
        # Predeterminado (naranja)
        '00': 'warning'
    }
    
    color_key = color_map.get(checkpoint_group, 'warning')
    color = get_theme_color(color_key, is_dark_theme)
    
    # Crear estilo CSS
    return f"""
        border: 2px solid {color};
        background-color: {color}33;  /* Color con 20% de opacidad */
        border-radius: 3px;
        padding: 2px;
    """

def get_system_font_size() -> int:
    """
    Obtiene el tamaño de fuente del sistema.
    
    Returns:
        int: Tamaño de fuente en puntos
    """
    app = QApplication.instance()
    if app:
        return app.font().pointSize()
    return 10  # Valor predeterminado

def set_universal_font_size(app_instance: QApplication, size: int = None):
    """
    Establece un tamaño de fuente universal para toda la aplicación.
    Útil para mejorar la accesibilidad.
    
    Args:
        app_instance: Instancia de QApplication
        size: Tamaño de fuente en puntos (None para usar el sistema)
    """
    font = app_instance.font()
    
    if size is None:
        # Usar el tamaño del sistema
        size = get_system_font_size()
    
    font.setPointSize(size)
    app_instance.setFont(font)
    
    logger.info(f"Tamaño de fuente universal establecido a {size}pt")

def save_app_settings(settings: Dict[str, Any]):
    """
    Guarda la configuración de la aplicación.
    
    Args:
        settings: Diccionario con configuraciones
    """
    qsettings = QSettings("PDF/UA Editor", "Settings")
    
    for key, value in settings.items():
        qsettings.setValue(key, value)
    
    logger.debug(f"Configuración guardada: {', '.join(settings.keys())}")

def load_app_settings() -> Dict[str, Any]:
    """
    Carga la configuración de la aplicación.
    
    Returns:
        Dict: Configuración cargada
    """
    qsettings = QSettings("PDF/UA Editor", "Settings")
    settings = {}
    
    # Valores predeterminados
    defaults = {
        "theme": "system",
        "font_size": get_system_font_size(),
        "recent_files": [],
        "last_directory": str(Path.home()),
        "show_tooltips": True,
        "auto_analyze": True,
        "high_contrast": False
    }
    
    # Cargar valores o usar predeterminados
    for key, default_value in defaults.items():
        value = qsettings.value(key, default_value)
        settings[key] = value
    
    logger.debug(f"Configuración cargada: {', '.join(settings.keys())}")
    return settings

def create_splash_screen() -> QSplashScreen:
    """
    Crea una pantalla de bienvenida para la aplicación.
    
    Returns:
        QSplashScreen: Pantalla de bienvenida
    """
    # Intentar cargar el logo desde recursos
    splash_img_path = Path(__file__).parent.parent / "resources" / "images" / "splash.png"
    
    if splash_img_path.exists():
        pixmap = QPixmap(str(splash_img_path))
    else:
        # Crear un pixmap básico si no hay imagen
        pixmap = QPixmap(500, 300)
        pixmap.fill(QColor("#1976d2"))
    
    splash = QSplashScreen(pixmap)
    
    # Configurar mensaje
    splash.showMessage(
        "Iniciando PDF/UA Editor...\nVerificando conformidad con ISO 14289-1", 
        Qt.AlignBottom | Qt.AlignCenter, 
        Qt.white
    )
    
    return splash

def create_help_dialog(parent: QWidget, title: str, content: str) -> QDialog:
    """
    Crea un diálogo de ayuda con información sobre PDF/UA.
    
    Args:
        parent: Widget padre
        title: Título del diálogo
        content: Contenido HTML
        
    Returns:
        QDialog: Diálogo de ayuda
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumSize(600, 400)
    
    layout = QVBoxLayout(dialog)
    
    # Crear etiqueta con contenido HTML
    content_label = QLabel(dialog)
    content_label.setTextFormat(Qt.RichText)
    content_label.setOpenExternalLinks(True)
    content_label.setText(content)
    content_label.setWordWrap(True)
    
    # Crear botón de cerrar
    close_button = QPushButton("Cerrar", dialog)
    close_button.clicked.connect(dialog.accept)
    
    layout.addWidget(content_label)
    layout.addWidget(close_button, 0, Qt.AlignRight)
    
    return dialog

def is_high_contrast_mode_enabled():
    """
    Detecta si el sistema está en modo de alto contraste.
    
    Returns:
        bool: True si está habilitado el modo de alto contraste
    """
    # En Windows
    if platform.system() == 'Windows':
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               r"Control Panel\Accessibility\HighContrast")
            value, _ = winreg.QueryValueEx(key, "Flags")
            return (value & 1) == 1  # Bit 0 indicates high contrast
        except Exception:
            pass
    
    # En otros sistemas, podemos verificar a través de variables de entorno o configuración
    # Por ahora, simplemente devolvemos False
    return False