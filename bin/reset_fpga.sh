#!/bin/bash

# Try to reset the FPGA board, by poking at the /sysfs reset file.

BUS_ID=$(get_fpga_bus_id.sh)
if test "$BUS_ID"; then
    echo 1 > "/sys/bus/pci/devices/$BUS_ID/reset"
    exit 0
else
    echo "Cannot find the RTD FPGA board on the bus!" >&2
    exit 1
fi
