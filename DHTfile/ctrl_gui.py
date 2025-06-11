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
        process = subprocess.run(["./dht_1", str(temp_threshold), str(humi_threshold)], capture_output=True, text=True)
        output = process.stdout.strip()
        
        if output:
            lines = output.split("\n")
            
            # The C program now prints the GUI line, then the two LCD lines.
            # We need to extract the relevant lines.
            if len(lines) >= 3: # Expect at least 3 lines: sensor_data_line, LCD_line1, LCD_line2
                sensor_data_line = lines[-3] # Original sensor and relay status line
                lcd_line1 = lines[-2].strip() # First line for LCD
                lcd_line2 = lines[-1].strip() # Second line for LCD

                try:
                    # Parse the original sensor data and relay status for the status_label
                    parts = sensor_data_line.split(" ")
                    humidity_relay_status = parts[5].replace(")", "")
                    temperature_relay_status = parts[13].replace(")", "") # Updated index due to F value

                    status_label.config(text=f"TEMP RELAY: {temperature_relay_status}, HUMI RELAY: {humidity_relay_status}")
                    # Display the exact LCD content in result_label
                    result_label.config(text=f"{lcd_line1}\n{lcd_line2}")

                except IndexError:
                    result_label.config(text=f"Error parsing data: {sensor_data_line}\nCannot read LCD data.")
                    status_label.config(text="STATUS: Data Parse Error")
            else: # Fallback for initial messages or incomplete output
                result_label.config(text="\n".join(lines) + "\nWaiting for sensor data...") 
                status_label.config(text="STATUS: Waiting for full sensor data...")
        else: # No output from C program (e.g., C program failed or sensor error without output)
            result_label.config(text="No data from sensor program. Check sensor/C program.")
            status_label.config(text="STATUS: No Sensor Data or Error")

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

# result_label to display LCD content
result_label = tk.Label(root, text="Current Sensor Data: --\n--", font=("Arial", 12, "bold"), fg="blue", justify=tk.LEFT)
result_label.grid(row=4, columnspan=2, pady=5)

root.mainloop()
