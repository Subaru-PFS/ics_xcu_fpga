#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>

#include "fpga.h"

int read_and_print_image(int nrows, int ncols)
{
  int npixels = nrows * ncols * N_AMPS;
  uint16_t *imageBuf;
  int ret;
  
  configureForReadout(1, 0, nrows, ncols);

  imageBuf = calloc(npixels, sizeof(uint16_t));

  fprintf(stderr, "ID: 0x%08x\n", peekWord(R_ID));
  ret = readImage(nrows, ncols, N_AMPS, imageBuf);
  fwrite(imageBuf, npixels, sizeof(uint16_t), stdout);

  return ret;
}

int main(void) 
{
  int ret;
  
  ret = configureFpga(PFS_FPGA_MMAP_FILE);
  if (!ret) exit(1);

  ret = read_and_print_image(PIX_H, PIX_W);

  exit(ret);
}

