#include <wiringPi.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#define DHT_PIN 5 // wiringPi 기준 핀 번호
#define MAX_TIMINGS 85
#define MAX_RETRY 5

int dht22_read(float *temperature, float *humidity) {
    uint8_t bits[5] = {0};
    uint8_t lastState = HIGH;
    int counter = 0;
    uint8_t j = 0, i;
    int retry;

    for (retry = 0; retry < MAX_RETRY; retry++) {
        j = 0;
        for (i = 0; i < 5; i++) bits[i] = 0;

        // 신호 초기화
        pinMode(DHT_PIN, OUTPUT);
        digitalWrite(DHT_PIN, LOW);
        delay(20); // 20ms
        digitalWrite(DHT_PIN, HIGH);
        delayMicroseconds(30);
        pinMode(DHT_PIN, INPUT);

        lastState = HIGH;

        for (i = 0; i < MAX_TIMINGS; i++) {
            counter = 0;
            while (digitalRead(DHT_PIN) == lastState) {
                counter++;
                delayMicroseconds(1);
                if (counter == 1000) break; // 1ms 타임아웃
            }

            lastState = digitalRead(DHT_PIN);
            if (counter == 1000) break;

            // 첫 3변화 무시 (시작 신호)
            if ((i >= 4) && (i % 2 == 0)) {
                bits[j / 8] <<= 1;
                if (counter > 50)
                    bits[j / 8] |= 1;
                j++;
            }
        }

        if (j >= 40) {
            uint8_t checksum = (bits[0] + bits[1] + bits[2] + bits[3]) & 0xFF;
            if (bits[4] == checksum) {
                *humidity = ((bits[0] << 8) + bits[1]) * 0.1;
                *temperature = (((bits[2] & 0x7F) << 8) + bits[3]) * 0.1;
                if (bits[2] & 0x80) *temperature *= -1;
                return 1; // 성공
            }
        }

        delay(100); // 재시도 전 잠시 대기
    }

    return 0; // 실패
}

int main(void) {
    float temp = 0.0, hum = 0.0;

    if (wiringPiSetup() == -1) {
        printf("wiringPi 초기화 실패\n");
        return 1;
    }

    while (1) {
        if (dht22_read(&temp, &hum)) {
            printf("temp: %.1f°C, hum: %.1f%%\n", temp, hum);
        } else {
            printf("ERROR...\n");
        }

        delay(2000); // 2초마다 갱신
    }

    return 0;
}


