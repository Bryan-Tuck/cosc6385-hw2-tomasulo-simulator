# Bryan E. Tuck
# Oct 2026
'''
Parse the simulator input file (format from programming-tomasulo.pdf):

               # of rs   Cycles in EX   Cycles in Mem   # of FUs
Integer adder     2          1                             1
FP adder          3          3                             1
FP multiplier     2         20                             1
Load/store unit   3          1              4              1

ROB entries = 128
Issue width = 2
R1=10, R2=20, F2=30.1
Mem[4]=1, Mem[8]=2, Mem[12]=3.4

Add.d F1, F2, F3
Ld F4, 8(R1)
Bne R2, R3, -12

Everything is case-insensitive; commas are optional. Lines starting with
'#' or '//' are comments. Any configuration line may be omitted; the
defaults are the values that were hard-coded in the original main.py, and
the issue width defaults to 1. Registers and memory default to zero.
'''
import re
from init import decode_instruction, is_instruction

class config(object):
    def __init__(self):
        # defaults = the configuration hard-coded in the original main.py
        self.size_rs_int_adder = 4
        self.time_fu_int_adder = 1
        self.num_fu_int_adder = 1
        self.size_rs_fp_adder = 3
        self.time_fu_fp_adder = 4
        self.num_fu_fp_adder = 1
        self.size_rs_fp_multi = 2
        self.time_fu_fp_multi = 15
        self.num_fu_fp_multi = 1
        self.size_ld_sd_queue = 5
        self.time_ld_sd_exe = 1
        self.time_ld_sd_mem = 5
        self.num_fu_ld_sd = 1
        self.size_ROB = 64
        self.issue_width = 1
        self.reg_int = [0] * 32
        self.reg_fp = [0] * 32
        self.memory = [0] * 256
        self.instructions = []        # canonical text, for the output table
        self.decoded = []             # instruction records

_UNIT_NAMES = (('integer adder', 'int_adder'),
               ('int adder', 'int_adder'),
               ('fp adder', 'fp_adder'),
               ('fp multiplier', 'fp_multi'),
               ('fp mult', 'fp_multi'),
               ('load/store unit', 'ld_sd'),
               ('load store unit', 'ld_sd'),
               ('load/store', 'ld_sd'),
               ('ld/sd', 'ld_sd'))

def _number(text):
    text = text.strip()
    try:
        return int(text)
    except ValueError:
        return float(text)

def _fu_line(cfg, unit, numbers, lineno):
    if unit == 'ld_sd':
        if len(numbers) == 4:
            rs, ex, mem, fus = numbers
        elif len(numbers) == 3:
            rs, ex, mem = numbers
            fus = 1
        else:
            raise ValueError('line %d: load/store unit needs "# of rs, EX cycles, '
                             'Mem cycles, # of FUs"' % lineno)
        cfg.size_ld_sd_queue = rs
        cfg.time_ld_sd_exe = ex
        cfg.time_ld_sd_mem = mem
        cfg.num_fu_ld_sd = fus
    else:
        if len(numbers) == 3:
            rs, ex, fus = numbers
        elif len(numbers) == 4:        # a Mem column was given; ignore it
            rs, ex, _, fus = numbers
        elif len(numbers) == 2:
            rs, ex = numbers
            fus = 1
        else:
            raise ValueError('line %d: %s needs "# of rs, EX cycles, # of FUs"'
                             % (lineno, unit))
        setattr(cfg, 'size_rs_' + unit, rs)
        setattr(cfg, 'time_fu_' + unit, ex)
        setattr(cfg, 'num_fu_' + unit, fus)
    for v in (rs, ex, fus):
        if v < 1:
            raise ValueError('line %d: configuration values must be >= 1' % lineno)

_REG_INIT = re.compile(r'\b([RF])(\d+)\s*=\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)')
_MEM_INIT = re.compile(r'\bMEM\s*\[\s*(\d+)\s*\]\s*=\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)')
_SETTING = re.compile(r'^([A-Za-z][A-Za-z /_-]*?)\s*[=:]\s*(.+)$')

def parse_input(path):
    cfg = config()
    with open(path) as f:
        lines = f.read().splitlines()
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if line == '' or line.startswith('#') or line.startswith('//'):
            continue
        low = line.lower()
        # table header
        if 'of rs' in low or 'cycles in' in low:
            continue
        # FU table rows
        matched = False
        for name, unit in _UNIT_NAMES:
            if low.startswith(name):
                rest = line[len(name):].replace(',', ' ').split()
                try:
                    numbers = [int(t) for t in rest]
                except ValueError:
                    raise ValueError('line %d: non-integer in FU table: "%s"'
                                     % (lineno, raw))
                _fu_line(cfg, unit, numbers, lineno)
                matched = True
                break
        if matched:
            continue
        # instructions
        if is_instruction(line):
            try:
                ins = decode_instruction(line)
            except ValueError as e:
                raise ValueError('line %d: %s' % (lineno, e))
            cfg.decoded.append(ins)
            cfg.instructions.append(ins.text)
            continue
        # register / memory initialization (several per line, comma separated)
        if _REG_INIT.search(line.upper()) or _MEM_INIT.search(line.upper()):
            up = line.upper()
            for kind, num, val in _REG_INIT.findall(up):
                num = int(num)
                if num > 31:
                    raise ValueError('line %d: no register %s%d' % (lineno, kind, num))
                if kind == 'R':
                    if num == 0:
                        continue            # R0 is hardwired to 0
                    cfg.reg_int[num] = _number(val)
                else:
                    cfg.reg_fp[num] = _number(val)
            for addr, val in _MEM_INIT.findall(up):
                addr = int(addr)
                if addr > 255:
                    raise ValueError('line %d: memory address %d out of range (0-255)'
                                     % (lineno, addr))
                cfg.memory[addr] = _number(val)
            continue
        # "name = value" settings
        m = _SETTING.match(line)
        if m:
            key = re.sub(r'[\s_-]+', ' ', m.group(1).strip().lower())
            val = m.group(2).strip()
            try:
                if key in ('rob entries', 'rob size', 'rob'):
                    cfg.size_ROB = int(val)
                elif key == 'issue width':
                    cfg.issue_width = int(val)
                else:
                    raise ValueError('unknown setting "%s"' % m.group(1).strip())
            except ValueError as e:
                raise ValueError('line %d: %s' % (lineno, e))
            continue
        raise ValueError('line %d: cannot parse "%s"' % (lineno, raw))
    # checks
    if not (1 <= cfg.issue_width <= 4):
        raise ValueError('Issue width must be between 1 and 4 (got %d)' % cfg.issue_width)
    if cfg.size_ROB < 1:
        raise ValueError('ROB entries must be >= 1')
    if len(cfg.decoded) == 0:
        raise ValueError('no instructions found in %s' % path)
    return cfg
