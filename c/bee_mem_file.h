/* Return the filename of the Spartan-6 FPGA memory, preferably as found by probing the PCI bus.

 This can be fetched using sane and published methods: we know the
1435:5800 vendor and device ids. But we provide a hardcoded default.
   
 But we do want to use this file instead of the full /dev/mem, as it
takes care of the variable base address and lets us setup non-root
permissions.

*/

#ifndef PFS_FPGA_BUSID
#define PFS_FPGA_BUSID "0000:03:00.0"
#endif

#define PFS_FPGA_DEV_DIR     "/sys/bus/pci/devices/" PFS_FPGA_BUSID

#define PFS_FPGA_MMAP_FILE   PFS_FPGA_DEV_DIR "/resource0"
#define PFS_FPGA_RESET_FILE  PFS_FPGA_DEV_DIR "/reset"

