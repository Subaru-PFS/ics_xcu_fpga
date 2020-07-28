# cython: language_level=3

import sys
import time
import cython
import numpy
from importlib import reload

import clocks

from cython cimport view
from libc.stdint cimport uint16_t, uint32_t
cimport numpy

# cimport pyFPGA

numpy.import_array()

cdef extern from "fpga.h":
     ctypedef enum readoutStates:
        OFF = 0,
        IDLE = 1, 
        ARMED = 2, 
        READING = 3, 
        FAILED = 4, 
        UNKNOWN = 5
     readoutStates readoutState
     int configureFpga(const char *mmapname)
     void releaseFpga()
     void pciReset()

     int sendAllOpcodes(uint32_t *states, uint16_t *durations, int cnt)
     int sendOneOpcode(uint32_t states, uint16_t duration)

     int resetReadout(int force)
     int armReadout(int nrows, int doTest, int ard18bit)

     void finishReadout()
     int readLine(int npixels, uint16_t *rowbuf,
                  uint32_t *dataCrc, uint32_t *fpgaCrc,
                  uint32_t *dataRow, uint32_t *fpgaRow);

     uint32_t peekWord(uint32_t addr)
     void pokeWord(uint32_t addr, uint32_t data)
     int fifoRead(int nBlocks)
     int fifoWrite(int nBlocks)

logger = None
def printProgress(row_i, image, errorMsg="OK", everyNRows=100, 
                  **kwargs):
    """ A sample end-of-row callback. Prints all errors and per-100 row progess lines. """
    global logger
    
    if logger is None:
        import logging
        logger = logging.getLogger('FPGA')
        
    nrows, ncols = image.shape

    if row_i%everyNRows == 0 or row_i == nrows-1 or errorMsg is not "OK":
        logger.info("line %05d %s", row_i, errorMsg)
    
cdef class FPGA:
    cdef dict __dict__
    
    def __cinit__(self):
        configureFpga(<const char *>0)

    def __init__(self):
        """ Please use the CCD subclass instead of FPGA! """
        pass

    def __deallocate__(self):
        releaseFpga()
    
    def readoutState(self):
        return readoutState

    def reconnect(self):
        releaseFpga()
        pciReset()
        configureFpga(<const char *>0)

    def pciReset(self):
        """ Trigger the PCI reset line. As it stands, this stops all FPGA processing and resets all pointers.
        """

        pciReset()

    def resetReadout(self, force=False):
        return resetReadout(1 if force else 0)
        
    def configureReadout(self, nrows, ncols, doTest=False,
                         clockFunc=None, rowBinning=1):

        """ Configure the detector for a readout.

        Returns:
           Expected readout time (s).
        """
        
        if clockFunc is None:
            raise RuntimeError("Must specify clocking")
        if not self.resetReadout(0):
            raise RuntimeError("failed to reset for readout")

        ticks, opcodes, readTime = clocks.genRowClocks(ncols, clockFunc, rowBinning=rowBinning)
        for i in range(len(ticks)):
            ret = sendOneOpcode(opcodes[i], ticks[i])
            if not ret:
                raise RuntimeError("failed to send opcode %d" % (i))

        if not armReadout(nrows, doTest, self.adc18bit):
            raise RuntimeError("failed to arm for readout)")

        return readTime * nrows

    def finishReadout(self):
        return finishReadout()
        
    def armReadout(self, int nrows, doTest=False, adcMode=1):
        return armReadout(nrows, doTest, adcMode)
    
    def sendOneOpcode(self, int opcode, int ticks):
        return sendOneOpcode(opcode, ticks)
        
    cpdef _readImage(self, int nrows=-1, int ncols=-1,  
                     doTest=False, debugLevel=1, 
                     doAmpMap=True, 
                     rowFunc=None, rowFuncArgs=None):
    
        """ Read out the detector. Does _not_ (re-)configure the FPGA.

        Parameters
        ----------
        nrows : int, optional
           The number of rows in the image. Default=4240
        ncols : int, optional
           The number of columns in the image. Note that this is per amp. Default=536
        doTest : bool, optional
           If set True, return an FPGA-generated synthetic image.
        doAmpMap : bool, optional
           If set False, do not remap the pixels from FPGA readout order to detector order
        rowFuncArgs : dict, optional
           If set and rowFunc is to be called, these are added to the rowFunc keyword arguments
        rowFunc : callable, optional
           If set, a function called at the end of each line. The signature is:
              rowFunc(rowNum, image, error=None, dataCrc=int, fpgaCrc=int, **rowFuncArgs)
           where rawNum is the 0-based index of the just-read row, image, is the full image, and error
           contains any error string from the row's readout.
           Pass False to call no per-row routine.
           Pass None (the default) to print errors and per-100 row happy-lines.

        Returns
        -------
        image
            An unsigned 16-bit pixels image of nrows, (ncols*namps) pixels.
        
        Examples
        --------

        >>> fpga = FPGA()
          or (better):
        >>> fpga = CCD() 
        >>> simImage = fpga.readImageByRows()
        >>> shortRealImage = fpga.readImageByRows(nrows=100, doTest=0)

        >>> def myRowFunc(rowNum, image, **kwargs):
                print "row %04d mean=%0.2f" % (rowNum, image[rowNum].mean())
        >>> im = fpga.readImage(nrows=100, rowFunc=myRowFunc)


        """

        if nrows == -1:
            nrows = self.nrows
        if ncols == -1:
            ncols = self.ncols
            
        # a contiguous C array with all the numpy and cython geometry information.
        # Yes, magic -- look at the cython manual...
        cdef int namps = self.namps
        cdef numpy.ndarray[numpy.uint16_t, ndim=2, mode="c"] image = numpy.zeros((nrows,ncols*namps), 
                                                                                 dtype='u2') + 0xdead
        cdef numpy.ndarray[numpy.uint16_t, ndim=1, mode="c"] rowImage = numpy.zeros((ncols*namps), 
                                                                                    dtype='u2') + 0xdead
        cdef uint32_t dataCrc, fpgaCrc
        cdef uint32_t dataRow, fpgaRow
        cdef int row_i, col_i, amp_i
        
        if rowFunc is None:
            rowFunc = printProgress
        if rowFunc and rowFuncArgs is None:
            rowFuncArgs = dict()

        for row_i in range(nrows):
            if debugLevel > 4:
                t0 = time.time()
            ret = readLine(ncols*namps, &rowImage[0], 
                           &dataCrc, &fpgaCrc,
                           &dataRow, &fpgaRow)
            if debugLevel > 4:
                t1 = time.time()
                sys.stderr.write('line %04d: %g\n' %  (row_i, t1-t0))
                                 
            if dataCrc != fpgaCrc:
                errorMsg = ("CRC mismatch: FPGA: 0x%08x calculated: 0x%08x. FPGA CRC MUST start with 0xccc0000\n" %
                            (fpgaCrc, dataCrc))
                sys.stderr.write("row %d %s\n" % (row_i+1, errorMsg))
            elif ret != 0:
                errorMsg = ("CRCs FPGA: 0x%08x calculated: 0x%08x." % (fpgaCrc, dataCrc))
            else:
                errorMsg = "OK?"
            
            if doAmpMap:
                for amp_i in range(namps):
                    for col_i in range(ncols):
                        image[row_i,amp_i*ncols + col_i] = rowImage[col_i*namps + amp_i]
            else:
                image[row_i,:] = rowImage

            if self.adc18bit > 1 and self.doCorrectSignBit:
                image[row_i, :] ^= 0x8000

            if rowFunc:
                rowFunc(row_i, image, error=errorMsg, 
                        fpgaCrc=fpgaCrc, dataCrc=dataCrc,
                        fpgaRow=fpgaRow, dataRow=dataRow,
                        **rowFuncArgs)

        finishReadout()

        return image

    cpdef peekWord(self, uint32_t addr):
        """ Read a 32-bit word from the PCI BRAM space.

        Parameters
        ----------
        addr : int
           The 0-index BAR0 address to read a 32-bit word from. [0..4095]

        Returns
        -------
        data
           the 32-bit value 
        
        """

        cdef uint32_t data

        if addr >= 4096:
            raise IndexError("addr (%d) must with the 4kB PCI BAR0 page" % (addr))

        data = peekWord(addr)
        return data

    cpdef pokeWord(self, uint32_t addr, uint32_t data):
        """ Read a 32-bit word from the PCI BRAM space.

        Parameters
        ----------
        addr : int
           The 0-index BAR0 address to write to. [0..4095]
        data : int
           The 32-bit data to write

        """

        if addr >= 4096:
            raise IndexError("addr (%d) must with the 4kB PCI BAR0 page" % (addr))

        pokeWord(addr, data)

    cpdef fifoTest(self, int nBlocks):
        """ Test the FPGA buffering, without a readout.

        There should be no significant output.

        Parameters
        ----------
        nBlocks : int
            The number of 1k blocks to write then read.

        
        """

        sys.stderr.write("writing %d blocks\n" % (nBlocks))
        fifoWrite(nBlocks)
        sys.stderr.write("reading %d blocks\n" % (nBlocks))
        fifoRead(nBlocks)


