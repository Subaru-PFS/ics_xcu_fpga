from clocks import Clocks

from clockIDs import *

def readClocks(tickTime=40e-9):
    pre = Clocks(tickTime)
    pre.changeFor(duration=120,
                  turnOn= [P1,P3,S1,CNV])
    
    pix = Clocks(tickTime, initFrom=pre)
    pix.changeFor(duration=8,
                  turnOff=[S1],
                  turnOn= [S2,RG,DCR,IR,SCK])

    pix.changeFor(duration=8,
                  turnOn=[SW])

    pix.changeFor(duration=8,
                  turnOff=[SCK,RG])

    pix.changeFor(duration=8,
                  turnOff=[S2,IR],
                  turnOn= [S1])

    pix.changeFor(duration=6,
                  turnOff=[DCR])

    pix.changeFor(duration=2,
                  turnOff=[CNV])

    pix.changeFor(duration=108,
                  turnOn= [I_M])

    pix.changeFor(duration=2,
                  turnOff=[I_M])

    pix.changeFor(duration=18,
                  turnOff=[SW])

    pix.changeFor(duration=108,
                  turnOn=[I_P])

    pix.changeFor(duration=16,
                  turnOff=[I_P])

    pix.changeFor(duration=56,
                  turnOn= [CNV])

    post = Clocks(tickTime, initFrom=pix)
    post.changeFor(duration=1000,
                   turnOff=[P1],
                   turnOn= [RG,IR,DCR])

    post.changeFor(duration=1000,
                   turnOn= [P2,TG,CRC])

    post.changeFor(duration=1000,
                   turnOff=[P3,CRC])

    post.changeFor(duration=1000,
                   turnOn=[P1])

    post.changeFor(duration=1000,
                   turnOff=[P2,TG])

    post.changeFor(duration=1000,
                   turnOn=[P3])

    post.changeFor(duration=50,
                   turnOff=[RG,IR])

    post.changeFor(duration=2,
                   turnOff= [DCR])

    return pre, pix, post

