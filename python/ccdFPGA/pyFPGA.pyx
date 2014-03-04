import sys
import cython
import numpy
from cython cimport view
from libc.stdint cimport uint16_t, uint32_t
cimport numpy

cimport pyFPGA

numpy.import_array()

cdef extern from "fpga.h":
     int configureFpga(const char *mmapname)
     void configureForReadout(int doTest)
     void finishReadout()
     uint32_t readWord()
     int readRawLine(int npixels, uint32_t *rowbuf, int rownum)
     int readLine(int npixels, uint16_t *rowbuf, int rownum)
     int readImage(int nrows, int ncols, int namps, uint16_t *imageBuf)
     uint32_t peekWord(uint32_t addr)
     int fifoRead(int nBlocks)
     int fifoWrite(int nBlocks)
     

cdef class FPGA:
    def __cinit__(self):
        configureFpga(<const char *>0)

        cpdef readImage(self, int nrows=4240, int ncols=536, int namps=8, doTest=1):
            # a contiguous C array with all the numpy and cython geometry information.
            # Yes, magic -- look at the cython manual...
        cdef numpy.ndarray[numpy.uint16_t, ndim=2, mode="c"] image = numpy.zeros((nrows,ncols*namps), 
                                                                                 dtype='u2')

        configureForReadout(doTest)
        ret = readImage(nrows, ncols, namps, &image[0,0])
        finishReadout()

        return image

    cpdef readImageByRows(self, int nrows=4240, int ncols=536, int namps=8, doTest=1, rowFunc=None):
        # a contiguous C array with all the numpy and cython geometry information.
        # Yes, magic -- look at the cython manual...
        cdef numpy.ndarray[numpy.uint16_t, ndim=2, mode="c"] image = numpy.zeros((nrows,ncols*namps), 
                                                                                 dtype='u2')

        configureForReadout(doTest)
        for row in range(nrows):
            ret = readLine(ncols*namps, &image[row,0], row)
            
            if rowFunc:
                rowFunc(row, image)
            else:
                if row%100 == 0 or row == nrows-1:
                    sys.stderr.write("line %d (ret=%s)\n" % (row, ret))
        finishReadout()

        return image

    cpdef fifoTest(self, int nBlocks):
        sys.stderr.write("writing %d blocks\n" % (nBlocks))
        fifoWrite(nBlocks)
        sys.stderr.write("reading %d blocks\n" % (nBlocks))
        fifoRead(nBlocks)


