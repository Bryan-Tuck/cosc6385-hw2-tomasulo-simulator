# Qing
# 21st May 2017
# Extended by Bryan E. Tuck, Oct 2026: multi-issue, decoded instructions
# instead of split(' '), branch prediction at issue with a RAT checkpoint
# per branch, R0 hardwired to zero.

"""
Each cycle, issue up to issue_width instructions in program order:
1. put the instruction in the ROB
2. put it in a RS / the ld_sd_queue, reading operands through the RAT
3. update the RAT
Issue stops at the first instruction that finds no free ROB entry, RS or
load/store queue slot (the later ones wait). Instructions in the same group
are renamed one after another, so a later one sees the ROB tag of an
earlier one. A branch is predicted at issue (branch.py); a predicted-taken
branch ends the group because fetch is redirected, a predicted-not-taken
one lets the group continue with the fall-through instruction.
"""
from init import ld_sd_entry, ROB_entry
from init import INT_ALU_OPS, FP_ADD_OPS, FP_MUL_OPS, BRANCH_OPS, LDSD_OPS
from branch import predict

# function: find a tag for ld_sd_entry
def find_tag_new_ldsd_entry(ld_sd_queue, size_ld_sd_queue):
    existing_tag = []
    tag_pool = []
    for i in range(len(ld_sd_queue)):
        existing_tag.append(ld_sd_queue[i].ld_sd_tag)
    for i in range(size_ld_sd_queue):
        tag_pool.append('ldsd'+str(i))
    return sorted(set(tag_pool)-set(existing_tag))[0]

# function: read a register through the RAT -> (tag, value, valid)
def read_operand(register, rat_int, rat_fp):
    if register[0] == 'F':
        source = rat_fp[int(register[1:])]
    else:
        source = rat_int[int(register[1:])]
    if type(source) == str:
        return source, None, 0
    return None, source, 1

# function put ins into ROB
def put_ins_into_ROB(ROB, PC, cycle, ins, ldsd_tag):
    ROB.append(ROB_entry())
    ROB[-1].ROB_tag = 'ROB'+str(PC.next_rob)
    PC.next_rob = (PC.next_rob+1) % PC.size_ROB
    ROB[-1].PC = PC.PC
    ROB[-1].op = ins.op
    ROB[-1].dest_tag = ins.dest       # '' for Sd and branches
    ROB[-1].ldsd_tag = ldsd_tag
    ROB[-1].issue.append(cycle)
    return ROB[-1]

# function: put ins into reservation station
def put_ins_into_rs(station, index, ins, ROB, rat_int, rat_fp):
    entry = station[index]
    entry.busy = 1
    entry.op = ins.op
    # reg 1
    entry.tag_1st, entry.value_1st, entry.valid_1st = read_operand(ins.src1, rat_int, rat_fp)
    # reg 2 / immediate
    if ins.src2 is not None:
        entry.tag_2nd, entry.value_2nd, entry.valid_2nd = read_operand(ins.src2, rat_int, rat_fp)
    else:
        entry.tag_2nd = None
        entry.value_2nd = ins.imm
        entry.valid_2nd = 1
    # dest_tag
    entry.dest_tag = ROB[-1].ROB_tag

# function: put a branch into rs (both operands are registers, like an Add)
def put_branch_into_rs(rs_int_adder, index, ins, rat_int, rat_fp, ROB):
    put_ins_into_rs(rs_int_adder, index, ins, ROB, rat_int, rat_fp)

# function: put ins into ld_sd_queue
def put_ins_into_ldsd(ldsd_tag, ld_sd_queue, ins, ROB, rat_int, rat_fp):
    ld_sd_queue.append(ld_sd_entry())
    # ld_sd_tag
    ld_sd_queue[-1].ld_sd_tag = ldsd_tag
    ld_sd_queue[-1].ready = 0
    ld_sd_queue[-1].committed = 0
    ld_sd_queue[-1].op = ins.op
    if ins.op == 'Sd':
        # data: a value, or the ROB tag that will produce it
        ld_sd_queue[-1].data = rat_fp[int(ins.src1[1:])]
    ld_sd_queue[-1].dest_tag = ROB[-1].ROB_tag
    # immediate and reg value
    ld_sd_queue[-1].immediate = ins.imm
    tag, value, valid = read_operand(ins.base, rat_int, rat_fp)
    ld_sd_queue[-1].reg_tag = tag
    ld_sd_queue[-1].reg_value = value
    ld_sd_queue[-1].valid = valid

# function: check space of reservation station
def check_rs_space(station):
    index = -1
    for i in range(len(station)):
        if station[i].busy == 0:
            index = i
            break
    return index

# update RAT
def update_rat(ROB, rat_int, rat_fp):
    dest = ROB[-1].dest_tag
    if dest == '' or dest == 'R0':    # stores, branches, writes to R0
        return
    if dest[0] == 'F':
        rat_fp[int(dest[1:])] = ROB[-1].ROB_tag
    else:
        rat_int[int(dest[1:])] = ROB[-1].ROB_tag

""""""
def issue(m, cycle):
    PC = m.PC
    ROB = m.ROB
    cfg = m.cfg
    if cycle < PC.resume:           # recovery cycle after a misprediction
        return 0
    issued = 0
    while (issued < cfg.issue_width) and (PC.PC < len(m.instructions)):
        ins = m.decoded[PC.PC]
        op = ins.op
        if len(ROB) >= cfg.size_ROB:
            break
        '''decode'''
        # LD/SD instructions
        if op in LDSD_OPS:
            # check space
            if len(m.ld_sd_queue) >= cfg.size_ld_sd_queue:
                break
            # find ldsd_tag
            ldsd_tag = find_tag_new_ldsd_entry(m.ld_sd_queue, cfg.size_ld_sd_queue)
            # put ins into ROB
            put_ins_into_ROB(ROB, PC, cycle, ins, ldsd_tag)
            # put ins into ld_sd_queue
            put_ins_into_ldsd(ldsd_tag, m.ld_sd_queue, ins, ROB, m.rat_int, m.rat_fp)
            # update RAT
            update_rat(ROB, m.rat_int, m.rat_fp)
            # PC
            PC.PC += 1
        # ALU instructions
        elif (op in INT_ALU_OPS) or (op in FP_ADD_OPS) or (op in FP_MUL_OPS):
            if op in INT_ALU_OPS:
                station = m.rs_int_adder
            elif op in FP_ADD_OPS:
                station = m.rs_fp_adder
            else:
                station = m.rs_fp_multi
            # check space
            index = check_rs_space(station)
            if index < 0:
                break
            # put ins into ROB
            put_ins_into_ROB(ROB, PC, cycle, ins, '')
            # put ins into rs
            put_ins_into_rs(station, index, ins, ROB, m.rat_int, m.rat_fp)
            # update RAT
            update_rat(ROB, m.rat_int, m.rat_fp)
            # PC
            PC.PC += 1
        # branches: use the integer adder's reservation stations
        elif op in BRANCH_OPS:
            # check space
            index = check_rs_space(m.rs_int_adder)
            if index < 0:
                break
            # put ins into ROB
            entry = put_ins_into_ROB(ROB, PC, cycle, ins, '')
            # put ins into rs_int_adder
            put_branch_into_rs(m.rs_int_adder, index, ins, m.rat_int, m.rat_fp, ROB)
            # checkpoint the RAT for recovery
            entry.rat_int_snapshot = list(m.rat_int)
            entry.rat_fp_snapshot = list(m.rat_fp)
            # predict at issue and keep fetching along the predicted path
            entry.pred_taken, entry.pred_target = predict(m.btb, PC.PC)
            PC.PC = entry.pred_target
            issued += 1
            if entry.pred_taken:
                break           # fetch is redirected: the group ends here
            continue
        else:
            raise ValueError('unsupported instruction %s' % ins.text)
        issued += 1
    return issued
