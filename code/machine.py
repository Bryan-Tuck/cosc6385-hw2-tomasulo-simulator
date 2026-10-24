# Bryan E. Tuck
# Oct 2026
'''
All simulator state in one object, built from a parsed configuration.
The original main.py kept these as module-level variables and passed each
stage a long positional argument list.
'''
from collections import deque
from init import build_rs, ld_sd_exe, ld_sd_mem, PC
from branch import build_btb

class machine(object):
    def __init__(self, cfg):
        self.cfg = cfg
        self.instructions = cfg.instructions    # canonical text
        self.decoded = cfg.decoded              # instruction records
        '''regs, RAT, memory'''
        self.reg_int = list(cfg.reg_int)
        self.reg_fp = list(cfg.reg_fp)
        self.rat_int = list(cfg.reg_int)        # value, or a ROB tag string
        self.rat_fp = list(cfg.reg_fp)
        self.memory = list(cfg.memory)
        '''reservation stations'''
        self.rs_int_adder = build_rs(cfg.size_rs_int_adder)
        self.rs_fp_adder = build_rs(cfg.size_rs_fp_adder)
        self.rs_fp_multi = build_rs(cfg.size_rs_fp_multi)
        '''functional units (in-flight instructions)'''
        self.fu_int_adder = deque()
        self.fu_fp_adder = deque()
        self.fu_fp_multi = deque()
        '''load/store queue, address adder, memory port'''
        self.ld_sd_queue = deque()
        self.ld_sd_exe = ld_sd_exe(busy=0, cycle=0)
        self.ld_sd_mem = ld_sd_mem(busy=0, cycle=0)
        '''ROB, CDB input queue'''
        self.ROB = deque()
        self.results_buffer = deque()
        '''branch predictor'''
        self.btb = build_btb(8)
        '''fetch state'''
        self.PC = PC(PC=0, resume=0, next_rob=0, size_ROB=cfg.size_ROB)
        '''bookkeeping for the output'''
        self.committed = []       # ROB entries in commit order
        self.squashed = []        # wrong-path ROB entries, in squash order
        self.branches = 0         # branches resolved
        self.mispredictions = 0
        self.cycles = 0
