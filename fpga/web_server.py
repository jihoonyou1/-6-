import os
import signal
import subprocess
import threading
import time
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# --- 전역 변수 및 상태 관리 ---
dht_process = None
last_sensor_data = {
    "temp_val": "--",
    "humi_val": "--",
    "temp_led_status": "--",
    "humi_led_status": "--"
}
current_temp_threshold = 25.0
current_humi_threshold = 60
process_output_buffer = [] # C 프로그램 로그를 저장할 버퍼

# --- C 프로그램 실행 및 로그 읽기 스레드 ---
def run_dht_program(temp_threshold, humi_threshold):
    global dht_process, last_sensor_data, process_output_buffer

    # 기존 프로세스 종료
    if dht_process and dht_process.poll() is None:
        print("Terminating existing dht_fpga process...")
        try:
            os.killpg(os.getpgid(dht_process.pid), signal.SIGTERM)
            dht_process.wait(timeout=2)
        except ProcessLookupError:
            pass
        if dht_process.poll() is None:
            os.killpg(os.getpgid(dht_process.pid), signal.SIGKILL)
            dht_process.wait(timeout=1)
        dht_process = None

    process_output_buffer.clear() # 버퍼 초기화
    last_sensor_data = { # 센서 데이터 초기화
        "temp_val": "N/A",
        "humi_val": "N/A",
        "temp_led_status": "N/A",
        "humi_led_status": "N/A"
    }

    try:
        dht_process = subprocess.Popen(
            ["./dht_fpga", str(temp_threshold), str(humi_threshold)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # 에러도 stdout으로 리다이렉트하여 함께 읽기
            text=True,
            bufsize=1,
            preexec_fn=os.setsid
        )
        print(f"Started dht_fpga with PID: {dht_process.pid}, PGID: {os.getpgid(dht_process.pid)}")

        # C 프로그램의 출력을 읽고 파싱하는 루프
        for line in iter(dht_process.stdout.readline, ''):
            line = line.strip()
            if line:
                process_output_buffer.append(line)
                if len(process_output_buffer) > 50: # 로그 버퍼 크기 제한
                    process_output_buffer.pop(0)

                # 정규표현식으로 센서 데이터 파싱
                # C 코드의 printf 형식: Humidity = %.1f %% (LED: %s) Temperature = %.1f *C (LED: %s)
                pattern = r"Humidity = (N/A|-?\d+\.?\d*)\s*%\s*\(LED:\s*(ON|OFF|N/A)\)\s*Temperature = (N/A|-?\d+\.?\d*)\s*\*C\s*\(LED:\s*(ON|OFF|N/A)\)"
                match = re.search(pattern, line)
                if match:
                    last_sensor_data["humi_val"] = match.group(1)
                    last_sensor_data["humi_led_status"] = match.group(2)
                    last_sensor_data["temp_val"] = match.group(3)
                    last_sensor_data["temp_led_status"] = match.group(4)
                else:
                    # 오류 메시지 또는 다른 출력 처리
                    if "Usage Error" in line or "WiringPi setup failed" in line:
                        last_sensor_data["temp_val"] = "ERROR"
                        last_sensor_data["humi_val"] = "ERROR"
                        last_sensor_data["temp_led_status"] = "ERROR"
                        last_sensor_data["humi_led_status"] = "ERROR"

        print("dht_fpga process ended.")
        dht_process = None
        # 프로세스 종료 후 센서 상태 초기화 또는 마지막 유효 값 유지
        last_sensor_data = {
            "temp_val": "Process Ended",
            "humi_val": "Process Ended",
            "temp_led_status": "Ended",
            "humi_led_status": "Ended"
        }

    except FileNotFoundError:
        print("Error: dht_fpga executable not found. Make sure it's compiled and in the same directory.")
        last_sensor_data = {
            "temp_val": "File Error",
            "humi_val": "File Error",
            "temp_led_status": "N/A",
            "humi_led_status": "N/A"
        }
    except Exception as e:
        print(f"An unexpected error occurred in run_dht_program: {e}")
        last_sensor_data = {
            "temp_val": "System Error",
            "humi_val": "System Error",
            "temp_led_status": "N/A",
            "humi_led_status": "N/A"
        }

# --- 웹 라우트 ---

@app.route('/')
def index():
    # 웹 페이지 템플릿 렌더링
    return render_template('index.html',
                            temp_threshold=current_temp_threshold,
                            humi_threshold=current_humi_threshold)

@app.route('/start_control', methods=['POST'])
def start_control():
    global current_temp_threshold, current_humi_threshold
    temp_str = request.form.get('temp_set')
    humi_str = request.form.get('humi_set')

    try:
        current_temp_threshold = float(temp_str)
        current_humi_threshold = int(humi_str)

        # C 프로그램 실행 스레드를 시작합니다.
        threading.Thread(target=run_dht_program, args=(current_temp_threshold, current_humi_threshold), daemon=True).start()
        return jsonify({"status": "success", "message": "Control started.",
                        "temp_threshold": current_temp_threshold,
                        "humi_threshold": current_humi_threshold})
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid input for thresholds."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to start control: {e}"})

@app.route('/get_sensor_data')
def get_sensor_data():
    return jsonify(last_sensor_data)

@app.route('/get_program_logs')
def get_program_logs():
    # 로그 버퍼를 역순으로 보내 최신 로그가 먼저 보이도록 합니다.
    return jsonify({"logs": list(reversed(process_output_buffer))})

@app.route('/stop_control', methods=['POST'])
def stop_control():
    global dht_process
    if dht_process and dht_process.poll() is None:
        print("Stopping dht_fpga process...")
        try:
            os.killpg(os.getpgid(dht_process.pid), signal.SIGINT) # C 코드의 SIGINT 핸들러 활용
            dht_process.wait(timeout=5)
            # C 프로그램이 종료된 후 FPGA LED를 끄도록 가정
            # 실제로는 C 프로그램의 cleanup_handler에서 처리될 것입니다.
            return jsonify({"status": "success", "message": "Control stopped."})
        except ProcessLookupError:
            return jsonify({"status": "success", "message": "dht_fpga process already terminated."})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error stopping control: {e}"})
    return jsonify({"status": "info", "message": "No active dht_fpga process to stop."})

# 애플리케이션 종료 시 정리
@app.before_server_stop
def cleanup_on_shutdown():
    global dht_process
    if dht_process and dht_process.poll() is None:
        print("Server shutting down. Terminating dht_fpga process...")
        try:
            os.killpg(os.getpgid(dht_process.pid), signal.SIGINT)
            dht_process.wait(timeout=5)
        except ProcessLookupError:
            pass
        except Exception as e:
            print(f"Error during shutdown cleanup: {e}")

if __name__ == '__main__':
    import re # 전역 변수 선언 문제로 임시로 여기에 re 추가. 실제로는 상단에 있어야 함.
    # GUI 스크립트가 이미 C 프로그램을 실행하므로, 여기서는 Flask만 실행
    # 로컬 네트워크의 모든 인터페이스에서 접근 가능하도록 host='0.0.0.0' 설정
    app.run(host='0.0.0.0', port=5000, debug=False) # 디버그 모드는 개발 중에만 사용하고 배포 시에는 False