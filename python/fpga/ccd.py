import numpy
import sys
import time

import astropy.io.fits as pyfits

import pyFPGA
import SeqPath

class CCD(pyFPGA.FPGA):
    """Top-level wrapper for FPGA control and readout. 

    The core routines to access the FPGA are in c/fpga.[ch]. We access
    parts of that through the Cython pyFPGA.pyx, which we subclass
    here to add python routines. Basically, we want to push all C
    access into fpga.c and pyFPGA.pyx. In practice, all that we
    encapsulate are the routines which need direct mmap access, and
    one single readLine() routine. pyFPGA.FPGA wraps that C readLine()
    with one (moderately complex) readImage() method.

    """
    def __init__(self, adc18bit=1, dewarID=12):
        baseTemplate = '%(filePrefix)s%(seqno)'
        self.fileMgr = SeqPath.NightFilenameGen('/data/pfs',
                                                filePrefix='PFSA',
                                                filePattern="%s%02d.fits" % (baseTemplate,
                                                                             dewarID))

    def ampidx(self, ampid, im=None):
        """ Return an ndarray mask for a single amp. 

        Examples
        --------

        >>> amp1mask = ccd.ampidx(1, im)
        >>> amp1inRow100 = im[100, amp1mask]
        >>> amp1forFullImage = im[:, amp1mask]
        """

        if im is not None:
            ncols = im.shape[1]/self.namps
        else:
            ncols = 536
        
        return numpy.arange(ncols) + ampid*ncols

    def writeImageFile(self, im, 
                       comment=None, addCards=None):

        fnames = self.fileMgr.getNextFileset()

        hdr = pyfits.Header()
        if comment is not None:
            hdr.add_comment(comment)
        if addCards is not None:
            for card in addCards:
                hdr.append(card)
        hdu = pyfits.PrimaryHDU(data=im, header=hdr)
        hdu.writeto(fnames[0])
        return fnames

    def readImage(self, nrows=4240, ncols=536,
                  doTest=False, debugLevel=1, 
                  doAmpMap=True, 
                  doReread=False,
                  rowFunc=None, rowFuncArgs=None,
                  doReset=True, doSave=True, 
                  comment=None, addCards=None,
                  clockFunc=None):
                  
        """ Configure and readout the detector; write image to disk. 

        Parameters
        ----------
        doReset : bool, optional
           If set False, does not PCI-reset the FPGA before starting.
        doSave : bool , optional
           If set False, does not save the image to disk FITS file.
        doReread : bool, optional
           If set, do not start a new exposure, but reread the one on the FPGA.

        Notes
        -----
        The bulk of the work is done in the _readImage routine -- see that
        documentation for most of the arguments.
        """

        if doReset:
            self.pciReset()

        if not doReread:
            self.configureReadout(nrows=nrows, ncols=ncols, doTest=doTest, clockFunc=clockFunc)

        im = self._readImage(nrows=nrows, ncols=ncols, 
                             doTest=doTest, debugLevel=debugLevel,
                             doAmpMap=doAmpMap,
                             rowFunc=rowFunc, rowFuncArgs=rowFuncArgs)

        if doSave:
            files = self.writeImageFile(im, comment=comment, addCards=addCards)
        else:
            files = []

        return im, files

