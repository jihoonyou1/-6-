#include <wiringPi.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>

#define DHTPIN 19
#define MAX_TIMINGS 85

int dht_data[5] = {0, 0, 0, 0, 0};

void read_dht22()
{
    uint8_t last_state = HIGH;
    uint8_t counter = 0;
    uint8_t j = 0, i;

    dht_data[0] = dht_data[1] = dht_data[2] = dht_data[3] = dht_data[4] = 0;

    pinMode(DHTPIN, OUTPUT);
    digitalWrite(DHTPIN, LOW);
    usleep(18000);
    digitalWrite(DHTPIN, HIGH);
    usleep(40);
    pinMode(DHTPIN, INPUT);

    for (i = 0; i < MAX_TIMINGS; i++) {
        counter = 0;
        while (digitalRead(DHTPIN) == last_state) {
            counter++;
            if (counter == 255) break;
        }
        last_state = digitalRead(DHTPIN);

        if (counter == 255) break;

        if ((i >= 4) && (i % 2 == 0)) {
            dht_data[j / 8] <<= 1;
            if (counter > 50)
                dht_data[j / 8] |= 1;
            j++;
        }
    }

    if ((j >= 40) &&
        (dht_data[4] == ((dht_data[0] + dht_data[1] + dht_data[2] + dht_data[3]) & 0xFF))) {
        printf("Temp: %.1f°C Humidity: %.1f%%\n", (float)dht_data[2], (float)dht_data[0]);
    } else {
        printf("Sensor error. Retrying...\n");
    }
}

int main()
{
    if (wiringPiSetupGpio() == -1) {
        printf("WiringPi initialization failed!\n");
        return -1;
    }

    while (1) {
        read_dht22();
        sleep(2);
    }

    return 0;
}
