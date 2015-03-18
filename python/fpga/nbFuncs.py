import logging
import time
import numpy as np
import matplotlib.pyplot as plt

import ccdFuncs

# A cell with some routines and variables I want handy.
def normed(arr):
    """ Return an array with its mean value subtracted. Not robust. """
    return arr - np.mean(arr)

def plotAmps(im, row=None, cols=None, amps=None, plotOffset=100, fig=None):
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
        fig = plt.figure(figsize=(10,6))
    yoff = 0
    for a in amps:
        seg = normed(im[row, cols + a*imcols])
        plt.plot(cols, seg+yoff, '-+')
        yoff += plotOffset

# Routines to set the mean amp levels to some handy level.
# tuneLevels() does all amps, to about 10k.

def ampStats(im, cols=None, ccd=None):
    rowCtr = im.shape[0]/2
    rowCnt = im.shape[0]/3
    rowim = im[rowCtr-rowCnt/2:rowCtr+rowCnt/2]
    if cols is None:
        cols = np.arange(im.shape[1]/ccd.namps)
        
    means = []
    devs = []
    for a in np.arange(8):
        ampCols = ccd.ampidx(a)[cols]
        means.append(rowim[:, ampCols].mean())
        devs.append(rowim[:, ampCols].std())

    return np.array(means), np.array(devs)

def fmtArr(a, format='%0.4f'):
    return [format % i for i in a]

def tuneLevels(ccd, fee, amps=None, 
               statCols=None, levels=1000, gains=None, sigTol=3, 
               maxLoops=10, adjOffset=10, nrows=100, startStep=0.05,
               sleepTime=0.3, clockFunc=None,legs='n'):
    namps = 8
    
    if amps is None:
        amps = range(namps)
    if isinstance(amps, int):
        amps = [amps]
    if isinstance(levels, (int, float)):
        levels = np.zeros(namps, dtype='f4') + levels
    if isinstance(startStep, (int, float)):
        startStep = np.zeros(namps, dtype='f4') + startStep
    if gains is None:
        gains = np.zeros(namps)
        
    levels[np.arange(namps)%2 == 0] += adjOffset
    levels[np.arange(namps)%2 == 1] -= adjOffset

    # We cannot yet read bias levels, so zero them first
    fee.zeroLevels(amps)
    if 'n' in legs:
        fee.setLevels(amps, startStep, leg='n')
    if 'p' in legs:
        fee.setLevels(amps, -startStep, leg='p')
    time.sleep(sleepTime)

    done = np.zeros(namps, dtype='i1')
    offsets = startStep.copy()
    lastLevels = np.zeros(namps, dtype='f4')

    ii = 0
    argDict = dict(everyNRows=nrows, ampList=amps, ccd=ccd)

    # Clear any accumulated charge
    toss = ccd.readImage(nrows=nrows, rowFunc=ccdFuncs.rowStats, rowFuncArgs=argDict, doSave=False,
                         clockFunc=clockFunc)

    lastOffset = offsets * 0
    offLimit = 0.199
    while True:
        if np.all(done) or ii > maxLoops:
            break 
        im, files = ccd.readImage(nrows=nrows, rowFunc=ccdFuncs.rowStats, rowFuncArgs=argDict, doSave=False,
                                  clockFunc=clockFunc)
        newLevels, devs = ampStats(im, cols=statCols, ccd=ccd)
        print "means(%d): %s" % (ii, fmtArr(newLevels))
        print "devs (%d): %s" % (ii, fmtArr(devs))
        
        thisOffset = offsets * 0
        for a_i in range(len(amps)):
            a = amps[a_i]
            mean = newLevels[a]
            last = lastLevels[a]
            stddev = devs[a]
            g = gains[a]

            if mean == 0 or mean > 50000:
                # We are not in range yet. Keep adding the starting step.
                print "%d %d: out of range: %0.2f" % (ii, a, mean)
                thisOffset[a] = startStep[a]
                
            elif last <= 0:
                # We don't have two levels yet. Bump and remeasure.
                print "%d %d: have one, need two" % (ii, a)
                thisOffset[a] = startStep[a]
                lastLevels[a] = mean
            else:
                # Have two levels. 
                dLevel = mean - last

                # Close enough? Stop.
                if np.fabs(levels[a]-mean) < sigTol*stddev:
                    done[a_i] = True
                    continue
                    
                # Remeasure gain and apply.
                dOffset = lastOffset[a]
                if dOffset != 0.0:
                    lastGain = dLevel/dOffset
                    gains[a] = lastGain
                else:
                    lastGain = gains[a]
                # print "%d,%d: dLevel/dOffset=gain %g/%g = %g vs. %s" % (a_i, a, dLevel, dOffset, lastGain, gains[a])
                    
                stillWant = levels[a]-mean
                thisOffset[a] = stillWant/gains[a]
                if np.fabs(thisOffset[a] + offsets[a]) >= offLimit:
                    thisOffset[a] = startStep[a]
                lastLevels[a] = mean
                print("%d,%d level,mean,want,offset,doffset %g %g %g %g %g" % 
                      (a_i, a, levels[a], mean, stillWant, thisOffset[a], dOffset))

        offsets += thisOffset
        if np.any(np.fabs(offsets) >= offLimit):
            print("!!!!!!!! WARNING: railed offsets !!!!!!!: %s" % (np.fabs(offsets) >= offLimit))
            offsets[offsets < -offLimit] = -offLimit
            offsets[offsets > offLimit] = offLimit
            #done[offsets >= offLimit] = True
            #done[offsets <= -offLimit] = True
            
        print 
        print "amps: %s" % (amps)
        print "offs!(%d): %s" % (ii, fmtArr(offsets[amps]))
        print "doffs(%d): %s" % (ii, fmtArr(thisOffset[amps]))
        print "gains(%d): %s" % (ii, fmtArr(gains[amps]))
        print "done(%d of %d)   : %s" % (ii, maxLoops, done)
        print
        
        ii += 1
        lastOffset = thisOffset.copy()
        # lastLevels = newLevels
        if 'n' in legs:
            fee.setLevels(amps, offsets[amps], leg='n')
        if 'p' in legs:
            fee.setLevels(amps, -offsets[amps], leg='p')
        time.sleep(sleepTime)
        
    im, files = ccd.readImage(nrows=nrows, rowFunc=ccdFuncs.rowStats, rowFuncArgs=argDict, doSave=False,
                       clockFunc=clockFunc)
    newLevels, devs = ampStats(im, cols=statCols, ccd=ccd)
    print "means(%d): %s" % (ii, fmtArr(newLevels))
    print "devs (%d): %s" % (ii, fmtArr(devs))

    return offsets, devs, gains

def gainCurve(ccd, fee, amps=None, 
              statCols=None, nrows=200, stepSize=0.04, offLimit=0.2, sleepTime=0.5):
    namps = 8
    
    if amps is None:
        amps = range(namps)
    if isinstance(amps, int):
        amps = [amps]

    done = [False]*len(amps)
    offsets = []
    levels = []

    argDict = dict(everyNRows=50, ampList=amps, ccd=ccd)

    # We cannot yet read bias levels, so zero them first
    fee.zeroLevels(amps)
    time.sleep(sleepTime)
    
    # Clear any accumulated charge
    toss = ccd.readImage(nrows=nrows, rowFunc=ccdFuncs.rowStats, rowFuncArgs=argDict, doSave=False)

    offset = 0.0
    while not np.all(done) and np.fabs(offset) <= offLimit:
        offsets.append(offset)
        fee.setLevels(amps, [offset]*namps)
        time.sleep(sleepTime)

        im, files = ccd.readImage(nrows=nrows, rowFunc=ccdFuncs.rowStats, rowFuncArgs=argDict, doSave=False)
        newLevels, devs = ampStats(im, statCols)
        print "means(%d): %s" % (offset, fmtArr(newLevels))
        print "devs (%d): %s" % (offset, fmtArr(devs))
        
        levels.append(newLevels.copy())
        offset += stepSize
        
        if np.any(np.fabs(offsets) >= offLimit):
            print "!!!!!!!! WARNING: railed offsets !!!!!!!"
            offsets[offsets < -offLimit] = -offLimit
            offsets[offsets > offLimit] = offLimit
            done[offsets >= offLimit] = True
            done[offsets <= -offLimit] = True
            
        print 
        print "done(%g/%g)   : %s" % (offset, offLimit, done)
        print
        
    return offsets, levels
        

def plotGains(ccd, offsets, levels):
    offs = offsets[1:]
    la = np.array(levels[1:])
    fig = plt.figure('levels')
    fig.clf()
    p = fig.add_subplot(111)

    fitgains = []
    for a in range(ccd.namps):
        fit = np.polyfit(offs, la[:,a], 1)
        ev = np.polyval(fit, offs)
        p.plot(offs, la[:,a]-ev, '+-')
        print "%d: %s" % (a, fit)
        fitgains.append(fit)
    
    return np.array(fitgains)
