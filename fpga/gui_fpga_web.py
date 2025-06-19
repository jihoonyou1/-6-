import tkinter as tk
import subprocess
import threading
import os
import signal
import re
import socket # IP 주소 확인을 위해 추가
from flask import Flask, render_template_string # 웹 서버를 위해 추가

# --- 전역 변수 초기화 ---
temp_threshold = 0.0
humi_threshold = 0
dht_process = None
last_temp_val = "--"
last_humi_val = "--"
last_relay1_stat = "--" # TEMP LED 상태
last_relay2_stat = "--" # HUMI LED 상태
web_server_started = False

# --- Flask 웹 서버 설정 ---
app = Flask(__name__)

# 웹 페이지 템플릿 (5초마다 새로고침)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>DHT22 & FPGA Status</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f4f4f4; }
        .container { max-width: 600px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; }
        .status-box { border: 1px solid #ddd; padding: 15px; margin-top: 20px; border-radius: 5px; }
        .status-item { font-size: 1.2em; margin-bottom: 10px; }
        .label { font-weight: bold; color: #555; min-width: 200px; display: inline-block; }
        .value { font-weight: bold; color: darkgreen; }
        .status-on { color: green; }
        .status-off { color: red; }
    </style>
</head>
<body>
    <div class="container">
        <h1>DHT22 & FPGA Live Status</h1>
        <div class="status-box">
            <div class="status-item">
                <span class="label">CURRENT TEMP:</span>
                <span class="value">{{ temp }} &deg;C</span>
            </div>
            <div class="status-item">
                <span class="label">TEMP LED (D1-D4):</span>
                <span class="value {{ 'status-on' if temp_led == 'ON' else 'status-off' }}">{{ temp_led }}</span>
            </div>
            <hr>
            <div class="status-item">
                <span class="label">CURRENT HUMI:</span>
                <span class="value">{{ humi }} %</span>
            </div>
             <div class="status-item">
                <span class="label">HUMI LED (D5-D8):</span>
                <span class="value {{ 'status-on' if humi_led == 'ON' else 'status-off' }}">{{ humi_led }}</span>
            </div>
        </div>
        <p style="text-align: center; color: #888; margin-top: 20px;">Page refreshes every 5 seconds.</p>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    """웹 페이지를 렌더링하고 현재 센서 데이터를 전달합니다."""
    global last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat
    return render_template_string(
        HTML_TEMPLATE,
        temp=last_temp_val,
        humi=last_humi_val,
        temp_led=last_relay1_stat,
        humi_led=last_relay2_stat
    )

def run_web_server():
    """웹 서버를 실행하는 함수 (별도 스레드에서 실행됨)"""
    # host='0.0.0.0'는 모든 IP 주소에서 접속 가능하도록 설정합니다.
    app.run(host='0.0.0.0', port=5000)

def get_ip_address():
    """로컬 IP 주소를 가져오는 함수"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# --- 기존 GUI 및 제어 로직 ---

def start_control():
    global temp_threshold, humi_threshold, dht_process, \
           last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat, \
           web_server_started
    
    temp_str = temp_entry.get()
    humi_str = humi_entry.get()
    
    try:
        temp_threshold = float(temp_str)
        humi_threshold = int(humi_str)
        
        temp_entry.config(state='disabled')
        humi_entry.config(state='disabled')
        start_button.config(state='disabled')
        
        current_temp_label.config(text=f"{last_temp_val}°C")
        current_humi_label.config(text=f"{last_humi_val}%")
        relay1_status_label.config(text=f"TEMP LED (D1-D4): {last_relay1_stat}") 
        relay2_status_label.config(text=f"HUMI LED (D5-D8): {last_relay2_stat}")

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

        dht_process = subprocess.Popen(
            ["./dht_fpga", str(temp_threshold), str(humi_threshold)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1, 
            preexec_fn=os.setsid 
        )
        print(f"Started dht_fpga with PID: {dht_process.pid}, PGID: {os.getpgid(dht_process.pid)}")

        threading.Thread(target=update_sensor_data, daemon=True).start()

        # 웹 서버가 시작되지 않았다면, 별도 스레드에서 시작
        if not web_server_started:
            web_thread = threading.Thread(target=run_web_server, daemon=True)
            web_thread.start()
            web_server_started = True
            ip_address = get_ip_address()
            web_info_label.config(text=f"Web UI at: http://{ip_address}:5000")


    except ValueError:
        current_temp_label.config(text="INPUT ERROR") 
        current_humi_label.config(text="INPUT ERROR") 
    except FileNotFoundError:
        current_temp_label.config(text="FILE ERROR") 
        current_humi_label.config(text="FILE ERROR") 
    except Exception as e:
        print(f"An unexpected error occurred in start_control: {e}") 
        current_temp_label.config(text="SYS ERROR") 
        current_humi_label.config(text="SYS ERROR") 


def update_sensor_data():
    global dht_process, last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat

    pattern = re.compile(r"Humidity = (N/A|-?\d+\.?\d*)\s*%\s*\(LED:\s*(ON|OFF|N/A)\)\s*Temperature = (N/A|-?\d+\.?\d*)\s*\*C\s*\(LED:\s*(ON|OFF|N/A)\)")

    for line in iter(dht_process.stdout.readline, ''):
        line = line.strip()
        print(f"Received from C: '{line}'")

        if line:
            match = pattern.match(line)
            if match:
                last_humi_val = match.group(1)
                last_relay2_stat = match.group(2) # 습도 LED
                last_temp_val = match.group(3)
                last_relay1_stat = match.group(4) # 온도 LED

                current_temp_label.config(text=f"{last_temp_val}°C")
                current_humi_label.config(text=f"{last_humi_val}%")
                relay1_status_label.config(text=f"TEMP LED (D1-D4): {last_relay1_stat}") 
                relay2_status_label.config(text=f"HUMI LED (D5-D8): {last_relay2_stat}") 
            else:
                print("DEBUG: Regex match failed.") 

    print("C program process ended. Exiting update thread.") 

def on_closing():
    global dht_process
    if dht_process and dht_process.poll() is None: 
        print("GUI closing. Sending SIGINT to dht_fpga process group...")
        try:
            os.killpg(os.getpgid(dht_process.pid), signal.SIGINT)
            dht_process.wait(timeout=5) 
        except Exception as e:
            print(f"Error sending SIGINT or waiting for dht_fpga: {e}")
    
    print("Destroying GUI...") 
    root.destroy() 

# --- Tkinter GUI 창 생성 ---
root = tk.Tk()
root.title("DHT22 & FPGA LED Control") 
root.protocol("WM_DELETE_WINDOW", on_closing)

# --- 입력 / 설정 섹션 ---
tk.Label(root, text="SET TEMP (°C):").grid(row=0, column=0, padx=5, pady=5, sticky='w')
temp_entry = tk.Entry(root, width=15)
temp_entry.grid(row=0, column=1, padx=5, pady=5)
temp_entry.insert(0, "25.0") 

tk.Label(root, text="SET HUMI (%):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
humi_entry = tk.Entry(root, width=15)
humi_entry.grid(row=1, column=1, padx=5, pady=5)
humi_entry.insert(0, "60") 

start_button = tk.Button(root, text="START CONTROL", command=start_control, font=("Arial", 10, "bold"))
start_button.grid(row=2, columnspan=2, pady=10)

# --- 현재 센서 데이터 및 LED 상태 섹션 ---
tk.Label(root, text="CURRENT TEMP:").grid(row=3, column=0, padx=5, pady=2, sticky='w')
current_temp_label = tk.Label(root, text="--", font=("Arial", 14, "bold"), fg="darkgreen", relief="solid", borderwidth=1, width=12)
current_temp_label.grid(row=3, column=1, padx=5, pady=2, sticky='ew')

tk.Label(root, text="TEMP LED (D1-D4) Status:").grid(row=4, column=0, padx=5, pady=2, sticky='w') 
relay1_status_label = tk.Label(root, text="--", font=("Arial", 10), fg="red") 
relay1_status_label.grid(row=4, column=1, padx=5, pady=2, sticky='ew')

tk.Label(root, text="CURRENT HUMI:").grid(row=5, column=0, padx=5, pady=2, sticky='w')
current_humi_label = tk.Label(root, text="--", font=("Arial", 14, "bold"), fg="darkblue", relief="solid", borderwidth=1, width=12)
current_humi_label.grid(row=5, column=1, padx=5, pady=2, sticky='ew')

tk.Label(root, text="HUMI LED (D5-D8) Status:").grid(row=6, column=0, padx=5, pady=2, sticky='w') 
relay2_status_label = tk.Label(root, text="--", font=("Arial", 10), fg="blue") 
relay2_status_label.grid(row=6, column=1, padx=5, pady=2, sticky='ew')

# --- 웹 UI 정보 표시 섹션 ---
web_info_label = tk.Label(root, text="Web UI will be available after start.", font=("Arial", 9), fg="gray")
web_info_label.grid(row=7, columnspan=2, pady=(10, 0))

# --- 종료 버튼 ---
exit_button = tk.Button(root, text="EXIT", command=on_closing, font=("Arial", 10, "bold"), fg="white", bg="red")
exit_button.grid(row=8, columnspan=2, pady=10) 

# --- GUI 시작 ---
root.mainloop()
