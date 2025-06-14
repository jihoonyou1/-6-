#!/bin/bash

# --- 0. dht_fpga C 코드 컴파일 (매번 재부팅 시 컴파일 필요하다고 가정) ---
echo "Compiling dht_fpga C code..."
# 컴파일러가 있는 경로로 이동
cd /home/pi/-6-/fpga/

# 컴파일 실행
sudo gcc -o dht_fpga dht_fpga.c -lwiringPi >/dev/null 2>&1

# 컴파일 성공 여부 확인
if [ $? -eq 0 ]; then
    echo "dht_fpga compiled successfully."
    chmod +x dht_fpga # 컴파일 성공 후 실행 권한 부여
else
    echo "Failed to compile dht_fpga. Please check dht_fpga.c or wiringPi library."
    exit 1 # 컴파일 실패 시 스크립트 종료
fi

# 다시 모듈 디렉토리로 이동 (아래 insmod를 위해)
cd /home/pi/Modules/

# --- 1. 드라이버 모듈 로드 (이미 로드되어 있지 않을 때만) ---
echo "Checking and loading FPGA drivers..."

# fpga_interface_driver.ko
if ! lsmod | grep -q 'fpga_interface_driver'; then
    echo "Loading fpga_interface_driver..."
    sudo insmod fpga_interface_driver.ko >/dev/null 2>&1
    if [ $? -ne 0 ]; then echo "Failed to load fpga_interface_driver."; fi
else
    echo "fpga_interface_driver is already loaded."
fi

# fpga_text_lcd_driver.ko
if ! lsmod | grep -q 'fpga_text_lcd_driver'; then
    echo "Loading fpga_text_lcd_driver..."
    sudo insmod fpga_text_lcd_driver.ko >/dev/null 2>&1
    if [ $? -ne 0 ]; then echo "Failed to load fpga_text_lcd_driver."; fi
else
    echo "fpga_text_lcd_driver is already loaded."
fi

# fpga_led_driver.ko
if ! lsmod | grep -q 'fpga_led_driver'; then
    echo "Loading fpga_led_driver..."
    sudo insmod fpga_led_driver.ko >/dev/null 2>&1
    if [ $? -ne 0 ]; then echo "Failed to load fpga_led_driver."; fi
else
    echo "fpga_led_driver is already loaded."
fi

# --- 2. 장치 노드 생성 및 권한 설정 ---
echo "Creating and setting permissions for device nodes..."

# 이 부분은 현재 디렉토리에서 실행될 수 있으나, 항상 절대 경로를 쓰는 것이 좋습니다.
sudo rm -f /dev/fpga_text_lcd
sudo mknod /dev/fpga_text_lcd c 263 0
sudo chmod 666 /dev/fpga_text_lcd

sudo rm -f /dev/fpga_led
sudo mknod /dev/fpga_led c 260 0
sudo chmod 666 /dev/fpga_led

# --- 3. GUI 파일 실행 ---
echo "Launching GUI application..."
# GUI 파일의 정확한 절대 경로를 사용하세요.
python3 /home/pi/-6-/fpga/gui_fpga.py

exit 0
