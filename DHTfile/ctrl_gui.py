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


def update_sensor_data():
    global dht_process, last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat
    
    # Regex pattern to parse the C program's output
    # Example: "Humidity = 55.0 % (Relay: ON) Temperature = 25.1 *C (Relay: OFF)"
    pattern = re.compile(r"Humidity = (\d+\.?\d*)\s*%\s*\(Relay:\s*(ON|OFF)\)\s*Temperature = (\d+\.?\d*)\s*\*C\s*\(Relay:\s*(ON|OFF)\)")

    while True:
        if dht_process and dht_process.poll() is None: # Check if C program is still running
            line = dht_process.stdout.readline()
            if line:
                line = line.strip()
                match = pattern.match(line)
                if match:
                    # Successfully parsed the line
                    last_humi_val = match.group(1)
                    last_relay2_stat = match.group(2)
                    last_temp_val = match.group(3)
                    last_relay1_stat = match.group(4)
                # Else: if parsing fails (e.g., "N/A" during startup or error),
                # last_temp_val etc. retain their previous values.

                # Update GUI labels with last valid values
                current_temp_label.config(text=f"{last_temp_val}°C")
                current_humi_label.config(text=f"{last_humi_val}%")
                relay1_status_label.config(text=f"TEMP RELAY: {last_relay1_stat}")
                relay2_status_label.config(text=f"HUMI RELAY: {last_relay2_stat}")
            
            # Check for any error output from C program's stderr (for debugging)
            stderr_output = dht_process.stderr.read()
            if stderr_output:
                print(f"C Program Stderr: {stderr_output.strip()}")

        else: # C program has ended or failed to start
            current_temp_label.config(text="C Program Ended")
            current_humi_label.config(text="C Program Ended")
            relay1_status_label.config(text="TEMP RELAY: Ended")
            relay2_status_label.config(text="HUMI RELAY: Ended")
            print("C program process ended. Exiting update thread.")
            break # Exit the update loop

        # C program updates every 4 seconds, GUI checks every 1 second
        time.sleep(1) 


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

# This label will now act as a general status or last C program message, if needed
# If you explicitly want to see the *raw* LCD lines from C, we'd need another label.
# Based on "네모 칸 안에" 요청, this setup is more appropriate.
# tk.Label(root, text="LAST MSG:").grid(row=7, column=0, padx=5, pady=5, sticky='w')
# result_label = tk.Label(root, text="READY", font=("Arial", 10), fg="purple")
# result_label.grid(row=7, column=1, padx=5, pady=5, sticky='ew')


# Start the Tkinter event loop
root.mainloop()
