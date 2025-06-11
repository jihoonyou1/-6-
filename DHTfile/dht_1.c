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
char last_lcd_line1[LINE_BUFF + 1] = "No Data";
char last_lcd_line2[LINE_BUFF + 1] = "Init...";


// Function to write two lines to the FPGA TEXT LCD
// Returns 0 on success, -1 on failure
int write_to_lcd(const char* line1, const char* line2) {
    int dev;
    unsigned char string[MAX_BUFF];
    memset(string, 0, sizeof(string));

    // Ensure lines fit within LCD buffer (16 chars per line)
    if (strlen(line1) > LINE_BUFF || strlen(line2) > LINE_BUFF) {
        return -1; 
    }

    // Open FPGA TEXT LCD device
    dev = open(FPGA_TEXT_LCD_DEVICE, O_WRONLY);
    if (dev < 0) {
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

    // Write the 32-byte buffer to the device
    write(dev, string, MAX_BUFF);
    close(dev);
    return 0;
}

// Signal handler for clean exit (e.g., on Ctrl+C or GUI close)
void cleanup_handler(int signum) {
    if (signum == SIGINT) {
        write_to_lcd("CHECK END!", "          "); // FPGA LCD에 메시지 출력
        
        // 릴레이 끄기 (안전한 상태로 돌리기)
        pinMode(RELAY1_PIN, OUTPUT); 
        digitalWrite(RELAY1_PIN, HIGH); // OFF
        pinMode(RELAY2_PIN, OUTPUT);
        digitalWrite(RELAY2_PIN, HIGH); // OFF
        
        delay(500); // Give LCD time to display the message

        exit(0); // Program 종료
    }
}

// Function to read DHT22, control relays, and print formatted output
void read_dht_and_control() {
    uint8_t laststate = HIGH;
    uint8_t counter = 0;
    uint8_t j = 0, i;
    data[0] = data[1] = data[2] = data[3] = data[4] = 0;

    // DHT22 communication sequence
    pinMode(DHT_PIN, OUTPUT);
    digitalWrite(DHT_PIN, HIGH);
    delay(100); 
    digitalWrite(DHT_PIN, LOW);
    delay(18); 
    digitalWrite(DHT_PIN, HIGH);
    delayMicroseconds(40); 
    pinMode(DHT_PIN, INPUT); 

    // Read DHT22 response bits
    for (i = 0; i < MAX_TIMINGS; i++) {
        counter = 0;
        while (digitalRead(DHT_PIN) == laststate) {
            counter++;
            delayMicroseconds(1);
            if (counter == 255) break; 
        }
        laststate = digitalRead(DHT_PIN);
        if (counter == 255) break; 

        if ((i >= 4) && (i % 2 == 0)) {
            data[j / 8] <<= 1; 
            if (counter > 16) 
                data[j / 8] |= 1; 
            j++;
        }
    }

    if (j >= 40 && (data[4] == ((data[0] + data[1] + data[2] + data[3]) & 0xFF))) {
        // Successfully read data
        float h = (float)((data[0] << 8) + data[1]) / 10;
        if (h > 100.0) h = 100.0; 
        if (h < 0.0) h = 0.0;     

        float c = (float)(((data[2] & 0x7F) << 8) + data[3]) / 10;
        if (data[2] & 0x80) c = -c; 
        if (c > 125.0) c = 125.0; 
        if (c < -40.0) c = -40.0; 

        // Update last valid sensor data
        last_temp_c = c;
        last_humi = h;

        // Control relays based on thresholds (with hysteresis)
        if (c >= threshold_temp + 0.5 && !relay1_on) { 
            digitalWrite(RELAY1_PIN, LOW); 
            relay1_on = 1;
        } else if (c <= threshold_temp - 0.5 && relay1_on) { 
            digitalWrite(RELAY1_PIN, HIGH); 
            relay1_on = 0;
        }

        if (h >= threshold_humi + 5 && !relay2_on) { 
            digitalWrite(RELAY2_PIN, LOW); 
            relay2_on = 1;
        } else if (h <= threshold_humi - 5 && relay2_on) { 
            digitalWrite(RELAY2_PIN, HIGH); 
            relay2_on = 0;
        }
        
        // --- Print formatted output to standard output for GUI ---
        printf("Temp: %.1f C, Humi: %.1f %%\n", last_temp_c, last_humi);
        printf("R1: %s, R2: %s\n", relay1_on ? "ON" : "OFF", relay2_on ? "ON" : "OFF");

        // Format strings for FPGA TEXT LCD display and update global LCD lines
        snprintf(last_lcd_line1, sizeof(last_lcd_line1), "Temp:%.1fC %s", last_temp_c, relay1_on ? "ON" : "OFF");
        snprintf(last_lcd_line2, sizeof(last_lcd_line2), "Humi:%.1f%% %s", last_humi, relay2_on ? "ON" : "OFF");

        write_to_lcd(last_lcd_line1, last_lcd_line2);
        printf("FPGA_LCD_L1: %s\n", last_lcd_line1);
        printf("FPGA_LCD_L2: %s\n", last_lcd_line2);

    } else {
        // Sensor data error. Output last valid data to GUI and LCD.
        printf("Temp: %.1f C, Humi: %.1f %%\n", last_temp_c, last_humi);
        printf("R1: %s, R2: %s\n", relay1_on ? "ON" : "OFF", relay2_on ? "ON" : "OFF"); // Keep current relay state

        // Write last valid LCD content to FPGA LCD
        write_to_lcd(last_lcd_line1, last_lcd_line2);
        printf("FPGA_LCD_L1: %s\n", last_lcd_line1);
        printf("FPGA_LCD_L2: %s\n", last_lcd_line2);
    }
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
        // Initial output for GUI on usage error
        printf("Temp: N/A C, Humi: N/A %%\n"); 
        printf("R1: N/A, R2: N/A\n");         
        write_to_lcd("Usage Error", "Check console"); 
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
        fprintf(stderr, "WiringPi setup failed!\n");
        // Initial output for GUI on WiringPi error
        printf("Temp: Setup Error, Humi: Setup Error\n"); 
        printf("R1: ERROR, R2: ERROR\n");                
        write_to_lcd("WiringPi Err", "Setup Failed");   
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
    printf("Temp: Initial C, Humi: Initial %%\n"); 
    printf("R1: OFF, R2: OFF\n"); 
    
    // Update global LCD lines with initial settings
    snprintf(last_lcd_line1, sizeof(last_lcd_line1), "Set T:%.1fC", threshold_temp);
    snprintf(last_lcd_line2, sizeof(last_lcd_line2), "Set H:%d%%", threshold_humi);
    write_to_lcd(last_lcd_line1, last_lcd_line2);
    printf("FPGA_LCD_L1: %s\n", last_lcd_line1);
    printf("FPGA_LCD_L2: %s\n", last_lcd_line2);
    fflush(stdout); 

    delay(2000); 

    // Main loop for continuous reading and control
    while (1) {
        read_dht_and_control();
        delay(2000); 
    }

    return 0; 
}
