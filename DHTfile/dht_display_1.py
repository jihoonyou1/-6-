import adafruit_dht
import board
import time
import sys

sensor = adafruit_dht.DHT22(board.D24)

try:
    while True:
        try:
            temperature = sensor.temperature
            humidity = sensor.humidity

            if temperature is not None and humidity is not None:
                print(f"Temp: {temperature:.1f}°C  Humidity: {humidity:.1f}%")
            else:
                print("Sensor returned None. Retrying...")

        except RuntimeError as e:
            print(f"Sensor error: {e}. Retrying...")

        except OverflowError as e:
            print(f"Overflow error: {e}. Resetting sensor...")
            time.sleep(2)
            continue

        except Exception as e:
            print(f"Unexpected error: {e}")
            sensor.exit()
            sys.exit(1)

        time.sleep(2)

except KeyboardInterrupt:
    print("Program stopped.")
    sensor.exit()
