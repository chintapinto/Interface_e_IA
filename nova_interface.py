#Nova interface
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QScrollArea, QGridLayout, QLineEdit
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor


class ColorPalette:
    """
    Centralizes the color palette for the entire application.
    """
    # Theme Colors
    PRIMARY = "#3B82F6"
    PRIMARY_HOVER = "#2563EB"
    PRIMARY_PRESSED = "#1D4ED8"
    BACKGROUND = "#EFEEEB"
    SURFACE = "#FFFFFF"

    # Text Colors
    TEXT_PRIMARY = "#111827"
    TEXT_SECONDARY = "#6B7280"
    TEXT_ON_PRIMARY = "#FFFFFF"

    # Status Colors
    STATUS_GREEN = "#10B981"
    STATUS_GREEN_HOVER = "#059669"
    STATUS_GRAY = "#6B7280"
    STATUS_RED = "#EF4444"
    STATUS_RED_HOVER = "#DC2626"
    STATUS_YELLOW = "#F59E0B"

    # UI Elements & Borders
    BORDER = "#E5E7EB"
    INPUT_BACKGROUND = "#F3F4F6"


class StatusIndicator(QFrame):
    def __init__(self, status="offline"):
        super().__init__()
        self.setFixedSize(10, 10)
        self.status = status
        self.update_status(status)

    def update_status(self, status):
        self.status = status
        colors = {
            "online": ColorPalette.STATUS_GREEN,
            "offline": ColorPalette.STATUS_GRAY,
            "error": ColorPalette.STATUS_RED,
            "warning": ColorPalette.STATUS_YELLOW
        }
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {colors.get(status, ColorPalette.STATUS_GRAY)};
                border-radius: 5px;
                border: none;
            }}
        """)


class CameraCard(QFrame):
    def __init__(self, name, url="rtsp://...", status="offline"):
        super().__init__()
        self.setFixedHeight(160)
        # Removido o efeito hover e contornos para aparência mais limpa
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ColorPalette.SURFACE};
                border-radius: 8px;
                border: none;
                margin: 2px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(0)

        self.status_indicator = StatusIndicator(status)

        name_label = QLabel(name)
        name_label.setStyleSheet(f"""
            QLabel {{
                font-weight: 600;
                font-size: 15px;
                color: {ColorPalette.TEXT_PRIMARY};
                margin-left: 8px;
            }}
        """)

        status_text_map = {"online": "Online", "offline": "Offline", "error": "Erro", "warning": "Atenção"}
        status_label = QLabel(status_text_map.get(status, "Offline"))
        status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {ColorPalette.TEXT_SECONDARY};
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
        """)

        header_layout.addWidget(self.status_indicator)
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        header_layout.addWidget(status_label)

        # URL
        url_label = QLabel(url)
        url_label.setStyleSheet(f"""
            QLabel {{
                color: {ColorPalette.TEXT_SECONDARY};
                font-size: 12px;
                font-family: 'Consolas', 'Monaco', monospace;
                background-color: {ColorPalette.INPUT_BACKGROUND};
                padding: 6px 8px;
                border-radius: 6px;
                border: 1px solid {ColorPalette.BORDER};
            }}
        """)
        url_label.setWordWrap(True)

        # Action Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)

        self.view_btn = QPushButton("Visualizar")
        self.start_btn = QPushButton("Iniciar")
        self.stop_btn = QPushButton("Parar")
        self.config_btn = QPushButton("⚙")
        self.delete_btn = QPushButton("🗑")

        primary_style = """
            QPushButton {
                font-size: 12px;
                font-weight: 500;
                border-radius: 6px;
                padding: 8px 12px;
                border: none;
            }
        """

        self.view_btn.setStyleSheet(primary_style + f"""
            QPushButton {{
                background-color: {ColorPalette.PRIMARY};
                color: {ColorPalette.TEXT_ON_PRIMARY};
            }}
            QPushButton:hover {{ background-color: {ColorPalette.PRIMARY_HOVER}; }}
            QPushButton:pressed {{ background-color: {ColorPalette.PRIMARY_PRESSED}; }}
        """)

        self.start_btn.setStyleSheet(primary_style + f"""
            QPushButton {{
                background-color: {ColorPalette.STATUS_GREEN};
                color: {ColorPalette.TEXT_ON_PRIMARY};
            }}
            QPushButton:hover {{ background-color: {ColorPalette.STATUS_GREEN_HOVER}; }}
        """)

        self.stop_btn.setStyleSheet(primary_style + f"""
            QPushButton {{
                background-color: {ColorPalette.STATUS_RED};
                color: {ColorPalette.TEXT_ON_PRIMARY};
            }}
            QPushButton:hover {{ background-color: {ColorPalette.STATUS_RED_HOVER}; }}
        """)

        icon_style = f"""
            QPushButton {{
                background-color: {ColorPalette.SURFACE};
                border: 1px solid {ColorPalette.BORDER};
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
                color: {ColorPalette.TEXT_SECONDARY};
                width: 32px;
                height: 32px;
            }}
            QPushButton:hover {{
                background-color: {ColorPalette.INPUT_BACKGROUND};
                border-color: #D1D5DB;
            }}
            QPushButton:pressed {{ background-color: {ColorPalette.BORDER}; }}
        """

        self.config_btn.setStyleSheet(icon_style)
        self.delete_btn.setStyleSheet(icon_style + f"""
            QPushButton:hover {{
                background-color: #FEF2F2;
                border-color: #FECACA;
                color: {ColorPalette.STATUS_RED_HOVER};
            }}
        """)

        buttons_layout.addWidget(self.view_btn)
        buttons_layout.addWidget(self.start_btn)
        buttons_layout.addWidget(self.stop_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.config_btn)
        buttons_layout.addWidget(self.delete_btn)

        layout.addLayout(header_layout)
        layout.addWidget(url_label)
        layout.addLayout(buttons_layout)


class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gitel - Sistema de Monitoramento Inteligente")
        self.setGeometry(100, 100, 1400, 800)

        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {ColorPalette.BACKGROUND};
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
        """)

        main_layout = QHBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        sidebar = self.create_sidebar()
        content_widget = self.create_content_area()

        main_layout.addWidget(sidebar)
        main_layout.addWidget(content_widget)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def create_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(280)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {ColorPalette.PRIMARY};
                border: none;
            }}
        """)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        header_container = QWidget()
        header_container.setFixedHeight(100)
        header_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)

        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(12, 0, 12, 0)

        logo_label = QLabel("Gitel")
        logo_label.setStyleSheet(f"""
            QLabel {{
                color: {ColorPalette.TEXT_ON_PRIMARY};
                font-size: 24px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
        """)
        subtitle = QLabel("Sistema de Monitoramento")
        subtitle.setStyleSheet(f"""
            QLabel {{
                color: rgba(255, 255, 255, 0.8);
                font-size: 12px;
                font-weight: 400;
                margin-top: 2px;
            }}
        """)
        header_layout.addStretch()
        header_layout.addWidget(logo_label)
        header_layout.addWidget(subtitle)
        header_layout.addStretch()

        nav_container = QWidget()
        # Adicionado relevo sutil entre header e navegação
        nav_container.setStyleSheet("""
            QWidget {
                border-top: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
            }
        """)

        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(4, 24, 4, 0)
        nav_layout.setSpacing(4)

        menu_buttons = [("", "Câmeras", True), ("", "Dashboard", False), ("", "Log de Eventos", False),
                        ("", "Configurações", False)]
        button_style = f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 12px 8px;
                text-align: left;
                color: rgba(255, 255, 255, 0.9);
                font-weight: 500;
                font-size: 14px;
            }}
            QPushButton:hover {{ background-color: rgba(255, 255, 255, 0.1); }}
        """
        active_style = button_style + f"""
            QPushButton {{
                background-color: rgba(0, 0, 0, 0.2);
                color: {ColorPalette.TEXT_ON_PRIMARY};
                font-weight: 600;
            }}
        """
        for icon, text, is_active in menu_buttons:
            btn = QPushButton(f"{icon}  {text}")
            btn.setStyleSheet(active_style if is_active else button_style)
            nav_layout.addWidget(btn)
        nav_layout.addStretch()

        add_btn = QPushButton("Adicionar Câmera")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ColorPalette.TEXT_ON_PRIMARY};
                border: none;
                color: {ColorPalette.PRIMARY};
                text-align: center;
                font-weight: 600;
                font-size: 14px;
                border-radius: 8px;
                padding: 14px;
                margin: 0 20px 24px 20px;
            }}
            QPushButton:hover {{ background-color: #F0F9FF; }}
            QPushButton:pressed {{ background-color: #E0F2FE; }}
        """)

        sidebar_layout.addWidget(header_container)
        sidebar_layout.addWidget(nav_container)
        sidebar_layout.addWidget(add_btn)
        return sidebar

    def create_content_area(self):
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(32, 32, 32, 32)
        content_layout.setSpacing(24)

        page_header = QHBoxLayout()
        title_container = QVBoxLayout()
        title = QLabel("Câmeras Conectadas")
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 28px;
                font-weight: 700;
                color: {ColorPalette.TEXT_PRIMARY};
                margin: 0;
            }}
        """)
        breadcrumb = QLabel("Dashboard / Câmeras")
        breadcrumb.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                color: {ColorPalette.TEXT_SECONDARY};
                margin-top: 4px;
            }}
        """)
        title_container.addWidget(title)
        title_container.addWidget(breadcrumb)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Buscar câmeras...")
        search_input.setFixedWidth(300)
        search_input.setFixedHeight(40)
        search_input.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {ColorPalette.BORDER};
                border-radius: 8px;
                padding: 0 16px;
                font-size: 14px;
                background-color: {ColorPalette.SURFACE};
            }}
            QLineEdit:focus {{
                border-color: {ColorPalette.PRIMARY};
            }}
        """)
        page_header.addLayout(title_container)
        page_header.addStretch()
        page_header.addWidget(search_input)

        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(24)
        stats_data = [
            ("12 Online", ColorPalette.STATUS_GREEN),
            ("3 Offline", ColorPalette.STATUS_GRAY),
            ("2 Alertas", ColorPalette.STATUS_RED),
            ("15 Total", ColorPalette.PRIMARY)
        ]
        for text, color in stats_data:
            stat_label = QLabel(text)
            stat_label.setStyleSheet(f"""
                QLabel {{
                    font-size: 16px;
                    font-weight: 600;
                    color: {color};
                    padding: 8px 16px;
                    background-color: transparent;
                }}
            """)
            stats_layout.addWidget(stat_label)
        stats_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_layout = QGridLayout(scroll_content)
        scroll_layout.setContentsMargins(4, 4, 4, 4)
        scroll_layout.setSpacing(20)
        scroll_layout.setAlignment(Qt.AlignTop)

        cameras_data = [
            ("Câmera Entrada Principal", "rtsp://192.168.0.101:554/stream", "online"),
            ("Câmera Estacionamento", "rtsp://192.168.0.102:554/stream", "online"),
            ("Câmera Recepção", "rtsp://192.168.0.103:554/stream", "warning"),
            ("Câmera Corredor Norte", "rtsp://192.168.0.104:554/stream", "offline"),
            ("Câmera Área Externa", "rtsp://192.168.0.105:554/stream", "online"),
            ("Câmera Sala de Reuniões", "rtsp://192.168.0.106:554/stream", "error"),
        ]
        for i, (name, url, status) in enumerate(cameras_data):
            cam = CameraCard(name, url, status)
            scroll_layout.addWidget(cam, i // 2, i % 2)

        scroll.setWidget(scroll_content)

        content_layout.addLayout(page_header)
        content_layout.addLayout(stats_layout)
        content_layout.addWidget(scroll)

        return content_widget


if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    window = Dashboard()
    window.show()
    sys.exit(app.exec())