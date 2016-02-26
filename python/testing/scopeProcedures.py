import re

import numpy as np
import matplotlib.pyplot as plt
import cPickle as pickle

import logging
import os

from fpga import SeqPath
from fee import feeControl

waveColors = ('#c0c000', 'cyan', 'magenta', '#00bf00')

class TestRig(object):
    """ Test sequence:

    Step 1: test the base voltages on the two CCDs
    0,0 V0
    1,0 V0

    Step 2: test the serials and parallels on both CCDs
    1,0 S0
    0,0 S0
    0,0 P0
    1,0 P0

    Step 3: test the secondary parallel signals on both CCDs
    1,0 P1
    0,0 P1

    [ Back at CCD 0,0! ]

    Step 4: make the S1 test there now.
    0,0 S1
    1,0 S1

    Step 5: step through S0, S1, and V0 on the rest of the amps.
    1,1 S1
    1,1 S0
    1,1 V0

    1,2 V0
    1,2 S0
    1,2 S1
    
    1,3 S1
    1,3 S0
    1,3 V0

    0,1 V0
    0,1 S0
    0,1 S1
    
    0,2 S1
    0,2 S0
    0,2 V0

    0,3 V0
    0,3 S0
    0,3 S1
    
    Step 6: finish the stray parallel tests.

    0   P2
    1   P3


    """
    
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

        self.tests = []
        
    def __str__(self):
        return "TestRig(seqno=%s, dirName=%s, %d tests)" % (self.seqno,
                                                            self.dirName,
                                                            len(self.tests))

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
        self.utday = os.path.split(dirName)[-2]
        os.makedirs(self.dirName, mode=02775)

    def registerTest(self, test):
        self.tests.append(test)

    def unregisterTest(self, test):
        self.tests.remove(test)
        
class OneTest(object):
    def __init__(self, rig, channel, amp, ccd='X', comment='', revision=1):
        self.initTest()

        self.rig = rig
        self.channel = channel
        self.ccd = ccd
        self.amp = amp
        self.comment0 = comment
        self.testData = None
        self.delayTime = 0
        
        self.revision = revision

    def initTest(self):
        self.testName = 'unnamed test'
        self.label = ''

    @property
    def scope(self):
        return self.rig.scope

    def fullName(self):
        return "%s-%s-%s_%02d" % (self.testName, 
                                  self.channel,
                                  self.amp,
                                  self.revision)
    def parseFullName(self, name):
        m = re.search('''(?P<testName>[^-]+)-
                         (?P<channel>[^-]+)-
                         (?:(?P<ccd>[^-]+)-)
                         (?P<amp>[^_]+)_
                         (?P<revision>\d+).pck.*''',
                      name, re.VERBOSE)
        if not m:
            raise RuntimeError("cannot parse %s as a %s test name" % (name,
                                                                      self.testName))

        self.channel = m['channel']
        self.ccd = m['ccd'] if 'ccd' in m else None
        self.amp = m['amp']
        self.revision = m['revision']

    def fullPath(self):
        dirName = self.rig.dirName
        while self.revision < 100:
            name = self.fullName()
            path = os.path.join(dirName, "%s.pck" % (name))
            if not os.path.exists(path):
                return path
            self.revision += 1

    def fullPathTemplate(self):
        name = self.fullName()
        path = self.rig.dirName
        return os.path.join(path, name)

    def save(self, comment=''):
        """ Save our test data to a properly named file. """
        
        if self.testData is None:
            raise RuntimeError("no data to save yet")

        path = self.fullPath()
        with open(path, "w+") as f:
            pickle.dump(self.testData, f, protocol=-1)

        return path

    def load(self, path, force=False):
        if self.testData is not None and not force:
            raise RuntimeError("data already exists. Add force=True to overwrite.")

        with open(path, "r") as f:
            rawdata = pickle.load(f)


        if 'version' in rawdata:
            self.testData = rawdata
        else:
            self.testData = dict()
            self.testData['waveforms'] = rawdata
            self.testData['version'] = 1
        
        return path

    def fetchData(self):
        self.testData = dict()
        self.testData['version'] = 2
        self.testData['waveforms'] = self.scope.getWaveforms()


    def channelData(self):
        """ Return an ndarray of data for the given channels. """

        datalen = self.testData['waveforms']['ch1']['x'].shape[0]
        arr = np.zeros((datalen, 5), dtype='f8')
        arr[:,0] = self.testData['waveforms']['ch1']['x']
        for i in range(4):
            arr[:,i+1] = self.testData['waveforms']['ch%d' % (i+1)]['data']

        return arr
    
    def plot(self):
        """ Default plot -- all channels, autoscaled. """

        sigplot(self.testData['waveforms'], xscale=1.0, noWide=True, 
                showLimits=True, title=self.title)

    @property
    def title(self):
        return "Test %s, amp %s/%s run %s/%04d, rev %02d: %s" % (self.testName,
                                                                 self.channel, self.amp,
                                                                 self.rig.utday, self.rig.seqno,
                                                                 self.revision,
                                                                 self.label)

class S0Test(OneTest):
    def initTest(self):
        self.testName = 'S0'
        self.label = "serial clocks, no averaging"
        
    def setup(self):
        self.scope.setAcqMode(numAvg=0)
        self.delayTime = 13.920*1e-6 * 10
        self.scope.setSampling(scale=200e-9, pos=50, triggerPos=20, delayMode=1, delayTime=self.delayTime)
        self.scope.setEdgeTrigger(source='ch3',
                                  level=2, slope='fall', holdoff='10e-6')

        # C4 C5 C7 C9
        self.scope.setWaveform(1, 'RG', scale=2)
        self.scope.setWaveform(2, 'S1', scale=2)
        self.scope.setWaveform(3, 'S2', scale=2)
        self.scope.setWaveform(4, 'SW', scale=2)
    
    def plot(self):
        sigplot(self.testData['waveforms'], xscale=1e-6,
                noWide=True,
                xlim=(-0.2,1.7), ylim=(-8,4), 
                showLimits=True, title=self.title)        

        return sigplot(self.testData['waveforms'], xscale=1e-6,
                       noWide=False,
                       xlim=(-0.5,14), ylim=(-8,4), 
                       showLimits=True, title=self.title)        

class S1Test(OneTest):
    def initTest(self):
        self.testName = 'S1'
        self.label = "Alternate serial clocks"

    def setup(self):
        self.scope.setAcqMode(numAvg=1)
        self.delayTime = 13.920*1e-6 * 10
        self.scope.setSampling(scale=200e-9, pos=50, triggerPos=20, delayMode=1, delayTime=self.delayTime)
        self.scope.setEdgeTrigger(source='ch3',
                                  level=2, slope='fall', holdoff='10e-6')

        # C4 C6 C8 C10
        self.scope.setWaveform(1, 'RG', scale=2)
        self.scope.setWaveform(2, 'S1.2', scale=2)
        self.scope.setWaveform(3, 'S2.2', scale=2)
        self.scope.setWaveform(4, 'OS', scale=2)
    
    def plot(self):
        sigplot(self.testData['waveforms'], xscale=1e-6,
                noWide=True,
                xlim=(-0.2,1.7), ylim=(-8,4), 
                showLimits=True, title=self.title)        

        return sigplot(self.testData['waveforms'], xscale=1e-6,
                       noWide=False,
                       xlim=(-0.5,14), ylim=(-8,4), 
                       showLimits=True, title=self.title)        

class V0Test(OneTest):

    def initTest(self):
        self.delayTime = 0 #13.920*1e-6 * 10
        self.testName = 'V0'
        self.label = "power up, all modes, readout, power off"

    def describe(self):
        # C1 C2 C11 M11
        pass
    
    def setup(self):
        # C1 C2 C11 M11
        self.scope.setWaveform(1, 'OG', scale=5)
        self.scope.setWaveform(2, 'RD', scale=5)
        self.scope.setWaveform(3, 'OD', scale=5)
        self.scope.setWaveform(4, 'BB', scale=5)

        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=1, pos=10, triggerPos=10, delayMode=0, delayTime=0)
        self.scope.setEdgeTrigger(source='ch3', level=-2.0, slope='fall', holdoff='1e-9')


    def plot(self):
        return sigplot(self.testData['waveforms'], xscale=1.0, 
                       xlim=(-1,15), ylim=(-20,20), 
                       showLimits=True, title=self.title)        

class P0Test(OneTest):
    def initTest(self):
        self.testName = 'P0'
        self.label = "Main parallel clocks"

    def setup(self):
        # M10 M4 M5 M6
        self.scope.setWaveform(1, 'TG', scale=5)
        self.scope.setWaveform(2, 'P1', scale=2)
        self.scope.setWaveform(3, 'P2', scale=2)
        self.scope.setWaveform(4, 'P3', scale=2)

        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=50e-6, pos=50, triggerPos=20, delayMode=0, delayTime=120e-6)

        self.scope.setEdgeTrigger(level=0.0, slope='fall', holdoff='250e-6')
        
    def plot(self):
        return sigplot(self.testData['waveforms'], xscale=1e-6,
                       xlim=(-50,250), ylim=(-7,7), 
                       showLimits=True, title=self.title)        

class P1Test(OneTest):
    def initTest(self):
        self.testName = 'P1'
        self.label = "Storage parallel clocks"

    def setup(self):
        # M10 M7 M8 M9
        self.scope.setWaveform(1, 'TG', scale=5)
        self.scope.setWaveform(2, 'P1S', scale=2)
        self.scope.setWaveform(3, 'P2S', scale=2)
        self.scope.setWaveform(4, 'P3S', scale=2)

        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=50e-6, pos=50, triggerPos=20, delayMode=0, delayTime=120e-6)

        self.scope.setEdgeTrigger(level=-2.0, slope='fall', holdoff='250e-6')
        
    def plot(self):
        return sigplot(self.testData['waveforms'], xscale=1e-6,
                       xlim=(-50,250), ylim=(-7,7), 
                       showLimits=True, title=self.title)        

class P2Test(OneTest):
    def initTest(self):
        self.testName = 'P2'
        self.label = "Storage parallel clocks"

    def setup(self):
        # M10 M1 M2 M3
        self.scope.setWaveform(1, 'TG', scale=2)
        self.scope.setWaveform(2, 'ISV', scale=2)
        self.scope.setWaveform(3, 'IG1', scale=5)
        self.scope.setWaveform(4, 'IG2', scale=5)

        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=50e-6, pos=50, triggerPos=20, delayMode=0, delayTime=120e-6)

        self.scope.setEdgeTrigger(level=-2.0, slope='fall', holdoff='250e-6')
        
    def plot(self):
        return sigplot(self.testData['waveforms'], xscale=1e-6,
                       xlim=(-50,250), ylim=(-7,7), 
                       showLimits=True, title=self.title)        

class P3Test(OneTest):
    def initTest(self):
        self.testName = 'P3'
        self.label = "ISV,IG1V,IG2V"
        self.probes = (('TG', 'Misc 10'),
                       ('ISV', 'Misc 1'),
                       ('IG1', 'Misc 2'),
                       ('IG2', 'Misc 3'))
        fee = feeControl.FeeControl(noConnect=True)
        mode = fee.presets['read']
        self.volts = dict(TG=(3.0,-5.0),
                          ISV=(-10.0,),
                          IG1=(5.0,),
                          IG2=(mode.presets['P_off'], mode.presets['P_on']))
        
    def setup(self):
        self.scope.setWaveform(1, 'TG', scale=2)
        self.scope.setWaveform(2, 'ISV', scale=2)
        self.scope.setWaveform(3, 'IG1', scale=2)
        self.scope.setWaveform(4, 'IG2', scale=5)

        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=50e-6, pos=50, triggerPos=20, delayMode=0, delayTime=120e-6)

        self.scope.setEdgeTrigger(level=0, slope='fall', holdoff='250e-6')
        
    def plot(self):
        fig, plots = sigplot(self.testData['waveforms'], xscale=1e-6,
                             xlim=(-50,250), ylim=(-7,7), 
                             showLimits=True, title=self.title)
        return fig, plots
            
class Switch1Test(OneTest):
    def initTest(self):
        self.testName = 'Switch1A'
        self.label = " switch times"
        self.clocks = None
        rowTime = 7925.920 * 1e-6
        self.pixTime = 13.920 * 1e-6
        self.delayTime = (0 * rowTime +  0 * self.pixTime)
        
    def setup(self):
        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=20e-9, # recordLength=1000000,
                               triggerPos=20,
                               delayMode=1, delayTime=self.delayTime / 1e-6, delayUnits='us')

        self.scope.setEdgeTrigger(source='ch2', level=1.3, slope='rise', holdoff='10e-6')

        self.scope.setWaveform(1, 'DCR', scale=0.2)
        self.scope.setWaveform(2, 'IR', scale=1.0)
        self.scope.setWaveform(3, 'ampout', scale=0.2)
        self.scope.setWaveform(4, '', scale=5)

    def setClocks(self, clocks=None):
        if clocks is None:
            import clocks.read

            pre, pix, post = clocks.read.readClocks()
            clocks = np.array(pix.ticks) * pix.tickTime
            
        self.clocks = clocks
        print "clocks: %s" % (self.clocks)
        
    def plot(self, channels=[0,1]):
        #self.setClocks()
        xscale = 1e-6
        fig, pl = sigplot(self.testData['waveforms'], xscale=xscale,
                          channels=range(3),
                          offsets=[0,-1,0,0],
                          noWide=False,
                          xoffset=self.pixTime,
                          ylim=(-0.25,0.75),
                          xlim=(-1.0,15),
                          #clocks=self.clocks,
                          showLimits=False, title=self.title)
        for p in pl:	
#            p.set_xticks(np.arange(0,pixTime,1000)/1000.0)
#            p.set_xticks(np.arange(0,pixTime,200)/1000.0, minor=True)
            p.grid(which='major', alpha=0.7)
            p.grid(which='minor', alpha=0.2)
                
                
        return fig, pl

class Switch2Test(OneTest):
    def initTest(self):
        self.testName = 'Switch2'
        self.label = " switch times"
        self.clocks = None
        rowTime = 7925.920 * 1e-6
        pixTime = 13.920 * 1e-6
        self.delayTime = (0 * rowTime +  0 * pixTime)
        
    def setup(self):
        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=20e-9, # recordLength=1000000,
                               triggerPos=0.2,
                               delayMode=1, delayTime=self.delayTime / 1e-6, delayUnits='us')

        self.scope.setEdgeTrigger(level=1.3, slope='rise', holdoff='10e-6')

        self.scope.setWaveform(1, 'DCR', scale=1.0)
        self.scope.setWaveform(2, 'IR', scale=1.0)
        self.scope.setWaveform(3, 'ampout', scale=0.5)
        self.scope.setWaveform(4, '', scale=5)

    def setClocks(self, clocks=None):
        if clocks is None:
            import clocks.read

            pre, pix, post = clocks.read.readClocks()
            clocks = np.array(pix.ticks) * pix.tickTime
            
        self.clocks = clocks
        print "clocks: %s" % (self.clocks)
        
    def plot(self, channels=[0,1]):
        #self.setClocks()
        xscale = 1e-6
        fig, pl = sigplot(self.testData['waveforms'], xscale=xscale,
                          channels=range(3),
                          offsets=[0,0,0,-10],
                          noWide=False,
                          # xoffset=self.delayTime,
                          ylim=(-0.25,0.5),
                          #xlim=(-1.0,15),
                          #clocks=self.clocks,
                          showLimits=False, title=self.title)
        for p in pl:	
#            p.set_xticks(np.arange(0,pixTime,1000)/1000.0)
#            p.set_xticks(np.arange(0,pixTime,200)/1000.0, minor=True)
            p.grid(which='major', alpha=0.7)
            p.grid(which='minor', alpha=0.2)
                
                
        return fig, pl

class xxV0Test(OneTest):
    def initTest(self):
        self.testName = 'V0'
        self.label = "bias voltages over an exposure."

    def setup(self):
        self.scope.setWaveform(1, 'OG', scale=5)
        self.scope.setWaveform(2, 'RD', scale=5)
        self.scope.setWaveform(3, 'OD', scale=5)
        self.scope.setWaveform(4, 'BB', scale=5)

        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=1, pos=20, triggerPos=10, delayMode=0, delayTime=0)
        self.scope.setManualTrigger(after=6.0)

    def plot(self):
        return sigplot(self.testData['waveforms'], xscale=1.0, 
                       ylim=(-20,20), 
                       showLimits=True, title=self.title)        

class xxV1Test(OneTest):
    def initTest(self):
        self.testName = 'V1'
        self.label = "slew between modes, no clocking"

    def setup(self):
        self.scope.setWaveform(1, 'OG', scale=5)
        self.scope.setWaveform(2, 'RD', scale=5)
        self.scope.setWaveform(3, 'OD', scale=5)
        self.scope.setWaveform(4, 'BB', scale=5)

        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=1, pos=5, triggerPos=5, delayMode=0, delayTime=0)
        self.scope.setEdgeTrigger(source='ch3', level=-8, slope='fall', holdoff='1e-9')


    def plot(self):
        return sigplot(self.testData['waveforms'], xscale=1.0, 
                       xlim=(-0.5,5.0), ylim=(-20,20), 
                       showLimits=True, title=self.title)        

def sigplot(waves,
            channels=None,
            offsets=None,
            ylim=None, xlim=None, 
            noWide=False, doNorm=False,
            xscale=1e-6, showLimits=False, 
            xoffset=0,
            clocks=None,
            title=None):

    if channels is None:
        channels = range(4)
    if offsets is None:
        offsets = np.zeros(4)
        
    colors = waveColors
    
    if noWide:
        fig, plist = plt.subplots(nrows=1, figsize=(14, 6))
        p0 = plist
    else:
        fig, plist = plt.subplots(nrows=2, figsize=(14, 12))
        p0, p1 = plist

    if xlim is not None:
        xdatalim = np.array(xlim) * xscale
    else:
        xdatalim = None
    #xoffset *= xscale
    for i in channels:
        chan = waves['ch%d' % (i+1)]
        x = chan['x']
        print "x %d: %g %g %s %s %s" % (i, x.min(), x.max(), xoffset, xlim, xdatalim) 
        x = x - xoffset
        if xlim is not None:
            xslice = (x >= xdatalim[0]) & (x <= xdatalim[1])
        else:
            xslice = slice(None, None)
        y = chan['data'] + offsets[i]

        if doNorm:
            y = y - y.mean()
        label = chan['label']
        if offsets[i] < 0:
            label = label + " - %g" % (-offsets[i])
        elif offsets[i] > 0:
            label = label + " + %g" % (offsets[i])
        p0.plot(x[xslice]/xscale, y[xslice], 
                color=colors[i], label=label)
        if not noWide:
            p1.plot(x/xscale, y, 
                    color=colors[i], label=label)
            p1.set_xlabel('%s sec' % (xscale))
        if showLimits:
            w = np.argmax(y[xslice])
            p0.plot(x[xslice][w]/xscale, y[xslice][w], 'o', color=colors[i])
            w = np.argmin(y[xslice])
            p0.plot(x[xslice][w]/xscale, y[xslice][w], 'o', color=colors[i])

    if ylim is not None:
        p0.set_ylim(ylim[0], ylim[1])
    if xlim is not None:
        p0.set_xlim(xlim[0], xlim[1])
        
        
    for c in (clocks if clocks is not None else []):
        c = c * 1e-9 / xscale
                
        print("vline @ %g" % (c))
        p0.axvline(c,
                   alpha=0.5,color='r',linestyle='dot')
            
    p0.legend(bbox_to_anchor=(1, 1), loc=2, borderaxespad=0.)
    p0.set_xlabel('%s sec' % (xscale))
    p0.set_ylabel('V')
    p0.grid()
    
    if title:
        p0.set_title(title, loc='center')

    return fig, plist

def clockplot(fig, plot, waves, clocks):
    pass


