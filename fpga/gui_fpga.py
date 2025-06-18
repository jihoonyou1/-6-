import tkinter as tk
import subprocess
import threading
import os
import signal
import re
import requests # requests 라이브러리 추가 (pip install requests)
import time # time 모듈 추가

# ... (기존 전역 변수들)

# 웹 서버 프로세스 관리를 위한 전역 변수
web_server_process = None

# ... (기존 start_control, update_sensor_data 등 함수)

def start_web_server():
    global web_server_process
    if web_server_process and web_server_process.poll() is None:
        print("Web server is already running.")
        return

    try:
        # 웹 서버를 백그라운드로 실행합니다.
        # preexec_fn=os.setsid를 사용하여 새 프로세스 그룹에 할당합니다.
        web_server_process = subprocess.Popen(
            ["python3", "web_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # 에러도 파이프를 통해 읽도록 설정
            text=True,
            bufsize=1,
            preexec_fn=os.setsid
        )
        print(f"Web server started with PID: {web_server_process.pid}, PGID: {os.getpgid(web_server_process.pid)}")
        # 웹 서버가 시작될 시간을 잠시 기다립니다.
        time.sleep(2)
        status_label.config(text="웹 서버 실행 중") # GUI에 웹 서버 상태 표시

        # 웹 서버의 로그를 읽기 위한 스레드 (선택 사항, 복잡해질 수 있음)
        # threading.Thread(target=read_web_server_logs, daemon=True).start()

    except FileNotFoundError:
        print("Error: web_server.py not found.")
        status_label.config(text="web_server.py 없음")
    except Exception as e:
        print(f"Error starting web server: {e}")
        status_label.config(text="웹 서버 시작 오류")

def stop_web_server():
    global web_server_process
    if web_server_process and web_server_process.poll() is None:
        print("Stopping web server...")
        try:
            # 웹 서버 프로세스 그룹에 SIGINT를 보냅니다.
            os.killpg(os.getpgid(web_server_process.pid), signal.SIGINT)
            web_server_process.wait(timeout=5)
            print("Web server stopped.")
            status_label.config(text="웹 서버 중지됨")
        except ProcessLookupError:
            print("Web server process already terminated or PID not found.")
        except subprocess.TimeoutExpired:
            print("Web server did not terminate gracefully. Forcing kill.")
            os.killpg(os.getpgid(web_server_process.pid), signal.SIGKILL)
            web_server_process.wait(timeout=1)
        except Exception as e:
            print(f"Error during web server termination: {e}")
        finally:
            web_server_process = None
    else:
        print("Web server is not running.")


# GUI에서 센서 데이터를 웹 서버 API를 통해 가져오는 함수로 변경 (GUI와 웹이 연동된 경우)
def update_sensor_data_from_web():
    try:
        response = requests.get("http://localhost:5000/get_sensor_data")
        response.raise_for_status() # HTTP 오류가 발생하면 예외 발생
        data = response.json()

        global last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat
        last_humi_val = data.get("humi_val", "--")
        last_relay2_stat = data.get("humi_led_status", "--")
        last_temp_val = data.get("temp_val", "--")
        last_relay1_stat = data.get("temp_led_status", "--")

        current_temp_label.config(text=f"{last_temp_val}°C")
        current_humi_label.config(text=f"{last_humi_val}%")
        relay1_status_label.config(text=f"TEMP LED (D1-D4): {last_relay1_stat}")
        relay2_status_label.config(text=f"HUMI LED (D5-D8): {last_relay2_stat}")

    except requests.exceptions.ConnectionError:
        print("DEBUG: Could not connect to web server. Is it running?")
        current_temp_label.config(text="Web Server Down")
        current_humi_label.config(text="Web Server Down")
        relay1_status_label.config(text="TEMP LED (D1-D4): N/A")
        relay2_status_label.config(text="HUMI LED (D5-D8): N/A")
    except Exception as e:
        print(f"Error updating sensor data from web: {e}")


def on_closing():
    global dht_process, web_server_process
    # GUI 종료 시 dht_fpga 프로세스와 웹 서버 프로세스 모두 종료 시도
    if dht_process and dht_process.poll() is None:
        print("GUI closing. Sending SIGINT to dht_fpga process group...")
        try:
            os.killpg(os.getpgid(dht_process.pid), signal.SIGINT)
            dht_process.wait(timeout=5)
        except Exception as e:
            print(f"Error stopping dht_fpga on GUI close: {e}")
    
    stop_web_server() # 웹 서버도 종료

    print("Destroying GUI...")
    root.destroy()

# ... (메인 GUI 창 생성 부분)

# "사이트 연동" 버튼 추가
link_site_button = tk.Button(root, text="사이트 연동", command=start_web_server, font=("Arial", 10, "bold"), bg="lightblue")
link_site_button.grid(row=8, columnspan=2, pady=10) # 적절한 row 설정

status_label = tk.Label(root, text="대기 중", font=("Arial", 10))
status_label.grid(row=9, columnspan=2)

# start_control 함수도 변경해야 합니다.
# 이제 start_control은 직접 dht_fpga를 실행하는 대신, 웹 서버의 /start_control API를 호출해야 합니다.
def start_control_via_web():
    temp_str = temp_entry.get()
    humi_str = humi_entry.get()

    try:
        temp_threshold = float(temp_str)
        humi_threshold = int(humi_str)

        # 웹 서버가 실행 중인지 확인
        if web_server_process is None or web_server_process.poll() is not None:
            print("Web server is not running. Please start the web server first.")
            status_label.config(text="웹 서버 시작 필요")
            return

        # 웹 서버의 /start_control API 호출
        response = requests.post(
            "http://localhost:5000/start_control",
            data={'temp_set': temp_str, 'humi_set': humi_str}
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            print("Control started via web server.")
            temp_entry.config(state='disabled')
            humi_entry.config(state='disabled')
            start_button.config(state='disabled')
            # 센서 데이터 업데이트를 웹 API를 통해 가져오도록 변경
            threading.Thread(target=lambda: root.after(0, lambda: update_sensor_data_from_web_loop()), daemon=True).start()
        else:
            print(f"Failed to start control via web: {data.get('message')}")
            status_label.config(text="웹 제어 시작 실패")

    except ValueError:
        current_temp_label.config(text="INPUT ERROR")
        current_humi_label.config(text="INPUT ERROR")
    except requests.exceptions.ConnectionError:
        print("Could not connect to web server to start control.")
        status_label.config(text="웹 서버 연결 불가")
    except Exception as e:
        print(f"An unexpected error occurred in start_control_via_web: {e}")
        status_label.config(text="SYS ERROR")

# 센서 데이터 업데이트 루프 (웹 API 사용)
def update_sensor_data_from_web_loop():
    while True:
        update_sensor_data_from_web()
        time.sleep(2) # 2초마다 업데이트 (웹 서버의 /get_sensor_data 주기와 일치)
        if web_server_process is None or web_server_process.poll() is not None:
            print("Web server stopped, stopping GUI data update.")
            break

# 기존 start_button command를 변경해야 합니다.
start_button.config(command=start_control_via_web)

# ... (나머지 GUI 코드)
