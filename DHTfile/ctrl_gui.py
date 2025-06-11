import tkinter as tk
import subprocess
import threading
import time

# 초기값 설정 (global variables to store thresholds)
temp_threshold = 0.0
humi_threshold = 0

def start_control():
    global temp_threshold, humi_threshold
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
        relay1_status_label.config(text="Relay 1: Initializing...")
        relay2_status_label.config(text="Relay 2: Initializing...")

        # 백그라운드에서 주기적으로 데이터 갱신
        threading.Thread(target=update_sensor_data, daemon=True).start()
    except ValueError:
        current_temp_label.config(text="ERROR")
        current_humi_label.config(text="ERROR")
        relay1_status_label.config(text="Relay 1: Invalid Input")
        relay2_status_label.config(text="Relay 2: Invalid Input")

def update_sensor_data():
    while True:
        # Execute the C program with thresholds
        # C program will output in a specific format for parsing:
        # Line 1: "Temp: XX.X C, Humi: YY.Y %"
        # Line 2: "R1: ON/OFF, R2: ON/OFF" (Optional, as relay status is also in line1)
        # Line 3: "FPGA_LCD_L1: <text for line 1>"
        # Line 4: "FPGA_LCD_L2: <text for line 2>"
        process = subprocess.run(["./dht_1", str(temp_threshold), str(humi_threshold)], capture_output=True, text=True)
        output = process.stdout.strip()
        
        if output:
            lines = output.split("\n")
            
            # Ensure we have enough lines for parsing
            if len(lines) >= 4: # Expected: Current Data, Relay Status, LCD Line 1, LCD Line 2
                
                # Parse current temp and humi
                data_line = lines[0] # "Temp: XX.X C, Humi: YY.Y %"
                try:
                    temp_str = data_line.split("Temp: ")[1].split(" C")[0]
                    humi_str = data_line.split("Humi: ")[1].split(" %")[0]
                    current_temp_label.config(text=f"{temp_str}°C")
                    current_humi_label.config(text=f"{humi_str}%")
                except IndexError:
                    current_temp_label.config(text="Temp: N/A")
                    current_humi_label.config(text="Humi: N/A")

                # Parse relay status
                relay_status_line = lines[1] # "R1: ON/OFF, R2: ON/OFF"
                try:
                    relay1_stat = relay_status_line.split("R1: ")[1].split(",")[0].strip()
                    relay2_stat = relay_status_line.split("R2: ")[1].strip()
                    relay1_status_label.config(text=f"TEMP RELAY: {relay1_stat}")
                    relay2_status_label.config(text=f"HUMI RELAY: {relay2_stat}")
                except IndexError:
                    relay1_status_label.config(text="Relay 1: N/A")
                    relay2_status_label.config(text="Relay 2: N/A")

                # Parse FPGA LCD lines for display in GUI
                fpga_lcd_line1 = lines[2].replace("FPGA_LCD_L1: ", "").strip()
                fpga_lcd_line2 = lines[3].replace("FPGA_LCD_L2: ", "").strip()
                fpga_lcd_display_label.config(text=f"{fpga_lcd_line1}\n{fpga_lcd_line2}")

            else: # Not enough lines, possibly an error or initial state
                current_temp_label.config(text="N/A")
                current_humi_label.config(text="N/A")
                relay1_status_label.config(text="Relay 1: Waiting...")
                relay2_status_label.config(text="Relay 2: Waiting...")
                fpga_lcd_display_label.config(text="Waiting for data...\n") # Display partial or waiting message
        else: # No output from C program
            current_temp_label.config(text="No Data")
            current_humi_label.config(text="No Data")
            relay1_status_label.config(text="Relay 1: No Data")
            relay2_status_label.config(text="Relay 2: No Data")
            fpga_lcd_display_label.config(text="No C program output\n")

        time.sleep(2)  # 2초마다 센서 갱신

# GUI 생성
root = tk.Tk()
root.title("DHT22 & Relay Control")

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
