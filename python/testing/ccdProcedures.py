import numpy as np
import time

import fpga.geom as geom

import fee.feeControl as feeMod
import fpga.ccdFuncs as ccdFuncs

reload(ccdFuncs)

class FeeTweaks(object):
    """ Interpose into fee.setMode() to override bias voltages after
        mode has been loaded from PROM.
            """
    
    def __init__(self):
        self.modes = dict()

    def getMode(self):
        return feeMod.fee.getMode()

    def setMode(self, mode):
        fee = feeMod.fee
    
        print "setting mode: ", mode
        fee.setMode(mode)
        if mode in self.modes:
            for vname, val in self.modes[mode].iteritems():
                self.setVoltage(None, vname, val)
        time.sleep(0.25)

    def setVoltage(self, mode, vname, val):

        if mode is not None:
            raise RuntimeError("tweaked modes can only set runtime voltages")
        
        fee = feeMod.fee
    
        oldVals = [fee.doGet('bias', vname, ch) for ch in 0,1]
        [fee.doSet('bias', vname, val, ch) for ch in 0,1]
        time.sleep(0.25)
        newVals = [fee.doGet('bias', vname, ch) for ch in 0,1]
        print("%s %0.1f,%0.1f -> %0.1f,%0.1f (%0.1f)" %
              (vname, oldVals[0], oldVals[1], newVals[0], newVals[1], val))

    def tweakMode(self, mode, doClear=True, **kws):
        if doClear:
            self.modes[mode] = dict()
        for k, v in kws.iteritems():
            self.modes[mode][k] = v

def stdExposures_biases(nwipes=1,
                        nbias=10,
                        feeControl=None,
                        comment='biases'):

    tweaks = FeeTweaks()

    ccdFuncs.expSequence(nwipes=nwipes, 
                         nbias=nbias,
                         feeControl=tweaks,
                         comment=comment,
                         title='%d biases' % (nbias))
    
def stdExposures_base(nrows=None, ncols=None, comment='base exposures'):
    tweaks = FeeTweaks()

    ccdFuncs.expSequence(nrows=nrows, ncols=ncols,
                         nwipes=0, 
                         nbias=20, 
                         nendbias=20, 
                         darks=[300,300,300, 1200,1200, 3600, 3600], 
                         flats=[2,2,2,10,10,10], 
                         feeControl=tweaks,
                         comment=comment,
                         title='base sequence')

def stdExposures_VOD_VOG(nrows=None, ncols=None,
                         comment='VOD/VOG tuning'):
    
    tweaks = FeeTweaks()

    ccdFuncs.expSequence(nrows=nrows, ncols=ncols,
                         nwipes=0, 
                         nbias=6, 
                         flats=[], 
                         feeControl=tweaks,
                         comment=comment,
                         title='pre-VOD/VOG tuning biases')
            
    for VOD in -21, -22:
        for VOG in -4.5, -5:
            tweaks = FeeTweaks()
            tweaks.tweakMode('read', OD=VOD, OG=VOG)

            ccdFuncs.expSequence(nrows=nrows, ncols=ncols,
                                 nwipes=0, 
                                 nbias=0, 
                                 flats=[3,3], 
                                 feeControl=tweaks,
                                 comment=comment,
                                 title='VOD/VOG tuning (%0.1f, %0.1f)' % (VOD, VOG))
            
def stdExposures_brightFlats(comment='bright flats'):
    tweaks = FeeTweaks()

    explist = (('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),

               ('flat', 2),
               ('flat', 2),
               ('flat', 4),
               ('flat', 4),
               ('flat', 6),
               ('flat', 8),
               ('flat', 8),
               ('flat', 2),
               
               ('bias', 0),
               ('flat', 12),
               ('flat', 16),
               ('flat', 16),
               ('flat', 2),
               
               ('bias', 0),
               ('flat', 24),
               ('flat', 32),
               ('flat', 32),
               ('flat', 2),
               
               ('bias', 0),
               ('flat', 48),
               ('flat', 64),
               ('flat', 64),
               ('flat', 2),
               
               ('bias', 0),
               ('flat', 80),
               ('flat', 96),
               ('flat', 112),
               ('flat', 112),
               ('flat', 128),
               ('flat', 128),
               ('flat', 2),
               
               ('bias', 0),
               ('flat', 144),
               ('flat', 160),
               ('flat', 2),
               
               ('bias', 0),
               ('flat', 192),
               ('flat', 256),
               ('flat', 2),
               
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0))

    
    ccdFuncs.expList(explist,
                     feeControl=tweaks,
                     comment=comment,
                     title='bright flats')
    

def stdExposures_lowFlats(comment='low flats'):
    tweaks = FeeTweaks()

    explist = []

    for i in range(10):
        explist.append(('bias', 0),)

    for i in range(1,31):
        explist.append(('flat', i),)
        explist.append(('flat', i),)

        if i > 0 and i % 10 == 0:
            explist.append(('bias', 0),)
            explist.append(('bias', 0),)
            explist.append(('flat', 2),)
            explist.append(('flat', 2),)

    for i in range(10):
        explist.append(('bias', 0),)
    
    ccdFuncs.expList(explist,
                     feeControl=tweaks,
                     comment=comment,
                     title='low flats')
    

def stdExposures_wipes(comment=''):
    tweaks = FeeTweaks()

    explist = (('wipe', 1),
               
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('flat', 10),
               ('bias', 0),
               
               ('flat', 16),
               ('bias', 0))

    ccdFuncs.expList(explist,
                     feeControl=tweaks,
                     comment='wipe tests',
                     title='wipe tests')

def stdExposures_Fe55(comment='Fe55 sequence'):
    tweaks = FeeTweaks()

    explist = []
    explist.append(('bias', 0),)

    for i in range(10):
        explist.extend(('dark', 1),
                       ('dark', 5),
                       ('dark', 10))
        
    for i in range(2):
        explist.extend(('dark', 30),
                       ('dark', 60))

    ccdFuncs.expList(explist,
                     feeControl=tweaks,
                     comment='Fe55 darks',
                     title='Fe55 darks')

def stdExposures_QE(comment='QE ramp', flatTime=5.0, slitWidth=1.0, waves=None):
    tweaks = FeeTweaks()

    ccdFuncs.monoSetSlitwidth(slitWidth)

    if waves is None:
        waves = np.arange(550,1100,50)
    for wave in waves:
        ccdFuncs.monoSetWavelength(wave)

        time.sleep(1.0)
        ccdFuncs.wipe()

        ret = ccdFuncs.pulseShutter(flatTime, wave)
        print ret
        stime, flux, current, energy = ret

        cards = []
        cards.append(('HIERARCH QE.slitwidth', slitWidth, 'monochrometer slit width, mm'),)
        cards.append(('HIERARCH QE.wave', wave, 'monochrometer wavelength, nm'),)
        cards.append(('HIERARCH QE.flux', slitWidth, 'calibrated flux, W/s'),)
        cards.append(('HIERARCH QE.current', current, 'Keithley current, A'),)
        cards.append(('HIERARCH QE.energy', energy, 'calibrated total energy, J'),)

        expComment = "%s wave: %s" % (comment, wave)
        im, imfile = ccdFuncs.readout('flat', expTime=flatTime,
                                      feeControl=tweaks,
                                      extraCards=cards,
                                      comment=expComment)
        
def CTEStats(flist, bias, amps=None):
    '''
    The algorithm is

    for either one flat or, better, a series of nominally identical flats prepared thus:

    adjust by adding a constant so that the median or mean OVERSCAN levels are the same

    median the frames pixel-by pixel and subtract a medianed bias, prepared the same way, and 
    also adjusted additively so that the median of the overscan area is the same as the frame--thus 
    the median of the overscanExtentsin the corrected frame is zero.

    let Ib be the median of the last illuminated row (for parallel CTE) or column (for serial), 
    (the last with level ~like the rest of the illuminated area.

    let Ic1 be the median of the next row or column, and Ic2 the median of
    the one after that, Ic3 the one after that, .... Let Ic be the sum of
    the first few (3?) of these

    Then if Ic1 << Ib, the CTE is

    1 - (Ic/Ib)/Npix

    Where Npix is the number of transfers to get to the edge you are
    investigating--512 for the serial CTE and 4xxx for the parallel.
    If Ic is not much less than Ib, the CTE is awful and it does notematter what you do.

    The last illuminated row or column is, of course, a property of the
    device, so determine it from the high flats and use the number
    for the low ones if it is unclear where it is for the low ones.
    '''

    flatExps = []
    
    allNormedOsCols = []
    allNormedOsRows = []
    allNormedCols = []
    allNormedRows = []

    allBiasOsRows = []
    allBiasOsCols = []
    allBiasRawAmps = []

    colCTEs = []
    rowCTEs = []
    
    expType = None
    expTime = None

    rowCteRowSlice = slice(100,None)
    colCteRowSlice = slice(150,-60)
    colSlice = slice(None,None)

    # preload the files
    for f_i, fname in enumerate(flist):
        exp = geom.Exposure(fname)

        if f_i == 0:
            expTime = exp.expTime
            
        if exp.expType != 'flat':
            raise RuntimeError("must use flats")
        if exp.expTime != expTime:
            raise RuntimeError("require matching flats (%s(%s) vs %s(%s)"
                               % (exp.header['IMAGETYP'], exp.header['EXPTIME'],
                                  expType, expTime))
        flatExps.append(exp)

        print("%s %0.1f: %s" % (exp.expType, exp.expTime, fname))

    print
    print("#amp    HCTE      VCTE   ampCol overCol  ampRow overRow")

    if amps is None:
        amps = range(exp.namps)
    for a_i in amps:
        biasexp = geom.Exposure(bias)
    
        # Load the bias parts once.
        biasOsRows = biasexp.overscanRowImage(a_i)[:, colSlice]
        biasOsCols = biasexp.overscanColImage(a_i)[colCteRowSlice, :]
        biasImg = biasexp.ampImage(a_i)

        allBiasOsRows.append(biasOsRows)
        allBiasOsCols.append(biasOsCols)
        allBiasRawAmps.append(biasImg)

        biasRowMed = np.median(biasOsRows)
        biasColMed = np.median(biasOsCols)

        ampOsCols = []
        ampOsRows = []
        ampRows = []
        ampCols = []
        for exp in flatExps:
            osRows = exp.overscanRowImage(a_i)[:, colSlice]
            osCols = exp.overscanColImage(a_i)[colCteRowSlice, :]
            ampImg = exp.ampImage(a_i)

            osRowMed = np.median(osRows)
            osColMed = np.median(osCols)

            ampOsCols.append((osCols - osColMed) -
                             (biasOsCols - biasColMed))
            ampOsRows.append((osRows - osRowMed) -
                             (biasOsRows - biasRowMed))
            ampCols.append((ampImg[colCteRowSlice,colSlice] - osColMed) -
                           (biasImg[colCteRowSlice,colSlice] - biasColMed))
            ampRows.append((ampImg[rowCteRowSlice,colSlice] - osRowMed) -
                           (biasImg[rowCteRowSlice,colSlice] - biasRowMed))

        normedOsCols = np.median(np.dstack(ampOsCols), axis=2)
        normedOsRows = np.median(np.dstack(ampOsRows), axis=2)
        normedCols = np.median(np.dstack(ampCols), axis=2)
        normedRows = np.median(np.dstack(ampRows), axis=2)

        allNormedOsCols.append(normedOsCols)
        allNormedOsRows.append(normedOsRows)
        allNormedCols.append(normedCols)
        allNormedRows.append(normedRows)
        

        if False:
            colCTE = 1 - (normedOsCols[:,:3].sum() / normedCols[:,-1].sum())/ampImg.shape[1]
            rowCTE = 1 - (normedOsRows[:3,:].sum() / normedRows[-1,:].sum())/ampImg.shape[0]
        else:
            osCol = normedOsCols[:,0]
            ampCol = normedCols[:,-1]
            colCTE = 1 - (np.mean(osCol*ampCol) / np.mean(ampCol*ampCol)) / ampImg.shape[1]

            osRow = normedOsRows[0,:]
            ampRow = normedRows[-1,:]
            rowCTE = 1 - (np.mean(osRow*ampRow) / np.mean(ampRow*ampRow)) / ampImg.shape[0]

            
        colCTEs.append(colCTE)
        rowCTEs.append(rowCTE)
        
        print("%d: %0.7f %0.7f  %7.2f %7.3f %7.2f %7.3f" %
              (a_i, colCTE, rowCTE,
               np.mean(ampCol), np.mean(osCol), np.mean(ampRow), np.mean(osRow)))

    return (colCTEs, rowCTEs,
            allNormedCols, allNormedOsCols,
            allNormedRows, allNormedOsRows)


def imStats(im):
    exp = geom.Exposure(im)
    
    ampIms, osIms, _ = exp.splitImage(doTrim=True)

    stats = np.zeros(shape=exp.namps,
                     dtype=([('amp', 'i2'),
                             ('signal','f4'),
                             ('sqrtSig', 'f4'),
                             ('bias', 'f4'),
                             ('readnoise', 'f4'),
                             ('readnoiseM', 'f4'),
                             ('shotnoise', 'f4'),
                             ('shotnoiseM', 'f4'),
                             ('gain', 'f4'),
                             ('gainM', 'f4'),
                             ('noise', 'f4'),
                             ('exptime', 'f4'),
                             ('flux', 'f4'),
                             ('ccd0temp', 'f4'),
                             ('preamptemp', 'f4')]))

    for a_i in range(8):
        stats[a_i]['amp'] = a_i
        ampIm = ampIms[a_i]
        osIm = osIms[a_i]
        ampSig = np.median(ampIm)
        osSig = np.median(osIm)
        stats[a_i]['signal'] = signal = ampSig - osSig
        stats[a_i]['flux'] = signal / exp.header['EXPTIME']
        stats[a_i]['exptime'] = exp.header['EXPTIME']
        stats[a_i]['preamptemp'] = exp.header['temp.PA']
        stats[a_i]['ccd0temp'] = exp.header['temp.CCD0']
        stats[a_i]['exptime'] = exp.header['EXPTIME']
        stats[a_i]['sqrtSig'] = np.sqrt(signal)
        stats[a_i]['bias'] = osSig

        sig1 = (0.741/np.sqrt(2)) * np.subtract.reduce(np.percentile(ampIm, [75,25]))
        sig2 = (0.741/np.sqrt(2)) * np.subtract.reduce(np.percentile(osIm, [75,25]))
        _, trusig1, _ = geom.clippedStats(ampIm) / np.sqrt(2)
        _, trusig2, _ = geom.clippedStats(osIm) / np.sqrt(2)
        stats[a_i]['readnoise'] = sig2
        stats[a_i]['readnoiseM'] = trusig2

        stats[a_i]['shotnoise'] = sig = np.sqrt(np.abs(sig1**2 - sig2**2))
        stats[a_i]['shotnoiseM'] = trusig = np.sqrt(np.abs(trusig1**2 - trusig2**2))

        stats[a_i]['gain'] = gain = signal/sig**2
        stats[a_i]['gainM'] = signal/trusig**2
        stats[a_i]['noise'] = sig2*gain
        
    return ampIms, osIms, stats

def flatStats(f1name, f2name):
    """ Return stats from two compatible flats.

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

    exp1 = geom.Exposure(f1name)
    exp2 = geom.Exposure(f2name)

    f1AmpIms, f1OsIms, _ = exp1.splitImage(doTrim=True)
    f2AmpIms, f2OsIms, _ = exp2.splitImage(doTrim=True)

    if (exp1.expType != 'flat' or
        exp2.expType != 'flat' or
        exp1.expTime != exp2.expTime):
        
        raise RuntimeError("require matching flats (%s(%s) vs %s(%s)"
                           % (exp1.expType, exp1.expTime,
                              exp2.expType, exp2.expTime))

    stats = np.zeros(shape=exp1.namps,
                     dtype=([('amp', 'i2'),
                             ('signal','f4'),
                             ('sqrtSig', 'f4'),
                             ('bias', 'f4'),
                             ('readnoise', 'f4'),
                             ('readnoiseM', 'f4'),
                             ('shotnoise', 'f4'),
                             ('shotnoiseM', 'f4'),
                             ('gain', 'f4'),
                             ('gainM', 'f4'),
                             ('noise', 'f4'),
                             ('flux', 'f4')]))

    diffAmpIms = []
    diffOsIms = []
    for a_i in range(8):
        stats[a_i] = a_i
        _s1 = np.median(f1AmpIms[a_i]) - np.median(f1OsIms[a_i])
        _s2 = np.median(f2AmpIms[a_i]) - np.median(f2OsIms[a_i])
        stats[a_i]['signal'] = signal = (_s1+_s2)/2
        stats[a_i]['sqrtSig'] = np.sqrt(signal)
        stats[a_i]['bias'] = (np.median(f1OsIms[a_i]) + np.median(f2OsIms[a_i]))/2

        ampIm = f2AmpIms[a_i].astype('f4') - f1AmpIms[a_i]
        osIm = f2OsIms[a_i].astype('f4') - f1OsIms[a_i]
        diffAmpIms.append(ampIm)
        diffOsIms.append(osIm)
        sig1 = (0.741/np.sqrt(2)) * np.subtract.reduce(np.percentile(ampIm, [75,25]))
        sig2 = (0.741/np.sqrt(2)) * np.subtract.reduce(np.percentile(osIm, [75,25]))
        _, trusig1, _ = geom.clippedStats(ampIm) / np.sqrt(2)
        _, trusig2, _ = geom.clippedStats(osIm) / np.sqrt(2)
        stats[a_i]['readnoise'] = sig2
        stats[a_i]['readnoiseM'] = trusig2

        stats[a_i]['shotnoise'] = sig = np.sqrt(np.abs(sig1**2 - sig2**2))
        stats[a_i]['shotnoiseM'] = trusig = np.sqrt(np.abs(trusig1**2 - trusig2**2))

        stats[a_i]['gain'] = gain = signal/sig**2
        stats[a_i]['gainM'] = signal/trusig**2
        stats[a_i]['noise'] = sig2*gain
        stats[a_i]['flux'] = signal / exp1.expTime
        
    return diffAmpIms, diffOsIms, stats

def printStats(stats):

    po = np.get_printoptions()
    np.set_printoptions(formatter=dict(float=lambda f: "%0.2f" % (f)))
    
    print("amp readnoise readnoiseM  gain  gainM    signal    bias sig^0.5 shotnoise shotnoiseM noise dn/s\n")

    for i in range(8):
        print(str(i) + "   %(readnoise)9.2f %(readnoiseM)9.2f %(gain)6.2f %(gainM)6.2f %(signal)9.2f %(bias)7.2f %(sqrtSig)7.2f %(shotnoise)9.2f %(shotnoiseM)9.2f %(noise)6.2f %(flux)5.1f" % stats[i])

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
    
