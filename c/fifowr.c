#include<unistd.h>
#include<sys/types.h>
#include<sys/mman.h>
#include<stdio.h>
#include<stdlib.h>
#include<fcntl.h>
#include<assert.h>
#include<stdint.h>

#include "fpga.h"

int main(int argc, char **argv) {
	int i, k;
	volatile uint32_t *fpga;
	int fd;

	assert(2 == argc);

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


