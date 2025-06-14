#!/bin/bash

sudo insmod /home/pi/Modules/fpga_interface_driver.ko
sudo insmod /home/pi/Modules/fpga_text_lcd_driver.ko
sudo insmod /home/pi/Modules/fpga_led_driver.ko

sudo rm -f /dev/fpga_text_lcd
sudo mknod /dev/fpga_text_lcd c 263 0
sudo chmod 666 /dev/fpga_text_lcd

sudo rm -f /dev/fpga_led
sudo mknod /dev/fpga_led c 260 0
sudo chmod 666 /dev/fpga_led

gcc -o dht_fpga dht_fpga.c -lwiringPi -lrt -lpthread

chmod +x /home/pi/-6-/fpga/dht_fpga

python3 /home/pi/-6-/fpga/gui_fpga.py 

exit 0
