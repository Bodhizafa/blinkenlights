#!/usr/bin/env python3
# (c) 2017 Landon Meernik, beerware license
# vim: set fileencoding=utf8
import argparse
import readline
import socket
import sys
import struct

parser = argparse.ArgumentParser()
parser.add_argument("--host", type=str, help="OPC host:port", default="10.4.20.2")
parser.add_argument("--histfile", type=str, help="History file", default=".opcc_history")
parser.add_argument("--port", type=int, default=42024)

def opc_send(socket, channel, command, body):
    blen = len(body)
    packet = struct.pack(">BBH%ds" % blen, channel, command, blen, body)
    socket.send(packet)

def opc_leds(socket, channel, leds): # leds is a list of (R, G, B) tuples, range 0-1
    color_bytes = [int(byte * 255) for color in leds for byte in color]
    print(repr(color_bytes))
    body = struct.pack("%ds" % (3 * len(leds)), bytearray(color_bytes))
    print(repr(body))
    opc_send(socket, channel, 0, body)

if __name__ == "__main__":
    gargs = parser.parse_args()
    readline.parse_and_bind("set editing-mode vi") # Deal with it 🕶
    try:
        readline.read_history_file(gargs.histfile)
    except FileNotFoundError:
        open(gargs.histfile, 'wb').close()
    sock = socket.socket()
    host = gargs.host
    port = gargs.port
    sock.connect((host, port))
    
    try:
        # I wrote all this neat cli parser shit for fuck.py, prolly shoulda made it more reusable, sho' would be nice here.
        while True:
            sys.stdout.write("🍆 ")
            raw = input()
            if raw.strip() == '':
                print("No.")
                continue
            elif raw == "t" : # test
                print("test")
                opc_send(sock, 0, 254, b'')
            elif raw == "pt": # protocol test
                if ' ' in raw:
                    _, chan = raw.split()
                    chan = int(chan)
                else:
                    chan = 0
                print("Channel %s test" % chan)
                opc_leds(sock, chan, [(0.5, 0, 0), (0, 0.5, 0), (0, 0, 0.5)])
            
    except EOFError:
        print("Bye.")
    except KeyboardInterrupt:
        print("Ouch!")
    finally:
        readline.write_history_file(gargs.histfile)
