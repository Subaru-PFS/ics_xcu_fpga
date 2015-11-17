#include <stdlib.h>
#include<unistd.h>
#include<sys/types.h>
#include<sys/mman.h>
#include<stdio.h>
#include<fcntl.h>

#include "fpga.h"

unsigned int parseBinary(char *str) {
  unsigned int val = 0;
  
  if (*str == 'b') {
    str++;
    while (*str) {
      if (*str == '0') {
	val <<= 1;
      } else if (*str == '1') {
	val = (val << 1) + 1;
      } else {
	goto binaryError;
      }
    }
  }
  return val;
 binaryError:
  fprintf(stderr,"Unrecognized numeric value: %s\n",str);
  exit(0);
}

unsigned short parseNumber(char *str) {
  unsigned int addr = 0;

  if (!sscanf(str, "0x%x", &addr)) {
    if (!sscanf(str, "%u", &addr)) {
      addr = parseBinary(str);
    }
  }
  return (unsigned short)addr;
}

typedef union {
  volatile unsigned char *charPtr;
  volatile unsigned short *shortPtr;
  volatile unsigned int *intPtr;
} typedPtr;
  
/*
  Features that the old peekXX/pokeXX did not have:
  1. Support for 8/16/32 bit READ/WRITE in one function
  2. Support for decimal and binary values
  3. The value return is returned (to become the status code)
 */
int main(int argc, char **argv) {
  off_t offset;
  int bits,dowrite=0,doread=1;
  volatile uint32_t *start;
  unsigned int ret;
  unsigned int intval = 0;
  int width;
  typedPtr ptr;
  
  if (argc < 3 || argc > 5) {
    fprintf(stderr,"Usage: peekpoke BIT_WIDTH ADDRESS <VALUE <x>>\n");
    fprintf(stderr,"<x> can be anything; supresses read-back on write\n");
    return 0;
  }
  sscanf(argv[1], "%d", &bits);
  if (bits != 8 && bits != 16 && bits != 32) {
    fprintf(stderr,"Error: BIT_WIDTH must be 8, 16, or 32\n");
    return 0;
  }
  offset = parseNumber(argv[2]);
  if (argc > 3 ) { // peekpoke BITS ADDRESS VALUE x
    intval = parseNumber(argv[3]);
    if (argc > 4) doread = 0;
    dowrite = 1;
  }

  ret = configureFpga(PFS_FPGA_MMAP_FILE);
  if (!ret) exit(1);

  start = fpgaAddr();

  if (bits == 8) {
    unsigned char charval = (unsigned char)intval;
    volatile unsigned char *chardat = (volatile unsigned char *)start + offset;
    ptr.charPtr = (volatile unsigned char *)start + offset;
    width = 2;
    if (dowrite) {
      *chardat = charval;
    }
    if (doread) {
      intval = (unsigned int)*chardat;
    }
  } else if (bits == 16) {
    unsigned short shortval = (unsigned short)intval;
    volatile unsigned short *shortdat = (volatile unsigned short *)start + offset;
    ptr.shortPtr = (volatile unsigned short *)start + offset;

    width = 4;
    if (dowrite) {
      *shortdat = shortval;
    }
    if (doread) {
      intval = (unsigned int)*shortdat;
    }
  } else { // bits == 32
    volatile unsigned int *intdat = start + offset;
    ptr.intPtr = (volatile unsigned int *)start + offset;
    width = 8;
    if (dowrite) {
      *intdat = intval;
    }
    if (doread) {
      intval = *intdat;
    }
  }
  if (doread) {
    printf("0x%08x 0x%0*X\n", ptr.intPtr, width, intval);
  }
  return intval;
}
