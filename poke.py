#!/usr/bin/env python3
from pprint import pprint
from time import sleep
from itertools import count
import os
import mmap
import struct
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--cycle", action="store_true")
parser.add_argument("--pru", type=int, choices=[0,1], default=0, help="Which PRU?")

def recv_struct(fd, fmt):
	size = struct.calcsize('=' + fmt)
	buf = bytes()
	while len(buf) < size:
		n = os.read(fd, size - len(buf))
		print("read", repr(n))
		buf += n
	return struct.unpack('=' + fmt, buf)

def send_struct(fd, fmt, *data):
	os.write(fd, struct.pack('=' + fmt, *data))

def write_struct(map, fmt, *data, **kwargs):
	offset = kwargs.pop("offset", None)
	if offset is not None:
		map.seek(offset, os.SEEK_SET)
	map.write(struct.pack('=' + fmt, *data))

def read_struct(map, fmt, offset=0):
	map.seek(offset, os.SEEK_SET)
	data = map.read(struct.calcsize(fmt))
	return struct.unpack('=' + fmt, data)
	
colors_by_strand = [
[ 	# pin 0
(0xFF, 0, 0),
(0, 0xFF, 0),
(0, 0, 0xFF),
(0xFF, 0xFF, 0),
(0, 0xFF, 0xFF),
(0xFF, 0, 0xFF),
], [ 	# pin 1
(0xFF, 0xFF, 0),
(0, 0xFF, 0xFF),
(0xFF, 0, 0xFF),
(0xFF, 0, 0),
(0, 0xFF, 0),
(0, 0, 0xFF),
]]
RGB = [(0xFF, 0x00, 0x00),
 (0x00, 0xFF, 0x00),
 (0x00, 0x00, 0xFF)] * 5

def display(colors_by_strand, fb, msgfd): # colors_by_strand will get mogrified to be square
	pprint(colors_by_strand)
	nlights = max(map(len, colors_by_strand))
	colors_by_strand.extend([(0,0,0)] * nlights for _ in range(16 - len(colors_by_strand)))
	regs = [] # beecomes an array of 16 bit register values that the PRU can march R30 through
	#translates R,G,B into GRB bits at a time
	for bins in zip(*map(lambda colors: list(map(lambda rgb: rgb[1]| rgb[0] << 8 | rgb[2] << 16, colors)), colors_by_strand)): 
		for cb in range(24):
			reg = 0;
			for pb in range(len(bins)):
				reg |= 1 << pb if bins[pb] & (1 << cb) else 0
			regs.append(reg)
	nregs = len(regs)
	print(nlights, nregs)
	write_struct(fb, "H" * nregs, *regs, offset=0)
	send_struct(msgfd, "cH", 'd'.encode('ascii'), nregs)
	print(recv_struct(msgfd, "H"))

if __name__ == "__main__":
	gargs = parser.parse_args()
	msgfd = os.open("/dev/rpmsg_pru3%d" % gargs.pru, os.O_RDWR)
	os.write(msgfd, "a".encode('ascii'))
	addr0, len0, addr1, len1 = recv_struct(msgfd, 'IIII')
	print("%08x %08x" % (addr0, len0))
	print("%08x %08x" % (addr1, len1))
	maps = []
	for addr, size in [(addr0, len0),(addr1, len1)]:
		memfd = os.open("/dev/mem", os.O_RDWR)
		mm = mmap.mmap(memfd, length=size, offset=addr)
		mm.write(b'\x00' * size)
		mm.seek(0, os.SEEK_SET)
		maps.append(mm)
	while(True):
		display([RGB], maps[0], msgfd)
		RGB.insert(0,RGB.pop())
		if not gargs.cycle:
			break
		input()
