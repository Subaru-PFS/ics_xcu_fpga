from __future__ import absolute_import

import logging
import time
import sys
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from fpga import ccd as ccdMod
from fee import feeControl as feeMod

from fpga import ccdFuncs
reload(ccdFuncs)

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
    fig.show()
    
    return fig

def rawAmpGrid(im, ccd, amps=None,
               title=None,
               cols=None, rows=None, 
               noiseLim=0.8,
               expectedLevels=None,
               fig=None, figSize=None):
    
    if amps is None:
        amps = range(8)
        
    if cols is None:
        cols = slice(0,-1)
    if rows is None:
        rows = slice(0,-1)

    figRows = 5
    figCols = 5
    
    if fig is None:
        figsize = (8, 11) if figSize is None else figSize
        fig = plt.figure(figsize=figsize)
        gs = gridspec.GridSpec(nrows=figRows, ncols=figCols,
                               top=0.9, bottom=0.05, left=0.05, right=0.9,
                               height_ratios=[1.0,1.0, 0.05, 1.0,1.0],
                               width_ratios=[1.0,1.0,1.0,1.0, 0.1],
                               wspace=0, hspace=0.25)

    ai_std = None
    bestAmp = None
    for a_i, a in enumerate(amps):
        ampCols = ccd.ampidx(a, im)[cols]
        ampIm = im[rows][:, ampCols]
        nAmpIm = ampIm - np.trunc(np.median(ampIm))

        newBest = False
        ai_std1 = np.std(nAmpIm)
        if ai_std is None:
            if ai_std1 > 0:
                ai_std = ai_std1
                bestAmp = a
                newBest = True
        else:        
            if ai_std1 > 0 and ai_std1 < ai_std:
                ai_std = ai_std1
                bestAmp = a
                newBest = True
        if newBest:
            normArr = ampIm - ampIm.mean()
            bestYhat = np.log10(np.absolute(np.fft.fft(normArr)))

    pixRange = np.trunc(2*ai_std)+1
    dataNorm = mpl.colors.Normalize(vmin=-pixRange,
                                    vmax=pixRange,
                                    clip=True)
    
    for a_i, a in enumerate(amps):
        ampCols = ccd.ampidx(a, im)[cols]
        ampIm = im[rows][:, ampCols]

        row = a_i // 4
        col = a_i % 4
        im_gs = gs[row, col]
        im_p = fig.add_subplot(im_gs)
        im_p.set_xticks([])
        im_p.set_yticks([])
        im_p.xaxis.set_visible(False)
        im_p.yaxis.set_visible(False)
        ai_med1 = np.trunc(np.median(ampIm))
        nAmpIm = ampIm - ai_med1

        im_pp = im_p.imshow(nAmpIm, aspect='equal',
                            norm=dataNorm, interpolation='none')
        # lo_w = np.where(nAmpIm < -pixRange)
        # hi_w = np.where(nAmpIm > pixRange)
        # im_p.plot(lo_w[1], lo_w[0], 'b,', alpha=0.3)
        offscale_w = np.where((nAmpIm < -pixRange) | (nAmpIm > pixRange))
        im_p.plot(offscale_w[1], offscale_w[0], 'r,', alpha=0.3)
        
        if col == 0:
            im_p.text(0, 0.5, 'CCD %d' % (row),
                      size=12,
                      horizontalalignment='right',
                      verticalalignment='center',
                      rotation='vertical',
                      transform=im_p.transAxes)

        if row == 0:
            im_p.set_title('Amp %d' % (col), fontsize=12)

        if row in (0,1) and col == figCols-2:
            cax = fig.add_subplot(gs[row,figCols-1])
            fig.colorbar(im_pp, cax=cax, ticks=[-pixRange,0,pixRange])
            cax.set_yticklabels([str(-pixRange),'0',str(pixRange)])
            
        ai_std1 = np.std(nAmpIm)
        im_p.text(0.99, -0.05, 'sig=%0.2f' % (ai_std1),
                  color=('black' if ai_std1 <= noiseLim else 'red'),
                  weight='bold',
                  horizontalalignment='right',
                  verticalalignment='top',
                  transform=im_p.transAxes)

        if expectedLevels is not None:
            inspec = np.abs(ai_med1 - expectedLevels[a_i]) <= 0.05*expectedLevels[a_i]
            color = 'black' if inspec else 'red'
        else:
            color = 'black'
            
        im_p.text(0.02, -0.05, 'med=%d' % (ai_med1),
                  color=color,
                  weight='bold',
                  horizontalalignment='left',
                  verticalalignment='top',
                  transform=im_p.transAxes)

        fftRow = row + 3
        fft_gs = gs[fftRow, col]
        fft_p = fig.add_subplot(fft_gs)
        fft_p.xaxis.set_visible(False)
        fft_p.yaxis.set_visible(False)

        normArr = ampIm - ampIm.mean()
        yhat = np.log10(np.absolute(np.fft.fft(normArr)))
        if a_i == 0:
            fft_mean = np.mean(bestYhat)
            fft_pixRange = 3*np.std(bestYhat)
            fftNorm = mpl.colors.Normalize(vmin=fft_mean - fft_pixRange,
                                           vmax=fft_mean + fft_pixRange,
                                           clip=True)
        fp = fft_p.imshow(yhat, aspect='equal',
                          norm=fftNorm, interpolation='none')

        if col == 0:
            fft_p.text(0, 0.5, 'CCD %d' % (row),
                       size='large',
                       horizontalalignment='right',
                       verticalalignment='center',
                       rotation='vertical',
                       transform=fft_p.transAxes)
            
        if row == 0:
            fft_p.set_title('Amp %d' % (col))

    if title is not None:
        fig.suptitle(title, fontsize=14, fontweight='bold')
        
    fig.show()
    
    return fig, gs

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
        ampIm -= np.int(np.round(np.median(ampIm)))
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

def gainCurve(ccd=None, fee=None, amps=None, 
              statCols=None, nrows=200, 
              doUnwrap=False, leg='n', clockFunc=None,
              stepSize=19.9*2, offLimit=199, sleepTime=0.1):

    if amps is None:
        amps = np.arange(8)
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
    ccdFuncs.wipe(ccd=ccd, feeControl=fee)
    
    offset = 0.0
    while np.fabs(offset) <= offLimit:
        offsets.append(offset)
        fee.setOffsets(amps, [offset]*namps, leg=leg)
        time.sleep(sleepTime)

        im, files = ccdFuncs.fullExposure('bias', ccd=ccd, feeControl=fee,
                                          nrows=nrows,
                                          # rowFunc=ccdFuncs.rowStats, rowFuncArgs=argDict,
                                          doSave=False, doReset=False,
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
    offs = offsets[0:]
    la = np.array(levels[0:])
    fig = plt.figure(figsize=(8,8))
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

def sinfit(x, a0, a1, a2, a3):
    """ Generate a0 * sin(a1 + x/a2) + a3 """
    return a0 * np.sin(a1 + x/a2) + a3

def argPeaks(arr):
    """ Locate all local peaks: pixels which are higher than both their neighbors. 
    
    Returns
    -------
    idx    : indices of all peaks, sorted from highest to lowest.
    """

    peakmask = np.where((arr[0:-2] < arr[1:-1]) & (arr[2:] < arr[1:-1]))
    peakmask = np.array(peakmask[0], dtype='i4') + 1
    peaks = arr * 0
    peaks[peakmask] = arr[peakmask]
    
    heights = (arr[peakmask]-arr[peakmask-1] + arr[peakmask]-arr[peakmask+1])/2
    idx = peaks.argsort()
        
    return idx[::-1]

def topPeriods(arr, topN=0, pixtime=1.392e-5):
    """ Return the identifiable spectral peaks, ordered by strength. 
    
    Parameters
    ----------
    arr : 1d array
        The vector we want a spectrum for.
    topN : integer, optional
        The number of peaks we want to limit to. default=0, which returns all peaks.
        
    Returns
    -------
    freqs  - the frequencies (Hz) of the returned FFT
    fft    - the FFT itself. Real, positive frequencies only.
    top_ii - the indices of the peaks, ordered by peak strength
    
    
    """
    normArr = arr - arr.mean()
    
    yhat = np.absolute(np.fft.fft(normArr))
    freqs = np.fft.fftfreq(yhat.size, pixtime)

    # Drop the negative half.
    pos_ii = np.where(freqs >= 0)
    yhat = yhat[pos_ii]
    freqs = freqs[pos_ii]

    peaks_ii = argPeaks(yhat)
    if topN:
        topPeaks_ii = peaks_ii[:topN]
    else:
        topPeaks_ii = peaks_ii

    return freqs, yhat, topPeaks_ii

def plotTopPeriods(arr, plot=None, topN=5):
    """ Plot the FFT of a given vector, and identify the first few
    """

    if plot is None:
        plot = plt.gca()
        
    freqs, yhat, top_ii = topPeriods(arr, topN=topN)
    
    plot.plot(freqs, yhat)
    for i in range(topN):
        freq = freqs[top_ii[i]]
        peak = yhat[top_ii[i]]
        plot.axvline(freq, color='r', alpha=0.4)
        plot.text(freq, peak, "%0.1f" % (freq),
                  horizontalalignment='center',
                  verticalalignment='bottom')

    return freqs, yhat, top_ii
        
