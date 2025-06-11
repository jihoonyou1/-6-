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

// Global variables to hold the last successfully read sensor data
float last_temp_c = -999.9; // Use an unlikely value to indicate no data yet
float last_humi = -999.9;
char last_lcd_line1[LINE_BUFF + 1] = "Waiting for data"; // Initial message for LCD
char last_lcd_line2[LINE_BUFF + 1] = "Connecting...";    // Initial message for LCD


// Function to write two lines to the FPGA TEXT LCD
// Returns 0 on success, -1 on failure
int write_to_lcd(const char* line1, const char* line2) {
    int dev;
    unsigned char string[MAX_BUFF];
    memset(string, 0, sizeof(string));

    // Ensure lines fit within LCD buffer (16 chars per line)
    // This check is mainly for safety, snprintf should handle sizing
    if (strlen(line1) > LINE_BUFF || strlen(line2) > LINE_BUFF) {
        return -1; 
    }

    dev = open(FPGA_TEXT_LCD_DEVICE, O_WRONLY);
    if (dev < 0) {
        // perror("Failed to open FPGA text LCD device"); // Uncomment for debugging LCD open failures
        return -1; // Silently fail if device cannot be opened
    }

    // Copy line1, pad with spaces to 16 chars
    strncpy((char*)string, line1, LINE_BUFF); 
    if (strlen((char*)string) < LINE_BUFF) { 
        memset(string + strlen((char*)string), ' ', LINE_BUFF - strlen((char*)string)); 
    }

    // Copy line2, pad with spaces to 16 chars
    strncpy((char*)string + LINE_BUFF, line2, LINE_BUFF); 
    if (strlen((char*)string + LINE_BUFF) < LINE_BUFF) { 
        memset(string + LINE_BUFF + strlen((char*)string + LINE_BUFF), ' ', LINE_BUFF - strlen((char*)string + LINE_BUFF));
    }

    write(dev, string, MAX_BUFF);
    close(dev);
    return 0;
}

// Signal handler for clean exit (e.g., on Ctrl+C or GUI close)
void cleanup_handler(int signum) {
    if (signum == SIGINT) {
        // 1. Write "CHECK END!" to FPGA LCD
        write_to_lcd("CHECK END!", "          "); // Pad second line with spaces

        // 2. Turn off relays to a safe state (HIGH for active-low)
        pinMode(RELAY1_PIN, OUTPUT); 
        digitalWrite(RELAY1_PIN, HIGH); // OFF
        pinMode(RELAY2_PIN, OUTPUT);
        digitalWrite(RELAY2_PIN, HIGH); // OFF
        
        delay(500); // Give LCD time to display the message

        // 3. Exit the program cleanly
        exit(0); 
    }
}

// Function to read DHT22, control relays, and prepare output strings
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

    if (j >= 40 && (data[4] == ((data[0] + data[1] + data[2] + data[3]) & 0xFF))) {
        // Successful read
        // Calculate Humidity
        float h = (float)((data[0] << 8) + data[1]) / 10;
        if (h > 100.0) h = 100.0; // Cap humidity at 100%
        if (h < 0.0) h = 0.0;     // Cap humidity at 0%

        // Calculate Temperature
        float c = (float)(((data[2] & 0x7F) << 8) + data[3]) / 10;
        if (data[2] & 0x80) c = -c; // Handle negative temperature (MSB of data[2] is sign bit)
        if (c > 125.0) c = 125.0; // Cap temperature at 125C
        if (c < -40.0) c = -40.0; // Cap temperature at -40C

        // Update last valid sensor data
        last_temp_c = c;
        last_humi = h;

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
        
        // Format strings for FPGA TEXT LCD display and update global LCD lines
        snprintf(last_lcd_line1, sizeof(last_lcd_line1), "Temp:%.1fC %s", last_temp_c, relay1_on ? "ON" : "OFF");
        snprintf(last_lcd_line2, sizeof(last_lcd_line2), "Humi:%.1f%% %s", last_humi, relay2_on ? "ON" : "OFF");

    } else {
        // Sensor data error. Keep last valid data and continue with last LCD message.
        // No change to last_temp_c, last_humi. Relay states remain as they were.
        // last_lcd_line1 and last_lcd_line2 will also remain unchanged from the last successful read.
    }

    // --- ALWAYS write to FPGA LCD and print to standard output for GUI to mirror ---
    // This uses the 'last_lcd_lineX' which holds either new valid data or previous valid data.
    write_to_lcd(last_lcd_line1, last_lcd_line2);

    // Also print these lines to standard output for GUI to parse and mirror
    printf("FPGA_LCD_L1:%s\n", last_lcd_line1);
    printf("FPGA_LCD_L2:%s\n", last_lcd_line2);
    fflush(stdout); // Ensure all printf output is flushed immediately
}

int main(int argc, char* argv[]) {
    // Register signal handler for SIGINT (Ctrl+C)
    if (signal(SIGINT, cleanup_handler) == SIG_ERR) {
        fprintf(stderr, "Error setting signal handler for SIGINT!\n");
        return 1;
    }

    // Argument validation
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <TEMP-SET> <HUMI-SET>\n", argv[0]);
        // Initial LCD messages on usage error, and mirror to stdout
        snprintf(last_lcd_line1, sizeof(last_lcd_line1), "Usage Error");
        snprintf(last_lcd_line2, sizeof(last_lcd_line2), "Check console");
        write_to_lcd(last_lcd_line1, last_lcd_line2);
        printf("FPGA_LCD_L1:%s\n", last_lcd_line1);
        printf("FPGA_LCD_L2:%s\n", last_lcd_line2);
        fflush(stdout);
        return 1;
    }

    // Convert command-line arguments to thresholds
    threshold_temp = atof(argv[1]);
    threshold_humi = atoi(argv[2]);

    // Initialize WiringPi
    if (wiringPiSetup() == -1) {
        fprintf(stderr, "WiringPi setup failed!\n");
        // Initial LCD messages on WiringPi error, and mirror to stdout
        snprintf(last_lcd_line1, sizeof(last_lcd_line1), "WiringPi Err");
        snprintf(last_lcd_line2, sizeof(last_lcd_line2), "Setup Failed");
        write_to_lcd(last_lcd_line1, last_lcd_line2);
        printf("FPGA_LCD_L1:%s\n", last_lcd_line1);
        printf("FPGA_LCD_L2:%s\n", last_lcd_line2);
        fflush(stdout);
        return 1;
    }

    // Initialize relay pins to OUTPUT and ensure they are OFF (HIGH for active-low)
    pinMode(RELAY1_PIN, OUTPUT);
    pinMode(RELAY2_PIN, OUTPUT);
    digitalWrite(RELAY1_PIN, HIGH); 
    digitalWrite(RELAY2_PIN, HIGH); 
    
    // Initial LCD messages with settings, and mirror to stdout
    snprintf(last_lcd_line1, sizeof(last_lcd_line1), "Set T:%.1fC", threshold_temp);
    snprintf(last_lcd_line2, sizeof(last_lcd_line2), "Set H:%d%%", threshold_humi);
    write_to_lcd(last_lcd_line1, last_lcd_line2);
    printf("FPGA_LCD_L1:%s\n", last_lcd_line1);
    printf("FPGA_LCD_L2:%s\n", last_lcd_line2);
    fflush(stdout); 

    delay(2000); // Show initial settings for a moment (2 seconds)

    // Main loop for continuous reading and control
    while (1) {
        read_dht_and_control();
        delay(4000); // Read and update every 4 seconds
    }

    return 0; // This line is theoretically unreachable due to while(1)
}
