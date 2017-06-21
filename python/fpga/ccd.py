import logging
import numpy as np
import sys
import time

import astropy.io.fits as pyfits

try:
    from pyFPGA import FPGA
except:
    FPGA = object
    
import SeqPath

class FakeCCD(object):
    def ampidx(self, ampid, im):
        """ Return an ndarray mask for a single amp. 

        Examples
        --------

        >>> amp1mask = ccd.ampidx(1, im)
        >>> amp1inRow100 = im[100, amp1mask]
        >>> amp1forFullImage = im[:, amp1mask]
        """

        nrows, ncols = im.shape
        ampCols = ncols / 8
        return np.arange(ampCols*ampid, ampCols*(ampid+1))
        
class CCD(FPGA):
    """Top-level wrapper for FPGA control and readout. 

    The core routines to access the FPGA are in c/fpga.[ch]. We access
    parts of that through the Cython pyFPGA.pyx, which we subclass
    here to add python routines. Basically, we want to push all C
    access into fpga.c and pyFPGA.pyx. In practice, all that we
    encapsulate are the routines which need direct mmap access, and
    one single readLine() routine. pyFPGA.FPGA wraps that C readLine()
    with one (moderately complex) readImage() method.

    """
    
    dewarNumbers = {'red':2,
                    'blue':1,
                    'r':2,
                    'b':1}
    
    def __init__(self, spectroId, dewarId,
                 rootDir='/data/pfs', site=None,
                 splitDetectors=False, adc18bit=1):
        if not isinstance(spectroId, int) and spectroId < 1 or spectroId > 9:
            raise RuntimeError('spectroId must be 1..9')
        if dewarId not in self.dewarNumbers:
            raise RuntimeError('dewarId must be one of: ', self.dewarNumbers.keys())

        assert splitDetectors is False, "cannot handle splitting detector files yet"

        self.logger = logging.getLogger('ccd')
        
        self.headerVersion = 1
        self.dewarId = dewarId
        self.spectroId = spectroId
        self.splitDetectors = splitDetectors

        baseTemplate = '%(filePrefix)s%(seqno)06d'
        self.fileMgr = SeqPath.NightFilenameGen(rootDir,
                                                filePrefix='PF%sA' % (site),
                                                filePattern="%s%s.fits" % (baseTemplate,
                                                                           self.detectorName))

        # Defaults for real detectors.  Put in config file, CPL
        self.ampCols = 520
        self.ccdRows = 4224
        self.overCols = 32
        self.overRows = 76
        self.leadinCols = 8
        self.leadinRows = 48
        self.namps = 8
        self.readDirection = 0b10101010
        
    @property
    def nrows(self):
        """ Number of rows for the readout, derived from .ccdRows + .overRows. """
        
        return self.ccdRows + self.overRows

    @property
    def ncols(self):
        """ Number of cols for one amp's readout, derived from .ampCols + .overCols. """

        return self.ampCols + self.overCols

    @property
    def detectorName(self):
        """ The 2-digit name for this device. Used for the FITS file name. """
        
        return "%1d%1d" % (self.spectroId,
                           self.dewarNumbers[self.dewarId])

    @property
    def detectorNum(self):
        assert not self.splitDetectors, "do not yet know how to split detector reads. "
        return 2

    def fpgaVersion(self):
        return "0x%08x" % ((self.peekWord(0) & 0xffff) + 1)
    
    def ampidx(self, ampid, im=None):
        """ Return an ndarray mask for a single amp. 

        Examples
        --------

        >>> amp1mask = ccd.ampidx(1, im)
        >>> amp1inRow100 = im[100, amp1mask]
        >>> amp1forFullImage = im[:, amp1mask]
        """

        if im is not None:
            nrows, ncols = im.shape
            ampCols = ncols / 8
            return np.arange(ampCols*ampid, ampCols*(ampid+1))
        else:
            return np.arange(ampid*self.ncols+self.leadinCols,
                             (ampid+1)*self.ncols-self.overCols)

    def idCards(self):
        """ Return the full set of FITS cards to identify this detector (pair). """

        cards = []
        cards.append(('HEADVERS', self.headerVersion, 'FITS header version'))
        cards.append(('HIERARCH versions.FPGA', self.fpgaVersion(), "FPGA version, read from FPGA."))
        cards.append(('HIERARCH W_VERSIONS_FPGA', self.fpgaVersion(), "FPGA version, read from FPGA."))
        cards.append(('SPECNUM', self.spectroId, "Spectrograph number: 1..4, plus engineering 5..9"))
        cards.append(('DEWARNAM', self.dewarId, "Dewar name: 'blue', 'red', 'NIR'"))
        cards.append(('DETNUM', self.detectorNum, "Detector number: 0/1, or 2 if both detectors."))

        return cards

    def geomCards(self):
        cards = []

        cards.append(('HIERARCH geom.rows.leadin', self.leadinRows, "rows in necked area"))
        cards.append(('HIERARCH geom.rows.active', self.ccdRows-self.leadinRows, "active rows"))
        cards.append(('HIERARCH geom.rows.overscan', self.overRows, "overscan rows"))
        cards.append(('HIERARCH geom.cols.leadin', self.leadinCols, "unilluminated cols"))
        cards.append(('HIERARCH geom.cols.active', self.ampCols-self.leadinCols, "active columns"))
        cards.append(('HIERARCH geom.cols.overscan', self.overCols, "overscan columnss"))
        cards.append(('HIERARCH geom.namps', self.namps, "number of amps in image"))
        cards.append(('HIERARCH geom.readDirection', self.readDirection,
                      "0th bit: right amp; 0: read right, 1: read left"))

        return cards
    
    def printProgress(row_i, image, errorMsg="OK", everyNRows=100, 
                      **kwargs):
        """ A sample end-of-row callback. Prints all errors and per-100 row progess lines. """

        nrows, ncols = image.shape

        if row_i%everyNRows == 0 or row_i == nrows-1 or errorMsg is not "OK":
            sys.stderr.write("line %05d %s\n" % (row_i, errorMsg))

    def addHeaderCards(self, hdr, cards):
        for card in cards:
            try:
                hdr.append(card)
            except Exception as e:
                self.logger.warning("failed to add card to header: %s", e)
                self.logger.warning("failed card: %r", card)
            
    def writeImageFile(self, im, 
                       comment=None, addCards=None):

        fnames = self.fileMgr.getNextFileset()
        fname = fnames[0]
        
        self.logger.warning('creating fits file: %s', fname)

        hdr = pyfits.Header()
        self.addHeaderCards(hdr, self.idCards())
        self.addHeaderCards(hdr, self.geomCards())
            
        if comment is not None:
            self.addHeaderCards(hdr, [comment])
        if addCards is not None:
            self.addHeaderCards(hdr, addCards)
                    
        try:
            pyfits.writeto(fname, im, hdr, checksum=True)
        except Exception as e:
            self.logger.warn('failed to write fits file %s: %s', fname, e)
            self.logger.warn('hdr : %s', hdr)
        
        return fname

    def readImage(self, nrows=None, ncols=None,
                  rowBinning=1,
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

        if nrows is None:
            nrows = self.nrows
        if ncols is None:
            ncols = self.ncols

        readRows = nrows / rowBinning
        if readRows * rowBinning != nrows:
            print "warning: rowBinning (%d) does not divide nrows (%d) integrally." % (rowBinning,
                                                                                       nrows)
            
        if doReset:
            self.pciReset()

        if not doReread:
            expectedTime = self.configureReadout(nrows=readRows, ncols=ncols,
                                                 rowBinning=rowBinning,
                                                 doTest=doTest, clockFunc=clockFunc)

        t0 = time.time()
        im = self._readImage(nrows=readRows, ncols=ncols, 
                             doTest=doTest, debugLevel=debugLevel,
                             doAmpMap=doAmpMap,
                             rowFunc=rowFunc, rowFuncArgs=rowFuncArgs)
        t1 = time.time()

        print("readTime = %g; expected %g" % (t1-t0, expectedTime))

        if doSave:
            imfile = self.writeImageFile(im, comment=comment, addCards=addCards)
        else:
            imfile = None

        return im, imfile
