import tkinter as tk
import subprocess

def start_control():
    temp = temp_entry.get()
    humi = humi_entry.get()
    if temp.isdigit() and humi.isdigit():
        subprocess.run(["./dht_relay_1", temp, humi])  # 수정된 C 프로그램 실행
    else:
        result_label.config(text="숫자를 입력하세요!")

root = tk.Tk()
root.title("DHT22 릴레이 제어")

tk.Label(root, text="SET TEMP:").grid(row=0, column=0)
temp_entry = tk.Entry(root)
temp_entry.grid(row=0, column=1)

tk.Label(root, text="SET HUMI:").grid(row=1, column=0)
humi_entry = tk.Entry(root)
humi_entry.grid(row=1, column=1)

start_button = tk.Button(root, text="제어 시작", command=start_control)
start_button.grid(row=2, columnspan=2)

result_label = tk.Label(root, text="")
result_label.grid(row=3, columnspan=2)

root.mainloop()
