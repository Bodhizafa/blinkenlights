#!/usr/bin/env python3
import digitalio
import board
import argparse
import math

parser = argparse.ArgumentParser("Send shit over SPI")

# Setup SPI bus using hardware SPI:
spi = board.SPI()
while spi.try_lock():
    pass
cs = digitalio.DigitalInOut(board.CE0)
cs.direction = digitalio.Direction.OUTPUT
cs.value = True
spi.configure(baudrate=6666666)
spi.write(b"\xFF" + b"\xFF\x00\x00"*8 * 31 + b"\x00" )
cs.value = False
