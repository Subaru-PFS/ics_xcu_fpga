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

int main(void) {
	int i, fd;

	assert(4 == sizeof(unsigned int));

        configureFpga(0);
        fpga = fpgaAddr();
        
	for (i=0; i<8000000; i++) {
		dummy = *fpga;
	}

	return 0;
}

