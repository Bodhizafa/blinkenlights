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
import jps
from pprint import pprint

parser = argparse.ArgumentParser()
parser.add_argument("--pru", type=int, default=argparse.SUPPRESS, choices=[0,1], help="Which PRU?")
parser.add_argument("--len", type=int, default=25, help="Length of the longest strand")
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

class Output(object):
    def __init__(self, strand_len, clear_color):
        self.lock = threading.RLock()
        self.strand_len = strand_len
        self.clear(clear_color)

    def clear(self, color=None):
        with self.lock:
            if color is None:
                color = (0,0,0)
            self._colors_by_strand = [[color] * self.strand_len for _ in range(16)]

    def set_strand(self, strand, strand_val):
        with self.lock:
            val = strand_val
            if len(val) > self.strand_len:
                raise ValueError("value too long")
            val.extend([(0,0,0)] * (self.strand_len - len(val)))
            self._colors_by_strand[strand] = val
    # Sets a strand to a pattern, given by a function from 0-TAU => (0-1, 0-1, 0-1) (i.e. one made by fuckparse)
    def pattern(self, strand, period, fn, t=0):
        leds = map(lambda th: clamp_and_rerange(*fn(th + t * TAU)), map(lambda ledno: float(ledno) / float(period) * TAU, range(self.strand_len)))
        self.set_strand(strand, list(leds))


class PRU(Output):
    def __init__(self, no, strand_len, clear_color=None):
        super().__init__(strand_len, clear_color)
        self.frame = threading.Event()
        self.no = no
        self.strand_len = strand_len
        self.msgfd = os.open("/dev/rpmsg_pru3%d" % no, os.O_RDWR)
        self.send("c", "a".encode('ascii'))
        memfd = os.open("/dev/mem", os.O_RDWR)
        addr, size = self.recv('II')
        print("Initialized PRU %d, FD %d\n" % (no, self.msgfd) + 
              "Framebuffer at %08x %08d\n" % (addr, size))
        self.fb = mmap.mmap(memfd, length=size, offset=addr)
        self.fb.write(b'\x00' * size)
        self.fb.seek(0, os.SEEK_SET)
        display_thread = threading.Thread(target=display_thread_main, name="display_thread", args=(self,))
        display_thread.daemon = True
        display_thread.start()

    def set_strand(self, strand, strand_val):
        if strand > 15:
            raise ValueError("strand doesn't exist: " + str(strand))
        super().set_strand(strand, strand_val)

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

# color-friendly operators. Should all take either an RGB tuple or a value and return the same.
# All tuple members and values should come in between 0 and 1 and be returned the same
def unary_sub(v):
    try:
        return 1 - v
    except TypeError:
        R, G, B = v
        return (1-R, 1-G, 1-B)

def binary_add(l, r):
    try:
        return (max(l[0] + r[0], 1),
            max(l[1] + r[1], 1),
            max(l[2] + r[2], 1))
    except TypeError:
        return max(l + r, 1)

def binary_sub(l, r):
    try:
        return (min(l[0] - r[0], 0),
            min(l[1] - r[1], 0),
            min(l[2] - r[2], 0))
    except TypeError:
        return min(l - r, 0)

def binary_mult(l, r):
    try:
        return (l[0] * r[0],
            l[1] * r[1],
            l[2] * r[2])
    except TypeError:
        return l * r

def binary_div(l, r):
    try:
        return (1 - ((1 - l[0]) * (1 - r[0])),
            1 - ((1 - l[1]) * (1 - r[1])),
            1 - ((1 - l[2]) * (1 - r[2])))
    except TypeError:
        return 1 - ((1 - l) * (1 - r))

unary_funcs_by_op = {
    ast.UAdd: lambda operand: operand,
    ast.USub: unary_sub,
}

binary_funcs_by_op = {
    ast.Add: binary_add,
    ast.Sub: binary_sub,
    ast.Mult: binary_mult,
}
# functions available in the fuck DSL
funcs_by_name = {
    # value functions - Take theta and produce 0 to 1. Should rougly follow cosine in phase-ness
    "cos": lambda th: (math.cos(th) + 1) / 2,
    "sin": lambda th: (math.sin(th) + 1) / 2,
    "sqr": lambda th: 1 if th < TAU / 2 else 0,
    "tri": lambda th: th / (TAU / 2) if th < TAU / 2 else 1 - (th / (TAU / 2)),

    # Interpolaters - take a value and return an RGB tuple
    "R": lambda v: (v, 0, 0),
    "G": lambda v: (0, v, 0),
    "B": lambda v: (0, 0, v),
    "Y": lambda v: (v, v, 0),
    "C": lambda v: (0, v, v),
    "M": lambda v: (v, 0, v),
    "W": lambda v: (v, v, v),
}
# Constants  available in the fuck DSL
constants_by_name = { 
    "TAU": TAU,
}

pat_args = ['th']

globals_dict = {k: v for k, v in itertools.chain(funcs_by_name.items(), constants_by_name.items(), zip(pat_args, itertools.repeat(None)))}

def fuckparse(arg_str):

    a = ast.parse(arg_str, mode="eval")
    lamb = ast.Lambda(args=ast.arguments(args=[ast.arg(arg=arg, annotation=None) for arg in pat_args],
                                         vararg=None, kwonlyargs=[],
                                         kw_defaults=[], kwarg=None, defaults=[]),
                  body=a.body)
    fn_ast = ast.Expression(body=lamb)
    for node in ast.walk(fn_ast): # ast.fix_missing_locations seems to not.
        node.lineno, node.col_offset = (0,0)
        if isinstance(node, ast.Name) and not node.id in globals_dict.keys():
            raise SyntaxError("Name %s unknown" % node.id)
    co = compile(fn_ast, filename="<fuck>", mode="eval")
    fn = eval(co, globals_dict)
    return fn
 
# All the math above works from 0 to 1 floating point, PRUs want 0 to 255 fixed point
def clamp_and_rerange(R, G, B):
    return (max(0, min(int(R * 255), 255)),
        max(0, min(int(G * 255), 255)),
        max(0, min(int(B * 255), 255)))

def cmd_clear(pru, j, color_str=None):
    if color_str is not None:
        color = ast.literal_eval(color_str)
    else:
        color = (0,0,0)
    pru.clear(color)
    print("Cleared to %s" % repr(color))

def cmd_reset(pru, j, color_str=None):
    if color_str is not None:
        try:
            color = ast.literal_eval(color_str)
        except SyntaxError:
            print("Couldn't parse args")
    else:
        color = (0,0,0)
    pru.reset()
    pru.clear(color)

def cmd_pulse(pru, j):
    stime = time.time()
    n = 0
    for i in itertools.chain(range(255), range(255,0,-1)):
        pru.clear((i,i,i))
        pru.wait_frame()
        n += 1
    etime = time.time()
    print("%s frames in %s seconds -- %s fps" % (n, etime - stime, float(n) / (etime - stime)))

def parse_strands(string):
    try:
        strands = [int(string)]
    except ValueError:
        try:
            start, end = map(int, string.split(":", maxsplit=1))
            strands = range(start, end)
        except ValueError:
            strands = map(int, string.split(','))
    return set(strands)
        
def cmd_pattern(pru, j, arg_str):
    strands, period, arg_str = arg_str.split(maxsplit=2)
    strands = parse_strands(strands)
    period = int(period)
    fn = j.parse_str(arg_str)
    for strand in strands:
        if strand in animations_by_strand:
            del animations_by_strand[strand]
        pru.pattern(strand, period, fn, 0)


def cmd_roll(pru, j, arg_str):
    strands, period, rpm, arg_str = arg_str.split(maxsplit=3)
    strands = parse_strands(strands)
    period = int(period)
    rpm = int(rpm)
    fn = j.parse_str(arg_str)
    with animations_lock:
        for strand in strands:
            animations_by_strand[strand] = (fn, period, rpm)

def cmd_set(pru, j, arg_str=None):
    strand, arg_str = arg_str.split(maxsplit=1)
    strand = int(strand)
    value = ast.literal_eval(arg_str)
    pru.set_strand(strand, value)

def cmd_print(pru, j):
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
    "roll": cmd_roll,
    "set": cmd_set,
}

animations_by_strand = {} # strand no => (fn, period, rpm)
animations_lock = threading.Lock()
def display_thread_main(pru): # Ghetto ass shit because I can't figure out why the fucking thing keeps hanging
    start = time.time()
    while True:
        with animations_lock:
            elapsed_min = (time.time() - start) / 60.
            for strand, (fn, period, rpm) in animations_by_strand.items():
                pru.pattern(strand, period, fn, elapsed_min * rpm)
        pru.display()

if __name__ == "__main__":
    gargs = parser.parse_args()
    if hasattr(gargs, 'pru'):
        print("PRU %d" % gargs.pru)
        pru = PRU(gargs.pru, gargs.len)
    else:
        pass
    j = jps.JPSVM(jps.funcs, jps.ops, jps.args, jps.consts)
    readline.parse_and_bind("set editing-mode vi") # Deal with it 🕶
    try:
        readline.read_history_file(gargs.histfile)
    except FileNotFoundError:
        open(histfile, 'wb').close()
    try:
        while True:
            sys.stdout.write("🍆 ")
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
                    funcs_by_cmd[possibilities[0]](pru, j, *args)
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
