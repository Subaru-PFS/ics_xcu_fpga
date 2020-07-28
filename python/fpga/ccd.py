from importlib import reload
import logging
import numpy as np
import sys
import time
from functools import partial

import astropy.io.fits as pyfits

from pyFPGA import FPGA
    
from . import SeqPath

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
        ampCols = ncols//8
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

    armNames = {'red':'red',
                'blue':'blue',
                'r':'red',
                'b':'blue'}

    def __init__(self, spectroId=None, arm=None,
                 rootDir='/data/pfs', site=None,
                 splitDetectors=False,
                 adcVersion=None, adcBits='default',
                 doCorrectSignBit=True):

        if not isinstance(spectroId, int) and spectroId < 1 or spectroId > 9:
            raise RuntimeError('spectroId must be 1..9')
        try:
            arm = self.armNames[arm]
        except KeyError:
            raise RuntimeError('arm must be one of: ', list(self.armNames.keys()))

        assert splitDetectors is False, "cannot handle splitting detector files yet"

        self.logger = logging.getLogger('ccd')
        
        self.headerVersion = 1
        self.arm = arm
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
        # self.logger.warn('ccd is: %s', str(self))

        self.setAdcVersion(adcVersion)
        self.setAdcType(adcBits, doCorrectSignBit=doCorrectSignBit)
        self.holdOn = set()
        self.holdOff = set()

    def __str__(self):
        return "FPGA(readoutState=%d,ver=%s,newADC=%s,adc18=%s,correctSignBit=%s)" % (self.readoutState(),
                                                                                      self.fpgaVersion(),
                                                                                      self.newAdc,
                                                                                      self.adc18bit,
                                                                                      self.doCorrectSignBit)
    def __repr__(self):
        return str(self)
    
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
                           self.dewarNumbers[self.arm])

    @property
    def detectorNum(self):
        assert not self.splitDetectors, "do not yet know how to split detector reads. "
        return 2

    def fpgaVersion(self):
        return "0x%04x" % ((self.peekWord(0) & 0xffff) + 1)

    def setAdcVersion(self, adcVersion=None):
        """Set whether we are using a new (full signed 18-bit) or old (18-bit, sign=0) ADC.

        This is used in two places:
         - to select the readout mode clocking file
         - to translate from the logical readout names to the FPGA bitmask 
        """
        if adcVersion is None:
            version = self.peekWord(0)
            majorVersion = version & 0x00f0
            if majorVersion == 0x70:
                isNew = False
            elif majorVersion == 0x80:
                isNew = True
            else:
                raise ValueError(f"unknown FPGA major version: {majorVersion:0x02f} from {version:0x04x}")
        elif adcVersion == 'old':
            isNew = False
        elif adcVersion == 'new':
            isNew = True
        else:
            raise ValueError(f"ADC version is neither 'old', nor 'new': {adcVersion}")

        self.newAdc = isNew

    def setAdcType(self, adcType, doCorrectSignBit=True):
        """Set the ADC 16-from-18 bit conversion mode. 

        Args:
        ----
        adcType : `str`
          'lsb' or 'mid' (default) for old ADCs.
          'lsb', 'mid', or 'msb' (default) for new ADCs.
        doCorrectSignBit : `bool`
          Whether to convert signed to unsigned pixel values,
          for 'msb' values on new ADCs.

        Must match FPGA and C code:

        WPU_18BIT and WPU_18BIT2:
        Old (0x70-series) ADC:
          11 - drop two MSBs ('lsb"==3==0b11)
          10 - NORMAL mode: drop LSB and MSB ("mid"==2==0b10)
          0x - never use: configures FPGA for 16-bit ADC boards.
        New (0x80-series):
          11 - NORMAL mode: drop two LSB ("msb"==3==0b11)
          10 - middle bits: drop LSB and MSB ("mid"==2==0b10)
          0x - low bits: drop twp MSB (lsb"==1==0b01)
        """
        if self.newAdc:
            if adcType in {'msb', 'default'}:
                adcType = 3
            elif adcType == 'mid':
                adcType = 2
            elif adcType == 'lsb':
                adcType = 1
            else:
                raise ValueError("for new ADCs, adcType (%s) must be 'lsb', or 'mid', or 'msb'" % (adcType))
        else:
            if adcType in {'mid', 'default'}:
                adcType = 2
            elif adcType == 'lsb':
                adcType = 3
            else:
                raise ValueError("for old ADCs, adcType (%s) must be 'lsb', or 'mid'" % (adcType))
                
        self.adc18bit = adcType
        self.doCorrectSignBit = (adcType == 3) and doCorrectSignBit
        

    def setClockLevels(self, turnOn=None, turnOff=None, cmd=None):
        """Set some clock lines on or off.
        
        Args
        ----
        turnOn : list of Clocks to set on
        tunOff : list of Clocks to set off
        cmd : optional Command to report to

        In order to set clocks we need to fire up the FPGA's clocking
        routine. This was mostly designed to readout the detector,
        sequencing clocks for P pixels and R rows, where R >= 1

        So we construct the clocking for a 0 pixel image, which simply
        prepares the clocks for a row. Then we run that for one one row.

        """
        
        from clocks import clocks
        reload(clocks)
        ticks, opcodes, readTime = clocks.genSetClocks(turnOn=turnOn,
                                                       turnOff=turnOff)
        self.resetReadout()     # Clear FPGA waveform array.
        for i in range(len(ticks)):
            if cmd is not None:
                cmd.inform('text="setting clocks: 0x%08x %d"' % (opcodes[i], ticks[i]))
            sys.stderr.write("setting clocks: 0x%08x %d\n" % (opcodes[i], ticks[i]))
            ret = self.sendOneOpcode(opcodes[i], ticks[i])
            if not ret:
                raise RuntimeError("failed to send opcode %d" % (i))
        if not self.armReadout(1, 0, self.adc18bit):
            raise RuntimeError("failed to arm for readout)")
        self.finishReadout()
        
    def holdClocks(self, holdOn=None, holdOff=None, cmd=None):
        """Set some clock lines on or off during subsequent reads.
        
        Args
        ----
        holdOn  : list of Clocks to set on
        holdOff : list of Clocks to set off
        cmd : optional Command to report to

        All this does is save what we want to do.
        """

        self.holdOn = holdOn
        self.holdOff = holdOff
        
        cmd.debug(f'text="set read clock holdOn={holdOn} and holdOff={holdOff}"')

    def getReadClocks(self):
        """ Fetch the final read mode clocking routine. """

        if self.newAdc:
            import clocks.read as readClocks
            reload(readClocks)
        else:
            import clocks.oldAdcRead as readClocks
            reload(readClocks)

        readClocks = partial(readClocks.readClocks, holdOn=self.holdOn, holdOff=self.holdOff)
        self.logger.info(f'clocks (new={self.newAdc}) with holdon={self.holdOn}, holdOff={self.holdOff}')
        
        return readClocks
    
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
            ampCols = ncols//8
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
        cards.append(('DEWARNAM', self.arm, "DEPRECATED: use ARM"))
        cards.append(('W_ARM', self.arm, "Dewar name: 'blue', 'red', 'NIR'"))
        cards.append(('DETNUM', self.detectorNum, "Detector number: 0/1, or 2 if both detectors."))
        if self.holdOn:
            cards.append(('W_HLDON', ','.join({str(s) for s in self.holdOn}), "clocks held on"))
        if self.holdOff:
            cards.append(('W_HLDOFF', ','.join({str(s) for s in self.holdOff}), "clocks held off"))
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
                  clockFunc=None,
                  doReset=True, doSave=True, 
                  comment=None, addCards=None):
                  
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

        self.logger.warn('ccd is: %s', str(self))

        if clockFunc is None:
            clockFunc = self.getReadClocks()
        
        if nrows is None:
            nrows = self.nrows
        if ncols is None:
            ncols = self.ncols

        readRows = nrows/rowBinning
        if readRows * rowBinning != nrows:
            self.logger.warn("warning: rowBinning (%d) does not divide nrows (%d) integrally." % (rowBinning,
                                                                                                  nrows))
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
        elapsedTime = t1-t0
        
        if abs(elapsedTime-expectedTime) > 0.1*expectedTime:
            self.logger.warn("readTime = %g; expected %g" % (elapsedTime, expectedTime))

        # INSTRM-40: Paper over an FPGA bug which we have not found, where there is
        # a spurious 0th pixel, which effectively wraps the rest of the pixels.
        #
        # I'm pretty sure this comes from the fact that we clock out
        # the pixel data from the ADC _before_ we convert it: we clock
        # out the previous pixel's value. So there is an _extra_ 0th
        # pixel, and we never read the last one.
        #
        # Not sure we should fix this.
        #
        imShape = im.shape
        im = im.ravel()
        im[:-1] = im[1:]
        im = im.reshape(imShape)

        if doSave:
            imfile = self.writeImageFile(im, comment=comment, addCards=addCards)
        else:
            imfile = None

        return im, imfile
