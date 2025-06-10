#include <wiringPi.h>           // wiringPi 라이브러리 포함 (GPIO 제어용)
#include <stdio.h>              // 표준 입출력 함수 포함
#include <stdlib.h>             // 표준 라이브러리 함수 포함
#include <stdint.h>             // 고정 크기 정수형 포함
#include <unistd.h>             // 유닉스 표준 함수 포함 (open, close 등)
#include <fcntl.h>              // 파일 제어 옵션 포함 (O_WRONLY 등)
#include <string.h>             // 문자열 처리 함수 포함

#define MAX_TIMINGS     85      // DHT 센서 신호 읽기 최대 반복 횟수
#define DHT_PIN         2       // DHT 센서가 연결된 wiringPi 핀 번호 - gpio27 - 2
#define FPGA_TEXT_LCD_DEVICE "/dev/fpga_text_lcd" // LCD 디바이스 파일 경로
#define MAX_BUFF        32      // LCD에 보낼 최대 버퍼 크기 (16*2)
#define LINE_BUFF       16      // LCD 한 줄 최대 문자 수

int data[5] = { 0, 0, 0, 0, 0 }; // 센서 데이터 저장 배열

// LCD에 두 줄의 문자열을 출력하는 함수
int write_to_lcd(const char* line1, const char* line2) {
    int dev;
    unsigned char string[MAX_BUFF];
    memset(string, 0, sizeof(string)); // 버퍼 0으로 초기화

    // 각 줄이 LCD 한 줄 최대 길이를 넘으면 에러
    if (strlen(line1) > LINE_BUFF || strlen(line2) > LINE_BUFF) {
        printf("Line too long for LCD!\n");
        return -1;
    }

    dev = open(FPGA_TEXT_LCD_DEVICE, O_WRONLY); // LCD 디바이스 파일 열기
    if (dev < 0) {
        printf("Device open error: %s\n", FPGA_TEXT_LCD_DEVICE);
        return -1;
    }

    // 첫 번째 줄 복사 후 남은 공간 공백으로 채움
    strncpy((char*)string, line1, strlen(line1));
    memset(string + strlen(line1), ' ', LINE_BUFF - strlen(line1));

    // 두 번째 줄 복사 후 남은 공간 공백으로 채움
    strncpy((char*)string + LINE_BUFF, line2, strlen(line2));
    memset(string + LINE_BUFF + strlen(line2), ' ', LINE_BUFF - strlen(line2));

    write(dev, string, MAX_BUFF); // LCD에 데이터 쓰기
    close(dev);                   // 디바이스 파일 닫기
    return 0;
}

// DHT 센서에서 데이터 읽고 LCD에 출력하는 함수
void read_dht_data()
{
    uint8_t laststate = HIGH;     // 마지막 신호 상태 저장
    uint8_t counter = 0;          // 신호 길이 측정용
    uint8_t j = 0, i;
    data[0] = data[1] = data[2] = data[3] = data[4] = 0; // 데이터 초기화

    pinMode(DHT_PIN, OUTPUT);     // 핀을 출력으로 설정
    digitalWrite(DHT_PIN, LOW);   // 핀 LOW로 20ms 유지(센서 초기화)
    delay(20);                    // 20ms 대기
    pinMode(DHT_PIN, INPUT);      // 핀을 입력으로 전환

    // 센서 신호 읽기
    for (i = 0; i < MAX_TIMINGS; i++) {
        counter = 0;
        while (digitalRead(DHT_PIN) == laststate) {
            counter++;
            delayMicroseconds(1);
            if (counter == 255) break;
        }
        laststate = digitalRead(DHT_PIN);
        if (counter == 255) break;

        // 데이터 비트 추출
        if ((i >= 4) && (i % 2 == 0)) {
            data[j / 8] <<= 1;
            if (counter > 16)
                data[j / 8] |= 1;
            j++;
        }
    }

    // 데이터 유효성 검사 및 LCD 출력
    if ((j >= 40) && (data[4] == ((data[0] + data[1] + data[2] + data[3]) & 0xFF))) {
        float h = (float)((data[0] << 8) + data[1]) / 10;
        if (h > 100) h = data[0]; // DHT11 센서일 경우

        float c = (float)(((data[2] & 0x7F) << 8) + data[3]) / 10;
        if (c > 125) c = data[2]; // DHT11 센서일 경우
        if (data[2] & 0x80) c = -c; // 음수 온도 처리

        float f = c * 1.8f + 32; // 화씨 변환

        printf("Humidity = %.1f %% Temperature = %.1f *C (%.1f *F)\n", h, c, f);

        char line1[LINE_BUFF + 1], line2[LINE_BUFF + 1];
        snprintf(line1, sizeof(line1), "Temp: %.1f C", c);
        snprintf(line2, sizeof(line2), "Humi: %.1f %%", h);
        write_to_lcd(line1, line2); // LCD에 출력
    } else {
        printf("Data not good, skip\n");
        write_to_lcd("Sensor Error", "Retrying..."); // 에러 메시지 출력
    }
}

// 메인 함수
int main(void)
{
    printf("Raspberry Pi DHT11/DHT22 to FPGA LCD\n");

    if (wiringPiSetup() == -1)   // wiringPi 초기화 실패 시 종료
        return 1;

    while (1) {
        read_dht_data();         // 센서 데이터 읽고 LCD 출력
        delay(4000);             // 4초 대기
    }

    return 0;
}
