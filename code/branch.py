# Bryan E. Tuck
# Oct 2026
'''
Branch unit: one-bit predictor, BTB, misprediction recovery.

1. BTB with 8 entries, indexed by the low 3 bits of the word address of the
   branch (the instruction index: byte PC = 4 * index). Each entry holds the
   branch PC (tag), its last target, and a 1-bit predictor (last outcome).
   A miss, or a tag mismatch, predicts not-taken.
2. The prediction is made at ISSUE (issue.py); the branch is resolved at the
   end of EX (exe.py calls resolve_branch).
3. On a misprediction detected in cycle n:
     - squash every ROB entry younger than the branch, and everything that
       belongs to them: RS entries (their wait-for tags go with them),
       in-flight FU entries, pending CDB results, load/store queue entries,
       the address adder and the memory port
     - restore the RAT from the checkpoint taken when the branch issued
     - redirect fetch; recovery takes cycle n+1 and issue resumes in n+2
Branch offsets are byte offsets relative to PC+4, the convention of the
starter's test case (Bne R1 R0 -12 jumps back two instructions).
'''
from collections import deque
from init import record

class btb_entry(record):
    _fields = ('valid', 'pc', 'target', 'taken')

def build_btb(num=8):
    return [btb_entry(valid=0, pc=None, target=None, taken=0) for _ in range(num)]

# function: look up the BTB -> (predicted taken, predicted next PC)
def predict(btb, pc):
    entry = btb[pc % len(btb)]
    if entry.valid == 1 and entry.pc == pc and entry.taken == 1:
        return 1, entry.target
    return 0, pc + 1

# function: record the outcome of a resolved branch
def update_btb(btb, pc, taken, target):
    entry = btb[pc % len(btb)]
    entry.valid = 1
    entry.pc = pc
    entry.target = target
    entry.taken = taken

# function: branch target as an instruction index (byte offset / 4)
def branch_target(pc, offset):
    if offset % 4 != 0:
        raise ValueError('byte offset %d is not a multiple of 4 '
                         '(offsets are in bytes, e.g. -12 = two instructions back)' % offset)
    return pc + 1 + offset // 4

# function: find ROB entry by tag (None if it is no longer in the ROB)
def find_ROB_entry(ROB, tag):
    for entry in ROB:
        if entry.ROB_tag == tag:
            return entry
    return None

# function: remove every ROB entry younger than the branch and all their state
def squash_younger(m, branch, cycle):
    tags = set()
    ldsd_tags = set()
    while m.ROB[-1] is not branch:
        entry = m.ROB.pop()
        entry.squashed = cycle
        tags.add(entry.ROB_tag)
        if entry.ldsd_tag:
            ldsd_tags.add(entry.ldsd_tag)
        m.squashed.append(entry)
    # the ROB tail moves back to the slot after the branch
    m.PC.next_rob = (int(branch.ROB_tag[3:]) + 1) % m.PC.size_ROB
    # reservation stations: free the entries (this also clears their tags)
    for rs in (m.rs_int_adder, m.rs_fp_adder, m.rs_fp_multi):
        for element in rs:
            if element.busy == 1 and element.dest_tag in tags:
                element.busy = 0
                element.tag_1st = None
                element.tag_2nd = None
    # functional units
    for name in ('fu_int_adder', 'fu_fp_adder', 'fu_fp_multi'):
        fu = getattr(m, name)
        setattr(m, name, deque(e for e in fu if e.dest_tag not in tags))
    # results waiting for the CDB
    m.results_buffer = deque(r for r in m.results_buffer if r.dest_tag not in tags)
    # load/store queue, address adder, memory port. A committed store keeps
    # its queue entry and the port until its write ends, and its ROB tag may
    # already belong to a squashed instruction, so it is never squashed.
    m.ld_sd_queue = deque(e for e in m.ld_sd_queue
                          if e.committed or e.dest_tag not in tags)
    if m.ld_sd_exe.busy == 1 and m.ld_sd_exe.dest_tag in ldsd_tags:
        m.ld_sd_exe.busy = 0
    if m.ld_sd_mem.busy == 1 and m.ld_sd_mem.op == 'Ld' and m.ld_sd_mem.dest_tag in tags:
        m.ld_sd_mem.busy = 0        # a wrong-path load
    return len(tags)

# function: restore one RAT from a checkpoint
# A checkpointed tag may belong to an instruction that has since broadcast
# (take its value from the ROB) or committed (take the architectural value).
def restore_rat(snapshot, rat, ROB, reg):
    for i in range(len(rat)):
        s = snapshot[i]
        if type(s) == str:
            entry = find_ROB_entry(ROB, s)
            if entry is None:
                rat[i] = reg[i]
            elif len(entry.cdb) != 0:
                rat[i] = entry.value
            else:
                rat[i] = s
        else:
            rat[i] = s

# function: resolve a branch at the end of EX (cycle = detection cycle n)
def resolve_branch(m, rob, value1, value2, cycle):
    ins = m.decoded[rob.PC]
    if ins.op == 'Beq':
        taken = 1 if value1 == value2 else 0
    else:
        taken = 1 if value1 != value2 else 0
    if taken:
        target = branch_target(rob.PC, ins.imm)
    else:
        target = rob.PC + 1
    if target < 0 or target > len(m.instructions):
        raise ValueError('%s at PC %d: target %d is outside the program'
                         % (ins.text, rob.PC, target))
    rob.taken = taken
    rob.target = target
    rob.ready = 1
    m.branches += 1
    update_btb(m.btb, rob.PC, taken, target)
    if (taken != rob.pred_taken) or (target != rob.pred_target):
        rob.mispredicted = 1
        m.mispredictions += 1
        squash_younger(m, rob, cycle)
        restore_rat(rob.rat_int_snapshot, m.rat_int, m.ROB, m.reg_int)
        restore_rat(rob.rat_fp_snapshot, m.rat_fp, m.ROB, m.reg_fp)
        m.PC.PC = target
        m.PC.resume = cycle + 2
