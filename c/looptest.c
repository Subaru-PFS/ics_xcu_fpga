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

volatile unsigned int *fpga;
volatile unsigned int dummy;
unsigned int bram_addr;
unsigned int output_states;

#define SET_1(x) output_states |= (x)
#define SET_0(x) output_states &= ~(x)

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
	unsigned int end_addr;

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

        fprintf(stderr, "configuring....\n");
                
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
        fprintf(stderr, "looping....\n");
	for (int i=0; i<PIX_H*PIX_W*4 + PIX_H; i++) {
	  int dummy;
          dummy = fpga[R_DDR_COUNT];
	}

	fpga[R_WPU_CTRL] = 0;
	return 0;
}

