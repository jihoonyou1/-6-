import wiringpi
import time

# 릴레이가 연결된 WiringPi 핀 번호 설정 (gpio readall 명령으로 확인한 번호 사용)
# 예를 들어, ext_gpio1이 WiringPi 핀 1번, ext_gpio2가 WiringPi 핀 2번에 연결되었다고 가정
RELAY_A_PIN = 5  # 릴레이 A 모듈에 연결된 WiringPi 핀 번호
RELAY_B_PIN = 25  # 릴레이 B 모듈에 연결된 WiringPi 핀 번호

# WiringPi 모드 설정: WiringPi 핀 번호 체계를 사용
wiringpi.wiringPiSetup()

# 릴레이 핀을 출력 모드로 설정
wiringpi.pinMode(RELAY_A_PIN, wiringpi.OUTPUT)
wiringpi.pinMode(RELAY_B_PIN, wiringpi.OUTPUT)

# 릴레이 초기 상태 설정 (릴레이 모듈에 따라 HIGH/LOW가 켜짐/꺼짐이 다를 수 있음)
# 일반적으로 LOW 신호가 릴레이를 ON 시키는 경우가 많으므로 LOW로 시작
wiringpi.digitalWrite(RELAY_A_PIN, wiringpi.HIGH) # 초기 상태 OFF (전원 인가시 릴레이 딸깍거림 방지)
wiringpi.digitalWrite(RELAY_B_PIN, wiringpi.HIGH) # 초기 상태 OFF

print("릴레이 테스트 시작 (Ctrl+C로 종료)")

try:
    while True:
        # 릴레이 A 켜기
        print(f"릴레이 A ({RELAY_A_PIN}번 핀) ON")
        wiringpi.digitalWrite(RELAY_A_PIN, wiringpi.LOW) # 릴레이 ON (릴레이 모듈에 따라 HIGH일 수도 있음)
        time.sleep(3) # 3초 대기

        # 릴레이 A 끄기
        print(f"릴레이 A ({RELAY_A_PIN}번 핀) OFF")
        wiringpi.digitalWrite(RELAY_A_PIN, wiringpi.HIGH) # 릴레이 OFF
        time.sleep(1) # 1초 대기

        # 릴레이 B 켜기
        print(f"릴레이 B ({RELAY_B_PIN}번 핀) ON")
        wiringpi.digitalWrite(RELAY_B_PIN, wiringpi.LOW) # 릴레이 ON
        time.sleep(3) # 3초 대기

        # 릴레이 B 끄기
        print(f"릴레이 B ({RELAY_B_PIN}번 핀) OFF")
        wiringpi.digitalWrite(RELAY_B_PIN, wiringpi.HIGH) # 릴레이 OFF
        time.sleep(1) # 1초 대기

except KeyboardInterrupt:
    print("\n테스트 종료. 모든 릴레이 OFF.")
    # 프로그램 종료 시 모든 릴레이 끄기
    wiringpi.digitalWrite(RELAY_A_PIN, wiringpi.HIGH)
    wiringpi.digitalWrite(RELAY_B_PIN, wiringpi.HIGH)
    wiringpi.gpio_close() # WiringPi 사용 종료 (선택 사항)
finally:
    # 프로그램 종료 시 GPIO 설정 정리 (WiringPi는 별도의 cleanup 함수가 필요하지 않을 수 있음)
    # 하지만 안전을 위해 릴레이 핀을 HIGH (OFF) 상태로 유지하는 것이 좋습니다.
    pass