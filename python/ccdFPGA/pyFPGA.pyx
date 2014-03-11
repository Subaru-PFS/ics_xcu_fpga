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
     void configureForReadout(int doTest, int nrows, int ncols)
     void finishReadout()
     uint32_t readWord()
     int readRawLine(int npixels, uint32_t *rowbuf, int rownum)
     int readLine(int npixels, uint16_t *rowbuf, int rownum)
     int readImage(int nrows, int ncols, int namps, uint16_t *imageBuf)
     uint32_t peekWord(uint32_t addr)
     int fifoRead(int nBlocks)
     int fifoWrite(int nBlocks)
     

def prow(row_i, image, **kwargs):
    """ A somple end-of-row callback. """

    nrows, ncols = image.shape

    extraArgs = kwargs if kwargs else ""

    if row_i%100 == 0 or row_i == nrows-1:
        sys.stderr.write("line %d %s" % (row_i, extraArgs))

cdef class FPGA:
    """ Provide access to the FPGA routines, especially for readout. 

    """

    def __cinit__(self):
        configureFpga(<const char *>0)

    cpdef readImageAtOnce(self, int nrows=4240, int ncols=536, int namps=8, doTest=True):
        # a contiguous C array with all the numpy and cython geometry information.
        # Yes, magic -- look at the cython manual...
        cdef numpy.ndarray[numpy.uint16_t, ndim=2, mode="c"] image = numpy.zeros((nrows,ncols*namps), 
                                                                                 dtype='u2')

        configureForReadout(doTest, nrows, ncols)
        ret = readImage(nrows, ncols, namps, &image[0,0])
        finishReadout()
        
        return image

    cpdef readImage(self, int nrows=4240, int ncols=536, int namps=8, 
                    doTest=False, rowFunc=None,
                    debug=1):
        """ Configure and read out a detector. 

        Parameters
        ----------
        nrows : int, optional
           The number of rows in the image. Default=4240
        ncols : int, optional
           The number of columns in the image. Note that this per amp. Default=536
        namps : int, optional
           The number of amps in the image. So the number of pixels is ncols * namps. Default=8
        doTest : bool, optional
           If true, return a BEE-generated synthetic image.
        rowFunc : callable, optional
           If set, a function called at the end of each line. The signature is:
              rowFunc(rowNum, image, error=None)
           where rawNum is the 0-based index of the just-read row, image, is the full image, and error
           contains any error string from the row's readout.

        Returns
        -------
        image
            An unsigned 16-bit pixels image of nrows, (ncols*namps) pixels.
        
        Examples
        --------

        >>> fpga = FPGA()
        >>> simImage = fpga.readImageByRows()
        >>> shortRealImage = fpga.readImageByRows(nrows=100, doTest=0)

        """

        # a contiguous C array with all the numpy and cython geometry information.
        # Yes, magic -- look at the cython manual...
        cdef numpy.ndarray[numpy.uint16_t, ndim=2, mode="c"] image = numpy.zeros((nrows,ncols*namps), 
                                                                                 dtype='u2')
        cdef int row_i

        configureForReadout(doTest, nrows, ncols)
        for row_i in range(nrows):
            ret = readLine(ncols*namps, &image[row_i,0], row_i)

            if rowFunc:
                rowFunc(row_i, image)
            else:
                if row_i%100 == 0 or row_i == nrows-1:
                    sys.stderr.write("line %d (ret=%s)\n" % (row_i, ret))
        finishReadout()

        return image

    cpdef fifoTest(self, int nBlocks):
        sys.stderr.write("writing %d blocks\n" % (nBlocks))
        fifoWrite(nBlocks)
        sys.stderr.write("reading %d blocks\n" % (nBlocks))
        fifoRead(nBlocks)


