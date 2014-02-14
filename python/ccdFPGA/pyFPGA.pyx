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
     void configureForReadout()
     void finishReadout()
     uint32_t readWord()
     int readLine(int npixels, uint16_t *rowbuf, int rownum)
     int readImage(int nrows, int ncols, uint32_t *imageBuf)
     int fifoRead(int nBlocks)
     int fifoWrite(int nBlocks)
     

cdef class FPGA:
    def __cinit__(self):
        configureFpga(<const char *>0)

    cpdef readImage(self, int nrows=4240, int ncols=536):
        # a contiguous C array with all the numpy and cython geometry information.
        # Yes, magic -- look at the cython manual...
        cdef numpy.ndarray[numpy.uint32_t, ndim=2, mode="c"] image = numpy.zeros((nrows,ncols*4), 
                                                                                 dtype='u4')

        configureForReadout()
        ret = readImage(nrows, ncols, &image[0,0])
        finishReadout()

        return image

    cpdef fifoTest(self, int nBlocks):
        sys.stderr.write("writing %d blocks\n" % (nBlocks))
        fifoWrite(nBlocks)
        sys.stderr.write("reading %d blocks\n" % (nBlocks))
        fifoRead(nBlocks)


