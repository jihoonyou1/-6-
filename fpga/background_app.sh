#!/usr/bin/env bash

echo "FPGA driver setting & LAUNCH PROGRAM"

#1. MODULE
cd /home/pi/Modules || { echo "NOT FOUND DIRECTORY"; exit 1; }

sudo insmod fpga_interface_driver.ko
sudo insmod fpga_text_lcd_driver .ko
sudo insmod fpga_led_driver .ko

#2. DEVICE NODE
sudo mknod /dev/fpga_text_lcd c 263 0
sudo mknod /dev/fpga_led c 260 0

#3. PROGRAM BUILD
cd /home/pi/-6-/fpga || { echo "NOT FOUND DIRECTORY" exit1: }

gcc -o dht_fpga dht_fpga.c -lwiringPi -lrt -lpthread
chmod +x dht_fpga

#4. LAUNCH
python3 web_server.py
