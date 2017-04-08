#!/usr/bin/env python3
# vim: set fileencoding=utf8
import os
import mmap
import struct
import argparse
import readline
import ast
import sys
import time
import itertools
import traceback
import math
import threading
from pprint import pprint
parser = argparse.ArgumentParser()
parser.add_argument("pru", type=int, choices=[0,1], help="Which PRU?")
parser.add_argument("--len", type=int, default=16, help="Length of the longest strand")
parser.add_argument("--histfile", type=str, default=".fuck_history", help="History file")
TAU = math.pi * 2
def translate_colors(colors_by_strand):
	regs = [] # becomes an array of 16 bit register values that the PRU can march R30 through
	#translates R,G,B into GRB bits at a time
	for bins in zip(*map(lambda colors: map(lambda rgb: rgb[1]| rgb[0] << 8 | rgb[2] << 16, colors), colors_by_strand)): 
		for cb in list(range(7,-1,-1)) + list(range(15,7,-1)) + list(range(23,15,-1)):
			reg = 0;
			for pb in range(len(bins)):
				reg |= 1 << pb if bins[pb] & (1 << cb) else 0
			regs.append(reg)
	return regs

class PRU(object):
	def __init__(self, no, strand_len, clear_color=None):
		self.lock = threading.RLock()
		self.frame = threading.Event()
		self.no = no
		self.strand_len = strand_len
		self.msgfd = os.open("/dev/rpmsg_pru3%d" % gargs.pru, os.O_RDWR)
		self.send("c", "a".encode('ascii'))
		memfd = os.open("/dev/mem", os.O_RDWR)
		addr, size = self.recv('II')
		print("Initialized PRU %d, FD %d\n" % (no, self.msgfd) + 
		      "Framebuffer at %08x %08d\n" % (addr, size))
		self.fb = mmap.mmap(memfd, length=size, offset=addr)
		self.fb.write(b'\x00' * size)
		self.fb.seek(0, os.SEEK_SET)
		self.clear(clear_color)

	def send(self, fmt, *data):
		with self.lock:
			os.write(self.msgfd, struct.pack('=' + fmt, *data))

	def recv(self, fmt):
		with self.lock:
			size = struct.calcsize('=' + fmt)
			buf = bytes()
			while len(buf) < size:
				n = os.read(self.msgfd, size - len(buf))
				buf += n
			return struct.unpack('=' + fmt, buf)

	def write(self, fmt, *data, **kwargs):
		with self.lock:
			offset = kwargs.pop("offset", None)
			if offset is not None:
				self.fb.seek(offset, os.SEEK_SET)
			self.fb.write(struct.pack('=' + fmt, *data))

	def read(self, fmt, offset=0):
		with self.lock:
			self.fb.seek(offset, os.SEEK_SET)
			data = self.fb.read(struct.calcsize("=" + fmt))
			return struct.unpack('=' + fmt, data)

	def display(self):
		with self.lock:
			regs = translate_colors(self._colors_by_strand)
			nregs = len(regs)
			self.write("H" * nregs, *regs, offset=0)
			self.send("cH", 'd'.encode('ascii'), nregs)
			self.recv("H")
			self.frame.set()

	def clear(self, color=None):
		with self.lock:
			if color is None:
				color = (0,0,0)
			self._colors_by_strand = [[color] * self.strand_len for _ in range(16)]

	def set_strand(self, strand, strand_val):
		with self.lock:
			if strand > 15:
				raise ValueError("strand too large: " + str(strand))
			val = strand_val
			if len(val) > self.strand_len:
				raise ValueError("value too long")
			val.extend([(0,0,0)] * (self.strand_len - len(val)))
			self._colors_by_strand[strand] = val
	def wait_frame(self):
		self.frame.wait()
		self.frame.clear()

	def reset(self, clear_color=None):
		with self.lock:
			os.close(self.msgfd)
			self.fb.close()
			ub = os.open("/sys/bus/platform/drivers/pru-rproc/unbind", os.O_WRONLY)
			b = os.open("/sys/bus/platform/drivers/pru-rproc/bind", os.O_WRONLY)
			if self.no == 0:
				os.write(ub, "4a334000.pru0".encode('ascii'))
				os.write(b, "4a334000.pru0".encode('ascii'))
			else:
				os.write(ub, "4a338000.pru1")
				os.write(b, "4a338000.pru1")
			os.close(ub)
			os.close(b)
			self.__init__(self.no, self.strand_len, clear_color)

	def ping(self):
		with self.lock:
			self.send("c", "p".encode('ascii'))
			print(self.recv("c"))

def cmd_clear(pru, color_str=None):
	if color_str is not None:
		color = ast.literal_eval(color_str)
	else:
		color = (0,0,0)
	pru.clear(color)
	print("Cleared to %s" % repr(color))

def cmd_reset(pru, color_str=None):
	if color_str is not None:
		try:
			color = ast.literal_eval(color_str)
		except SyntaxError:
			print("Couldn't parse args")
	else:
		color = (0,0,0)
	pru.reset()
	pru.clear(color)

def cmd_pulse(pru):
	stime = time.time()
	n = 0
	for i in itertools.chain(range(255), range(255,0, -1)):
		pru.clear((i,i,i))
		pru.wait_frame()
		n += 1
	etime = time.time()
	print("%s frames in %s seconds -- %s fps" % (n, etime - stime, float(n) / (etime - stime)))

def cmd_pattern(pru, arg_str):
	pats_by_name = { # range from 0 to 255
		"sin": lambda period: lambda x: (sin(x / TAU)/ 2) + 0.5, 
		"square": lambda period: lambda x: (1 if x < period / 2 else 0)
	}
	strand, pattern, period, arg_str = map(int, arg_str.split(maxsplit=3))
	rgb_by_led = list(map(pats_by_name[pattern], range(pru.strand_len)))
	pru.set_strand(strand, val)

def cmd_set(pru, arg_str=None):
	strand, arg_str = arg_str.split(maxsplit=1)
	strand = int(strand)
	value = ast.literal_eval(arg_str)
	pru.set_strand(strand, value)
	

def cmd_print(pru):
	pprint(pru._colors_by_strand)
	regs = translate_colors(pru._colors_by_strand)
	colors = itertools.cycle(["G", "R", "B"])
	for n, r in enumerate(regs):
		if not n % 8:
			print("LED %d %s" % (n / 24, next(colors)))
		print(bin(r))

	

funcs_by_cmd = {
	"clear": cmd_clear,
	"reset": cmd_reset,
	"pulse": cmd_pulse,
	"ping": lambda pru: pru.ping(),
	"help": lambda pru: print("\n".join(funcs_by_cmd.keys())),
	"print": cmd_print,
	"pattern": cmd_pattern,
	"set": cmd_set,
}

def ping_thread_main(pru): # Ghetto ass shit because I can't figure out why the fucking thing keeps hanging
	while True:
		pru.display()

if __name__ == "__main__":
	gargs = parser.parse_args()
	pru = PRU(gargs.pru, gargs.len)
	ping_thread = threading.Thread(target=ping_thread_main, name="ping_thread", args=(pru,))
	ping_thread.daemon = True
	ping_thread.start()
	readline.parse_and_bind("set editing-mode vi") # Deal with iti 🕶
	try:
		readline.read_history_file(gargs.histfile)
	except FileNotFoundError:
		open(histfile, 'wb').close()
	try:
		while True:
			sys.stdout.write(": ")
			raw = input()
			if raw.strip() == '':
				print("No.")
				continue
			cmd_data = raw.split(maxsplit=1)
			if len(cmd_data) == 1:
				args = []
				cmd = cmd_data[0]
			else:
				cmd, data = cmd_data
				args = [data]
			possibilities = [k for k in funcs_by_cmd.keys() if k.startswith(cmd)]
			n = len(possibilities)
			if n == 1:
				try:
					funcs_by_cmd[possibilities[0]](pru, *args)
					print("Ok.")
				except:
					traceback.print_exc()
			elif n == 0:
				print("What?")
			else:
				print("Nebulous: %r" % possibilities)
	except EOFError:
		print("Bye.")
	except KeyboardInterrupt:
		print("Ouch!")
	finally:
		readline.write_history_file(gargs.histfile)
