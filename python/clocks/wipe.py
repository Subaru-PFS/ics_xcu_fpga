from __future__ import absolute_import
from .clocks import Clocks
from .clockIDs import *

def wipeClocks(tickTime=40e-9):
    pre = Clocks(tickTime)
    pre.changeFor(duration=120,
                  turnOn= [P1,P3,S1])

    pix = Clocks(tickTime, initFrom=pre)
    pix.changeFor(duration=16,
                  turnOff=[S1],
                  turnOn= [S2,SW,RG,DCR,IR])

    pix.changeFor(duration=8,
                  turnOff=[RG])

    pix.changeFor(duration=24,
                  turnOff=[S2,SW],
                  turnOn= [S1])

    post = Clocks(tickTime, initFrom=pix)
    post.changeFor(duration=1000,
                   turnOff=[P1],
                   turnOn= [RG,IR,DCR])

    post.changeFor(duration=1000,
                   turnOn= [P2,TG])

    post.changeFor(duration=1000,
                   turnOff=[P3])

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

