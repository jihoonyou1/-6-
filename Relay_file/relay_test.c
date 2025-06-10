#include <wiringPi.h>
#include <stdio.h>

#define RELAY1_PIN  5   // GPIO24 (wiringPi 5번)
#define RELAY2_PIN  25  // GPIO26 (wiringPi 25번)

void relay_test() {
    printf("Relay Test Start\n");

    wiringPiSetup();
    pinMode(RELAY1_PIN, OUTPUT);
    pinMode(RELAY2_PIN, OUTPUT);

    printf("Relay1 ON\n");
    digitalWrite(RELAY1_PIN, LOW); // 릴레이 ON (Low 트리거 방식)
    delay(2000);

    printf("Relay1 OFF\n");
    digitalWrite(RELAY1_PIN, HIGH); // 릴레이 OFF
    delay(2000);

    printf("Relay2 ON\n");
    digitalWrite(RELAY2_PIN, LOW); // 릴레이 ON
    delay(2000);

    printf("Relay2 OFF\n");
    digitalWrite(RELAY2_PIN, HIGH); // 릴레이 OFF
    delay(2000);

    printf("Relay Test End\n");
}

int main() {
    relay_test();
    return 0;
}
