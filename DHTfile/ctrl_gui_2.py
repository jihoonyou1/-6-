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
last_relay1_stat = "--"
last_relay2_stat = "--"


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
        relay1_status_label.config(text=f"TEMP RELAY: {last_relay1_stat}")
        relay2_status_label.config(text=f"HUMI RELAY: {last_relay2_stat}")

        # 기존 dht_process 종료 (새로운 프로세스 시작 전에)
        if dht_process and dht_process.poll() is None:
            print("Terminating existing dht_1 process...") # 기존 dht_1 프로세스 종료 중...
            try:
                os.killpg(os.getpgid(dht_process.pid), signal.SIGTERM) # 우아한 종료 신호 전송
                dht_process.wait(timeout=2) # 종료될 때까지 대기
            except ProcessLookupError: # 프로세스가 이미 종료되었을 수 있음
                pass # 프로세스가 없어도 괜찮음
            if dht_process.poll() is None: # 아직 실행 중이면 강제 종료
                os.killpg(os.getpgid(dht_process.pid), signal.SIGKILL)
                dht_process.wait(timeout=1)
            dht_process = None # 이전 프로세스 참조 제거

        # C 프로그램 시작 (비동기 통신을 위해 Popen 사용)
        dht_process = subprocess.Popen(
            ["./dht_1", str(temp_threshold), str(humi_threshold)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1, # 라인 버퍼링된 출력
            preexec_fn=os.setsid # 프로세스 그룹에 신호 전송을 위해 중요
        )
        print(f"Started dht_1 with PID: {dht_process.pid}, PGID: {os.getpgid(dht_process.pid)}") # dht_1 시작. PID: {dht_process.pid}, PGID: {os.getpgid(dht_process.pid)}

        # 센서 데이터 업데이트를 위한 백그라운드 스레드 시작
        threading.Thread(target=update_sensor_data, daemon=True).start()

    except ValueError:
        current_temp_label.config(text="INPUT ERROR") # 입력 오류
        current_humi_label.config(text="INPUT ERROR") # 입력 오류
        relay1_status_label.config(text="TEMP RELAY: INVALID")
        relay2_status_label.config(text="HUMI RELAY: INVALID")
    except FileNotFoundError:
        current_temp_label.config(text="FILE ERROR") # 파일 오류
        current_humi_label.config(text="FILE ERROR") # 파일 오류
        relay1_status_label.config(text="TEMP RELAY: N/A")
        relay2_status_label.config(text="HUMI RELAY: N/A")
    except Exception as e:
        print(f"An unexpected error occurred in start_control: {e}") # start_control에서 예기치 않은 오류 발생: {e}
        current_temp_label.config(text="SYS ERROR") # 시스템 오류
        current_humi_label.config(text="SYS ERROR") # 시스템 오류


def update_sensor_data():
    global dht_process, last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat

    # 강력한 정규식 패턴은 그대로 사용합니다.
    pattern = re.compile(r"Humidity = (N/A|-?\d+\.?\d*)\s*%\s*\(Relay:\s*(ON|OFF|N/A)\)\s*Temperature = (N/A|-?\d+\.?\d*)\s*\*C\s*\(Relay:\s*(ON|OFF|N/A)\)")

    # stdout에서 한 줄씩 실시간으로 읽어오기 위한 안정적인 반복문입니다.
    # C 프로그램이 종료되어 빈 문자열('')을 보낼 때까지 계속 실행됩니다.
    for line in iter(dht_process.stdout.readline, ''):
        line = line.strip()
        
        # (디버깅용) C 프로그램에서 어떤 데이터가 넘어오는지 터미널에 출력합니다.
        print(f"Received from C: '{line}'")

        if line:
            match = pattern.match(line)
            if match:
                # 성공적으로 파싱한 경우
                print("DEBUG: Regex match success!") # 디버깅 메시지
                last_humi_val = match.group(1)
                last_relay2_stat = match.group(2)
                last_temp_val = match.group(3)
                last_relay1_stat = match.group(4)

                # GUI 레이블 업데이트
                current_temp_label.config(text=f"{last_temp_val}°C")
                current_humi_label.config(text=f"{last_humi_val}%")
                relay1_status_label.config(text=f"TEMP RELAY: {last_relay1_stat}")
                relay2_status_label.config(text=f"HUMI RELAY: {last_relay2_stat}")
            else:
                # 파싱에 실패한 경우
                print("DEBUG: Regex match failed.") # 디버깅 메시지

    # C 프로그램 프로세스가 종료되면 루프가 끝나고 아래 코드가 실행됩니다.
    print("C program process ended. Exiting update thread.") # C 프로그램 프로세스 종료. 업데이트 스레드 종료.
    root.after(100, lambda: current_temp_label.config(text="C Program Ended")) # C 프로그램 종료
    root.after(100, lambda: current_humi_label.config(text="C Program Ended")) # C 프로그램 종료
    root.after(100, lambda: relay1_status_label.config(text="TEMP RELAY: Ended")) # 종료
    root.after(100, lambda: relay2_status_label.config(text="HUMI RELAY: Ended")) # 종료

def on_closing():
    global dht_process
    if dht_process and dht_process.poll() is None: # C 프로그램이 아직 실행 중인지 확인
        print("GUI closing. Sending SIGINT to dht_1 process group...") # GUI 종료 중. dht_1 프로세스 그룹에 SIGINT 전송...
        try:
            # dht_1 프로세스 그룹에 SIGINT 전송
            os.killpg(os.getpgid(dht_process.pid), signal.SIGINT)
            dht_process.wait(timeout=5) # C 프로그램이 깨끗하게 종료될 때까지 대기
        except ProcessLookupError: # 프로세스가 이미 종료되었을 수 있음
            print("dht_1 process already terminated or PID not found.") # dht_1 프로세스가 이미 종료되었거나 PID를 찾을 수 없습니다.
        except Exception as e:
            print(f"Error sending SIGINT or waiting for dht_1: {e}") # dht_1에 SIGINT 전송 또는 대기 중 오류: {e}
    
    print("Destroying GUI...") # GUI 종료 중...
    root.destroy() # Tkinter GUI 창 종료

# 메인 GUI 창 생성
root = tk.Tk()
root.title("DHT22 & Relay Control")

# 창 닫기 이벤트 핸들러 등록
root.protocol("WM_DELETE_WINDOW", on_closing)

# --- 입력 / 설정 섹션 ---
tk.Label(root, text="SET TEMP (°C):").grid(row=0, column=0, padx=5, pady=5, sticky='w')
temp_entry = tk.Entry(root, width=15)
temp_entry.grid(row=0, column=1, padx=5, pady=5)
temp_entry.insert(0, "25.0") # 기본값

tk.Label(root, text="SET HUMI (%):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
humi_entry = tk.Entry(root, width=15)
humi_entry.grid(row=1, column=1, padx=5, pady=5)
humi_entry.insert(0, "60") # 기본값

start_button = tk.Button(root, text="START CONTROL", command=start_control, font=("Arial", 10, "bold"))
start_button.grid(row=2, columnspan=2, pady=10)

# --- 현재 센서 데이터 및 릴레이 상태 섹션 ---
# 현재 온도 표시
tk.Label(root, text="CURRENT TEMP:").grid(row=3, column=0, padx=5, pady=2, sticky='w')
current_temp_label = tk.Label(root, text="--", font=("Arial", 14, "bold"), fg="darkgreen", relief="solid", borderwidth=1, width=12)
current_temp_label.grid(row=3, column=1, padx=5, pady=2, sticky='ew')

# 온도 릴레이 상태
relay1_status_label = tk.Label(root, text="TEMP RELAY: --", font=("Arial", 10), fg="red")
relay1_status_label.grid(row=4, columnspan=2, padx=5, pady=2, sticky='w')

# 현재 습도 표시
tk.Label(root, text="CURRENT HUMI:").grid(row=5, column=0, padx=5, pady=2, sticky='w')
current_humi_label = tk.Label(root, text="--", font=("Arial", 14, "bold"), fg="darkgreen", relief="solid", borderwidth=1, width=12)
current_humi_label.grid(row=5, column=1, padx=5, pady=2, sticky='ew')

# 습도 릴레이 상태
relay2_status_label = tk.Label(root, text="HUMI RELAY: --", font=("Arial", 10), fg="red")
relay2_status_label.grid(row=6, columnspan=2, padx=5, pady=2, sticky='w')

# --- 종료 버튼 추가 ---
# 기존 레이블들 아래에 추가합니다.
exit_button = tk.Button(root, text="EXIT", command=on_closing, font=("Arial", 10, "bold"), fg="white", bg="red")
exit_button.grid(row=7, columnspan=2, pady=10) # row 번호를 기존 내용에 맞춰 조정

# 창 중앙 정렬
root.update_idletasks() # 위젯이 렌더링되고 크기가 결정되도록 강제
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
window_width = root.winfo_width()
window_height = root.winfo_height()

x_coordinate = int((screen_width / 2) - (window_width / 2))
y_coordinate = int((screen_height / 2) - (window_height / 2))

root.geometry(f"+{x_coordinate}+{y_coordinate}")

# Tkinter 이벤트 루프 시작
root.mainloop()