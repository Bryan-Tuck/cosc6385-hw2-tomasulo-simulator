# Qing
# 21st May 2017
# Extended by Bryan E. Tuck, Oct 2026: configuration and program come from an
# input file (parse_input.py), multi-issue, branch prediction, final
# register/memory dump.
'''
usage: python main.py [input_file] [--issue-width N]
  input_file defaults to code.in (the original program with the original
  hard-coded configuration; see parse_input.py for the file format).
  --issue-width overrides the "Issue width = N" line of the input file.
'''
import sys
from parse_input import parse_input
from machine import machine
from issue import issue
from exe import exe
from mem import mem
from wb import wb
from commit import commit, print_ROB

MAX_CYCLES = 1000000

# function: run the machine until everything has committed
def run(m):
    cycle = 1
    while ((len(m.ROB)>0) | (cycle==1) | (m.ld_sd_mem.busy==1)
           | (m.PC.PC<len(m.instructions))):
        '''ISSUE stage'''
        issue(m, cycle)
        '''EXE stage'''
        exe(m, cycle)
        '''MEM stage'''
        mem(m, cycle)
        '''CDB stage'''
        wb(m, cycle)
        '''COMMIT stage'''
        commit(m, cycle)
        # cycle number
        cycle +=1
        if cycle > MAX_CYCLES:
            raise RuntimeError('more than %d cycles: is the program an infinite loop?' % MAX_CYCLES)
    # total cycles = last cycle in which anything happened (commit or memory write)
    last = 0
    for entry in m.committed:
        for column in (entry.issue, entry.exe, entry.mem, entry.cdb, entry.commit):
            if len(column) > 0:
                last = max(last, column[-1])
    m.cycles = last
    return m

# function: print the instruction status table, registers and memory
def print_results(m):
    # print title
    item = ''.ljust(30)
    item += 'ISSUE'.ljust(15)
    item += 'EXE'.ljust(15)
    item += 'MEM'.ljust(15)
    item += 'WB'.ljust(15)
    item += 'COMMIT'.ljust(15)
    print (item)
    for entry in m.committed:
        print_ROB(entry, m.instructions)
    if len(m.squashed) > 0:
        print ('')
        print ('SQUASHED INSTRUCTIONS'.ljust(30) + 'ISSUE'.ljust(15)
               + 'EXE'.ljust(15) + 'MEM'.ljust(15) + 'WB'.ljust(15) + 'SQUASHED')
        for entry in m.squashed:
            item = m.instructions[entry.PC].ljust(30)
            item += str(entry.issue).ljust(15)
            item += str(entry.exe).ljust(15)
            item += str(entry.mem).ljust(15)
            item += str(entry.cdb).ljust(15)
            item += str([entry.squashed])
            print (item)
    print ('')
    print ('REGISTER VALUES')
    print ('value: ' + ' '.join('R%d=%s' % (i, m.reg_int[i]) for i in range(32)))
    print ('value: ' + ' '.join('F%d=%s' % (i, m.reg_fp[i]) for i in range(32)))
    print ('')
    print ('NON-ZERO MEMORY VALUES')
    print ('Addresses'.ljust(12) + 'Values')
    for addr in range(len(m.memory)):
        if m.memory[addr] != 0:
            print (str(addr).ljust(12) + str(m.memory[addr]))
    print ('')
    n = len(m.committed)
    ipc = float(n) / m.cycles if m.cycles > 0 else 0.0
    print ('Issue width = %d: committed %d instructions in %d cycles, IPC = %.3f'
           % (m.cfg.issue_width, n, m.cycles, ipc))
    print ('Branches resolved = %d, mispredicted = %d, squashed instructions = %d'
           % (m.branches, m.mispredictions, len(m.squashed)))

# function: command line -> (input path, issue width override or None)
def parse_args(argv):
    path = 'code.in'
    width = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--issue-width':
            if i + 1 >= len(argv):
                raise ValueError('--issue-width needs a value')
            width = int(argv[i + 1])
            i += 2
        elif a.startswith('--'):
            raise ValueError('unknown option %s' % a)
        else:
            path = a
            i += 1
    return path, width

if __name__ == '__main__':
    try:
        path, width = parse_args(sys.argv[1:])
        cfg = parse_input(path)
        if width is not None:
            if not (1 <= width <= 4):
                raise ValueError('Issue width must be between 1 and 4 (got %d)' % width)
            cfg.issue_width = width
    except (IOError, OSError) as e:
        sys.stderr.write('cannot read input: %s\n' % e)
        sys.exit(1)
    except ValueError as e:
        sys.stderr.write('%s\n' % e)
        sys.exit(1)
    m = machine(cfg)
    try:
        run(m)
    except (ValueError, RuntimeError) as e:
        sys.stderr.write('simulation error: %s\n' % e)
        sys.exit(2)
    print_results(m)
