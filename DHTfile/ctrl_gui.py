import tkinter as tk
import subprocess
import threading
import time
import os
import signal # For sending signals

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
last_fpga_lcd_line1 = "Waiting for data..."
last_fpga_lcd_line2 = ""


def start_control():
    global temp_threshold, humi_threshold, dht_process, \
           last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat, \
           last_fpga_lcd_line1, last_fpga_lcd_line2
    
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
        
        # Initial display updates
        # Display the 'last known' values, which are initial '--' at start
        current_temp_label.config(text=f"{last_temp_val}°C")
        current_humi_label.config(text=f"{last_humi_val}%")
        relay1_status_label.config(text=f"TEMP RELAY: {last_relay1_stat}")
        relay2_status_label.config(text=f"HUMI RELAY: {last_relay2_stat}")
        fpga_lcd_display_label.config(text=f"{last_fpga_lcd_line1}\n{last_fpga_lcd_line2}")

        # Terminate any existing dht_process before starting a new one
        if dht_process and dht_process.poll() is None:
            print("Terminating existing dht_1 process...")
            os.killpg(os.getpgid(dht_process.pid), signal.SIGTERM) # Send graceful termination
            dht_process.wait(timeout=2) # Wait for it to terminate
            if dht_process.poll() is None: # If still running, force kill
                os.killpg(os.getpgid(dht_process.pid), signal.SIGKILL)
                dht_process.wait(timeout=1)
            dht_process = None # Clear the old process reference

        # Start the C program using Popen for asynchronous communication
        # preexec_fn=os.setsid makes the C program a process group leader.
        # This allows sending signals to its entire process group (including itself).
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
    except Exception as e:
        print(f"An unexpected error occurred in start_control: {e}")
        current_temp_label.config(text="SYSTEM ERROR")
        current_humi_label.config(text="SYSTEM ERROR")


def update_sensor_data():
    global dht_process, last_temp_val, last_humi_val, last_relay1_stat, last_relay2_stat, \
           last_fpga_lcd_line1, last_fpga_lcd_line2
    
    while True:
        if dht_process and dht_process.poll() is None: # Check if C program is still running
            all_lines = []
            # Read multiple lines in a short burst, expecting the 4 lines of output
            # C program outputs every 2 seconds, so we try to read for a bit longer.
            start_read_time = time.time()
            # Read up to 4 lines or until a timeout/EOF
            for _ in range(4): # Expecting 4 lines
                line = dht_process.stdout.readline()
                if line:
                    all_lines.append(line.strip())
                else:
                    break # EOF or no more lines

            # Attempt to parse
            temp_parsed = False
            humi_parsed = False
            relay_parsed = False
            lcd1_parsed = False
            lcd2_parsed = False

            # Initialize temporary variables for current read
            current_temp = None
            current_humi = None
            current_relay1 = None
            current_relay2 = None
            current_lcd1 = None
            current_lcd2 = None
            
            for line in all_lines:
                if line.startswith("Temp: ") and "Humi:" in line:
                    try:
                        current_temp = line.split("Temp: ")[1].split(" C")[0]
                        current_humi = line.split("Humi: ")[1].split(" %")[0]
                        temp_parsed = True
                        humi_parsed = True
                    except IndexError:
                        pass # Parsing error, keep previous values
                elif line.startswith("R1: ") and "R2:" in line:
                    try:
                        current_relay1 = line.split("R1: ")[1].split(",")[0].strip()
                        current_relay2 = line.split("R2: ")[1].strip()
                        relay_parsed = True
                    except IndexError:
                        pass # Parsing error, keep previous values
                elif line.startswith("FPGA_LCD_L1: "):
                    current_lcd1 = line.replace("FPGA_LCD_L1: ", "").strip()
                    lcd1_parsed = True
                elif line.startswith("FPGA_LCD_L2: "):
                    current_lcd2 = line.replace("FPGA_LCD_L2: ", "").strip()
                    lcd2_parsed = True
            
            # Update GUI labels only if new data was successfully parsed
            if temp_parsed:
                current_temp_label.config(text=f"{current_temp}°C")
                last_temp_val = current_temp
            else:
                current_temp_label.config(text=f"{last_temp_val}°C") # Display last valid
            
            if humi_parsed:
                current_humi_label.config(text=f"{current_humi}%")
                last_humi_val = current_humi
            else:
                current_humi_label.config(text=f"{last_humi_val}%") # Display last valid

            if relay_parsed:
                relay1_status_label.config(text=f"TEMP RELAY: {current_relay1}")
                relay2_status_label.config(text=f"HUMI RELAY: {current_relay2}")
                last_relay1_stat = current_relay1
                last_relay2_stat = current_relay2
            else:
                relay1_status_label.config(text=f"TEMP RELAY: {last_relay1_stat}") # Display last valid
                relay2_status_label.config(text=f"HUMI RELAY: {last_relay2_stat}") # Display last valid

            if lcd1_parsed and lcd2_parsed:
                fpga_lcd_display_label.config(text=f"{current_lcd1}\n{current_lcd2}")
                last_fpga_lcd_line1 = current_lcd1
                last_fpga_lcd_line2 = current_lcd2
            else:
                fpga_lcd_display_label.config(text=f"{last_fpga_lcd_line1}\n{last_fpga_lcd_line2}") # Display last valid

            # Check for any error output from C program
            stderr_output = dht_process.stderr.read()
            if stderr_output:
                print(f"C Program Stderr: {stderr_output.strip()}")

        else: # C program is not running
            current_temp_label.config(text="C Program Ended")
            current_humi_label.config(text="C Program Ended")
            relay1_status_label.config(text="TEMP RELAY: Ended")
            relay2_status_label.config(text="HUMI RELAY: Ended")
            fpga_lcd_display_label.config(text="C Program has ended or failed to start.\n")
            print("C program process ended. Exiting update thread.")
            break # Exit the update loop

        time.sleep(1) # Check for new output every 1 second (C program updates every 2s)

# GUI window closing event handler
def on_closing():
    global dht_process
    if dht_process and dht_process.poll() is None: # Check if C program is still running
        print("GUI closing. Sending SIGINT to dht_1 process group...")
        try:
            os.killpg(os.getpgid(dht_process.pid), signal.SIGINT)
            dht_process.wait(timeout=5) # Wait for C program to terminate cleanly
        except ProcessLookupError:
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
tk.Label(root, text="FPGA LCD Output:").grid(row=7, column=0, padx=5, pady=5, sticky='w')
fpga_lcd_display_label = tk.Label(root, text="Line 1\nLine 2", font=("Courier New", 12), fg="blue", justify=tk.LEFT, relief="groove", borderwidth=2, width=20, height=2)
fpga_lcd_display_label.grid(row=7, column=1, padx=5, pady=5, sticky='ew')

# Start the Tkinter event loop
root.mainloop()
