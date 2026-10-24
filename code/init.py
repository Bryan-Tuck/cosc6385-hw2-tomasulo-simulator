# Qing
# 21st May 2017
# Extended by Bryan E. Tuck, Oct 2026:
#   - records are plain classes (the starter used namedtuple classes as
#     mutable records, which works but breaks copy/compare semantics)
#   - instruction decoder: case-insensitive, commas optional, registers above
#     R9/F9, the operand layout of the spec's input format
#   - ROB fields for branches (prediction, RAT checkpoint) and squashing

import re

'''define data types'''
class record(object):
    # mutable record with a fixed field list; unset fields are None
    _fields = ()
    def __init__(self, **kw):
        for f in self._fields:
            setattr(self, f, None)
        for k, v in kw.items():
            setattr(self, k, v)

# reservation station
class rs_entry(record):
    _fields = ('busy', 'op', 'tag_1st', 'value_1st', 'valid_1st',
               'tag_2nd', 'value_2nd', 'valid_2nd', 'dest_tag')
# functional unit
class fu_entry(record):
    _fields = ('cycle', 'op', 'value1', 'value2', 'dest_tag')
# function result (cycle = cycle in which the result was produced)
class fu_result(record):
    _fields = ('value', 'dest_tag', 'cycle')
# ld/sd entry (addr_cycle = cycle in which the address became known;
# committed = 1 while a store's memory write is in progress;
# in_mem = 1 while a load is in the memory port)
class ld_sd_entry(record):
    _fields = ('ld_sd_tag', 'ready', 'op', 'address', 'data', 'dest_tag',
               'immediate', 'reg_tag', 'reg_value', 'valid', 'addr_cycle',
               'committed', 'in_mem')
# ld/sd exe (address adder)
class ld_sd_exe(record):
    _fields = ('busy', 'cycle', 'value1', 'value2', 'dest_tag')
# ld/sd mem (the single memory port; entry = the ROB entry being served)
class ld_sd_mem(record):
    _fields = ('busy', 'cycle', 'op', 'data', 'address', 'dest_tag', 'entry',
               'ldsd_entry')
# ROB_entry
class ROB_entry(record):
    _fields = ('ROB_tag', 'PC', 'op', 'value', 'dest_tag', 'ldsd_tag',
               'issue', 'exe', 'mem', 'cdb', 'commit', 'ready',
               # branch fields
               'pred_taken', 'pred_target', 'taken', 'target',
               'rat_int_snapshot', 'rat_fp_snapshot', 'mispredicted',
               'squashed')
    def __init__(self, **kw):
        record.__init__(self, **kw)
        self.issue = []
        self.exe = []
        self.mem = []
        self.cdb = []
        self.commit = []
        self.ready = 0
        self.squashed = 0
# PC and fetch state
#   PC        index of the next instruction to issue (word address)
#   resume    first cycle in which issue may continue after a misprediction
#   next_rob  running counter for ROB tags (mod size_ROB)
class PC(record):
    _fields = ('PC', 'resume', 'next_rob', 'size_ROB')

'''instruction decoding'''
# canonical spelling of each opcode, keyed by lower case
OPCODES = {'ld': 'Ld', 'sd': 'Sd', 'beq': 'Beq', 'bne': 'Bne',
           'add': 'Add', 'add.d': 'Add.d', 'addi': 'Addi',
           'sub': 'Sub', 'sub.d': 'Sub.d', 'mult.d': 'Mult.d'}
INT_ALU_OPS = ('Add', 'Addi', 'Sub')
FP_ADD_OPS = ('Add.d', 'Sub.d')
FP_MUL_OPS = ('Mult.d',)
BRANCH_OPS = ('Beq', 'Bne')
LDSD_OPS = ('Ld', 'Sd')

# decoded instruction
#   dest   destination register ('' for Sd and branches)
#   src1   first source register (Sd: the data register)
#   src2   second source register (None if the operand is an immediate)
#   imm    immediate / branch offset in bytes (None for 3-register ops)
#   base   base register of Ld/Sd
#   text   canonical text used in the output table
class instruction(record):
    _fields = ('op', 'text', 'dest', 'src1', 'src2', 'imm', 'base')

_REG = re.compile(r'^[RF](\d|[12]\d|3[01])$')
_MEMOP = re.compile(r'^(-?\d+)\((R(?:\d|[12]\d|3[01]))\)$')

def _reg(tok, kind=None):
    tok = tok.upper()
    if not _REG.match(tok):
        raise ValueError('bad register "%s"' % tok)
    if kind == 'R' and tok[0] != 'R':
        raise ValueError('expected an integer register, got "%s"' % tok)
    if kind == 'F' and tok[0] != 'F':
        raise ValueError('expected an FP register, got "%s"' % tok)
    return tok

def _int(tok):
    try:
        return int(tok)
    except ValueError:
        raise ValueError('bad immediate "%s"' % tok)

def is_instruction(line):
    tok = line.replace(',', ' ').split()
    return len(tok) > 0 and tok[0].lower() in OPCODES

# function: decode one assembly line into an instruction record
def decode_instruction(line):
    tok = line.replace(',', ' ').split()
    if len(tok) == 0 or tok[0].lower() not in OPCODES:
        raise ValueError('unknown instruction "%s"' % line)
    op = OPCODES[tok[0].lower()]
    ins = instruction(op=op, dest='', src1=None, src2=None, imm=None, base=None)
    args = tok[1:]
    if op in LDSD_OPS:
        # Ld Fa, offset(Ra) -- allow a space between offset and (Ra)
        memop = ''.join(args[1:]).upper()
        m = _MEMOP.match(memop)
        if len(args) < 2 or not m:
            raise ValueError('bad load/store operands in "%s"' % line)
        reg = _reg(args[0], 'F')
        if op == 'Ld':
            ins.dest = reg
        else:
            ins.src1 = reg
        ins.imm = int(m.group(1))
        ins.base = m.group(2)
        ins.text = '%s %s %d(%s)' % (op, reg, ins.imm, ins.base)
    elif op in BRANCH_OPS:
        if len(args) != 3:
            raise ValueError('bad branch operands in "%s"' % line)
        ins.src1 = _reg(args[0], 'R')
        ins.src2 = _reg(args[1], 'R')
        ins.imm = _int(args[2])
        ins.text = '%s %s %s %d' % (op, ins.src1, ins.src2, ins.imm)
    elif op == 'Addi':
        if len(args) != 3:
            raise ValueError('bad Addi operands in "%s"' % line)
        ins.dest = _reg(args[0], 'R')
        ins.src1 = _reg(args[1], 'R')
        ins.imm = _int(args[2])
        ins.text = '%s %s %s %d' % (op, ins.dest, ins.src1, ins.imm)
    else:
        if len(args) != 3:
            raise ValueError('bad ALU operands in "%s"' % line)
        kind = 'R' if op in INT_ALU_OPS else 'F'
        ins.dest = _reg(args[0], kind)
        ins.src1 = _reg(args[1], kind)
        ins.src2 = _reg(args[2], kind)
        ins.text = '%s %s %s %s' % (op, ins.dest, ins.src1, ins.src2)
    return ins

# function: build rs
def build_rs(num):
    rs = []
    for _ in range(num):
        temp = rs_entry()
        temp.busy = 0
        rs.extend([temp])
    return rs
