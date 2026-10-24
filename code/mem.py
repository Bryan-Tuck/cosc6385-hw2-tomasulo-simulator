# Qing
# 26th May 2017
# Extended by Bryan E. Tuck, Oct 2026: forwarding checks every older store
# (not only the nearest one), forwarding takes its own MEM cycle, stores go
# to memory from commit.py only, the memory port serves committed stores and
# loads, a load leaves the queue when its data returns.

'''
1. Ld forward check from older Sds in ld_sd_queue (one forward per cycle)
    -- walk the older stores, nearest first:
         unknown address        -> wait
         same address, has data -> forward (1 cycle in MEM)
         same address, no data  -> wait
         other address          -> keep looking
       none matched             -> the load may go to memory
2. advance the memory port (single-ported, non-pipelined)
    -- once a LD gets its data, put the result on the CDB queue and remove
       the LD from the queue
    -- a SD writes memory when its access finishes and leaves the queue then
       (it was sent to the port at commit; while the write is in progress
       younger loads to the same address still forward from it)
3. send the oldest load that may go to memory into the port
    -- the LD keeps its queue entry until its data returns
    -- stores enter the port at commit (commit.py)
'''
from init import fu_result
from exe import find_ROB_entry

def is_number(x):
    return (type(x)==int)|(type(x)==float)

# function: forward check from older sds -> ('forward', value) | ('wait', None) | ('memory', None)
def forward_check_from_sd(ld_sd_queue, index):
    for i in reversed(range(index)):
        if (ld_sd_queue[i].op=='Sd'):
            if ld_sd_queue[i].ready == 0:
                return 'wait', None
            if (ld_sd_queue[i].address == ld_sd_queue[index].address):
                if is_number(ld_sd_queue[i].data):
                    return 'forward', ld_sd_queue[i].data
                return 'wait', None
    return 'memory', None

# function: put entry into ld_sd_mem
def put_entry_into_ld_sd_mem(ld_sd_mem, entry, rob):
    ld_sd_mem.busy = 1
    ld_sd_mem.cycle = 0
    ld_sd_mem.address = entry.address
    ld_sd_mem.dest_tag = entry.dest_tag
    ld_sd_mem.op = entry.op
    ld_sd_mem.entry = rob
    ld_sd_mem.ldsd_entry = entry
    if ld_sd_mem.op == 'Sd':
        ld_sd_mem.data = entry.data

# function: mem
def mem(m, cycle):
    ld_sd_queue = m.ld_sd_queue
    ld_sd_mem = m.ld_sd_mem
    time_ld_sd_mem = m.cfg.time_ld_sd_mem
    '''forwarding check for Ld instructions whose address is known'''
    for index in range(len(ld_sd_queue)):
        element = ld_sd_queue[index]
        if (element.op=='Ld') and (element.ready==1) and (element.addr_cycle < cycle) and not element.in_mem:
            status, data = forward_check_from_sd(ld_sd_queue, index)
            if status == 'forward':
                rob = find_ROB_entry(m.ROB, element.dest_tag)
                # Ld gets data: 1 cycle in MEM, result on the CDB queue
                rob.mem.append(cycle)
                m.results_buffer.append(fu_result(value=data, dest_tag=element.dest_tag, cycle=cycle))
                # remove the Ld instruction
                ld_sd_queue.remove(element)
                break
    '''ld_sd_mem execution'''
    if ld_sd_mem.busy == 1:
        rob = ld_sd_mem.entry
        # write mem starting cycle
        if ld_sd_mem.cycle == 0:
            rob.mem.extend([cycle, cycle+time_ld_sd_mem-1])
        # cycle ++
        ld_sd_mem.cycle +=1
        # get the data for Ld or reach the memory for Sd
        if ld_sd_mem.cycle == time_ld_sd_mem:
            ld_sd_mem.busy = 0
            if ld_sd_mem.op == 'Ld':
                # put Ld data into results_buffer
                data = m.memory[ld_sd_mem.address]
                m.results_buffer.append(fu_result(value=data, dest_tag=ld_sd_mem.dest_tag, cycle=cycle))
                # the data has returned: remove the Ld instruction
                if ld_sd_mem.ldsd_entry in ld_sd_queue:
                    ld_sd_queue.remove(ld_sd_mem.ldsd_entry)
            # put data into memory for Sd, then dequeue it
            else:
                m.memory[ld_sd_mem.address] = ld_sd_mem.data
                if ld_sd_mem.ldsd_entry in ld_sd_queue:
                    ld_sd_queue.remove(ld_sd_mem.ldsd_entry)
    '''fetch the oldest load that may go to memory into ld_sd_mem'''
    if (ld_sd_mem.busy==0)&(len(ld_sd_queue)>0):
        for index in range(len(ld_sd_queue)):
            element = ld_sd_queue[index]
            if (element.op=='Ld') and (element.ready==1) and not element.in_mem:
                status, data = forward_check_from_sd(ld_sd_queue, index)
                # all previous Sd addresses are known and none matches
                if status == 'memory':
                    rob = find_ROB_entry(m.ROB, element.dest_tag)
                    put_entry_into_ld_sd_mem(ld_sd_mem, element, rob)
                    element.in_mem = 1
                    break
