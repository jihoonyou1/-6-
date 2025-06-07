import RPi.GPIO as GPIO
import time

RELAY_PIN = 24  # ext-GPIO0 => GPIO24
GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT)

relay_on = False  # 현재 릴레이 상태 추적

try:
    while True:
        # 여기에 센서값을 읽는 부분이 들어올 예정이지만,
        # 지금은 수동으로 테스트용 값 입력
        value = int(input("센서 값을 입력하세요: "))  # 예: 온도나 습도 값
        
        if not relay_on and value >= 50:
            print("릴레이 ON")
            GPIO.output(RELAY_PIN, GPIO.LOW)  # 릴레이 ON
            relay_on = True

        elif relay_on and value <= 30:
            print("릴레이 OFF")
            GPIO.output(RELAY_PIN, GPIO.HIGH)  # 릴레이 OFF
            relay_on = False

        else:
            print("릴레이 상태 유지:", "ON" if relay_on else "OFF")

        time.sleep(1)

except KeyboardInterrupt:
    print("프로그램 종료")

finally:
    GPIO.cleanup()
