#include <wiringPi.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

#define MAX_TIMINGS 85
#define DHT_PIN 2         // WiringPi pin for DHT22
#define RELAY1_PIN 5      // WiringPi pin for Temperature control relay
#define RELAY2_PIN 25     // WiringPi pin for Humidity control relay

int data[5] = { 0, 0, 0, 0, 0 };
int relay1_on = 0; // 0 for OFF (HIGH), 1 for ON (LOW)
int relay2_on = 0; // 0 for OFF (HIGH), 1 for ON (LOW)
float threshold_temp;
int threshold_humi;

void read_dht_and_control() {
    uint8_t laststate = HIGH;
    uint8_t counter = 0;
    uint8_t j = 0, i;
    data[0] = data[1] = data[2] = data[3] = data[4] = 0;

    pinMode(DHT_PIN, OUTPUT);
    digitalWrite(DHT_PIN, HIGH);
    delay(100);

    // Request data from DHT22
    digitalWrite(DHT_PIN, LOW);
    delay(18);
    digitalWrite(DHT_PIN, HIGH);
    delayMicroseconds(40);
    pinMode(DHT_PIN, INPUT);

    // Read DHT22 response
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
        if (h > 100.0) h = 100.0;
        if (h < 0.0) h = 0.0;

        float c = (float)(((data[2] & 0x7F) << 8) + data[3]) / 10;
        if (data[2] & 0x80) c = -c;
        if (c > 125.0) c = 125.0;
        if (c < -40.0) c = -40.0;

        // Control relays (active-low)
        if (c >= threshold_temp + 0.5 && !relay1_on) {
            digitalWrite(RELAY1_PIN, LOW); // ON
            relay1_on = 1;
        } else if (c <= threshold_temp - 0.5 && relay1_on) {
            digitalWrite(RELAY1_PIN, HIGH); // OFF
            relay1_on = 0;
        }

        if (h >= threshold_humi + 5 && !relay2_on) {
            digitalWrite(RELAY2_PIN, LOW); // ON
            relay2_on = 1;
        } else if (h <= threshold_humi - 5 && relay2_on) {
            digitalWrite(RELAY2_PIN, HIGH); // OFF
            relay2_on = 0;
        }
        
        printf("Humidity = %.1f %% (Relay: %s) Temperature = %.1f *C (Relay: %s)\n",
               h, relay2_on ? "ON" : "OFF",
               c, relay1_on ? "ON" : "OFF");
    } else {
        printf("DHT22 data not ready or checksum error.\n");
    }
}

int main(int argc, char* argv[]) {
    if (argc != 3) {
        printf("Usage: %s <TEMP-SET> <HUMI-SET>\n", argv[0]);
        return 1;
    }

    threshold_temp = atof(argv[1]);
    threshold_humi = atoi(argv[2]);

    printf("DHT22 SENSOR - SET TEMP: %.1f°C, SET HUMI: %d%%\n", threshold_temp, threshold_humi);

    if (wiringPiSetup() == -1) {
        printf("WiringPi setup failed!\n");
        return 1;
    }

    pinMode(RELAY1_PIN, OUTPUT);
    pinMode(RELAY2_PIN, OUTPUT);
    digitalWrite(RELAY1_PIN, HIGH); // Relays OFF at start
    digitalWrite(RELAY2_PIN, HIGH); // Relays OFF at start

    while (1) {
        read_dht_and_control();
        delay(2000); // Read and update every 2 seconds
    }

    return 0;
}
