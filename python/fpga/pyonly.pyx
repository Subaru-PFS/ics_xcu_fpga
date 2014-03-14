import mmap
import numpy
import struct
import sys
import time

CCD_CRC  = (1 << 15)  # CRC Control
CCD_P1   = (1 << 16)  # Parallel 1
CCD_P2   = (1 << 17)  # Parallel 2
CCD_P3   = (1 << 18)  # Parallel 3
CCD_TG   = (1 << 19)  # Transfer Gate
CCD_S1   = (1 << 20)  # Serial 1
CCD_S2   = (1 << 21)  # Serial 2
CCD_RG   = (1 << 22)  # Reset Gate
CCD_SW   = (1 << 23)  # Summing Well
CCD_DCR  = (1 << 24)  # DC Restore
CCD_IR   = (1 << 25)  # Integrate Reset
CCD_I_M  = (1 << 26)  # Integrate Minus
CCD_I_P  = (1 << 27)  # Integrate Plus
CCD_CNV  = (1 << 28)  # ADC Convert
CCD_SCK  = (1 << 29)  # ADC SCK Burst
CCD_DG   = (1 << 30)  # Draig Gate
CCD_IRQ  = (1 << 31)  # Interrupt

R_DDR_RD_DATA	 =	(0x50/4)
R_DDR_COUNT	 =	(0x58/4)
R_BR_WR_DATA	 =	(0x14/4)
R_BR_ADDR	 =	(0x18/4)
R_WPU_CTRL	 =	(0x20/4)
R_WPU_COUNT	 =	(0x24/4)
R_WPU_START_STOP =	(0x28/4)
R_WPU_STATUS	 =	(0x2C/4)

# Control register bits:
EN_SYNCH =	(1<<0)
WPU_RST	 =	(1<<1)
WPU_TEST =	(1<<2)

CRC_POLY = 0xa001

cpdef class ClockTable(object):
    def __init__(self, fpgaMem, baseAddr=0):
        self.opcode = 0
        self.fpgaMem = fpgaMem
        self.baseAddr = baseAddr
        self.addr = baseAddr
        self.table = []

    def tick(self, nClocks, enabled, disabled):
        for c in enabled:
            self.opcode |= c
        for c in disabled:
            self.opcode &= ~c

        clocks = self.opcode | nClocks
        self.table.append((nClocks, clocks))
        self.fpgaMem[R_BR_ADDR] = self.addr
        self.fpgaMem[R_BR_WR_DATA] = clocks
        self.addr += 4

    @property
    def endAddr(self):
        return self.addr - 4

cpdef class BEE(object):
    mmapPath = "/sys/bus/pci/devices/0000:03:00.0/resource0"

    def __init__(self, nRows=4240, nCols=536):
        #self.mapFile = open(self.mmapPath, "r+b")
        #self.fpgaMem = mmap.mmap(self.mapFile.fileno(), 0)
        self.fpgaMem = numpy.memmap(self.mmapPath, dtype='u4')
        self.nRows = nRows
        self.nCols = nCols
        self.nPixels = self.nCols * 4

    def peek(self, offset, fmt="0x%08x"):
        nWords = 1
        data = self.fpgaMem[offset]
        chars = data.tostring()

        print("0x%08x(%04d) %r" % (offset, nWords, data))
        print("0x%08x(%04d) %s" % (offset, nWords, (fmt%data)))
        print("0x%08x(%04d) %s" % (offset, nWords, chars))

    def downloadRowClocks(self):
        """ write_row_readout() is a routine to write blockram with opcodes that read
            a row of CCD pixels.
        """

        clocks = ClockTable(self.fpgaMem)
        self.rowClocks = clocks

	# initial states:
	# arbitrary 4000ns -- initial states should already be present
        clocks.tick(100,
                    (CCD_CNV, CCD_DG, CCD_P2, CCD_RG, CCD_S1, CCD_SW, CCD_TG),
                    (CCD_CRC, CCD_DCR, CCD_IR, CCD_IRQ, CCD_I_M, CCD_I_P, CCD_P1, CCD_P3, CCD_S2, CCD_SCK))


        for i in range(self.nCols):
		# Each loop iteration here does 1 serial pixel
                clocks.tick(16,
                            (CCD_S2, CCD_DCR, CCD_IR, CCD_SCK),
                            (CCD_S1, CCD_RG))

                clocks.tick(8,
                            (CCD_RG,),
                            (CCD_SCK,))

                clocks.tick(8,
                            (CCD_S1,),
                            (CCD_S2, CCD_SW, CCD_IR, CCD_CNV))

                clocks.tick(8,
                            (),
                            (CCD_DCR,))

                clocks.tick(120,
                            (CCD_I_M,),
                            ())

                clocks.tick(8,
                            (CCD_SW,),
                            (CCD_I_M,))

                clocks.tick(120,
                            (CCD_I_P,),
                            ())

                clocks.tick(4,
                            (),
                            (CCD_I_P,))

                clocks.tick(44,
                            (CCD_CNV,),
                            ())

	# parallel clocking:
        clocks.tick(1000, 
                    (CCD_P1, CCD_DCR),
                    (CCD_RG,))

        clocks.tick(1000, 
                    (CCD_CRC,),
                    (CCD_P2, CCD_TG,))

        clocks.tick(1000, 
                    (CCD_P3,),
                    (CCD_CRC,))

        clocks.tick(1000, 
                    (),
                    (CCD_P1,))

        clocks.tick(1000, 
                    (CCD_P2, CCD_TG),
                    ())

        clocks.tick(1000, 
                    (CCD_P1,),
                    ())

        clocks.tick(50, 
                    (CCD_RG,),
                    ())

        clocks.tick(2,
                    (),
                    (CCD_DCR,))

	# START_STOP register wants D-word addresses.
	self.fpgaMem[R_WPU_START_STOP] = (clocks.endAddr/4) << 16
	self.fpgaMem[R_WPU_COUNT] = self.nRows #  wants N-1 for N loops.

    def configure(self):
        sys.stderr.write("configuring....\n")

	# Reset WPU, disable synch clock
	self.fpgaMem[R_WPU_CTRL] = WPU_RST

	# Load waveform into blockram
        self.downloadRowClocks()

	# At this point the master must get acknowledgement that
	# all units are ready via network communications.
	# Start and stop synch clock
	self.fpgaMem[R_WPU_CTRL] = WPU_RST | EN_SYNCH
	self.fpgaMem[R_WPU_CTRL] = WPU_RST
	# Release WPU reset
	self.fpgaMem[R_WPU_CTRL] = 0
	# At this point the master must again get acknowledgement that
	# all units are ready.

	# Start clock
	self.fpgaMem[R_WPU_CTRL] = EN_SYNCH | WPU_TEST # Enable test pattern

    def addToRowCrc(self, crc, x):
        for b in range(4):
            crc ^= (x & 0xff)
            for c in range(8):
                if crc & 1:
                    crc = (crc>>1) ^ CRC_POLY
                else:
                    crc = crc>>1
            x = x >> 8

        return crc

    def readWord(self, sleepTime=0.001):
        if self.wordsReady == 0:
            self.wordsReady = self.fpgaMem[R_DDR_COUNT]
            sys.stderr.write('set to %d\n' % (self.wordsReady))
            while self.wordsReady == 0:
                time.sleep(sleepTime)
                self.wordsReady = self.fpgaMem[R_DDR_COUNT]
                sys.stderr.write('slept to %d' % (self.wordsReady))
            
        x = self.fpgaMem[R_DDR_RD_DATA]
        self.wordsReady -= 1
        return x
        
    def loopTest(self, nloops=None):
        self.configure()
        if not nloops:
            nloops = self.nRows * self.nPixels
        sys.stderr.write("looping....\n")
        for i in range(nloops):
            x = self.fpgaMem[R_DDR_RD_DATA]
        sys.stderr.write("done....\n")
            
    def readout(self):
        self.imageBuf = numpy.zeros((self.nRows, self.nPixels), dtype='u2')
        rowbuf = numpy.zeros(self.nPixels, dtype='u4')

        self.configure()

	# Just to clarify the four layers of looping that follows:
	# i increments for each row
	# j increments for each D-word of data
	# b increments for each byte
	# c increments for each bit (to compute CRC)
	self.wordsReady = 0
        sys.stderr.write("looping....\n")

        for i in range(self.nRows):
            rowCrc = 0
            for j in range(self.nPixels):
                pixel = self.readWord()
                rowbuf[j] = pixel
                #rowCrc = self.addToRowCrc(rowCrc, pixel)

            # Check CRC per row:
            crcCheck = self.readWord()

            # 0xcccc is the magic upper word that indicates a CRC word.
            if False and (0xcccc0000 | rowCrc) != crcCheck:
                sys.stderr.write('CRC mismatch on row %d (0x%08x vs 0x%08x)!!\n' % 
                                 (i, rowCrc, crcCheck))
            # sys.stdout.write(rowbuf)
            if i%1 == 0 or i == self.nRows-1:
                sys.stderr.write("end line %d (wordsReady=%d)\n" % (i, self.wordsReady))

	self.fpgaMem[R_WPU_CTRL] = 0
	return 0
