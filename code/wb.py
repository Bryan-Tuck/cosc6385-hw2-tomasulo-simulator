# Qing
# 29th May 2017
# Extended by Bryan E. Tuck, Oct 2026: results carry the cycle they were
# produced in and are broadcast the cycle after, in completion order, one
# per cycle (one CDB); the RAT only takes a value from a broadcast whose tag
# it still holds (needed once two writers of a register can be in flight).

'''
1. broadcast data on cdb
2. fetch data from results queue
3. remove entry in results queue
'''
from exe import find_ROB_entry

# function: broadcast one result
# rat_int, rat_fp, reservation stations, ld_sd_queue, ROB
def broadcast(m, result, cycle):
    dest_tag = result.dest_tag
    value = result.value
    rob = find_ROB_entry(m.ROB, dest_tag)
    if rob is None:
        return
    reg_tag = rob.dest_tag
    # rat_int / rat_fp: only if nobody younger has renamed the register since
    if reg_tag != '':
        if reg_tag[0] == 'R':
            if m.rat_int[int(reg_tag[1:])] == dest_tag:
                m.rat_int[int(reg_tag[1:])] = value
        if reg_tag[0] == 'F':
            if m.rat_fp[int(reg_tag[1:])] == dest_tag:
                m.rat_fp[int(reg_tag[1:])] = value
    # rs list
    rs_list = [m.rs_int_adder, m.rs_fp_adder, m.rs_fp_multi]
    for rs in rs_list:
        for element in rs:
            if element.busy == 0:
                continue
            if (element.tag_1st==dest_tag)&(element.valid_1st==0):
                element.value_1st = value
                element.valid_1st = 1
            if (element.tag_2nd==dest_tag)&(element.valid_2nd==0):
                element.value_2nd = value
                element.valid_2nd = 1
    # ld_sd_queue
    for element in m.ld_sd_queue:
        if (element.op=='Sd')&(element.data==dest_tag):
            element.data = value
        if (element.reg_tag==dest_tag)&(element.valid==0):
            element.reg_value = value
            element.valid = 1
    # ROB
    rob.value = value
    rob.cdb.append(cycle)
    rob.ready = 1

# function: wb
def wb(m, cycle):
    # the oldest result produced in an earlier cycle takes the single CDB
    if len(m.results_buffer)>0:
        if m.results_buffer[0].cycle < cycle:
            result = m.results_buffer.popleft()
            broadcast(m, result, cycle)
