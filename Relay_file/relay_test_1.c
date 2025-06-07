#include <wiringPi.h>
#include <stdio.h>
#include <stdlib.h>

#define RELAY_PIN 5  // wiringPi 핀 번호: GPIO24는 wiringPi에서 5번

int main(void) {
    int value;
    int relay_on = 0;

    // wiringPi 초기화
    if (wiringPiSetup() == -1) {
        printf("wiringPi initialization fail!\n");
        return 1;
    }

    pinMode(RELAY_PIN, OUTPUT);
    digitalWrite(RELAY_PIN, HIGH);  // 릴레이 OFF (HIGH가 OFF인 모듈 기준)

    while (1) {
        printf("Input sensor value: ");
        scanf("%d", &value);

        if (!relay_on && value >= 50) {
            printf("Relay ON\n");
            digitalWrite(RELAY_PIN, LOW);  // 릴레이 ON
            relay_on = 1;
        }
        else if (relay_on && value <= 30) {
            printf("Relay OFF\n");
            digitalWrite(RELAY_PIN, HIGH);  // 릴레이 OFF
            relay_on = 0;
        }
        else {
            printf("Relay on ? : %s\n", relay_on ? "ON" : "OFF");
        }

        delay(4000);  // 1초 대기
    }

    return 0;
}
