#!/usr/bin/env python3
import board
import digitalio
import busio

spi = busio.SPI(board.SCLK, board.MOSI, board.MISO)
while not spi.try_lock():
    pass
pin = digitalio.DigitalInOut(board.pin.D4)
pin.direction = digitalio.Direction.OUTPUT
pin.value = True

spi.configure(baudrate=6666666)
spi.write(b"\xFF" * 100)
pin.value = False
print("Sent")
