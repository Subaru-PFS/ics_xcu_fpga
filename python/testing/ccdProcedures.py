from importlib import reload

import numpy as np
import time

import fpga.geom as geom

import fpga.ccdFuncs as ccdFuncs
import fpga.opticslab as opticslab
from testing.logbook import storeExposures
from testing.scopeProcedures import calcOffsets1

reload(geom)
reload(ccdFuncs)
reload(opticslab)

def stdExposures_biases(ccd=None,
                        nbias=21,
                        feeControl=None,
                        comment='biases'):

    files = ccdFuncs.expSequence(ccd=ccd,
                                 nbias=nbias,
                                 feeControl=feeControl,
                                 comment=comment,
                                 title='%d biases' % (nbias))
    
    storeExposures("std_exposures_biases", files, comments=comment)
    return files

def stdExposures_darks(ccd=None,
                       nbias=2, ndarks=21, darkTime=150,
                       feeControl=None,
                       comment='darks'):

    files = ccdFuncs.expSequence(ccd=ccd,
                                 nbias=nbias,
                                 darks=[darkTime]*ndarks,
                                 feeControl=feeControl,
                                 comment=comment,
                                 title='%d %gs darks' % (ndarks, darkTime))
    
    storeExposures("std_exposures_darks", files, comments=comment)
    return files

def stdExposures_base(ccd=None, feeControl=None, comment=None):

    files = stdExposures_biases(ccd=ccd, feeControl=feeControl, comment=comment)
    files += stdExposures_darks(ccd=ccd, feeControl=feeControl, comment=comment)
    
    storeExposures("std_exposures_base", files, comments=comment)
    return files
    
    
def stdExposures_hours(ccd=None, feeControl=None, hours=4, comment=None):
    darkTime = 900
    files = []
    for i in range(hours):
        files += ccdFuncs.expSequence(ccd=ccd,
                                      biases=5,
                                      darks=[900]*4,
                                      feeControl=feeControl,
                                      comment=comment,
                                      title='1 hour %fs dark loop' % (darkTime))
        
    storeExposures("std_exposures_hours", files, comments=comment)
    return files
        
    
def calcOffsets(target, current):
    m = np.round((target - current)/30, 2)
    r = np.round(m * 40.0/57.0, 2)

    return m, r

                
                
def tuneOffsets(ccd=None, feeControl=None):
    amps = list(range(8))
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

    files = ccdFuncs.expSequence(ccd=ccd,
                                 nrows=nrows, ncols=ncols,
                                 nbias=3,
                                 feeControl=feeControl,
                                 comment=comment,
                                 title='pre-VOD/VOG tuning biases')

    storeExposures("std_exposures_biases", files, 'pre-VOD/VOG tuning biases')

    files = []
    for vod in VOD:
        for vog in VOG:
            tweaks = ccdFuncs.FeeTweaks(feeControl)
            tweaks.tweakMode('read', OD=vod, OG=vog)

            files1 = ccdFuncs.expSequence(ccd=ccd,
                                          nrows=nrows, ncols=ncols,
                                          nbias=1,
                                          flats=[4],
                                          feeControl=tweaks,
                                          comment=comment,
                                          title='VOD/VOG tuning (%0.1f, %0.1f)' % (vod, vog))
            files.extend(files1)

    storeExposures("std_exposures_vod_vog", files)
    return files

def stdExposures_brightFlats(ccd=None, feeControl=None, comment='bright flats'):
    """ Canonical bright flats sequence. 

    At 1000ADU/s, take flats running up past saturation.
    """
    files = []
    opticslab.setup(ccd.arm, flux=1000)

    explist = (('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('dark', 100),
               
               ('flat', 30),
               ('flat', 30),
               ('flat', 1),
               ('flat', 1),
               ('flat', 2),
               ('flat', 2),
               ('flat', 3),
               ('flat', 3),               
               ('flat', 4),
               ('flat', 4),
               ('flat', 5),
               ('flat', 5),
               
               ('flat', 30),                              
               ('flat', 30),
               ('flat', 6),
               ('flat', 6),
               ('flat', 7),
               ('flat', 7),
               ('flat', 8),
               ('flat', 8),               
               ('flat', 9),
               ('flat', 9),               
               ('flat', 10),
               ('flat', 10),
 
               ('flat', 30),              
               ('flat', 30),
               ('flat', 12),
               ('flat', 12),               
               ('flat', 14),
               ('flat', 14),
               ('flat', 20),
               ('flat', 20),               
               ('flat', 28),
               ('flat', 28),
               ('flat', 32),
               ('flat', 32),
               
               ('flat', 30),              
               ('flat', 30),
               ('flat', 36),
               ('flat', 36),               
               ('flat', 40),
               ('flat', 40),
               ('flat', 44),
               ('flat', 44),               
               ('flat', 48),
               ('flat', 48),
               ('flat', 52),
               ('flat', 52),              
               
               ('flat', 30),              
               ('flat', 30),
               ('flat', 55),
               ('flat', 55),               
               ('flat', 57),
               ('flat', 57),
               ('flat', 62),
               ('flat', 62),               
               ('flat', 65),
               ('flat', 65),
               ('flat', 67),
               ('flat', 67),               
               
               
               ('flat', 30),               
               ('flat', 30),
               ('flat', 50),
               ('flat', 50),
               ('flat', 60),
               ('flat', 60),               
               ('flat', 70),
               ('flat', 70),               
               ('flat', 71),
               ('flat', 71),               
               ('flat', 73),
               ('flat', 73),
               
               ('flat', 30),               
               ('flat', 30),               
               ('flat', 75),
               ('flat', 75),               
               ('flat', 77),
               ('flat', 77),               
               ('flat', 78),
               ('flat', 78),               
               ('flat', 79),
               ('flat', 79),  
               ('flat', 80),
               ('flat', 80),                
               
               ('flat', 30),               
               ('flat', 30),
               ('flat', 72),
               ('flat', 72),
               ('flat', 74),
               ('flat', 74),
               ('flat', 76),
               ('flat', 76),
               ('flat', 85),
               ('flat', 85),
               ('flat', 90),
               ('flat', 90),               

               ('bias', 0),
               ('flat', 100),
               ('bias', 0),
               ('flat', 200),
               ('bias', 0),
               ('flat', 400),
               ('bias', 0),
               
               ('flat', 30),
               ('flat', 30),      
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('dark', 100))

    files = ccdFuncs.expList(explist, ccd=ccd,
                             feeControl=feeControl,
                             comment=comment,
                             title='bright flats')
    
    storeExposures("std_exposures_bright_flats", files, comments=comment)
    return files
    
    

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
               ('flat', 112),
               ('flat', 1),
               ('flat', 1),
               ('flat', 2),
               ('flat', 2),
               ('flat', 3),
               ('flat', 3),
               ('flat', 5),
               ('flat', 5),
               ('flat', 7),
               ('flat', 7),

               ('flat', 112),
               ('flat', 112),
               ('flat', 8),
               ('flat', 8),
               ('flat', 10),
               ('flat', 10),
               ('flat', 14),
               ('flat', 14),               
               ('flat', 20),
               ('flat', 20),               
               ('flat', 28),
               ('flat', 28),
               ('flat', 40),
               ('flat', 40),

               ('flat', 112),
               ('flat', 112),
               ('flat', 45),
               ('flat', 45),               
               ('flat', 56),
               ('flat', 56),
               ('flat', 80),
               ('flat', 80),               
               ('flat', 112),
               ('flat', 112),               
               ('flat', 160),
               ('flat', 160),               
               ('flat', 224),
               ('flat', 224),               
               ('flat', 320),
               ('flat', 320),               
               ('flat', 450),
               ('flat', 450),
               ('flat', 112),
               ('flat', 112),
               ('flat', 600),
               ('flat', 600),
               ('flat', 112),
               ('flat', 112),
               ('flat', 800),
               ('flat', 800),
               ('flat', 112),
               ('flat', 112),
               ('flat', 1000),
               ('flat', 1000),
               ('flat', 112),
               ('flat', 112),
               ('flat', 1200),
               ('flat', 1200),
               ('flat', 112),
               ('flat', 112),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('dark', 100))
               
    files = ccdFuncs.expList(explist, ccd=ccd,
                             feeControl=feeControl,
                             comment=comment,
                             title='low flats')
    
    storeExposures("std_exposures_low_flats", files, comments=comment)
    return files
    
    
def stdExposures_masterFlats(ccd=None, feeControl=None, nflats=21, exptime=10, flux=1000, comment='master flats'):
    """ Canonical bright flats sequence. 

    At 1000ADU/s, take flats running up past saturation.
    """
    if flux is not None:
        opticslab.setup(ccd.arm, flux=flux)

    flatlist = nflats * [('flat', exptime)]
    head = tail = 5 * [('bias', 0)] + [('dark', 100)]
    explist = head + flatlist + tail

    files = ccdFuncs.expList(explist, ccd=ccd,
                             feeControl=feeControl,
                             comment=comment,
                             title='master flats')
    
    storeExposures("std_exposures_master_flats", files, comments=comment)
    return files

def stdExposures_Fe55(ccd=None, feeControl=None, comment='Fe55 sequence'):
    """ Take standard set of Fe55 exposures.

    The Fe55 source illuminates a pretty narrow area, so we move the arm
    to three positions. At each position we take 10 30s and 10 60s exposures.

    In practice, the calling routine would run this many times.
    """
    files = []
    explist = []
    explist.append(('bias', 0),)
    for i in range(10):
        explist.append(('dark', 30),)
    for i in range(10):
        explist.append(('dark', 60),)

    opticslab.setPower('off')
    
    for pos in 45,53,61,69:
        opticslab.setFe55(pos)
        
        files += ccdFuncs.expList(explist, ccd=ccd,
                                  feeControl=feeControl,
                                  comment='Fe55 dark %s'%str(pos),
                                  title='Fe55 darks')
    
    storeExposures("std_exposures_fe55", files, comments=comment)
    return files

def stdExposures_QE(ccd=None, feeControl=None,
                    comment='QE ramp', waves=None, duplicate=1, flatTime=10, exptimes=None):
    """ Take standard QE test exposures.

    Currently taking 50m steps across the detector bandpass, with 
    10s exposures at ~1000 ADU/s
    """
    files = []
    opticslab.setup(ccd.arm, flux=1000)

    if waves is None:
        if ccd.arm == 'red':
            waves = np.arange(600,1051,50)
        elif ccd.arm == 'blue':
            waves = np.arange(350,701,50)
        else:
            raise RuntimeError('QE test only knows about red and blue detectors.')
            
    exptimes = [flatTime for wave in waves] if exptimes is None else exptimes
    
    for wave,flatTime in zip(waves, exptimes):
        wave = int(round(wave))
        opticslab.setWavelength(wave)
        
        for i in range(duplicate):
            time.sleep(2.0)
            ccdFuncs.wipe(ccd)

            ret = opticslab.pulseShutter(flatTime)
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
            files.append(imfile)
        
    storeExposures("std_exposures_qe", files, comments=comment)
    return files
    
    
def CTEStats(flist, bias, amps=None, useCols=None):
    '''
    The algorithm is

    for either one flat or, better, a series of nominally identical flats prepared thus:

    adjust by adding a constant so that the median or mean OVERSCAN levels are the same

    median the frames pixel-by pixel and subtract a medianed bias, prepared the same way, and 
    also adjusted additively so that the median of the overscan area is the same as the frame--thus 
    the median of the overscan extents in the corrected frame is zero.

    let Ib be the median of the last illuminated row (for parallel CTE) or column (for serial), 
    (the last with level ~like the rest of the illuminated area.

    let Ic1 be the median of the next row or column, and Ic2 the median of
    the one after that, Ic3 the one after that, .... Let Ic be the sum of
    the first few (3?) of these

    Then if Ic1 << Ib, the CTE is

    1 - (Ic/Ib)/Npix

    Where Npix is the number of transfers to get to the edge you are
    investigating--512 for the serial CTE and 4xxx for the parallel.
    If Ic is not much less than Ib, the CTE is awful and it does not matter what you do.

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

    print()
    print("#amp    HCTE      VCTE   ampCol overCol  ampRow overRow")

    if amps is None:
        amps = list(range(exp.namps))
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
            colCTE = 1 - (normedOsCols[:,:3].sum()/normedCols[:,-1].sum())/ampImg.shape[1]
            rowCTE = 1 - (normedOsRows[:3,:].sum()/normedRows[-1,:].sum())/ampImg.shape[0]
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

        colCTE = 1 - (np.mean(osCol*ampCol)/np.mean(ampCol*ampCol))/ampImg.shape[1]
        rowCTE = 1 - (np.mean(osRow*ampRow)/np.mean(ampRow*ampRow))/ampImg.shape[0]

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
              ('npix', 'i4'),
              ('adus', 'f4'),
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

def areaStats(ampIm, osIm, exptime, ampNum=-1,
              hdr=None, asBias=False):
    
    stats = np.zeros(shape=(1,),
                     dtype=statDtype)
    a_i = 0

    stats[a_i]['amp'] = ampNum
    stats[a_i]['npix'] = ampIm.size

    ampSig = np.median(ampIm)
    osSig = np.median(osIm)
    if osSig is np.nan:
        osSig = 0
    stats[a_i]['adus'] = ampSig
    stats[a_i]['signal'] = signal = ampSig - osSig

    stats[a_i]['flux'] = signal/exptime
    stats[a_i]['exptime'] = exptime
    if hdr is not None:
        stats[a_i]['preamptemp'] = hdr['temps.PA']
        stats[a_i]['ccd0temp'] = hdr['temps.CCD0']

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

def ampStats(ampIm, osIm, hdr=None, exptime=0.0, asBias=False):

    stats = areaStats(ampIm, osIm, exptime, hdr=hdr, asBias=asBias)

    return stats

def ampDiffStats(ampIm1, ampIm2, osIm1, osIm2, exptime=0.0):
    stats = np.zeros(shape=(1,),
                     dtype=statDtype)

    a_i = 0
    _s1 = np.median(ampIm1) - np.median(osIm1)
    _s2 = np.median(ampIm2) - np.median(osIm2)
    stats[a_i]['signal'] = signal = (_s1 + _s2)/2
    stats[a_i]['npix'] = ampIm1.size
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
    stats[a_i]['flux'] = signal/exptime if exptime != 0 else 0.0

    return stats, ampIm, osIm

def imStats(im, asBias=False,
            rowTrim=(5,5), colTrim=(5,5),
            osColTrim=(3,1)):

    exp = geom.Exposure(im)
    expTime = exp.expTime
    
    ampIms, osIms, _ = exp.splitImage()

    stats = []

    ampRows = slice(rowTrim[0], None if rowTrim[-1] in {0,None} else -rowTrim[1])
    ampCols = slice(colTrim[0], None if colTrim[-1] in {0,None} else -colTrim[1])

    osRows = ampRows
    osCols = slice(osColTrim[0], None if osColTrim[-1] in {0,None} else -osColTrim[1])

    for a_i in range(8):
        stats1 = ampStats(ampIms[a_i][ampRows,ampCols], osIms[a_i][osRows,osCols], exp.header,
                          exptime=exp.header['EXPTIME'],
                          asBias=asBias)
        stats1['amp'] = a_i
        stats.append(stats1)

    return expTime, ampIms, osIms, stats

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
    
    print("amp readnoise readnoiseM  gain  gainM      adus    signal     bias sig^0.5 shotnoise shotnoiseM noise(e-)   dn/s\n")

    for i in range(len(stats)):
        print( "%(amp)d   %(readnoise)9.2f %(readnoiseM)9.2f %(gain)6.2f %(gainM)6.2f %(adus)9.2f %(signal)9.2f %(bias)8.2f %(sqrtSig)7.2f %(shotnoise)9.2f %(shotnoiseM)9.2f %(noise)10.2f %(flux)7.1f" % stats[i])

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
    
