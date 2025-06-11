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
int relay1_on = 0; // 0 for OFF (HIGH), 1 for ON (LOW)
int relay2_on = 0; // 0 for OFF (HIGH), 1 for ON (LOW)

// User input thresholds
float threshold_temp;
int threshold_humi;

// Function to write two lines to the FPGA TEXT LCD
int write_to_lcd(const char* line1, const char* line2) {
    int dev;
    unsigned char string[MAX_BUFF];
    memset(string, 0, sizeof(string));

    if (strlen(line1) > LINE_BUFF || strlen(line2) > LINE_BUFF) {
        return -1;
    }

    dev = open(FPGA_TEXT_LCD_DEVICE, O_WRONLY);
    if (dev < 0) {
        return -1; // Device open error - silently fail as requested
    }

    strncpy((char*)string, line1, LINE_BUFF);
    memset(string + strlen((char*)string), ' ', LINE_BUFF - strlen((char*)string));
    strncpy((char*)string + LINE_BUFF, line2, LINE_BUFF);
    memset(string + LINE_BUFF + strlen((char*)string + LINE_BUFF), ' ', LINE_BUFF - strlen((char*)string + LINE_BUFF));

    write(dev, string, MAX_BUFF);
    close(dev);
    return 0;
}

// Signal handler for clean exit
void cleanup_handler(int signum) {
    if (signum == SIGINT) {
        // printf("\nCaught SIGINT. Cleaning up...\n"); // Debug message, can be removed
        write_to_lcd("CHECK END!", "          "); // FPGA LCD에 메시지 출력
        
        // 릴레이 끄기 (안전한 상태로 돌리기)
        digitalWrite(RELAY1_PIN, HIGH); // OFF (active-low)
        digitalWrite(RELAY2_PIN, HIGH); // OFF (active-low)
        
        delay(500); // 메시지가 LCD에 표시될 시간을 줍니다.
        exit(0); // 프로그램 종료
    }
}

void read_dht_and_control() {
    uint8_t laststate = HIGH;
    uint8_t counter = 0;
    uint8_t j = 0, i;
    data[0] = data[1] = data[2] = data[3] = data[4] = 0;

    pinMode(DHT_PIN, OUTPUT);
    digitalWrite(DHT_PIN, HIGH);
    delay(100);
    digitalWrite(DHT_PIN, LOW);
    delay(18);
    digitalWrite(DHT_PIN, HIGH);
    delayMicroseconds(40);
    pinMode(DHT_PIN, INPUT);

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

    if ((j >= 40) && (data[4] == ((data[0] + data[1] + data[2] + data[3]) & 0xFF))) {
        float h = (float)((data[0] << 8) + data[1]) / 10;
        if (h > 100.0) h = 100.0;
        if (h < 0.0) h = 0.0;

        float c = (float)(((data[2] & 0x7F) << 8) + data[3]) / 10;
        if (data[2] & 0x80) c = -c;
        if (c > 125.0) c = 125.0;
        if (c < -40.0) c = -40.0;

        // Control relays
        if (c >= threshold_temp + 0.5 && !relay1_on) {
            digitalWrite(RELAY1_PIN, LOW); // ON
            relay1_on = 1;
        } else if (c <= threshold_temp - 0.5 && relay1_on) {
            digitalWrite(RELAY1_PIN, HIGH); // OFF
            relay1_on = 0;
        }

        if (h >= threshold_humi + 5 && !relay2_on) {
            digitalWrite(RELAY2_PIN, LOW); // ON
            relay2_on = 1;
        } else if (h <= threshold_humi - 5 && relay2_on) {
            digitalWrite(RELAY2_PIN, HIGH); // OFF
            relay2_on = 0;
        }
        
        // Print to standard output for GUI (new format)
        printf("Temp: %.1f C, Humi: %.1f %%\n", c, h);
        printf("R1: %s, R2: %s\n", relay1_on ? "ON" : "OFF", relay2_on ? "ON" : "OFF");

        char lcd_line1[LINE_BUFF + 1], lcd_line2[LINE_BUFF + 1];
        snprintf(lcd_line1, sizeof(lcd_line1), "Temp: %.1fC %s", c, relay1_on ? "ON" : "OFF");
        snprintf(lcd_line2, sizeof(lcd_line2), "Humi: %.1f%% %s", h, relay2_on ? "ON" : "OFF");

        write_to_lcd(lcd_line1, lcd_line2);
        printf("FPGA_LCD_L1: %s\n", lcd_line1);
        printf("FPGA_LCD_L2: %s\n", lcd_line2);

    } else {
        // DHT22 data not ready or checksum error.
        // Print default/N/A values to maintain consistent output structure for Python GUI
        printf("Temp: N/A C, Humi: N/A %%\n");
        printf("R1: N/A, R2: N/A\n");

        // Keep LCD updated with sensor error, even if not shown on console
        write_to_lcd("Sensor Error", "Check DHT22");
        printf("FPGA_LCD_L1: Sensor Error\n");
        printf("FPGA_LCD_L2: Check DHT22\n");
    }
}

int main(int argc, char* argv[]) {
    // Register signal handler for SIGINT
    if (signal(SIGINT, cleanup_handler) == SIG_ERR) {
        // Consider alternative error handling if signal fails
        return 1;
    }

    if (argc != 3) {
        printf("Usage: %s <TEMP-SET> <HUMI-SET>\n", argv[0]);
        // Also print default LCD output for initial state
        printf("R1: N/A, R2: N/A\n"); // Consistent output
        printf("FPGA_LCD_L1: Usage:\n");
        printf("FPGA_LCD_L2: <TEMP> <HUMI>\n");
        return 1;
    }

    threshold_temp = atof(argv[1]);
    threshold_humi = atoi(argv[2]);

    // Initial state output for GUI. This will be the first set of lines Python reads.
    printf("Temp: Initial C, Humi: Initial %%\n"); // Placeholder values
    printf("R1: OFF, R2: OFF\n"); // Assuming they start off initially

    char lcd_set_line1[LINE_BUFF + 1];
    char lcd_set_line2[LINE_BUFF + 1];
    snprintf(lcd_set_line1, sizeof(lcd_set_line1), "Set T:%.1fC", threshold_temp);
    snprintf(lcd_set_line2, sizeof(lcd_set_line2), "Set H:%d%%", threshold_humi);
    write_to_lcd(lcd_set_line1, lcd_set_line2);
    printf("FPGA_LCD_L1: %s\n", lcd_set_line1);
    printf("FPGA_LCD_L2: %s\n", lcd_set_line2);
    
    delay(2000); // Show initial settings for a moment

    if (wiringPiSetup() == -1) {
        // If wiringPi fails, provide distinct output for GUI
        printf("Temp: WiringPi Error, Humi: WiringPi Error\n");
        printf("R1: ERROR, R2: ERROR\n");
        write_to_lcd("WiringPi Err", "Setup Failed");
        printf("FPGA_LCD_L1: WiringPi Err\n");
        printf("FPGA_LCD_L2: Setup Failed\n");
        return 1;
    }

    pinMode(RELAY1_PIN, OUTPUT);
    pinMode(RELAY2_PIN, OUTPUT);
    digitalWrite(RELAY1_PIN, HIGH); // Relays OFF at start (active-low)
    digitalWrite(RELAY2_PIN, HIGH); // Relays OFF at start (active-low)

    while (1) {
        read_dht_and_control();
        delay(2000);
    }

    return 0;
}
