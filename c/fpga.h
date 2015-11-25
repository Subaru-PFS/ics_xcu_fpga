#include <stdint.h>

#include "bee_mem_file.h"

typedef enum { OFF, IDLE, ARMED, READING, FAILED, UNKNOWN } readoutStates;

#define CRC_POLY 0xa001

// Map of BAR0. Probably should get from FPGA definition file.
#define R_ID                    (0x00/4)
#define R_STATUS                (0x04/4)
#define R_EEPROM                (0x08/4)
#define R_DDR_RD_DATA		(0x50/4)
#define R_DDR_WR_DATA	        (0x54/4)
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
#define FIFO_RD_RST	(1<<3)
#define FIFO_WR_RST	(1<<4)
#define WPU_18BIT	(1<<5)
#define WPU_18LOWBITS	(1<<6)

// Default image size. Should probably not be here.
#define PIX_H 4224 // number of rows
#define PIX_W 520  // number of columns (pixels per amp)

#define N_AMPS 8   // number of amps. So the number of pixels in a row is N_AMPS * PIX_W
                   // This is set by the readout hardware.

extern readoutStates readoutState;

extern int configureFpga(const char *mmapname);
extern void releaseFpga(void);
extern void pciReset(void);

extern int resetReadout(int force);
extern int armReadout(int nrows, int doTest, int adc18bit);
extern void finishReadout(void);

extern int sendAllOpcodes(uint32_t *states, uint16_t *durations, int cnt);
extern int sendOneOpcode(uint32_t states, uint16_t duration);

extern uint32_t readWord(void);
extern int readRawLine(int nwords, uint32_t *rowbuf, uint32_t *dataCrc,
		uint32_t *fpgaCrc, uint32_t *dataRow, uint32_t *fpgaRow);
extern int readLine(int npixels, uint16_t *rowbuf,
	     uint32_t *dataCrc, uint32_t *fpgaCrc,
	     uint32_t *dataRow, uint32_t *fpgaRow);
extern int readImage(int nrows, int ncols, int namps, uint16_t *imageBuf);


extern volatile uint32_t *fpgaAddr(void);
extern uint32_t peekWord(uint32_t addr);
extern void pokeWord(uint32_t addr, uint32_t data);
extern int fifoRead(int nBlocks);
extern void fifoWrite(int nBlocks);

