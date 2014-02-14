#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>

#include "fpga.h"

int read_and_print_image()
{
  uint32_t *imageBuf;
  int ret;

  imageBuf = calloc(PIX_H * PIX_W * 4, sizeof(uint32_t));

  fprintf(stderr, "ID: 0x%08x\n", peekWord(R_ID));
  ret = readImage(PIX_H, PIX_W, imageBuf);
  fwrite(imageBuf, PIX_H*PIX_W*4, sizeof(uint32_t), stdout);

  return ret;
}

int main(void) 
{
  int ret;
  
  ret = configureFpga(PFS_FPGA_MMAP_FILE);
  if (!ret) exit(1);

  configureForReadout();
  ret = read_and_print_image();

  exit(ret);
}

