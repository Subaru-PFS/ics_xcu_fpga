#include<unistd.h>
#include<sys/types.h>
#include<sys/mman.h>
#include<stdio.h>
#include<stdlib.h>
#include<fcntl.h>
#include<assert.h>
#include <time.h>
#include <sys/time.h>

#include "fpga.h"

volatile unsigned int *fpga;
volatile unsigned int dummy;

#define TEST_KS (35 * 1024)

int main(void) {
        struct timeval t0, t1, t2, td1, td2;
        
	assert(4 == sizeof(unsigned int));

        configureFpga(0);
        fpga = fpgaAddr();
        pciReset();
        
        gettimeofday(&t0, NULL);
        fifoWrite(TEST_KS);
        gettimeofday(&t1, NULL);
        fifoRead(TEST_KS);
        gettimeofday(&t2, NULL);

        timersub(&t1, &t0, &td1);
        timersub(&t2, &t1, &td2);

        fprintf(stdout, "write: %0.2f read: %0.2f\n",
                td1.tv_usec / 1.0e6 + td1.tv_sec,
                td2.tv_usec / 1.0e6 + td2.tv_sec);

	return 0;
}

