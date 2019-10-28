#!/usr/bin/env python

from importlib import reload
import glob
import logging
import os
import sys
import time

import numpy as np

import fitsio

from fpga import ccd as ccdMod
from fee import feeControl as feeMod
from fpga import opticslab
reload(opticslab)

reload(ccdMod)

def rowProgress(row_i, image, errorMsg="OK", 
                everyNRows=100, 
                **kwargs):
    """ A sample end-of-row callback. """

    nrows, ncols = image.shape

    if (everyNRows is not None and (row_i%everyNRows == 0 or row_i == nrows-1)) or errorMsg != "OK":
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
    """ Append a single line to our night's LOG file. """
    
    ddir = lastNight()
    bellFile = open(os.path.join(ddir, 'LOG.txt'), 'a+', buffering=1)
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
    
def fetchCards(exptype=None, feeControl=None, expTime=0.0, darkTime=None, getCards=True):
    """ Generate all FEE exposure cards, included times and IMAGETYP. """

    if feeControl is None:
        feeControl = feeMod.fee

    if getCards:
        feeCards = feeControl.statusAsCards()
    else:
        feeCards = []
    if exptype is not None:
        feeCards.insert(0, ('EXPTIME', expTime, ''))
        feeCards.insert(0, ('DARKTIME', darkTime if darkTime is not None else expTime, ''))
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
        nrows = ccd.ccdRows//rowBinning + 5
        
    if nwipes > 0:
        if feeControl.getMode != 'idle':
            feeControl.setMode('idle')
            time.sleep(1.0)
        feeControl.setMode('erase')
        time.sleep(1.0)
        feeControl.setMode('wipe')
        time.sleep(1.0)
    for i in range(nwipes):
        print("wiping....")
        ccd.pciReset()
        readTime = ccd.configureReadout(nrows=nrows, ncols=ncols,
                                        clockFunc=getWipeClocks(),
                                        rowBinning=rowBinning)
        time.sleep(readTime+0.1)
        print("wiped %d %d %g s" % (nrows, ncols, readTime))

    if toExposeMode:
        feeControl.setMode('expose')
        time.sleep(0.25)

def clock(ncols, nrows=None, ccd=None, feeControl=None, cmd=None):
    """ Configure and start the clocks for nrows of ncols. """

    if nrows is None:
        nrows = 2*1024*1024*1024 - 1
        
    if ccd is None:
        ccd = ccdMod.ccd

    if feeControl is None:
        feeControl = feeMod.fee

    ccd.pciReset()
    readTime = ccd.configureReadout(nrows=nrows, ncols=ncols,
                                    clockFunc=getReadClocks())
    if cmd is not None:
        cmd.inform('text="started clocking %d rows of %d columns: %0.2fs or so"' % (nrows, ncols, readTime))
    
    
def readout(imtype, ccd=None,
            expTime=0, darkTime=None,
            nrows=None, ncols=None,
            doSave=True, comment='',
            extraCards=(),
            doFeeCards=True,
            feeControl=None, cmd=None,
            rowStatsFunc=None,
            doModes=True):

    """ Wrap a complete detector readout: no wipe, but with a log note, FITS cards and left in idle mode.  """
    
    if ccd is None:
        ccd = ccdMod.ccd
    
    argDict = dict(everyNRows=(nrows//5 if nrows else 500), ccd=ccd, cols=slice(50,-40))

    if feeControl is None:
        feeControl = feeMod.fee

    t0 = time.time()
    if doModes:
        feeControl.setMode('read')
        time.sleep(0.5)               # 1s per JEG
    t1 = time.time()

    feeCards = fetchCards(imtype, feeControl=feeControl, expTime=expTime,
                          darkTime=darkTime,
                          getCards=doFeeCards)

    feeCards.extend(extraCards)
    im, imfile = ccd.readImage(nrows=nrows, ncols=ncols, 
                               rowFunc=rowStatsFunc, rowFuncArgs=argDict,
                               doSave=doSave,
                               comment=comment, addCards=feeCards)
    t2 = time.time()
    if doModes:
        feeControl.setMode('idle')
        time.sleep(0.5)
    t3 = time.time()
    
    print("file : %s" % (imfile))
    print("times: %0.2f, %0.2f, %0.2f"
          % (t1-t0,t2-t1,t3-t2))
    
    fnote(imfile, comment)
    
    return im, imfile


def fullExposure(imtype, ccd=None, expTime=0.0, 
                 nrows=None, ncols=None,
                 clockFunc=None, doWipe=True,
                 doSave=True, comment='',
                 extraCards=(), doFeeCards=True,
                 feeControl=None, cmd=None):

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
        if cmd is not None:
            cmd.inform('exposureState="wiping", 5.0')
        wipe(ccd=ccd, feeControl=feeControl)

    # This cannot be used in real life!
    t1 = time.time()
    if cmd is not None:
        cmd.inform('exposureState="integrating",%0.2f' % (expTime))
    time.sleep(expTime)
    t2 = time.time()
    
    if cmd is not None:
        cmd.inform('exposureState="reading",%0.2f' % (45.0))
    im, imfile = readout(imtype, ccd=ccd, expTime=expTime,
                         nrows=nrows, ncols=ncols,
                         clockFunc=clockFunc, doSave=doSave,
                         doFeeCards=doFeeCards,
                         comment=comment, extraCards=extraCards,
                         rowStatsFunc=False, cmd=cmd,
                         feeControl=feeControl)
    t3 = time.time()

    if cmd is not None:
        cmd.inform('exposureState="idle",0.0')

    print("file : %s" % (imfile))
    print("times: wipe: %0.2f, exposure: %0.2f, readout: %0.2f, total=%0.2f"
          % (t1-t0,t2-t1,t3-t2,t3-t0))
    
    fnote(imfile, comment)
    
    return im, imfile

def fastRevRead(ccd=None, rowBinning=10,
                nrows=None, ncols=None,
                clockFunc=None,
                doSave=True, comment='',
                feeControl=None, cmd=None):

    if ccd is None:
        ccd = ccdMod.ccd
    
    argDict = dict(everyNRows=500//rowBinning, ccd=ccd, cols=slice(50,-40))

    if clockFunc is None:
        clockFunc = getFastRevReadClocks()

    if feeControl is None:
        feeControl = feeMod.fee
    try:
        feeControl.setFast()
        feeControl.setMode('revRead')
        time.sleep(1)               # Per JEG
    
        feeCards = fetchCards('revread', expTime=0)
        im, imfile = ccd.readImage(nrows=nrows, ncols=ncols, rowBinning=rowBinning,
                                   rowFunc=rowStats, rowFuncArgs=argDict,
                                   clockFunc=clockFunc, doSave=doSave,
                                   comment=comment, addCards=feeCards)
        fnote(imfile, comment)
    finally:
        feeControl.setSlow()
        feeControl.setMode('idle')
        time.sleep(1)               # Per JEG
        
    
    return im, imfile

def expSequence(ccd=None,
                nrows=None, ncols=None, nwipes=0, nbias=2, nendbias=0,
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
        
    return expList(explist, ccd=ccd,
                   nrows=nrows, ncols=ncols,
                   feeControl=feeControl, clockFunc=clockFunc,
                   comment=comment, title=title)
    
def expList(explist, ccd=None,
            nrows=None, ncols=None,
            feeControl=None,
            clockFunc=None,
            comment='',
            title='Running exposure list'):

    """ Currently the main entry-point for taking multiple exposures. 

    Takes a list of exposure tuples:
      (bias 0)
      (dark DARKTIME)
      (flat FLATTIME)
      (wipe NWIPES)
      (flash DARKTIME FLATTIME)

    """

    if feeControl is None:
        feeControl = feeMod.fee
    note('... %s (%s exposures)' % (title, len(explist)))

    files = []

    try:
        for e_i, exp in enumerate(explist):
            exptype = exp[0]
            expargs = exp[1:]
            expComment = comment + " exp. %d/%d" % (e_i+1, len(explist))
            print("%s %s" % (exptype, exp[1:]))
            if exptype == 'wipe':
                exparg = expargs[0]
                wipe(ccd=ccd, nwipes=exparg, feeControl=feeControl)
                continue

            # Wipe before all exposures, including in runs of biases.
            wipe(ccd=ccd, feeControl=feeControl)

            if exptype == 'bias':
                im, imfile = readout('bias', ccd=ccd,
                                     nrows=nrows, ncols=ncols,
                                     clockFunc=clockFunc, 
                                     feeControl=feeControl,
                                     comment=expComment)
            elif exptype == 'dark':
                darkTime = expargs[0]
                time.sleep(darkTime)
                im, imfile = readout('dark', ccd=ccd,
                                     expTime=darkTime,
                                     nrows=nrows, ncols=ncols,
                                     clockFunc=clockFunc, 
                                     feeControl=feeControl,
                                     comment=expComment)
            elif exptype == 'flat':
                flatTime = expargs[0]
                ret = opticslab.pulseShutter(flatTime)
                print(ret)

                stime, flux, current, wave, slitWidth = ret

                cards = []
                cards.append(('HIERARCH QE.slitwidth', slitWidth, 'monochrometer slit width, mm'),)
                cards.append(('HIERARCH QE.wave', wave, 'monochrometer wavelength, nm'),)
                cards.append(('HIERARCH QE.flux', flux, 'calibrated flux, W'),)
                cards.append(('HIERARCH QE.current', current, 'Keithley current, A'),)

                im, imfile = readout('flat', ccd=ccd,
                                     expTime=flatTime,
                                     nrows=nrows, ncols=ncols,
                                     clockFunc=clockFunc, 
                                     feeControl=feeControl,
                                     extraCards=cards,
                                     comment=expComment)
            elif exptype == 'flash':
                darkTime = expargs[0]
                flatTime = expargs[1]
                time.sleep(darkTime)

                ret = opticslab.pulseShutter(flatTime)
                print(ret)

                stime, flux, current, wave, slitWidth = ret

                cards = []
                cards.append(('HIERARCH QE.slitwidth', slitWidth, 'monochrometer slit width, mm'),)
                cards.append(('HIERARCH QE.wave', wave, 'monochrometer wavelength, nm'),)
                cards.append(('HIERARCH QE.flux', flux, 'calibrated flux, W'),)
                cards.append(('HIERARCH QE.current', current, 'Keithley current, A'),)

                im, imfile = readout('flash', ccd=ccd,
                                     expTime=flatTime,
                                     nrows=nrows, ncols=ncols,
                                     clockFunc=clockFunc, 
                                     feeControl=feeControl,
                                     extraCards=cards,
                                     comment=expComment)
            else:
                raise KeyError('unknown exposure type: %s' % (exptype))

            files.append(imfile)

            print(imfile)    
    finally:
        feeControl.setMode('idle')
        
    note('Done with exposure list.')
    return files

def rowStats(line, image, errorMsg="OK", everyNRows=100, 
             ampList=list(range(8)), cols=None, 
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
    
def main(argv=None):
    import argparse
    import pyFPGA

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
    print("trying to exec: %s" % (execStr))
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
