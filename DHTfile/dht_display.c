#include <stdio.h>
#include <stdlib.h>
#include <wiringPi.h>
#include <stdint.h>
#include <unistd.h>

#define DHT_PIN 24  // GPIO 핀 번호 설정

void readDHT(int *temperature, int *humidity) {
    uint8_t data[5] = {0};
    uint8_t lastState = HIGH;
    uint8_t counter = 0;
    uint8_t j = 0, i;

    pinMode(DHT_PIN, OUTPUT);
    digitalWrite(DHT_PIN, LOW);
    usleep(18000);
    digitalWrite(DHT_PIN, HIGH);
    usleep(40);
    pinMode(DHT_PIN, INPUT);

    for (i = 0; i < 85; i++) {
        counter = 0;
        while (digitalRead(DHT_PIN) == lastState) {
            counter++;
            if (counter == 255) {
                break;
            }
        }
        lastState = digitalRead(DHT_PIN);
        if (counter == 255) {
            break;
        }

        if ((i >= 3) && (i % 2 == 0)) {
            data[j / 8] <<= 1;
            if (counter > 16) {
                data[j / 8] |= 1;
            }
            j++;
        }
    }

    if ((j >= 40) &&
        (data[4] == ((data[0] + data[1] + data[2] + data[3]) & 0xFF))) {
        *humidity = data[0];
        *temperature = data[2];
    } else {
        *humidity = -1;
        *temperature = -1;
    }
}

int main() {
    if (wiringPiSetup() == -1) {
        printf("WiringPi setup failed!\n");
        return -1;
    }

    int temperature, humidity;
    while (1) {
        readDHT(&temperature, &humidity);
        if (temperature != -1 && humidity != -1) {
            printf("Temp: %d°C  Humidity: %d%%\n", temperature, humidity);
        } else {
            printf("Sensor error, retrying...\n");
        }
        sleep(2);
    }

    return 0;
}
