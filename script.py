import sys
import threading
import time
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QAction, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLineEdit, QLabel, QFileDialog, QComboBox, QMessageBox, QSlider, QCheckBox,
    QTabWidget, QProgressBar, QGroupBox, QFormLayout
)

import serial
import serial.tools.list_ports


class SerialThread(QObject):
    log_signal = pyqtSignal(str)
    temp_signal = pyqtSignal(float, float)  # hotend, bed temps

    def __init__(self):
        super().__init__()
        self.ser = None
        self.running = False

    def connect(self, port, baudrate=115200):
        try:
            self.ser = serial.Serial(port, baudrate, timeout=0.1)
            self.running = True
            threading.Thread(target=self.read_loop, daemon=True).start()
            self.log_signal.emit(f"[INFO] Conectado a {port} a {baudrate}bps.")
        except Exception as e:
            self.log_signal.emit(f"[ERROR] No se pudo conectar: {e}")

    def disconnect(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.log_signal.emit("[INFO] Desconectado.")

    def read_loop(self):
        while self.running and self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode(errors='ignore').strip()
                if line:
                    self.log_signal.emit(f"< {line}")
                    self.parse_temperature(line)
            except Exception as e:
                self.log_signal.emit(f"[ERROR lectura]: {e}")

    def send_command(self, cmd):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write((cmd.strip() + '\n').encode())
                self.log_signal.emit(f">>> {cmd.strip()}")
            except Exception as e:
                self.log_signal.emit(f"[ERROR envío comando]: {e}")
        else:
            self.log_signal.emit("[ERROR] No conectado.")

    def parse_temperature(self, line):
        # Ejemplo básico parsing de temperaturas en respuesta Marlin: "ok T:200.0 /200.0 B:60.0 /60.0"
        if 'T:' in line and 'B:' in line:
            try:
                hotend_str = line.split('T:')[1].split(' ')[0]
                bed_str = line.split('B:')[1].split(' ')[0]
                hotend_temp = float(hotend_str)
                bed_temp = float(bed_str)
                self.temp_signal.emit(hotend_temp, bed_temp)
            except:
                pass


class PrinterTerminal(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Terminal Impresora 3D Marlin - Pro Edition")
        self.resize(900, 700)

        self.serial_thread = SerialThread()
        self.serial_thread.log_signal.connect(self.append_log)
        self.serial_thread.temp_signal.connect(self.update_temps)

        self.init_ui()

        self.gcode_file = None
        self.gcode_lines = []
        self.printing = False
        self.current_line = 0

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Tabs ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab Consola
        self.console_tab = QWidget()
        self.tabs.addTab(self.console_tab, "Consola / Terminal")
        self.setup_console_tab()

        # Tab Control Manual
        self.control_tab = QWidget()
        self.tabs.addTab(self.control_tab, "Control Manual")
        self.setup_control_tab()

        # Tab Temperaturas
        self.temp_tab = QWidget()
        self.tabs.addTab(self.temp_tab, "Temperaturas")
        self.setup_temp_tab()

        # Tab Configuración
        self.config_tab = QWidget()
        self.tabs.addTab(self.config_tab, "Configuración")
        self.setup_config_tab()

    def setup_console_tab(self):
        layout = QVBoxLayout()
        self.console_tab.setLayout(layout)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setFont(QFont("Consolas", 10))
        layout.addWidget(self.log_console)

        h_cmd = QHBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Introduce comando G-code (Ej: G28)")
        h_cmd.addWidget(self.cmd_input)

        send_btn = QPushButton("Enviar")
        send_btn.clicked.connect(self.on_send_command)
        h_cmd.addWidget(send_btn)

        layout.addLayout(h_cmd)

        # Botones para archivos
        file_btn = QPushButton("Cargar archivo G-code")
        file_btn.clicked.connect(self.load_gcode_file)
        layout.addWidget(file_btn)

        # Barra progreso impresión
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Progreso impresión: %p%")
        layout.addWidget(self.progress_bar)

        # Botones de control impresión
        btn_layout = QHBoxLayout()

        self.start_print_btn = QPushButton("Iniciar impresión")
        self.start_print_btn.clicked.connect(self.start_print)
        self.start_print_btn.setEnabled(False)
        btn_layout.addWidget(self.start_print_btn)

        self.pause_print_btn = QPushButton("Pausar impresión")
        self.pause_print_btn.clicked.connect(self.pause_print)
        self.pause_print_btn.setEnabled(False)
        btn_layout.addWidget(self.pause_print_btn)

        self.resume_print_btn = QPushButton("Reanudar impresión")
        self.resume_print_btn.clicked.connect(self.resume_print)
        self.resume_print_btn.setEnabled(False)
        btn_layout.addWidget(self.resume_print_btn)

        self.stop_print_btn = QPushButton("Detener impresión")
        self.stop_print_btn.clicked.connect(self.stop_print)
        self.stop_print_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_print_btn)

        layout.addLayout(btn_layout)

    def setup_control_tab(self):
        layout = QVBoxLayout()
        self.control_tab.setLayout(layout)

        # Movimiento ejes
        move_group = QGroupBox("Movimiento de Ejes")
        move_layout = QFormLayout()
        move_group.setLayout(move_layout)

        self.move_speed = QLineEdit("3000")
        move_layout.addRow(QLabel("Velocidad (mm/min):"), self.move_speed)

        btn_move_xp = QPushButton("Mover X +")
        btn_move_xp.clicked.connect(lambda: self.move_axis('X', 10))
        btn_move_xm = QPushButton("Mover X -")
        btn_move_xm.clicked.connect(lambda: self.move_axis('X', -10))

        btn_move_yp = QPushButton("Mover Y +")
        btn_move_yp.clicked.connect(lambda: self.move_axis('Y', 10))
        btn_move_ym = QPushButton("Mover Y -")
        btn_move_ym.clicked.connect(lambda: self.move_axis('Y', -10))

        btn_move_zp = QPushButton("Mover Z +")
        btn_move_zp.clicked.connect(lambda: self.move_axis('Z', 1))
        btn_move_zm = QPushButton("Mover Z -")
        btn_move_zm.clicked.connect(lambda: self.move_axis('Z', -1))

        move_layout.addRow(btn_move_xp, btn_move_xm)
        move_layout.addRow(btn_move_yp, btn_move_ym)
        move_layout.addRow(btn_move_zp, btn_move_zm)

        layout.addWidget(move_group)

        # Control extrusor
        extrude_group = QGroupBox("Control Extrusor")
        extrude_layout = QHBoxLayout()
        extrude_group.setLayout(extrude_layout)

        self.extrude_amount = QLineEdit("5")
        extrude_layout.addWidget(QLabel("Cantidad (mm):"))
        extrude_layout.addWidget(self.extrude_amount)

        btn_extrude = QPushButton("Extruir")
        btn_extrude.clicked.connect(self.extrude)
        btn_retract = QPushButton("Retractar")
        btn_retract.clicked.connect(self.retract)

        extrude_layout.addWidget(btn_extrude)
        extrude_layout.addWidget(btn_retract)

        layout.addWidget(extrude_group)

        # Botones Home y Reset
        home_btn = QPushButton("Home All (G28)")
        home_btn.clicked.connect(lambda: self.send_command("G28"))
        layout.addWidget(home_btn)

        reset_btn = QPushButton("Reset Impresora (M999)")
        reset_btn.clicked.connect(lambda: self.send_command("M999"))
        layout.addWidget(reset_btn)

    def setup_temp_tab(self):
        layout = QVBoxLayout()
        self.temp_tab.setLayout(layout)

        self.hotend_label = QLabel("Hotend: 0.0 °C")
        self.bed_label = QLabel("Cama: 0.0 °C")
        self.hotend_label.setFont(QFont("Arial", 14))
        self.bed_label.setFont(QFont("Arial", 14))

        layout.addWidget(self.hotend_label)
        layout.addWidget(self.bed_label)

        # Precalentados
        presets_group = QGroupBox("Precalentados")
        presets_layout = QHBoxLayout()
        presets_group.setLayout(presets_layout)

        btn_preheat_pla = QPushButton("PLA (200/60)")
        btn_preheat_pla.clicked.connect(lambda: self.preheat(200, 60))
        btn_preheat_abs = QPushButton("ABS (230/100)")
        btn_preheat_abs.clicked.connect(lambda: self.preheat(230, 100))

        presets_layout.addWidget(btn_preheat_pla)
        presets_layout.addWidget(btn_preheat_abs)

        layout.addWidget(presets_group)

        # Ventilador control
        fan_group = QGroupBox("Ventilador")
        fan_layout = QHBoxLayout()
        fan_group.setLayout(fan_layout)

        self.fan_slider = QSlider(Qt.Orientation.Horizontal)
        self.fan_slider.setMinimum(0)
        self.fan_slider.setMaximum(255)
        self.fan_slider.setValue(0)
        self.fan_slider.valueChanged.connect(self.set_fan_speed)

        fan_layout.addWidget(QLabel("Velocidad:"))
        fan_layout.addWidget(self.fan_slider)

        layout.addWidget(fan_group)

    def setup_config_tab(self):
        layout = QFormLayout()
        self.config_tab.setLayout(layout)

        # Puerto serial
        self.port_combo = QComboBox()
        self.refresh_ports()
        layout.addRow("Puerto Serial:", self.port_combo)

        refresh_btn = QPushButton("Actualizar Puertos")
        refresh_btn.clicked.connect(self.refresh_ports)
        layout.addRow(refresh_btn)

        # Baudrate
        self.baud_combo = QComboBox()
        self.baud_combo.addItems([str(x) for x in [9600, 14400, 19200, 38400, 57600, 115200, 250000]])
        self.baud_combo.setCurrentText("115200")
        layout.addRow("Baudrate:", self.baud_combo)

        # Botones conectar/desconectar
        btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Conectar")
        self.connect_btn.clicked.connect(self.connect_serial)
        btn_layout.addWidget(self.connect_btn)

        self.disconnect_btn = QPushButton("Desconectar")
        self.disconnect_btn.clicked.connect(self.disconnect_serial)
        self.disconnect_btn.setEnabled(False)
        btn_layout.addWidget(self.disconnect_btn)

        layout.addRow(btn_layout)

        # Modo oscuro
        self.dark_mode_checkbox = QCheckBox("Modo oscuro")
        self.dark_mode_checkbox.stateChanged.connect(self.toggle_dark_mode)
        layout.addRow(self.dark_mode_checkbox)

    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_combo.addItem(p.device)
        if self.port_combo.count() == 0:
            self.port_combo.addItem("No hay puertos")

    def connect_serial(self):
        port = self.port_combo.currentText()
        baud = int(self.baud_combo.currentText())
        if port == "No hay puertos":
            QMessageBox.warning(self, "Error", "No hay puertos serial disponibles.")
            return
        self.serial_thread.connect(port, baud)
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        self.start_print_btn.setEnabled(True)

    def disconnect_serial(self):
        self.serial_thread.disconnect()
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.start_print_btn.setEnabled(False)
        self.pause_print_btn.setEnabled(False)
        self.resume_print_btn.setEnabled(False)
        self.stop_print_btn.setEnabled(False)

    def on_send_command(self):
        cmd = self.cmd_input.text()
        if cmd.strip() == '':
            return
        self.send_command(cmd)
        self.cmd_input.clear()

    def send_command(self, cmd):
        self.serial_thread.send_command(cmd)

    def append_log(self, text):
        self.log_console.append(text)
        self.log_console.moveCursor(QTextCursor.MoveOperation.End)

    def update_temps(self, hotend, bed):
        self.hotend_label.setText(f"Hotend: {hotend:.1f} °C")
        self.bed_label.setText(f"Cama: {bed:.1f} °C")

    def load_gcode_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Abrir archivo G-code", "", "G-code (*.gcode *.gc *.txt);;Todos los archivos (*)")
        if fname:
            self.gcode_file = fname
            with open(fname, 'r', encoding='utf-8', errors='ignore') as f:
                self.gcode_lines = [line.strip() for line in f if line.strip() and not line.startswith(';')]
            self.append_log(f"[INFO] Archivo G-code cargado: {Path(fname).name} ({len(self.gcode_lines)} líneas)")
            self.progress_bar.setValue(0)
            self.current_line = 0
            self.start_print_btn.setEnabled(True)

    def start_print(self):
        if not self.gcode_lines:
            QMessageBox.warning(self, "Error", "No hay archivo G-code cargado.")
            return
        if self.printing:
            QMessageBox.warning(self, "Error", "Ya hay una impresión en curso.")
            return
        self.printing = True
        self.pause_print_btn.setEnabled(True)
        self.stop_print_btn.setEnabled(True)
        self.start_print_btn.setEnabled(False)
        self.send_gcode_thread = threading.Thread(target=self.send_gcode_lines, daemon=True)
        self.send_gcode_thread.start()

    def send_gcode_lines(self):
        while self.current_line < len(self.gcode_lines) and self.printing:
            line = self.gcode_lines[self.current_line]
            self.send_command(line)
            self.current_line += 1
            progress = int((self.current_line / len(self.gcode_lines)) * 100)
            self.progress_bar.setValue(progress)
            time.sleep(0.05)  # Control de velocidad envío
            while not self.printing:  # pausa activa
                time.sleep(0.1)
        if self.current_line >= len(self.gcode_lines):
            self.append_log("[INFO] Impresión finalizada.")
            self.printing = False
            self.pause_print_btn.setEnabled(False)
            self.resume_print_btn.setEnabled(False)
            self.stop_print_btn.setEnabled(False)
            self.start_print_btn.setEnabled(True)
            self.progress_bar.setValue(100)

    def pause_print(self):
        if self.printing:
            self.printing = False
            self.append_log("[INFO] Impresión pausada.")
            self.pause_print_btn.setEnabled(False)
            self.resume_print_btn.setEnabled(True)

    def resume_print(self):
        if not self.printing and self.current_line < len(self.gcode_lines):
            self.printing = True
            self.append_log("[INFO] Impresión reanudada.")
            self.pause_print_btn.setEnabled(True)
            self.resume_print_btn.setEnabled(False)
            self.send_gcode_thread = threading.Thread(target=self.send_gcode_lines, daemon=True)
            self.send_gcode_thread.start()

    def stop_print(self):
        self.printing = False
        self.current_line = len(self.gcode_lines)
        self.append_log("[INFO] Impresión detenida.")
        self.pause_print_btn.setEnabled(False)
        self.resume_print_btn.setEnabled(False)
        self.stop_print_btn.setEnabled(False)
        self.start_print_btn.setEnabled(True)
        self.progress_bar.setValue(0)

    def move_axis(self, axis, distance):
        try:
            speed = int(self.move_speed.text())
        except:
            speed = 3000
        cmd = f"G91\nG1 {axis}{distance} F{speed}\nG90"
        self.send_command(cmd)

    def extrude(self):
        try:
            amt = float(self.extrude_amount.text())
        except:
            amt = 5.0
        cmd = f"G91\nG1 E{amt} F200\nG90"
        self.send_command(cmd)

    def retract(self):
        try:
            amt = float(self.extrude_amount.text())
        except:
            amt = 5.0
        cmd = f"G91\nG1 E-{amt} F200\nG90"
        self.send_command(cmd)

    def preheat(self, hotend_temp, bed_temp):
        self.send_command(f"M104 S{hotend_temp}")  # hotend sin espera
        self.send_command(f"M140 S{bed_temp}")    # cama sin espera
        self.send_command(f"M190 S{bed_temp}")    # espera cama
        self.send_command(f"M109 S{hotend_temp}") # espera hotend

    def set_fan_speed(self, value):
        self.send_command(f"M106 S{value}")

    def toggle_dark_mode(self, state):
        if state == Qt.CheckState.Checked.value:
            self.setStyleSheet("""
                QWidget {
                    background-color: #121212;
                    color: #e0e0e0;
                }
                QPushButton {
                    background-color: #1f1f1f;
                    color: #e0e0e0;
                    border: 1px solid #444;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #333;
                }
                QLineEdit, QTextEdit, QComboBox {
                    background-color: #222;
                    color: #eee;
                    border: 1px solid #555;
                }
                QSlider::handle:horizontal {
                    background: #666;
                }
            """)
        else:
            self.setStyleSheet("")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    terminal = PrinterTerminal()
    terminal.show()
    sys.exit(app.exec())
