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
# Global variables for raw LCD output mirroring
last_fpga_lcd_line1_raw = "Waiting for data"
last_fpga_lcd_line2_raw = "Connecting..."


def start_control():
    global temp_threshold, humi_threshold, dht_process, \
           last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat, \
           last_fpga_lcd_line1_raw, last_fpga_lcd_line2_raw
    
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
        
        # Initial display updates - use current last_X values (which are defaults at start)
        current_temp_label.config(text=f"{last_temp_val}°C")
        current_humi_label.config(text=f"{last_humi_val}%")
        relay1_status_label.config(text=f"TEMP RELAY: {last_relay1_stat}")
        relay2_status_label.config(text=f"HUMI RELAY: {last_relay2_stat}")
        fpga_lcd_display_label.config(text=f"{last_fpga_lcd_line1_raw}\n{last_fpga_lcd_line2_raw}")

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
        fpga_lcd_display_label.config(text="Invalid input values.\n")
    except FileNotFoundError:
        current_temp_label.config(text="FILE ERROR")
        current_humi_label.config(text="FILE ERROR")
        relay1_status_label.config(text="TEMP RELAY: N/A")
        relay2_status_label.config(text="HUMI RELAY: N/A")
        fpga_lcd_display_label.config(text="Error: dht_1 program not found.\nPlease compile dht_1.c\n")
    except Exception as e:
        print(f"An unexpected error occurred in start_control: {e}")
        current_temp_label.config(text="SYS ERROR")
        current_humi_label.config(text="SYS ERROR")
        fpga_lcd_display_label.config(text=f"Unexpected Error:\n{e}")


def update_sensor_data():
    global dht_process, last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat, \
           last_fpga_lcd_line1_raw, last_fpga_lcd_line2_raw
    
    while True:
        if dht_process and dht_process.poll() is None: # Check if C program is still running
            # We expect two lines from C: "FPGA_LCD_L1:..." and "FPGA_LCD_L2:..."
            current_raw_line1 = None
            current_raw_line2 = None
            
            # Read lines until we get both LCD lines or timeout
            start_read_time = time.time()
            while time.time() - start_read_time < 5: # Give C program enough time (4s loop + buffer)
                line = dht_process.stdout.readline()
                if line:
                    line = line.strip()
                    if line.startswith("FPGA_LCD_L1:"):
                        current_raw_line1 = line.replace("FPGA_LCD_L1:", "").strip()
                    elif line.startswith("FPGA_LCD_L2:"):
                        current_raw_line2 = line.replace("FPGA_LCD_L2:", "").strip()
                    
                    if current_raw_line1 is not None and current_raw_line2 is not None:
                        break # Got both lines, stop reading for this cycle
                else:
                    time.sleep(0.05) # Small delay to avoid busy-waiting

            # --- Parse and update individual GUI labels ---
            temp_parsed_successfully = False
            humi_parsed_successfully = False
            relay1_parsed_successfully = False
            relay2_parsed_successfully = False

            if current_raw_line1:
                # Regex to extract Temperature and Relay1 status from "Temp:XX.XC ON/OFF"
                match_temp = re.match(r"Temp:(\d+\.?\d*)C\s*(ON|OFF)", current_raw_line1)
                if match_temp:
                    last_temp_val = match_temp.group(1)
                    last_relay1_stat = match_temp.group(2)
                    temp_parsed_successfully = True
                    relay1_parsed_successfully = True

            if current_raw_line2:
                # Regex to extract Humidity and Relay2 status from "Humi:XX.X% ON/OFF"
                match_humi = re.match(r"Humi:(\d+\.?\d*)%%\s*(ON|OFF)", current_raw_line2)
                if match_humi:
                    last_humi_val = match_humi.group(1)
                    last_relay2_stat = match_humi.group(2)
                    humi_parsed_successfully = True
                    relay2_parsed_successfully = True

            # Update GUI labels with last valid values
            current_temp_label.config(text=f"{last_temp_val}°C")
            current_humi_label.config(text=f"{last_humi_val}%")
            relay1_status_label.config(text=f"TEMP RELAY: {last_relay1_stat}")
            relay2_status_label.config(text=f"HUMI RELAY: {last_relay2_stat}")

            # Update raw LCD mirroring label (always use the latest raw lines received)
            if current_raw_line1 is not None and current_raw_line2 is not None:
                last_fpga_lcd_line1_raw = current_raw_line1
                last_fpga_lcd_line2_raw = current_raw_line2
            
            fpga_lcd_display_label.config(text=f"{last_fpga_lcd_line1_raw}\n{last_fpga_lcd_line2_raw}")
            
            # Check for any error output from C program's stderr (for debugging)
            stderr_output = dht_process.stderr.read()
            if stderr_output:
                print(f"C Program Stderr: {stderr_output.strip()}")

        else: # C program has ended or failed to start
            current_temp_label.config(text="C Program Ended")
            current_humi_label.config(text="C Program Ended")
            relay1_status_label.config(text="TEMP RELAY: Ended")
            relay2_status_label.config(text="HUMI RELAY: Ended")
            fpga_lcd_display_label.config(text="C Program has ended.\nRestart control.")
            print("C program process ended. Exiting update thread.")
            break # Exit the update loop

        # C program updates every 4 seconds, GUI checks every 1 second
        # This loop continues even if C program output is not parsed,
        # displaying the last known good values.
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

# --- FPGA TEXT LCD Content Mirroring Section ---
# This label will show the exact 2 lines currently on the FPGA LCD
tk.Label(root, text="FPGA LCD Output:").grid(row=7, column=0, padx=5, pady=5, sticky='w')
fpga_lcd_display_label = tk.Label(root, text="Line 1\nLine 2", font=("Courier New", 12), fg="blue", justify=tk.LEFT, relief="groove", borderwidth=2, width=20, height=2)
fpga_lcd_display_label.grid(row=7, column=1, padx=5, pady=5, sticky='ew')

# Start the Tkinter event loop
root.mainloop()
