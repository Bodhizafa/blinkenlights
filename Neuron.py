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
# Transfer functions - take a float and return a chr
def clamp(val):
    return int(max(min(val, 255), 0))

class WhatTheFuck(Exception):
    pass

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

class Model2(MoreAbstractModel): # new model supports multiple strands (and uses hella generators)
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
        segments = []
        for strand, segs in self.segments_by_strand.items():
           segments.extend(({
                "strand": strand,
                "start": seg['start'],
                "key": self.unfind(seg['thing']),
                "color": seg['color'],
                "scale": list(seg['scale'])
            } for seg in segs))
        params.update({
            "segments": segments
        })
        return params

    @staticmethod
    def _fix_segments(segs): # mutates segs such that it contains enough blanks and doesn't contain overlaps
        segs.sort(key=lambda seg: seg['start'])
        for i in range(len(segs) - 1):
            seg = segs[i]
            segend = seg['start'] + seg['thing'].nlights
            # ensure there's no overlaps
            if segs[i]['start'] + segs[i]['thing'].nlights > segs[i + 1]['start']:
                raise WhatTheFuck("Overlapping segments: %r %r" % (segs[i], segs[i+1]))
            # and insert gaps if necessary (this results in an iteration of the loop fizzling, as the next i will be this blank, which won't need another blank added.)
            elif segs[i]['start'] + segs[i]['thing'].nlights < segs[i + 1]['start']:
                nextseg = segs[i+1]
                segs.insert(i+1, {
                    "start": segend,
                    "thing": Blank(nextseg['start'] - segend),
                    "color": (0, 0, 0),
                    "scale": (1, 0)
                })

    def _insert_segment(self, seg):
        if seg['strand'] not in self.segments_by_strand:
            self.segments_by_strand[seg['strand']] = []
            if seg['start'] != 0:
                self.segments_by_strand[seg['strand']].append({
                    "start": 0,
                    "thing": Blank(seg['start']),
                    "color": (0, 0, 0),
                    "scale": (1, 0)
                })
        segs = self.segments_by_strand[seg['strand']]
        segs.append({
            "start": seg['start'],
            "thing": self.find(seg['key']),
            "color": seg['color'],
            "scale": (seg['scale'][0], seg['scale'][1])})
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
        k, s = super().connect(prekey, postkey, **kwargs)
        # TODO

    def generate_colors(self, strand): # yields a color generator. I don't reccomend keeping these around if you got it before a call to step() or modifying the network
        segs = self.segments_by_strand[strand]
        yield from itertools.chain(*[
            (color_mult(val * seg['scale'][0] + seg['scale'][1], seg['color']) for val in seg['thing'].generate_vals()) 
            for seg in self.segments_by_strand[strand]
        ])

    def generate_colors_by_strand(self):
        return {
            strand: self.generate_colors(strand)
                for strand in self.segments_by_strand.keys()
        }
    
            
def color_mult(val, color):
    R, G, B = color
    R *= val
    G *= val
    B *= val
    return (R, G, B)

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
        self.buf.flush()
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
        self._values = collections.deque([0 for _ in range(self.nlights)]) 
        self._frame = 0

    def step(self):
        if not self._frame % (self._length // self.nlights):
            self._values.popleft()
            self._values.append(self.pre.V)
        self._frame += 1
    def output(self):
        "Effect on postsynaptic current"
        return self._values[0] * self._weight
    def params(self):
        return {"weight": self._weight,
                "reverse": self._reverse,
                "nlights": self.nlights,
                "length": self._length,}
    def generate_vals(self):
        if self._reverse:
            yield from reversed(self._values)
        else:
            yield from self._values
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
