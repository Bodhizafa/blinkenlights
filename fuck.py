#!/usr/bin/env python3
# vim: set fileencoding=utf8
import os
import mmap
import struct
import argparse
import readline
import ast
from pprint import pprint
parser = argparse.ArgumentParser()
parser.add_argument("pru", type=int, choices=[0,1], help="Which PRU?")
parser.add_argument("--len", type=int, default=16, help="Length of the longest strand")
parser.add_argument("--histfile", type=str, default=".fuck_history", help="History file")
class PRU(object):
	def __init__(self, no, strand_len, clear_color=None):
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

	def recv(self, fmt):
		size = struct.calcsize('=' + fmt)
		buf = bytes()
		while len(buf) < size:
			n = os.read(self.msgfd, size - len(buf))
			print("read", repr(n))
			buf += n
		return struct.unpack('=' + fmt, buf)

	def send(self, fmt, *data):
		os.write(self.msgfd, struct.pack('=' + fmt, *data))

	def write(self, fmt, *data, **kwargs):
		offset = kwargs.pop("offset", None)
		if offset is not None:
			self.fb.seek(offset, os.SEEK_SET)
		self.fb.write(struct.pack('=' + fmt, *data))

	def read(self, fmt, offset=0):
		self.fb.seek(offset, os.SEEK_SET)
		data = self.fb.read(struct.calcsize("=" + fmt))
		return struct.unpack('=' + fmt, data)

	def display(self):
		#pprint(self._colors_by_strand)
		regs = [] # becomes an array of 16 bit register values that the PRU can march R30 through
		#translates R,G,B into GRB bits at a time
		for bins in zip(*map(lambda colors: list(map(lambda rgb: rgb[1]| rgb[0] << 8 | rgb[2] << 16, colors)), self._colors_by_strand)): 
			for cb in range(24):
				reg = 0;
				for pb in range(len(bins)):
					reg |= 1 << pb if bins[pb] & (1 << cb) else 0
				regs.append(reg)
		nregs = len(regs)
		self.write("H" * nregs, *regs, offset=0)
		self.send("cH", 'd'.encode('ascii'), nregs)
		print("Displayed %d regs" % self.recv("H"))

	def clear(self, color=None):
		if color is None:
			color = (0,0,0)
		self._colors_by_strand = [[color] * self.strand_len for _ in range(16)]

	def reset(self, clear_color=None):
		os.close(self.msgfd)
		self.fb.close()
		if self.no == 0:
			ub = os.open("/sys/bus/platform/drivers/pru-rproc/unbind", os.O_WRONLY)
			os.write(ub, "4a334000.pru0".encode('ascii'))
			b = os.open("/sys/bus/platform/drivers/pru-rproc/bind", os.O_WRONLY)
			os.write(b, "4a334000.pru0".encode('ascii'))
		else:
			open("/sys/bus/platform/drivers/pru-rproc/unbind", 'w').write("4a338000.pru1")
			open("/sys/bus/platform/drivers/pru-rproc/bind", 'w').write("4a338000.pru1")
		self.__init__(self.no, self.strand_len, clear_color)

def cmd_clear(pru, color_str=None):
	if color_str is not None:
		color = ast.literal_eval(color_str)
	else:
		color = (0,0,0)
	pru.clear(color)
	print("Cleared to %s" % repr(color))

def cmd_reset(pru, color_str=None):
	if color_str is not None:
		color = ast.literal_eval(color_str)
	else:
		color = (0,0,0)
	pru.reset()
	pru.clear(color)
	pru.display()

funcs_by_cmd = {
	"display": lambda pru: pru.display(),
	"clear": cmd_clear,
	"reset": cmd_reset,
}
if __name__ == "__main__":
	gargs = parser.parse_args()
	pru = PRU(gargs.pru, gargs.len)
	readline.parse_and_bind("set editing-mode vi") # Deal with iti 🕶
	try:
		readline.read_history_file(gargs.histfile)
	except FileNotFoundError:
		open(histfile, 'wb').close()
	try:
		while True:
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
				print("Ok.")
				funcs_by_cmd[possibilities[0]](pru, *args)
			elif n == 0:
				print("What?")
			else:
				print("Nebulous: %r" % possibilities)
	except EOFError:
		print("Bye.")
	except KeyboardInterrupt:
		print("Ouch!")
		raise
	finally:
		readline.write_history_file(gargs.histfile)
