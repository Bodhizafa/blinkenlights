#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 28 16:19:21 2014

ACHTUNG!
ALLES TURISTEN UND NONTEKNISCHEN LOOKENPEEPERS!
DAS KOMPUTERMASCHINE IST NICHT FUR DER GEFINGERPOKEN UND MITTENGRABEN! 
ODERWISE IST EASY TO SCHNAPPEN DER SPRINGENWERK, BLOWENFUSEN UND POPPENCORKEN MIT SPITZENSPARKEN.
IST NICHT FUR GEWERKEN BEI DUMMKOPFEN. 
DER RUBBERNECKEN SIGHTSEEREN KEEPEN DAS COTTONPICKEN HANDER IN DAS POCKETS MUSS.
ZO RELAXEN UND WATSCHEN DER BLINKENLICHTEN.

@author: Sharri, Landon
"""

import math
import random
import sys
import uuid
import struct
import io
import collections
import itertools

class WhatTheFuck(Exception):
    pass

def color_mult(val, color):
    R, G, B = color
    R *= val
    G *= val
    B *= val
    return (R, G, B)

class MoreAbstractModel(object):
    def __init__(self,
                 dT,
                 neurons=None,
                 synapses=None):
        self._dT = dT
        self._t = 0.
        if neurons:
            self._neurons = {k: Neuron(**args) for k, args in neurons.items()}
        else:
            self._neurons = {}
        if synapses:
            self._synapses = {k: (Synapse(self._neurons[prekey], self._neurons[postkey], **args), prekey, postkey) for k, (args, prekey, postkey) in synapses.items()}
        else:
            self._synapses = {}

    def find(self, key):
        if key in self._neurons:
            return self._neurons[key]
        elif key in self._synapses:
            return self._synapses[key][0]
        else:
            raise WhatTheFuck("What the fuck is %s?" % key)

    def unfind(self, thing):
        for k, v in self._neurons.items():
            if v is thing:
                return k
        for k, v in self._synapses.items():
            if v[0] is thing:
                return k
        raise WhatTheFuck("Couldn't unfind %s" % thing)

    def step(self):
        self._t += self._dT
        for n in self._neurons.values():
            n.step(self._dT)
        for syn, prekey, postkey in self._synapses.values():
            syn.step()

    def params(self):
        return {
            "dT": self._dT,
            "synapses": {k: (s.params(), prekey, postkey) for k, (s, prekey, postkey) in self._synapses.items()},
            "neurons": {k: n.params() for k, n in self._neurons.items()}
        }

    def add(self, **kwargs):
        n = Neuron(**kwargs)
        k = str(uuid.uuid4())
        self._neurons[k] = n
        return (k, n)

    def connect(self, prekey, postkey, **kwargs):
        k = str(uuid.uuid4())
        s = Synapse(self._neurons[prekey], self._neurons[postkey], **kwargs)
        self._synapses[k] = (s, prekey, postkey)
        return (k, s)

class Model2(MoreAbstractModel): # What Single Responsibility Principle?
    default_scale = (1. / 255., 0)
    def __init__(self,
                 dT,
                 neurons=None,
                 synapses=None,
                 segments=None):
        """ 
            segments is a list of:
            {
                "strand": strand (0 indexed, not OPC channel),
                "start": <first LED>, 
                "key": <neuron or synapse key>, 
                "color": (R, G, B) ranged 0-1,
                "scale": (multiplier, offset) floats, should result in v being between 0 and 1
            }
            and they get put into segments_by_strand as:
            {
                "start": <first LED>
                "thing": <reference to Neuron, Synapse, or Blank>
                "color": <color>
                "scale": (<multiplier>, <offset>)
            } 
        """
        super().__init__(dT, neurons, synapses)
        # this becomes a dict of strand: <ordered, nonoverlapping list of segments on that strand>
        segments_by_strand = {} 
        if segments is not None:
            for seg in segments:
                if seg["strand"] not in segments_by_strand:
                    segments_by_strand[seg['strand']] = []
                segments_by_strand[seg["strand"]].append({
                    "start": seg['start'],
                    "thing": self.find(seg['key']),
                    "color": seg['color'],
                    "scale": (seg['scale'][0], seg['scale'][1])
                })
        else:
            segments_by_strand = {}
        for segs in segments_by_strand.values():
            self._fix_segments(segs)
        self.segments_by_strand = segments_by_strand

    def params(self):
        params = super().params()
        params.update({
            "segments": [seg for seg in self.generate_segments() 
                            if (seg['key'] in self._synapses
                                or seg['key'] in self._neurons)] # we don't care about blanks
        })
        return params

    @staticmethod
    def _fix_segments(segs): # mutates segs such that they're contiguous (inserting blanks as necessary) and checks for overlaps
        segs.sort(key=lambda seg: seg['start'])
        newsegs = []
        if segs[0]['start'] != 0:
            newsegs.append({
                "start": 0,
                "thing": Blank(segs[0]['start']),
                "color": (0, 0, 0),
                "scale": (1, 0)
            })

        for i in range(len(segs) - 1):
            seg = segs[i]
            nseg = segs[i + 1]
            segstart = seg['start']
            segend = seg['start'] + seg['thing'].nlights
            nsegstart = nseg['start']
            nsegend = nseg['start'] + nseg['thing'].nlights
            # ensure there's no overlaps
            if segstart >= nsegstart:
                raise WhatTheFuck("Overlapping segments: %r %r" % (segs[i], segs[i+1]))
            # and insert gaps if necessary (this results in an iteration of the loop fizzling, as the next i will be this blank, which won't need another blank added.)
            elif segend < nsegstart:
                nextseg = segs[i + 1]
                newsegs.append({
                    "start": segend,
                    "thing": Blank(nsegstart - segend),
                    "color": (0, 0, 0),
                    "scale": (1, 0)
                })
        # this is inefficient, we could insert them at the right place, buuuut....
        segs.extend(newsegs)
        segs.sort(key=lambda seg: seg['start'])

    def _insert_segment(self, segment):
    # to insert a segment, it must overlap a blank space, and thing must already be filled out
        if segment['strand'] not in self.segments_by_strand:
            self.segments_by_strand[segment['strand']] = []
        segs = self.segments_by_strand[segment['strand']]
        # If we are completely surrounded by a blank, remove it
        to_remove = None
        start = segment['start']
        end = segment['start'] + self.find(segment['key']).nlights
        for i, iseg in enumerate(segs):
            if isinstance(iseg['thing'], Blank):
                istart = iseg['start']
                iend = iseg['start'] + iseg['thing'].nlights
                if istart <= start and iend >= end:
                    to_remove = i
                    break
        if to_remove is not None:
            del segs[to_remove]
        segs.append({
            "start": segment['start'],
            "thing": self.find(segment['key']),
            "color": segment['color'],
            "scale": (segment['scale'][0], segment['scale'][1])})
        self._fix_segments(segs)

    def add(self, segment, **kwargs): 
        # segment is the same as for Model2 params, 
        # but key will be ignored (the new neuron key will be returned)
        # and scale may be omitted (and the default will be used)
        k, n = super().add(**kwargs)
        seg = segment.copy() # don't mutate arguments
        seg['key'] = k
        if 'scale' not in seg:
            seg['scale'] = self.default_scale
        self._insert_segment(seg)
        return (k, n)

    def connect(self, segment, prekey, postkey, **kwargs):
        # seg is the same as for Model2 params, 
        # but key will be ignored (the new neuron key will be returned)
        # and scale may be omitted (and the default will be used)
        k, s = super().connect(prekey, postkey, **kwargs)
        seg = segment.copy()
        seg['key'] = k
        if 'scale' not in seg:
            seg['scale'] = self.default_scale
        self._insert_segment(seg)
        return (k, s)

    def generate_colors(self, strand): # yields a color generator. 
        # I don't reccomend keeping these around across calls to step() or add() or connect()
        segs = self.segments_by_strand[strand]
        for seg in segs:
            for val in seg['thing'].generate_vals():
                yield color_mult(val * seg['scale'][0] + seg['scale'][1], seg['color'])

    def generate_segments(self, typ=None): 
        # generate segment descriptors for segments that are of type typ.
        # if typ is none, generate all segments
        for strand, segs in self.segments_by_strand.items():
            for seg in segs:
                if (typ is None or isinstance(seg['thing'], typ)) and not isinstance(seg['thing'], Blank):
                    yield {
                        "strand": strand,
                        "start": seg['start'],
                        "key": self.unfind(seg['thing']),
                        "color": seg['color'],
                        "scale": list(seg['scale'])
                    }

    def generate_colors_by_strand(self):
        return {
            strand: self.generate_colors(strand)
                for strand in self.segments_by_strand.keys()
        }
            
# XXX No idea if this works anymore. 
# I tried to keep it sane but it hasn't been tested since half of it got vivisected into MoreAbstractModel
class Model(MoreAbstractModel): # old model serializes to a single strand
    def __init__(self, 
                 dT,            # integration step delta
                 neurons=None,  # Map of key: Neuron kwargs
                 synapses=None, # map of key: (Synapse kwargs, pre neuron key, post neuron key)
                 keyorder=None):# Order that neuron or synapse values are serialized (need not be comprehensive)
        super().__init__(dT, neurons, synapses)
        if keyorder:
            self.keyorder = keyorder
        else:
            self.keyorder = []
        for keys, idx in zip(self.keyorder, itertools.count()):
            if isinstance(keys, basestring):
                thing = self.find(keys)
                if type(thing) == Neuron:
                    print("Keyorder entry [%d]%r is a string for a neuron. Assuming you want it green." % (idx, keys))
                    self.keyorder[idx] = [None, keys, None]
                elif type(thing) == Synapse:
                    print("Keyorder entry [%d]%r is a string for a synapse. Assuming you want it blue." % (idx, keys))
                    self.keyorder[idx] = [None, None, keys]
                else:
                    raise WhatTheFuck("Thing is (%r)%r. Expected Neuron or Synapse" % (type(thing), thing))
            if len(self.keyorder[idx]) < 3:
                self.keyorder[idx] += ([None] * len(3 - self.keyorder[keys]))
            if len(self.keyorder[idx]) is not 3:
                raise WhatTheFuck("Keyorder entry [%d]%r is the wrong length." % (idx, self.keyorder[idx]))
            if not set(keyorder[idx]) - set([None]):
                raise WhatTheFuck("Keyorder entry [%d]%r is entirely None." % (idx, self.keyorder[idx]))
        self.buf = io.BytesIO()
    def params(self):
        p = super().params()
        p.update({
            "keyorder": self.keyorder[:],
        })
    def add(self, **kwargs):
        k, n = super().add(**kwargs)
        self.keyorder.append(k)
        return (k, n)
    def header(self):
        return self.keyorder;
    def connect(self, prekey, postkey, **kwargs):
        k, s = super().connect(self, prekey, postkey, **kwargs)
        self.keyorder.append(k)
        return (k, s)
    def step(self, bufferize=True):
        super().step()
        if bufferize:
            self.buf.seek(0)
            for rgbkey, idx in zip(self.keyorder, itertools.count()):
                R, G, B = [self.find(k).lights() if k is not None else itertools.repeat(0) for k in rgbkey]
                #print "%s" % [(r, g, b) for r, g, b in zip(R, G, B)]
                self.buf.write("".join([chr(r) + chr(g) + chr(b) for r, g, b in zip(R, G, B)]))
            self.buf.seek(0)
        """
        if bufferize:
            for k in self.keyorder:
                self.find(k).bufferize(self.buf)
            self.buf.flush()
            self.buf.truncate()
            self.buf.seek(0)
        """
        return v
    def test(self, key):
        self.buf.seek(0)
        key = filter(lambda x: x, key)[0]
        print(key)
        for k in self.keyorder:
            k = filter(lambda x: x, k)[0]
            if k == key:
                print("Found %s" % k)
                if k in self._neurons:
                    self._neurons[k].test(self.buf)
                elif k in self._synapses:
                    self._synapses[k][0].test(self.buf)
            else:
                print("Blanking %s" % k)
                if k in self._neurons:
                    self._neurons[k].blank(self.buf)
                elif k in self._synapses:
                    self._synapses[k][0].blank(self.buf)
        self.buf.flush(),
        self.buf.truncate()
        self.buf.seek(0)

class Blank(object):
    def __init__(self, nlights, intensity=0):
        self.nlights = nlights
        self.intensity = intensity

    def generate_vals(self):
        yield from itertools.islice(itertools.repeat(self.intensity), self.nlights)

    def params(self):
        return {
            "nlights": self.nlights
        }

class Synapse(object):
    def __init__(self, pre, post, weight, length, reverse=True, nlights=None):
        self._weight = weight
        self.pre = pre
        post.inputs.append(self)
        self._length = length
        self._reverse = reverse
        self.nlights = nlights or length
        self._values = collections.deque([0 for _ in range(self._length)]) 

    def step(self):
        self._values.appendleft(self.pre.V)
        self._values.pop()

    def output(self):
        "Effect on postsynaptic current"
        return self._values[0] * self._weight

    def params(self):
        return {"weight": self._weight,
                "reverse": self._reverse,
                "nlights": self.nlights,
                "length": self._length}
    def generate_vals(self):
        #print(self._values)
        vlen = len(self._values)
        if self._reverse:
            pass # TODO
            # yield from (self._values[vlen - (n ) for n in range(nlights))
        else:
            yield from (self._values[int((float(n) / self.nlights) * vlen)] for n in range(self.nlights))
    def lights(self):
        if self._reverse:
            return [clamp(v)for v in reversed(self._values)]
        else:
            return [clamp(v)for v in self._values]
    def bufferize(self, buf):
        if self._reverse:
            buf.write("".join(["\x00\x00" + chr(clamp(v)) for v in reversed(self._values)]))
        else:
            buf.write("".join(["\x00\x00" + chr(clamp(v)) for v in self._values]))
    def test(self, buf):
        if self._reverse:
            buf.write("".join(["\x00\x00\xFF" for v in reversed(self._values)]))
        else:
            buf.write("".join(["\x00\x00\xFF" for v in self._values]))
    def blank(self, buf):
        if self._reverse:
            buf.write("".join(["\x00\x00\x00" for v in reversed(self._values)]))
        else:
            buf.write("".join(["\x00\x00\x00" for v in self._values]))

class Neuron(object):
    def alpha_n(self,v):
        return 0.01*(-v + 10)/(math.exp((-v + 10)/10) - 1) if v != 10 else 0.1
    def beta_n(self,v):
        return 0.125*math.exp(-v/80)
    def alpha_m(self,v):
        return 0.1*(-v + 25)/(math.exp((-v + 25)/10) - 1) if v != 25 else 1
    def beta_m(self,v):
        return 4*math.exp(-v/18)
    def alpha_h(self,v):
        return 0.07*math.exp(-v/20)
    def beta_h(self,v):
        return 1/(math.exp((-v + 30)/10) + 1)

    def __init__(
        self,
        nlights  = 0,     # LED
        ### channel activity ###
        ## setup parameters and state variables
        ## HH Parameters
        V_zero  = -10,    # mV
        I       = 0,      # IDKLOL
        Cm      = 1,      # uF/cm2
        gbar_Na = 120,    # mS/cm2
        gbar_K  = 36,     # mS/cm2
        gbar_l  = 0.3,    # mS/cm2
        E_Na    = 115,    # mV
        E_K     = -12,    # mV
        E_l     = 10.613):# mV
        ## LED parameters
        self.nlights =nlights
        ## HH Parameters
        self.V_zero = V_zero
        self.Cm     = Cm
        self.gbar_Na= gbar_Na    
        self.gbar_K = gbar_K
        self.gbar_l = gbar_l
        self.E_Na   = E_Na
        self.E_K    = E_K
        self.E_l    = E_l
        self._I     = I
        self.I      = 0
        # Initial Conditions
        self.V      = V_zero
        self.m      = self.alpha_m(V_zero)/(self.alpha_m(V_zero) + self.beta_m(V_zero))
        self.n      = self.alpha_n(V_zero)/(self.alpha_n(V_zero) + self.beta_n(V_zero))
        self.h      = self.alpha_h(V_zero)/(self.alpha_h(V_zero) + self.beta_h(V_zero))
        # idx n = value at T - n * dT
        self.inputs  = []

    def step(self, dT):
        "Step the model by dT. Strange things may happen if you vary dT"
        self.I = sum([i.output() for i in self.inputs])

        self.m += dT*(self.alpha_m(self.V)*(1 - self.m) - self.beta_m(self.V)*self.m)
        self.h += dT*(self.alpha_h(self.V)*(1 - self.h) - self.beta_h(self.V)*self.h)
        self.n += dT*(self.alpha_n(self.V)*(1 - self.n) - self.beta_n(self.V)*self.n)
        g_Na = self.gbar_Na*(self.m**3)*self.h
        g_K  = self.gbar_K*(self.n**4)
        g_l  = self.gbar_l 
        self.V += (self._I + self.I - 
                    g_Na*(self.V - self.E_Na) - 
                    g_K*(self.V - self.E_K) - 
                    g_l*(self.V - self.E_l)) / self.Cm * dT
        return self.V
    def __str__(self):
        return "HH Neuron: m: \t%r\tn:%r\th:\t%r\tV:\t%r\tI:%r" % \
                (self.m, self.n, self.h, self.V, self._I)
    def params(self): # return a dict such that you can pass it as kwargs to the constructor and get an equivalent neuron to this one
        return  {
            'nlights':  self.nlights,
            'V_zero':   self.V_zero,
            'Cm':       self.Cm,
            'gbar_Na':  self.gbar_Na,
            'gbar_K':   self.gbar_K,
            'gbar_l':   self.gbar_l,
            'E_Na':     self.E_Na,
            'E_K':      self.E_K,
            'E_l':      self.E_l,
            'I':        self._I
        }
    def lights(self):
        return [clamp(self.V)] * self.nlights
    def generate_vals(self):
        yield from itertools.islice(itertools.repeat(self.V), self.nlights)
    def bufferize(self, buf):
        buf.write(("\x00" + chr(clamp(self.V)) + "\x00") * self.nlights) #G
    def test(self, buf):
        buf.write(("\x00\xFF\x00") * self.nlights) #G
    def blank(self, buf):
        buf.write(("\x00\x00\x00") * self.nlights) #G
