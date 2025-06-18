import tkinter as tk
import subprocess
import threading
import os
import signal
import re

# 전역 변수 초기화
temp_threshold = 0.0
humi_threshold = 0
dht_process = None
last_temp_val = "--"
last_humi_val = "--"
last_relay1_stat = "--" # 이제 TEMP LED 상태를 나타냅니다.
last_relay2_stat = "--" # 이제 HUMI LED 상태를 나타냅니다.


def start_control():
    global temp_threshold, humi_threshold, dht_process, \
           last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat
    
    temp_str = temp_entry.get()
    humi_str = humi_entry.get()
    
    try:
        temp_threshold = float(temp_str)
        humi_threshold = int(humi_str)
        
        # 입력 필드 및 시작 버튼 비활성화
        temp_entry.config(state='disabled')
        humi_entry.config(state='disabled')
        start_button.config(state='disabled')
        
        # 초기 GUI 디스플레이 업데이트 (초기 값 또는 "N/A" 표시)
        current_temp_label.config(text=f"{last_temp_val}°C")
        current_humi_label.config(text=f"{last_humi_val}%")
        relay1_status_label.config(text=f"TEMP LED (D1-D4): {last_relay1_stat}") 
        relay2_status_label.config(text=f"HUMI LED (D5-D8): {last_relay2_stat}")

        # 기존 dht_process 종료 (새로운 프로세스 시작 전에)
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

        # C 프로그램 시작 (비동기 통신을 위해 Popen 사용)
        dht_process = subprocess.Popen(
            ["./dht_fpga", str(temp_threshold), str(humi_threshold)], # 파일명 변경 반영
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1, 
            preexec_fn=os.setsid 
        )
        print(f"Started dht_fpga with PID: {dht_process.pid}, PGID: {os.getpgid(dht_process.pid)}") # 파일명 변경 반영

        # 센서 데이터 업데이트를 위한 백그라운드 스레드 시작
        threading.Thread(target=update_sensor_data, daemon=True).start()

    except ValueError:
        current_temp_label.config(text="INPUT ERROR") 
        current_humi_label.config(text="INPUT ERROR") 
        relay1_status_label.config(text="TEMP LED (D1-D4): INVALID") 
        relay2_status_label.config(text="HUMI LED (D5-D8): INVALID") 
    except FileNotFoundError:
        current_temp_label.config(text="FILE ERROR") 
        current_humi_label.config(text="FILE ERROR") 
        relay1_status_label.config(text="TEMP LED (D1-D4): N/A") 
        relay2_status_label.config(text="HUMI LED (D5-D8): N/A") 
    except Exception as e:
        print(f"An unexpected error occurred in start_control: {e}") 
        current_temp_label.config(text="SYS ERROR") 
        current_humi_label.config(text="SYS ERROR") 


def update_sensor_data():
    global dht_process, last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat

    # 정규표현식에서 "Relay"를 "LED"로 변경
    pattern = re.compile(r"Humidity = (N/A|-?\d+\.?\d*)\s*%\s*\(LED:\s*(ON|OFF|N/A)\)\s*Temperature = (N/A|-?\d+\.?\d*)\s*\*C\s*\(LED:\s*(ON|OFF|N/A)\)")

    for line in iter(dht_process.stdout.readline, ''):
        line = line.strip()
        
        print(f"Received from C: '{line}'")

        if line:
            match = pattern.match(line)
            if match:
                print("DEBUG: Regex match success!") 
                last_humi_val = match.group(1)
                last_relay2_stat = match.group(2)
                last_temp_val = match.group(3)
                last_relay1_stat = match.group(4)

                # GUI 레이블 업데이트
                current_temp_label.config(text=f"{last_temp_val}°C")
                current_humi_label.config(text=f"{last_humi_val}%")
                relay1_status_label.config(text=f"TEMP LED (D1-D4): {last_relay1_stat}") 
                relay2_status_label.config(text=f"HUMI LED (D5-D8): {last_relay2_stat}") 
            else:
                print("DEBUG: Regex match failed.") 

    print("C program process ended. Exiting update thread.") 
    root.after(100, lambda: current_temp_label.config(text="C Program Ended")) 
    root.after(100, lambda: current_humi_label.config(text="C Program Ended")) 
    root.after(100, lambda: relay1_status_label.config(text="TEMP LED (D1-D4): Ended")) 
    root.after(100, lambda: relay2_status_label.config(text="HUMI LED (D5-D8): Ended")) 

def on_closing():
    global dht_process
    if dht_process and dht_process.poll() is None: 
        print("GUI closing. Sending SIGINT to dht_fpga process group...") # 파일명 변경 반영
        try:
            os.killpg(os.getpgid(dht_process.pid), signal.SIGINT)
            dht_process.wait(timeout=5) 
        except ProcessLookupError: 
            print("dht_fpga process already terminated or PID not found.") # 파일명 변경 반영
        except Exception as e:
            print(f"Error sending SIGINT or waiting for dht_fpga: {e}") # 파일명 변경 반영
    
    print("Destroying GUI...") 
    root.destroy() 

# 메인 GUI 창 생성
root = tk.Tk()
root.title("DHT22 & FPGA LED Control") 

# 창 닫기 이벤트 핸들러 등록
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
# 현재 온도 표시
tk.Label(root, text="CURRENT TEMP:").grid(row=3, column=0, padx=5, pady=2, sticky='w')
current_temp_label = tk.Label(root, text="--", font=("Arial", 14, "bold"), fg="darkgreen", relief="solid", borderwidth=1, width=12)
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

# --- 종료 버튼 추가 ---
exit_button = tk.Button(root, text="EXIT", command=on_closing, font=("Arial", 10, "bold"), fg="white", bg="red")
exit_button.grid(row=7, columnspan=2, pady=10) 

# 창 중앙 정렬
root.update_idletasks() 
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
window_width = root.winfo_width()
window_height = root.winfo_height()

x_coordinate = int((screen_width / 2) - (window_width / 2))
y_coordinate = int((screen_height / 2) - (window_height / 2))

root.geometry(f"+{x_coordinate}+{y_coordinate}")

# Tkinter 이벤트 루프 시작
root.mainloop()
