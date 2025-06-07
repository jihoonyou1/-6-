import RPi.GPIO as GPIO
import time

RELAY_PIN = 17  # BCM 기준 GPIO17 사용

GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT)

try:
    while True:
        print("릴레이 ON")
        GPIO.output(RELAY_PIN, GPIO.LOW)  # LOW로 작동하는 모듈이 많음
        time.sleep(3)

        print("릴레이 OFF")
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        time.sleep(3)

except KeyboardInterrupt:
    print("프로그램 종료")

finally:
    GPIO.cleanup()


