/* This program controls the CCD clocks, collects the resulting image data,
 * and sends it to stdout.
 */
#include<unistd.h>
#include<sys/types.h>
#include<sys/mman.h>
#include<stdio.h>
#include<stdlib.h>
#include<fcntl.h>
#include<assert.h>

#include "fpga.h"

#define CRC_POLY 0xa001

volatile unsigned int *fpga;
unsigned int bram_addr;
unsigned int output_states;

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

#define SET_1(x) output_states |= (x)
#define SET_0(x) output_states &= ~(x)

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

// send_opcode(d) causes the output states currently stored in the global
// output_states to be driven on the outputs for d*40ns
inline void send_opcode(unsigned int duration) {
	fpga[R_BR_ADDR] = bram_addr;
	fpga[R_BR_WR_DATA] = output_states | duration;
	bram_addr += 4;
}

// write_row_readout() is a routine to write blockram with opcodes that read
// a row of CCD pixels.
unsigned int write_row_readout(unsigned int start) {

	int i;
	bram_addr = start;

	// initial states:
	SET_0(CCD_P1);
	SET_1(CCD_P2);
	SET_0(CCD_P3);
	SET_1(CCD_TG);
	SET_1(CCD_S1);
	SET_0(CCD_S2);
	SET_1(CCD_RG);
	SET_1(CCD_SW);
	SET_0(CCD_DCR);
	SET_0(CCD_IR);
	SET_0(CCD_I_M);
	SET_0(CCD_I_P);
	SET_1(CCD_CNV);
	SET_0(CCD_SCK);
	SET_1(CCD_DG);
	SET_0(CCD_IRQ);
	SET_0(CCD_CRC);
	// arbitrary 4000ns -- initial states should already be present
	send_opcode(100);

	for(i=0; i<PIX_W; i++) {
		// Each loop iteration here does 1 serial pixel
		SET_0(CCD_S1);
		SET_1(CCD_S2);
		SET_0(CCD_RG);
		SET_1(CCD_DCR);
		SET_1(CCD_IR);
		SET_1(CCD_SCK);
		send_opcode(16);

		SET_1(CCD_RG);
		SET_0(CCD_SCK);
		send_opcode(8);

		SET_1(CCD_S1);
		SET_0(CCD_S2);
		SET_0(CCD_SW);
		SET_0(CCD_IR);
		SET_0(CCD_CNV);
		send_opcode(8);

		SET_0(CCD_DCR);
		send_opcode(8);

		SET_1(CCD_I_M);
		send_opcode(120);

		SET_0(CCD_I_M);
		SET_1(CCD_SW);
		send_opcode(8);

		SET_1(CCD_I_P);
		send_opcode(120);

		SET_0(CCD_I_P);
		send_opcode(4);

		SET_1(CCD_CNV);
		send_opcode(44);
	}

	// parallel clocking:
	SET_1(CCD_P1);
	SET_0(CCD_RG);
	SET_1(CCD_DCR);
	send_opcode(1000);

	SET_0(CCD_P2);
	SET_0(CCD_TG);
	SET_1(CCD_CRC);
	send_opcode(1000);
	
	SET_1(CCD_P3);
	SET_0(CCD_CRC);
	send_opcode(1000);

	SET_0(CCD_P1);
	send_opcode(1000);

	SET_1(CCD_P2);
	SET_1(CCD_TG);
	send_opcode(1000);

	SET_1(CCD_P1);
	send_opcode(1000);

	SET_1(CCD_RG);
	send_opcode(50);

	SET_0(CCD_DCR);
	send_opcode(2);

	return bram_addr - 4;
}

int main(void) {
	int fd;
	unsigned int i, j, x, b, c, end_addr, words_ready;
	unsigned short crc;

	assert(4 == sizeof(unsigned int));
	fd = open(PFS_FPGA_MMAP_FILE, O_RDWR|O_SYNC);
	if (fd == -1) {
		perror("open(/dev/mem):");
		return 0;
	}
	fpga = mmap(0, getpagesize(), PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
	if (fpga == MAP_FAILED) {
		perror("mmap:");
		return 0;
	}

	// Reset WPU, disable synch clock
	fpga[R_WPU_CTRL] = WPU_RST;
	// Load waveform into blockram
	end_addr = write_row_readout(0);
	// Set parameters
	// START_STOP register wants D-word addresses.
	fpga[R_WPU_START_STOP] = (end_addr/4) << 16;
	fpga[R_WPU_COUNT] = PIX_H; // FPGA wants N-1 for N loops.
	// At this point the master must get acknowledgement that
	// all units are ready via network communications.
	// Start and stop synch clock
	fpga[R_WPU_CTRL] = WPU_RST | EN_SYNCH;
	fpga[R_WPU_CTRL] = WPU_RST;
	// Release WPU reset
	fpga[R_WPU_CTRL] = 0;
	// At this point the master must again get acknowledgement that
	// all units are ready.
	// Start clock
	fpga[R_WPU_CTRL] = EN_SYNCH | WPU_TEST; // Enable test pattern
	// Read data and calculate CRC
	usleep(10000);
	//
	// Just to clarify the four layers of looping that follows:
	// i increments for each row
	// j increments for each D-word of data
	// b increments for each byte
	// c increments for each bit (to compute CRC)
	words_ready = 0;
	for (i=0; i<PIX_H; i++) {
		crc = 0;
		for (j=0; j<PIX_W * 4; j++) {
		// PIX_W * 4 because each pixel generates 4 D-words of data
			if (words_ready == 0) {
				words_ready = fpga[R_DDR_COUNT];
				while (words_ready == 0) {
					usleep(1000);
					words_ready = fpga[R_DDR_COUNT];
				}
			}
			x = fpga[R_DDR_RD_DATA];
			words_ready--;
			for (b=0; b<4; b++) {
				putchar(x & 0xff);
				crc ^= (x & 0xff);
				for (c=0; c<8; c++) {
					if (crc & 1) crc = (crc>>1) ^ CRC_POLY;
					else crc = crc>>1;
				}
				x = x >> 8;
			}
		}
		// Check CRC per row:
		if (words_ready == 0) {
			words_ready = fpga[R_DDR_COUNT];
			while (words_ready == 0) {
				usleep(1000);
				words_ready = fpga[R_DDR_COUNT];
			}
		}
		x = fpga[R_DDR_RD_DATA];
		words_ready--;
		assert ((0xcccc0000 | crc) == x);
		// 0xcccc is the magic upper word that indicates a CRC word.
	}

	fpga[R_WPU_CTRL] = 0;
	return 0;
}

