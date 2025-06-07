#include <wiringPi.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

#define MAX_TIMINGS     85
#define DHT_PIN         5
#define FPGA_TEXT_LCD_DEVICE "/dev/fpga_text_lcd"
#define MAX_BUFF        32
#define LINE_BUFF       16

int data[5] = { 0, 0, 0, 0, 0 };

int write_to_lcd(const char* line1, const char* line2) {
    int dev;
    unsigned char string[MAX_BUFF];
    memset(string, 0, sizeof(string));

    if (strlen(line1) > LINE_BUFF || strlen(line2) > LINE_BUFF) {
        printf("Line too long for LCD!\n");
        return -1;
    }

    dev = open(FPGA_TEXT_LCD_DEVICE, O_WRONLY);
    if (dev < 0) {
        printf("Device open error: %s\n", FPGA_TEXT_LCD_DEVICE);
        return -1;
    }

    strncpy((char*)string, line1, strlen(line1));
    memset(string + strlen(line1), ' ', LINE_BUFF - strlen(line1));

    strncpy((char*)string + LINE_BUFF, line2, strlen(line2));
    memset(string + LINE_BUFF + strlen(line2), ' ', LINE_BUFF - strlen(line2));

    write(dev, string, MAX_BUFF);
    close(dev);
    return 0;
}

void read_dht_data()
{
    uint8_t laststate = HIGH;
    uint8_t counter = 0;
    uint8_t j = 0, i;
    data[0] = data[1] = data[2] = data[3] = data[4] = 0;

    pinMode(DHT_PIN, OUTPUT);
    digitalWrite(DHT_PIN, LOW);
    delay(20);  // increased to 20ms
    pinMode(DHT_PIN, INPUT);

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
        if (h > 100) h = data[0]; // DHT11

        float c = (float)(((data[2] & 0x7F) << 8) + data[3]) / 10;
        if (c > 125) c = data[2]; // DHT11
        if (data[2] & 0x80) c = -c;

        float f = c * 1.8f + 32;

        printf("Humidity = %.1f %% Temperature = %.1f *C (%.1f *F)\n", h, c, f);

        char line1[LINE_BUFF + 1], line2[LINE_BUFF + 1];
        snprintf(line1, sizeof(line1), "Temp: %.1f C", c);
        snprintf(line2, sizeof(line2), "Humi: %.1f %%", h);
        write_to_lcd(line1, line2);
    } else {
        printf("Data not good, skip\n");
        write_to_lcd("Sensor Error", "Retrying...");
    }
}

int main(void)
{
    printf("Raspberry Pi DHT11/DHT22 to FPGA LCD\n");

    if (wiringPiSetup() == -1)
        return 1;

    while (1) {
        read_dht_data();
        delay(4000);  // 4초 간격
    }

    return 0;
}
