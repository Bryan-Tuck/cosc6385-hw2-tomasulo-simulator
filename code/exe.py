# Qing
# 24th May 2017
# Extended by Bryan E. Tuck, Oct 2026: oldest-first dispatch, pipelined vs
# unpipelined units with a configurable number of FUs, dispatch only of
# instructions issued in an earlier cycle, Beq/Bne resolution with
# misprediction recovery (branch.py), squash-safe completion.

'''
1. advance in-flight instructions
    -- for ALU instructions, write results into results_buffer, remove that fu entry
    -- for Beq/Bne, resolve at the end of EX (branch.py recovers on a mispredict)
    -- for LD/SD, write the address back to ld_sd_queue
2. dispatch ready instructions into function units with spare capacity
    -- oldest first (ROB order), only instructions issued in an earlier cycle
    -- remove ALU instructions from rs
    -- don't remove ld/sd instructions
Timing: an instruction issued in cycle c can start EX in cycle c+1; an
unpipelined unit that finishes in cycle n takes a new instruction in n+1;
a pipelined unit accepts one new instruction per cycle (per FU).
'''
from init import fu_entry, fu_result, BRANCH_OPS
from branch import resolve_branch

# function: check rs and return the oldest valid instruction index
def check_valid_ins_in_rs(rs, ROB, cycle):
    index = -1
    best_pos = None
    order = {}
    for pos in range(len(ROB)):
        order[ROB[pos].ROB_tag] = pos
    for i in range(len(rs)):
        if (rs[i].valid_1st==1)&(rs[i].valid_2nd==1)&(rs[i].busy==1):
            pos = order.get(rs[i].dest_tag)
            if pos is None:
                continue
            if ROB[pos].issue[0] < cycle and ((best_pos is None) or (pos < best_pos)):
                index = i
                best_pos = pos
    return index

# function: check ld_sd_queue and return the oldest entry needing an address
def check_valid_ins_in_ldsd(ldsd, ROB, cycle):
    index = -1
    for i in range(len(ldsd)):
        if (ldsd[i].valid==1) & (ldsd[i].ready==0):
            rob = find_ROB_entry(ROB, ldsd[i].dest_tag)
            if rob is not None and rob.issue[0] < cycle:
                index = i
                break
    return index

# function: add entry into fu
def add_entry_into_fu(fu, ins_in_rs):
    fu[-1].cycle = 0
    fu[-1].op = ins_in_rs.op
    fu[-1].value1 = ins_in_rs.value_1st
    fu[-1].value2 = ins_in_rs.value_2nd
    fu[-1].dest_tag = ins_in_rs.dest_tag

# function: find ROB entry by tag (None if it is not in the ROB)
def find_ROB_entry(ROB, tag):
    for entry in ROB:
        if entry.ROB_tag == tag:
            return entry
    return None

# function: complete one instruction leaving a functional unit
def fu_complete(m, element, cycle):
    rob = find_ROB_entry(m.ROB, element.dest_tag)
    if rob is None:                 # squashed earlier in this cycle
        return
    rob.exe.append(cycle)
    if element.op in BRANCH_OPS:
        resolve_branch(m, rob, element.value1, element.value2, cycle)
        return
    result = fu_result()
    result.dest_tag = element.dest_tag
    result.cycle = cycle
    if (element.op=='Add')|(element.op=='Add.d')|(element.op=='Addi'):
        result.value = element.value1 + element.value2
    elif (element.op=='Sub')|(element.op=='Sub.d'):
        result.value = element.value1 - element.value2
    elif (element.op=='Mult.d'):
        result.value = element.value1 * element.value2
    else:
        raise ValueError('unknown op %s in functional unit' % element.op)
    m.results_buffer.append(result)

# function: functional units execution (one cycle for every in-flight entry)
# returns the number of entries that finished this cycle
def fu_exe(m, name, time_fu, cycle):
    fu = getattr(m, name)
    finished = 0
    if len(fu)!=0:
        for element in fu:
            element.cycle += 1
            # write starting cycle
            if element.cycle == 1:
                find_ROB_entry(m.ROB, element.dest_tag).exe.append(cycle)
        # finish cycle
        for element in list(fu):
            fu = getattr(m, name)       # a recovery may have replaced the deque
            if element.cycle == time_fu and element in fu:
                fu.remove(element)
                finished += 1
                fu_complete(m, element, cycle)
    return finished

# function: ld_sd_execution (address adder)
def ld_sd_execution(ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ROB, cycle):
    finished = 0
    if ld_sd_exe.busy == 1:
        element = None
        for candidate in ld_sd_queue:
            if candidate.ld_sd_tag == ld_sd_exe.dest_tag:
                element = candidate
                break
        if element is None:             # squashed meanwhile
            ld_sd_exe.busy = 0
            return 0
        rob = find_ROB_entry(ROB, element.dest_tag)
        # write down starting cycle
        if ld_sd_exe.cycle == 0:
            rob.exe.append(cycle)
        # execute
        ld_sd_exe.cycle += 1
        # write address back to ld_sd_queue
        if ld_sd_exe.cycle == time_ld_sd_exe:
            address = ld_sd_exe.value1 + ld_sd_exe.value2
            if address < 0 or address > 255:
                raise ValueError('%s: address %d is outside the 256-byte memory'
                                 % (element.op, address))
            element.address = address
            element.ready = 1
            element.addr_cycle = cycle
            # write down finish cycle
            rob.exe.append(cycle)
            ld_sd_exe.busy = 0
            finished = 1
    return finished

# function: move ready instructions from a rs into its functional unit
def dispatch_rs(m, rs, name, time_fu, num_fu, pipelined, freed, cycle):
    fu = getattr(m, name)
    if pipelined:
        capacity = num_fu                       # one new instruction per FU per cycle
    else:
        capacity = num_fu - len(fu) - freed     # a unit freed this cycle is used next cycle
    while capacity > 0:
        index = check_valid_ins_in_rs(rs, m.ROB, cycle)
        if index < 0:
            break
        fu.append(fu_entry())
        add_entry_into_fu(fu, rs[index])
        # remove ins from rs
        rs[index].busy = 0
        capacity -= 1
        # first execution cycle happens now (the instruction was issued earlier)
        element = fu[-1]
        element.cycle = 1
        find_ROB_entry(m.ROB, element.dest_tag).exe.append(cycle)
        if element.cycle == time_fu:
            fu.remove(element)
            fu_complete(m, element, cycle)
            fu = getattr(m, name)       # a recovery may have replaced the deque

# function: execution
def exe(m, cycle):
    cfg = m.cfg
    '''execution in fu and ld_sd address calculation'''
    freed_ldsd = ld_sd_execution(m.ld_sd_exe, cfg.time_ld_sd_exe, m.ld_sd_queue, m.ROB, cycle)
    # functional units (the integer adder first: a branch resolves before
    # the other units produce results that may belong to the wrong path)
    freed_int = fu_exe(m, 'fu_int_adder', cfg.time_fu_int_adder, cycle)
    fu_exe(m, 'fu_fp_adder', cfg.time_fu_fp_adder, cycle)
    fu_exe(m, 'fu_fp_multi', cfg.time_fu_fp_multi, cycle)
    '''fetch instructions from rs and ld_sd_queue'''
    # from ld_sd_queue: one address adder, unpipelined
    if (m.ld_sd_exe.busy==0) & (freed_ldsd==0):
        index = check_valid_ins_in_ldsd(m.ld_sd_queue, m.ROB, cycle)
        if index>=0:
            m.ld_sd_exe.busy = 1
            m.ld_sd_exe.cycle = 0
            m.ld_sd_exe.value1 = m.ld_sd_queue[index].reg_value
            m.ld_sd_exe.value2 = m.ld_sd_queue[index].immediate
            m.ld_sd_exe.dest_tag = m.ld_sd_queue[index].ld_sd_tag
            ld_sd_execution(m.ld_sd_exe, cfg.time_ld_sd_exe, m.ld_sd_queue, m.ROB, cycle)
    # from rs
    # int_adder: unpipelined
    dispatch_rs(m, m.rs_int_adder, 'fu_int_adder', cfg.time_fu_int_adder,
                cfg.num_fu_int_adder, False, freed_int, cycle)
    # fp_adder: pipelined
    dispatch_rs(m, m.rs_fp_adder, 'fu_fp_adder', cfg.time_fu_fp_adder,
                cfg.num_fu_fp_adder, True, 0, cycle)
    # fp_multi: pipelined
    dispatch_rs(m, m.rs_fp_multi, 'fu_fp_multi', cfg.time_fu_fp_multi,
                cfg.num_fu_fp_multi, True, 0, cycle)
