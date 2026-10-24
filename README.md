# COSC 6385 Assignment 2: multi-issue Tomasulo simulator

Bryan E. Tuck, University of Houston, Fall 2026 (Prof. Weidong Shi).

`code/` is the course's single-issue Tomasulo simulator (Python, with a reorder
buffer), extended to issue up to four instructions per cycle in program order and
to predict branches with a one-bit predictor and an 8-entry branch target buffer,
with recovery from mispredictions. The issue width comes from the input file. The
report (`report/report.pdf`) describes what was added, the test cases and the
results at widths 1 to 4.

## Contents

```
README.md
code/            the simulator (Python 3, no packages beyond the standard library)
  main.py          entry point: python main.py [input_file] [--issue-width N]
  parse_input.py   reads the input file (configuration + program)
  init.py          data structures and the instruction decoder
  machine.py       all simulator state, built from the parsed configuration
  issue.py         ISSUE stage (multi-issue, renaming, branch prediction)
  exe.py           EX stage (functional units, address adder, branch resolution)
  branch.py        BTB, one-bit predictor, misprediction recovery
  mem.py           MEM stage (load/store queue, forwarding, memory port)
  wb.py            WB stage (one CDB)
  commit.py        COMMIT stage (up to issue_width per cycle, stores to memory)
  code.in          the starter's program with the configuration it hard-coded
  test_case.txt    the same program in the handout's input format
  data_structure.txt  field list of every record (the starter's, plus the new fields)
tests/           input files, one per test (see the report, Section 4)
results/         simulator output of every test at widths 1, 2, 3 and 4,
                 plus summary.md (cycles and IPC per test and width)
report/          report.pdf and its LaTeX source
```

## How to run

```bash
cd code
python main.py                                  # runs code.in (width 1)
python main.py test_case.txt
python main.py ../tests/t1_independent.txt
python main.py ../tests/t1_independent.txt --issue-width 4
```

`--issue-width N` overrides the `Issue width = N` line of the input file (1 to 4).
The program prints the instruction status table (ISSUE, EX, MEM, WB, COMMIT cycles
of every committed instruction), a second table with the instructions squashed on a
misprediction (and the cycle they were squashed in), the register values, the
non-zero memory values, and two summary lines with the cycle count, IPC, branch count
and misprediction count. Errors go to stderr. A line of the input file that cannot be
read, such as an unknown instruction, is reported with its line number. An issue width
outside 1 to 4, an address outside the 256-byte memory, or a taken branch whose offset
is not a multiple of 4 stops the program with a message.

To reproduce `results/`, run each file in `tests/` at each width, for example:

```bash
cd code
for t in ../tests/*.txt; do for w in 1 2 3 4; do
  python main.py $t --issue-width $w > ../results/$(basename $t .txt).w$w.txt
done; done
```

## Input format

The input file follows the format of the assignment handout. Everything is
case-insensitive, commas are optional, and lines starting with `#` or `//` are
comments. A configuration line that is missing keeps the starter's hard-coded
value; the issue width defaults to 1; registers and memory default to zero. The
example below is `tests/spec_sample.txt`, the handout's sample input with an `Addi`
added so that its loop ends and with the branch offset written in bytes.

```
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
Addi R2, R2, -10
Bne R2, R3, -16
```

Instructions: `Ld`, `Sd`, `Beq`, `Bne`, `Add`, `Add.d`, `Addi`, `Sub`, `Sub.d`,
`Mult.d`. Memory addresses are byte addresses in 0 to 255. A branch offset is in bytes
and is added to PC+4, as in the starter's test case: its `Bne R1 R0 -12`, the eighth
instruction, goes to the sixth, and the `Bne R2, R3, -16` above, the fourth, goes to the
first. The handout's formula `PC+4+offset<<2` would send the starter's branch to byte
address -16, before the start of the program, so the starter's convention is kept.

## Timing conventions

An instruction issued in cycle c can start EX in c+1. A result produced in cycle c is
broadcast on the single CDB in c+1 at the earliest, in completion order. The integer
adder and the address adder are unpipelined; the FP adder and multiplier are pipelined.
A load reads memory the cycle after its address is known, once every older store's
address is known and none matches. If the nearest older store with the same address
has its data, the load forwards from it in one MEM cycle instead. A load leaves the
load/store queue when its data returns; a store leaves when its memory write ends.
Stores write memory at commit. Up to `issue_width` ready instructions commit per cycle,
in order (the commit width follows the issue width, as in the course's sample report
and two-issue example); an instruction commits at the earliest in the cycle after its
write-back. With one CDB, instructions that write a register still broadcast one per
cycle.

Branches are predicted at issue from the BTB (8 entries indexed by the low 3 bits of
the word address; a hit with the one-bit predictor set predicts taken, anything else
predicts not-taken) and resolved at the end of EX. A misprediction detected in cycle n
squashes every younger instruction from the ROB, reservation stations, functional
units, CDB queue and load/store queue, restores the RAT from the checkpoint taken when
the branch issued, and issue resumes from the correct target in cycle n+2. The
report's Section 2 has the full table.

## Checks

For every test the final registers and memory are the same at widths 1, 2, 3 and 4 and
match the hand-computed values listed in the report; on `code.in` they are the values
the unmodified starter computes. Because the starter stalled fetch at every branch and
had no predictor, its cycle table and `results/original_code_in.w1.txt` agree up to the
first `Bne` and differ after it.
