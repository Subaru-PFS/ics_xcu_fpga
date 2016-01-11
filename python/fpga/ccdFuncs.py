#!/usr/bin/env python

import argparse
import glob
import logging
import os
import sys
import time

import numpy as np
import matplotlib.pyplot as plt

import fitsio

import pyFPGA

import fpga.ccd as ccdMod
import fee.feeControl as feeMod
import fpga.opticslab as opticslab

reload(ccdMod)

def rowProgress(row_i, image, errorMsg="OK", 
                everyNRows=100, 
                **kwargs):
    """ A sample end-of-row callback. """

    nrows, ncols = image.shape

    if (everyNRows is not None and (row_i%everyNRows == 0 or row_i == nrows-1)) or errorMsg is not "OK":
        sys.stderr.write("line %05d %s\n" % (row_i, errorMsg))

def getReadClocks():
    """ Dynamically load read clock pattern. """

    import clocks.read
    reload(clocks.read)
    
    return clocks.read.readClocks

def getFastRevReadClocks():
    """ Dynamically load reverse read clock pattern. """
    
    import clocks.fastrevread
    reload(clocks.fastrevread)
    
    return clocks.fastrevread.readClocks

def getWipeClocks():
    """ Dynamically load wipe clock pattern. """

    import clocks.wipe
    reload(clocks.wipe)
    
    return clocks.wipe.wipeClocks

def lastNight():
    """ Convenience for getting the latest night's directory. """
    
    ddirs = glob.glob('/data/pfs/201[0-9]-[0-9][0-9]-[0-9][0-9]')
    return sorted(ddirs)[-1]

def ts(t=None):
    if t is None:
        t = time.time()
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t))

                    
def note(text, tick=None):
    ddir = lastNight()
    bellFile = file(os.path.join(ddir, 'LOG.txt'), 'ab+', buffering=1)
    bellFile.write("%s %s\n" % (ts(), text))
    bellFile.flush()
    bellFile.close()

def fnote(fname, ftype='', notes=''):
    if fname is None:
        return
    
    hdr = fitsio.read_header(fname)
    hdrNotes = "ccd=%s,%s pa=%s %s %s" % (hdr.get('temp.ccd0'),
                                          hdr.get('temp.ccd1'),
                                          hdr.get('temp.PA'),
                                          hdr.get('IMAGETYP', 'unknown').strip(),
                                          hdr.get('EXPTIME', ''))

    note("%s %s %s %s" % (fname, ftype, hdrNotes, notes))
    
def fetchCards(exptype=None, expTime=0.0):
    feeCards = feeMod.fee.statusAsCards()
    if exptype is not None:
        feeCards.insert(0, ('EXPTIME', expTime, ''))
        feeCards.insert(0, ('IMAGETYP', exptype, ''))
        feeCards.insert(0, ('DATE-OBS', ts(), 'Crude Lab Time'))
    return feeCards

def wipe(ccd=None, nwipes=1, ncols=None, nrows=None,
         rowBinning=1,
         feeControl=None,
         toExposeMode=True):
    """ Run nwipes full-detector wipes. Leave CCD in expose mode. 

    Per JEG, 2015-12-01:
     Before each exposure, you should do the following sequence:

     Gate voltages in erase mode, Vbb high. Wait ~1 second
     Vbb to zero, wait ~ 1s
     Vbb to read voltage, wait ~ 1s
     Fast wipe
     Set expose mode 

     Later: read.

    """

    if ccd is None:
        ccd = ccdMod.ccd

    if feeControl is None:
        feeControl = feeMod.fee

    if ncols is None:
        ncols = ccd.ampCols
    if nrows is None:
        nrows = ccd.ccdRows / rowBinning + 5
        
    if nwipes > 0:
        if feeControl.getMode != 'idle':
            feeControl.setMode('idle')
            time.sleep(1.0)
        feeControl.setMode('erase')
        time.sleep(1.0)
        feeControl.setMode('wipe')
        time.sleep(1.0)
    for i in range(nwipes):
        print "wiping...."
        ccd.pciReset()
        readTime = ccd.configureReadout(nrows=nrows, ncols=ncols,
                                        clockFunc=getWipeClocks(),
                                        rowBinning=rowBinning)
        time.sleep(readTime+0.1)
        print "wiped %d %d %g s" % (nrows, ncols, readTime)

    if toExposeMode:
        feeControl.setMode('expose')
        time.sleep(0.25)

def readout(imtype, ccd=None, expTime=0, 
            nrows=None, ncols=None,
            clockFunc=None,
            doSave=True, comment='',
            extraCards=(),
            feeControl=None):

    """ Wrap a complete detector readout: no wipe, but with a log note, FITS cards and left in idle mode.  """
    
    if ccd is None:
        ccd = ccdMod.ccd
    
    argDict = dict(everyNRows=(nrows/5 if nrows else 500), ccd=ccd, cols=slice(50,-40))

    if clockFunc is None:
        clockFunc = getReadClocks()

    if feeControl is None:
        feeControl = feeMod.fee

    t0 = time.time()
    feeControl.setMode('read')
    time.sleep(1)               # Per JEG
    t1 = time.time()
    
    feeCards = fetchCards(imtype, expTime=expTime)
    feeCards.extend(extraCards)
    im, files = ccd.readImage(nrows=nrows, ncols=ncols, 
                              rowFunc=rowStats, rowFuncArgs=argDict,
                              clockFunc=clockFunc, doSave=doSave,
                              comment=comment, addCards=feeCards)
    t2 = time.time()
    feeControl.setMode('idle')
    time.sleep(0.5)
    t3 = time.time()
    
    print "files: %s" % (files)
    print("times: %0.2f, %0.2f, %0.2f"
          % (t1-t0,t2-t1,t3-t2))
    
    if files:
        imfile = files[0]
    else:
        imfile = None
    fnote(imfile, comment)
    
    return im, imfile


def fullExposure(imtype, ccd=None, expTime=0, 
                 nrows=None, ncols=None,
                 clockFunc=None, doWipe=True,
                 doSave=True, comment='',
                 extraCards=(),
                 feeControl=None):

    """ Wrap a complete exposure, including wipe, sleep, and readout. 

    Because of the sleep, this is only useful for biases and short darks.
    """
    
    if ccd is None:
        ccd = ccdMod.ccd
    
    if clockFunc is None:
        clockFunc = getReadClocks()

    if feeControl is None:
        feeControl = feeMod.fee

    t0 = time.time()
    if doWipe:
        wipe(ccd=ccd, ncols=ncols, nrows=nrows, feeControl=feeControl)

    # This cannot be used in real life!
    t1 = time.time()
    time.sleep(expTime)
    t2 = time.time()
    
    im, files = readout(imtype, ccd=ccd, expTime=expTime,
                        nrows=nrows, ncols=ncols,
                        clockFunc=clockFunc, doSave=doSave,
                        comment=comment, extraCards=extraCards,
                        feeControl=feeControl)
    t3 = time.time()


    print "files: %s" % (files)
    print("times: wipe: %0.2f, exposure: %0.2f, readout: %0.2f, total=%0.2f"
          % (t1-t0,t2-t1,t3-t2,t3-t0))
    
    if files:
        imfile = files[0]
    else:
        imfile = None
    fnote(imfile, comment)
    
    return im, imfile

def fastRevRead(rowBinning=10,
                nrows=None, ncols=None,
                clockFunc=None,
                doSave=True, comment='',
                feeControl=None):
    
    ccd = ccdMod.ccd
    
    argDict = dict(everyNRows=500/rowBinning, ccd=ccd, cols=slice(50,-40))

    if clockFunc is None:
        clockFunc = getFastRevReadClocks()

    if feeControl is None:
        feeControl = feeMod.fee
    try:
        feeControl.setFast()
        feeControl.setMode('revRead')
        time.sleep(1)               # Per JEG
    
        feeCards = fetchCards('revread', expTime=0)
        im, files = ccd.readImage(nrows=nrows, ncols=ncols, rowBinning=rowBinning,
                                  rowFunc=rowStats, rowFuncArgs=argDict,
                                  clockFunc=clockFunc, doSave=doSave,
                                  comment=comment, addCards=feeCards)
        fnote(files[0], comment)
    finally:
        feeControl.setSlow()
        feeControl.setMode('idle')
        time.sleep(1)               # Per JEG
        
    
    return im, files[0]

def expSequence(nrows=None, ncols=None, nwipes=1, nbias=2, nendbias=0,
                darks=(), flats=(), 
                feeControl=None,
                clockFunc=None,
                comment='',
                title='Running sequence'):

    explist = []
    if nwipes > 0:
        explist.append(('wipe', nwipes),)
    for i in range(nbias):
        explist.append(('bias', 0),)
    for darkTime in darks:
        explist.append(('dark', darkTime),)
    for flatTime in flats:
        explist.append(('flat', flatTime),)
    for i in range(nendbias):
        explist.append(('bias', 0),)
        
    return expList(explist, nrows=nrows, ncols=ncols,
                   feeControl=feeControl, clockFunc=clockFunc,
                   comment=comment, title=title)
    
def expList(explist, nrows=None, ncols=None,
            feeControl=None,
            clockFunc=None,
            comment='',
            title='Running exposure list'):

    if feeControl is None:
        feeControl = feeMod.fee
    note('... %s (%s exposures)' % (title, len(explist)))

    for e_i, exp in enumerate(explist):
        exptype, exparg = exp
        expComment = comment + " exp. %d/%d" % (e_i+1, len(explist))
        print "%s %s" % (exptype, exparg)
        if exptype == 'wipe':
            wipe(nrows=nrows, ncols=ncols, nwipes=exparg, feeControl=feeControl)
            continue

        wipe(nrows=nrows, ncols=ncols,
             toExposeMode=(exptype != 'bias'),
             feeControl=feeControl)
        if exptype == 'bias':
            im, imfile = fullExposure('bias',
                                      nrows=nrows, ncols=ncols,
                                      clockFunc=clockFunc, 
                                      feeControl=feeControl,
                                      comment=expComment)
        elif exptype == 'dark':
            darkTime = exparg
            time.sleep(darkTime)
            im, imfile = fullExposure('dark', expTime=darkTime,
                                      nrows=nrows, ncols=ncols,
                                      clockFunc=clockFunc, 
                                      feeControl=feeControl,
                                      comment=expComment)
        elif exptype == 'flat':
            time.sleep(0.25)
            
            flatTime = exparg
            pulseShutter(flatTime)
            time.sleep(flatTime + 1)
            im, imfile = fullExposure('flat', expTime=flatTime,
                                      nrows=nrows, ncols=ncols,
                                      clockFunc=clockFunc, 
                                      feeControl=feeControl,
                                      comment=expComment)
        print imfile    

    feeControl.setMode('idle')
    note('Done with exposure list.')
    

def rowStats(line, image, errorMsg="OK", everyNRows=100, 
             ampList=range(8), cols=None, 
             lineDetail=False, **kwargs):

    """ Per-row callback to print basic per-amp stats.

    We currently output means and std deviations for the given
    ampList, taken over the last everyNrows.

    Parameters
    ----------
    line : int
       The row index, into the image arg. 
    image : 2d array of pixels.
       The full image, with valid data up to this line. So this
       row is image[line,:]
    ccd : ccd object
       The calling CCD object. We need this.
    everyNRows : int, optional
       Specifies how often we want an output line. The stats are taken
       over the last eveyrNRows lines.
    ampList : tuple, optional
       The amps we want stats for.
    cols : optional
       The columns we want to take stats over.
    lineDetail : bool, optional
       If True, print line info from the FPGA.

    Examples
    --------

    # Take a 10000 row exposure, where we get stats every 50 rows. We do not save the image 
    # to disk.
    >>> argDict = dict(ccd=ccd, everyNRows=50, ampList=(1,6))
    >>> im = readImage(nrows=10000, rowFunc=ccdFuncs.rowStats, rowFuncArgs=argDict, doSave=False)

    """

    ccd = kwargs['ccd']
    nrows = image.shape[0]
    ampMasks = {}
    if cols is None:
        cols = slice(0,(len(ccd.ampidx(0,image))))
    for a in ampList:
        ampMasks[a] = ccd.ampidx(a, image)[cols]

    if (everyNRows is not None and (line % everyNRows == 0 or line == nrows-1)) or errorMsg is not "OK":
        imRow = image[line]

        parts = ["%04d" % line]
        if lineDetail:
            parts.append("%04d %04d" % (
                kwargs.get('dataRow', 9999),
                kwargs.get('fpgaRow', 9999)))

        for a in ampList:
            parts.append("%0.1f" % (imRow[ampMasks[a]][cols].mean()))
        for a in ampList:
            parts.append("%0.2f" % (imRow[ampMasks[a]][cols].std()))
        parts.append(errorMsg)

        print(' '.join(parts))
    
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

def plotTopPeriods(arr, topN=5):
    """ Plot the FFT of a given vector, and identify the first few
    """
    
    freqs, yhat, top_ii = topPeriods(arr, topN=topN)
    
    plt.plot(freqs, yhat)
    plt.vlines(freqs[top_ii[:topN]], 0, yhat.max(), 
               'r', alpha=0.4)
    plt.show()
    for i in range(topN):
        freq = freqs[top_ii[i]]
        print "%0.1fHz -- %0.1f" % (freq, yhat[top_ii[i]])

    return freqs, yhat, top_ii
        
def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if isinstance(argv, basestring):
        argv = argv.split()

    parser = argparse.ArgumentParser(description="Send one or more commands to the FEE controller.",
                                     epilog="At least one command must be specified.\n")
    parser.add_argument('--rows', type=int, default=4240,
                        help='number of rows to read')
    parser.add_argument('--sim', action='store_true',
                        help='read FPGA simulated image')
    parser.add_argument('--save', action='store_true',
                        help='whether to save the image file')
    parser.add_argument('--rowFunc', type=str, default='rowProgress',
                        help='the function to pass each line to.')
    parser.add_argument('--rowFuncArgs', type=str, default="",
                        help='extra args to pass to rowFunc.')
    parser.add_argument('--debug', action='store_true',
                        help='print more stuff')

    args = parser.parse_args(argv)

    logLevel = logging.DEBUG if args.debug else logging.WARN

    exec("rowFunc = %s" % (args.rowFunc))
    execStr = "rowFuncArgs = dict(%s)" % (args.rowFuncArgs)
    print "trying to exec: %s" % (execStr)
    exec(execStr)

    fee = pyFPGA.FPGA()
    im = fee.readImage(doTest=args.sim, 
                       debugLevel=logLevel,
                       nrows=args.rows, 
                       rowFunc=args.rowFunc, 
                       rowFuncArgs=args.rowFuncArgs)

    return im

if __name__ == "__main__":
    main()
