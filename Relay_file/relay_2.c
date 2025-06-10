#include <wiringPi.h>
#include <stdio.h>
#include <stdlib.h>

#define RELAY1_PIN 5  // GPIO24 (wiringPi 5번)
#define RELAY2_PIN 25  // GPIO26 (wiringPi 25번)

int main(void) {
    int temperature, humidity;
    int relay1_on = 0;
    int relay2_on = 0;

    if (wiringPiSetup() == -1) {
        printf("wiringPi initialization failed!\n");
        return 1;
    }

    pinMode(RELAY1_PIN, OUTPUT);
    pinMode(RELAY2_PIN, OUTPUT);
    digitalWrite(RELAY1_PIN, HIGH);  // OFF
    digitalWrite(RELAY2_PIN, HIGH);  // OFF

    while (1) {
        printf("Input temperature: ");
        scanf("%d", &temperature);
        printf("Input humidity: ");
        scanf("%d", &humidity);

        // 릴레이1: 온도 기준
        if (!relay1_on && temperature >= 50) {
            printf("Relay1 ON (Temp)\n");
            digitalWrite(RELAY1_PIN, LOW);
            relay1_on = 1;
        } else if (relay1_on && temperature <= 30) {
            printf("Relay1 OFF (Temp)\n");
            digitalWrite(RELAY1_PIN, HIGH);
            relay1_on = 0;
        } else {
            printf("Relay1 status: %s\n", relay1_on ? "ON" : "OFF");
        }

        // 릴레이2: 습도 기준
        if (!relay2_on && humidity >= 70) {
            printf("Relay2 ON (Humidity)\n");
            digitalWrite(RELAY2_PIN, LOW);
            relay2_on = 1;
        } else if (relay2_on && humidity <= 50) {
            printf("Relay2 OFF (Humidity)\n");
            digitalWrite(RELAY2_PIN, HIGH);
            relay2_on = 0;
        } else {
            printf("Relay2 status: %s\n", relay2_on ? "ON" : "OFF");
        }

        delay(4000);  // 4초 대기
    }

    return 0;
}
