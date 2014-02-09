/* This can be fetched using sane and published methods: we know the
   1435:5800 vendor and device ids. For now, hardcode it.
   
   But we do want to use this file instead of the full /dev/mem, as it
takes care of the variable base address and lets us setup non-root
permissions.

 */

#define PFS_FPGA_MMAP_FILE "/sys/bus/pci/devices/0000:03:00.0/resource0"

#define CRC_POLY 0xa001
#define PIX_H 4240 // number of rows
#define PIX_W 536 // number of columns

#define CCD_P1   (1 << 16)  // Parallel 1
#define CCD_P2   (1 << 17)  // Parallel 2
#define CCD_P3   (1 << 18)  // Parallel 3
#define CCD_TG   (1 << 19)  // Transfer Gate
#define CCD_S1   (1 << 20)  // Serial 1
#define CCD_S2   (1 << 21)  // Serial 2
#define CCD_RG   (1 << 22)  // Reset Gate
#define CCD_SW   (1 << 23)  // Summing Well
#define CCD_DCR  (1 << 24)  // DC Restore
#define CCD_IR   (1 << 25)  // Integrate Reset
#define CCD_I_M  (1 << 26)  // Integrate Minus
#define CCD_I_P  (1 << 27)  // Integrate Plus
#define CCD_CNV  (1 << 28)  // ADC Convert
#define CCD_SCK  (1 << 29)  // ADC SCK Burst
#define CCD_DG   (1 << 30)  // Draig Gate
#define CCD_IRQ  (1 << 31)  // Interrupt
#define CCD_CRC  (1 << 15)  // CRC Control

#define R_DDR_RD_DATA		(0x50/4)
#define R_DDR_COUNT		(0x58/4)
#define	R_BR_WR_DATA		(0x14/4)
#define	R_BR_ADDR		(0x18/4)
#define	R_WPU_CTRL		(0x20/4)
#define	R_WPU_COUNT		(0x24/4)
#define	R_WPU_START_STOP	(0x28/4)
#define	R_WPU_STATUS		(0x2C/4)

// Control register bits:
#define EN_SYNCH	(1<<0)
#define WPU_RST		(1<<1)
#define WPU_TEST	(1<<2)

