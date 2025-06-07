#include <stdio.h>
#include <stdint.h>
#include <pigpio.h>

#define DHT_PIN 5  //ext_gpio0

int dht22_read(float *temperature, float *humidity) {
    uint8_t bits[5] = {0};
    uint8_t lastState = 1;
    uint8_t counter = 0;
    uint8_t j = 0, i;

    // 1. 시작 신호
    gpioSetMode(DHT_PIN, PI_OUTPUT);
    gpioWrite(DHT_PIN, PI_LOW);
    gpioDelay(20000);  // 20ms
    gpioWrite(DHT_PIN, PI_HIGH);
    gpioDelay(40);     // 40us
    gpioSetMode(DHT_PIN, PI_INPUT);

    // 2. 응답 신호와 데이터 비트 읽기
    // 최대 85번 상태 변화 감지 (응답+40비트)
    lastState = 1;
    for (i = 0; i < 85; i++) {
        counter = 0;
        while (gpioRead(DHT_PIN) == lastState) {
            counter++;
            gpioDelay(1);  // 1us 대기
            if (counter == 255)
                break;
        }
        lastState = gpioRead(DHT_PIN);

        if (counter == 255)
            break;

        // 첫 3번 변화는 시작 신호 무시
        if ((i >= 4) && (i % 2 == 0)) {
            bits[j / 8] <<= 1;
            if (counter > 50)  // 50us 이상이면 1로 판단
                bits[j / 8] |= 1;
            j++;
        }
    }

    // 3. 40비트 수신 확인 및 체크섬 검사
    if (j >= 40) {
        uint8_t checksum = bits[0] + bits[1] + bits[2] + bits[3];
        if (bits[4] == checksum) {
            *humidity = ((bits[0] << 8) | bits[1]) * 0.1f;
            *temperature = (((bits[2] & 0x7F) << 8) | bits[3]) * 0.1f;
            if (bits[2] & 0x80)
                *temperature *= -1;
            return 1;
        }
    }

    return 0;
}

int main() {
    if (gpioInitialise() < 0) {
        printf("pigpio ERROR\n");
        return 1;
    }

    float temperature = 0.0, humidity = 0.0;

    while (1) {
        if (dht22_read(&temperature, &humidity)) {
            printf("Temperature: %.1f°C, Humidity: %.1f%%\n", temperature, humidity);
        } else {
            printf("DHT22 read ERROR\n");
        }
        gpioDelay(2000000);  // 2초 대기
    }

    gpioTerminate();
    return 0;
}


