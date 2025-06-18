import os
import signal
import subprocess
import threading
import time
import re # 추가
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

# --- 시그널 핸들러 함수 ---
def signal_handler(sig, frame):
    print(f"\nReceived signal {sig}. Initiating graceful shutdown...")
    stop_dht_process_gracefully()
    # Flask 앱 자체를 종료하려면 sys.exit()를 호출하거나,
    # 이 함수가 리턴되면 웹 서버가 자연스럽게 종료되도록 합니다.
    # Werkzeug 개발 서버는 SIGINT를 받으면 자동으로 종료됩니다.
    os._exit(0) # 즉시 종료 (정리 후)

def stop_dht_process_gracefully():
    global dht_process
    if dht_process and dht_process.poll() is None:
        print("Terminating dht_fpga process gracefully...")
        try:
            # C 코드의 SIGINT 핸들러를 사용하도록 SIGINT를 보냅니다.
            # os.killpg는 프로세스 그룹 전체에 시그널을 보냅니다.
            os.killpg(os.getpgid(dht_process.pid), signal.SIGINT)
            dht_process.wait(timeout=5) # 최대 5초 대기
            print("dht_fpga process terminated.")
        except ProcessLookupError:
            print("dht_fpga process already terminated or not found.")
        except subprocess.TimeoutExpired:
            print("dht_fpga did not terminate gracefully. Forcing kill.")
            os.killpg(os.getpgid(dht_process.pid), signal.SIGKILL)
            dht_process.wait(timeout=1)
        except Exception as e:
            print(f"Error during dht_fpga termination: {e}")
        dht_process = None
        # 프로세스 종료 후 센서 상태 초기화
        last_sensor_data = {
            "temp_val": "Stopped",
            "humi_val": "Stopped",
            "temp_led_status": "OFF",
            "humi_led_status": "OFF"
        }
        process_output_buffer.append("dht_fpga process stopped by server.")


# --- C 프로그램 실행 및 로그 읽기 스레드 ---
def run_dht_program(temp_threshold, humi_threshold):
    global dht_process, last_sensor_data, process_output_buffer

    # 기존 프로세스 종료
    if dht_process and dht_process.poll() is None:
        print("Terminating existing dht_fpga process for restart...")
        stop_dht_process_gracefully() # 기존 프로세스를 우아하게 종료
        time.sleep(1) # 종료될 시간을 줌

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
            preexec_fn=os.setsid # 자식 프로세스 그룹을 생성하여 SIGINT가 이 그룹에만 전달되도록 함
        )
        print(f"Started dht_fpga with PID: {dht_process.pid}, PGID: {os.getpgid(dht_process.pid)}")
        process_output_buffer.append(f"dht_fpga started with T:{temp_threshold} H:{humi_threshold}")

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
        process_output_buffer.append("dht_fpga process stopped naturally.")


    except FileNotFoundError:
        print("Error: dht_fpga executable not found. Make sure it's compiled and in the same directory.")
        process_output_buffer.append("Error: dht_fpga executable not found!")
        last_sensor_data = {
            "temp_val": "File Error",
            "humi_val": "File Error",
            "temp_led_status": "N/A",
            "humi_led_status": "N/A"
        }
    except Exception as e:
        print(f"An unexpected error occurred in run_dht_program: {e}")
        process_output_buffer.append(f"Runtime Error: {e}")
        last_sensor_data = {
            "temp_val": "System Error",
            "humi_val": "System Error",
            "temp_led_status": "N/A",
            "humi_led_status": "N/A"
        }
    finally:
        dht_process = None # 확실히 None으로 설정

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
    stop_dht_process_gracefully()
    return jsonify({"status": "success", "message": "Control stop requested. Check logs for status."})


if __name__ == '__main__':
    # SIGINT (Ctrl+C) 및 SIGTERM 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 로컬 네트워크의 모든 인터페이스에서 접근 가능하도록 host='0.0.0.0' 설정
    # 개발 중에만 debug=True를 사용하고, 프로덕션에서는 False로 설정해야 합니다.
    app.run(host='0.0.0.0', port=5000, debug=False)
