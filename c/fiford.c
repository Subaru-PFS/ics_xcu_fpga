#include<unistd.h>
#include<sys/types.h>
#include<sys/mman.h>
#include<stdio.h>
#include<stdlib.h>
#include<fcntl.h>
#include<assert.h>

#include "fpga.h"

int main(int argc, char **argv) {
	int i, k;
	volatile unsigned int *fpga;
	int fd;
	unsigned int x, y;

	assert(2 == argc);

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

	k = strtoul(argv[1], 0, 0);
	fprintf(stderr, "kbytes=%d\n", k);

	y=0xffffffff;
	for(i=0; i<k*1024/4; i++) {
		x = fpga[R_DDR_RD_DATA];
		if (y+1 != x) fprintf(stderr, "%x followed %x\n", x, y);
		y=x;
		/*
		putchar(x & 0xff);
		x >>= 8;
		putchar(x & 0xff);
		x >>= 8;
		putchar(x & 0xff);
		x >>= 8;
		putchar(x & 0xff);
		*/
	}
	return 0;
}


