#include <wiringPi.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

#define MAX_TIMINGS     85
#define DHT_PIN         2       // GPIO27 (wiringPi 2번)
#define RELAY1_PIN      5       // GPIO24 (wiringPi 5번)
#define RELAY2_PIN      25      // GPIO26 (wiringPi 25번)
#define FPGA_TEXT_LCD_DEVICE "/dev/fpga_text_lcd"
#define MAX_BUFF        32
#define LINE_BUFF       16

int data[5] = { 0, 0, 0, 0, 0 };

// 릴레이 상태 전역변수
int relay1_on = 0;
int relay2_on = 0;

// 사용자 입력 기준값
int threshold_temp;
int threshold_humi;

int write_to_lcd(const char* line1, const char* line2) {
    int dev;
    unsigned char string[MAX_BUFF];
    memset(string, 0, sizeof(string));

    if (strlen(line1) > LINE_BUFF || strlen(line2) > LINE_BUFF) {
        printf("Line too long for LCD!\n");
        return -1;
    }

    dev = open(FPGA_TEXT_LCD_DEVICE, O_WRONLY);
    if (dev < 0) {
        printf("Device open error: %s\n", FPGA_TEXT_LCD_DEVICE);
        return -1;
    }

    strncpy((char*)string, line1, strlen(line1));
    memset(string + strlen(line1), ' ', LINE_BUFF - strlen(line1));
    strncpy((char*)string + LINE_BUFF, line2, strlen(line2));
    memset(string + LINE_BUFF + strlen(line2), ' ', LINE_BUFF - strlen(line2));

    write(dev, string, MAX_BUFF);
    close(dev);
    return 0;
}

void read_dht_and_control() {
    uint8_t laststate = HIGH;
    uint8_t counter = 0;
    uint8_t j = 0, i;
    data[0] = data[1] = data[2] = data[3] = data[4] = 0;

    pinMode(DHT_PIN, OUTPUT);
    digitalWrite(DHT_PIN, LOW);
    delay(20);
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
        if (h > 100) h = data[0];

        float c = (float)(((data[2] & 0x7F) << 8) + data[3]) / 10;
        if (c > 125) c = data[2];
        if (data[2] & 0x80) c = -c;

        float f = c * 1.8f + 32;

        // 사용자 입력 기준값에서 온도는 0.5, 습도는 5 +-
        if (!relay1_on && c >= threshold_temp + 0.5) {
            digitalWrite(RELAY1_PIN, LOW);
            relay1_on = 1;
        } else if (relay1_on && c <= threshold_temp - 0.5) {
            digitalWrite(RELAY1_PIN, HIGH);
            relay1_on = 0;
        }

        if (!relay2_on && h >= threshold_humi + 5) {
            digitalWrite(RELAY2_PIN, LOW);
            relay2_on = 1;
        } else if (relay2_on && h <= threshold_humi - 5) {
            digitalWrite(RELAY2_PIN, HIGH);
            relay2_on = 0;
        }

        printf("Humidity = %.1f %% (Relay: %s) Temperature = %.1f *C (%.1f *F) (Relay: %s)\n",
               h, relay2_on ? "ON" : "OFF",
               c, f, relay1_on ? "ON" : "OFF");

        char line1[LINE_BUFF + 1], line2[LINE_BUFF + 1];
        snprintf(line1, sizeof(line1), "Temp: %.1fC %s", c, relay1_on ? "ON" : "OFF");
        snprintf(line2, sizeof(line2), "Humi: %.1f%% %s", h, relay2_on ? "ON" : "OFF");

        write_to_lcd(line1, line2);
    }
}

int main(void) {
    printf("DHT22 Sensor & Relay Control Start\n");

    if (wiringPiSetup() == -1)
        return 1;

    pinMode(RELAY1_PIN, OUTPUT);
    pinMode(RELAY2_PIN, OUTPUT);
    digitalWrite(RELAY1_PIN, HIGH);
    digitalWrite(RELAY2_PIN, HIGH);

    // 사용자 입력 받기
    printf("SET TEMP: ");
    scanf("%d", &threshold_temp);
    printf("SET HUMI: ");
    scanf("%d", &threshold_humi);

    while (1) {
        read_dht_and_control();
        delay(4000);
    }

    return 0;
}
