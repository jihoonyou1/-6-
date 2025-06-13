import tkinter as tk
import subprocess
import threading
import time
import os
import signal # For sending signals
import re # For regular expressions to parse strings

# Global variables for thresholds (initial values)
temp_threshold = 0.0
humi_threshold = 0

# Global variable to hold the C program's subprocess object
dht_process = None

# Global variables to store the last valid sensor data and relay states
# This is crucial for displaying "previous results" on sensor error
last_temp_val = "--"
last_humi_val = "--"
last_relay1_stat = "--"
last_relay2_stat = "--"


def start_control():
    global temp_threshold, humi_threshold, dht_process, \
           last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat
    
    # Get threshold values from entry fields
    temp_str = temp_entry.get()
    humi_str = humi_entry.get()
    
    try:
        temp_threshold = float(temp_str)
        humi_threshold = int(humi_str)
        
        # Disable input fields and start button after starting
        temp_entry.config(state='disabled')
        humi_entry.config(state='disabled')
        start_button.config(state='disabled')
        
        # Initial display updates with default values or "N/A"
        current_temp_label.config(text=f"{last_temp_val}°C")
        current_humi_label.config(text=f"{last_humi_val}%")
        relay1_status_label.config(text=f"TEMP RELAY: {last_relay1_stat}")
        relay2_status_label.config(text=f"HUMI RELAY: {last_relay2_stat}")

        # Terminate any existing dht_process before starting a new one
        if dht_process and dht_process.poll() is None:
            print("Terminating existing dht_1 process...")
            try:
                os.killpg(os.getpgid(dht_process.pid), signal.SIGTERM) # Send graceful termination
                dht_process.wait(timeout=2) # Wait for it to terminate
            except ProcessLookupError: # Process might have already died
                pass # It's okay if process is already gone
            if dht_process.poll() is None: # If still running, force kill
                os.killpg(os.getpgid(dht_process.pid), signal.SIGKILL)
                dht_process.wait(timeout=1)
            dht_process = None # Clear the old process reference

        # Start the C program using Popen for asynchronous communication
        dht_process = subprocess.Popen(
            ["./dht_1", str(temp_threshold), str(humi_threshold)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1, # Line-buffered output
            preexec_fn=os.setsid # Crucial for sending signals to the process group
        )
        print(f"Started dht_1 with PID: {dht_process.pid}, PGID: {os.getpgid(dht_process.pid)}")

        # Start a background thread to update sensor data
        threading.Thread(target=update_sensor_data, daemon=True).start()

    except ValueError:
        current_temp_label.config(text="INPUT ERROR")
        current_humi_label.config(text="INPUT ERROR")
        relay1_status_label.config(text="TEMP RELAY: INVALID")
        relay2_status_label.config(text="HUMI RELAY: INVALID")
    except FileNotFoundError:
        current_temp_label.config(text="FILE ERROR")
        current_humi_label.config(text="FILE ERROR")
        relay1_status_label.config(text="TEMP RELAY: N/A")
        relay2_status_label.config(text="HUMI RELAY: N/A")
    except Exception as e:
        print(f"An unexpected error occurred in start_control: {e}")
        current_temp_label.config(text="SYS ERROR")
        current_humi_label.config(text="SYS ERROR")


# ctrl_gui.py 파일

# threading, re, time 등 다른 import 구문들은 그대로 둡니다.

def update_sensor_data():
    global dht_process, last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat

    # 이전 단계에서 수정한 강력한 정규식 패턴은 그대로 사용합니다.
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
    print("C program process ended. Exiting update thread.")
    root.after(100, lambda: current_temp_label.config(text="C Program Ended"))
    root.after(100, lambda: current_humi_label.config(text="C Program Ended"))
    root.after(100, lambda: relay1_status_label.config(text="TEMP RELAY: Ended"))
    root.after(100, lambda: relay2_status_label.config(text="HUMI RELAY: Ended"))
# GUI window closing event handler
def on_closing():
    global dht_process
    if dht_process and dht_process.poll() is None: # Check if C program is still running
        print("GUI closing. Sending SIGINT to dht_1 process group...")
        try:
            # Send SIGINT to the process group of dht_1
            os.killpg(os.getpgid(dht_process.pid), signal.SIGINT)
            dht_process.wait(timeout=5) # Wait for C program to terminate cleanly
        except ProcessLookupError: # Process might have already died
            print("dht_1 process already terminated or PID not found.")
        except Exception as e:
            print(f"Error sending SIGINT or waiting for dht_1: {e}")
    
    print("Destroying GUI...")
    root.destroy() # Destroy the Tkinter GUI window

# Create main GUI window
root = tk.Tk()
root.title("DHT22 & Relay Control")

# Register the on_closing function to be called when the window is closed
root.protocol("WM_DELETE_WINDOW", on_closing)

# --- Input / Settings Section ---
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

# --- Current Sensor Data and Relay Status Section ---
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

# --- Add an EXIT button ---
# 기존 레이블들 아래에 추가합니다.
exit_button = tk.Button(root, text="EXIT", command=on_closing, font=("Arial", 10, "bold"), fg="white", bg="red")
exit_button.grid(row=7, columnspan=2, pady=10) # row 번호를 기존 내용에 맞춰 조정

# Start the Tkinter event loop
root.mainloop()