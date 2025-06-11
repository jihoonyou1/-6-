#include <wiringPi.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

#define MAX_TIMINGS 85
#define DHT_PIN 2         // WiringPi pin for DHT22
#define RELAY1_PIN 25     // WiringPi pin for Temperature control relay (GPIO24)
#define RELAY2_PIN 5      // WiringPi pin for Humidity control relay (GPIO26)
#define FPGA_TEXT_LCD_DEVICE "/dev/fpga_text_lcd" // FPGA TEXT LCD device path
#define MAX_BUFF 32       // Total buffer size for LCD (2 lines * 16 chars)
#define LINE_BUFF 16      // Characters per LCD line

int data[5] = { 0, 0, 0, 0, 0 };

// Global variables for relay states
int relay1_on = 0; // 0 for OFF (HIGH), 1 for ON (LOW)
int relay2_on = 0; // 0 for OFF (HIGH), 1 for ON (LOW)

// User input thresholds
float threshold_temp; // Changed to float to match GUI input and comparison
int threshold_humi;

// Function to write two lines to the FPGA TEXT LCD
int write_to_lcd(const char* line1, const char* line2) {
    int dev;
    unsigned char string[MAX_BUFF];
    memset(string, 0, sizeof(string));

    // Ensure lines fit within LCD buffer
    if (strlen(line1) > LINE_BUFF || strlen(line2) > LINE_BUFF) {
        printf("Line too long for LCD!\n");
        return -1;
    }

    // Open FPGA TEXT LCD device
    dev = open(FPGA_TEXT_LCD_DEVICE, O_WRONLY);
    if (dev < 0) {
        printf("Device open error: %s\n", FPGA_TEXT_LCD_DEVICE);
        return -1;
    }

    // Copy line1, pad with spaces, then copy line2, pad with spaces
    strncpy((char*)string, line1, strlen(line1));
    memset(string + strlen(line1), ' ', LINE_BUFF - strlen(line1));
    strncpy((char*)string + LINE_BUFF, line2, strlen(line2));
    memset(string + LINE_BUFF + strlen(line2), ' ', LINE_BUFF - strlen(line2));

    // Write to the device
    write(dev, string, MAX_BUFF);
    close(dev);
    return 0;
}

void read_dht_and_control() {
    uint8_t laststate = HIGH;
    uint8_t counter = 0;
    uint8_t j = 0, i;
    data[0] = data[1] = data[2] = data[3] = data[4] = 0;

    // Prepare DHT_PIN for communication
    pinMode(DHT_PIN, OUTPUT);
    digitalWrite(DHT_PIN, HIGH); // Ensure high for clean start
    delay(100); // Wait for DHT22 to be ready

    // Request data from DHT22
    digitalWrite(DHT_PIN, LOW);
    delay(18); // DHT22 requires 18ms low signal
    digitalWrite(DHT_PIN, HIGH);
    delayMicroseconds(40); // Pull high for 40us
    pinMode(DHT_PIN, INPUT);

    // Read DHT22 response
    for (i = 0; i < MAX_TIMINGS; i++) {
        counter = 0;
        while (digitalRead(DHT_PIN) == laststate) {
            counter++;
            delayMicroseconds(1);
            if (counter == 255) break;
        }
        laststate = digitalRead(DHT_PIN);
        if (counter == 255) break;

        // Collect data bits (ignore first 3 transitions)
        if ((i >= 4) && (i % 2 == 0)) {
            data[j / 8] <<= 1;
            if (counter > 16) // If the pulse is long, it's a '1' bit
                data[j / 8] |= 1;
            j++;
        }
    }

    // Validate data and checksum
    if ((j >= 40) && (data[4] == ((data[0] + data[1] + data[2] + data[3]) & 0xFF))) {
        float h = (float)((data[0] << 8) + data[1]) / 10;
        if (h > 100.0) h = 100.0; // Cap humidity at 100%
        if (h < 0.0) h = 0.0;     // Cap humidity at 0%

        float c = (float)(((data[2] & 0x7F) << 8) + data[3]) / 10;
        if (data[2] & 0x80) c = -c; // Handle negative temperature
        if (c > 125.0) c = 125.0; // Cap temperature at 125C
        if (c < -40.0) c = -40.0; // Cap temperature at -40C

        float f = c * 1.8f + 32; // Calculate Fahrenheit

        // Control relays (active-low: LOW for ON, HIGH for OFF)
        // Temperature Relay (RELAY1_PIN)
        if (c >= threshold_temp + 0.5 && !relay1_on) {
            digitalWrite(RELAY1_PIN, LOW); // ON
            relay1_on = 1;
        } else if (c <= threshold_temp - 0.5 && relay1_on) {
            digitalWrite(RELAY1_PIN, HIGH); // OFF
            relay1_on = 0;
        }

        // Humidity Relay (RELAY2_PIN)
        if (h >= threshold_humi + 5 && !relay2_on) {
            digitalWrite(RELAY2_PIN, LOW); // ON
            relay2_on = 1;
        } else if (h <= threshold_humi - 5 && relay2_on) {
            digitalWrite(RELAY2_PIN, HIGH); // OFF
            relay2_on = 0;
        }
        
        // Print to standard output for GUI
        printf("Humidity = %.1f %% (Relay: %s) Temperature = %.1f *C (%.1f *F) (Relay: %s)\n",
               h, relay2_on ? "ON" : "OFF",
               c, f, relay1_on ? "ON" : "OFF");

        // Format strings for LCD display
        char line1[LINE_BUFF + 1], line2[LINE_BUFF + 1];
        snprintf(line1, sizeof(line1), "Temp: %.1fC %s", c, relay1_on ? "ON" : "OFF");
        snprintf(line2, sizeof(line2), "Humi: %.1f%% %s", h, relay2_on ? "ON" : "OFF");

        // Write to FPGA TEXT LCD
        write_to_lcd(line1, line2);

    } else {
        printf("DHT22 data not ready or checksum error.\n");
        // Optionally, write an error message to LCD
        write_to_lcd("Sensor Error", "Check DHT22");
    }
}

int main(int argc, char* argv[]) {
    // Check for correct number of arguments (TEMP and HUMI thresholds)
    if (argc != 3) {
        printf("Usage: %s <TEMP-SET> <HUMI-SET>\n", argv[0]);
        // Also display usage on LCD if possible
        write_to_lcd("Usage:", "<TEMP> <HUMI>");
        return 1;
    }

    // Convert command-line arguments to thresholds
    threshold_temp = atof(argv[1]);
    threshold_humi = atoi(argv[2]);

    printf("DHT22 SENSOR - SET TEMP: %.1f°C, SET HUMI: %d%%\n", threshold_temp, threshold_humi);
    // Display initial thresholds on LCD
    char lcd_set_line1[LINE_BUFF + 1];
    char lcd_set_line2[LINE_BUFF + 1];
    snprintf(lcd_set_line1, sizeof(lcd_set_line1), "Set T:%.1fC", threshold_temp);
    snprintf(lcd_set_line2, sizeof(lcd_set_line2), "Set H:%d%%", threshold_humi);
    write_to_lcd(lcd_set_line1, lcd_set_line2);
    delay(2000); // Show initial settings for a moment

    // Initialize WiringPi
    if (wiringPiSetup() == -1) {
        printf("WiringPi setup failed!\n");
        write_to_lcd("WiringPi", "Setup Failed");
        return 1;
    }

    // Initialize relay pins to OUTPUT and ensure they are OFF
    pinMode(RELAY1_PIN, OUTPUT);
    pinMode(RELAY2_PIN, OUTPUT);
    digitalWrite(RELAY1_PIN, HIGH); // Relays OFF at start (active-low)
    digitalWrite(RELAY2_PIN, HIGH); // Relays OFF at start (active-low)

    // Main loop for continuous reading and control
    while (1) {
        read_dht_and_control();
        delay(2000); // Read and update every 2 seconds (was 4000)
    }

    return 0;
}
