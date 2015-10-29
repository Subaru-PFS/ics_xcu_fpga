import logging
import time
import numpy as np
import matplotlib.pyplot as plt

import ccdFuncs

def normed(arr):
    """ Return an array with its mean value subtracted. Not robust. """
    return arr - np.median(arr)

def plotRows(im, prows, imName='', figName=None, figWidth=10, pixRange=None):
    medpix = np.median(im[prows])

    f1 = plt.figure(figsize=(figWidth,figWidth/4))
    for prow in prows:
        plt.plot(im[prow], scaley=pixRange is None)
        if pixRange is not None:
            plt.axis([None, None, medpix-pixRange, medpix+pixRange])
    plt.title('%s rows %s, all amps, clipped to %0.2f +/- %s' % (imName, prows, medpix, pixRange))
    plt.show()

def plotAmps(im, row=None, cols=None, amps=None, plotOffset=100, fig=None, figWidth=None, 
             peaks=None, clipPeaks=True):

    """ In one figure, plot one row (middle) of the specified amps (all). Limit to range of cols if desired. 
    
    The per-amp plots are offset by their mean value, and plotted plotOffset pixels apart.

    Parameters
    ----------
    im - 2d array
        The image to plot from
    row - int 
        The row to plot from. (default is the middle row of the image)
    cols - 1d array-like
        The columns to plot. (default is the full width of the amps)
    amps - 1d array-like
        The amps to plot. (default is all)
    plotOffset - int
        The y offset between plots. (default is 50, should be from data)
    """

    namps = 8
    imcols = im.shape[1]/namps
    if amps is None: 
        amps = range(namps)
    if row is None:
        row = im.shape[0]/2
    if cols is None:
        cols = np.arange(imcols)

    if fig is None:
        fig = plt.figure()
    if figWidth is not None:
        fig.set_figwidth(figWidth)

    yoff = 0
    for a in amps:
        normedIm = normed(im[:, cols + a*imcols])
        seg = normedIm[row]
        plt.plot(cols, seg+yoff, '-+')

        if peaks is not None:
            for ii in range(-3,4):
                print "%d: %s" % (ii, np.round(np.mean(normedIm[:, peaks+ii]), 3))

        print 
        yoff += plotOffset

    plt.axis([None, None, -plotOffset, yoff+plotOffset])

    plt.title('row %d, amps: %s, cols [%d,%d]' % (row, amps, 
                                                  cols[0],cols[-1]))

def rawAmpGrid(im, ccd, cols=None, rows=None, 
               showFfts=False,
               fig=None, figWidth=None):
    if fig is None:
        fig = plt.figure('amp_hists', figsize=(figWidth, figWidth*2), tight_layout=True)
    fig.clf()

    #if figWidth is not None:
    #    fig.set_figwidth(figWidth*2)

    if cols is None:
        cols = slice(0,-1)
    if rows is None:
        rows = slice(0,-1)

    fig.subplots_adjust(hspace=0.1, wspace=0.05)
    if showFfts:
        r = 8
        c = 2
    else:
        r = 4
        c = 2
        
    for a in range(8):
        ampIm = im[rows, ccd.ampidx(a, im)[cols]]

        if showFfts:
            p = fig.add_subplot(r, c, 2*a + 1)
        else:
            p = fig.add_subplot(r, c, a + 1)

        p.xaxis.set_visible(False)
        p.yaxis.set_visible(False)
        nAmpIm = ampIm - np.median(ampIm)
        ai_std = np.std(nAmpIm)
        pp = p.imshow(nAmpIm, aspect='equal')
        pp.set_clim(-3*ai_std, 3*ai_std)
        plt.title('amp %d dev=%0.2f' % (a, ampIm.std()))

        if showFfts:
            p = fig.add_subplot(r, c, 2*a + 2)
            p.xaxis.set_visible(False)
            p.yaxis.set_visible(False)
            
            normArr = ampIm - ampIm.mean()
            yhat = np.log10(np.absolute(np.fft.fft(normArr)))
            yh_mean = np.mean(yhat)
            yh_std = np.std(yhat)
            fp = p.imshow(yhat, aspect='equal')
            fp.set_clim(yh_mean-3*yh_std, yh_mean+3*yh_std)
            plt.title('amp %d fft' % (a))

    return fig

def ampHistGrid(im, ccd, cols=None, rows=None, fig=None, histRange=10, figWidth=None):
    if fig is None:
        fig = plt.figure('amp_images')
    fig.clf()
    if figWidth is not None:
        fig.set_figwidth(figWidth)

    if cols is None:
        cols = slice(0,-1)
    if rows is None:
        rows = slice(0,-1)

    #fig.subplots_adjust(hspace=0.1, wspace=0.01)
    r = 2
    c = 4
    hists = []
    means, devs = ampStats(im, ccd=ccd, rows=rows, cols=cols)
    for a in range(8):
        ampIm = im[rows, ccd.ampidx(a, im)[cols]].flatten()
        #ampIm -= np.round(np.mean(ampIm))
        ampIm -= np.median(ampIm)
        p = fig.add_subplot(r, c, a+1)
        #p.xaxis.set_visible(False)
        p.yaxis.set_visible(False)

        ph = p.hist(ampIm, bins=np.arange(histRange)-(histRange/2.0 - 0.5), normed=False)

        p.annotate("s=%0.2f" % (devs[a]), xy=(0.65, 0.85), xycoords="axes fraction")
        p.annotate("amp %d,%d" % (a/4, a%4), xy=(0.05, 0.85), xycoords="axes fraction")
        hists.append(ph)
        #plt.title('amp %d dev=%0.2f' % (a, ampIm.std()))

    return fig, hists

# Routines to set the mean amp levels to some handy level.
# tuneLevels() does all amps, to about 10k.

def ampStats(im, cols=None, rows=None, ccd=None):
    if cols is None:
        cols = np.arange(im.shape[1]/ccd.namps)
    if rows is None:
        rows = np.arange(im.shape[0])
        
    rowim = im[rows]
    means = []
    devs = []
    for a in np.arange(8):
        ampCols = ccd.ampidx(a, im=im)[cols]
        means.append(rowim[:, ampCols].mean())
        devs.append(rowim[:, ampCols].std())

    return np.array(means), np.array(devs)

def fmtArr(a, format='%0.4f'):
    return "[" + " ".join([format % i for i in a]) + "]"

def tuneLevels(ccd, fee, amps=None, 
               statCols=None, levels=1000, useGains=None, sigTol=3, 
               maxLoops=10, adjOffset=10, nrows=100, 
               startOffset=None, startStep=10,
               sleepTime=0.5, clockFunc=None,legs='n',
               doZero=True, doUnwrap=65000):
    nAllAmps = 8
    
    if amps is None:
        amps = range(nAllAmps)
    if isinstance(amps, int):
        amps = [amps]

    namps = len(amps)
    if isinstance(levels, (int, float)):
        levels = np.zeros(nAllAmps, dtype='f4') + levels

    if isinstance(startStep, (int, float)):
        startStep = np.zeros(nAllAmps, dtype='f4') + startStep

    if startOffset is None:
        startOffset = startStep.copy()
    elif isinstance(startOffset, (int, float)):
        startOffset = np.zeros(nAllAmps, dtype='f4') + startOffset

    if useGains is None:
        gains = np.zeros(nAllAmps)
    else:
        gains = useGains 

    if doUnwrap is True:
        doUnwrap = 65000

    levels[np.arange(namps)%2 == 0] += adjOffset
    levels[np.arange(namps)%2 == 1] -= adjOffset

    # We cannot yet read bias levels, so zero them first
    offsets = np.zeros(nAllAmps)
    offsets[amps] = startOffset.copy()
    if doZero:
        fee.zeroOffsets(amps)
    if 'n' in legs:
        fee.setOffsets(amps, offsets[amps], leg='n')
    if 'p' in legs:
        fee.setOffsets(amps, -offsets[amps], leg='p')
    time.sleep(sleepTime)

    done = np.ones(nAllAmps, dtype='i1')
    done[amps] = False
    lastLevels = np.zeros(nAllAmps, dtype='f4')

    ii = 0
    argDict = dict(everyNRows=None, ampList=amps, ccd=ccd)

    # Clear any accumulated charge
    toss = ccd.readImage(nrows=nrows, rowFunc=ccdFuncs.rowStats, rowFuncArgs=argDict, doSave=False,
                         clockFunc=clockFunc)

    lastOffset = offsets * 0
    offLimit = 199
    print
    print "amps: %s" % (amps)
    print
    while True:
        im, files = ccd.readImage(nrows=nrows, rowFunc=ccdFuncs.rowStats, rowFuncArgs=argDict, 
                                  doSave=False, clockFunc=clockFunc)

        if doUnwrap:
            im = im.astype('i4')
            hi = im > doUnwrap
            if hi.sum() > 0:
                print "!!!! unwrapping %d pixels !!!!" % (hi.sum())
                im[hi] -= 65535

        newLevels, devs = ampStats(im, cols=statCols, ccd=ccd)
        print "====== read %d" % (ii)
        print "offs (%d): %s" % (ii, fmtArr(offsets[amps]))
        print "means(%d): %s" % (ii, fmtArr(newLevels))
        print "devs (%d): %s" % (ii, fmtArr(devs))
        print "done(%d of %d)   : %s" % (ii, maxLoops, done)

        if np.all(done) or ii > maxLoops:
            break 

        thisOffset = offsets * 0
        for a_i in range(len(amps)):
            a = amps[a_i]
            mean = newLevels[a]
            last = lastLevels[a]
            stddev = devs[a]

            if mean == 0 or mean > doUnwrap:
                # We are not in range yet. Keep adding the starting step.
                # print "%d %d: out of range: %0.2f" % (ii, a, mean)
                thisOffset[a] = startStep[a]
                
            # Close enough? Stop.
            elif np.fabs(levels[a]-mean) < sigTol*stddev:
                done[a_i] = True
                continue
                    
            elif last <= 0 and useGains is None:
                # We don't have two levels yet. Bump and remeasure.
                # print "%d %d: have one, need two" % (ii, a)
                thisOffset[a] = startStep[a]
                lastLevels[a] = mean
            else:
                if useGains is None:
                    # Have two levels. 
                    dLevel = mean - last

                    # Remeasure gain and apply.
                    dOffset = lastOffset[a]
                    if dOffset != 0.0:
                        gains[a] = dLevel/dOffset

                # print "%d,%d: dLevel/dOffset=gain %g/%g = %g vs. %s" % (a_i, a, dLevel, dOffset, lastGain, gains[a])
                    
                stillWant = levels[a]-mean
                thisOffset[a] = stillWant/gains[a]
                if np.fabs(thisOffset[a] + offsets[a]) >= offLimit:
                    thisOffset[a] = startStep[a]
                lastLevels[a] = mean  
                # print("%d,%d level,mean,want,offset,doffset %g %g %g %g %g" % 
                #       (a_i, a, levels[a], mean, stillWant, thisOffset[a], dOffset))

        offsets += thisOffset
        if np.any(np.fabs(offsets) >= offLimit):
            print("!!!!!!!! WARNING: railed offsets !!!!!!!: %s" % (np.fabs(offsets) >= offLimit))
            offsets[offsets < -offLimit] = -offLimit
            offsets[offsets > offLimit] = offLimit
            # done[offsets >= offLimit] = True
            # done[offsets <= -offLimit] = True
            
        print 
        print "offs!(%d): %s" % (ii, fmtArr(offsets[amps]))
        print "doffs(%d): %s" % (ii, fmtArr(thisOffset[amps]))
        print "gains(%d): %s" % (ii, fmtArr(gains[amps]))
        print
        
        ii += 1
        
        lastOffset = thisOffset.copy()
        # lastLevels = newLevels
        if 'n' in legs:
            fee.setOffsets(amps, offsets[amps], leg='n')
        if 'p' in legs:
            fee.setOffsets(amps, -offsets[amps], leg='p')
        time.sleep(sleepTime)
        
    return offsets, devs, gains

def gainCurve(ccd, fee, amps=None, 
              statCols=None, nrows=200, 
              doUnwrap=False, leg='n', clockFunc=None,
              stepSize=19.9*2, offLimit=199, sleepTime=0.1):
    
    if amps is None:
        amps = np.arange(namps)
    if isinstance(amps, int):
        amps = np.zeros(8, dtype='i2') + amps

    namps = len(amps)

    offsets = []
    levels = []

    argDict = dict(everyNRows=100, ampList=amps, ccd=ccd)

    # We cannot yet read bias levels, so zero them first
    fee.zeroOffsets(amps)
    time.sleep(sleepTime)
    
    # Clear any accumulated charge
    toss = ccd.readImage(nrows=nrows, rowFunc=ccdFuncs.rowStats, rowFuncArgs=argDict, doSave=False,
                         clockFunc=clockFunc)

    offset = 0.0
    while np.fabs(offset) <= offLimit:
        offsets.append(offset)
        fee.setOffsets(amps, [offset]*namps, leg=leg)
        time.sleep(sleepTime)

        im, files = ccd.readImage(nrows=nrows, rowFunc=ccdFuncs.rowStats, rowFuncArgs=argDict, doSave=False,
                                  clockFunc=clockFunc)
        if doUnwrap is not False:
            im = im.astype('i4')
            hi_w = im > doUnwrap
            if hi_w.sum() > 0:
                print "!!!! unwraping %d pixels !!!!" % (hi_w.sum())
                im[hi_w] -= 65535

        newLevels, devs = ampStats(im, statCols, ccd=ccd)
        print "means(%0.3f): %s" % (offset, fmtArr(newLevels))
        print "devs (%0.3f): %s" % (offset, fmtArr(devs))
        print

        levels.append(newLevels.copy())
        offset += stepSize
        
    return offsets, levels
        

def plotGains(offsets, levels, amps=None):
    offs = offsets[1:]
    la = np.array(levels[1:])
    fig = plt.figure()
    p1 = fig.add_subplot(121)
    p2 = fig.add_subplot(122)
    
    if amps is None:
        amps = range(len(offsets))

    fitgains = []
    for a in amps:
        fit = np.polyfit(offs, la[:,a], 1)
        ev = np.polyval(fit, offs)
        p1.plot(offs, la[:,a], '+-')
        p2.plot(offs, la[:,a]-ev, '+-')
        print "%d: %s" % (a, fit)
        fitgains.append(fit)
    
    return np.array(fitgains)
