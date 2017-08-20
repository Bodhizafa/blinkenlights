#!/usr/bin/env python3
# (c) 2017 Landon Meernik
# vim: set fileencoding=utf8
import argparse
import tty
import termios
import readline
import socket
import sys
import struct
import itertools

parser = argparse.ArgumentParser()
parser.add_argument("--host", type=str, help="OPC host", default="10.4.20.2")
parser.add_argument("--histfile", type=str, help="History file", default=".opcc_history")
parser.add_argument("--len", type=int, default=600, help="Number of LEDs per channel")
parser.add_argument("--port", type=int, default=42024)


class opc_client(object):
    def __init__(self, host, port):
        self.socket = socket.socket()
        self.socket.connect((host, port))

    def send(self, channel, command, body):
        blen = len(body)
        packet = struct.pack(">BBH%ds" % blen, channel, command, blen, body)
        self.socket.send(packet)

    def send_leds(self, strand, leds): # leds is a list of (R, G, B) tuples, range 0-1
        channel = strand + 1
        color_bytes = bytearray((int(byte * 255) for color in leds for byte in color))
        body = struct.pack("%ds" % len(color_bytes), color_bytes)
        self.send(channel, 0, body)

    def test(self):
        self.send(0, 254, b'')

MEASURE_COLOR = (0,0.25,0)

if __name__ == "__main__":
    gargs = parser.parse_args()
    readline.parse_and_bind("set editing-mode vi") # Deal with it 🕶
    try:
        readline.read_history_file(gargs.histfile)
    except FileNotFoundError:
        open(gargs.histfile, 'wb').close()
    host = gargs.host
    port = gargs.port
    opcc = opc_client(host, port)

    try:
        # I wrote all this neat cli parser shit for fuck.py, prolly shoulda made it more reusable, sho' would be nice here.
        mstrand = 0;
        mstart = 0;
        mend = 1;
        old_tcattr = termios.tcgetattr(sys.stdin.fileno())
        while True:
            sys.stdout.write("🍆 ")
            raw = input()
            if raw.strip() == '':
                print("No.")
                continue
            elif raw == "t" : # test
                print("test")
                opcc.test()
            elif raw == "pt": # protocol test
                if ' ' in raw:
                    _, chan = raw.split()
                    chan = int(chan)
                else:
                    chan = 0
                print("Channel %s test" % chan)
                opcc.send_leds(chan, [(0.5, 0, 0), (0, 0.5, 0), (0, 0, 0.5)])
            elif raw == "m": # measuring tape
                sys.stdout.write("Measuring. [t][y] move start, [u][i] to move section, [o][p] move end, [j][k] to change channels\n")
                tty.setcbreak(sys.stdin)
                c = None
                while c is not '\x1b': # escape
                    sys.stdout.write("\r\033[Kstrand: %d %d:%d" % (mstrand, mstart, mend))
                    opcc.send_leds(mstrand, 
                        itertools.chain(((0,0,0) for _ in range(mstart)), 
                                        (MEASURE_COLOR for _ in range(mend - mstart)), 
                                        ((0,0,0) for _ in range(gargs.len - mend))))
                    c = sys.stdin.read(1)
                    if c == "p" or c == "i":
                        mend = min(mend + 1, gargs.len)
                    if c == "o" or c == "u":
                        mend = max(mend - 1, mstart + 1)
                    if c == "t" or c == "u":
                        mstart = max(mstart - 1, 0)
                    if c == "y" or c == "i":
                        mstart = min(mstart + 1, mend - 1)
                    if c == "j":
                        opcc.send_leds(mstrand, [(0,0,0)] * gargs.len)
                        mstrand = max(mstrand - 1, 0)
                    if c == "k":
                        opcc.send_leds(mstrand, [(0,0,0)] * gargs.len)
                        mstrand = min(mstrand + 1, 255)
                          
                    
                    
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_tcattr)
                
            
    except EOFError:
        print("Bye.")
    except KeyboardInterrupt:
        print("Ouch!")
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_tcattr)
        readline.write_history_file(gargs.histfile)
