import cv2
import numpy as np
from PySide6.QtWidgets import (QApplication, QLabel, QDialog, QVBoxLayout, QHBoxLayout, QMessageBox,
                               QLineEdit, QPushButton, QCheckBox, QComboBox, QWidget,
                               QFormLayout, QGroupBox, QStackedWidget, QSizePolicy)
from PySide6.QtCore import QTimer, Qt, QPoint, QRect, Signal, QSize
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QCursor, QPolygon

# (O dicionário YOLO_CLASSES permanece o mesmo)
YOLO_CLASSES = {0: 'pessoa', 1: 'bicicleta', 2: 'carro', 3: 'motocicleta', 4: 'avião', 5: 'ônibus', 6: 'trem',
                7: 'caminhão', 8: 'barco', 9: 'semáforo', 10: 'hidrante', 11: 'placa de pare', 12: 'parquímetro',
                13: 'banco', 14: 'pássaro', 15: 'gato', 16: 'cão', 17: 'cavalo', 18: 'ovelha', 19: 'vaca',
                20: 'elefante', 21: 'urso', 22: 'zebra', 23: 'girafa', 24: 'mochila', 25: 'guarda-chuva', 26: 'bolsa',
                27: 'gravata', 28: 'mala', 29: 'frisbee', 30: 'esquis', 31: 'snowboard', 32: 'bola esportiva',
                33: 'pipa', 34: 'taco de beisebol', 35: 'luva de beisebol', 36: 'skate', 37: 'prancha de surfe',
                38: 'raquete de tênis', 39: 'garrafa', 40: 'taça de vinho', 41: 'copo', 42: 'garfo', 43: 'faca',
                44: 'colher', 45: 'tigela', 46: 'banana', 47: 'maçã', 48: 'sanduíche', 49: 'laranja', 50: 'brócolis',
                51: 'cenoura', 52: 'cachorro-quente', 53: 'pizza', 54: 'donut', 55: 'bolo', 56: 'cadeira', 57: 'sofá',
                58: 'vaso de planta', 59: 'cama', 60: 'mesa de jantar', 61: 'vaso sanitário', 62: 'tv', 63: 'laptop',
                64: 'mouse', 65: 'controle remoto', 66: 'teclado', 67: 'celular', 68: 'micro-ondas', 69: 'forno',
                70: 'torradeira', 71: 'pia', 72: 'geladeira', 73: 'livro', 74: 'relógio', 75: 'vaso', 76: 'tesoura',
                77: 'ursinho de pelúcia', 78: 'secador de cabelo', 79: 'escova de dentes'}


class LiveViewDialog(QDialog):
    def __init__(self, cam_config, parent=None):
        super().__init__(parent)
        self.cam_config = cam_config
        self.cam_name = cam_config.get('name', 'Câmera')
        cam_url_text = cam_config.get('url')

        cam_url = int(cam_url_text) if cam_url_text.isdigit() else cam_url_text

        self.setWindowTitle(f"Ao Vivo: {self.cam_name}")
        self.setMinimumSize(640, 480)
        self.setWindowModality(Qt.NonModal)
        self.video_label = QLabel("Conectando...", self)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_label)

        self.latest_detections = None
        self.target_ids = []
        if self.cam_config.get('mode') == 'object':
            try:
                self.target_ids = [int(i.strip()) for i in self.cam_config.get('object_ids', '').split(',')]
            except ValueError:
                self.target_ids = []

        if isinstance(cam_url, int):
            self.cap = cv2.VideoCapture(cam_url, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(cam_url)

        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.update_frame)

        if not self.cap.isOpened():
            self.video_label.setText(f"Falha ao conectar à câmera:\n{cam_url_text}")
        else:
            self.timer.start()

    def update_detections(self, detection_data):
        self.latest_detections = detection_data

    def _draw_detections_on_frame(self, frame):
        if not self.latest_detections:
            return frame

        roi_points = self.latest_detections.get('roi')
        if roi_points and len(roi_points) > 2:
            pts = np.array(roi_points, np.int32)
            pts = pts.reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], isClosed=True, color=(255, 0, 0), thickness=2)

        offset_x, offset_y = self.latest_detections.get('offset', (0, 0))

        for det in self.latest_detections.get('detections', []):
            x1, y1, x2, y2, conf, cls_id = det
            x1, y1, x2, y2 = int(x1 + offset_x), int(y1 + offset_y), int(x2 + offset_x), int(y2 + offset_y)

            if int(cls_id) in self.target_ids:
                label = f"{YOLO_CLASSES.get(int(cls_id), f'ID:{int(cls_id)}')}: {conf:.2f}"
                color = (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        return frame

    def update_frame(self):
        if not self.cap.isOpened():
            self.video_label.setText("Não foi possível conectar à câmera.")
            self.timer.stop()
            return

        ret, frame = self.cap.read()
        if ret:
            if self.cam_config.get('mode') == 'object':
                frame = self._draw_detections_on_frame(frame)

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

    def closeEvent(self, event):
        self.timer.stop()
        if self.cap.isOpened(): self.cap.release()
        if self.parent():
            self.parent().on_live_view_closed(self.cam_name)
        event.accept()


class PolygonRoiLabel(QLabel):
    handle_size = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.polygon_closed = False
        self.dragging_point_index = -1
        self.dragging_polygon = False
        self.start_drag_pos = QPoint()
        self.start_drag_points = []
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.points:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pen = QPen(QColor("#A3BE8C"), 2, Qt.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        if len(self.points) > 1:
            painter.drawPolyline(self.points)

        if not self.polygon_closed and len(self.points) > 0:
            painter.drawLine(self.points[-1], self.mapFromGlobal(QCursor.pos()))

        handle_color = QColor("#D8DEE9")
        pen.setWidth(1)
        pen.setColor(QColor("#2E3440"))
        painter.setPen(pen)

        for i, p in enumerate(self.points):
            if i == 0 and not self.polygon_closed and len(self.points) > 2:
                painter.setBrush(QColor("#BF616A"))
            else:
                painter.setBrush(handle_color)
            painter.drawEllipse(p, self.handle_size // 2, self.handle_size // 2)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()

            if not self.polygon_closed and len(self.points) > 2 and self.get_handle_at(pos) == 0:
                self.polygon_closed = True
                self.points.append(self.points[0])
                self.update()
                return

            handle_index = self.get_handle_at(pos)
            if handle_index is not None:
                self.dragging_point_index = handle_index
                return

            if self.polygon_closed and QPolygon(self.points).containsPoint(pos, Qt.OddEvenFill):
                self.dragging_polygon = True
                self.start_drag_pos = pos
                self.start_drag_points = [QPoint(p) for p in self.points]
                return

            if not self.polygon_closed:
                self.points.append(pos)
                self.update()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        if self.dragging_point_index != -1:
            self.points[self.dragging_point_index] = pos
            if self.polygon_closed and (
                    self.dragging_point_index == 0 or self.dragging_point_index == len(self.points) - 1):
                self.points[0] = pos
                self.points[-1] = pos
            self.update()
        elif self.dragging_polygon:
            delta = pos - self.start_drag_pos
            self.points = [p + delta for p in self.start_drag_points]
            self.update()
        else:
            self.update_cursor(pos)

        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging_point_index = -1
            self.dragging_polygon = False

    def get_handle_at(self, pos):
        for i, p in enumerate(self.points):
            if (p - pos).manhattanLength() < self.handle_size:
                return i
        return None

    def update_cursor(self, pos):
        if self.get_handle_at(pos) is not None:
            self.setCursor(Qt.PointingHandCursor)
        elif self.polygon_closed and QPolygon(self.points).containsPoint(pos, Qt.OddEvenFill):
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.CrossCursor)


class ROISelector(QDialog):
    def __init__(self, video_url, existing_roi=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Definir Área - Carregando imagem...")

        video_source = int(video_url) if video_url.isdigit() else video_url

        if isinstance(video_source, int):
            self.cap = cv2.VideoCapture(video_source, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(video_source)

        self.image_label = PolygonRoiLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.image_label)
        self.setMinimumSize(800, 600)

        self.final_roi_points = None
        self.original_frame = None
        self.original_frame_size = None
        self.initial_roi_coords = existing_roi

        self.setup_buttons()

        if not self.cap.isOpened():
            QMessageBox.critical(self, "Erro", f"Não foi possível conectar à câmera em {video_url}")
            QTimer.singleShot(0, self.reject)
        else:
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.try_capture_frame)
            self.timer.start(50)

    def setup_buttons(self):
        buttons_layout = QHBoxLayout()
        confirm_button = QPushButton("Confirmar")
        clear_button = QPushButton("Limpar")
        cancel_button = QPushButton("Cancelar")

        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_button)
        buttons_layout.addWidget(clear_button)
        buttons_layout.addWidget(confirm_button)
        buttons_layout.addStretch()

        self.layout.addLayout(buttons_layout)

        confirm_button.clicked.connect(self.confirm_selection)
        clear_button.clicked.connect(self.clear_selection)
        cancel_button.clicked.connect(self.reject)

    def try_capture_frame(self):
        if not self.cap.isOpened(): self.timer.stop(); return
        ret, frame = self.cap.read()
        if ret:
            self.timer.stop()
            self.cap.release()
            self.original_frame = frame
            h, w, _ = self.original_frame.shape
            self.original_frame_size = (w, h)
            self.setWindowTitle("Definir Área - Clique para adicionar pontos, mova-os ou feche o polígono")
            self.update_display()
            if self.initial_roi_coords:
                self.load_existing_roi()

    def update_display(self):
        if self.original_frame is None: return
        h, w, _ = self.original_frame.shape
        bytes_per_line = 3 * w
        rgb_image = cv2.cvtColor(self.original_frame, cv2.COLOR_BGR2RGB)
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)

    def load_existing_roi(self):
        if self.original_frame_size is None or not self.initial_roi_coords: return

        pixmap_rect = self.get_pixmap_rect_in_label()
        if pixmap_rect.isNull(): return

        x_scale = pixmap_rect.width() / self.original_frame_size[0]
        y_scale = pixmap_rect.height() / self.original_frame_size[1]

        loaded_points = []
        for p in self.initial_roi_coords:
            px = int(p[0] * x_scale + pixmap_rect.left())
            py = int(p[1] * y_scale + pixmap_rect.top())
            loaded_points.append(QPoint(px, py))

        self.image_label.points = loaded_points
        if len(loaded_points) > 2:
            self.image_label.polygon_closed = True
            if loaded_points: self.image_label.points.append(loaded_points[0])
        self.image_label.update()

    def get_pixmap_rect_in_label(self):
        if not self.image_label.pixmap() or self.image_label.pixmap().isNull():
            return QRect()

        pixmap_size = self.image_label.pixmap().size()
        label_size = self.image_label.size()

        scaled_size = pixmap_size.scaled(label_size, Qt.KeepAspectRatio)

        x_offset = (label_size.width() - scaled_size.width()) / 2
        y_offset = (label_size.height() - scaled_size.height()) / 2

        return QRect(x_offset, y_offset, scaled_size.width(), scaled_size.height())

    def confirm_selection(self):
        points = self.image_label.points
        if not points or not self.original_frame_size:
            self.final_roi_points = []
            self.accept()
            return

        pixmap_rect = self.get_pixmap_rect_in_label()
        if pixmap_rect.isNull() or pixmap_rect.width() == 0 or pixmap_rect.height() == 0:
            return

        original_w, original_h = self.original_frame_size

        x_scale = original_w / pixmap_rect.width()
        y_scale = original_h / pixmap_rect.height()

        self.final_roi_points = []
        points_to_convert = points[:-1] if self.image_label.polygon_closed and len(points) > 1 else points

        for p in points_to_convert:
            orig_x = int((p.x() - pixmap_rect.left()) * x_scale)
            orig_y = int((p.y() - pixmap_rect.top()) * y_scale)
            self.final_roi_points.append([max(0, orig_x), max(0, orig_y)])

        self.accept()

    def clear_selection(self):
        self.image_label.points = []
        self.image_label.polygon_closed = False
        self.image_label.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_display()
        self.load_existing_roi()

    def closeEvent(self, event):
        if self.cap and self.cap.isOpened():
            self.cap.release()
        super().closeEvent(event)

    @staticmethod
    def get_roi(video_url, existing_roi=None, parent=None):
        dialog = ROISelector(video_url, existing_roi, parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.final_roi_points
        return existing_roi


class CameraConfigDialog(QDialog):
    def __init__(self, cam_name, cam_data, row, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Câmera")
        self.setMinimumWidth(500)
        self.row = row
        self.layout = QVBoxLayout(self)
        self.roi_coords = None

        general_groupbox = QGroupBox("Configurações Gerais")
        general_layout = QFormLayout(general_groupbox)
        self.name_edit = QLineEdit()
        self.url_edit = QLineEdit()
        self.rearm_time_edit = QLineEdit("5")
        self.rearm_time_edit.setPlaceholderText("0 para desativar")
        general_layout.addRow("Nome da Câmera:", self.name_edit)
        general_layout.addRow("URL do Vídeo (RTSP/HTTP/0):", self.url_edit)
        general_layout.addRow("Tempo de Rearme (s):", self.rearm_time_edit)
        self.layout.addWidget(general_groupbox)

        mode_groupbox = QGroupBox("Modo de Operação")
        mode_layout = QVBoxLayout(mode_groupbox)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Leitura de Temperatura (OCR)", "Detecção de Objetos (YOLO)"])
        mode_layout.addWidget(self.mode_combo)
        self.layout.addWidget(mode_groupbox)

        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)

        temp_groupbox = QGroupBox("Parâmetros de Leitura de Temperatura (OCR)")
        temp_layout = QFormLayout(temp_groupbox)
        self.limite_edit = QLineEdit()
        self.receptor_edit_ocr = QLineEdit()
        self.receptor_port_edit_ocr = QLineEdit("5000")
        self.set_roi_button = QPushButton("Definir Área de Leitura (ROI)")
        self.roi_label = QLabel("Área não definida")
        self.gpu_checkbox_ocr = QCheckBox("Usar GPU (EasyOCR)")
        temp_layout.addRow("Limite de Temperatura (°C):", self.limite_edit)
        temp_layout.addRow("URL do PC Receptor:", self.receptor_edit_ocr)
        temp_layout.addRow("Porta do Receptor:", self.receptor_port_edit_ocr)
        temp_layout.addRow(self.set_roi_button)
        temp_layout.addRow(self.roi_label)
        temp_layout.addRow(self.gpu_checkbox_ocr)
        self.stacked_widget.addWidget(temp_groupbox)

        yolo_groupbox = QGroupBox("Parâmetros de Detecção de Objetos (YOLO)")
        yolo_layout = QFormLayout(yolo_groupbox)
        self.object_ids_edit = QLineEdit()
        self.object_ids_edit.setPlaceholderText("Ex: 0, 67 (separados por vírgula)")
        self.quantity_edit = QLineEdit("1")
        self.exact_number_checkbox = QCheckBox("Ativar contagem exata")
        self.sensitivity_edit = QLineEdit("0")
        self.sensitivity_edit.setPlaceholderText("Tempo que a condição deve durar")

        # --- ALTERAÇÃO AQUI: Campos de receptor para o modo YOLO ---
        self.receptor_edit_yolo = QLineEdit()
        self.receptor_port_edit_yolo = QLineEdit("5000")

        self.use_roi_checkbox_yolo = QCheckBox("Usar Área de Detecção (ROI)")
        self.use_roi_checkbox_yolo.toggled.connect(self.toggle_roi_widgets)

        self.set_roi_button_yolo = QPushButton("Definir Área de Detecção (ROI)")
        self.roi_label_yolo = QLabel("Área não definida (tela inteira)")

        self.gpu_checkbox_yolo = QCheckBox("Tentar usar GPU (se disponível)")
        self.gpu_checkbox_yolo.setChecked(True)

        yolo_layout.addRow("IDs dos Objetos a Detectar:", self.object_ids_edit)
        yolo_layout.addRow("Quantidade de Objetos:", self.quantity_edit)
        yolo_layout.addRow("Número Exato:", self.exact_number_checkbox)
        yolo_layout.addRow("Sensibilidade (s):", self.sensitivity_edit)
        yolo_layout.addRow("URL do PC Receptor:", self.receptor_edit_yolo)
        yolo_layout.addRow("Porta do Receptor:", self.receptor_port_edit_yolo)
        yolo_layout.addRow(self.use_roi_checkbox_yolo)
        yolo_layout.addRow(self.set_roi_button_yolo)
        yolo_layout.addRow(self.roi_label_yolo)
        yolo_layout.addRow(self.gpu_checkbox_yolo)
        self.stacked_widget.addWidget(yolo_groupbox)

        self.layout.addStretch()
        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.save_button)
        self.layout.addLayout(buttons_layout)

        self.mode_combo.currentIndexChanged.connect(self.stacked_widget.setCurrentIndex)
        self.set_roi_button.clicked.connect(self.set_roi)
        self.set_roi_button_yolo.clicked.connect(self.set_roi)
        self.save_button.clicked.connect(self.accept)

        if cam_name and cam_data:
            self.load_config(cam_name, cam_data)
        else:
            self.stacked_widget.setCurrentIndex(0)
            self.toggle_roi_widgets(False)

    def toggle_roi_widgets(self, checked):
        self.set_roi_button_yolo.setEnabled(checked)
        self.roi_label_yolo.setEnabled(checked)
        if not checked:
            self.roi_label_yolo.setText("Área não definida (tela inteira)")
            self.roi_label_yolo.setStyleSheet("")
            self.roi_coords = None

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
            # --- ALTERAÇÃO AQUI: Carrega dados do receptor para o modo YOLO ---
            self.receptor_edit_yolo.setText(data.get('receptor', ''))
            self.receptor_port_edit_yolo.setText(str(data.get('receptor_port', '5000')))

            use_roi = data.get('use_roi', False)
            self.use_roi_checkbox_yolo.setChecked(use_roi)
            self.toggle_roi_widgets(use_roi)

            self.roi_coords = data.get('roi')
            if use_roi and self.roi_coords:
                self.roi_label_yolo.setText(f"Área definida")
                self.roi_label_yolo.setStyleSheet("color: #A3BE8C;")
        else:
            self.mode_combo.setCurrentIndex(0)
            self.limite_edit.setText(str(data.get('limite', '')))
            self.receptor_edit_ocr.setText(data.get('receptor', ''))
            self.receptor_port_edit_ocr.setText(str(data.get('receptor_port', '5000')))
            self.roi_coords = data.get('roi')
            self.gpu_checkbox_ocr.setChecked(data.get('gpu', False))
            if self.roi_coords:
                self.roi_label.setText(f"Área definida")
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
                config['receptor_port'] = int(self.receptor_port_edit_ocr.text())
                config['receptor'] = self.receptor_edit_ocr.text()
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

                # --- ALTERAÇÃO AQUI: Salva dados do receptor para o modo YOLO ---
                config['receptor'] = self.receptor_edit_yolo.text()
                config['receptor_port'] = int(self.receptor_port_edit_yolo.text())

                config['use_roi'] = self.use_roi_checkbox_yolo.isChecked()
                if config['use_roi']:
                    if not self.roi_coords:
                        QMessageBox.warning(self, "Atenção",
                                            "A opção de usar ROI está marcada, mas nenhuma área foi definida.")
                        return None
                    config['roi'] = self.roi_coords
                else:
                    config['roi'] = None

            except (ValueError, TypeError) as e:
                QMessageBox.critical(self, "Erro",
                                     f"Dados inválidos para o modo YOLO. Verifique se os IDs estão preenchidos e se Quantidade e Sensibilidade são números inteiros.\nDetalhe: {e}")
                return None
        return config

    def set_roi(self):
        video_url_text = self.url_edit.text()
        if not video_url_text:
            QMessageBox.warning(self, "Atenção", "Por favor, insira a URL do vídeo primeiro.")
            return

        roi = ROISelector.get_roi(video_url_text, self.roi_coords, self)

        self.roi_coords = roi if roi is not None else self.roi_coords

        label_text = "Área definida" if self.roi_coords else "Área não definida"
        style_sheet = "color: #A3BE8C;" if self.roi_coords else ""

        if self.mode_combo.currentIndex() == 0:
            self.roi_label.setText(label_text)
            self.roi_label.setStyleSheet(style_sheet)
        else:
            self.roi_label_yolo.setText(
                label_text if self.use_roi_checkbox_yolo.isChecked() else "Área não definida (tela inteira)")
            self.roi_label_yolo.setStyleSheet(style_sheet if self.use_roi_checkbox_yolo.isChecked() else "")
