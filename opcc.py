#!/usr/bin/env python3
# (c) 2017 Landon Meernik
# vim: set fileencoding=utf8

import random
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
import ast
import time
import jps
from collections import namedtuple
from Neuron import Model2, Neuron, Synapse
TAU = math.pi * 2


parser = argparse.ArgumentParser()
parser.add_argument("--host", type=str, help="OPC host", default="10.4.20.2")
parser.add_argument("--histfile", type=str, help="History file", default=".opcc_history")
parser.add_argument("--nlights", type=int, default=300, help="Number of LEDs per channel")
parser.add_argument("--port", type=int, default=42024)
parser.add_argument("--network", default="network.json", type=str, help="Network to load into the synaq")
parser.add_argument("--steps", default=500, type=str, help="Number of model steps per visible frame")
parser.add_argument("--fuzz", action="store_true")

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

class Animator(object):
    Animation = namedtuple("animation", ["fn", "period", "rpm"])
    def __init__(self, nlights):
        self._animations_by_strand = {}
        self.nlights = nlights
        self._t_0 = time.time()

    def _strand_generator(self, fn, period, t):
       yield from map(lambda th: fn(th + t * TAU), 
                      map(lambda ledno: float(ledno) / float(period) * TAU,
                          range(self.nlights)))

    def roll(self, strand, fn, period=None, rpm=20):
        if period is None:
            period = self.nlights
        self._animations_by_strand[strand] = self.Animation(fn, period, rpm)

    def generate_colors_by_strand(self):
        t_min = (time.time() - self._t_0) / 60.* TAU
        return {strand: self._strand_generator(a.fn, a.period, t_min * a.rpm) for strand, a in self._animations_by_strand.items()}

def clamp(val):
    return int(max(min(val, 255), 0))

# linear interpolation. looks bad, but is easy, and we only use it for highlighting
def generate_interpolated_color(color1, color2, nlights): 
    R1, G1, B1 = color1
    R2, G2, B2 = color2
    for pos in range(nlights):
        intensity2 =  float(pos) / nlights
        intensity1 = 1. - intensity2
        yield (R1 * intensity1 + R2 * intensity2,
               G1 * intensity1 + G2 * intensity2,
               B1 * intensity1 + B2 * intensity2)

class opc_client(object):
    def __init__(self, host, port, nlights):
        self.nlights = nlights
        self.socket = socket.socket()
        self.socket.connect((host, port))

    def send(self, channel, command, body):
        blen = len(body)
        packet = struct.pack(">BBH%ds" % blen, channel, command, blen, body)
        self.socket.send(packet)

    def highlight(self, strand, start, nlights, color1, color2 = None):
        if color2 is None:
            color2 = color1
        colors = itertools.chain(itertools.islice(itertools.repeat((0,0,0)), start), 
                                 generate_interpolated_color(color1, color2, nlights),
                                 itertools.islice(itertools.repeat((0,0,0)), self.nlights - (start + nlights)))
        self.send_leds(strand, colors)

    def multi_highlight(self, highlights):
        """
        highlights should be a list of kwargs equivalent to highlight
        """
        highlights.sort(key=lambda hl: hl.start)
        cur = 0
        colors = []
        for hl in highlights:
            start = hl['start']
            nlights = hl['nlights']
            color1 = hl['color1']
            color2 = hl['color2'] if 'color2' in  hl else hl['color1']
            if start > cur: # we need a blank
                colors.extend(list(itertools.islice(itertools.repeat((0,0,0), start - cur))))
        # TODO finish this

    def clear(self):
        self.send_leds(0, itertools.islice(itertools.repeat((0,0,0)), self.nlights))

    def send_leds(self, strand, colors, **kwargs): 
        # colors is an iterable of (R, G, B) tuples, range 0-1
        channel = strand + 1
        color_bytes = bytearray((clamp(int(component * 255)) for color in colors for component in color))
        body = struct.pack("%ds" % min(len(color_bytes), self.nlights * 3), color_bytes)
        self.send(channel, 0, body, **kwargs)

    def test(self):
        self.send(0, 254, b'')

class opc_segment_fuzzer(opc_client):
    def send(self, channel, command, body, fenceposts=None):
        blen = len(body)
        packet = struct.pack(">BBH%ds" % blen, channel, command, blen, body)
        if fenceposts is None:
            fenceposts = [0] + \
                         list(random.sample(set(filter(lambda f: f < len(packet), [1,2,3,4,5,6,10,100,1000])), 
                                             random.choice([0, 1, 2, 3]))) + \
                         [len(packet)]
            fenceposts.sort()
        else:
            fenceposts = [0] + \
                         fenceposts + \
                         [len(packet)]
            fenceposts.sort()
        #print("Packet fenceposts: %r" % fenceposts)
        for i, post in enumerate(fenceposts[:-1]):
            npost = fenceposts[i+1]
            self.socket.send(packet[post: npost])
            #print("Sent %d:%d" % (post, npost))

class cbreak_terminal(object): # context handler for putting the terminal into and out of cbreak mode
    def __enter__(self):
        self.old_tcattr = termios.tcgetattr(sys.stdin.fileno())
        tty.setcbreak(sys.stdin)
    def __exit__(self, *args):
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.old_tcattr)

if __name__ == "__main__":
    gargs = parser.parse_args()
    readline.parse_and_bind("set editing-mode vi") # Deal with it 🕶
    try:
        readline.read_history_file(gargs.histfile)
    except FileNotFoundError:
        open(gargs.histfile, 'wb').close()
    host = gargs.host
    port = gargs.port
    if gargs.fuzz:
        opcc = opc_segment_fuzzer(host, port, gargs.nlights)
    else:
        opcc = opc_client(host, port, gargs.nlights)
    # opcc.clear() XXX UNCOMMENT THIS
    try:
        with open(gargs.network) as network:
            try:
                params = json.load(network)
            except ValueError:
                traceback.print_exc()
                print("Network was unparseable. Starting anew.")
                params = {"dT": 0.0001}
    except IOError:
        print("Network doesn't exist. starting anew.")
        params = {"dT": 0.0001}
    model = Model2(**params)
    anim = Animator(gargs.nlights)
    j = jps.JPSVM(jps.funcs, jps.ops, jps.args, jps.consts)
    try:
        mstrand = 0
        mstart = 0
        mend = 1
        mcolor = (0, 1, 0)
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
                [c] clear the lights
                [m] measure
                [f] flash all lights
                [s] save the network (to the file given by --network, default network.json)
                [d] display the current model state
                [p] print model state to stdout
                [n] step the model by dT
                [nd][dn] step and display
                [r] run the synaq model
                [j*] edit animations
                 [c] <strands> clear animation on <strands>
                 [p] <strands> <period> <function> set a pattern on a strand
                 [s] <strands> <period> <rpm> <function> spin a pattern on a strand
                 [r] run the animator
                [z] send a packet full of shit
                [N] create a soma on the current measured strip
                [S] create a synapse on the current measured strip
                [C] change neuron/synapse parameters
                [o] display an overview of the network
                """)
            elif raw.startswith("j"):
                try:
                    subcmd = raw[1]
                    if subcmd =="c":
                        strands = raw.split(maxsplit=1)[1]
                        strands = parse_strands(strands)
                        for strand in strands:
                            anim.roll(lambda t: (0, 0, 0), 1, 0)
                    elif subcmd == "p":
                        strands, period, fn_str = raw.split(maxsplit=3)[1:]
                        strands = parse_strands(strands)
                        period = int(period)
                        fn = j.parse_str(fn_str)
                        for strand in strands:
                            anim.roll(strand, fn, period, 0)
                    elif subcmd == "s":
                        strands, period, rpm, fn_str = raw.split(maxsplit=4)[1:]
                        strands = parse_strands(strands)
                        rpm = int(rpm)
                        period = int(period)
                        fn = j.parse_str(fn_str)
                        for strand in strands:
                            anim.roll(strand, fn, period, rpm)
                    elif subcmd == "r":
                        print("Running JPS. Ctrl-C to stop")
                        try:
                            while True:
                                for strand, colors in anim.generate_colors_by_strand().items():
                                    opcc.send_leds(strand, colors)
                        except KeyboardInterrupt:
                            print("Stopped")
                except:
                    print("Fuk u m8")
                    print(traceback.format_exc())
            elif raw.startswith("z"):
                nlights = 1
                if ' ' in raw:
                    nlights = int(raw.split(maxsplit=2)[1])
                if len(raw.split()) > 2:
                    fenceposts = ast.literal_eval(raw.split(maxsplit=2)[2])
                else:
                    fenceposts = None
                opcc.send_leds(0, itertools.islice(itertools.repeat((0xA5, 0xA5, 0xA5)), nlights),
                               fenceposts=fenceposts)
            elif raw == "C":
                with cbreak_termina():
                    print("[j][k] select segment")
                    segs = list(model.generate_segs())
                    i = 0
                    while c not in ("\x1b", "\n"):
                        if c == "j":
                            i = max(i - 1, 0)
                        elif c == "k":
                            i = min(i + 1, len(segs) - 1)
                        seg = segs[i]
                        opcc.highlight(seg['strand'], seg['start'], model.find(seg['key']).nlights, (0, 0, 0.5))
                        c = sys.stdin.read(1)
                
            elif raw == "c":
                opcc.clear()
            elif raw == "r":
                print("Running synaq. Ctrl-C to stop")
                try:
                    while True:
                        for _ in range(gargs.steps):
                            model.step()
                        for strand, colors in model.generate_colors_by_strand().items():
                            opcc.send_leds(strand, colors)
                except KeyboardInterrupt:
                    print("Stopped")
            elif raw in ("d", "n", "nd", "dn"): # Step and/or Display
                if 'n' in raw:
                    model.step()
                if 'd' in raw:
                    for strand, colors in model.generate_colors_by_strand().items():
                        opcc.send_leds(strand, colors)
            elif raw == "s": # Save
                with open(gargs.network, "w") as network:
                    json.dump(model.params(), network, indent=4)
                print("Saved to %s" % gargs.network)
            elif raw == "N": # New Neuron
                sys.stdout.write("I?:")
                I = int(input())
                k, n = model.add({
                        "start": mstart, 
                        "color": mcolor, 
                        "strand": mstrand
                    }, 
                    nlights = mend - mstart, 
                    I = I)
                print("Created Neuron %s: %s" % (k, n))
            elif raw == "o": # overview
                with cbreak_terminal():
                    c = None
                    print("[j][k] select prev/next segment")
                    print("[m] copy to measuring tape")
                    segs = list(model.generate_segments())
                    i = 0
                    while c not in ("\x1b", "\n"):
                        c = sys.stdin.read(1)
                        if c == "j":
                            i = max(i - 1, 0)
                        elif c == "k":
                            i = min(i + 1, len(segs) - 1)
                        elif c == 'm':
                            mstrand = seg['strand']
                            mstart = seg['start']
                            mend = seg['start'] + model.find(seg['key']).nlights
                            print("copied")
                            break
                        seg = segs[i]
                        thing = model.find(seg['key'])
                        if isinstance(thing, Neuron):
                            opcc.highlight(seg['strand'], 
                                           seg['start'], 
                                           model.find(seg['key']).nlights,
                                           (0,0, 1))
                        elif isinstance(thing, Synapse):
                            opcc.highlight(seg['strand'], 
                                           seg['start'], 
                                           model.find(seg['key']).nlights,
                                           (0, 1, 0))
                        print("%s: %r\n%r" % (seg['key'], repr(seg), repr(thing)))
            elif raw == "S": # New Synapse
                print("[enter] select, [esc] cancel")
                with cbreak_terminal():
                    c = None
                    neuron_segs = list(model.generate_segments(typ=Neuron))
                    preseg = None # presynaptic neuron's segment desc
                    postseg = None # postsynaptic neuron's segment desc
                    i = 0
                    # Select presynaptic neuron
                    print("Select presynaptic neuron [j][k] prev/next")
                    opcc.highlight(neuron_segs[0]['strand'], 
                                   neuron_segs[0]['start'], 
                                   model.find(neuron_segs[0]['key']).nlights, 
                                   (0, 0, 0.5))
                    while c not in ("\x1b", "\n"):
                        c = sys.stdin.read(1)
                        if c == "j":
                            i = max(i - 1, 0)
                        elif c == "k":
                            i = min(i + 1, len(neuron_segs) - 1)
                        elif c == "\n":
                            preseg = neuron_segs[i]
                            break
                        seg = neuron_segs[i]
                        opcc.clear()
                        opcc.highlight(seg['strand'], seg['start'], model.find(seg['key']).nlights, (0, 0, 0.5))
                    if preseg is None:
                        print("Cancelled")
                        continue
                    else:
                        print("Presynaptic: %s" % preseg['key'])
                    # Select postsynaptic neuron
                    print("Select postsynaptic neuron [j][k] prev/next")
                    opcc.highlight(neuron_segs[i]['strand'], 
                                   neuron_segs[i]['start'], 
                                   model.find(neuron_segs[i]['key']).nlights, 
                                   (0.5, 0, 0))
                    c = None
                    while c not in ("\x1b", "\n"):
                        c = sys.stdin.read(1)
                        if c == "j":
                            i = max(i - 1, 0)
                        elif c == "k":
                            i = min(i + 1, len(neuron_segs) - 1)
                        elif c == "\n":
                            postseg = neuron_segs[i]
                            break
                        seg = neuron_segs[i]
                        opcc.highlight(seg['strand'], seg['start'], model.find(seg['key']).nlights, (0.5, 0, 0))
                    if postseg is None:
                        print("Cancelled")
                        continue
                    else:
                        print("Postsynaptic: %s" % postseg['key'])
                    # Select reversedness
                    rev = False
                    print("[r] reverse neuron (they go blue->red)")
                    opcc.highlight(mstrand, mstart, mend - mstart, (0, 0, 0.5), (0.5, 0, 0))
                    c = None
                    while c not in ("\x1b", "\n"):
                        c = sys.stdin.read(1)
                        if c == "r":
                            rev = not rev
                        elif c == '\x1b':
                            rev = None
                        if rev: # red->blue
                            opcc.highlight(mstrand, mstart, mend - mstart, (0.5, 0, 0), (0, 0, 0.5))
                        else: # blue->red
                            opcc.highlight(mstrand, mstart, mend - mstart, (0, 0, 0.5), (0.5, 0, 0))
                    if rev is None:
                        print("Cancelled")
                        continue
                    else:
                        print("Reverse: %s" % rev)
                sys.stdout.write("Weight?:")
                weight = input()
                weight = float(weight)
                sys.stdout.write("Model length?:")
                length = input()
                length = int(length)
                model.connect({
                                "strand": mstrand,
                                "color": mcolor,
                                "start": mstart,
                              },
                              preseg['key'], 
                              postseg['key'], 
                              weight = weight,
                              length = length,
                              nlights = mend - mstart, 
                              reverse = rev)
            elif raw == "m": # measuring tape
                print("Measuring. [t][y] move start, [u][i] to move both, [o][p] move end")
                print("[j][k] to change channels down/up")
                print("[q][w][e] to increase R/G/B, [a][s][d] to decrease")
                print("[esc] or [enter] to exit")
                with cbreak_terminal():
                    c = None
                    while c not in ('\x1b', '\n'): # escape, enter
                        sys.stdout.write("\r\033[Kstrand:%d\tsegment:%d:%d\tcolor: %s" % (mstrand, mstart, mend, mcolor))
                        #opcc.clear()
                        opcc.highlight(mstrand, mstart, mend - mstart, mcolor)
                        c = sys.stdin.read(1)
                        if c == "p" or c == "i":
                            mend = min(mend + 1, gargs.nlights)
                        if c == "o" or c == "u":
                            mend = max(mend - 1, mstart + 1)
                        if c == "t" or c == "u":
                            mstart = max(mstart - 1, 0)
                        if c == "y" or c == "i":
                            mstart = min(mstart + 1, mend - 1)
                        if c == "j":
                            opcc.send_leds(mstrand, [(0,0,0)] * gargs.nlights)
                            mstrand = max(mstrand - 1, 0)
                        if c == "k":
                            opcc.send_leds(mstrand, [(0,0,0)] * gargs.nlights)
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
                                mb = max(mb - .125, 0)
                            mcolor = (mr, mg, mb)
                        if c == '.':
                            mstart = 0
                            mend = 1
                sys.stdout.write("\n")
            else:
                print("No.")
            
    except EOFError:
        print("Bye.")
    except KeyboardInterrupt:
        print("Ouch!")
    finally:
        readline.write_history_file(gargs.histfile)
