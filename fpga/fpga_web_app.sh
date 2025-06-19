#!/usr/bin/env bash

# =================================================================
# FPGA Driver Setting & Application Launcher
#
# - Checks for root privileges.
# - Loads necessary FPGA kernel modules idempotently.
# - Creates device nodes idempotently.
# - Compiles and launches the main application.
# - Cleans up all resources on exit.
# =================================================================

# --- 설정 변수 ---
MODULE_DIR="/home/pi/Modules"
APP_DIR="/home/pi/-6-/fpga" # 사용자 디렉토리명 '-6-' 유지

# 드라이버 모듈 (.ko 파일 이름만)
TEXT_LCD_MODULE="fpga_text_lcd_driver"
LED_MODULE="fpga_led_driver"
INTERFACE_MODULE="fpga_interface_driver" # 필요시 주석 해제

# 장치 노드 정보
TEXT_LCD_DEV_NODE="/dev/fpga_text_lcd"
LED_DEV_NODE="/dev/fpga_led"

# --- 루트 권한 확인 ---
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root.
Please run with 'sudo'." 
   exit 1
fi

# --- 자동 정리 함수 ---
# 스크립트가 종료될 때 (정상 종료 또는 Ctrl+C) 호출됩니다.
cleanup() {
    echo ""
    echo "Cleaning up resources..."
    
    # 생성된 장치 노드 삭제
    if [ -c "$TEXT_LCD_DEV_NODE" ]; then
        rm "$TEXT_LCD_DEV_NODE"
        echo "Removed $TEXT_LCD_DEV_NODE"
    fi
    if [ -c "$LED_DEV_NODE" ]; then
        rm "$LED_DEV_NODE"
        echo "Removed $LED_DEV_NODE"
    fi

    # 로드된 커널 모듈 언로드 (역순으로)
    if lsmod | grep -q "$TEXT_LCD_MODULE"; then
        rmmod "$TEXT_LCD_MODULE"
        echo "Unloaded $TEXT_LCD_MODULE module."
    fi
    if lsmod | grep -q "$LED_MODULE"; then
        rmmod "$LED_MODULE"
        echo "Unloaded $LED_MODULE module."
    fi
    # 인터페이스 드라이버가 다른 드라이버에 의해 사용될 경우, 가장 마지막에 언로드합니다.
    if lsmod | grep -q "$INTERFACE_MODULE"; then
        rmmod "$INTERFACE_MODULE"
        echo "Unloaded $INTERFACE_MODULE module."
    fi

    echo "Cleanup finished."
}

# 스크립트 종료 신호(EXIT)를 감지하면 cleanup 함수를 실행하도록 설정
trap cleanup EXIT


# --- 1. 커널 모듈 로드 ---
echo "STEP 1: Loading kernel modules..."
cd "$MODULE_DIR" || { echo "Directory not found: $MODULE_DIR"; exit 1; }

# 각 모듈이 이미 로드되었는지 확인 후, 로드되지 않았을 때만 insmod 실행
if ! lsmod | grep -q "$INTERFACE_MODULE"; then
    insmod "$INTERFACE_MODULE.ko"
    echo "Loaded $INTERFACE_MODULE.ko"
else
    echo "$INTERFACE_MODULE is already loaded."
fi

if ! lsmod | grep -q "$TEXT_LCD_MODULE"; then
    insmod "$TEXT_LCD_MODULE.ko" # 오타 수정 (" .ko" -> ".ko")
    echo "Loaded $TEXT_LCD_MODULE.ko"
else
    echo "$TEXT_LCD_MODULE is already loaded."
fi

if ! lsmod | grep -q "$LED_MODULE"; then
    insmod "$LED_MODULE.ko" # 오타 수정 (" .ko" -> ".ko")
    echo "Loaded $LED_MODULE.ko"
else
    echo "$LED_MODULE is already loaded."
fi


# --- 2. 장치 노드 생성 ---
echo "STEP 2: Creating device nodes..."

# 각 장치 노드가 이미 존재하는지 확인 후, 없을 때만 mknod 실행
if [ ! -c "$TEXT_LCD_DEV_NODE" ]; then
    mknod "$TEXT_LCD_DEV_NODE" c 263 0
    echo "Created $TEXT_LCD_DEV_NODE"
else
    echo "$TEXT_LCD_DEV_NODE already exists."
fi

if [ ! -c "$LED_DEV_NODE" ]; then
    mknod "$LED_DEV_NODE" c 260 0
    echo "Created $LED_DEV_NODE"
else
    echo "$LED_DEV_NODE already exists."
fi


# --- 3. 프로그램 빌드 ---
echo "STEP 3: Building the application..."
cd "$APP_DIR" || { echo "Directory not found: $APP_DIR"; exit 1; } # 문법 오류 수정

echo "Compiling dht_fpga.c..."
gcc -o dht_fpga dht_fpga.c -lwiringPi -lrt -lpthread
if [ $? -ne 0 ]; then
    echo "Compilation failed."
    exit 1 # 컴파일 실패 시 스크립트 종료
fi
chmod +x dht_fpga
echo "Build successful."


# --- 4. 프로그램 실행 ---
echo "STEP 4: LAUNCHING PROGRAM"
echo "--------------------------------"
# GUI 프로그램은 일반 사용자 권한으로 실행하는 것이 더 안전합니다.
# 만약 sudo 권한이 반드시 필요하다면 'sudo -u pi' 부분을 제거하세요.
sudo -u pi python3 gui_fpga_web.py
