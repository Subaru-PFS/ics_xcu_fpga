#!/usr/bin/env python

import argparse
import logging
import sys

import numpy
import matplotlib.pyplot as plt

import pyFPGA


def rowProgress(row_i, image, errorMsg="OK", 
                everyNRows=100, 
                **kwargs):
    """ A sample end-of-row callback. """

    nrows, ncols = image.shape

    if row_i%everyNRows == 0 or row_i == nrows-1 or errorMsg is not "OK":
        sys.stderr.write("line %05d %s\n" % (row_i, errorMsg))


def rowStats(line, image, errorMsg="OK", everyNRows=100, 
             ampList=range(8), cols=None, **kwargs):

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
        cols = numpy.arange(len(ccd.ampidx(0,image)))
    for a in ampList:
        ampMasks[a] = ccd.ampidx(a, image)[cols]

    if line > 0 and line % everyNRows == 0 or line == nrows-1 or errorMsg is not "OK":
        flatim = image[line-everyNRows:line,:]

        parts = ["%04d %04d %04d" % (line, 
                                     kwargs.get('dataRow', 9999),
                                     kwargs.get('fpgaRow', 9999))]
        for a in ampList:
            parts.append("%8.1f" % (flatim[:,ampMasks[a]].mean()))
        for a in ampList:
            parts.append("%5.2f" % (flatim[:,ampMasks[a]].std()))
        parts.append(errorMsg)

        print(' '.join(parts))
    
def sinfit(x, a0, a1, a2, a3):
    """ Generate a0 * sin(a1 + x/a2) + a3 """
    return a0 * numpy.sin(a1 + x/a2) + a3

def argPeaks(arr):
    """ Locate all local peaks: pixels which are higher than both their neighbors. 
    
    Returns
    -------
    idx    : indices of all peaks, sorted from highest to lowest.
    """

    peakmask = numpy.where((arr[0:-2] < arr[1:-1]) & (arr[2:] < arr[1:-1]))
    peakmask = numpy.array(peakmask[0], dtype='i4') + 1
    peaks = arr * 0
    peaks[peakmask] = arr[peakmask]
    
    heights = (arr[peakmask]-arr[peakmask-1] + arr[peakmask]-arr[peakmask+1])/2
    idx = peaks.argsort()
        
    return idx[::-1]

def topPeriods(arr, topN=0, pixtime=1.344e-5):
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
    
    yhat = numpy.absolute(numpy.fft.fft(normArr))
    freqs = numpy.fft.fftfreq(yhat.size, pixtime)

    # Drop the negative half.
    pos_ii = numpy.where(freqs >= 0)
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
