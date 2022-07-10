#!/usr/bin/env python3
import Adafruit_PureIO.spi
import time

spi = Adafruit_PureIO.spi.SPI('/dev/spidev0.0')

while True:
    spi.max_speed_hz = 6666666
    print(f"{spi.max_speed_hz=}")
    spi.writebytes(b"\xFF"*960)
    time.sleep(2)

print("ok")
