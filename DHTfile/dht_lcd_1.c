#include <wiringPi.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

#define MAX_TIMINGS     85
#define DHT_PIN         5  // WiringPi 기준
#define FPGA_TEXT_LCD_DEVICE "/dev/fpga_text_lcd"
#define MAX_BUFF        32
#define LINE_BUFF       16

int data[5] = { 0, 0, 0, 0, 0 };

int write_to_lcd(const char* line1, const char* line2) {
    int dev;
    unsigned char string[MAX_BUFF];
    memset(string, 0, sizeof(string));

    dev = open(FPGA_TEXT_LCD_DEVICE, O_WRONLY);
    if (dev < 0) {
        printf("Device open error: %s\n", FPGA_TEXT_LCD_DEVICE);
        return -1;
    }

    // 첫 줄
    int len1 = strlen(line1);
    strncpy((char*)string, line1, len1);
    memset(string + len1, ' ', LINE_BUFF - len1);

    // 둘째 줄
    int len2 = strlen(line2);
    strncpy((char*)string + LINE_BUFF, line2, len2);
    memset(string + LINE_BUFF + len2, ' ', LINE_BUFF - len2);

    write(dev, string, MAX_BUFF);
    close(dev);
    return 0;
}

void read_dht22_data()
{
    uint8_t laststate = HIGH;
    uint8_t counter = 0;
    uint8_t j = 0, i;
    data[0] = data[1] = data[2] = data[3] = data[4] = 0;

    // Start signal
    pinMode(DHT_PIN, OUTPUT);
    digitalWrite(DHT_PIN, LOW);
    delay(20);  // 최소 1ms 이상 필요. 20ms 안정적
    pinMode(DHT_PIN, INPUT);

    // 읽기
    for (i = 0; i < MAX_TIMINGS; i++) {
        counter = 0;
        while (digitalRead(DHT_PIN) == laststate) {
            counter++;
            delayMicroseconds(1);
            if (counter == 255) break;
        }
        laststate = digitalRead(DHT_PIN);
        if (counter == 255) break;

        // 유효 데이터 비트 (i >= 4 이후 짝수)
        if ((i >= 4) && (i % 2 == 0)) {
            data[j / 8] <<= 1;
            if (counter > 50)  // DHT22는 1비트가 약 70us (높은 파형이 길수록 1)
                data[j / 8] |= 1;
            j++;
        }
    }

    // Checksum 검증
    if (j >= 40 && data[4] == ((data[0] + data[1] + data[2] + data[3]) & 0xFF)) {
        float humidity = ((data[0] << 8) + data[1]) * 0.1;
        float temperature = (((data[2] & 0x7F) << 8) + data[3]) * 0.1;
        if (data[2] & 0x80) temperature *= -1;

        printf("Temp: %.1f°C, Humi: %.1f%%\n", temperature, humidity);

        char line1[LINE_BUFF + 1], line2[LINE_BUFF + 1];
        snprintf(line1, sizeof(line1), "Temp: %.1f C", temperature);
        snprintf(line2, sizeof(line2), "Humi: %.1f %%", humidity);
        write_to_lcd(line1, line2);
    } else {
        printf("Data not good, skip\n");
        write_to_lcd("Sensor Error", "Retrying...");
    }
}

int main(void)
{
    printf("DHT22 to FPGA Text LCD\n");

    if (wiringPiSetup() == -1) {
        fprintf(stderr, "wiringPi 초기화 실패\n");
        return 1;
    }

    while (1) {
        read_dht22_data();
        delay(4000);  // 4초 간격으로 읽기
    }

    return 0;
}
