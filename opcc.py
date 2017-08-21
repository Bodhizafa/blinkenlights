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
import json
import traceback
from Neuron import Model2, Neuron, Synapse, clamp

parser = argparse.ArgumentParser()
parser.add_argument("--host", type=str, help="OPC host", default="10.4.20.2")
parser.add_argument("--histfile", type=str, help="History file", default=".opcc_history")
parser.add_argument("--len", type=int, default=300, help="Number of LEDs per channel")
parser.add_argument("--port", type=int, default=42024)
parser.add_argument("--network", default="network.json", type=str, help="Network to load into the synaq")
parser.add_argument("--steps", default=50, type=str, help="number of model steps per visible frame")


class opc_client(object):
    def __init__(self, host, port):
        self.socket = socket.socket()
        self.socket.connect((host, port))

    def send(self, channel, command, body):
        blen = len(body)
        packet = struct.pack(">BBH%ds" % blen, channel, command, blen, body)
        self.socket.send(packet)

    def send_leds(self, strand, colors): # colors is an iterable of (R, G, B) tuples, range 0-1
        channel = strand + 1
        colors = list(colors)
        color_bytes = bytearray((clamp(int(component * 255)) for color in colors for component in color))
        body = struct.pack("%ds" % len(color_bytes), color_bytes)
        self.send(channel, 0, body)

    def test(self):
        self.send(0, 254, b'')


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
        with open(gargs.network) as network:
            try:
                params = json.load(network)
            except ValueError:
                print("Network was unparseable. Starting anew.")
                traceback.print_exc()
                params = {"dT": 0.0001}
    except IOError:
        print("Network doesn't exist. starting anew.")
        params = {"dT": 0.0001}
    model = Model2(**params)
    try:
        # I wrote all this neat cli parser shit for fuck.py, prolly shoulda made it more reusable, sho' would be nice here.
        mstrand = 0;
        mstart = 0;
        mend = 1;
        mcolor = (0, 1, 0)
        old_tcattr = termios.tcgetattr(sys.stdin.fileno())
        while True:
            sys.stdout.write("🍆 ")
            raw = input()
            raw = raw.strip()
            if raw == "f" : # test
                print("flash")
                opcc.test()
            elif raw == "h": # help
                print("""
                [h] Help
                [m] measure
                [f] flash all lights
                [s] save the network (to the file given by --network, default network.json
                [d] display the current model state
                [p] print model state to stdout
                [n] step the model by dT
                [nd][dn] step and display
                [N] create a soma on the current measured strip
                [S] create a synapse on the current measured strip
                [r] run the model
                """)
            elif raw == "r":
                try:
                    while True:
                        for _ in range(gargs.steps):
                            model.step()
                        for strand, colors in model.generate_colors_by_strand().items():
                            opcc.send_leds(strand, colors)
                except KeyboardInterrupt:
                    print("Interrupted")
            elif raw in ("d", "n", "nd", "dn"):
                if 'n' in raw:
                    model.step()
                if 'd' in raw:
                    for strand, colors in model.generate_colors_by_strand().items():
                        opcc.send_leds(strand, colors)
            elif raw == "s": # save network
                with open(gargs.network, "w") as network:
                    json.dump(model.params(), network)
                print("Saved to %s" % gargs.network)
            elif raw == "N":
                k, n = model.add({
                        "start": mstart, 
                        "color": mcolor, 
                        "strand": mstrand
                    }, 
                    nlights = mend - mstart, 
                    I = 100)
                print("Created Neuron %s: %s" % (k, n))
            elif raw == "S":
                pass # TODO this
            elif raw == "m": # measuring tape
                print("Measuring. [t][y] move start, [u][i] to move section, [o][p] move end")
                print("[j][k] to change channels down/up")
                print("[q][w][e] to increase R/G/B, [a][s][d] to decrease")
                print("[esc] to exit")
                tty.setcbreak(sys.stdin)
                c = None
                while c is not '\x1b': # escape
                    sys.stdout.write("\r\033[Kstrand: %d %d:%d %s" % (mstrand, mstart, mend, mcolor))
                    opcc.send_leds(mstrand, 
                        itertools.chain(((0,0,0) for _ in range(mstart)), 
                                        (mcolor for _ in range(mend - mstart)), 
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
                    if c in ['q', 'w' , 'e', 'a', 's', 'd']:
                        mr, mg, mb = mcolor
                        if c == 'q':
                            mr = min(mr + .125, 1)
                        elif c == 'a':
                            mr = max(mr - .125, 0)
                        elif c == 'w':
                            mg = min(mg + .123, 1)
                        elif c == "s":
                            mg = max(mg - .123, 0)
                        elif c == 'e':
                            mb = min(mb + .125, 1)
                        elif c == 'd':
                            mb = min(mb - .125, 0)
                        mcolor = (mr, mg, mb)
                sys.stdout.write("\n")
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_tcattr)
            else:
                print("No.")
            
    except EOFError:
        print("Bye.")
    except KeyboardInterrupt:
        print("Ouch!")
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_tcattr)
        readline.write_history_file(gargs.histfile)
