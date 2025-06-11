import sys
import subprocess
import os
import re # 정규 표현식 모듈 추가
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLineEdit, QLabel, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QRegExp
from PyQt5.QtGui import QRegExpValidator

# --- 라즈베리파이 환경에 따라 경로 설정 (개발 시에는 더미, 배포 시에는 실제 경로) ---
FPGA_MODULE_PATH = "/home/pi/Modules/"
DHT_RELAY_DIR = "/home/pi/Work/-6-/DHTfile/"
DHT_RELAY_EXEC = os.path.join(DHT_RELAY_DIR, "dht_relay")
FPGA_TEXT_LCD_DEV_NODE = "/dev/fpga_text_lcd"

# --- DHT Relay 실행을 위한 스레드 클래스 ---
class DhtRelayThread(QThread):
    output_signal = pyqtSignal(str) # DHT 프로그램의 한 줄 출력을 보낼 시그널
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, command, parent=None):
        super().__init__(parent)
        self.command = command
        self._running = True
        self.process = None

    def run(self):
        try:
            # Popen을 사용하여 실시간으로 출력 읽기
            self.process = subprocess.Popen(
                self.command,
                cwd=DHT_RELAY_DIR, # dht_relay 실행 시 cwd 설정
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # 한 줄씩 버퍼링
                universal_newlines=True # 텍스트 모드에서 유니버설 개행 지원
            )
            for line in iter(self.process.stdout.readline, ''):
                if not self._running:
                    break
                self.output_signal.emit(line.strip()) # 줄바꿈 제거 후 시그널 전송

            # 프로세스 종료 대기 및 stderr 확인
            self.process.stdout.close()
            # self.process.stderr.close() # stderr는 에러 발생 시 읽기 위해 나중에 닫음
            self.process.wait()

            if self.process.returncode != 0:
                stderr_output = self.process.stderr.read()
                # `dht_relay.c`에서 센서 에러 시 아무것도 출력 안하므로, 여기에 도착하면 다른 종류의 에러일 가능성
                if stderr_output.strip(): # stderr에 내용이 있다면
                    self.error_signal.emit(f"Error running dht_relay (Code: {self.process.returncode}):\n{stderr_output}")
                else: # stderr에 내용이 없지만 비정상 종료
                    self.error_signal.emit(f"dht_relay exited with non-zero code {self.process.returncode} (No stderr output).")

        except FileNotFoundError:
            self.error_signal.emit(f"Error: Command not found or invalid path. Check '{self.command[0]}' and '{DHT_RELAY_DIR}'")
        except Exception as e:
            self.error_signal.emit(f"An unexpected error occurred in DHT thread: {e}")
        finally:
            if self.process and self.process.poll() is None: # 아직 실행 중인 경우
                self.process.terminate()
            self.finished_signal.emit()

    def stop(self):
        self._running = False
        if self.process and self.process.poll() is None:
            self.process.terminate() # 자식 프로세스 종료 시도
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill() # 강제 종료

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.title = 'Raspberry Pi Hardware Control GUI'
        self.setGeometry(100, 100, 800, 700) # 창 크기 조정
        self.setWindowTitle(self.title)

        self.initUI()
        self.dht_relay_thread = None # DHT 스레드 참조 변수
        self.dht_relay_running = False

    def initUI(self):
        main_layout = QVBoxLayout()

        # --- FPGA Driver Control Group ---
        fpga_group = QGroupBox("FPGA Driver & Device Node Control")
        fpga_layout = QVBoxLayout()
        self.btn_load_fpga = QPushButton('Load FPGA Drivers')
        self.btn_load_fpga.clicked.connect(self.load_fpga_drivers)
        fpga_layout.addWidget(self.btn_load_fpga)

        self.btn_make_lcd_node = QPushButton('Make LCD Node & Set Permissions')
        self.btn_make_lcd_node.clicked.connect(self.make_lcd_node)
        fpga_layout.addWidget(self.btn_make_lcd_node)
        fpga_group.setLayout(fpga_layout)
        main_layout.addWidget(fpga_group)

        # --- DHT Relay Control Group ---
        dht_group = QGroupBox("DHT Sensor & Relay Control")
        dht_layout = QVBoxLayout()

        # Threshold input
        threshold_input_layout = QHBoxLayout()
        threshold_input_layout.addWidget(QLabel("Set Temp Threshold (°C):"))
        self.temp_threshold_input = QLineEdit("25") # 기본값
        self.temp_threshold_input.setValidator(QRegExpValidator(QRegExp("[0-9]{1,3}"))) # 숫자만 입력
        threshold_input_layout.addWidget(self.temp_threshold_input)

        threshold_input_layout.addWidget(QLabel("Set Humi Threshold (%):"))
        self.humi_threshold_input = QLineEdit("60") # 기본값
        self.humi_threshold_input.setValidator(QRegExpValidator(QRegExp("[0-9]{1,3}"))) # 숫자만 입력
        threshold_input_layout.addWidget(self.humi_threshold_input)
        dht_layout.addLayout(threshold_input_layout)

        # Start/Stop buttons
        dht_button_layout = QHBoxLayout()
        self.btn_run_dht = QPushButton('Start DHT Relay with Thresholds')
        self.btn_run_dht.clicked.connect(self.run_dht_relay)
        dht_button_layout.addWidget(self.btn_run_dht)

        self.btn_stop_dht = QPushButton('Stop DHT Relay')
        self.btn_stop_dht.clicked.connect(self.stop_dht_relay)
        self.btn_stop_dht.setEnabled(False) # 처음엔 비활성화
        dht_button_layout.addWidget(self.btn_stop_dht)
        dht_layout.addLayout(dht_button_layout)

        # Display current sensor values and relay states
        self.current_temp_label = QLabel("Current Temperature: N/A")
        self.current_humi_label = QLabel("Current Humidity: N/A")
        self.relay1_status_label = QLabel("Relay 1 (Temp): N/A")
        self.relay2_status_label = QLabel("Relay 2 (Humi): N/A")
        
        dht_layout.addWidget(self.current_temp_label)
        dht_layout.addWidget(self.current_humi_label)
        dht_layout.addWidget(self.relay1_status_label)
        dht_layout.addWidget(self.relay2_status_label)

        dht_group.setLayout(dht_layout)
        main_layout.addWidget(dht_group)

        # --- LCD Text Input Group ---
        lcd_group = QGroupBox("FPGA Text LCD Control")
        lcd_text_layout = QVBoxLayout()
        lcd_text_layout.addWidget(QLabel("Text to send to FPGA LCD (16 chars per line):"))
        
        self.lcd_input_line1 = QLineEdit()
        self.lcd_input_line1.setPlaceholderText("Line 1 (max 16 chars)")
        self.lcd_input_line1.setMaxLength(16)
        lcd_text_layout.addWidget(self.lcd_input_line1)

        self.lcd_input_line2 = QLineEdit()
        self.lcd_input_line2.setPlaceholderText("Line 2 (max 16 chars)")
        self.lcd_input_line2.setMaxLength(16)
        lcd_text_layout.addWidget(self.lcd_input_line2)

        self.btn_send_lcd = QPushButton('Send Text to LCD')
        self.btn_send_lcd.clicked.connect(self.send_to_lcd)
        lcd_text_layout.addWidget(self.btn_send_lcd)
        lcd_group.setLayout(lcd_text_layout)
        main_layout.addWidget(lcd_group)

        # --- Log Output ---
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        main_layout.addWidget(QLabel("Application Log:"))
        main_layout.addWidget(self.log_output)

        self.setLayout(main_layout)

    def log(self, message):
        self.log_output.append(message)
        # 스크롤을 항상 최하단으로 유지
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def execute_command(self, command, cwd=None, success_msg="", error_msg="", sudo_required=True):
        full_command = ["sudo"] + command if sudo_required else command
        self.log(f"Executing: {' '.join(full_command)}")
        try:
            result = subprocess.run(
                full_command,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True # Non-zero exit code raises CalledProcessError
            )
            self.log(f"SUCCESS: {success_msg}")
            if result.stdout:
                self.log(f"STDOUT:\n{result.stdout.strip()}")
            if result.stderr:
                self.log(f"STDERR:\n{result.stderr.strip()}")
            return True
        except FileNotFoundError:
            self.log(f"ERROR: Command not found. Is '{full_command[0]}' in PATH? (Path: {os.environ.get('PATH')})")
            QMessageBox.critical(self, "Error", f"Command not found: '{full_command[0]}'. Make sure it's installed and in your PATH.")
        except subprocess.CalledProcessError as e:
            self.log(f"ERROR: {error_msg} (Exit Code: {e.returncode})")
            self.log(f"STDOUT:\n{e.stdout.strip()}")
            self.log(f"STDERR:\n{e.stderr.strip()}")
            QMessageBox.critical(self, "Error", f"{error_msg}\nError Code: {e.returncode}\n{e.stderr.strip()}")
        except Exception as e:
            self.log(f"AN UNEXPECTED ERROR OCCURRED: {e}")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")
        return False

    def load_fpga_drivers(self):
        # FPGA 모듈 로드 (sudo 필요)
        self.log("Attempting to load FPGA interface driver...")
        if self.execute_command(
            ["insmod", "fpga_interface_driver.ko"],
            cwd=FPGA_MODULE_PATH,
            success_msg="FPGA interface driver loaded.",
            error_msg="Failed to load FPGA interface driver.",
            sudo_required=True
        ):
            self.log("Attempting to load FPGA text LCD driver...")
            self.execute_command(
                ["insmod", "fpga_text_lcd_driver.ko"],
                cwd=FPGA_MODULE_PATH,
                success_msg="FPGA text LCD driver loaded.",
                error_msg="Failed to load FPGA text LCD driver.",
                sudo_required=True
            )

    def make_lcd_node(self):
        # 장치 파일 생성 (sudo 필요)
        self.log(f"Attempting to create {FPGA_TEXT_LCD_DEV_NODE} node...")
        # 기존 노드가 있으면 삭제 후 생성 (선택 사항, 에러 방지)
        self.execute_command(
            ["rm", "-f", FPGA_TEXT_LCD_DEV_NODE],
            success_msg=f"Removed existing {FPGA_TEXT_LCD_DEV_NODE} (if any).",
            error_msg=f"Failed to remove {FPGA_TEXT_LCD_DEV_NODE}.",
            sudo_required=True
        )

        if self.execute_command(
            ["mknod", FPGA_TEXT_LCD_DEV_NODE, "c", "263", "0"],
            cwd="/dev/", # mknod는 보통 /dev에서 실행하지만, 절대경로 사용 가능
            success_msg=f"Created {FPGA_TEXT_LCD_DEV_NODE} node.",
            error_msg=f"Failed to create {FPGA_TEXT_LCD_DEV_NODE} node.",
            sudo_required=True
        ):
            # 생성 후에는 접근 권한을 설정해주는 것이 좋습니다.
            self.execute_command(
                ["chmod", "666", FPGA_TEXT_LCD_DEV_NODE],
                success_msg=f"Set permissions for {FPGA_TEXT_LCD_DEV_NODE}.",
                error_msg=f"Failed to set permissions for {FPGA_TEXT_LCD_DEV_NODE}.",
                sudo_required=True
            )

    def run_dht_relay(self):
        if self.dht_relay_running:
            self.log("DHT Relay is already running.")
            return

        temp_thresh = self.temp_threshold_input.text()
        humi_thresh = self.humi_threshold_input.text()

        if not temp_thresh or not humi_thresh:
            QMessageBox.warning(self, "Input Error", "Please enter both Temperature and Humidity thresholds.")
            return

        # dht_relay.c를 수정하여 명령줄 인자로 임계값을 받도록 가정합니다.
        # 예: ./dht_relay 25 60
        command = [DHT_RELAY_EXEC, temp_thresh, humi_thresh]
        
        self.log(f"Attempting to run DHT Relay: {' '.join(command)}")
        self.dht_relay_thread = DhtRelayThread(command)
        self.dht_relay_thread.output_signal.connect(self.process_dht_output)
        self.dht_relay_thread.finished_signal.connect(self.dht_relay_finished)
        self.dht_relay_thread.error_signal.connect(self.dht_relay_error)
        self.dht_relay_thread.start()
        self.dht_relay_running = True
        self.btn_run_dht.setEnabled(False)
        self.btn_stop_dht.setEnabled(True)
        self.log("DHT Relay started in a separate thread. Waiting for output...")

    def process_dht_output(self, msg):
        # 예시 출력: Humidity = 50.2 % (Relay: OFF) Temperature = 25.5 *C (77.9 *F) (Relay: ON)
        self.log(f"DHT Raw: {msg}") 
        
        match = re.search(
            r"Humidity = (\d+\.\d+) % \(Relay: (ON|OFF)\) Temperature = (\d+\.\d+) \*C \(\d+\.\d+ \*F\) \(Relay: (ON|OFF)\)",
            msg
        )
        if match:
            humi_val = float(match.group(1))
            humi_relay_status = match.group(2)
            temp_val = float(match.group(3))
            temp_relay_status = match.group(4)
            
            self.current_humi_label.setText(f"Current Humidity: {humi_val:.1f}%")
            self.current_temp_label.setText(f"Current Temperature: {temp_val:.1f}°C")
            self.relay1_status_label.setText(f"Relay 1 (Temp): {temp_relay_status}") # Relay1이 온도 릴레이
            self.relay2_status_label.setText(f"Relay 2 (Humi): {humi_relay_status}") # Relay2가 습도 릴레이

            self.log(f"Extracted - Temp: {temp_val:.1f}°C ({temp_relay_status}), Humi: {humi_val:.1f}% ({humi_relay_status})")
        # dht_relay.c에서 센서 에러 시 아무것도 출력 안하므로 else if는 필요 없을 수 있음.
        # else:
        #     self.log("DHT: Unexpected output format or sensor error.")

    def dht_relay_finished(self):
        self.log("DHT Relay process finished.")
        self.dht_relay_running = False
        self.btn_run_dht.setEnabled(True)
        self.btn_stop_dht.setEnabled(False)
        self.dht_relay_thread = None

    def dht_relay_error(self, message):
        self.log(f"DHT Relay Error: {message}")
        QMessageBox.critical(self, "DHT Relay Error", message)
        self.dht_relay_running = False
        self.btn_run_dht.setEnabled(True)
        self.btn_stop_dht.setEnabled(False)
        self.dht_relay_thread = None

    def stop_dht_relay(self):
        if self.dht_relay_running and self.dht_relay_thread:
            self.log("Stopping DHT Relay process...")
            self.dht_relay_thread.stop()
            self.dht_relay_thread.wait() # 스레드가 완전히 종료될 때까지 대기
            self.log("DHT Relay process stopped.")
        else:
            self.log("DHT Relay is not running.")
        self.dht_relay_running = False
        self.btn_run_dht.setEnabled(True)
        self.btn_stop_dht.setEnabled(False)


    def send_to_lcd(self):
        line1_text = self.lcd_input_line1.text()
        line2_text = self.lcd_input_line2.text()

        # `dht_relay.c`의 `write_to_lcd` 함수를 직접 호출하는 것은 파이썬에서 어렵습니다.
        # 대신, 이 명령을 수행하는 별도의 C 프로그램을 만들거나,
        # 파이썬에서 직접 장치 파일을 열고 쓰는 방식을 사용해야 합니다.
        # 여기서는 파이썬에서 직접 장치 파일에 쓰는 방식을 사용합니다.
        
        # C 코드의 write_to_lcd와 동일하게 32바이트 버퍼를 만듭니다.
        # 첫 16바이트는 line1, 다음 16바이트는 line2
        display_buffer = bytearray(32)
        
        # line1 채우기 (최대 16바이트, 부족하면 공백으로 채움)
        line1_bytes = line1_text.encode('ascii', 'replace')[:16]
        display_buffer[:len(line1_bytes)] = line1_bytes
        for i in range(len(line1_bytes), 16):
            display_buffer[i] = ord(' ') # 공백으로 채움

        # line2 채우기 (최대 16바이트, 부족하면 공백으로 채움)
        line2_bytes = line2_text.encode('ascii', 'replace')[:16]
        display_buffer[16:16+len(line2_bytes)] = line2_bytes
        for i in range(16 + len(line2_bytes), 32):
            display_buffer[i] = ord(' ') # 공백으로 채움

        self.log(f"Attempting to send '{line1_text}' (Line1) and '{line2_text}' (Line2) to {FPGA_TEXT_LCD_DEV_NODE}")
        try:
            # 라즈베리파이에서 이 부분이 실제 장치 파일에 쓰여짐
            # 'wb' 모드로 바이너리 쓰기
            with open(FPGA_TEXT_LCD_DEV_NODE, "wb") as f:
                f.write(display_buffer)
            self.log(f"SUCCESS: Sent text to FPGA LCD.")
        except FileNotFoundError:
            self.log(f"ERROR: LCD device node '{FPGA_TEXT_LCD_DEV_NODE}' not found. Make sure it's created and drivers are loaded.")
            QMessageBox.critical(self, "Error", f"LCD device node '{FPGA_TEXT_LCD_DEV_NODE}' not found. Make sure it's created and drivers are loaded.")
        except PermissionError:
            self.log(f"ERROR: Permission denied to write to {FPGA_TEXT_LCD_DEV_NODE}. (Run GUI with sudo or fix permissions)")
            QMessageBox.critical(self, "Error", f"Permission denied to write to {FPGA_TEXT_LCD_DEV_NODE}. Please ensure correct permissions (e.g., sudo chmod 666 {FPGA_TEXT_LCD_DEV_NODE}) or run the GUI with sudo.")
        except Exception as e:
            self.log(f"AN UNEXPECTED ERROR OCCURRED while writing to LCD: {e}")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    ex.show()
    sys.exit(app.exec_())
