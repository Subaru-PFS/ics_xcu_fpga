#!/bin/bash

# Return the name of a pfs group-accessible memory resource file. This lets us
# avoid running as root and takes care of the variable base address.
#

BUS_ID=$(get_fpga_bus_id.sh)
if test "$BUS_ID"; then
    echo "/sys/bus/pci/devices/$BUS_ID/resource0"
    exit 0
else
    echo "Cannot find the RTD FPGA board on the bus!" >&2
    exit 1
fi

