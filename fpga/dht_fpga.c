#include <wiringPi.h> // wiringPi 라이브러리 사용
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>   // 파일 연산
#include <string.h>  // 문자열 연산
#include <signal.h>  // 시그널 핸들링

#define MAX_TIMINGS 85
#define DHT_PIN 5        // WPi pin for DHT22 (GPIO27) 
#define FPGA_TEXT_LCD_DEVICE "/dev/fpga_text_lcd" // FPGA TEXT LCD 
#define FPGA_LED_DEVICE "/dev/fpga_led" // FPGA LED  
#define MAX_BUFF 32       
#define LINE_BUFF 16      

int data[5] = { 0, 0, 0, 0, 0 };

// 비트 0-3 은 Temp LED (D1-D4)
// 비트 4-7 은 Humi LED (D5-D8)
unsigned char current_led_state = 0; // All LEDs off 

// 설정 온도 / 습도 함수
float threshold_temp;
int threshold_humi;

// 프로그램 시작 후 센서가 처음으로 읽기 전에 표시할 값
float last_temp_c = -999.9; 
float last_humi = -999.9;

// TEXT LCD 쓰기 함수
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

// LED 제어 함수
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

// 시그널 제어 함수 (CTRL C)
void cleanup_handler(int signum) {
    if (signum == SIGINT) {
        write_to_lcd("CHECK END!", "          ");

        write_to_fpga_led(0x00); // All LEDs off
        
        delay(500); 

        exit(0); 
    }
}

// dht22 센서에서 값 읽기기
void read_dht_and_control() {
    uint8_t laststate = HIGH;
    uint8_t counter = 0;
    uint8_t j = 0, i;
    data[0] = data[1] = data[2] = data[3] = data[4] = 0;

    // DHT22 핀 초기설정 / 준비
    pinMode(DHT_PIN, OUTPUT);
    digitalWrite(DHT_PIN, HIGH);
    delay(100); 
    digitalWrite(DHT_PIN, LOW);
    delay(18);
    digitalWrite(DHT_PIN, HIGH);
    delayMicroseconds(40);
    pinMode(DHT_PIN, INPUT);

    // DHT22 센서로 읽기기
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

    // 온도 : D1 ~ D4, 습도 : D5 ~ D8
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

        if (c >= threshold_temp + 0.5) {
            temp_led_segment = 0xF0; // D1-D4 켜기 
        } else if (c <= threshold_temp - 0.5) {
            temp_led_segment = 0x00; // D1-D4 끄기
        } else {
            // 현재 온도 LED 상태를 유지 
            temp_led_segment = (current_led_state & 0xF0); 
        }

        if (h >= threshold_humi + 5) {
            humi_led_segment = 0x0F; // D5-D8 켜기 
        } else if (h <= threshold_humi - 5) {
            humi_led_segment = 0x00; // D5-D8 끄기
        } else {
            // 현재 습도 LED 상태를 유지 
            humi_led_segment = (current_led_state & 0x0F); 
        }
        
        // 최종 LED 상태는 두 세그먼트의 합
        current_led_state = temp_led_segment | humi_led_segment;

        write_to_fpga_led(current_led_state);

        // printf 출력 및 LCD 출력
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
    while (1) {
        read_dht_and_control();
        delay(4000); // 읽기 / 업데이트는 4초 간격
    }

    return 0; 
}
