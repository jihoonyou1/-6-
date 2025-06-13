#include <wiringPi.h>
#include <stdio.h>
#include <stdlib.h>

#define RELAY_A_PIN 1 // WiringPi pin for Relay A
#define RELAY_B_PIN 2 // WiringPi pin for Relay B

int main(void) {
    if (wiringPiSetup() == -1) {
        fprintf(stderr, "WiringPi init failed!\n");
        return 1;
    }

    pinMode(RELAY_A_PIN, OUTPUT);
    pinMode(RELAY_B_PIN, OUTPUT);

    // Set initial state to OFF (HIGH for most relay modules)
    digitalWrite(RELAY_A_PIN, HIGH);
    digitalWrite(RELAY_B_PIN, HIGH);

    printf("Starting relay test (Ctrl+C to exit).\n");

    while (1) {
        // Turn Relay A ON
        printf("Relay A ON\n");
        digitalWrite(RELAY_A_PIN, LOW); // ON
        delay(3000); // 3 seconds

        // Turn Relay A OFF
        printf("Relay A OFF\n");
        digitalWrite(RELAY_A_PIN, HIGH); // OFF
        delay(1000); // 1 second

        // Turn Relay B ON
        printf("Relay B ON\n");
        digitalWrite(RELAY_B_PIN, LOW); // ON
        delay(3000); // 3 seconds

        // Turn Relay B OFF
        printf("Relay B OFF\n");
        digitalWrite(RELAY_B_PIN, HIGH); // OFF
        delay(1000); // 1 second
    }

    // This part is generally not reached in an infinite loop
    digitalWrite(RELAY_A_PIN, HIGH); // Ensure OFF state on exit
    digitalWrite(RELAY_B_PIN, HIGH); // Ensure OFF state on exit

    return 0;
}
