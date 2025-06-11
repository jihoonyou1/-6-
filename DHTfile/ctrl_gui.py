import tkinter as tk
import subprocess
import threading
import time

# 초기값 설정
temp_threshold = 0.0
humi_threshold = 0

def start_control():
    global temp_threshold, humi_threshold
    temp = temp_entry.get()
    humi = humi_entry.get()
    try:
        temp_threshold = float(temp)  # 실수형 변환
        humi_threshold = int(humi)
        result_label.config(text="READ DATA")
        
        # 백그라운드에서 주기적으로 데이터 갱신
        threading.Thread(target=update_sensor_data, daemon=True).start()
    except ValueError:
        result_label.config(text="WRONG INPUT")

def update_sensor_data():
    while True:
        process = subprocess.run(["./dht_1", str(temp_threshold), str(humi_threshold)], capture_output=True, text=True)
        output = process.stdout.strip().split("\n")
        if output:
            result_label.config(text=output[-1])  # 마지막 출력값을 GUI에 표시
        time.sleep(4)  # 4초마다 센서 갱신

# GUI 생성
root = tk.Tk()
root.title("DHT22 CTRL")

# 설정값 고정 표시
tk.Label(root, text="SET TEMP (°C):").grid(row=0, column=0)
temp_entry = tk.Entry(root)
temp_entry.grid(row=0, column=1)

tk.Label(root, text="SET HUMI (%):").grid(row=1, column=0)
humi_entry = tk.Entry(root)
humi_entry.grid(row=1, column=1)

start_button = tk.Button(root, text="START", command=start_control)
start_button.grid(row=2, columnspan=2)

# 릴레이 상태 및 센서 데이터 표시
status_label = tk.Label(root, text="STATUS")
status_label.grid(row=3, columnspan=2)

result_label = tk.Label(root, text="", font=("Arial", 12))
result_label.grid(row=4, columnspan=2)

root.mainloop()
