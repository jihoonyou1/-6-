#include <wiringPi.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#define MAX_TIMINGS 85
#define DHT_PIN 24

int data[5] = {0, 0, 0, 0, 0};

void read_dht22() {
    int last_state = HIGH;
    int j = 0;

    data[0] = data[1] = data[2] = data[3] = data[4] = 0;

    // 준비: 신호 시작
    pinMode(DHT_PIN, OUTPUT);
    digitalWrite(DHT_PIN, LOW);
    delay(18);  // 최소 1ms 필요
    digitalWrite(DHT_PIN, HIGH);
    delayMicroseconds(40);

    // 센서에서 신호 읽기
    pinMode(DHT_PIN, INPUT);

    for (int i = 0; i < MAX_TIMINGS; i++) {
        int count = 0;
        while (digitalRead(DHT_PIN) == last_state) {
            count++;
            delayMicroseconds(1);
            if (count == 255)
                break;
        }

        last_state = digitalRead(DHT_PIN);

        if (count == 255)
            break;

        // 처음 3개 신호는 무시
        if ((i >= 4) && (i % 2 == 0)) {
            data[j / 8] <<= 1;
            if (count > 50)
                data[j / 8] |= 1;
            j++;
        }
    }

    // 체크섬 확인
    if ((j >= 40) &&
        (data[4] == ((data[0] + data[1] + data[2] + data[3]) & 0xFF))) {
        float humidity = ((data[0] << 8) + data[1]) * 0.1;
        float temperature = (((data[2] & 0x7F) << 8) + data[3]) * 0.1;
        if (data[2] & 0x80) temperature *= -1;

        printf("온도: %.1f°C  습도: %.1f%%\n", temperature, humidity);
    } else {
        printf("DHT22 데이터 읽기 실패\n");
    }
}

int main(void) {
    printf("DHT22 센서 데이터 읽기 시작 (GPIO24)\n");

    if (wiringPiSetup() == -1) {
        fprintf(stderr, "wiringPi 초기화 실패\n");
        exit(1);
    }

    while (1) {
        read_dht22();
        delay(2000);  // 2초마다 측정
    }

    return 0;
}

