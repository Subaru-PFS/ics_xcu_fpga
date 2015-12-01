from clocks import Clocks

from clockIDs import *

def readClocks():
    pre = Clocks()
    pre.changeFor(duration=120,
                  turnOn= [P1,P3,S1,CNV])
    
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

    par = Clocks(initFrom=pix)
    par.changeFor(duration=500,
                  turnOff=[P1],
                  turnOn= [RG,IR,DCR])

    par.changeFor(duration=500,
                  turnOn= [P2,TG,CRC])

    par.changeFor(duration=500,
                  turnOff=[P3,CRC])

    par.changeFor(duration=500,
                  turnOn=[P1])

    par.changeFor(duration=500,
                  turnOff=[P2,TG])

    par.changeFor(duration=500,
                  turnOn=[P3])

    par.changeFor(duration=50,
                  turnOff=[RG,IR])

    par.changeFor(duration=2,
                  turnOff= [DCR])

    return pre, pix, par

