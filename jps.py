import ast
import sys
import math
import itertools
from collections import namedtuple
from pprint import pprint
from astpp import dump as astdump

TAU = math.pi * 2
period = 10
strand_len = 10

class COLOR(object):
    pass

class NUMBER(object):
    pass

# Type system symbol signature
# type_out is the type produced by the thing, types_in is a list of argument types
# Funcs with no args have types_in=(), non-function symbols have types_in=None
# impl is either a value (for a constant), None (for a pattern arg), or a function(for a function)
sig = namedtuple("signature", ['name', 'type_out', 'types_in', 'impl'])
# All color are clamped between 0 and 1. HDR is for hippies.
# numbers cannot be negitive (there's no USub, and Sub clamps at 0, so making one should be impossible)

funcs = [
    # value functions - Take theta and produce 0 to 1. Should rougly follow cosine in phase-ness
    sig("Cos", NUMBER, (NUMBER,), lambda th: (math.cos(th) + 1) / 2),
    sig("Sin", NUMBER, (NUMBER,), lambda th: (math.sin(th) + 1) / 2),
    sig("Sqr", NUMBER, (NUMBER,), lambda th: 1 if th < TAU / 2 else 0),
    sig("Tri", NUMBER, (NUMBER,), lambda th: th / (TAU / 2) if th < TAU / 2 else 1 - (th / (TAU / 2))),
    # Interpolaters - take a value and return an RGB tuple
    sig("R",   COLOR, (NUMBER,), lambda v: (v, 0, 0)),
    sig("G",   COLOR, (NUMBER,), lambda v: (0, v, 0)),
    sig("B",   COLOR, (NUMBER,), lambda v: (0, 0, v)),
    sig("Y",   COLOR, (NUMBER,), lambda v: (v, v, 0)),
    sig("C",   COLOR, (NUMBER,), lambda v: (0, v, v)),
    sig("M",   COLOR, (NUMBER,), lambda v: (v, 0, v)),
    sig("W",   COLOR, (NUMBER,), lambda v: (v, v, v)),
]

# Unary and binary operators - turned into name-mangled function calls
ops = [
    # Unary ~
    sig(ast.Invert, COLOR, (COLOR,),           lambda rgb: (1 - rgb[0], 1 - rgb[1], 1 - rgb[2])),
    sig(ast.Invert, NUMBER, (NUMBER,),         lambda v: 1 - v),
    # Binary + additive blending
    sig(ast.Add, COLOR, (COLOR, COLOR),        lambda rgbl, rgbr: (min(rgbl[0] + rgbr[0], 1),
                                                                   min(rgbl[1] + rgbr[1], 1),
                                                                   min(rgbl[2] + rgbr[2], 1))),
    sig(ast.Add, NUMBER, (NUMBER, NUMBER),     lambda vl, vr: vl + vr),

    # Binary - subtractive blending
    sig(ast.Sub, NUMBER, (NUMBER, NUMBER),     lambda vl, vr: max(vl - vr, 0)),
    sig(ast.Sub, COLOR, (COLOR, COLOR),        lambda rgbl, rgbr: (max(rgbl[0] - rgbr[0], 0),
                                                                   max(rgbl[1] - rgbr[1], 0),
                                                                   max(rgbl[2] - rgbr[2], 0))),

    # Binary * multiply blending
    sig(ast.Mult, NUMBER, (NUMBER, NUMBER),    lambda vl, vr: vl * vr),
    sig(ast.Mult, COLOR, (COLOR, COLOR),       lambda rgbl, rgbr: (min(rgbl[0] * rgbr[0], 1),
                                                                   min(rgbl[1] * rgbr[1], 1),
                                                                   min(rgbl[2] * rgbr[2], 1))),
    sig(ast.Mult, COLOR, (NUMBER, COLOR),      lambda vl, rgbr: (min(vl * rgbr[0], 1),
                                                                 min(vl * rgbr[1], 1),
                                                                 min(vl * rgbr[2], 1))),
    sig(ast.Mult, COLOR, (COLOR, NUMBER),      lambda rgbl, vr: (min(rgbl[0] * vr, 1),
                                                                 min(rgbl[1] * vr, 1),
                                                                 min(rgbl[2] * vr, 1))),
    # binary / numeric division
    sig(ast.Div, NUMBER, (NUMBER, NUMBER),     lambda vl, vr: vl / vr),
    sig(ast.Div, COLOR, (COLOR, NUMBER),       lambda rgbl, vr: (1.0, 1.0, 1.0) if vr == 0 else (
                                                                 min(rgbl[0] / vr, 1),
                                                                 min(rgbl[1] / vr, 1),
                                                                 min(rgbl[2] / vr, 1))),
    # binary // screen blending
    sig(ast.FloorDiv, COLOR, (COLOR, COLOR),   lambda rgbl, rgbr: (1 - ((1 - rgbl[0]) * (1 - rgbr[0])),
                                                                   1 - ((1 - rgbl[1]) * (1 - rgbr[1])),
                                                                   1 - ((1 - rgbl[2]) * (1 - rgbr[2])))),
]

args = [sig('T', NUMBER, None, None)]

consts = [
    sig('QTR', NUMBER, None, TAU / 4.),         # QuarTeR turn
    sig('THR', NUMBER, None, TAU / 3.),         # THiRd turn
    sig('HLF', NUMBER, None, TAU / 2.),         # HaLF turn
    sig('TTH', NUMBER, None, 2. * TAU / 3.),    # Two THirds turn
    sig('TQT', NUMBER, None, 3. * TAU / 4.),    # Three Quarter Turn
    sig('TAU', NUMBER, None, TAU),              # full turn

    sig('Red', COLOR, None, (1., 0., 0.)),
    sig('Green', COLOR, None, (0., 1., 0.)),
    sig('Blue', COLOR, None, (0., 0., 1.)),
    sig('White', COLOR, None, (1., 1., 1.)),
    sig('Black', COLOR, None, (0., 0., 0.)),
]

mangle_abbrevs_by_type = {
    NUMBER: "N",
    COLOR: "C",
}

# We don't support all of these, but we might as well have infra for it
names_by_op  = {
    ast.UAdd: "UAdd",
    ast.USub: "USub",
    ast.Not: "Not",
    ast.Invert: "Invert",
    ast.Add: "Add",
    ast.Sub: "Sub",
    ast.Mult: "Mult",
    ast.Div: "Div",
    ast.FloorDiv: "FloorDiv",
    ast.Mod: "Mod",
    ast.Pow: "Pow",
    ast.LShift: "LShift",
    ast.RShift: "RShift",
    ast.BitOr: "BitOr",
    ast.BitXor: "BitXor",
    ast.BitAnd: "BitAnd",
    #ast.MatMult: "MatMult" #python >3.5 only, which I don't have right now.
}

class TrippingBallsError(Exception):
    @staticmethod
    def print_node(node):
        if type(node) is ast.Name:
            return node.id
        else:
            return repr(node)
    def __init__(self, string, node):
        super().__init__(string + " " + self.print_node(node))

class JPSVM(object):
    def __init__(self, funcs, ops, args, consts):
        # globals passed to eval - contains all constant, mangled op and mangled function names. Values are impls
        self.globals_by_name = {}
        # symbol tables
        self.var_types_by_name = {}
        self.func_types_by_name_types_in = {}
        self.op_types_by_op_types_in = {}
        self.args = []

        for name, type_out, _, val in consts:
            assert _ is None, "Constant %s not allowed types_in." % name
            self._check_name(name, internal=True)
            self.globals_by_name[name] = val
            self.var_types_by_name[name] = type_out
        for name, type_out, _, _ in args:
            self.args.append(name)
            self.var_types_by_name[name] = type_out
        for name, type_out, types_in, impl in funcs:
            self._check_name(name, internal=True)
            name_types_in = (name, types_in)
            assert name_types_in not in self.func_types_by_name_types_in, "Function name/type %r already exists" % (name_types_in,)
            assert name not in names_by_op
            self.func_types_by_name_types_in[name_types_in] = type_out
            self.globals_by_name[self._mangle(*name_types_in)] = impl
        for op, type_out, types_in, impl in ops:
            op_types_in = (op, types_in)
            assert op_types_in not in self.func_types_by_name_types_in, "Operator name/type %r already exists" % (op_types_in,)
            self.op_types_by_op_types_in[op_types_in] = type_out
            self.globals_by_name[self._mangle(*op_types_in)] = impl
        pprint(self.globals_by_name)

    @staticmethod
    def _mangle(name, types_in):
        type_abbrevs = [mangle_abbrevs_by_type[type_in] for type_in in types_in]
        if name in names_by_op:
            name = names_by_op[name]
        return "_".join(itertools.chain([name], type_abbrevs))

    def _check_name(self, name, internal=False):
        assert name not in self.globals_by_name, "Name %s already exists" % name
        assert "_" not in name, "Name %s cannot contain underscores" % name
        if internal:
            assert name[0].isupper(), "Name %s must begin with a capital" % name
        else:
            assert name[0].islower(), "Name %s must begin with a lowercase" % name

    def _mogrify_ast_r(self, node, types_by_node): 
        print("mogrifying %s", node)
        if type(node) is ast.BinOp:
            l = self._mogrify_ast_r(node.left, types_by_node)
            r = self._mogrify_ast_r(node.right, types_by_node)
            op_types_in = (type(node.op), (types_by_node[l], types_by_node[r]))
            if op_types_in not in self.op_types_by_op_types_in:
                raise TrippingBallsError("Don't know how to do this", node)
            typ = self.op_types_by_op_types_in[op_types_in]
            name = self._mangle(*op_types_in)
            new_node = ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=[l, r], keywords=[])
            types_by_node[new_node] = typ
            return new_node
        elif type(node) is ast.UnaryOp:
            o = self._mogrify_ast_r(node.operand, types_by_node)
            op_types_in = (type(node.op), (types_by_node[o]))
            if op_types_in not in self.op_types_by_op_types_in:
                raise TrippingBallsError("Don't know how to do this " + str(op_types_in), astdump(node))
            typ = self.op_types_by_op_types_in[op_types_in]
            name = self._mangle(*op_types_in)
            new_node = ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=[o], keywords=[])
            types_by_node[new_node] = typ
            return new_node
        elif type(node) is ast.Call:
            args = [self._mogrify_ast_r(arg, types_by_node) for arg in node.args]
            if type(node.func) is not ast.Name:
                raise TrippingBallsError("Name isn't normal", astdump(node))
            name_types_in = (node.func.id, tuple([types_by_node[arg] for arg in args]))
            if name_types_in not in self.func_types_by_name_types_in:
                raise TrippingBallsError("Don't know how to %s(%r) " % name_types_in)
            typ = self.func_types_by_name_types_in[name_types_in]
            name = self._mangle(*name_types_in)
            new_node = ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=args, keywords=[])
            types_by_node[new_node] = typ
            return new_node
        elif type(node) is ast.Name:
            if node.id in self.var_types_by_name:
                types_by_node[node] = self.var_types_by_name[node.id] 
            else:
                raise TrippingBallsError("What's this?", node)
            return node
        elif type(node) is ast.Num:
            types_by_node[node] = NUMBER
            return node
        elif type(node) is ast.Tuple:
            node.elts = [self._mogrify_ast_r(elt, types_by_node) for elt in node.elts]
            if len(node.elts) != 3:
                raise TrippingBallsError("Color is wrong.", node)
            for i, elt in enumerate(node.elts, 1):
                if types_by_node[elt] is not NUMBER:
                    raise TrippingBallsError("Numbers must be numbers. %s" % i, node)
            types_by_node[node] = COLOR
            return node
        else:
            raise TrippingBallsError("Cannot deal with node.", node)

    def parse_str(self, arg_str):
        types_by_node = {}
        a = self._mogrify_ast_r(ast.parse(arg_str, mode="eval").body, types_by_node) # strip off the outer Expression() node
        print(astdump(a))
        if types_by_node[a] is not COLOR:
            raise TrippingBallsError("That's not a color...", a)
        lamb = ast.Lambda(args=ast.arguments(args=[ast.arg(arg=arg, annotation=None) for arg in self.args],
                                             vararg=None, kwonlyargs=[],
                                             kw_defaults=[], kwarg=None, defaults=[ast.Num(n=0)]),
                      body=a)
        fn_ast = ast.Expression(body=lamb)
        for node in ast.walk(fn_ast): # ast.fix_missing_locations seems to not.
            node.lineno, node.col_offset = (0,0)
        co = compile(fn_ast, filename="<jps>", mode="eval")
        fn = eval(co, self.globals_by_name)
        return fn

