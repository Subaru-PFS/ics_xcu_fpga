/* 
   This is a library of the FPGA readout routines.
*/

#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <assert.h>
#include <time.h>
#include <errno.h>
#include <stdint.h>
#include <string.h>

#include "fpga.h"

readoutStates readoutState = OFF;

static volatile uint32_t *fpga;
static uint32_t bram_addr;
static int wordsReady;

#define STATES_MASK 0xffff8000
#define DURATION_MASK (0xffffffff & ~STATES_MASK)

// sendOneOpcode(states, d) causes the given states to be driven on the outputs for d*40ns
//
int sendOneOpcode(uint32_t states, uint16_t duration)
{
  if (states & DURATION_MASK) {
      fprintf(stderr, "invalid states (0x%08x). duration=0x%08x!!\n",
              states, duration);
      return 0;
  }

  if (duration & STATES_MASK) {
      fprintf(stderr, "invalid duration (0x%08x). states=0x%08x!!\n",
              duration, states);
      return 0;
  }
      
  fpga[R_BR_ADDR] = bram_addr;
  fpga[R_BR_WR_DATA] = states | duration;
  bram_addr += 4;

  return 1;
}

// sendAllOpcodes(states, durations, cnt) causes the given states to be driven on the outputs for d*40ns
//
int sendAllOpcodes(uint32_t *states, uint16_t *durations, int cnt)
{
  bram_addr = 0;
  for (int i=0; i<cnt; i++) {
    if (!sendOneOpcode(states[i], durations[i])) {
      // I do wish I could raise an exception here!
      fprintf(stderr, "invalid opcode %d. Aborting download!\n",
              i);
      readoutState = UNKNOWN;
      return 0;
    }
  }

  return 1;
}

int configureFpga(const char *mmapname)
{
  const char *mapfile;
  static int fd;

  readoutState = UNKNOWN;

  if (fpga) {
    releaseFpga();
  }

  mapfile = mmapname ? mmapname : PFS_FPGA_MMAP_FILE;
  fd = open(mapfile, O_RDWR|O_SYNC);
  if (fd == -1) {
    perror("open(/dev/mem):");
    return 0;
  }
  fpga = mmap(0, sysconf(_SC_PAGESIZE), PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
  if (fpga == MAP_FAILED) {
    perror("mmap:");
    return 0;
  }

  readoutState = IDLE;
  fprintf(stderr, "Configured ID: 0x%08x\n", peekWord(R_ID));
  return 1;
}

void releaseFpga(void)
{
  readoutState = FAILED;

  fprintf(stderr, "closing and re-opening FPGA mmap\n");
  munmap((void *)fpga, sysconf(_SC_PAGESIZE));
  fpga = 0;

  readoutState = OFF;
}

int requireFpga(void)
{
  if (!fpga) {
    fprintf(stderr, "FPGA has not yet been configured!");
    return 0;
  }
  return 1;
}

int resetReadout(int force)
{
  if (!requireFpga()) 
    return 0;

  if (readoutState != IDLE) {
    if (!force) {
      fprintf(stderr, "readoutState=%d, but need it to be %d to configure readout", readoutState, IDLE);
      return 0;
    } else {
      fprintf(stderr, "readoutState=%d, forcing it to IDLE", readoutState);
      readoutState = IDLE;
    }
  }
    
  bram_addr = 0;

  // Reset WPU and FIFO, disable synch clock
  fpga[R_WPU_CTRL] = WPU_RST | FIFO_RD_RST | FIFO_WR_RST;
  usleep(100); // FIFO reset signals need about 50us to work.
  
  return 1;
}

int armReadout(int nrows, int doTest, int adc18bit)
{
  uint32_t end_addr = bram_addr-4;

  if (!requireFpga()) 
    return 0;

  if (readoutState != IDLE) {
    fprintf(stderr, "readoutState=%d, but need it to be %d to arm readout", readoutState, IDLE);
    return 0;
  }

  // Set parameters
  // START_STOP register wants D-word addresses.
  fpga[R_WPU_START_STOP] = (end_addr/4) << 16;
  fpga[R_WPU_COUNT] = nrows; // FPGA wants N-1 for N loops.
  // At this point the master must get acknowledgement that
  // all units are ready via network communications.
  // Start and stop synch clock
  fpga[R_WPU_CTRL] = WPU_RST | EN_SYNCH;
  fpga[R_WPU_CTRL] = WPU_RST;
  // Release WPU reset
  fpga[R_WPU_CTRL] = 0;
  // At this point the master must again get acknowledgement that
  // all units are ready.
  // Start clock
  fpga[R_WPU_CTRL] = EN_SYNCH |
    (doTest ? WPU_TEST : 0) | // Optionally enable test pattern
    (adc18bit ? WPU_18BIT : 0) | // Optionally configure for 18 bit ADC
    ((adc18bit > 1) ? WPU_18LOWBITS : 0); // Optionally configure for low-bits of 18 bit ADC
  readoutState = ARMED;

  // Not sure about how necessary this is. -- CPL
  usleep(5000);

  return 1;
}

void finishReadout(void)
{
  // Need tons of sanity checks.
  fpga[R_WPU_CTRL] = 0;
  readoutState = IDLE;
}

#if 0
static
void usleep(long usecs)
{
  struct timespec req, rem;
  int ret;

  rem.tv_sec = req / 1000000;
  rem.tv_usec = req % 1000000;

  do {
    req = rem;
    ret = nanosleep(req, rem);
  } while (ret == -1 && errno == EINTR);
}
#endif

uint32_t readWord(void)
{
  uint32_t word;
  int i;

  if (wordsReady == 0) {
    wordsReady = fpga[R_DDR_COUNT];
    while (wordsReady == 0) {
      usleep(1000);
      wordsReady = fpga[R_DDR_COUNT];
      fprintf(stderr, "slept on line (avail=%d)\n", wordsReady);
      /* If fpga[R_DDR_COUNT] stays at zero for 50ms, we can infer
       * that the deserializer is done feeding it and we need to
       * feed some words into it in order to cause those that are
       * stuck in the FIFO to feed through.
       */
      if ((wordsReady == 0) && (fpga[R_WPU_STATUS] == 0)) {
        for (i=0; i<256; i++)
          fpga[R_DDR_WR_DATA] = 0xbeef;
      }
    }
  }
  word = fpga[R_DDR_RD_DATA];
  wordsReady -= 1;

  return word;
}

/* readRawLine -- read a single line of raw FPGA words. */
int readRawLine(int nwords, uint32_t *rowbuf, 
                uint32_t *dataCrc, uint32_t *fpgaCrc, 
                uint32_t *dataRow, uint32_t *fpgaRow)
{
  uint32_t word, crc;

  crc = 0;
  
  for (int j=0; j<nwords; j++) {
    word = readWord();
    rowbuf[j] = word;

    for (short b=0; b<4; b++) {
      crc ^= (word & 0xff);
      for (short c=0; c<8; c++) {
        if (crc & 1) crc = (crc>>1) ^ CRC_POLY;
        else crc = crc>>1;
      }
      word = word >> 8;
    }
  }
  // Check CRC per row:
  // 0xcccc is the magic upper word that indicates a CRC word. We add that
  // in instead of masking it off of the FPGA CRC so that we can keep the full
  // 32-bits of the perhaps trashed FPGA value.
  *fpgaRow = readWord();
  *dataRow |= 0x00050000;
  *fpgaCrc = readWord();
  *dataCrc = crc << 16 | 0x000a;

  return (*dataCrc != *fpgaCrc) || (*dataRow != *fpgaRow);
}

/* readLine -- read a single line of _pixels_. */
int readLine(int npixels, uint16_t *rowbuf,
	     uint32_t *dataCrc, uint32_t *fpgaCrc,
	     uint32_t *dataRow, uint32_t *fpgaRow)
{
  int nwords, ret;

  if (!requireFpga()) 
    return 0;
#if 0 // #iffing this out because maybe we have more states now that we allow re-read.
  if (readoutState != ARMED) {
    fprintf(stderr, "FPGA must be armed for readout! (readoutState=%d)", readoutState);
    return 0;
  }
#endif

  // Round up, so that we can read odd-width rows.
  // It may be safe to assume namps is always even so npixels is always even. -- GP
  nwords = (npixels * sizeof(uint16_t) + sizeof(uint16_t)/2)/sizeof(uint32_t);

  readoutState = READING;
  ret = readRawLine(nwords, (uint32_t *)rowbuf, dataCrc, fpgaCrc, dataRow, fpgaRow);
  readoutState = ARMED;

  return ret;
}

int readImage(int nrows, int ncols, int namps, uint16_t *imageBuf)
{
  int badRows = 0;
  int rowPixels = ncols*namps;
  uint32_t dataCrc, fpgaCrc, dataRow, fpgaRow;

  fpga[R_WPU_CTRL] |= FIFO_RD_RST;
  usleep(100); // FIFO reset signals need about 50us to work.
  fpga[R_WPU_CTRL] &= ~FIFO_RD_RST;

  fprintf(stderr, "Reading ID: 0x%08x (%d,%d*%d=%d,0x%08lx)\n", 
	  peekWord(R_ID), 
	  nrows, ncols, namps, rowPixels, (unsigned long)imageBuf);

  for (int i=0; i<nrows; i++) {
    int lineBad;
    uint16_t *rowBuf = imageBuf + i*rowPixels;
    dataRow = i;
    
    lineBad = readLine(rowPixels, rowBuf, &dataCrc, &fpgaCrc, &dataRow, &fpgaRow);
    if (lineBad) {
      badRows++;

      fprintf(stderr, 
	      "Bad metadata on row %d. Expected: 0x%08x 0x%08x Received: 0x%08x 0x%08x\n",
	      i, dataRow, dataCrc, fpgaRow, fpgaCrc);
    }
  }

  finishReadout();
  return badRows;
}

volatile uint32_t *fpgaAddr(void)
{
  return fpga;
}

uint32_t peekWord(uint32_t addr)
{
  uint32_t intdat = (fpga[addr]);

  return intdat;
}

void pokeWord(uint32_t addr, uint32_t data)
{
  fpga[addr] = data;
  // Set readoutState = UNKNOWN?
}

/* Try to send the PCI reset signal. */
void pciReset(void)
{
  int f, ret;

  f = open(PFS_FPGA_RESET_FILE, O_WRONLY);
  if (f < 0) {
    fprintf(stderr, "cannot open FPGA reset file %s (%s)\n", PFS_FPGA_RESET_FILE, strerror(errno));
    return;
  }
  ret = write(f, "1", 1);
  if (ret < 0) {
    fprintf(stderr, "cannot write to FPGA reset file %s (%s)\n", PFS_FPGA_RESET_FILE, strerror(errno));
    return;
  }
  close(f);
  
  readoutState = IDLE;
}


int fifoRead(int nBlocks)
{
  int errCnt = 0;
  uint32_t y;

  readoutState = UNKNOWN;

  y = 0xffffffff;
  for (uint32_t i=0; i<nBlocks*1024/sizeof(uint32_t); i++) {
    uint32_t x = fpga[R_DDR_RD_DATA];
    if (y+1 != x) {
      errCnt += 1;
      fprintf(stderr, "at %0x08x; 0x%04x followed 0x%04x\n", i, x, y);
    } else {
      errCnt = 0;
    }

    y = x;

    if (errCnt > 100) {
      fprintf(stderr, "giving up after 100 consecutive errors\n");
      return errCnt;
    }
  }

  return errCnt;
}

void fifoWrite(int nBlocks)
{
  readoutState = UNKNOWN;

  for (uint32_t i=0; i<nBlocks*1024/sizeof(uint32_t); i++) {
    fpga[R_DDR_WR_DATA] = i;
  }
}
