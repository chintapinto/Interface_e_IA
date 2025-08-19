import cv2
import json
from PySide6.QtWidgets import (QLabel, QDialog, QVBoxLayout, QHBoxLayout, QMessageBox,
                               QLineEdit, QPushButton, QCheckBox, QComboBox, QWidget, QFormLayout)
from PySide6.QtCore import QTimer, Qt, QPoint, QRect, Signal
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor

class LiveViewDialog(QDialog):
    def __init__(self, cam_name, cam_url, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Ao Vivo: {cam_name}")
        self.setMinimumSize(480, 360)
        self.setWindowModality(Qt.NonModal)
        self.video_label = QLabel("Conectando...", self)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_label)
        self.cap = cv2.VideoCapture(cam_url)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_frame)
        if not self.cap.isOpened():
            self.video_label.setText(f"Falha ao conectar à câmera:\n{cam_url}")
        else:
            self.timer.start()

    def update_frame(self):
        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qt_image)
                self.video_label.setPixmap(
                    pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.video_label.setText("Sinal de vídeo perdido.")
                self.timer.stop()
        else:
            self.video_label.setText("Não foi possível conectar à câmera.")
            self.timer.stop()

    def closeEvent(self, event):
        self.timer.stop()
        if self.cap.isOpened(): self.cap.release()
        event.accept()

class ClickableLabel(QLabel):
    roiSelected = Signal(QRect)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.begin = QPoint()
        self.end = QPoint()
        self.drawing = False

    def mousePressEvent(self, event):
        self.begin = event.position().toPoint()
        self.end = self.begin
        self.drawing = True
        self.update()

    def mouseMoveEvent(self, event):
        if self.drawing: self.end = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event):
        if not self.drawing: return
        self.drawing = False
        self.end = event.position().toPoint()
        self.roiSelected.emit(QRect(self.begin, self.end).normalized())
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.begin.isNull() and not self.end.isNull():
            painter = QPainter(self)
            painter.setPen(QPen(QColor("#A3BE8C"), 2, Qt.SolidLine))
            painter.drawRect(QRect(self.begin, self.end).normalized())

class ROISelector(QDialog):
    def __init__(self, video_url, existing_roi=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Definir Área - Carregando imagem...")
        self.video_url = video_url
        self.cap = cv2.VideoCapture(self.video_url)
        self.image_label = ClickableLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.roiSelected.connect(self.on_roi_selected)
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.image_label)
        self.setMinimumSize(800, 600)
        self.roi_rect = None
        self.original_frame = None
        self.original_frame_size = None
        self.initial_roi_coords = existing_roi
        if not self.cap.isOpened():
            QMessageBox.critical(self, "Erro", f"Não foi possível conectar à câmera em {self.video_url}")
            QTimer.singleShot(0, self.reject)
        else:
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.try_capture_frame)
            self.timer.start(50)

    def try_capture_frame(self):
        if not self.cap.isOpened(): self.timer.stop(); return
        ret, frame = self.cap.read()
        if ret:
            self.timer.stop()
            self.cap.release()
            self.original_frame = frame
            h, w, _ = self.original_frame.shape
            self.original_frame_size = (w, h)
            self.setWindowTitle("Definir Área - Arraste o mouse para desenhar")
            self.update_display()
            if self.initial_roi_coords: self.draw_existing_roi()

    def draw_existing_roi(self):
        if self.original_frame_size is None: return
        orig_y1, orig_y2, orig_x1, orig_x2 = self.initial_roi_coords
        original_w, original_h = self.original_frame_size
        displayed_pixmap = self.image_label.pixmap()
        if not displayed_pixmap or displayed_pixmap.isNull(): return
        displayed_w = displayed_pixmap.width()
        displayed_h = displayed_pixmap.height()
        x_scale = displayed_w / original_w
        y_scale = displayed_h / original_h
        x_offset = (self.image_label.width() - displayed_w) / 2
        y_offset = (self.image_label.height() - displayed_h) / 2
        display_x1 = int(orig_x1 * x_scale + x_offset)
        display_y1 = int(orig_y1 * y_scale + y_offset)
        display_x2 = int(orig_x2 * x_scale + x_offset)
        display_y2 = int(orig_y2 * y_scale + y_offset)
        self.image_label.begin = QPoint(display_x1, display_y1)
        self.image_label.end = QPoint(display_x2, display_y2)
        self.image_label.update()

    def update_display(self):
        if self.original_frame is None: return
        h, w, _ = self.original_frame.shape
        bytes_per_line = 3 * w
        rgb_image = cv2.cvtColor(self.original_frame, cv2.COLOR_BGR2RGB)
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)

    def on_roi_selected(self, selection_rect):
        if self.original_frame_size is None: return
        original_w, original_h = self.original_frame_size
        displayed_pixmap = self.image_label.pixmap()
        if not displayed_pixmap or displayed_pixmap.isNull(): return
        displayed_w, displayed_h = displayed_pixmap.width(), displayed_pixmap.height()
        if displayed_w == 0 or displayed_h == 0: return
        x_scale = original_w / displayed_w
        y_scale = original_h / displayed_h
        x_offset = (self.image_label.width() - displayed_w) / 2
        y_offset = (self.image_label.height() - displayed_h) / 2
        orig_x1 = int((selection_rect.left() - x_offset) * x_scale)
        orig_y1 = int((selection_rect.top() - y_offset) * y_scale)
        orig_x2 = int((selection_rect.right() - x_offset) * x_scale)
        orig_y2 = int((selection_rect.bottom() - y_offset) * y_scale)
        self.roi_rect = [max(0, orig_y1), min(original_h, orig_y2), max(0, orig_x1), min(original_w, orig_x2)]
        self.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_display()
        if self.initial_roi_coords: self.draw_existing_roi()

    def closeEvent(self, event):
        if self.cap.isOpened(): self.cap.release()
        super().closeEvent(event)

    @staticmethod
    def get_roi(video_url, existing_roi=None, parent=None):
        dialog = ROISelector(video_url, existing_roi, parent)
        if dialog.exec() == QDialog.Accepted: return dialog.roi_rect
        return None

class CameraConfigDialog(QDialog):
    def __init__(self, cam_name, cam_data, row, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Câmera")
        self.row = row
        self.layout = QVBoxLayout(self)
        self.roi_coords = None

        # --- Campos Comuns ---
        self.form_layout = QFormLayout()
        self.name_edit = QLineEdit()
        self.url_edit = QLineEdit()
        self.rearm_time_edit = QLineEdit("5")
        self.rearm_time_edit.setPlaceholderText("0 para desativar")

        self.form_layout.addRow("Nome da Câmera:", self.name_edit)
        self.form_layout.addRow("URL do Vídeo (RTSP/HTTP/0):", self.url_edit)
        self.form_layout.addRow("Tempo de Rearme (s):", self.rearm_time_edit)

        # --- Seletor de Modo ---
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Leitura de Temperatura (OCR)", "Detecção de Objetos (YOLO)"])
        self.form_layout.addRow("Modo de Operação:", self.mode_combo)

        self.layout.addLayout(self.form_layout)

        # --- Container para Configs de Temperatura ---
        self.temp_widget = QWidget()
        temp_layout = QFormLayout(self.temp_widget)
        temp_layout.setContentsMargins(0, 10, 0, 0)
        self.limite_edit = QLineEdit()
        self.receptor_edit = QLineEdit()
        self.receptor_port_edit = QLineEdit("5000")
        self.set_roi_button = QPushButton("Definir Área de Leitura (ROI)")
        self.roi_label = QLabel("Área não definida")
        self.gpu_checkbox_ocr = QCheckBox("Usar GPU (EasyOCR)")

        temp_layout.addRow("Limite de Temperatura (°C):", self.limite_edit)
        temp_layout.addRow("URL do PC Receptor:", self.receptor_edit)
        temp_layout.addRow("Porta do Receptor:", self.receptor_port_edit)
        temp_layout.addRow(self.set_roi_button)
        temp_layout.addRow(self.roi_label)
        temp_layout.addRow(self.gpu_checkbox_ocr)
        self.layout.addWidget(self.temp_widget)

        # --- Container para Configs de Detecção de Objetos ---
        self.yolo_widget = QWidget()
        yolo_layout = QFormLayout(self.yolo_widget)
        yolo_layout.setContentsMargins(0, 10, 0, 0)
        self.object_ids_edit = QLineEdit()
        self.object_ids_edit.setPlaceholderText("Ex: 0, 67 (separados por vírgula)")

        self.quantity_edit = QLineEdit("1")
        self.exact_number_checkbox = QCheckBox("Ativar contagem exata")
        self.sensitivity_edit = QLineEdit("0")
        self.sensitivity_edit.setPlaceholderText("Tempo que a condição deve durar")

        self.gpu_checkbox_yolo = QCheckBox("Tentar usar GPU (se disponível)")
        self.gpu_checkbox_yolo.setChecked(True)

        yolo_layout.addRow("IDs dos Objetos a Detectar:", self.object_ids_edit)
        yolo_layout.addRow("Quantidade de Objetos:", self.quantity_edit)
        yolo_layout.addRow("Número Exato:", self.exact_number_checkbox)
        yolo_layout.addRow("Sensibilidade (s):", self.sensitivity_edit)
        yolo_layout.addRow(self.gpu_checkbox_yolo)
        self.layout.addWidget(self.yolo_widget)

        # --- Botões ---
        self.layout.addStretch()
        buttons_layout = QHBoxLayout()
        self.live_view_button = QPushButton("Ver ao Vivo")
        self.save_button = QPushButton("Salvar")
        buttons_layout.addWidget(self.live_view_button)
        buttons_layout.addWidget(self.save_button)
        self.layout.addLayout(buttons_layout)

        # --- Conexões de Sinais ---
        self.mode_combo.currentIndexChanged.connect(self.update_ui_for_mode)
        self.set_roi_button.clicked.connect(self.set_roi)
        self.save_button.clicked.connect(self.accept)
        self.live_view_button.clicked.connect(self.show_live_view)

        if cam_name and cam_data:
            self.load_config(cam_name, cam_data)
        else:
            self.update_ui_for_mode(0)

        self.live_dialog = None

    def update_ui_for_mode(self, index):
        if index == 0:
            self.temp_widget.show()
            self.yolo_widget.hide()
        elif index == 1:
            self.temp_widget.hide()
            self.yolo_widget.show()

    def load_config(self, name, data):
        self.name_edit.setText(name)
        self.url_edit.setText(data.get('url', ''))
        self.rearm_time_edit.setText(str(data.get('rearm_time', 5)))

        mode = data.get('mode', 'temperature')
        if mode == 'object':
            self.mode_combo.setCurrentIndex(1)
            self.object_ids_edit.setText(data.get('object_ids', ''))
            self.quantity_edit.setText(str(data.get('quantity', 1)))
            self.exact_number_checkbox.setChecked(data.get('exact_number', False))
            self.sensitivity_edit.setText(str(data.get('sensitivity', 0)))
            self.gpu_checkbox_yolo.setChecked(data.get('use_gpu', True))
        else: # Padrão é temperatura
            self.mode_combo.setCurrentIndex(0)
            self.limite_edit.setText(str(data.get('limite', '')))
            self.receptor_edit.setText(data.get('receptor', ''))
            self.receptor_port_edit.setText(str(data.get('receptor_port', '5000')))
            self.roi_coords = data.get('roi')
            self.gpu_checkbox_ocr.setChecked(data.get('gpu', False))
            if self.roi_coords:
                self.roi_label.setText(f"Área definida: {self.roi_coords}")
                self.roi_label.setStyleSheet("color: #A3BE8C;")

    def get_config(self):
        config = {'name': self.name_edit.text(), 'url': self.url_edit.text()}

        if not all([config['name'], config['url'], self.rearm_time_edit.text()]):
            QMessageBox.critical(self, "Erro", "Nome, URL e Tempo de Rearme são obrigatórios.")
            return None

        try:
            config['rearm_time'] = int(self.rearm_time_edit.text())
        except ValueError:
            QMessageBox.critical(self, "Erro", "O Tempo de Rearme deve ser um número inteiro.")
            return None

        mode_index = self.mode_combo.currentIndex()
        if mode_index == 0:
            config['mode'] = 'temperature'
            try:
                config['limite'] = float(self.limite_edit.text().replace(',', '.'))
                config['receptor_port'] = int(self.receptor_port_edit.text())
                config['receptor'] = self.receptor_edit.text()
                config['gpu'] = self.gpu_checkbox_ocr.isChecked()
                config['roi'] = self.roi_coords
                if not all([config['receptor'], self.roi_coords]):
                    raise ValueError("Campos obrigatórios não preenchidos.")
            except (ValueError, TypeError):
                QMessageBox.critical(self, "Erro",
                    "Para o modo Temperatura, verifique se todos os campos estão corretos e se a ROI foi definida.")
                return None
        elif mode_index == 1:
            config['mode'] = 'object'
            try:
                object_ids = self.object_ids_edit.text().strip()
                if not object_ids:
                    raise ValueError("IDs dos Objetos não pode estar vazio.")
                config['object_ids'] = object_ids
                config['quantity'] = int(self.quantity_edit.text())
                config['exact_number'] = self.exact_number_checkbox.isChecked()
                config['sensitivity'] = int(self.sensitivity_edit.text())
                config['use_gpu'] = self.gpu_checkbox_yolo.isChecked()
            except (ValueError, TypeError) as e:
                QMessageBox.critical(self, "Erro",
                    f"Dados inválidos para o modo YOLO. Verifique se os IDs estão preenchidos e se Quantidade e Sensibilidade são números inteiros.\nDetalhe: {e}")
                return None
        return config

    def show_live_view(self):
        cam_url_text = self.url_edit.text()
        if not cam_url_text:
            QMessageBox.warning(self, "Atenção", "É necessário preencher a URL do vídeo.")
            return
        cam_url = int(cam_url_text) if cam_url_text.isdigit() else cam_url_text
        self.live_dialog = LiveViewDialog(self.name_edit.text(), cam_url, self)
        self.live_dialog.show()

    def set_roi(self):
        video_url_text = self.url_edit.text()
        if not video_url_text:
            QMessageBox.warning(self, "Atenção", "Por favor, insira a URL do vídeo primeiro.")
            return
        video_url = int(video_url_text) if video_url_text.isdigit() else video_url_text
        roi = ROISelector.get_roi(video_url, self.roi_coords, self)
        if roi:
            self.roi_coords = roi
            self.roi_label.setText(f"Área definida: {self.roi_coords}")
            self.roi_label.setStyleSheet("color: #A3BE8C;")