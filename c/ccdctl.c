// CCD waveform output tool
#include<unistd.h>
#include<sys/types.h>
#include<sys/mman.h>
#include<stdio.h>
#include<stdlib.h>
#include<fcntl.h>
#include<assert.h>

#define FPGABASE 0xfe9ff000
#define CRC_POLY 0xa001

/* VHDL register definitions:
	constant	R_DDR_RD_DATA	: natural := 16#0050#/4;
	constant	R_DDR_WR_DATA	: natural := 16#0054#/4;
	constant	R_DDR_ADDR	: natural := 16#0058#/4;
	constant	R_BR_RD_DATA	: natural := 16#0010#/4;
	constant	R_BR_WR_DATA	: natural := 16#0014#/4;
	constant	R_BR_ADDR	: natural := 16#0018#/4;
	constant	R_WPU_CTRL	: natural := 16#0020#/4;
	constant	R_WPU_COUNT	: natural := 16#0024#/4;
	constant	R_WPU_LEN	: natural := 16#0028#/4;
	constant	R_WPU_STATUS	: natural := 16#002C#/4;
	constant	R_IMAGE_ADR	: natural := 16#0030#/4;
	constant	R_CRC   	: natural := 16#0034#/4;
*/
#define R_DDR_RD_DATA	(0x50/4)
#define R_DDR_WR_DATA	(0x54/4)
#define R_DDR_ADDR	(0x58/4)
#define	R_BR_RD_DATA	(0x10/4)
#define	R_BR_WR_DATA	(0x14/4)
#define	R_BR_ADDR	(0x18/4)
#define	R_WPU_CTRL	(0x20/4)
#define	R_WPU_COUNT	(0x24/4)
#define	R_WPU_LEN	(0x28/4)
#define	R_WPU_STATUS	(0x2C/4)
#define	R_IMAGE_ADR	(0x30/4)
#define	R_CRC   	(0x34/4)

// Control register bits:
#define EN_SYNCH	(1<<0)
#define WPU_RST		(1<<1)
#define ADR_RST		(1<<2)

int main(int argc, char **argv) {
	volatile unsigned int *fpga;
	int fd;
	unsigned int i, j, x, length, reps, bytes_read;
	unsigned short crc = 0;
	volatile unsigned int dummy;

	if (argc != 3) {
		fprintf(stderr, "\nUsage: ccdctl <length> <reps> < wave.bin > row.bin\n\n");
		return -1;
	}

	assert(4 == sizeof(unsigned int));
	fd = open("/dev/mem", O_RDWR|O_SYNC);
	if (fd == -1) {
		perror("open(/dev/mem):");
		return 0;
	}
	fpga = mmap(0, getpagesize(), PROT_READ|PROT_WRITE, MAP_SHARED, fd, FPGABASE);
	if (fpga == MAP_FAILED) {
		perror("mmap:");
		return 0;
	}

	length = strtoul(argv[1], 0, 0);
	fprintf(stderr, "length=%d\n", length);
	reps = strtoul(argv[2], 0, 0);
	fprintf(stderr, "reps=%d\n", reps);

	// Reset WPU, disable synch clock
	fpga[R_WPU_CTRL] = WPU_RST | ADR_RST;

	// Load waveform into blockram
	for (i=0; i<length; i++) {
		fpga[R_BR_ADDR] = 4*i;
		x = getchar();
		x |= getchar() << 8;
		x |= getchar() << 16;
		x |= getchar() << 24;
		fpga[R_BR_WR_DATA] = x;
	}

	// Set parameters
	fpga[R_WPU_LEN] = length - 1; // FPGA needs (length - 1)
	fpga[R_WPU_COUNT] = reps;
	// Start and stop synch clock
	fpga[R_WPU_CTRL] = WPU_RST | ADR_RST | EN_SYNCH;
	fpga[R_WPU_CTRL] = WPU_RST | ADR_RST;
	// Release WPU reset
	fpga[R_WPU_CTRL] = 0;
	// Start clock
	fpga[R_WPU_CTRL] = EN_SYNCH;
	// Read data and calculate CRC
	bytes_read = 0;
	// This while loop would be dangerous because the two FPGA registers are
	// not updated at the same time.  We know we get reps*16 bytes.
	// while ((fpga[R_WPU_STATUS] != 0) || (bytes_read != fpga[R_IMAGE_ADR])){
	while (reps * 16 != bytes_read){
		if (bytes_read == fpga[R_IMAGE_ADR]) usleep(5000);
		else {
			fpga[R_DDR_ADDR] = bytes_read;
			dummy = fpga[R_DDR_ADDR]; // Dummy read to waste time
			x = fpga[R_DDR_RD_DATA];
			for (i=0; i<4; i++) {
				putchar(x & 0xff);
				crc ^= (x & 0xff);
				for (j=0; j<8; j++) {
					if (crc & 1) crc = (crc >> 1) ^ CRC_POLY;
					else crc = crc >> 1;
					//fprintf(stderr, "crc=0x%x\n", crc);
				}
				x = x >> 8;
			}
			bytes_read += 4;
		}
	}
	// Verify CRC
	fprintf(stderr, "software_crc=0x%x\n", crc);
	fprintf(stderr, "hardware_crc=0x%x\n", fpga[R_CRC]);
	return 0;
}

