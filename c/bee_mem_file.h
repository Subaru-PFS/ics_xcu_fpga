/* Return the filename of the Spartan-6 FPGA memory, preferably as found by probing the PCI bus.

 This can be fetched using sane and published methods: we know the
1435:5800 vendor and device ids. But we provide a hardcoded default.
   
 But we do want to use this file instead of the full /dev/mem, as it
takes care of the variable base address and lets us setup non-root
permissions.

*/

#undef PROBED_FILENAME

#ifdef PROBED_FILENAME
#define PFS_FPGA_MMAP_FILE PROBED_FILENAME
#else
#define PFS_FPGA_MMAP_FILE "/sys/bus/pci/devices/0000:03:00.0/resource0"
#endif
