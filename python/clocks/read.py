from importlib import reload

from . import clocks
from .clockIDs import *

reload(clocks)

def insertIdlePixels(clks, cnt):
    """ Insert a number of complete pixel clockings, without shift or conversion. 

    Args:
    -----
    clks : a Clocks instance
       The clocking which we insert into.
    cnt : int
       The number of pixels to insert..

    We want to run the serial clocks during parallel clocking, so that
    charge does not accumulate. Of course we don't want to actually _read_
    the pixels.
    """

    for i in range(cnt):
        clks.changeFor(duration=8,
                       turnOff=[IR])

        clks.changeFor(duration=4,
                       turnOn=[SW])

        clks.changeFor(duration=4+8+12,
                       turnOn=[DCR])

        clks.changeFor(duration=2,
                       turnOff=[DCR])

        clks.changeFor(duration=16+108,
                       turnOn=[IR])

        clks.changeFor(duration=20+108+16+32,
                       turnOff=[SW])

        clks.changeFor(duration=12,
                       turnOn= [RG])

        clks.changeFor(duration=12,
                       turnOff= [RG])

def readClocks(holdOn=None, holdOff=None):
    pre = clocks.Clocks(holdOn=holdOn, holdOff=holdOff)
    pre.changeFor(duration=120,
                  turnOn= [P1,P3,S1,CNV,IR])
    
    pix = clocks.Clocks(initFrom=pre, logLevel=20)
    pix.changeFor(duration=8,
                  turnOff=[S1,IR],
                  turnOn= [S2,SCK])

    pix.changeFor(duration=4,
                  turnOn=[SW])

    pix.changeFor(duration=4,
                  turnOn=[DCR])

    pix.changeFor(duration=8,
                  turnOff=[SCK])

    pix.changeFor(duration=12,
                  turnOff=[S2],
                  turnOn= [S1])

    pix.changeFor(duration=2,
                  turnOff=[DCR])

    pix.changeFor(duration=16, # was 2
                  turnOff=[CNV],
                  turnOn=[IR])

    pix.changeFor(duration=108,
                  turnOn= [I_M])

    pix.changeFor(duration=20,
                  turnOff=[I_M, SW])

    pix.changeFor(duration=108,
                  turnOn=[I_P])

    pix.changeFor(duration=16,
                  turnOff=[I_P])

    pix.changeFor(duration=32,
                  turnOn= [CNV])

    pix.changeFor(duration=12,
                  turnOn= [RG])

    pix.changeFor(duration=12,
                  turnOff= [RG])

    # We want each phase of the parallel clocking to take ~40us.
    # We also want each phase to consist of an integral number of
    # complete pixels clockings. With the current pixel time
    # of 14.48 us, we make it 3.
    #
    pixTicks = pix.ticks[-1]
    parPhasePixCnt = 3 # np.int(np.ceil(40000 / (pixTicks * 40)))
    parPhaseTicks = pixTicks * parPhasePixCnt

    par = clocks.Clocks(initFrom=pix, logLevel=20)
    par.changeAt(at=0,
                 turnOff=[P1])
    insertIdlePixels(par, parPhasePixCnt)
    
    par.changeAt(at=1*parPhaseTicks,
                 turnOn= [P2,TG,CRC])
    insertIdlePixels(par, parPhasePixCnt)

    par.changeAt(at=2*parPhaseTicks,
                 turnOff=[P3,CRC])
    insertIdlePixels(par, parPhasePixCnt)

    par.changeAt(at=3*parPhaseTicks,
                 turnOn=[P1])
    insertIdlePixels(par, parPhasePixCnt)

    par.changeAt(at=4*parPhaseTicks,
                 turnOff=[P2,TG])
    insertIdlePixels(par, parPhasePixCnt)

    par.changeAt(at=5*parPhaseTicks,
                 turnOn=[P3])
    insertIdlePixels(par, 1)

    return pre, pix, par

