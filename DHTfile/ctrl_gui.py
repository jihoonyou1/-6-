-import tkinter as tk
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

def start_control():
    global temp_threshold, humi_threshold, dht_process
    
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
        current_temp_label.config(text="Reading...")
        current_humi_label.config(text="Reading...")
        relay1_status_label.config(text="TEMP RELAY: Initializing...")
        relay2_status_label.config(text="HUMI RELAY: Initializing...")
        fpga_lcd_display_label.config(text="Starting C program...\n")

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
    global dht_process
    while True:
        if dht_process and dht_process.poll() is None: # Check if C program is still running
            all_lines = []
            # Read multiple lines in a short burst, expecting the 4 lines of output
            # C program outputs every 2 seconds, so we try to read for a bit longer.
            start_read_time = time.time()
            while time.time() - start_read_time < 2.5: # Timeout for reading a full block
                line = dht_process.stdout.readline()
                if line:
                    all_lines.append(line.strip())
                    # Assuming FPGA_LCD_L2 is the last line of a complete data block
                    if "FPGA_LCD_L2:" in line:
                        break
                else: # No new line, give it a tiny moment
                    time.sleep(0.01) # Small delay to avoid busy-waiting too much
            
            # --- Parsing the received lines ---
            data_line = ""
            relay_status_line = ""
            fpga_lcd_line1_content = ""
            fpga_lcd_line2_content = ""

            for line in all_lines:
                if line.startswith("Temp: ") and "Humi:" in line:
                    data_line = line
                elif line.startswith("R1: ") and "R2:" in line:
                    relay_status_line = line
                elif line.startswith("FPGA_LCD_L1: "):
                    fpga_lcd_line1_content = line.replace("FPGA_LCD_L1: ", "").strip()
                elif line.startswith("FPGA_LCD_L2: "):
                    fpga_lcd_line2_content = line.replace("FPGA_LCD_L2: ", "").strip()
            
            # Update Current Temp & Humi
            if data_line:
                try:
                    temp_val = data_line.split("Temp: ")[1].split(" C")[0]
                    humi_val = data_line.split("Humi: ")[1].split(" %")[0]
                    current_temp_label.config(text=f"{temp_val}°C")
                    current_humi_label.config(text=f"{humi_val}%")
                except IndexError:
                    current_temp_label.config(text="Temp: PARSE ERR")
                    current_humi_label.config(text="Humi: PARSE ERR")
            else:
                current_temp_label.config(text="Temp: N/A")
                current_humi_label.config(text="Humi: N/A")

            # Update Relay Status
            if relay_status_line:
                try:
                    relay1_stat = relay_status_line.split("R1: ")[1].split(",")[0].strip()
                    relay2_stat = relay_status_line.split("R2: ")[1].strip()
                    relay1_status_label.config(text=f"TEMP RELAY: {relay1_stat}")
                    relay2_status_label.config(text=f"HUMI RELAY: {relay2_stat}")
                except IndexError:
                    relay1_status_label.config(text="TEMP RELAY: PARSE ERR")
                    relay2_status_label.config(text="HUMI RELAY: PARSE ERR")
            else:
                relay1_status_label.config(text="TEMP RELAY: N/A")
                relay2_status_label.config(text="HUMI RELAY: N/A")

            # Update FPGA LCD display in GUI
            if fpga_lcd_line1_content and fpga_lcd_line2_content:
                fpga_lcd_display_label.config(text=f"{fpga_lcd_line1_content}\n{fpga_lcd_line2_content}")
            else:
                fpga_lcd_display_label.config(text="LCD data not found\nCheck C program output.")
                
            # If C program has error output to stderr, print it
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
        # Send SIGINT to the process group of dht_1
        # This will trigger the cleanup_handler in the C program
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
