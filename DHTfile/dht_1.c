#include <wiringPi.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

#define MAX_TIMINGS 85
#define DHT_PIN 2
#define RELAY1_PIN 5
#define RELAY2_PIN 25

int data[5] = { 0, 0, 0, 0, 0 };
int relay1_on = 0;
int relay2_on = 0;
float threshold_temp;
int threshold_humi;

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

        // 릴레이 제어 (±0.5°C, ±5%)
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

        printf("Humidity = %.1f %% (Relay: %s) Temperature = %.1f *C (Relay: %s)\n",
               h, relay2_on ? "ON" : "OFF",
               c, relay1_on ? "ON" : "OFF");
    }
}

int main(int argc, char* argv[]) {
    if (argc != 3) {
        printf("사용법: %s <TEMP-SET> <HUMI-SET>\n", argv[0]);
        return 1;
    }

    threshold_temp = atof(argv[1]);  // 온도 실수형 값으로 변경
    threshold_humi = atoi(argv[2]);

    printf("DHT22 SENSOR - SET TEMP: %.1f°C, SET HUMI: %d%%\n", threshold_temp, threshold_humi);

    if (wiringPiSetup() == -1)
        return 1;

    pinMode(RELAY1_PIN, OUTPUT);
    pinMode(RELAY2_PIN, OUTPUT);
    digitalWrite(RELAY1_PIN, HIGH);
    digitalWrite(RELAY2_PIN, HIGH);

    while (1) {
        read_dht_and_control();
        delay(4000);
    }

    return 0;
}
