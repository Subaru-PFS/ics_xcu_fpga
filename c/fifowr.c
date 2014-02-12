#include<unistd.h>
#include<sys/types.h>
#include<sys/mman.h>
#include<stdio.h>
#include<stdlib.h>
#include<fcntl.h>
#include<assert.h>

#define FPGABASE 0xfe9ff000

/* VHDL register definitions:
	constant	R_DDR_RD_DATA	: natural := 16#0050#/4;
	constant	R_DDR_WR_DATA	: natural := 16#0054#/4;
*/
#define R_DDR_RD_DATA	(0x50/4)
#define R_DDR_WR_DATA	(0x54/4)

int main(int argc, char **argv) {
	int i, k;
	volatile unsigned int *fpga;
	int fd;
	//unsigned int x;

	assert(2 == argc);

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

	k = strtoul(argv[1], 0, 0);
	fprintf(stderr, "kbytes=%d\n", k);

	for(i=0; i<k*1024/4; i++) {
		/*
		x = getchar();
		x |= getchar() << 8;
		x |= getchar() << 16;
		x |= getchar() << 24;
		*/
		fpga[R_DDR_WR_DATA] = i;
		//if (!(i & 0xff)) usleep(100);
	}
	return 0;
}


