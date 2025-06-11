import tkinter as tk
import subprocess
import threading
import time

# Initialize global variables for thresholds
temp_threshold = 0.0
humi_threshold = 0

def start_control():
    global temp_threshold, humi_threshold
    temp = temp_entry.get()
    humi = humi_entry.get()
    try:
        temp_threshold = float(temp)
        humi_threshold = int(humi)
        result_label.config(text="READING SENSOR DATA...")
        status_label.config(text="STATUS: Relays Initializing...")
        
        # Disable input fields and start button after starting
        temp_entry.config(state='disabled')
        humi_entry.config(state='disabled')
        start_button.config(state='disabled')

        # Start data update in a background thread
        threading.Thread(target=update_sensor_data, daemon=True).start()
    except ValueError:
        result_label.config(text="WRONG INPUT: Please enter valid numbers.")
        status_label.config(text="STATUS: Error")

def update_sensor_data():
    while True:
        # Execute the C program with thresholds
        # Note: The C program now handles writing to FPGA_TEXT_LCD directly.
        # This Python script just receives the print output for its own GUI.
        process = subprocess.run(["./dht_1", str(temp_threshold), str(humi_threshold)], capture_output=True, text=True)
        output = process.stdout.strip()
        
        if output:
            lines = output.split("\n")
            # The last line printed by dht_1.c should contain the sensor data and relay status.
            # The C code now also writes to the FPGA LCD, so we parse the last output line for the GUI.
            if len(lines) > 1:
                sensor_data_line = lines[-1]
                try:
                    # Expected format: "Humidity = X.X % (Relay: Y) Temperature = Z.Z *C (Z.Z *F) (Relay: W)"
                    parts = sensor_data_line.split(" ")
                    humidity_value = parts[2]
                    humidity_relay_status = parts[5].replace(")", "")
                    temperature_value = parts[8]
                    temperature_relay_status = parts[13].replace(")", "") # Updated index due to F value

                    result_label.config(text=f"Humidity: {humidity_value}% Temp: {temperature_value}°C")
                    status_label.config(text=f"TEMP RELAY: {temperature_relay_status}, HUMI RELAY: {humidity_relay_status}")
                except IndexError:
                    result_label.config(text=f"Error parsing data: {sensor_data_line}")
                    status_label.config(text="STATUS: Data Parse Error")
            else: # Fallback for initial messages or errors from C program
                result_label.config(text=lines[-1])
                status_label.config(text="STATUS: Waiting for sensor data...")
        else:
            result_label.config(text="No data from sensor program.")
            status_label.config(text="STATUS: No Sensor Data")

        time.sleep(2)  # Update every 2 seconds

# Create GUI
root = tk.Tk()
root.title("DHT22 CTRL")

# Input fields
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

# Status and sensor data display
status_label = tk.Label(root, text="STATUS: Enter values and click START", font=("Arial", 10))
status_label.grid(row=3, columnspan=2, pady=5)

result_label = tk.Label(root, text="Current Sensor Data: --", font=("Arial", 12, "bold"), fg="blue")
result_label.grid(row=4, columnspan=2, pady=5)

root.mainloop()
