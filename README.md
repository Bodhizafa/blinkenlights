# Blinkenlights

This is a repo of various things I use to blink a large number of LEDs to visualize a neural network. It's based on the Hodgkin-Huxley model of neuron conductance.

There's also a mini-language for making simple-ish patterns in jps.py, I use it for testing, much more sophisticated tools for making LED patterns have since been written by others.

A video of it in action can be found here: https://vimeo.com/354540007

It's not clean (in either human language or computer ones) or idiomatic, and I'm not sure anyone other than me has ever run it. That said, it does work, and has been known to trap hippies.

The mathematical model is in Neuron.py (with a half baked CUDA reimplementation that I haven't finished due to summer 2020 being cancelled in cuda/)

Entry point is in opcc.py, which can be used to run various tests and create networks.

Framethworing happens on a beaglebone black running opcd.c, which reformats the images and uses a really shady memory map to DMA into pru_main.c, which does signal generation.

In theory, one could hook light strands directly to pins, in practice I use a bunch of RS485 line drivers to make the signal go farther cause 3.3v signals just don't have enough oomph to get up in a tree.

In theory, it can be installed on a fresh beaglebone debian installation and run using `sudo make more_magic` but I haven't tried since October 2019 and for a 10 year old devkit, they break compat unfortunately often.

Everything else is either historical or random support detritus for making the "new" (i.e. non uio-pruss) PRU drivers behave reasonably.
