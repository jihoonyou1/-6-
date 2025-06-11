#include <wiringPi.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <signal.h> // For signal handling

#define MAX_TIMINGS 85
#define DHT_PIN 2         // WiringPi pin for DHT22 (GPIO27)
#define RELAY1_PIN 25     // WiringPi pin for Temperature control relay (GPIO24)
#define RELAY2_PIN 5      // WiringPi pin for Humidity control relay (GPIO26)
#define FPGA_TEXT_LCD_DEVICE "/dev/fpga_text_lcd" // FPGA TEXT LCD device path
#define MAX_BUFF 32       // Total buffer size for LCD (2 lines * 16 chars)
#define LINE_BUFF 16      // Characters per LCD line

int data[5] = { 0, 0, 0, 0, 0 };

// Global variables for relay states
// 0 for OFF (HIGH), 1 for ON (LOW) - assuming active-low relays
int relay1_on = 0; 
int relay2_on = 0; 

// User input thresholds
float threshold_temp;
int threshold_humi;

// Function to write two lines to the FPGA TEXT LCD
// Returns 0 on success, -1 on failure
int write_to_lcd(const char* line1, const char* line2) {
    int dev;
    unsigned char string[MAX_BUFF];
    memset(string, 0, sizeof(string));

    // Ensure lines fit within LCD buffer (16 chars per line)
    if (strlen(line1) > LINE_BUFF || strlen(line2) > LINE_BUFF) {
        // This case should ideally not happen if snprintf limits are correct
        return -1; 
    }

    // Open FPGA TEXT LCD device
    dev = open(FPGA_TEXT_LCD_DEVICE, O_WRONLY);
    if (dev < 0) {
        // Silently fail if device cannot be opened, as requested
        return -1;
    }

    // Copy line1, pad with spaces to 16 chars
    strncpy((char*)string, line1, LINE_BUFF); 
    if (strlen((char*)string) < LINE_BUFF) { // Only pad if necessary
        memset(string + strlen((char*)string), ' ', LINE_BUFF - strlen((char*)string)); 
    }

    // Copy line2, pad with spaces to 16 chars
    strncpy((char*)string + LINE_BUFF, line2, LINE_BUFF); 
    if (strlen((char*)string + LINE_BUFF) < LINE_BUFF) { // Only pad if necessary
        memset(string + LINE_BUFF + strlen((char*)string + LINE_BUFF), ' ', LINE_BUFF - strlen((char*)string + LINE_BUFF));
    }

    // Write the 32-byte buffer to the device
    write(dev, string, MAX_BUFF);
    close(dev);
    return 0;
}

// Signal handler for clean exit (e.g., on Ctrl+C or GUI close)
void cleanup_handler(int signum) {
    if (signum == SIGINT) {
        // printf("\nCaught SIGINT. Cleaning up...\n"); // Debug message, can be removed in final version

        // 1. Write "CHECK END!" to FPGA LCD
        write_to_lcd("CHECK END!", "          "); // Pad second line with spaces

        // 2. Turn off relays to a safe state (HIGH for active-low)
        // Ensure pins are set to OUTPUT mode first if not already (though main does this)
        pinMode(RELAY1_PIN, OUTPUT); 
        digitalWrite(RELAY1_PIN, HIGH); // OFF
        pinMode(RELAY2_PIN, OUTPUT);
        digitalWrite(RELAY2_PIN, HIGH); // OFF
        
        delay(500); // Give LCD time to display the message

        // 3. Exit the program cleanly
        exit(0); 
    }
}

// Function to read DHT22, control relays, and print formatted output
void read_dht_and_control() {
    uint8_t laststate = HIGH;
    uint8_t counter = 0;
    uint8_t j = 0, i;
    // Reset data buffer for each read attempt
    data[0] = data[1] = data[2] = data[3] = data[4] = 0;

    // DHT22 communication sequence
    pinMode(DHT_PIN, OUTPUT);
    digitalWrite(DHT_PIN, HIGH);
    delay(100); // Wait for DHT22 to be ready
    digitalWrite(DHT_PIN, LOW);
    delay(18); // DHT22 requires 18ms low signal
    digitalWrite(DHT_PIN, HIGH);
    delayMicroseconds(40); // Pull high for 40us
    pinMode(DHT_PIN, INPUT); // Switch to input mode to read DHT22 response

    // Read DHT22 response bits
    for (i = 0; i < MAX_TIMINGS; i++) {
        counter = 0;
        while (digitalRead(DHT_PIN) == laststate) {
            counter++;
            delayMicroseconds(1);
            if (counter == 255) break; // Timeout
        }
        laststate = digitalRead(DHT_PIN);
        if (counter == 255) break; // Timeout

        // Collect data bits (ignore first 3 transitions which are start bits)
        if ((i >= 4) && (i % 2 == 0)) {
            data[j / 8] <<= 1; // Shift existing bits left
            if (counter > 16) // If the pulse is long, it's a '1' bit
                data[j / 8] |= 1; // Set LSB to 1
            j++;
        }
    }

    // Validate data and checksum
    if (j >= 40 && (data[4] == ((data[0] + data[1] + data[2] + data[3]) & 0xFF))) {
        // Calculate Humidity
        float h = (float)((data[0] << 8) + data[1]) / 10;
        if (h > 100.0) h = 100.0; // Cap humidity at 100%
        if (h < 0.0) h = 0.0;     // Cap humidity at 0%

        // Calculate Temperature
        float c = (float)(((data[2] & 0x7F) << 8) + data[3]) / 10;
        if (data[2] & 0x80) c = -c; // Handle negative temperature (MSB of data[2] is sign bit)
        if (c > 125.0) c = 125.0; // Cap temperature at 125C
        if (c < -40.0) c = -40.0; // Cap temperature at -40C

        // Control relays based on thresholds (with hysteresis)
        // Temperature Relay (RELAY1_PIN) - Active Low
        if (c >= threshold_temp + 0.5 && !relay1_on) { // If temp is high and relay is off
            digitalWrite(RELAY1_PIN, LOW); // Turn ON
            relay1_on = 1;
        } else if (c <= threshold_temp - 0.5 && relay1_on) { // If temp is low and relay is on
            digitalWrite(RELAY1_PIN, HIGH); // Turn OFF
            relay1_on = 0;
        }

        // Humidity Relay (RELAY2_PIN) - Active Low
        if (h >= threshold_humi + 5 && !relay2_on) { // If humi is high and relay is off
            digitalWrite(RELAY2_PIN, LOW); // Turn ON
            relay2_on = 1;
        } else if (h <= threshold_humi - 5 && relay2_on) { // If humi is low and relay is on
            digitalWrite(RELAY2_PIN, HIGH); // Turn OFF
            relay2_on = 0;
        }
        
        // --- Print formatted output to standard output for GUI ---
        // Line 1: Current Temperature and Humidity
        printf("Temp: %.1f C, Humi: %.1f %%\n", c, h);
        // Line 2: Relay Status (R1 for Temp, R2 for Humi)
        printf("R1: %s, R2: %s\n", relay1_on ? "ON" : "OFF", relay2_on ? "ON" : "OFF");

        // Format strings for FPGA TEXT LCD display
        char lcd_line1[LINE_BUFF + 1], lcd_line2[LINE_BUFF + 1];
        snprintf(lcd_line1, sizeof(lcd_line1), "Temp:%.1fC %s", c, relay1_on ? "ON" : "OFF");
        snprintf(lcd_line2, sizeof(lcd_line2), "Humi:%.1f%% %s", h, relay2_on ? "ON" : "OFF");

        // Write to FPGA TEXT LCD device
        write_to_lcd(lcd_line1, lcd_line2);

        // --- Also print LCD lines to standard output for GUI to mirror ---
        // Use unique prefixes to help Python identify these specific lines
        printf("FPGA_LCD_L1: %s\n", lcd_line1);
        printf("FPGA_LCD_L2: %s\n", lcd_line2);

    } else {
        // Sensor data not ready or checksum error.
        // Print "N/A" or "Error" values to maintain consistent 4-line output structure for Python GUI
        printf("Temp: N/A C, Humi: N/A %%\n");
        printf("R1: N/A, R2: N/A\n");

        // Update FPGA LCD with an error message
        write_to_lcd("Sensor Error", "Check DHT22");
        // Also print LCD error lines to standard output for GUI to mirror
        printf("FPGA_LCD_L1: Sensor Error\n");
        printf("FPGA_LCD_L2: Check DHT22\n");
    }
    fflush(stdout); // Ensure all printf output is flushed immediately
}

int main(int argc, char* argv[]) {
    // Register signal handler for SIGINT (Ctrl+C)
    if (signal(SIGINT, cleanup_handler) == SIG_ERR) {
        // If signal handler setup fails, print error and exit (this should rarely happen)
        fprintf(stderr, "Error setting signal handler for SIGINT!\n");
        return 1;
    }

    // Argument validation
    if (argc != 3) {
        // If incorrect arguments, print usage to stderr and consistent output to stdout for GUI
        fprintf(stderr, "Usage: %s <TEMP-SET> <HUMI-SET>\n", argv[0]);
        printf("Temp: N/A C, Humi: N/A %%\n"); // Placeholder for data line
        printf("R1: N/A, R2: N/A\n");         // Placeholder for relay line
        write_to_lcd("Usage Error", "Check console"); // LCD message
        printf("FPGA_LCD_L1: Usage Error\n");
        printf("FPGA_LCD_L2: Check console\n");
        fflush(stdout);
        return 1;
    }

    // Convert command-line arguments to thresholds
    threshold_temp = atof(argv[1]);
    threshold_humi = atoi(argv[2]);

    // Initialize WiringPi
    if (wiringPiSetup() == -1) {
        // If WiringPi setup fails, print error to stderr and consistent output to stdout for GUI
        fprintf(stderr, "WiringPi setup failed!\n");
        printf("Temp: Setup Error, Humi: Setup Error\n"); // Placeholder for data line
        printf("R1: ERROR, R2: ERROR\n");                // Placeholder for relay line
        write_to_lcd("WiringPi Err", "Setup Failed");   // LCD message
        printf("FPGA_LCD_L1: WiringPi Err\n");
        printf("FPGA_LCD_L2: Setup Failed\n");
        fflush(stdout);
        return 1;
    }

    // Initialize relay pins to OUTPUT and ensure they are OFF (HIGH for active-low)
    pinMode(RELAY1_PIN, OUTPUT);
    pinMode(RELAY2_PIN, OUTPUT);
    digitalWrite(RELAY1_PIN, HIGH); 
    digitalWrite(RELAY2_PIN, HIGH); 
    
    // Initial output for GUI (after successful setup)
    // This provides initial values before the main loop starts reading sensor data
    printf("Temp: Initial C, Humi: Initial %%\n"); // Placeholder values
    printf("R1: OFF, R2: OFF\n"); // Assuming they start off initially
    
    char lcd_set_line1[LINE_BUFF + 1];
    char lcd_set_line2[LINE_BUFF + 1];
    snprintf(lcd_set_line1, sizeof(lcd_set_line1), "Set T:%.1fC", threshold_temp);
    snprintf(lcd_set_line2, sizeof(lcd_set_line2), "Set H:%d%%", threshold_humi);
    write_to_lcd(lcd_set_line1, lcd_set_line2);
    printf("FPGA_LCD_L1: %s\n", lcd_set_line1);
    printf("FPGA_LCD_L2: %s\n", lcd_set_line2);
    fflush(stdout); // Flush after initial output

    delay(2000); // Show initial settings for a moment

    // Main loop for continuous reading and control
    while (1) {
        read_dht_and_control();
        delay(2000); // Read and update every 2 seconds
    }

    return 0; // This line is theoretically unreachable due to while(1)
}
