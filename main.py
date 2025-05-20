import os
import sys
from pathlib import Path
import importlib
import argparse
from loguru import logger

# Cambiar el directorio de trabajo al directorio del script
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Asegurar que el directorio de la aplicación esté en el PYTHONPATH
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QPixmap

# Importar componentes del proyecto
from ui.main_window import MainWindow
from core.pdf_loader import PDFLoader
from utils.ui_utils import setup_logger, set_application_style, show_error_message

def verify_dependencies():
    """Verifica que todas las dependencias críticas estén instaladas"""
    # Mapeo de paquetes a sus nombres de módulo para importación
    packages_modules = {
        'PySide6': 'PySide6',
        'pymupdf': 'fitz',
        'pikepdf': 'pikepdf',
        'pdfplumber': 'pdfplumber',
        'pytesseract': 'pytesseract',
        'opencv-python': 'cv2',
        'Pillow': 'PIL',
        'loguru': 'loguru'
    }
    
    missing_packages = []
    
    for package, module in packages_modules.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Faltan las siguientes dependencias: {', '.join(missing_packages)}")
        print("Instale las dependencias necesarias con: pip install -r requirements.txt")
        return False
    
    return True

def parse_arguments():
    """Procesa los argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(description='PDF/UA Editor - Remediación de PDFs accesibles')
    parser.add_argument('file', nargs='?', help='Archivo PDF para abrir')
    parser.add_argument('--debug', action='store_true', help='Habilitar modo de depuración')
    parser.add_argument('--style', choices=['system', 'fusion', 'dark'], default='system',
                        help='Estilo visual de la aplicación')
    parser.add_argument('--dump-structure', action='store_true', help='Guardar estructura del PDF en archivo JSON')
    
    return parser.parse_args()

def setup_application(args):
    """Configura la aplicación, incluyendo registros y estilo visual"""
    # Crear directorios de logs si no existen
    log_path = Path("./logs")
    log_path.mkdir(exist_ok=True)
    
    # Configurar nivel de log basado en argumentos
    if args.debug:
        # Establecer variable de entorno para nivel de log (utilizada por setup_logger)
        os.environ["PDFUA_LOG_LEVEL"] = "DEBUG"
    
    # Configurar logger usando la ruta del archivo
    setup_logger(log_path / "pdfua_editor.log")
    
    logger.info("Iniciando PDF/UA Editor")
    
    # Configurar aplicación Qt con soporte para alta DPI
    if hasattr(Qt, 'HighDpiScaleFactorRoundingPolicy'):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    
    QCoreApplication.setOrganizationName("PDF/UA Editor")
    QCoreApplication.setApplicationName("PDF/UA Editor")
    QCoreApplication.setApplicationVersion("1.0.0")
    
    # Crear y configurar la aplicación
    app = QApplication(sys.argv)
    
    # Aplicar estilo
    if args.style == 'system':
        set_application_style(app)
    elif args.style == 'dark':
        try:
            import qdarkstyle
            app.setStyleSheet(qdarkstyle.load_stylesheet_pyside6())
            logger.info("Usando tema oscuro (qdarkstyle)")
        except ImportError:
            logger.warning("No se pudo cargar qdarkstyle. Usando estilo predeterminado.")
            set_application_style(app)
    elif args.style == 'fusion':
        app.setStyle('Fusion')
        logger.info("Usando estilo Fusion")
    
    return app

def create_splash_screen():
    """Crea y devuelve una pantalla de bienvenida"""
    # Intentar cargar el logo desde recursos, si no existe usar uno básico
    splash_img_path = Path(__file__).parent / "resources" / "images" / "splash.png"
    
    if splash_img_path.exists():
        pixmap = QPixmap(str(splash_img_path))
    else:
        # Crear un pixmap básico si no hay imagen
        pixmap = QPixmap(500, 300)
        pixmap.fill(Qt.blue)
    
    splash = QSplashScreen(pixmap)
    splash.showMessage(
        "Iniciando PDF/UA Editor...\nVerificando dependencias y conformidad con ISO 14289-1", 
        Qt.AlignBottom | Qt.AlignCenter, 
        Qt.white
    )
    
    return splash

def main():
    """Función principal que inicia la aplicación"""
    try:
        # Verificar dependencias
        if not verify_dependencies():
            sys.exit(1)
        
        # Procesar argumentos
        args = parse_arguments()
        
        # Configurar aplicación primero (¡importante!)
        app = setup_application(args)
        
        # Ahora podemos crear el splash screen (después de QApplication)
        splash = create_splash_screen()
        splash.show()
        
        # Actualizar splash
        splash.showMessage(
            "Cargando componentes...", 
            Qt.AlignBottom | Qt.AlignCenter, 
            Qt.white
        )
        app.processEvents()
        
        # Crear ventana principal
        main_window = MainWindow()
        
        # Actualizar splash
        splash.showMessage(
            "Inicializando interfaz...", 
            Qt.AlignBottom | Qt.AlignCenter, 
            Qt.white
        )
        app.processEvents()
        
        # Mostrar ventana principal y cerrar splash
        main_window.show()
        splash.finish(main_window)
        
        # Si se proporcionó un archivo, abrirlo
        if args.file and os.path.isfile(args.file):
            main_window.load_file(args.file)
            
            # Si se solicitó guardar la estructura, hacerlo
            if args.dump_structure and hasattr(main_window, 'pdf_loader') and main_window.pdf_loader:
                if main_window.pdf_loader.structure_tree:
                    structure_file = main_window.pdf_loader.save_structure_tree()
                    if structure_file:
                        logger.info(f"Estructura guardada en: {structure_file}")
                else:
                    logger.warning("No se pudo guardar la estructura: no existe árbol de estructura")
        
        # Ejecutar loop principal
        sys.exit(app.exec())
        
    except Exception as e:
        logger.exception(f"Error inesperado durante la inicialización: {e}")
        
        # Mostrar diálogo de error si la aplicación ya está inicializada
        if QApplication.instance():
            show_error_message(None, "Error de inicialización", 
                           f"Ha ocurrido un error al iniciar la aplicación:\n{str(e)}")
        else:
            print(f"Error crítico: {str(e)}")
            # Mantener la consola abierta para ver el error
            input("Presiona Enter para salir...")
        
        sys.exit(1)

if __name__ == "__main__":
    main()