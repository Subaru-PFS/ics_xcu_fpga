import numpy as np
import time

import fpga.geom as geom

import fpga.ccdFuncs as ccdFuncs
import fpga.opticslab as opticslab

reload(geom)
reload(ccdFuncs)
reload(opticslab)

class FeeTweaks(object):
    """ Interpose into fee.setMode() to override bias voltages after mode has been loaded from PROM.

    Also prints out overrides.
    """
    
    def __init__(self, fee=None):
        if fee is None:
            from fee import feeControl as feeMod
            reload(feeMod)
            fee = feeMod.fee
            
        self.fee = fee
        self.modes = dict()

    def getMode(self):
        return self.fee.getMode()

    def statusAsCards(self):
        return self.fee.statusAsCards()

    def setMode(self, mode):
        print "setting mode: ", mode
        self.fee.setMode(mode)
        if mode in self.modes:
            for vname, val in self.modes[mode].iteritems():
                self.setVoltage(None, vname, val)
        time.sleep(0.25)

    def setVoltage(self, mode, vname, val):

        if mode is not None:
            raise RuntimeError("tweaked modes can only set runtime voltages")
        
        fee = self.fee
    
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

def stdExposures_biases(ccd=None,
                        nbias=21,
                        feeControl=None,
                        comment='biases'):

    ccdFuncs.expSequence(ccd=ccd,
                         nbias=nbias,
                         feeControl=feeControl,
                         comment=comment,
                         title='%d biases' % (nbias))

def stdExposures_darks(ccd=None,
                       ndarks=21, darkTime=150,
                       feeControl=None,
                       comment='darks'):

    ccdFuncs.expSequence(ccd=ccd,
                         darks=[darkTime]*ndarks,
                         feeControl=feeControl,
                         comment=comment,
                         title='%d %gs darks' % (ndarks, darkTime))

def stdExposures_base(ccd=None, feeControl=None, comment=None):

    stdExposures_biases(ccd=ccd, feeControl=feeControl, comment=comment)
    stdExposures_darks(ccd=ccd, feeControl=feeControl, comment=comment)

def stdExposures_hours(ccd=None, feeControl=None, hours=4, comment=None):
    darkTime = 900
    for i in range(hours):
        ccdFuncs.expSequence(ccd=ccd,
                             biases=5,
                             darks=[900]*4,
                             feeControl=feeControl,
                             comment=comment,
                             title='1 hour %fs dark loop' % (darkTime))

def calcOffsets(target, current):
    m = np.round((target - current) / 30, 2)
    r = np.round(m * 40.0/57.0, 2)

    return m, r

def tuneOffsets(ccd=None, feeControl=None):
    amps = range(8)
    feeControl.zeroOffsets(amps)

    im, fname = ccdFuncs.fullExposure('bias', ccd=ccd,
                                      feeControl=feeControl, nrows=300)
    exp = geom.Exposure(im)

    ampIms, osIms, _ = exp.splitImage(doTrim=False)

    means = []
    for a_i in range(8):
        reg = osIms[a_i][20:-20][2:-2]
        means.append(reg.mean())

    m, r = calcOffsets(1000,np.array(means))
    print("applying master: %s" % (m))
    print("applying refs  : %s" % (r))

    feeControl.setOffsets(amps, m, leg='n', doSave=False)
    feeControl.setOffsets(amps, r, leg='p', doSave=True)
    feeControl.setMode('offset')
    
    im, fname = ccdFuncs.fullExposure('bias', ccd=ccd,
                                      feeControl=feeControl, nrows=200)
    exp = geom.Exposure(im)

    ampIms, osIms, _ = exp.splitImage(doTrim=False)
    means = []
    for a_i in range(8):
        reg = osIms[a_i][20:-20][2:-2]
        means.append(reg.mean())
    print("final means: %s" % ' '.join(["%0.1f" % m for m in means]))

def stdExposures_VOD_VOG(ccd=None, feeControl=None,
                         VOD=None, VOG=None,
                         nrows=None, ncols=None,
                         comment='VOD/VOG tuning'):

    if VOD is None:
        VOD = np.arange(-18.0, -22.01, -0.5)
    if VOG is None:
        VOG = np.arange(-3.0, -5.01, -0.25)
        
    opticslab.setup(ccd.arm, flux=1000)

    ccdFuncs.expSequence(ccd=ccd,
                         nrows=nrows, ncols=ncols,
                         nbias=3, 
                         feeControl=feeControl,
                         comment=comment,
                         title='pre-VOD/VOG tuning biases')

    files = []
    for vod in VOD:
        for vog in VOG:
            tweaks = FeeTweaks(feeControl)
            tweaks.tweakMode('read', OD=vod, OG=vog)

            files1 = ccdFuncs.expSequence(ccd=ccd,
                                          nrows=nrows, ncols=ncols,
                                          nbias=1, 
                                          flats=[4], 
                                          feeControl=tweaks,
                                          comment=comment,
                                          title='VOD/VOG tuning (%0.1f, %0.1f)' % (vod, vog))
            files.extend(files1)

    return files

def stdExposures_brightFlats(ccd=None, feeControl=None, comment='bright flats'):
    """ Canonical bright flats sequence. 

    At 1000ADU/s, take flats running up past saturation.
    """
    
    opticslab.setup(ccd.arm, flux=1000)

    explist = (('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('dark', 100),
               
               ('flat', 100),
               ('flat', 1),
               ('flat', 2),
               ('flat', 3),
               ('flat', 5),
               ('flat', 7),

               ('flat', 100),
               ('flat', 10),
               ('flat', 14),
               ('flat', 20),
               ('flat', 28),
               ('flat', 40),

               ('flat', 100),
               ('flat', 50),
               ('flat', 60),
               ('flat', 70),
               ('flat', 80),
               ('flat', 90),

               ('flat', 100),
               ('flat', 110),
               ('flat', 120),
               ('flat', 130),
               ('flat', 140),

               ('flat', 100),
               ('flat', 160),
               ('flat', 180),
               ('flat', 200),
               ('flat', 220),
               
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('dark', 100))

    ccdFuncs.expList(explist, ccd=ccd,
                     feeControl=feeControl,
                     comment=comment,
                     title='bright flats')

def stdExposures_lowFlats(ccd=None, feeControl=None,
                          comment='low flats'):
    """ Canonical low flats sequence. 

    At 10 ADU/s, take flats running up to ~4000 ADU.
    """

    opticslab.setup(ccd.arm, flux=10)

    explist = (('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('dark', 100),
               
               ('flat', 112),
               ('flat', 1),
               ('flat', 2),
               ('flat', 3),
               ('flat', 5),
               ('flat', 7),

               ('flat', 112),
               ('flat', 10),
               ('flat', 14),
               ('flat', 20),
               ('flat', 28),
               ('flat', 40),

               ('flat', 112),
               ('flat', 56),
               ('flat', 80),
               ('flat', 112),
               ('flat', 224),
               
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('dark', 100))

    ccdFuncs.expList(explist, ccd=ccd,
                     feeControl=feeControl,
                     comment=comment,
                     title='low flats')

def stdExposures_Fe55(ccd=None, feeControl=None, comment='Fe55 sequence'):
    explist = []
    explist.append(('bias', 0),)

    for i in range(10):
        explist.extend(('dark', 1),
                       ('dark', 5),
                       ('dark', 10))
        
    for i in range(2):
        explist.extend(('dark', 30),
                       ('dark', 60))

    ccdFuncs.expList(explist, ccd=ccd,
                     feeControl=feeControl,
                     comment='Fe55 darks',
                     title='Fe55 darks')

def stdExposures_QE(ccd=None, feeControl=None,
                    comment='QE ramp', flatTime=5.0, slitWidth=1.0, waves=None):

    opticslab.setSlitwidth(slitWidth)

    if waves is None:
        waves = np.arange(550,1051,50)
    for wave in waves:
        opticslab.setWavelength(wave)

        time.sleep(1.0)
        ccdFuncs.wipe(ccd)

        ret = opticslab.pulseShutter(flatTime)
        print ret
        stime, flux, current, wave, slitWidth = ret
        
        cards = []
        cards.append(('HIERARCH QE.slitwidth', slitWidth, 'monochrometer slit width, mm'),)
        cards.append(('HIERARCH QE.wave', wave, 'monochrometer wavelength, nm'),)
        cards.append(('HIERARCH QE.flux', flux, 'calibrated flux, W'),)
        cards.append(('HIERARCH QE.current', current, 'Keithley current, A'),)

        expComment = "%s wave: %s" % (comment, wave)
        im, imfile = ccdFuncs.readout('flat', ccd=ccd,
                                      expTime=flatTime,
                                      feeControl=feeControl,
                                      extraCards=cards,
                                      comment=expComment)
        
def CTEStats(flist, bias, amps=None, useCols=None):
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
    biasexp = geom.Exposure(bias)
    for a_i in amps:
    
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
        elif useCols == 'b1':
            osCol = normedOsCols[:,0]
            ampCol = normedCols[:,-1]

            osRow = normedOsRows[2,:]
            ampRow = np.mean(normedOsRows[0:2,:], axis=0)
        else:
            osCol = normedOsCols[:,0]
            ampCol = normedCols[:,-1]
            osRow = normedOsRows[0,:]
            ampRow = normedRows[-1,:]

        colCTE = 1 - (np.mean(osCol*ampCol) / np.mean(ampCol*ampCol)) / ampImg.shape[1]
        rowCTE = 1 - (np.mean(osRow*ampRow) / np.mean(ampRow*ampRow)) / ampImg.shape[0]

        colCTEs.append(colCTE)
        rowCTEs.append(rowCTE)

        print("%d: %0.7f %0.7f  %7.2f %7.3f %7.2f %7.3f" %
              (a_i, colCTE, rowCTE,
               np.mean(ampCol), np.mean(osCol), np.mean(ampRow), np.mean(osRow)))

    return (colCTEs, rowCTEs,
            allNormedCols, allNormedOsCols,
            allNormedRows, allNormedOsRows,
            allBiasOsCols, allBiasOsRows)

statDtype = ([('amp', 'i2'),
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
              ('preamptemp', 'f4')])

def ampStats(ampIm, osIm, hdr=None, exptime=0.0, asBias=False):
    stats = np.zeros(shape=(1,),
                     dtype=statDtype)

    a_i = 0
    
    stats[a_i]['amp'] = a_i
    ampSig = np.median(ampIm)
    osSig = np.median(osIm)
    if osSig is np.nan:
        osSig = 0
    stats[a_i]['signal'] = signal = ampSig - osSig

    stats[a_i]['flux'] = signal / exptime
    stats[a_i]['exptime'] = exptime
    try:
        stats[a_i]['preamptemp'] = hdr['temps.PA']
        stats[a_i]['ccd0temp'] = hdr['temps.CCD0']
    except:
        pass
    stats[a_i]['sqrtSig'] = np.sqrt(signal)
    stats[a_i]['bias'] = osSig

    sig1 = 0.741 * np.subtract.reduce(np.percentile(ampIm, [75,25]))
    sig2 = 0.741 * np.subtract.reduce(np.percentile(osIm, [75,25]))
    _, trusig1, _ = geom.clippedStats(ampIm)
    _, trusig2, _ = geom.clippedStats(osIm)
    if asBias:
        stats[a_i]['readnoise'] = sig1
        stats[a_i]['readnoiseM'] = trusig1
    else:
        stats[a_i]['readnoise'] = sig2
        stats[a_i]['readnoiseM'] = trusig2

    stats[a_i]['shotnoise'] = sig = np.sqrt(np.abs(sig1**2 - sig2**2))
    stats[a_i]['shotnoiseM'] = trusig = np.sqrt(np.abs(trusig1**2 - trusig2**2))

    stats[a_i]['gain'] = gain = signal/sig**2
    stats[a_i]['gainM'] = signal/trusig**2
    stats[a_i]['noise'] = sig2*gain

    return stats

def ampDiffStats(ampIm1, ampIm2, osIm1, osIm2, exptime=0.0):
    stats = np.zeros(shape=(1,),
                     dtype=statDtype)

    a_i = 0
    _s1 = np.median(ampIm1) - np.median(osIm1)
    _s2 = np.median(ampIm2) - np.median(osIm2)
    stats[a_i]['signal'] = signal = (_s1+_s2)/2
    stats[a_i]['sqrtSig'] = np.sqrt(signal)
    stats[a_i]['bias'] = (np.median(osIm1) + np.median(osIm2))/2

    ampIm = ampIm2.astype('f4') - ampIm1
    osIm = osIm2.astype('f4') - osIm1

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
    stats[a_i]['flux'] = signal / exptime if exptime != 0 else 0.0

    return stats, ampIm, osIm

def imStats(im, asBias=False):

    exp = geom.Exposure(im)
    
    ampIms, osIms, _ = exp.splitImage(doTrim=True)

    stats = []

    for a_i in range(8):
        stats1 = ampStats(ampIms[a_i], osIms[a_i], exp.header,
                          exptime=exp.header['EXPTIME'],
                          asBias=asBias)
        stats1['amp'] = a_i
        stats.append(stats1)

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

    stats = []
    diffAmpIms = []
    diffOsIms = []
    for a_i in range(8):
        stats1, ampIm1, osIm1 = ampDiffStats(f1AmpIms[a_i], f2AmpIms[a_i],
                                             f1OsIms[a_i], f2OsIms[a_i],
                                             exptime=exp1.expTime)
        stats1['amp'] = a_i
        stats.append(stats1)
        diffAmpIms.append(ampIm1)
        diffOsIms.append(osIm1)
        
    return diffAmpIms, diffOsIms, stats

def printStats(stats):

    po = np.get_printoptions()
    np.set_printoptions(formatter=dict(float=lambda f: "%0.2f" % (f)))
    
    print("amp readnoise readnoiseM  gain  gainM    signal    bias sig^0.5 shotnoise shotnoiseM noise(e-) dn/s\n")

    for i in range(len(stats)):
        print( "%(amp)d   %(readnoise)9.2f %(readnoiseM)9.2f %(gain)6.2f %(gainM)6.2f %(signal)9.2f %(bias)7.2f %(sqrtSig)7.2f %(shotnoise)9.2f %(shotnoiseM)9.2f %(noise)10.2f %(flux)5.1f" % stats[i])

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
    
