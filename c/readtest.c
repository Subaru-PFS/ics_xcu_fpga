#include<unistd.h>
#include<sys/types.h>
#include<sys/mman.h>
#include<stdio.h>
#include<stdlib.h>
#include<fcntl.h>
#include<assert.h>

#define FPGABASE 0xfe9ff000 // XXX change as needed

volatile unsigned int *fpga;
volatile unsigned int dummy;

int main(void) {
	int i, fd;

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

	for (i=0; i<8000000; i++) {
		dummy = *fpga;
	}

	return 0;
}

