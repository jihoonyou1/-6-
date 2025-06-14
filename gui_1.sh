#!/bin/bash

# 드라이버 모듈 로드 (절대 경로 사용)
sudo insmod /home/pi/Modules/fpga_interface_driver.ko
sudo insmod /home/pi/Modules/fpga_text_lcd_driver.ko
sudo insmod /home/pi/Modules/fpga_led_driver.ko

# 장치 노드 생성 및 권한 설정 (기존 노드 삭제 및 권한 부여 추가)
sudo rm -f /dev/fpga_text_lcd
sudo mknod /dev/fpga_text_lcd c 263 0
sudo chmod 666 /dev/fpga_text_lcd

sudo rm -f /dev/fpga_led
sudo mknod /dev/fpga_led c 260 0
sudo chmod 666 /dev/fpga_led

# dht_fpga 실행 권한 부여 (이미 되어 있다면 생략 가능)
# 한 번만 실행하면 되므로 스크립트에는 굳이 매번 넣을 필요는 없습니다.
# 하지만 혹시 모르니 일단 여기에 두겠습니다.
chmod +x /home/pi/-6-/fpga/dht_fpga

# GUI 파일 실행 (절대 경로 사용)
python3 /home/pi/my_gui_app/gui_fpga.py # gui_fpga.py의 실제 경로로 변경
                                      # 또는 gui_fpga.py가 /home/pi/-6-/fpga에 있다면
                                      # python3 /home/pi/-6-/fpga/gui_fpga.py

exit 0
