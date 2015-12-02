import numpy as np

class Exposure(object):
    def __init__(self, nccds=2):
        self.nccds = nccds
        self._setDefaultGeometry()
        
    def _setDefaultGeometry(self):
        self.ampRows = 4224
        self.ampCols = 520
        self.overRows = 100
        self.overCols = 32
        self.leadinCols = 9
        self.leadinRows = 50

        self.namps = 4 * self.nccds
        
    @property
    def nrows(self):
        return self.ampRows + self.overRows

    @property
    def ncols(self):
        return self.ampCols + self.overCols

    def ampExtents(self, ampId):
        x0 = ampId*self.ncols + self.leadinCols
        x1 = (ampId+1)*self.ampCols

        if ampId%2 == 0:
            xr = slice(x0, x1)
        else:
            xr = slice(x1-1, x0-1, -1)

        yr = slice(self.leadinRows, self.ampRows)

        return yr, xr

    def ampImage(self, im, ampId):
        yr, xr = self.ampExtents(ampId)
    
        return im[yr, xr]

    def overscanExtents(self, ampId):
        x0 = ampId*self.ncols + self.ampCols
        x1 = (ampId+1)*self.ncols

        xr = slice(x0, x1)
        yr = slice(self.leadinRows, self.ampRows)

        return xr, yr

    def overscanImage(self, im, ampId, doTrim=False):
        xr, yr = self.overscanExtents(ampId, doTrim=doTrim)
    
        return im[yr, xr]

    def coreAmpImage(self, im, ampId):
        ampImg = self.ampImage(im, ampId)

        amph, ampw = ampImg.shape
        hslice = slice(int(amph/2.0 - 50), int(amph/2.0 + 50))
        wslice = slice(int(ampw/2.0 - 50), int(ampw/2.0 + 50))
    
        return ampImg[hslice, wslice]

    def coreOverscanImage(self, im, ampId):
        ampImg = self.overscanImage(im, ampId, doTrim=False)

        amph, ampw = ampImg.shape
        hslice = slice(int(amph/2.0 - 50), int(amph/2.0 + 50))
        wslice = slice(5, None)
    
        return ampImg[hslice, wslice]
    
def biasSubtract(selim):
    bsim = np.zeros((ampRows,8*ampCols), dtype='f4')
    
    for a in range(8):
        bImg = biasSubtractAmp(im, a)
        bsim[:, a*ampCols:(a+1)*ampCols] = bImg
        
    return bsim
        
def biasSubtractAmp(im, ampId):
    x0 = ampId * ncols
    osx0 = x0 + ampCols
    
    ampIm = im[:-overRows, x0:x0+ampCols]
    osIm = im[:-overRows, osx0:osx0+overCols]
    biasVec = np.median(osIm, axis=0)

    return ampIm - biasVec[:,None]
                        
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


def splitImage(im, doTrim=False):
    exp = Exposure()
    
    ampIms = []
    osIms = []

    for a_i in range(exp.namps):
        if doTrim:
            ampIm = exp.coreAmpImage(im, a_i)
            osIm = exp.coreOverscanImage(im, a_i)
        else:
            ampIm = exp.ampImage(im, a_i)
            osIm = exp.overscanImage(im, a_i)

        ampIms.append(ampIm)
        osIms.append(osIm)

    return ampIms, osIms

def flatStats(f1, f2):
    exp = Exposure()
    
    f1AmpIms, f1OsIms = splitImage(f1, doTrim=True)
    f2AmpIms, f2OsIms = splitImage(f2, doTrim=True)
    diffAmpIms, diffOsIms = splitImage(f2-f1.astype('f4'), doTrim=True)

    stats = np.zeros(shape=exp.namps,
                     dtype=([('signal','f4'),
                             ('bias', 'f4'),
                             ('readnoise', 'f4'),
                             ('readnoiseM', 'f4'),
                             ('shotnoise', 'f4'),
                             ('shotnoiseM', 'f4'),
                             ('gain', 'f4'),
                             ('gainM', 'f4'),
                             ('noise', 'f4')]))

    for a_i in range(8):
        _s1 = np.median(f1AmpIms[a_i]) - np.median(f1OsIms[a_i])
        _s2 = np.median(f2AmpIms[a_i]) - np.median(f2OsIms[a_i])
        stats[a_i]['signal'] = signal = (_s1+_s2)/2
        stats[a_i]['bias'] = (np.median(f1OsIms[a_i]) + np.median(f2OsIms[a_i]))/2

        ampIm = diffAmpIms[a_i]
        osIm = diffOsIms[a_i]
        
        sig1 = (0.741/np.sqrt(2)) * np.subtract.reduce(np.percentile(ampIm, [75,25]))
        sig2 = (0.741/np.sqrt(2)) * np.subtract.reduce(np.percentile(osIm, [75,25]))
        _, trusig1, _ = clippedStats(ampIm) / np.sqrt(2)
        _, trusig2, _ = clippedStats(osIm) / np.sqrt(2)
        stats[a_i]['readnoise'] = sig2
        stats[a_i]['readnoiseM'] = trusig2

        stats[a_i]['shotnoise'] = sig = np.sqrt(np.abs(sig1**2 - sig2**2))
        stats[a_i]['shotnoiseM'] = trusig = np.sqrt(np.abs(trusig1**2 - trusig2**2))

        stats[a_i]['gain'] = gain = signal/sig**2
        stats[a_i]['gainM'] = signal/trusig**2
        stats[a_i]['noise'] = sig2*gain
        
    return diffAmpIms, diffOsIms, stats

def printStats(stats):

    po = np.get_printoptions()
    np.set_printoptions(formatter=dict(float=lambda f: "%0.2f" % (f)))
    
    print("amp readnoise readnoiseM  gain  gainM    signal    bias shotnoise shotnoiseM noise\n")
    for i in range(8):
        print(str(i) + "   %(readnoise)9.2f %(readnoiseM)9.2f %(gain)6.2f %(gainM)6.2f %(signal)9.2f %(bias)7.2f %(shotnoise)9.2f %(shotnoiseM)9.2f %(noise)6.2f" % stats[i])

    np.set_printoptions(**po)
        
def dispStats(f1,f2, d, frames=(2,3,4,5)):
    ampIms, osIms, stats = flatStats(f1,f2)


    d.set('frame hide all')
    for _f in frames:
        d.set('frame show %d' % (_f))
    d.set('tile row')
    
    d.set('frame %d' % frames[0])
    d.set('scale xscale')
    d.set('zoom to fit')
    
    ampIm = np.hstack(ampIms)
    d.set_np2arr(ampIm)

    d.set('frame %d' % frames[1])
    d.set('scale xscale')
    d.set('zoom to fit')
    
    osIm = np.hstack(osIms)
    d.set_np2arr(osIm)

    d.set('frame %d' % frames[2])
    d.set('scale xscale')
    d.set('zoom to fit')
    
    sigIm = np.hstack([ampIms[i] - np.median(osIms[i]) for i in range(8)])
    d.set_np2arr(sigIm)

    d.set('frame %d' % frames[3])
    d.set('scale xscale')
    d.set('zoom to fit')
    
    osIm = np.hstack([osIms[i] - np.median(osIms[i]) for i in range(8)])
    d.set_np2arr(osIm)

    return ampIms, osIms, stats
    
"""
To calculate the gain and noise:

Take two identical flats. Do
stats in a standard central region, say 100x100.
Find the median signal level in this region and
subtract the median signal in the overscan. The
average of these two is the SIGNAL, S

Subtract them

Find the quartiles in this same region. For
gaussian noise, the sigma is .741*(3rdqt - 1stqt),
but we have taken a difference, so
Sig1 = (0.741/sqrt(2))*(3rdqt - 1stqt)

is the `sigma' in the illuminated part. Also calculate
the 3-sigma clipped standard deviation and divide it
by sqrt(2). This is Trusig1.

In the
overscan region, do the same

Sig2 = (0.741/sqrt(2))*(3rdqt - 1stqt),

This is the read noise in ADU.

calculate Trusig2 likewise.

Then

Sig = sqrt (Sig1^2 - Sig2^2)

is the shot noise in the signal, and

Trusig = sqrt(Trusig1^2 - Trusig2^2)

is the `real' sigma. Compare.


Then the inverse gain G in e-/ADU is

G = S/(Sig^2). Calculate for both the
sigma based on quartiles and the one
based on moments.

The noise in electrons is Sig2*G.

"""
