#!/usr/bin/env python3
import time
import socket
import argparse
import threading
from fuck import PRU

parser = argparse.ArgumentParser()
parser.add_argument("--len", default=600, type=int)
parser.add_argument("--port", default=42024, type=int)
gargs = None
pru_lock = threading.Lock()

def display_thread_main(*prus): # Ghetto ass shit because I can't figure out why the fucking thing keeps hanging
    start = time.time()
    while True:
        with pru_lock:
            elapsed_min = (time.time() - start) / 60.
            # TODO this
        for pru in prus:
            pru.display()

def accept_thread_main(conn, addr):
    print("accepted")
    hdr = conn.recv(4096)
    print("header %r" % hdr)

if __name__ == "__main__":
    gargs = parser.parse_args()
    pru0 = PRU(0, gargs.len)
    pru1 = PRU(1, gargs.len)
    display_thread = threading.Thread(target=display_thread_main, name="display_thread", args=(pru0, pru1))
    display_thread.daemon = True
    display_thread.start()
    sock = socket.socket()
    print(sock.bind(("0.0.0.0", 42024)))
    sock.listen(128)
    while True:
        conn, addr = sock.accept()
        t = threading.Thread(target=accept_thread_main, name="accept_thread", args=(conn, addr))
        t.daemon = True
        t.start()
