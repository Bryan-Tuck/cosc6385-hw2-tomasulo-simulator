# Qing
# 29th may 2017
# Extended by Bryan E. Tuck, Oct 2026: commit up to issue_width entries per
# cycle, stores go to memory at commit, branches commit in order like
# everything else, R0 stays zero.
'''
Commit the ROB head while it is ready, up to issue_width entries per cycle
(the commit width follows the issue width, as in the course's sample report):
  ALU / Ld : result has been broadcast             -> write the register
  Sd       : address known, data present, port free -> start the memory write
  Beq / Bne: resolved (and recovered from, if mispredicted) -> nothing to write
An entry handled in cycle c gets commit cycle c+1 (the starter's convention:
WB in cycle c, visible at commit in the next cycle). A store's queue entry
is kept until its memory write completes (mem.py).
'''
from init import BRANCH_OPS
from mem import put_entry_into_ld_sd_mem, is_number

# function: print ROB entry
def print_ROB(entry, instructions):
    item = instructions[entry.PC].ljust(30)
    item += str(entry.issue).ljust(15)
    item += str(entry.exe).ljust(15)
    item += str(entry.mem).ljust(15)
    item += str(entry.cdb).ljust(15)
    item += str(entry.commit)
    print(item)

# function: modify architectual reg
def modify_arch_reg(entry, reg_int, reg_fp):
    if entry.dest_tag == '' or entry.dest_tag == 'R0':
        return
    if entry.dest_tag[0] == 'F':
        reg_fp[int(entry.dest_tag[1:])] = entry.value
    elif entry.dest_tag[0] == 'R':
        reg_int[int(entry.dest_tag[1:])] = entry.value

# function: the ld_sd_queue entry of a store at the ROB head
def find_ldsd_entry(ld_sd_queue, ldsd_tag):
    for element in ld_sd_queue:
        if element.ld_sd_tag == ldsd_tag:
            return element
    return None

# function: commit
def commit(m, cycle):
    ROB = m.ROB
    count = 0
    while (len(ROB)>0) and (count < m.cfg.issue_width):
        head = ROB[0]
        if head.op in BRANCH_OPS:
            if head.ready == 0:
                break
        elif head.op == 'Sd':
            element = find_ldsd_entry(m.ld_sd_queue, head.ldsd_tag)
            # address known since an earlier cycle, data present, memory port free
            if (element.ready==0) or (element.addr_cycle >= cycle):
                break
            if not is_number(element.data):
                break
            if m.ld_sd_mem.busy == 1:
                break
            # the entry stays in the queue until the write completes, so
            # younger loads to the same address can still forward from it
            put_entry_into_ld_sd_mem(m.ld_sd_mem, element, head)
            element.committed = 1
        else:
            if len(head.cdb)==0:        # not broadcast yet
                break
            modify_arch_reg(head, m.reg_int, m.reg_fp)
        head.commit.append(cycle+1)
        ROB.popleft()
        m.committed.append(head)
        count += 1
    return count
