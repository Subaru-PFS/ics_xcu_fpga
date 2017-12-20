from clocks import Clocks

from clockIDs import *

from read import insertIdlePixels

def readClocks():
    pre = Clocks()
    pre.changeFor(duration=120,
                  turnOn= [P1,P2,S1,CNV])
    
    pix = Clocks(initFrom=pre)
    pix.changeFor(duration=8,
                  turnOff=[S1],
                  turnOn= [S2,DCR,IR,SCK])

    pix.changeFor(duration=8,
                  turnOn=[SW])

    pix.changeFor(duration=8,
                  turnOff=[SCK])

    pix.changeFor(duration=8,
                  turnOff=[S2,IR],
                  turnOn= [S1])

    pix.changeFor(duration=6,
                  turnOff=[DCR])

    pix.changeFor(duration=2,
                  turnOff=[CNV])

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
    # of 13.92 us, we make it 3.
    #
    pixTicks = pix.ticks[-1]
    parPhasePixCnt = 3 # np.int(np.ceil(40000 / (pixTicks * 40)))
    parPhaseTicks = pixTicks * parPhasePixCnt

    par = Clocks(initFrom=pix, logLevel=20)
    par.changeAt(at=0,
                 turnOff=[P1])
    insertIdlePixels(par, parPhasePixCnt)
    
    par.changeAt(at=1*parPhaseTicks,
                 turnOn= [P3,TG,CRC])
    insertIdlePixels(par, parPhasePixCnt)

    par.changeAt(at=2*parPhaseTicks,
                 turnOff=[P2,CRC])
    insertIdlePixels(par, parPhasePixCnt)

    par.changeAt(at=3*parPhaseTicks,
                 turnOn=[P1])
    insertIdlePixels(par, parPhasePixCnt)

    par.changeAt(at=4*parPhaseTicks,
                 turnOff=[P3,TG])
    insertIdlePixels(par, parPhasePixCnt)

    par.changeAt(at=5*parPhaseTicks,
                 turnOn=[P2])
    insertIdlePixels(par, 1)

    return pre, pix, par

