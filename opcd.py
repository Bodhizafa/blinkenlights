#!/usr/bin/env python3
import time
import socket
import argparse
import threading
import struct
from fuck import PRU

parser = argparse.ArgumentParser()
parser.add_argument("--len", default=600, type=int)
parser.add_argument("--port", default=42024, type=int)
gargs = None

def display_thread_main(*prus): # Ghetto ass shit because I can't figure out why the fucking thing keeps hanging
    start = time.time()
    while True:
        elapsed_min = (time.time() - start) / 60.
        # TODO this
        for pru in prus:
            pru.display()
        print('d')


def dispatch_opc(channel, cmd, body):
    global pru0, pru1
    print("OPC dispatch %s %s %s" % (channel, cmd, body))
    if cmd is 254:
        print("testing 0")
        for i in range(15):
            pru0.pattern(i, 1, lambda tau: (0.1, 0.1, 0.1))
            time.sleep(0.25)
        print("testing 1")
        for i in range(15):
            pru1.pattern(i, 1, lambda tau: (0.1, 0.1, 0.1))
            time.sleep(0.25)
        print("tested")
    

def accept_thread_main(conn, addr):
    print("accepted")
    while True:
        ndata = conn.recv(4096)
        print("got %r" % ndata)
        if not ndata:
            print("client left")
            return
        if len(ndata) < 4:
            print("Didn't get whole header")
            continue
        channel, cmd, n = struct.unpack(">BBH", ndata[0:4])
        if len(ndata) != n + 4:
            print("Packet length is %d, not %d" % (len(ndata), n + 4))
            continue
        dispatch_opc(channel, cmd, ndata[4:n+4])

if __name__ == "__main__":
    gargs = parser.parse_args()
    pru0 = PRU(0, gargs.len)
    pru1 = PRU(1, gargs.len)
    pru_pins_by_channel = {

    }
    display_thread = threading.Thread(target=display_thread_main, name="display_thread", args=(pru0,))
    display_thread.daemon = True
    display_thread.start()
    sock = socket.socket()
    print(sock.bind(("0.0.0.0", gargs.port)))
    sock.listen(128)
    while True:
        conn, addr = sock.accept()
        t = threading.Thread(target=accept_thread_main, name="accept_thread", args=(conn, addr))
        t.daemon = True
        t.start()
