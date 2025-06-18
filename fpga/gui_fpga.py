import tkinter as tk
import subprocess
import threading
import os
import signal
import re
import requests # requests 라이브러리 추가
import time # time 모듈 추가

# 전역 변수 초기화
temp_threshold = 0.0
humi_threshold = 0
# dht_process는 이제 web_server.py에 의해 관리되므로, 여기서는 직접 사용하지 않습니다.
dht_process = None # 더 이상 dht_fpga.c 프로세스를 직접 관리하지 않음
last_temp_val = "--"
last_humi_val = "--"
last_relay1_stat = "--" # 이제 TEMP LED 상태를 나타냅니다.
last_relay2_stat = "--" # 이제 HUMI LED 상태를 나타냅니다.

# 웹 서버 프로세스 관리를 위한 전역 변수
web_server_process = None
sensor_update_thread = None # 센서 데이터 업데이트 스레드
log_update_thread = None    # 로그 업데이트 스레드

# --- 웹 서버 관리 함수 ---
def start_web_server():
    global web_server_process
    if web_server_process and web_server_process.poll() is None:
        print("Web server is already running.")
        status_label.config(text="웹 서버 이미 실행 중")
        return

    try:
        # 웹 서버를 백그라운드로 실행합니다.
        # preexec_fn=os.setsid를 사용하여 새 프로세스 그룹에 할당하여,
        # 부모 프로세스 종료 시 자식 프로세스도 함께 종료될 수 있도록 합니다.
        web_server_process = subprocess.Popen(
            ["python3", "web_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # 에러도 파이프를 통해 읽도록 설정
            text=True,
            bufsize=1, # 라인 버퍼링
            preexec_fn=os.setsid
        )
        print(f"Web server started with PID: {web_server_process.pid}, PGID: {os.getpgid(web_server_process.pid)}")
        # 웹 서버가 완전히 시작될 시간을 잠시 기다립니다.
        time.sleep(3) # Flask 서버 시작에 시간이 걸릴 수 있습니다.
        status_label.config(text="웹 서버 실행 중 (http://localhost:5000)")
        link_site_button.config(state='disabled') # 웹 서버 실행 후 버튼 비활성화

        # 웹 서버가 시작되면, 웹 API를 통해 센서 데이터와 로그를 업데이트하는 스레드를 시작
        start_sensor_and_log_updates()

    except FileNotFoundError:
        print("Error: web_server.py not found. Make sure it's in the same directory.")
        status_label.config(text="web_server.py 없음")
    except Exception as e:
        print(f"Error starting web server: {e}")
        status_label.config(text=f"웹 서버 시작 오류: {e}")

def stop_web_server():
    global web_server_process, sensor_update_thread, log_update_thread
    if web_server_process and web_server_process.poll() is None:
        print("Stopping web server...")
        try:
            # 웹 서버 종료 API 호출 (dht_fpga도 종료시킴)
            requests.post("http://localhost:5000/stop_control")
            
            # 웹 서버 프로세스 그룹에 SIGINT를 보냅니다.
            # 웹 서버 내부적으로 SIGINT를 처리하도록 되어 있으므로, 이 부분은 예비용입니다.
            os.killpg(os.getpgid(web_server_process.pid), signal.SIGINT)
            web_server_process.wait(timeout=5) # 최대 5초 대기
            print("Web server stopped.")
            status_label.config(text="웹 서버 중지됨")
        except ProcessLookupError:
            print("Web server process already terminated or PID not found.")
        except subprocess.TimeoutExpired:
            print("Web server did not terminate gracefully. Forcing kill.")
            os.killpg(os.getpgid(web_server_process.pid), signal.SIGKILL)
            web_server_process.wait(timeout=1)
        except requests.exceptions.ConnectionError:
            print("Could not connect to web server to send stop command. Attempting direct kill.")
            try:
                os.killpg(os.getpgid(web_server_process.pid), signal.SIGINT)
                web_server_process.wait(timeout=5)
            except Exception as e:
                print(f"Error during direct web server termination: {e}")
        except Exception as e:
            print(f"Error during web server termination: {e}")
        finally:
            web_server_process = None
            stop_sensor_and_log_updates() # 업데이트 스레드 중지
            link_site_button.config(state='normal') # 웹 서버 중지 후 버튼 활성화
    else:
        print("Web server is not running.")


def start_sensor_and_log_updates():
    global sensor_update_thread, log_update_thread
    if sensor_update_thread and sensor_update_thread.is_alive():
        return # 이미 실행 중이면 중복 실행 방지

    # 센서 데이터 업데이트 스레드 시작
    sensor_update_thread = threading.Thread(target=update_sensor_data_from_web_loop, daemon=True)
    sensor_update_thread.start()

    # 로그 업데이트 스레드 시작
    log_update_thread = threading.Thread(target=update_program_logs_from_web_loop, daemon=True)
    log_update_thread.start()

def stop_sensor_and_log_updates():
    global sensor_update_thread, log_update_thread
    # 스레드에 종료 신호를 보내는 직접적인 방법은 없으므로,
    # 루프 내에서 web_server_process 상태를 확인하여 종료되도록 합니다.
    # 여기서는 스레드 객체를 None으로 만들어 다음 시작 시 새 스레드가 생성되도록 합니다.
    sensor_update_thread = None
    log_update_thread = None
    # GUI에 N/A 표시
    current_temp_label.config(text="--°C")
    current_humi_label.config(text="--%")
    relay1_status_label.config(text="TEMP LED (D1-D4): --")
    relay2_status_label.config(text="HUMI LED (D5-D8): --")


# --- 센서 데이터 및 로그 업데이트 (웹 API를 통해) ---
def update_sensor_data_from_web():
    global last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat
    try:
        response = requests.get("http://localhost:5000/get_sensor_data")
        response.raise_for_status() # HTTP 오류가 발생하면 예외 발생
        data = response.json()

        last_humi_val = data.get("humi_val", "--")
        last_relay2_stat = data.get("humi_led_status", "--") # D5-D8 (습도)
        last_temp_val = data.get("temp_val", "--")
        last_relay1_stat = data.get("temp_led_status", "--") # D1-D4 (온도)

        current_temp_label.config(text=f"{last_temp_val}°C")
        current_humi_label.config(text=f"{last_humi_val}%")
        relay1_status_label.config(text=f"TEMP LED (D1-D4): {last_relay1_stat}")
        relay2_status_label.config(text=f"HUMI LED (D5-D8): {last_relay2_stat}")

    except requests.exceptions.ConnectionError:
        # print("DEBUG: Could not connect to web server. Is it running?")
        current_temp_label.config(text="N/A (WS Down)")
        current_humi_label.config(text="N/A (WS Down)")
        relay1_status_label.config(text="TEMP LED (D1-D4): N/A")
        relay2_status_label.config(text="HUMI LED (D5-D8): N/A")
    except Exception as e:
        print(f"Error updating sensor data from web: {e}")
        current_temp_label.config(text="Error")
        current_humi_label.config(text="Error")


def update_program_logs_from_web():
    try:
        response = requests.get("http://localhost:5000/get_program_logs")
        response.raise_for_status()
        data = response.json()
        logs_text.delete('1.0', tk.END) # 기존 로그 삭제
        for log_line in data.get("logs", []):
            logs_text.insert(tk.END, log_line + '\n')
        logs_text.see(tk.END) # 스크롤을 항상 아래로 이동
    except requests.exceptions.ConnectionError:
        # print("DEBUG: Could not connect to web server for logs. Is it running?")
        logs_text.delete('1.0', tk.END)
        logs_text.insert(tk.END, "Web server not reachable for logs.\n")
    except Exception as e:
        print(f"Error updating program logs from web: {e}")
        logs_text.insert(tk.END, f"Error fetching logs: {e}\n")


def update_sensor_data_from_web_loop():
    while web_server_process and web_server_process.poll() is None:
        update_sensor_data_from_web()
        time.sleep(2) # 2초마다 업데이트
    print("Sensor data update loop terminated.")


def update_program_logs_from_web_loop():
    while web_server_process and web_server_process.poll() is None:
        update_program_logs_from_web()
        time.sleep(1) # 1초마다 로그 업데이트
    print("Program logs update loop terminated.")


# --- GUI 컨트롤 함수 (웹 서버 API 호출) ---
def start_control_via_web():
    global temp_threshold, humi_threshold
    
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
        response.raise_for_status() # HTTP 오류가 발생하면 예외 발생
        data = response.json()

        if data.get("status") == "success":
            print("Control started via web server.")
            status_label.config(text="제어 시작됨")
            temp_entry.config(state='disabled')
            humi_entry.config(state='disabled')
            start_button.config(state='disabled')
        else:
            print(f"Failed to start control via web: {data.get('message')}")
            status_label.config(text=f"웹 제어 시작 실패: {data.get('message')}")

    except ValueError:
        current_temp_label.config(text="INPUT ERROR")
        current_humi_label.config(text="INPUT ERROR")
        status_label.config(text="임계값 입력 오류")
    except requests.exceptions.ConnectionError:
        print("Could not connect to web server to start control.")
        status_label.config(text="웹 서버 연결 불가")
    except Exception as e:
        print(f"An unexpected error occurred in start_control_via_web: {e}")
        status_label.config(text="시스템 오류")


def stop_control_via_web():
    global dht_process # 이제 dht_process는 web_server에 의해 관리
    
    # 웹 서버가 실행 중인지 확인
    if web_server_process is None or web_server_process.poll() is not None:
        print("Web server is not running. Nothing to stop.")
        status_label.config(text="웹 서버 비활성")
        return

    try:
        # 웹 서버의 /stop_control API 호출
        response = requests.post("http://localhost:5000/stop_control")
        response.raise_for_status() # HTTP 오류가 발생하면 예외 발생
        data = response.json()

        if data.get("status") == "success":
            print("Control stop requested via web server.")
            status_label.config(text="제어 중지 요청됨")
            temp_entry.config(state='normal')
            humi_entry.config(state='normal')
            start_button.config(state='normal')
            # 센서값 및 LED 상태 초기화
            current_temp_label.config(text="--°C")
            current_humi_label.config(text="--%")
            relay1_status_label.config(text="TEMP LED (D1-D4): --")
            relay2_status_label.config(text="HUMI LED (D5-D8): --")
        else:
            print(f"Failed to stop control via web: {data.get('message')}")
            status_label.config(text=f"웹 제어 중지 실패: {data.get('message')}")

    except requests.exceptions.ConnectionError:
        print("Could not connect to web server to stop control.")
        status_label.config(text="웹 서버 연결 불가")
    except Exception as e:
        print(f"An unexpected error occurred in stop_control_via_web: {e}")
        status_label.config(text="시스템 오류")


def on_closing():
    print("GUI closing. Attempting to stop web server...")
    stop_web_server() # GUI 종료 시 웹 서버 종료 시도
    print("Destroying GUI...")
    root.destroy()

# --- Tkinter GUI 설정 ---
root = tk.Tk()
root.title("DHT22 & FPGA Control GUI")
root.protocol("WM_DELETE_WINDOW", on_closing) # 윈도우 닫기 버튼 이벤트 핸들러

# 레이블 및 엔트리 생성
tk.Label(root, text="온도 임계값 (°C):").grid(row=0, column=0, padx=5, pady=2, sticky='w')
temp_entry = tk.Entry(root, width=15)
temp_entry.grid(row=0, column=1, padx=5, pady=2, sticky='ew')
temp_entry.insert(0, "25.0") # 초기값

tk.Label(root, text="습도 임계값 (%):").grid(row=1, column=0, padx=5, pady=2, sticky='w')
humi_entry = tk.Entry(root, width=15)
humi_entry.grid(row=1, column=1, padx=5, pady=2, sticky='ew')
humi_entry.insert(0, "60") # 초기값

# 시작/중지 버튼
start_button = tk.Button(root, text="START CONTROL", command=start_control_via_web, font=("Arial", 12, "bold"), bg="green", fg="white")
start_button.grid(row=2, column=0, padx=5, pady=10, sticky='ew')

stop_button = tk.Button(root, text="STOP CONTROL", command=stop_control_via_web, font=("Arial", 12, "bold"), bg="red", fg="white")
stop_button.grid(row=2, column=1, padx=5, pady=10, sticky='ew')

# 현재 온도 표시
tk.Label(root, text="CURRENT TEMP:").grid(row=3, column=0, padx=5, pady=2, sticky='w')
current_temp_label = tk.Label(root, text="--", font=("Arial", 14, "bold"), fg="blue", relief="solid", borderwidth=1, width=12)
current_temp_label.grid(row=3, column=1, padx=5, pady=2, sticky='ew')

# 온도 LED 상태 (D1-D4)
tk.Label(root, text="TEMP LED (D1-D4) Status:").grid(row=4, column=0, padx=5, pady=2, sticky='w') 
relay1_status_label = tk.Label(root, text="--", font=("Arial", 10), fg="red") 
relay1_status_label.grid(row=4, column=1, padx=5, pady=2, sticky='ew')


# 현재 습도 표시
tk.Label(root, text="CURRENT HUMI:").grid(row=5, column=0, padx=5, pady=2, sticky='w')
current_humi_label = tk.Label(root, text="--", font=("Arial", 14, "bold"), fg="darkgreen", relief="solid", borderwidth=1, width=12)
current_humi_label.grid(row=5, column=1, padx=5, pady=2, sticky='ew')

# 습도 LED 상태 (D5-D8)
tk.Label(root, text="HUMI LED (D5-D8) Status:").grid(row=6, column=0, padx=5, pady=2, sticky='w') 
relay2_status_label = tk.Label(root, text="--", font=("Arial", 10), fg="red") 
relay2_status_label.grid(row=6, column=1, padx=5, pady=2, sticky='ew')

# "사이트 연동" 버튼
link_site_button = tk.Button(root, text="사이트 연동", command=start_web_server, font=("Arial", 10, "bold"), bg="lightblue")
link_site_button.grid(row=7, columnspan=2, pady=10) # 적절한 row 설정

# 상태 메시지 레이블
status_label = tk.Label(root, text="대기 중", font=("Arial", 10), fg="purple")
status_label.grid(row=8, columnspan=2, pady=5)

# 로그 표시를 위한 Text 위젯
tk.Label(root, text="Program Logs:").grid(row=9, column=0, padx=5, pady=2, sticky='w')
logs_text = tk.Text(root, height=10, width=50, bg="lightgray", font=("Courier", 8))
logs_text.grid(row=10, columnspan=2, padx=5, pady=5, sticky='nsew')
logs_scrollbar = tk.Scrollbar(root, command=logs_text.yview)
logs_scrollbar.grid(row=10, column=2, sticky='ns')
logs_text.config(yscrollcommand=logs_scrollbar.set)

# 초기 업데이트 (연결되지 않은 상태)
update_sensor_data_from_web()
update_program_logs_from_web()

root.mainloop()
