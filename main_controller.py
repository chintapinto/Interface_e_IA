import sys
import json
import os
import subprocess
import threading
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QLabel, QMessageBox,
                               QTableWidget, QTableWidgetItem, QAbstractItemView,
                               QHeaderView, QStyle, QSplitter, QDialog)
from PySide6.QtCore import Qt, QRect, QPropertyAnimation, QSequentialAnimationGroup, Signal, QObject
from PySide6.QtGui import QColor, QKeySequence, QShortcut, QIcon, QPixmap, QPainter, QPen
from ui_components import CameraConfigDialog, LiveViewDialog  # LiveViewDialog importado aqui


def resource_path(relative_path):
    """ Retorna o caminho absoluto para o recurso, funcionando tanto em dev quanto no PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class WorkerSignals(QObject):
    log_received = Signal(dict)
    error_received = Signal(dict)
    detection_received = Signal(dict)  # NOVO SINAL
    finished = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        icon = self.create_themed_icon()
        self.setWindowIcon(icon)
        self.setWindowTitle("Sistema de Monitoramento Inteligente")
        self.setGeometry(100, 100, 900, 500)
        self.running_processes = {}
        self.live_view_dialogs = {}  # Dicionário para gerenciar janelas de live view

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        splitter = QSplitter(Qt.Vertical)

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(10, 10, 10, 0)
        top_layout.addWidget(QLabel("Câmeras:"))
        table_and_buttons_layout = QHBoxLayout()
        self.camera_table = QTableWidget()
        self.camera_table.setColumnCount(2)
        self.camera_table.setHorizontalHeaderLabels(["Câmera", "Status"])
        self.camera_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.camera_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.camera_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.camera_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.camera_table.setAlternatingRowColors(True)
        table_and_buttons_layout.addWidget(self.camera_table, 7)

        right_panel = QVBoxLayout()
        self.add_cam_button = QPushButton("Adicionar Câmera")
        self.edit_cam_button = QPushButton("Editar Câmera")
        self.remove_cam_button = QPushButton("Remover Câmeras")
        self.view_cam_button = QPushButton("Ver ao Vivo")  # NOVO BOTÃO
        right_panel.addWidget(self.add_cam_button)
        right_panel.addWidget(self.edit_cam_button)
        right_panel.addWidget(self.remove_cam_button)
        right_panel.addWidget(self.view_cam_button)
        right_panel.addStretch()
        self.start_button = QPushButton("▶ Iniciar Selecionadas")
        self.stop_button = QPushButton("■ Parar Selecionadas")
        self.start_button.setObjectName("startButton")
        self.stop_button.setObjectName("stopButton")
        right_panel.addWidget(self.start_button)
        right_panel.addWidget(self.stop_button)
        table_and_buttons_layout.addLayout(right_panel, 3)
        top_layout.addLayout(table_and_buttons_layout)

        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(10, 10, 10, 10)
        bottom_layout.addWidget(QLabel("Log de Eventos:"))
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(3)
        self.log_table.setHorizontalHeaderLabels(["Data e Hora", "Câmera", "Mensagem de Alerta / Erro"])
        self.log_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        bottom_layout.addWidget(self.log_table)

        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setSizes([400, 300])
        main_layout.addWidget(splitter)

        self.worker_signals = WorkerSignals()
        self.worker_signals.log_received.connect(self.add_log_entry)
        self.worker_signals.error_received.connect(self.add_error_entry)
        self.worker_signals.detection_received.connect(self.on_detection_received)  # CONEXÃO DO SINAL
        self.worker_signals.finished.connect(self.on_worker_finished)

        self.camera_table.itemDoubleClicked.connect(self.edit_camera)
        self.camera_table.itemSelectionChanged.connect(self.update_button_states)
        self.add_cam_button.clicked.connect(self.add_camera)
        self.edit_cam_button.clicked.connect(self.edit_camera)
        self.remove_cam_button.clicked.connect(self.remove_cameras)
        self.view_cam_button.clicked.connect(self.show_live_view)  # CONEXÃO DO BOTÃO
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button.clicked.connect(self.stop_monitoring)

        self.add_cam_button.pressed.connect(lambda: self.animate_click(self.add_cam_button))
        self.edit_cam_button.pressed.connect(lambda: self.animate_click(self.edit_cam_button))
        self.remove_cam_button.pressed.connect(lambda: self.animate_click(self.remove_cam_button))
        self.view_cam_button.pressed.connect(lambda: self.animate_click(self.view_cam_button))
        self.start_button.pressed.connect(lambda: self.animate_click(self.start_button))
        self.stop_button.pressed.connect(lambda: self.animate_click(self.stop_button))

        shortcut_select_all = QShortcut(QKeySequence("Ctrl+A"), self)
        shortcut_select_all.activated.connect(self.camera_table.selectAll)
        self.load_cameras()
        self.update_button_states()

    def on_detection_received(self, data):
        cam_name = data.get("camera")
        if cam_name in self.live_view_dialogs:
            self.live_view_dialogs[cam_name].update_detections(data)

    def on_worker_finished(self, cam_name):
        print(f"Worker da câmera '{cam_name}' finalizou. Atualizando status.")
        if cam_name in self.running_processes:
            self.running_processes.pop(cam_name)

        for row in range(self.camera_table.rowCount()):
            if self.camera_table.item(row, 0).text() == cam_name:
                config = self.camera_table.item(row, 0).data(Qt.UserRole)
                self.add_or_update_camera_in_table(cam_name, config, row)
                break
        self.update_button_states()

    def stream_reader(self, process, cam_name):
        for line in iter(process.stdout.readline, ''):
            if not line: break
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    msg_type = data.get("type")
                    if msg_type == "alert":
                        self.worker_signals.log_received.emit(data)
                    elif msg_type == "error":
                        self.worker_signals.error_received.emit(data)
                    elif msg_type == "detection":
                        self.worker_signals.detection_received.emit(data)
                    else:
                        print(f"[{cam_name}] (saída ignorada): {data}")
            except json.JSONDecodeError:
                print(f"[{cam_name}]: {line.strip()}")
        process.stdout.close()
        process.wait()
        self.worker_signals.finished.emit(cam_name)

    # (As funções add_log_entry, add_error_entry, create_themed_icon, animate_click permanecem as mesmas)
    def add_log_entry(self, log_data):
        row_position = self.log_table.rowCount()
        self.log_table.insertRow(row_position)
        timestamp = QTableWidgetItem(log_data.get("timestamp", ""))
        camera = QTableWidgetItem(log_data.get("camera", ""))
        message = QTableWidgetItem(log_data.get('message', "Evento recebido"))
        self.log_table.setItem(row_position, 0, timestamp)
        self.log_table.setItem(row_position, 1, camera)
        self.log_table.setItem(row_position, 2, message)
        self.log_table.scrollToBottom()

    def add_error_entry(self, error_data):
        row_position = self.log_table.rowCount()
        self.log_table.insertRow(row_position)
        timestamp_item = QTableWidgetItem(error_data.get("timestamp", ""))
        camera_item = QTableWidgetItem(error_data.get("camera", ""))
        message_item = QTableWidgetItem(error_data.get("message", "Erro desconhecido"))
        error_color = QColor(191, 97, 106, 80)
        timestamp_item.setBackground(error_color)
        camera_item.setBackground(error_color)
        message_item.setBackground(error_color)
        self.log_table.setItem(row_position, 0, timestamp_item)
        self.log_table.setItem(row_position, 1, camera_item)
        self.log_table.setItem(row_position, 2, message_item)
        self.log_table.scrollToBottom()

    def create_themed_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        bgColor = QColor("#3B4252")
        fgColor = QColor("#88C0D0")
        painter.setBrush(bgColor)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(pixmap.rect(), 12, 12)
        pen = QPen(fgColor)
        pen.setWidth(8)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        rect_arc = QRect(16, 16, 32, 32)
        start_angle, span_angle = 45 * 16, 270 * 16
        painter.drawArc(rect_arc, start_angle, span_angle)
        painter.end()
        return QIcon(pixmap)

    def animate_click(self, button):
        if not button.isEnabled(): return
        start_rect = button.geometry()
        anim_down = QPropertyAnimation(button, b"geometry")
        anim_down.setDuration(60)
        anim_down.setStartValue(start_rect)
        anim_down.setEndValue(QRect(start_rect.x() + 1, start_rect.y() + 1, start_rect.width(), start_rect.height()))
        anim_up = QPropertyAnimation(button, b"geometry")
        anim_up.setDuration(80)
        anim_up.setStartValue(anim_down.endValue())
        anim_up.setEndValue(start_rect)
        self.anim_group = QSequentialAnimationGroup()
        self.anim_group.addAnimation(anim_down)
        self.anim_group.addAnimation(anim_up)
        self.anim_group.start()

    def update_button_states(self):
        selected_rows = self.get_selected_rows()
        has_selection = bool(selected_rows)
        is_single_selection = len(selected_rows) == 1

        self.edit_cam_button.setEnabled(is_single_selection)
        self.view_cam_button.setEnabled(is_single_selection)
        self.remove_cam_button.setEnabled(has_selection)

        if not has_selection:
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(False)
        else:
            can_start = any(self.camera_table.item(row, 1).text() == "Inativo" for row in selected_rows)
            can_stop = any(self.camera_table.item(row, 1).text() == "Ativo" for row in selected_rows)
            self.start_button.setEnabled(can_start)
            self.stop_button.setEnabled(can_stop)

    # (As funções add_or_update_camera_in_table, load_cameras, save_cameras, get_selected_rows, add_camera, edit_camera, open_camera_dialog, remove_cameras permanecem as mesmas)
    def add_or_update_camera_in_table(self, cam_name, config, row_to_update=None):
        name_item = QTableWidgetItem(cam_name)
        name_item.setData(Qt.UserRole, config)
        status = "Ativo" if cam_name in self.running_processes else "Inativo"
        status_item = QTableWidgetItem(status)
        icon = self.style().standardIcon(
            QStyle.SP_DialogApplyButton if status == "Ativo" else QStyle.SP_DialogCancelButton)
        status_item.setIcon(icon)
        row = row_to_update if row_to_update is not None else self.camera_table.rowCount()
        if row_to_update is None:
            self.camera_table.insertRow(row)
        self.camera_table.setItem(row, 0, name_item)
        self.camera_table.setItem(row, 1, status_item)

    def load_cameras(self):
        if not os.path.exists('cameras_config.json'): return
        try:
            with open('cameras_config.json', 'r', encoding='utf-8') as f:
                cameras = json.load(f)
            self.camera_table.setRowCount(0)
            for cam_name, config in cameras.items():
                self.add_or_update_camera_in_table(cam_name, config)
        except json.JSONDecodeError:
            print("Aviso: 'cameras_config.json' está corrompido.")

    def save_cameras(self):
        cameras = {}
        for row in range(self.camera_table.rowCount()):
            name_item = self.camera_table.item(row, 0)
            cameras[name_item.text()] = name_item.data(Qt.UserRole)
        with open('cameras_config.json', 'w', encoding='utf-8') as f:
            json.dump(cameras, f, indent=4)

    def get_selected_rows(self):
        return sorted(list(set(item.row() for item in self.camera_table.selectedItems())))

    def add_camera(self):
        self.open_camera_dialog(None, None, None)

    def edit_camera(self):
        selected_rows = self.get_selected_rows()
        if len(selected_rows) != 1: return
        row = selected_rows[0]
        name_item = self.camera_table.item(row, 0)
        self.open_camera_dialog(name_item.text(), name_item.data(Qt.UserRole), row)

    def open_camera_dialog(self, cam_name, cam_data, row):
        dialog = CameraConfigDialog(cam_name, cam_data, row, self)
        if dialog.exec() == QDialog.Accepted:
            config = dialog.get_config()
            if not config: return
            new_name = config.get('name')
            was_running = cam_name in self.running_processes
            if was_running:
                reply = QMessageBox.question(self, "Aplicar Alterações",
                                             f"Para aplicar as novas configurações na câmera '{cam_name}', ela precisa ser reiniciada. Deseja continuar?",
                                             QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self._stop_single_camera(cam_name)
                    time.sleep(0.5)
                    self.add_or_update_camera_in_table(new_name, config, dialog.row)
                    self.save_cameras()
                    self._start_single_camera(dialog.row)
                else:
                    self.add_or_update_camera_in_table(new_name, config, dialog.row)
                    self.save_cameras()
            else:
                self.add_or_update_camera_in_table(new_name, config, dialog.row)
                self.save_cameras()

    def remove_cameras(self):
        selected_rows = self.get_selected_rows()
        if not selected_rows: return
        reply = QMessageBox.question(self, "Confirmar",
                                     f"Tem certeza que deseja remover as câmeras selecionadas?")
        if reply == QMessageBox.Yes:
            for row in sorted(selected_rows, reverse=True):
                cam_name = self.camera_table.item(row, 0).text()
                if cam_name in self.running_processes:
                    self._stop_single_camera(cam_name)
                self.camera_table.removeRow(row)
            self.save_cameras()
            self.update_button_states()

    def show_live_view(self):
        selected_rows = self.get_selected_rows()
        if not selected_rows: return
        row = selected_rows[0]

        name_item = self.camera_table.item(row, 0)
        cam_name = name_item.text()
        config = name_item.data(Qt.UserRole)

        if cam_name in self.live_view_dialogs:
            self.live_view_dialogs[cam_name].activateWindow()
            return

        config_with_name = {'name': cam_name, **config}

        dialog = LiveViewDialog(config_with_name, self)
        self.live_view_dialogs[cam_name] = dialog
        dialog.show()

    def on_live_view_closed(self, cam_name):
        if cam_name in self.live_view_dialogs:
            del self.live_view_dialogs[cam_name]

    def _start_single_camera(self, row):
        name_item = self.camera_table.item(row, 0)
        cam_name = name_item.text()
        config = name_item.data(Qt.UserRole)

        if cam_name in self.running_processes: return True

        worker_script_path = resource_path('detector_worker.py')

        command = [
            sys.executable, worker_script_path,
            '--name', cam_name,
            '--url', config['url'],
            '--mode', config.get('mode', 'temperature'),
            '--rearm_time', str(config.get('rearm_time', 5))
        ]

        if config.get('mode') == 'object':
            command.extend(['--object_ids', config.get('object_ids', '')])
            command.extend(['--quantity', str(config.get('quantity', 1))])
            if config.get('exact_number', False):
                command.append('--exact_number')
            command.extend(['--sensitivity', str(config.get('sensitivity', 0))])

            if config.get('use_roi') and config.get('roi'):
                command.extend(['--roi', ','.join(map(str, config['roi']))])

            use_gpu = config.get('use_gpu', True)
            device_arg = '0' if use_gpu else 'cpu'
            command.extend(['--device', device_arg])
        else:  # Modo temperatura
            command.extend(['--roi', ','.join(map(str, config.get('roi', [0, 0, 0, 0])))])
            command.extend(['--limite', str(config.get('limite', 0))])
            command.extend(['--receptor_url', config.get('receptor', '')])
            command.extend(['--receptor_port', str(config.get('receptor_port', 5000))])
            if config.get('gpu', False):
                command.append('--gpu')

        try:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding='utf-8', bufsize=1, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.running_processes[cam_name] = process
            thread = threading.Thread(target=self.stream_reader, args=(process, cam_name), daemon=True)
            thread.start()
            self.add_or_update_camera_in_table(cam_name, config, row)
        except FileNotFoundError:
            QMessageBox.critical(self, "Erro", "Script 'detector_worker.py' não encontrado.")
            return False
        return True

    def start_monitoring(self):
        selected_rows = self.get_selected_rows()
        if not selected_rows: return
        for row in selected_rows:
            self._start_single_camera(row)
        self.update_button_states()

    def _stop_single_camera(self, cam_name):
        if cam_name in self.running_processes:
            process = self.running_processes.pop(cam_name)
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()

    def stop_monitoring(self):
        selected_rows = self.get_selected_rows()
        if not selected_rows: return
        for row in selected_rows:
            cam_name = self.camera_table.item(row, 0).text()
            self._stop_single_camera(cam_name)

    def closeEvent(self, event):
        for dialog in self.live_view_dialogs.values():
            dialog.close()
        for process in self.running_processes.values():
            process.terminate()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        with open('style.qss', 'r', encoding='utf-8') as f:
            style = f.read()
        app.setStyleSheet(style)
    except FileNotFoundError:
        print("Aviso: Arquivo de estilo 'style.qss' não encontrado.")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
