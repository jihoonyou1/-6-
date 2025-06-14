#include <wiringPi.h> // wiringPi 라이브러리 사용
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>   // For file operations (LCD and LED device)
#include <string.h>  // For string operations
#include <signal.h>  // For signal handling

#define MAX_TIMINGS 85
#define DHT_PIN 2         // WiringPi pin for DHT22 (GPIO27) - 이 값은 실제 연결된 핀 번호로 확인해주세요.
#define FPGA_TEXT_LCD_DEVICE "/dev/fpga_text_lcd" // FPGA TEXT LCD device path
#define FPGA_LED_DEVICE "/dev/fpga_led" // FPGA LED device path
#define MAX_BUFF 32       // Total buffer size for LCD (2 lines * 16 chars)
#define LINE_BUFF 16      // Characters per LCD line

int data[5] = { 0, 0, 0, 0, 0 };

// Global variables for LED states
// Use a single byte to represent 8 LEDs.
// Bit 0-3 for Temperature LEDs (D1-D4)
// Bit 4-7 for Humidity LEDs (D5-D8)
unsigned char current_led_state = 0; // All LEDs off initially

// User input thresholds
float threshold_temp;
int threshold_humi;

// Global variables to hold the last successfully read sensor data
float last_temp_c = -999.9; // Use an unlikely value to indicate no data yet
float last_humi = -999.9;

// Function to write two lines to the FPGA TEXT LCD
// Returns 0 on success, -1 on failure
int write_to_lcd(const char* line1, const char* line2) {
    int dev;
    unsigned char string[MAX_BUFF];
    memset(string, 0, sizeof(string));

    dev = open(FPGA_TEXT_LCD_DEVICE, O_WRONLY);
    if (dev < 0) {
        return -1;
    }

    strncpy((char*)string, line1, LINE_BUFF); 
    if (strlen((char*)string) < LINE_BUFF) { 
        memset(string + strlen((char*)string), ' ', LINE_BUFF - strlen((char*)string)); 
    }

    strncpy((char*)string + LINE_BUFF, line2, LINE_BUFF); 
    if (strlen((char*)string + LINE_BUFF) < LINE_BUFF) { 
        memset(string + LINE_BUFF + strlen((char*)string + LINE_BUFF), ' ', LINE_BUFF - strlen((char*)string + LINE_BUFF));
    }

    write(dev, string, MAX_BUFF);
    close(dev);
    return 0;
}

// Function to control FPGA LEDs
// Takes an 8-bit value where each bit corresponds to an LED
// Returns 0 on success, -1 on failure
int write_to_fpga_led(unsigned char value) {
    int dev;
    dev = open(FPGA_LED_DEVICE, O_WRONLY);
    if (dev < 0) {
        return -1;
    }
    write(dev, &value, 1);
    close(dev);
    return 0;
}

// Signal handler for clean exit (e.g., on Ctrl+C or GUI close)
void cleanup_handler(int signum) {
    if (signum == SIGINT) {
        write_to_lcd("CHECK END!", "          ");

        write_to_fpga_led(0x00); // All LEDs off
        
        delay(500); 

        exit(0); 
    }
}

// Function to read DHT22, control LEDs, and print formatted output
void read_dht_and_control() {
    uint8_t laststate = HIGH;
    uint8_t counter = 0;
    uint8_t j = 0, i;
    data[0] = data[1] = data[2] = data[3] = data[4] = 0;

    // DHT22 communication sequence using WiringPi
    pinMode(DHT_PIN, OUTPUT);
    digitalWrite(DHT_PIN, HIGH);
    delay(100); 
    digitalWrite(DHT_PIN, LOW);
    delay(18);
    digitalWrite(DHT_PIN, HIGH);
    delayMicroseconds(40);
    pinMode(DHT_PIN, INPUT);

    // Read DHT22 response bits using WiringPi
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

    // 각 LED 그룹의 상태를 개별적으로 계산할 임시 변수
    unsigned char temp_led_segment = 0; // D1-D4 (하위 4비트)
    unsigned char humi_led_segment = 0; // D5-D8 (상위 4비트)

    if (j >= 40 && (data[4] == ((data[0] + data[1] + data[2] + data[3]) & 0xFF))) {
        float h = (float)((data[0] << 8) + data[1]) / 10;
        if (h > 100.0) h = 100.0;
        if (h < 0.0) h = 0.0;

        float c = (float)(((data[2] & 0x7F) << 8) + data[3]) / 10;
        if (data[2] & 0x80) c = -c;
        if (c > 125.0) c = 125.0;
        if (c < -40.0) c = -40.0;

        last_temp_c = c;
        last_humi = h;

        // ******** 수정된 부분: TEMP LED (D1-D4) 제어에 0xF0 마스크 사용 ********
        if (c >= threshold_temp + 0.5) {
            temp_led_segment = 0xF0; // D1-D4 켜기 (FPGA 비트 매핑이 반대라고 가정)
        } else if (c <= threshold_temp - 0.5) {
            temp_led_segment = 0x00; // D1-D4 끄기
        } else {
            // 현재 온도 LED 상태를 유지 (current_led_state에서 상위 4비트만 가져와서 TEMP LED로 사용)
            temp_led_segment = (current_led_state & 0xF0); 
        }

        // ******** 수정된 부분: HUMI LED (D5-D8) 제어에 0x0F 마스크 사용 ********
        if (h >= threshold_humi + 5) {
            humi_led_segment = 0x0F; // D5-D8 켜기 (FPGA 비트 매핑이 반대라고 가정)
        } else if (h <= threshold_humi - 5) {
            humi_led_segment = 0x00; // D5-D8 끄기
        } else {
            // 현재 습도 LED 상태를 유지 (current_led_state에서 하위 4비트만 가져와서 HUMI LED로 사용)
            humi_led_segment = (current_led_state & 0x0F); 
        }
        
        // 최종 LED 상태는 두 세그먼트의 합
        current_led_state = temp_led_segment | humi_led_segment;

        write_to_fpga_led(current_led_state);

        // printf 출력 및 LCD 출력도 마스크에 맞게 변경 (하위 비트는 HUMI, 상위 비트는 TEMP로 출력)
        printf("Humidity = %.1f %% (LED: %s) Temperature = %.1f *C (LED: %s)\n",
               last_humi, (current_led_state & 0x0F) ? "ON" : "OFF", // HUMI LED는 이제 0x0F로 확인
               last_temp_c, (current_led_state & 0xF0) ? "ON" : "OFF"); // TEMP LED는 이제 0xF0으로 확인

        char lcd_line1[LINE_BUFF + 1];
        char lcd_line2[LINE_BUFF + 1];
        snprintf(lcd_line1, sizeof(lcd_line1), "Temp:%.1fC %s", last_temp_c, (current_led_state & 0xF0) ? "ON" : "OFF");
        snprintf(lcd_line2, sizeof(lcd_line2), "Humi:%.1f%% %s", last_humi, (current_led_state & 0x0F) ? "ON" : "OFF");
        write_to_lcd(lcd_line1, lcd_line2);

    } else {
        // 데이터 읽기 실패 시, 마지막 유효 데이터와 LED 상태를 계속 표시
        printf("Humidity = %.1f %% (LED: %s) Temperature = %.1f *C (LED: %s)\n",
               last_humi, (current_led_state & 0x0F) ? "ON" : "OFF",
               last_temp_c, (current_led_state & 0xF0) ? "ON" : "OFF");

        char lcd_line1[LINE_BUFF + 1];
        char lcd_line2[LINE_BUFF + 1];
        snprintf(lcd_line1, sizeof(lcd_line1), "Temp:%.1fC %s", last_temp_c, (current_led_state & 0xF0) ? "ON" : "OFF");
        snprintf(lcd_line2, sizeof(lcd_line2), "Humi:%.1f%% %s", last_humi, (current_led_state & 0x0F) ? "ON" : "OFF");
        write_to_lcd(lcd_line1, lcd_line2);
    }
    fflush(stdout);
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
        write_to_lcd("Usage Error", "Check console");
        printf("Humidity = N/A %% (LED: N/A) Temperature = N/A *C (LED: N/A)\n");
        fflush(stdout);
        return 1;
    }

    // Convert command-line arguments to thresholds
    threshold_temp = atof(argv[1]);
    threshold_humi = atoi(argv[2]);

    // Initialize WiringPi
    if (wiringPiSetup() == -1) {
        fprintf(stderr, "WiringPi setup failed!\n");
        write_to_lcd("WiringPi Err", "Setup Failed");
        printf("Humidity = N/A %% (LED: N/A) Temperature = N/A *C (LED: N/A)\n");
        fflush(stdout);
        return 1;
    }

    // Initialize all LEDs to OFF (0x00)
    write_to_fpga_led(0x00);
    
    // Initial LCD messages with settings, and mirror to stdout
    char init_lcd_line1[LINE_BUFF + 1];
    char init_lcd_line2[LINE_BUFF + 1];
    snprintf(init_lcd_line1, sizeof(init_lcd_line1), "Set T:%.1fC", threshold_temp);
    snprintf(init_lcd_line2, sizeof(init_lcd_line2), "Set H:%d%%", threshold_humi);
    write_to_lcd(init_lcd_line1, init_lcd_line2);
    // Initial data for GUI, before first sensor read
    printf("Humidity = N/A %% (LED: N/A) Temperature = N/A *C (LED: N/A)\n");
    fflush(stdout); 

    delay(2000); // Show initial settings for a moment (2 seconds)

    // Main loop for continuous reading and control
    while (1) {
        read_dht_and_control();
        delay(4000); // Read and update every 4 seconds
    }

    return 0; 
}
