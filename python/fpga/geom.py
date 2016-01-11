import itertools
import numpy as np

import fitsio

class Exposure(object):
    def __init__(self, obj=None, nccds=2, copyExposure=False):
        self.nccds = nccds
        self._setDefaultGeometry()

        if obj is None:
            self.rawImage = None
            self.image = None
            self.header = dict()
        elif isinstance(obj, Exposure):
            self.rawImage = obj.rawImage
            self.image = obj.image
            self.header = obj.header
            
            if copyExposure:
                self.image = self.image.copy()
                self.header = self.header.copy()
        elif isinstance(obj, basestring):
            self.rawImage, self.header = fitsio.read(obj, header=True)
            self.image = self.fixEdgeColsBug(self.rawImage)

        elif isinstance(obj, np.ndarray):
            self.rawImage = None
            self.image = obj.copy() if copyExposure else obj
            self.header = dict()
        else:
            raise RuntimeError("do not know how to construct from a %s" % (type(obj)))


    def fixEdgeColsBug(self, image):

        if ('CPL has not fixed the outer columns and rows yet'):
            fixedImage1 = np.ndarray(shape=image.shape, dtype=image.dtype)
            fixedImage1[:,:-1] = image[:,1:]
            fixedImage1[:,-1] = image[:,0]

            fixedImage = np.ndarray(shape=image.shape, dtype=image.dtype)
            fixedImage[:-1,:] = fixedImage1[1:,:]
            fixedImage[-1,:] = fixedImage1[0,:]

            return fixedImage
        else:
            return image
        
    def _setDefaultGeometry(self):
        self.ampCols = 520
        self.ccdRows = 4224
        self.overCols = 32
        self.leadinCols = 8
        self.leadinRows = 48
        
        self.flipAmps = True
        
        self.namps = 4 * self.nccds

    @property
    def expType(self):
        return self.header.get('IMAGETYP', 'unknown').strip()
    
    @property
    def expTime(self):
        return self.header.get('EXPTIME', -1.0)

    @property
    def activeRows(self):
        self.ccdRows - self.leadinRows
        
    @property
    def activeCols(self):
        self.ampCols - self.leadinCols
        
    @property
        self.overRows = 76
    def nrows(self):
        return self.ccdRows + self.overRows

    @property
    def ncols(self):
        return self.ampCols + self.overCols

    def ampExtents(self, ampId, leadingCols=False, leadingRows=False):
        x0 = ampId*self.ncols + self.leadinCols*(not leadingCols)
        x1 = ampId*self.ncols + self.ampCols

        if not self.flipAmps or ampId%2 == 0:
            xr = slice(x0, x1)
        else:
            xr = slice(x1-1, x0-1, -1)

        yr = slice(self.leadinRows*(not leadingRows), self.ccdRows)

        return yr, xr

    def ampImage(self, ampId, im=None, leadingCols=False, leadingRows=False):
        if im is None:
            im = self.image
            
        yr, xr = self.ampExtents(ampId, leadingRows=leadingRows, leadingCols=leadingCols)

        return im[yr, xr]

    def overscanCols(self, ampId, leadingRows=False, overscanRows=False):
        x0 = ampId*self.ncols + self.ampCols
        x1 = x0 + self.overCols

        xr = slice(x0, x1)
        yr = slice(self.leadinRows*(not leadingRows),
                   self.ccdRows + self.overRows*(overscanRows))

        return yr, xr

    def overscanRows(self, ampId, leadingCols=False, overscanCols=False):
        x0 = ampId*self.ncols + self.leadinCols*(not leadingCols)
        x1 = ampId*self.ncols + self.ampCols + self.overCols*(overscanCols)

        xr = slice(x0, x1)
        yr = slice(self.ccdRows, self.ccdRows + self.overRows)

        return yr, xr

    def overscanRowImage(self, ampId, im=None, leadingCols=False, overscanCols=False):
        if im is None:
            im = self.image
        yr, xr = self.overscanRows(ampId, leadingCols=leadingCols, overscanCols=overscanCols)
    
        return im[yr, xr]

    def overscanColImage(self, ampId, im=None, leadingRows=False, overscanRows=False):
        if im is None:
            im = self.image
        yr, xr = self.overscanCols(ampId, leadingRows=leadingRows, overscanRows=overscanRows)
    
        return im[yr, xr]

    def coreAmpImage(self, ampId, im=None, offset=(0,0)):
        if im is None:
            im = self.image
        ampImg = self.ampImage(ampId, im=im)

        amph, ampw = ampImg.shape
        hslice = slice(int(amph/2.0 - 50 + offset[0]),
                       int(amph/2.0 + 50 + offset[0]))
        wslice = slice(int(ampw/2.0 - 50 + offset[1]),
                       int(ampw/2.0 + 50 + offset[1]))
    
        return ampImg[hslice, wslice]

    def coreOverscanColImage(self, ampId, im=None):
        if im is None:
            im = self.image
        ampImg = self.overscanColImage(ampId, im=im)

        amph, ampw = ampImg.shape
        hslice = slice(int(amph/2.0 - 50), int(amph/2.0 + 50))
        wslice = slice(5, -1)
    
        return ampImg[hslice, wslice]

    def coreOverscanRowImage(self, ampId, im=None):
        if im is None:
            im = self.image
        ampImg = self.overscanRowImage(ampId, im=im)

        amph, ampw = ampImg.shape
        hslice = slice(5, -1)
        wslice = slice(int(ampw/2.0 - 50), int(ampw/2.0 + 50))
    
        return ampImg[hslice, wslice]

    def allAmpsImages(self, leadingCols=False, leadingRows=False):
        ampIms = []
        
        for i in range(self.namps):
            ampIms.append(self.ampImage(i, leadingCols=leadingCols,
                                        leadingRows=leadingRows))

        return ampIms
    
    def allOverscanColImages(self, leadingRows=False, overscanRows=False):
        osIms = []
        
        for i in range(self.namps):
            osIms.append(self.overscanColImage(i, leadingRows=leadingRows,
                                               overscanRows=overscanRows))

        return osIms
    
    def allOverscanRowImages(self, leadingCols=False, overscanCols=False):
        osIms = []
        
        for i in range(self.namps):
            osIms.append(self.overscanRowImage(i, leadingCols=leadingCols,
                                               overscanCols=overscanCols))

        return osIms

    def splitImage(self, doTrim=False, doFull=False):

        if doTrim and doFull:
            raise RuntimeError("cannot accept both doFull and doTrim")
        
        ampIms = []
        osColIms = []
        osRowIms = []

        for a_i in range(self.namps):
            if doTrim:
                ampIm = self.coreAmpImage(a_i)
                osColIm = self.coreOverscanColImage(a_i)
                osRowIm = self.coreOverscanRowImage(a_i)
            elif doFull:
                ampIm = self.ampImage(a_i, leadingCols=True, leadingRows=True)
                osColIm = self.overscanColImage(a_i, leadingRows=True)
                osRowIm = self.overscanRowImage(a_i, leadingCols=True, overscanCols=True)
            else:
                ampIm = self.ampImage(a_i)
                osColIm = self.overscanColImage(a_i)
                osRowIm = self.overscanRowImage(a_i)

            ampIms.append(ampIm)
            osColIms.append(osColIm)
            osRowIms.append(osRowIm)

        return ampIms, osColIms, osRowIms

    def biasSubtract(self, bias):
        bias = Exposure(bias)

        biasParts = bias.splitImage()
        coreBiasParts = bias.splitImage(doTrim=True)
        
        parts = self.splitImage()
        coreParts = self.splitImage(doTrim=True)

        newAmps = []
        newOverCols = []
        
        for a_i in range(self.namps):
            biasOffset = np.median(coreBiasParts[1][a_i]) - np.median(coreParts[1][a_i])

            newAmps.append(parts[0][a_i] - (biasParts[0][a_i] - biasOffset))
            newOverCols.append(parts[1][a_i] - (biasParts[1][a_i] - biasOffset))

        print newAmps[0].shape, newOverCols[0].shape
        return newAmps, newOverCols
        
    def biasSubtractOne(self, im=None, byRow=False):
        if im is None:
            im = self.image
        amps = []

        for a_i in range(8):
            amps.append(self.biasSubtractAmp(a_i, im=im, byRow=byRow))
        
        return np.hstack(amps)

    
    def biasSubtractAmp(self, ampId, im=None, byRow=False):
        if im is None:
            im = self.image

        ampIm = self.ampImage(ampId, im=im)
        osYr, osXr = self.overscanExtents(ampId)

        if byRow:
            imMed = np.median(im[osYr, osXr],
                              axis=1, keepdims=True).astype('i4')
            print "%s: %s %s" % (ampId, osYr, osXr)
        else:
            osYr = slice(osYr.start + 500,
                         osYr.stop - 500)
            osXr = slice(osXr.start+3, osXr.stop)
            print "%s: %s %s" % (ampId, osYr, osXr)
        
            imMed = int(np.median(im[osYr, osXr]))

        return ampIm.astype('i4') - imMed
    
    def finalImage(self):
        ampImages = self.allAmpsImages()
        return np.hstack(ampImages)
    
def clippedStats(a, nsig=3.0, niter=5):
    a = a.reshape(-1)
    keep = np.ones(a.size, dtype=np.bool)

    for i in range(niter):
        mn = a[keep].mean()
        sd = a[keep].std()
        nkeep0 = keep.sum()
        keep &= np.abs(a - mn) < nsig*sd
        nkeep1 = keep.sum()

        if nkeep1 == nkeep0:
            return mn, sd, float(nkeep1)/a.size

    print "too many iterations (%d): fullsize=%d clipped=%d lastclipped=%d" % (i, a.size,
                                                                               nkeep0, nkeep1)
    return a[keep].mean(), a[keep].std(), float(nkeep1)/a.size

def clippedStack(flist, dtype='i4'):
    """ Return the median of a stack of images.

    Notes:
    
    The individual images are median-subtracted before medianed together, and 
    the median offset is added back to the result.

    All images must match the images type and exposure time of the first image.
    
    """

    exp = Exposure(flist[0])
    imshape = exp.image.shape
    imtype = exp.header['IMAGETYP']
    exptime = exp.header['EXPTIME']

    stack = np.zeros((len(flist), imshape[0], imshape[1]), dtype=dtype)
    meds = np.zeros(len(flist))

    for i, f in enumerate(flist):
        exp = Exposure(f)
        if exp.header['IMAGETYP'] != imtype or exp.header['EXPTIME'] != exptime:
            print("%s: unexpected imagetyp: %s(%0.2f) vs %s(%0.2f)"
                  % (f, 
                     exp.header['IMAGETYP'], exp.header['EXPTIME'],
                     imtype, exptime))
            
        meds[i] = np.median(exp.image)
        stack[i] = exp.image - meds[i]

    medimg = np.median(stack, axis=0)
    return medimg + np.median(meds), meds
                                                                                                            
def finalImage(exp, bias=None, dark=None, flat=None):
    exp = Exposure(exp)
    return exp.biasSubtract(bias)
    
def constructImage(ampIms, osColIms=None, osRowIms=None):
    orderedIms = []

    if osColIms is not None:
        for i in range(len(ampIms)):
            orderedIms.append(np.concatenate((ampIms[i], osColIms[i]), axis=1))
    else:
        orderedIms = ampIms[:]

    if osRowIms is not None:
        for i in range(len(orderedIms)):
            orderedIms[i] = np.concatenate((orderedIms[i], osRowIms[i]), axis=0)

    ret = np.concatenate(orderedIms, axis=1)
    return ret

