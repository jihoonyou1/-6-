#include <stdio.h>
#include <pigpio.h>
#include <stdlib.h>
#include <stdint.h>

#define DHT_PIN 5 

int dht22_read(float *temperature, float *humidity) {
    uint8_t data[5] = {0};
    int bitidx = 0;

    // 신호 초기화
    gpioSetMode(DHT_PIN, PI_OUTPUT);
    gpioWrite(DHT_PIN, PI_LOW);
    gpioDelay(1000 * 20); // 20ms
    gpioWrite(DHT_PIN, PI_HIGH);
    gpioDelay(40); // 40us
    gpioSetMode(DHT_PIN, PI_INPUT);

    // 응답 대기
    int count = 0;
    while (gpioRead(DHT_PIN) == PI_HIGH) {
        gpioDelay(1);
        if (++count > 100) return 0;
    }

    // 응답 신호 (LOW-HIGH-LOW)
    count = 0;
    while (gpioRead(DHT_PIN) == PI_LOW) {
        gpioDelay(1);
        if (++count > 100) return 0;
    }

    count = 0;
    while (gpioRead(DHT_PIN) == PI_HIGH) {
        gpioDelay(1);
        if (++count > 100) return 0;
    }

    // 40비트 데이터 수신
    for (int i = 0; i < 40; i++) {
        // LOW 신호 길이 측정
        count = 0;
        while (gpioRead(DHT_PIN) == PI_LOW) {
            gpioDelay(1);
            if (++count > 100) return 0;
        }

        // HIGH 신호 길이 측정
        count = 0;
        while (gpioRead(DHT_PIN) == PI_HIGH) {
            gpioDelay(1);
            if (++count > 100) return 0;
        }

        // 26~28us면 0, ~70us면 1
        data[i / 8] <<= 1;
        if (count > 40) {
            data[i / 8] |= 1;
        }
    }

    // 체크섬 검증
    if ((uint8_t)(data[0] + data[1] + data[2] + data[3]) != data[4]) return 0;

    *humidity = ((data[0] << 8) | data[1]) * 0.1;
    *temperature = (((data[2] & 0x7F) << 8) | data[3]) * 0.1;
    if (data[2] & 0x80) *temperature *= -1;

    return 1;
}

int main() {
    float temperature = 0.0, humidity = 0.0;

    if (gpioInitialise() < 0) {
        printf("pigpio ERROR\n");
        return 1;
    }

    while (1) {
        if (dht22_read(&temperature, &humidity)) {
            printf("Temperature: %.1f°C, Humidity: %.1f%%\n", temperature, humidity);
        } else {
            printf("READ (ERROR)\n");
        }
        gpioDelay(2000000); // 2초
    }

    gpioTerminate();
    return 0;
}
