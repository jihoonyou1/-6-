import tkinter as tk
import subprocess
import threading
import time
import os
import signal # For sending signals

# 초기값 설정 (global variables to store thresholds)
temp_threshold = 0.0
humi_threshold = 0

# C 프로그램 프로세스를 저장할 전역 변수
dht_process = None

def start_control():
    global temp_threshold, humi_threshold, dht_process
    temp = temp_entry.get()
    humi = humi_entry.get()
    try:
        temp_threshold = float(temp)
        humi_threshold = int(humi)
        
        # Disable input fields and start button after starting
        temp_entry.config(state='disabled')
        humi_entry.config(state='disabled')
        start_button.config(state='disabled')
        
        # Initial display setup
        current_temp_label.config(text="Reading...")
        current_humi_label.config(text="Reading...")
        relay1_status_label.config(text="TEMP RELAY: Initializing...")
        relay2_status_label.config(text="HUMI RELAY: Initializing...")
        fpga_lcd_display_label.config(text="Starting C program...\n")

        # Start data update in a background thread
        # dht_process를 직접 시작하고 관리하여 종료 시그널을 보낼 수 있도록 합니다.
        dht_process = subprocess.Popen(
            ["./dht_1", str(temp_threshold), str(humi_threshold)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1, # Line-buffered output
            preexec_fn=os.setsid # 새로운 세션 리더로 시작하여 프로세스 그룹 ID를 PID와 동일하게 설정 (SIGINT 전송 위함)
        )
        threading.Thread(target=update_sensor_data, daemon=True).start()

    except ValueError:
        current_temp_label.config(text="ERROR")
        current_humi_label.config(text="ERROR")
        relay1_status_label.config(text="TEMP RELAY: Invalid Input")
        relay2_status_label.config(text="HUMI RELAY: Invalid Input")
        fpga_lcd_display_label.config(text="Invalid input values.\n")
    except FileNotFoundError:
        current_temp_label.config(text="ERROR")
        current_humi_label.config(text="ERROR")
        relay1_status_label.config(text="TEMP RELAY: N/A")
        relay2_status_label.config(text="HUMI RELAY: N/A")
        fpga_lcd_display_label.config(text="Error: dht_1 program not found.\nPlease compile dht_1.c\n")
        
def update_sensor_data():
    global dht_process
    while True:
        if dht_process and dht_process.poll() is None: # Process is still running
            # Read all available lines from stdout for this cycle
            # This is more robust as it doesn't assume fixed line numbers for each readline call
            all_lines = []
            start_time = time.time()
            while time.time() - start_time < 2.5: # Try to read for a bit longer than C program's delay
                line = dht_process.stdout.readline()
                if line:
                    all_lines.append(line.strip())
                    if "FPGA_LCD_L2:" in line: # Assuming this is the last line of a data block
                        break
                else: # No new line immediately, wait a bit
                    time.sleep(0.1)
                
            if len(all_lines) >= 4: # Expected: Current Data, Relay Status, LCD Line 1, LCD Line 2
                
                # Find specific lines based on content prefixes
                data_line = ""
                relay_status_line = ""
                fpga_lcd_line1 = ""
                fpga_lcd_line2 = ""

                for line in all_lines:
                    if line.startswith("Temp: ") and "Humi:" in line:
                        data_line = line
                    elif line.startswith("R1: ") and "R2:" in line:
                        relay_status_line = line
                    elif line.startswith("FPGA_LCD_L1: "):
                        fpga_lcd_line1 = line.replace("FPGA_LCD_L1: ", "").strip()
                    elif line.startswith("FPGA_LCD_L2: "):
                        fpga_lcd_line2 = line.replace("FPGA_LCD_L2: ", "").strip()

                # Parse current temp and humi
                if data_line:
                    try:
                        temp_str = data_line.split("Temp: ")[1].split(" C")[0]
                        humi_str = data_line.split("Humi: ")[1].split(" %")[0]
                        current_temp_label.config(text=f"{temp_str}°C")
                        current_humi_label.config(text=f"{humi_str}%")
                    except IndexError:
                        current_temp_label.config(text="Temp: N/A")
                        current_humi_label.config(text="Humi: N/A")
                else:
                    current_temp_label.config(text="Temp: No Data")
                    current_humi_label.config(text="Humi: No Data")

                # Parse relay status
                if relay_status_line:
                    try:
                        relay1_stat = relay_status_line.split("R1: ")[1].split(",")[0].strip()
                        relay2_stat = relay_status_line.split("R2: ")[1].strip()
                        relay1_status_label.config(text=f"TEMP RELAY: {relay1_stat}")
                        relay2_status_label.config(text=f"HUMI RELAY: {relay2_stat}")
                    except IndexError:
                        relay1_status_label.config(text="TEMP RELAY: N/A")
                        relay2_status_label.config(text="HUMI RELAY: N/A")
                else:
                    relay1_status_label.config(text="TEMP RELAY: No Data")
                    relay2_status_label.config(text="HUMI RELAY: No Data")

                # Update FPGA LCD lines for display in GUI
                if fpga_lcd_line1 and fpga_lcd_line2:
                    fpga_lcd_display_label.config(text=f"{fpga_lcd_line1}\n{fpga_lcd_line2}")
                else:
                    fpga_lcd_display_label.config(text="LCD data not found\n")
            else: # Not enough lines or no expected content
                current_temp_label.config(text="N/A")
                current_humi_label.config(text="N/A")
                relay1_status_label.config(text="TEMP RELAY: Waiting...")
                relay2_status_label.config(text="HUMI RELAY: Waiting...")
                fpga_lcd_display_label.config(text="\n".join(all_lines) + "\nWaiting for data...") 
        else: # C program is not running
            current_temp_label.config(text="C Program Not Running")
            current_humi_label.config(text="C Program Not Running")
            relay1_status_label.config(text="TEMP RELAY: Not Running")
            relay2_status_label.config(text="HUMI RELAY: Not Running")
            fpga_lcd_display_label.config(text="C Program has ended or failed to start.\n")
            break # Exit loop if C program is not running

        time.sleep(1) # 1초마다 C 프로그램 출력 확인 (C 프로그램은 2초마다 출력하므로 1초로 설정)

# GUI 창 닫기 이벤트 핸들러
def on_closing():
    global dht_process
    if dht_process and dht_process.poll() is None:
        print("GUI closing. Sending SIGINT to dht_1 process group...")
        os.killpg(os.getpgid(dht_process.pid), signal.SIGINT)
        dht_process.wait(timeout=5) # C 프로그램이 종료될 때까지 최대 5초 대기
    
    print("Destroying GUI...")
    root.destroy() # Tkinter GUI 종료

# GUI 생성
root = tk.Tk()
root.title("DHT22 & Relay Control")

# GUI 창 닫기 이벤트를 on_closing 함수에 연결
root.protocol("WM_DELETE_WINDOW", on_closing)

# --- 설정값 입력 섹션 ---
tk.Label(root, text="SET TEMP (°C):").grid(row=0, column=0, padx=5, pady=5, sticky='w')
temp_entry = tk.Entry(root, width=15)
temp_entry.grid(row=0, column=1, padx=5, pady=5)
temp_entry.insert(0, "25.0") # Default value

tk.Label(root, text="SET HUMI (%):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
humi_entry = tk.Entry(root, width=15)
humi_entry.grid(row=1, column=1, padx=5, pady=5)
humi_entry.insert(0, "60") # Default value

start_button = tk.Button(root, text="START CONTROL", command=start_control, font=("Arial", 10, "bold"))
start_button.grid(row=2, columnspan=2, pady=10)

# --- 현재 온습도 및 릴레이 상태 섹션 ---
# Current Temperature Display
tk.Label(root, text="CURRENT TEMP:").grid(row=3, column=0, padx=5, pady=2, sticky='w')
current_temp_label = tk.Label(root, text="--", font=("Arial", 14, "bold"), fg="darkgreen", relief="solid", borderwidth=1, width=12)
current_temp_label.grid(row=3, column=1, padx=5, pady=2, sticky='ew')

# Temperature Relay Status
relay1_status_label = tk.Label(root, text="TEMP RELAY: --", font=("Arial", 10), fg="red")
relay1_status_label.grid(row=4, columnspan=2, padx=5, pady=2, sticky='w')

# Current Humidity Display
tk.Label(root, text="CURRENT HUMI:").grid(row=5, column=0, padx=5, pady=2, sticky='w')
current_humi_label = tk.Label(root, text="--", font=("Arial", 14, "bold"), fg="darkgreen", relief="solid", borderwidth=1, width=12)
current_humi_label.grid(row=5, column=1, padx=5, pady=2, sticky='ew')

# Humidity Relay Status
relay2_status_label = tk.Label(root, text="HUMI RELAY: --", font=("Arial", 10), fg="red")
relay2_status_label.grid(row=6, columnspan=2, padx=5, pady=2, sticky='w')

# --- FPGA TEXT LCD 내용 미러링 섹션 ---
tk.Label(root, text="FPGA LCD Output:").grid(row=7, column=0, padx=5, pady=5, sticky='w')
fpga_lcd_display_label = tk.Label(root, text="Line 1\nLine 2", font=("Courier New", 12), fg="blue", justify=tk.LEFT, relief="groove", borderwidth=2, width=20, height=2)
fpga_lcd_display_label.grid(row=7, column=1, padx=5, pady=5, sticky='ew')

root.mainloop()
