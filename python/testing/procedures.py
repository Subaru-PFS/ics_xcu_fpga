import numpy as np
import matplotlib.pyplot as plt
import cPickle as pickle

import logging
import os

from fpga import SeqPath

waveColors = ('#c0c000', 'cyan', 'magenta', '#00bf00')

class TestRig(object):
    def __init__(self, scope, dirName=None, seqno=None, root='/data/pfseng'):
        self.rootDir = root
        self.fileMgr = SeqPath.NightFilenameGen(root,
                                                filePrefix='xx',
                                                filePattern="%(seqno)06d")
        self.seqno = seqno
        self.dirName = dirName

        if dirName is not None and seqno is not None:
            self.loadSet(dirName, seqno)
        elif dirName is None and seqno is None:
            self.newSet()
        else:
            raise RuntimeError("both dirName and seqno must be set, or neither")

        self.setScope(scope)

    def __str__(self):
        return "TestRig(seqno=%s, dirName=%s)" % (self.seqno, self.dirName)

    def setScope(self, scope):
        self.scope = scope

    def loadSet(self, dirName, seqno):
        self.seqno = seqno
        dirName = os.path.join(self.fileMgr.rootDir, dirName)
        self.dirName = self.fileMgr.namesFunc(dirName, seqno)

    def newSet(self):
        if self.seqno is not None:
            raise RuntimeError("this test set has already been created")

        seqno, dirName = self.fileMgr.genNextSet()
        self.seqno = seqno
        self.dirName = dirName
        os.makedirs(self.dirName, mode=02775)
    
class OneTest(object):
    def __init__(self, rig, channel, ccd, amp, comment=''):
        self.testName = 'unnamed test'
        self.label = ''

        self.rig = rig
        self.channel = channel
        self.ccd = ccd
        self.amp = amp
        self.comment0 = comment
        self.testData = None

        self.revision = 1

    @property
    def scope(self):
        return self.rig.scope

    def fullName(self):
        return "%s-%s-%s-%s_%02d" % (self.testName, 
                                     self.channel,
                                     self.ccd,
                                     self.amp,
                                     self.revision)
    def fullPath(self):
        name = self.fullName()
        path = self.rig.dirName
        while self.revision < 50:
            path = os.path.join(path, "%s.pck" % (name))
            if not os.path.exists(path):
                return path
            self.revision += 1

    def save(self):
        if self.testData is None:
            raise RuntimeError("no data to save yet")

        path = self.fullPath()
        with open(path, "w+") as f:
            pickle.dump(self.testData, f, protocol=-1)

        return path

    def fetchData(self):
        self.testData = self.scope.getWaveforms()

    def plot(self):
        """ Default plot -- all channels, autoscaled. """

        sigplot(self.testData, xscale=1.0, noWide=True, 
                showLimits=True, title=self.label)

    @property
    def title(self):
        return "%s: %s" % (self.testName, self.label)

class S0Test(OneTest):
    def setup(self):
        self.testName = 'S0'
        self.label = "serial clocks, no averaging"

        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=200e-9, pos=50, triggerPos=20, delayMode=0, delayTime=200e-9)
        self.scope.setEdgeTrigger(level=0, slope='fall', holdoff='10e-6')
        self.scope.setLabels(('RG','S1','S2','SW'))
    
class S1Test(OneTest):
    def setup(self):
        self.testName = 'S1'
        self.label = "serial clocks, with averaging"

        self.scope.setAcqMode(numAvg=256)
        self.scope.setSampling(scale=100e-9, pos=50, triggerPos=20, delayMode=0, delayTime=200e-9)
        self.scope.setEdgeTrigger(level=0, slope='fall', holdoff='10e-6')
        self.scope.setLabels(('RG','S1','S2','SW'))
    
class V0Test(OneTest):
    def setup(self):
        self.testName = 'V0'
        self.label = "bias voltages over an exposure."

        self.scope.setWaveform(1, 'OG', scale=5)
        self.scope.setWaveform(2, 'RD', scale=5)
        self.scope.setWaveform(3, 'OD', scale=5)
        self.scope.setWaveform(4, 'BB', scale=5)

        self.scope.setSampling(scale=1, pos=50, triggerPos=20, delayMode=0, delayTime=0)
        self.scope.setManualTrigger(after=6.0)
        self.scope.setAcqMode(numAvg=0)

class V1Test(OneTest):
    def setup(self):
        self.testName = 'V1'
        self.label = "slew between modes, no clocking"

        self.scope.setWaveform(1, 'OG', scale=5)
        self.scope.setWaveform(2, 'RD', scale=5)
        self.scope.setWaveform(3, 'OD', scale=5)
        self.scope.setWaveform(4, 'BB', scale=5)

        self.scope.setSampling(scale=1, pos=50, triggerPos=20, delayMode=0, delayTime=0)
        self.scope.setEdgeTrigger(source='ch3', level=-8, slope='fall', holdoff='1')
        self.scope.setAcqMode(numAvg=0)

    def plot(self):
        sigplot(self.testData, xscale=1.0, noWide=True, 
                showLimits=True, title=self.label)
        sigplot(self.testData, xscale=1.0, noWide=True, xlim=(-0.5,4.5), ylim=(-20,20), 
                showLimits=True, title=self.label)        

class P0Test(OneTest):
    def setup(self):
        self.testName = 'P0'
        self.label = "Main parallel clocks"

        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=50e-6, pos=50, triggerPos=20, delayMode=0, delayTime=120e-6)
        self.scope.setLabels(('P1','P2','P3','TG'))
        self.scope.setEdgeTrigger(level=-4.0, slope='rise', holdoff='250e-6')
        
def sigplot(waves, channels=range(4), 
            ylim=None, xlim=None, 
            noWide=False, doNorm=False,
            xscale=1e-6, showLimits=False, 
            title=None):
    
    colors = waveColors
    
    if noWide:
        fig, plist = plt.subplots(nrows=1, figsize=(18, 6))
        p0 = plist
    else:
        fig, plist = plt.subplots(nrows=2, figsize=(18, 12))
        p0, p1 = plist

    pslice = slice(None, None)
    for i in channels:
        chan = waves['ch%d' % (i+1)]
        x = chan['x'][pslice]
        y = chan['data'][pslice]
        if doNorm:
            y -= y.mean()
        p0.plot(x/xscale, y, 
                color=colors[i], label=chan['label'])
        if not noWide:
            p1.plot(x/xscale, y, 
                    color=colors[i], label=chan['label'])
            p1.set_xlabel('%s sec' % (xscale))
        if showLimits:
            w = np.argmax(y)
            p0.plot(x[w]/xscale, y[w], 'o', color=colors[i])
            w = np.argmin(y)
            p0.plot(x[w]/xscale, y[w], 'o', color=colors[i])

    if ylim is not None:
        p0.set_ylim(ylim[0], ylim[1])
    if xlim is not None:
        p0.set_xlim(xlim[0], xlim[1])
        
    p0.legend(bbox_to_anchor=(1.1,1.0))
    p0.set_xlabel('%s sec' % (xscale))
    if title:
        p0.set_title(title, loc='center')
