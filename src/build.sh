#!/bin/bash

# This is the full build "stanza" from FPGA....cmd_log, extracted after requesting a .bit file 
# after doing a Clean Project.
# The only changes were:
#   - replaced "-intstyle ise" with "-inststyle xflow", which adjusts the tool outputs for "batch mode".
#   - define and use $ROOT, $PROJ, $TARG
#
# In other words, I have no idea what the zillions of options do.
#
# I webbed for Makefiles, but found either toys or things so complex I could not trust them. But given
# our specific needs we almost certainly could.
#
# The final .bit file is identical to that from the ISE, barring four bytes which feel like a timestamp.
#

ROOT=$PWD
PROJ="FPGA35S6045_TOP"
TARG="xc6slx45t-fgg484-2"

# Required for xst to run.
mkdir -p xst/projnav.tmp

# Required inputs for xst (and all the rest?) are: 
#   ${PROJ}.xst
#   ${PROJ}.prj
#   iseconfig/filter.filter
#   ${PROJ}.ut  # for bitgen, looks like an option list.
##   The .vhd files listed in the ${PROJ}.prj file
#
xst -intstyle xflow -filter "$ROOT/iseconfig/filter.filter" -ifn "$ROOT/${PROJ}.xst" -ofn "$ROOT/${PROJ}.syr" 

ngdbuild -filter "iseconfig/filter.filter" -intstyle xflow -dd _ngo -sd ipcore_dir -aul -aut -nt timestamp -uc "hdl_constraints/FPGA35S6045 Top-Level.ucf" -p ${TARG} ${PROJ}.ngc ${PROJ}.ngd  
map -filter "$ROOT/iseconfig/filter.filter" -intstyle xflow -p ${TARG} -w -logic_opt off -ol high -t 1 -xt 0 -register_duplication off -r 4 -global_opt off -mt 2 -ir off -pr off -lc off -power off -o ${PROJ}_map.ncd ${PROJ}.ngd ${PROJ}.pcf 
par -filter "$ROOT/iseconfig/filter.filter" -w -intstyle xflow -ol high -mt 4 ${PROJ}_map.ncd ${PROJ}.ncd ${PROJ}.pcf 
trce -filter $ROOT/iseconfig/filter.filter -intstyle xflow -v 3 -s 2 -n 3 -fastpaths -xml ${PROJ}.twx ${PROJ}.ncd -o ${PROJ}.twr ${PROJ}.pcf 
bitgen -filter "iseconfig/filter.filter" -intstyle xflow -f ${PROJ}.ut ${PROJ}.ncd 

echo
echo "=========================================================================="
echo "To load the FPGA, run something like 'xc3sprog -c xpc -p 0 -v ${PROJ}.bit'"
echo 
echo "   Note: 'xc3sprog -c' lists the bus types, and 'xc3sprog -c xpc' lists the Xilinx Platform Cable bus."
echo "   Note: you might also need to 'setup xc3sprog' if the program is not found."
