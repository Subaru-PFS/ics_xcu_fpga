from __future__ import absolute_import, division

import collections
import re

import numpy as np
import matplotlib.pyplot as plt
import cPickle as pickle
import shutil
import subprocess
import time

import logging
import os

import astropy.io.fits as pyfits
from matplotlib.backends.backend_pdf import PdfPages

from fpga import SeqPath
from fpga import ccdFuncs
from fpga import nbFuncs

from . import pfsScope
reload(pfsScope)

from . import scopeMux
reload(scopeMux)

waveColors = ('#c0c000', 'cyan', 'magenta', '#00bf00')

class TestRig(object):
    def __init__(self, dirName=None, seqno=None, root='/data/pfseng'):
        self.rootDir = root
        self.fileMgr = SeqPath.NightFilenameGen(root,
                                                filePrefix='xx',
                                                filePattern="%(seqno)06d")

        self.scope = None
        self.mux = None
        
        self.seqno = seqno
        self.dirName = dirName

        if dirName is not None and seqno is not None:
            self.loadSet(dirName, seqno)
        elif dirName is None and seqno is None:
            self.newSet()
        else:
            raise RuntimeError("both dirName and seqno must be set, or neither")

        self.newScope()
        self.newMux()

        self.sequence = []
        self.pdf = None
        
    def __str__(self):
        return "%s(seqno=%s, dirName=%s, %d tests)" % (self.__class__.__name__,
                                                       self.seqno,
                                                       self.dirName,
                                                       len(self.sequence))

    def __del__(self):
        self.close()

    def close(self):
        if self.pdf is not None:
            self.pdf.close()
            self.pdf = None
            
        print "deleting mux...."
        if self.mux is not None:
            self.mux.mux.close()
        del self.mux
        self.mux = None
        
    def newScope(self):
        reload(pfsScope)

        if self.scope is not None:
            del self.scope
            self.scope = None
            
        self.scope = pfsScope.PfsCpo()
        self.scope.setProbes()
        
    def newMux(self):
        reload(scopeMux)

        if self.mux is not None:
            self.mux.mux.close()
            del self.mux
            self.mux = None
            
        self.mux = scopeMux.ScopeMux()
        
    def loadSet(self, dirName, seqno):
        self.seqno = seqno
        dirName = os.path.join(self.fileMgr.rootDir, dirName)
        self.dirName = self.fileMgr.namesFunc(dirName, seqno)

        self.seqNum = 0
        
    def newSet(self):
        if self.seqno is not None:
            raise RuntimeError("this test set has already been created")

        seqno, dirName = self.fileMgr.genNextSet()
        self.seqno = seqno
        self.dirName = dirName
        self.utday = os.path.split(dirName)[-2]
        os.makedirs(self.dirName, mode=02775)

        self.seqNum = 0

class BenchRig(TestRig):
    leadNames = dict(C1='OG',
                     C2='RD',
                     
                     C4='RG',
                     C5='S1',
                     C6='S1.2',
                     C7='S2',
                     C8='S2.2',
                     C9='SW',
                     C10='OS',
                     C11='OD',
                     
                     M1='ISV',
                     M2='IG1',
                     M3='IG2',
                     M4='P1',
                     M5='P2',
                     M6='P3',
                     M7='P1S',
                     M8='P2S',
                     M9='P3S',
                     M10='TG',
                     M11='BB')

    leadPins = {v:k for k,v in leadNames.items()}
    
    def __init__(self, dewar=None, **argd):
        """ a collection of tests to qualify PFS CCD ADCs

        By default, creates a new, empty test rig and directory.

        Args
        ----
        dewar : str
          Name of piepan/dewar we are running on (default=b9)

        """

        TestRig.__init__(self, **argd)

        if dewar is None:
            dewar = 'b9'
        self.dewar = dewar
        
        self.sequence = [[0, 0, SanityTest, None],
                         
                         [0, 0, None, 'switch MUX leads to CCD0, amp 0 (1 is unused)'],
                         [0, 0, V0Test, None],
                         [0, 0, S0Test, None],
                         [0, 0, P0Test, None],

                         [0, 0, None, 'insert terminators into all amp channels'],
                         [0, 0, ReadnoiseTest, None],

                         [1, 0, None, 'switch MUX leads to CCD1, amps 0,1'],
                         [1, 0, V0Test, None],
                         [1, 0, S0Test, None],
                         [1, 0, P0Test, None],
                         [1, 0, P1Test, None],
                         [1, 0, S1Test, None],
                         [1, 1, V0Test, None],
                         [1, 1, S0Test, None],
                         [1, 1, S1Test, None],
                         [1, 0, P2Test, None],

                         [1, 0, None, 'switch MUX leads to CCD1, amps 2,3'],
                         [1, 2, V0Test, None],
                         [1, 2, S0Test, None],
                         [1, 2, S1Test, None],
                         [1, 3, V0Test, None],
                         [1, 3, S0Test, None],
                         [1, 3, S1Test, None],

                         [0, 0, None, 'switch MUX leads to CCD0, amps 0,1'],
                         [0, 0, P1Test, None],
                         [0, 0, S1Test, None],
                         [0, 1, V0Test, None],
                         [0, 1, S0Test, None],
                         [0, 1, S1Test, None],

                         [0, 0, None, 'switch MUX leads to CCD0, amps 2,3'],
                         [0, 2, V0Test, None],
                         [0, 2, S0Test, None],
                         [0, 2, S1Test, None],
                         [0, 3, V0Test, None],
                         [0, 3, S0Test, None],
                         [0, 3, S1Test, None],
                         [0, 3, P2Test, None],
        ]

        self.ccd = None
        self.amp = None

    def __str__(self):
        """ describe all our tests and where the test pointer is. """
        
        superStr = TestRig.__str__(self)

        return "%s\n\n%s" % (superStr, self.describeSequence())
    
    def describeTest(self, seqNum=None, withLeads=True):
        if seqNum is None:
            seqNum = self.seqNum
        ccd, amp, test, comment = self.sequence[seqNum]

        if comment is None:
            comment = "%s [ccd %d, amp %d]: %s" % (test.testName,
                                                   ccd, amp,
                                                   test.label)

        fullComment = "%-2d %s %s" % (seqNum, "**" if seqNum == self.seqNum else "  ", comment)
        if test is None:
            return fullComment
        
        if withLeads:
            fullComment = "%s\n     leads: %s" % (fullComment,
                                                  test.describeLeads())
            
        return fullComment

    def describeSequence(self):
        retList = []
        for s_i in range(len(self.sequence)):
            retList.append(self.describeTest(s_i, withLeads=False))

        return '\n'.join(retList)
                           
    def setTest(self, seqNum):
        """set the sequence number of the next test to run.

        Args
        ----
        seqNum : int
           0-based index to the next test to run.
           print() this object to see the sequence and pointer.
        """

        if seqNum < 0 or seqNum >= len(self.sequence):
            raise IndexError('test number must be 0..%d' % (len(self.sequence)))
        
        self.seqNum = seqNum
        return self.describeTest()

    def incrTest(self, incr=1):
        """relatively move the index of the next test to run.

        Args
        ----
        incr : int
           how much to move the index. (default=next)
        """

        return self.setTest(self.seqNum + incr)
        
    def configMux(self, ccd, amp, test):
        if self.mux is None:
            self.mux = scopeMux.ScopeMux()
            self.ccd = None
            self.amp = None
            
        if self.ccd != ccd or amp//2 != self.amp//2:
            plist = test.leadNames()
            if plist:
                self.mux.setProbes(plist, amp//2 + 1)

    def runTest(self, noRun=False, trigger=None):
        """ run the current test

        Args
        ----
        noRun : bool
          If True, only print what we would do.
        trigger : dict
          Override the scope trigger for the test. Always is an edge trigger.
          See, say, S0Test for an example, but you need to set:
           source='chN' : the channel (N=1..4)
           level=V : the trigger voltage
           slope='rise'/'fall' : the trigger direction through the level.
        """
        
        ccd, amp, testClass, comment = self.sequence[self.seqNum]

        if testClass is None:
            print("You need to %s" % (comment))
            self.seqNum += 1
            return True
        
        print("configuring MUX for %s%s\n" % (self.describeTest(), ("" if not comment else " (%s)" % comment)))

        test = testClass(self, ccd, amp,
                         dewar=self.dewar,
                         comment=comment)
        self.configMux(ccd, amp, test)

        print("running %s%s\n" % (self.describeTest(withLeads=False), ("" if not comment else " (%s)" % comment)))

        if noRun:
            print("skipping actual scope run!")
            return True

        try:
            if hasattr(test, 'runTest'):
                ret = test.runTest(test)
            else:
                ret = self.scope.runTest(test, trigger=trigger)
        except Exception as e:
            print("test FAILED: %s" % (e))
            return False

        test.save()
        ret = test.plot()
        fig, pl = ret
        basePath, _ = os.path.splitext(test.fullPath)
        pdfPath = "%s.pdf" % (basePath)

        if fig is not None:
            if self.pdf is None:
                self.pdf = PdfPages(os.path.join(self.dirName, 'report-%0.5d.pdf' % (self.seqno)))

            fig.savefig(pdfPath)
            self.pdf.savefig(fig)
            print("PDF is at %s" % (pdfPath))

        self.seqNum += 1
        
        return test

    def runBlock(self, noRun=False, muxOK=False):
        """ run tests until failure or the next MUX reconfiguration

        Args
        ---
        noRun : bool
          if True, only print what we would do.
        muxOK: bool
          if True and we start at a MUX reconfiguration step, assume
          that the MUX has already been configured, and skip that step.

        """
        ccd, amp, testClass, comment2 = self.sequence[self.seqNum]
        if testClass is None and muxOK:
            self.incrTest()

        while True:
            ccd, amp, testClass, comment2 = self.sequence[self.seqNum]
            if testClass is None:
                print("MUX reconfiguration: you need to %s" % (comment2))
                return True

            ret = self.runTest(noRun=noRun)
            if ret is False:
                print("STOPPING at failed test.")
                return
        
                
class OneTest(object):
    def __init__(self, rig, channel, amp, ccd='X', comment='', dewar=None, revision=1):
        self.logger = logging.getLogger('testrig')
        self.logger.setLevel(logging.INFO)
        
        self.dewar = dewar
        self.initTest()

        self.rig = rig
        self.channel = channel
        self.ccd = ccd
        self.amp = amp
        self.comment0 = comment
        self.testData = None
        self.delayTime = 0
        
        self.revision = revision

    @classmethod
    def leadNames(self, leads=None):
        if isinstance(self.leads, str):
            return []

        if leads is None:
            leads = self.leads
        return [BenchRig.leadPins[l] for l in leads]
    
    @classmethod
    def describeLeads(self):
        if isinstance(self.leads, str):
            return self.leads
        
        leads = [("%s(%s)" % (l, BenchRig.leadPins[l])) for l in self.leads]
        return ", ".join(leads)
    
    @property
    def scope(self):
        return self.rig.scope

    def initTest(self):
        pass
    
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

    @property
    def fullPath(self):
        dirName = self.rig.dirName
        name = self.fullName()
        path = os.path.join(dirName, "%s.pck" % (name))

        return path
        
    def newPath(self):
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

        path = self.newPath()
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
        try:
            testData = dict()
            testData['version'] = 2
            testData['waveforms'] = self.scope.getWaveforms()
        except Exception as e:
            raise e

        self.testData = testData

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

        return sigplot(self.testData['waveforms'], xscale=1.0, noWide=True, 
                       showLimits=True, title=self.title)

    @property
    def title(self):
        return "Test %s, amp %s/%s run %s/%04d, rev %02d: %s" % (self.testName,
                                                                 self.channel, self.amp,
                                                                 self.rig.utday, self.rig.seqno,
                                                                 self.revision,
                                                                 self.label)
def oneCmd(actor, cmdStr, doPrint=True):
    fullCmdStr = "oneCmd.py %s %s" % (actor, cmdStr)

    output = subprocess.check_output(fullCmdStr, shell=True, universal_newlines=True)
    p = subprocess.Popen(fullCmdStr, shell=True, bufsize=1,
                         universal_newlines=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    output = []
    while True:
        p.poll()
        if p.returncode is not None:
            break
        l = p.stdout.readline()
        if not l:
            break
        if doPrint:
            print l.strip()

        output.append(l)

    return output

def getCardValue(cards, name, cnv=None):
    cardRe = re.compile(' ([wi:f]) (%s)=(.*)' % (name))

    for c in cards:
        m = re.search(cardRe, c)
        if m is not None:
            flag = m.group(1)
            val = m.group(3)
            if val.startswith('"') or val.startswith("'"):
                val = val[1:-1]
            if cnv:
                val = cnv(val)
            return flag, val
        
    raise KeyError('%s not found in cards' % (name))

class FakeCcd(object):
    def ampidx(self, ampid, im=None):
        if im is not None:
            nrows, ncols = im.shape
                
        ampCols = ncols / 8
        # return slice(ampCols*ampid, ampCols*(ampid+1))
        return np.arange(ampCols*ampid, ampCols*(ampid+1), dtype='i4')
    
class SanityTest(OneTest):
    testName = 'Sanity'
    label = 'serials and voltages'
    leads = ''
    timeout = 30
    
    def initTest(self):
        pass

    def setup(self, trigger=None):
        pass

    @staticmethod
    def asciiCnv(val):
        return val.decode('ascii')
                
    @staticmethod
    def base10Cnv(val):
        return int(val, base=10)
        
    def checkSerials(self, cards):
        """ Check all chain serial numbers, etc. """
        
        errors = []

        for n in 'fee', 'adc', 'pa0':
            try:
                flag, numVal = getCardValue(cards, 'serial_%s' % (n), self.base10Cnv)
            except KeyError:
                errors.append(n)
                self.logger.warning('could not get serial ID for %s', n)
                continue
            except ValueError:
                errors.append(n)
                flag, rawVal = getCardValue(cards, 'serial_%s' % (n))
                self.logger.warning('serial ID for %s is not an integer: %s', n, rawVal)
                continue

            if numVal == 2**32 - 1:
                errors.append(n)
                self.logger.warning('serial ID for %s has not been set: %s', n, numVal)
                continue

            self.logger.info('OK %s serial: %s', n, numVal)
            
        for n in 'ccd0', 'ccd1':
            try:
                flag, asciiVal = getCardValue(cards, 'serial_%s' % (n), self.asciiCnv)
            except KeyError:
                errors.append(n)
                self.logger.warning('could not get serial ID for %s', n)
                continue
            except UnicodeDecodeError:
                errors.append(n)
                flag, rawVal = getCardValue(cards, 'serial_%s' % (n))
                self.logger.warning('serial ID for %s is garbage or has not been set: %r', n, rawVal)
                continue

            self.logger.info('OK %s serial: %s', n, asciiVal)

        for error in errors:
            self.logger.critical('MUST set %s serial number with: !oneCmd.py ccd_%s fee setSerials %s=VALUE',
                                 error, self.dewar, error.upper())

        return len(errors) == 0

    def checkVoltages(self, cards):

        Voltage = collections.namedtuple('Voltage', ['name', 'nominal', 'lo', 'hi'])
        vlist = [
            Voltage(name='3v3m', nominal=3.3, lo=0.02, hi=0.02),
            Voltage(name='3v3', nominal=3.3, lo=0.02, hi=0.02),
            Voltage(name='5vp', nominal=5.0, lo=0.03, hi=0.03),
            Voltage(name='5vn', nominal=-5.0, lo=0.02, hi=0.02),
            Voltage(name='5vppa', nominal=5.0, lo=0.02, hi=0.02),
            Voltage(name='5vnpa', nominal=-5.0, lo=0.02, hi=0.02),
            Voltage(name='12vp', nominal=12.0, lo=0.03, hi=0.03),
            Voltage(name='12vn', nominal=-12.0, lo=0.04, hi=0.04),
            Voltage(name='24vn', nominal=-24.0, lo=0.05, hi=0.05),
            Voltage(name='54vp', nominal=54.0, lo=0.10, hi=0.10),
        ]
        errors = []

        for v in vlist:
            try:
                flag, numVal = getCardValue(cards, 'voltage_%s' % (v.name), float)
            except KeyError:
                errors.append(v.name)
                self.logger.warning('could not get measured voltage %s', v.name)
                continue
            except ValueError:
                errors.append(v.name)
                flag, rawVal = getCardValue(cards, 'voltage_%s' % (v.name))
                self.logger.warning('voltage %s is not a float: %s', v.name, rawVal)
                continue

            loLimit = v.nominal - v.nominal*v.lo
            hiLimit = v.nominal + v.nominal*v.hi
            if loLimit > hiLimit:
                loLimit, hiLimit = hiLimit, loLimit
                
            if numVal < loLimit or numVal > hiLimit:
                errors.append(v.name)
                self.logger.warning('voltage %s is out of range %0.3fV vs. [%0.3fV, %0.3fV]',
                                    v.name, numVal, loLimit, hiLimit)
                continue

            self.logger.info('OK voltage %s: %0.3fV (%0.1fV %+0.1f%%)',
                             v.name, numVal, v.nominal, 100*(numVal/v.nominal - 1))

        for error in errors:
            self.logger.critical('FIX voltage %s', error)

        return len(errors) == 0

    def runTest(self, trigger=None):
        cards = oneCmd('ccd_%s' % (self.dewar), '--level=i fee status', doPrint=False)
        if not self.checkSerials(cards):
            raise RuntimeError('serial number checks failed!')
        if not self.checkVoltages(cards):
            raise RuntimeError('voltage checks failed!')
            
    def fetchData(self):
        pass
    
    def save(self, comment=''):
        pass
    
    def plot(self, fitspath=None):
        return None, None

class ReadnoiseTest(OneTest):
    testName = 'Readnoise'
    label = "terminated readout"
    leads = 'terminators only'
    timeout = 30
    
    def initTest(self):
        pass

    def setup(self, trigger=None):
        pass

    def runTest(self, trigger=None):
        self.logger.info("calling for a wipe")
        oneCmd('ccd_%s' % (self.dewar), 'wipe')
        self.logger.info("done with wipe")
        self.logger.info("calling for a read")
        output = oneCmd('ccd_%s' % (self.dewar), 'read bias nrows=500 ncols=500')

        # 2017-04-07T15:12:36.223 ccd_b9 i filepath=/data/pfs,2017-04-07,PFJA00775691.fits
        self.fitspath = None
        for l in output:
            m = re.search('.*filepath=(.*\.fits).*', l)
            if m:
                pathparts = m.group(1)
                self.fitspath = os.path.join(*pathparts.split(','))
                print("set filepath to: %s" % self.fitspath)
            
    def fetchData(self):
        pass
    
    def save(self, comment=''):
        if self.fitspath is not None:
            shutil.copy(self.fitspath, os.path.join(self.rig.dirName,
                                                    os.path.basename(self.fitspath)))
    
    def plot(self, fitspath=None):
        if fitspath is None:
            fitspath = self.fitspath
        plt.ioff()
        im = pyfits.getdata(fitspath)
        fig, gs = nbFuncs.rawAmpGrid(im, FakeCcd(),
                                     title=fitspath,
                                     cols=slice(50,None))
        return fig, gs


class V0Test(OneTest):
    testName = 'V0'
    label = "power up, all modes, power off"
    leads = ('OG', 'RD', 'OD', 'BB')
    timeout = 30
    
    def triggerCB(self):
        print("trigger set, call for read...")
        subprocess.call('oneCmd.py ccd_%s test V0' % (self.dewar), shell=True)
        time.sleep(1)
        subprocess.call('oneCmd.py xcu_%s power on fee' % (self.dewar), shell=True)
        time.sleep(3.5)
        subprocess.call('oneCmd.py ccd_%s connect controller=fee' % (self.dewar), shell=True)
        time.sleep(1.1)
    
    def initTest(self):
        self.delayTime = 0 # 13.920*1e-6 * 10

    def setup(self, trigger=None):
        self.scope.setWaveform(1, 'OG', scale=5)
        self.scope.setWaveform(2, 'RD', scale=5)
        self.scope.setWaveform(3, 'OD', scale=5)
        self.scope.setWaveform(4, 'BB', scale=5)

        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=2.0, pos=10, triggerPos=10, delayMode=0, delayTime=0)
        if trigger is None:
            self.scope.setEdgeTrigger(source='ch3', level=-2.0, slope='fall', holdoff='1e-9')
        else:
            self.scope.setEdgeTrigger(**trigger)

        print("powering FEE down....")
        subprocess.call('oneCmd.py xcu_%s power off fee' % (self.dewar), shell=True)
        time.sleep(1.1)

    def plot(self):
        return sigplot(self.testData['waveforms'], xscale=1.0, 
                       xlim=(-1,15), ylim=(-20,20), 
                       showLimits=True, title=self.title)        

class S0Test(OneTest):
    testName = 'S0'
    label = "main serial clocks"
    leads = ('RG', 'S1', 'S2', 'SW')
    timeout = 15
    
    def triggerCB(self):
        print("trigger set, call for read...")
        subprocess.call('oneCmd.py ccd_%s test SP' % (self.dewar), shell=True)
        
    def setup(self, trigger=None):
        self.scope.setAcqMode(numAvg=0)
        self.delayTime = 13.920*1e-6 * 10
        self.scope.setSampling(scale=200e-9, pos=50, triggerPos=20, delayMode=1, delayTime=self.delayTime)
        if trigger is None:
            self.scope.setEdgeTrigger(source='ch3',
                                      level=2.0, slope='fall', holdoff='10e-6')
        else:
            self.scope.setEdgeTrigger(**trigger)

        # C4 C5 C7 C9
        self.scope.setWaveform(1, 'RG', scale=2)
        self.scope.setWaveform(2, 'S1', scale=2)
        self.scope.setWaveform(3, 'S2', scale=2)
        self.scope.setWaveform(4, 'SW', scale=2)

        subprocess.call('oneCmd.py ccd_%s fee setMode read' % (self.dewar), shell=True)
        time.sleep(1.1)

        
    def plot(self):
        return sigplot(self.testData['waveforms'], xscale=1e-6,
                       noWide=False,
                       xlim=(-0.5,14),
                       ylim=(-8,4), 
                       showLimits=True, title=self.title)        

class S1Test(OneTest):
    testName = 'S1'
    label = "alternate serial clocks"
    leads = ('RG', 'S1.2', 'S2.2', 'OS')
    timeout = 15
    
    def triggerCB(self):
        print("trigger set, call for read...")
        subprocess.call('oneCmd.py ccd_%s test SP' % (self.dewar), shell=True)
        
        
    def setup(self, trigger=None):
        self.scope.setAcqMode(numAvg=1)
        self.delayTime = 13.920*1e-6 * 10
        self.scope.setSampling(scale=200e-9, pos=50, triggerPos=20, delayMode=1, delayTime=self.delayTime)
        if trigger is None:
            self.scope.setEdgeTrigger(source='ch3',
                                      level=2, slope='fall', holdoff='10e-6')
        else:
            self.scope.setEdgeTrigger(**trigger)

        # C4 C6 C8 C10
        self.scope.setWaveform(1, 'RG', scale=2)
        self.scope.setWaveform(2, 'S1.2', scale=2)
        self.scope.setWaveform(3, 'S2.2', scale=2)
        self.scope.setWaveform(4, 'OS', scale=2)

        subprocess.call('oneCmd.py ccd_%s fee setMode read' % (self.dewar), shell=True)
        time.sleep(1.1)
    
    def plot(self):
        return sigplot(self.testData['waveforms'], xscale=1e-6,
                       noWide=False,
                       xlim=(-0.5,14), ylim=(-8,4), 
                       showLimits=True, title=self.title)        

class P0Test(OneTest):
    testName = 'P0'
    label = "main parallel clocks"
    leads = ('TG', 'P1', 'P2', 'P3')
    timeout = 15
    
    def triggerCB(self):
        print("trigger set, call for read...")
        subprocess.call('oneCmd.py ccd_%s test SP' % (self.dewar), shell=True)
        

    def setup(self, trigger=None):
        self.scope.setWaveform(1, 'TG', scale=5)
        self.scope.setWaveform(2, 'P1', scale=2)
        self.scope.setWaveform(3, 'P2', scale=2)
        self.scope.setWaveform(4, 'P3', scale=2)

        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=50e-6, pos=50, triggerPos=20, delayMode=0, delayTime=120e-6)

        if trigger is None:
            self.scope.setEdgeTrigger(level=0.0, slope='fall', holdoff='250e-6')
        else:
            self.scope.setEdgeTrigger(**trigger)

        subprocess.call('oneCmd.py ccd_%s fee setMode read' % (self.dewar), shell=True)
        time.sleep(1.1)
        
    def plot(self):
        return sigplot(self.testData['waveforms'], xscale=1e-6,
                       xlim=(-50,250), ylim=(-7,7),
                       xoffset=-40e-6,
                       showLimits=True, title=self.title)        

class P1Test(OneTest):
    testName = 'P1'
    leads = ('TG', 'P1S', 'P2S', 'P3S')
    label = "storage parallel clocks"
    timeout = 15
    
    def triggerCB(self):
        print("trigger set, call for read...")
        subprocess.call('oneCmd.py ccd_%s test SP' % (self.dewar), shell=True)
        

    def setup(self, trigger=None):
        self.scope.setWaveform(1, 'TG', scale=5)
        self.scope.setWaveform(2, 'P1S', scale=2)
        self.scope.setWaveform(3, 'P2S', scale=2)
        self.scope.setWaveform(4, 'P3S', scale=2)

        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=50e-6, pos=50, triggerPos=20, delayMode=0, delayTime=120e-6)

        if trigger is None:
            self.scope.setEdgeTrigger(level=-2.0, slope='fall', holdoff='250e-6')
        else:
            self.scope.setEdgeTrigger(**trigger)
        
        subprocess.call('oneCmd.py ccd_%s fee setMode read' % (self.dewar), shell=True)
        time.sleep(1.1)

    def plot(self):
        return sigplot(self.testData['waveforms'], xscale=1e-6,
                       xlim=(-50,250), ylim=(-7,7), 
                       showLimits=True, title=self.title)        

class P2Test(OneTest):
    testName = 'P2'
    leads = ('TG', 'ISV', 'IG1', 'IG2')
    label = "strays"
    timeout = 15
    
    def triggerCB(self):
        print("trigger set, call for read...")
        subprocess.call('oneCmd.py ccd_%s test SP' % (self.dewar), shell=True)
        

    def setup(self, trigger=None):
        self.scope.setWaveform(1, 'TG', scale=2)
        self.scope.setWaveform(2, 'ISV', scale=2)
        self.scope.setWaveform(3, 'IG1', scale=5)
        self.scope.setWaveform(4, 'IG2', scale=5)

        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=50e-6, pos=50, triggerPos=20, delayMode=0, delayTime=120e-6)

        self.scope.setEdgeTrigger(level=-2.0, slope='fall', holdoff='250e-6')

        if trigger is None:
            subprocess.call('oneCmd.py ccd_%s fee setMode read' % (self.dewar), shell=True)
        else:
            self.scope.setEdgeTrigger(**trigger)
            
        time.sleep(1.1)
        
    def plot(self):
        return sigplot(self.testData['waveforms'], xscale=1e-6,
                       xlim=(-50,250), ylim=(-7,7), 
                       showLimits=True, title=self.title)        

class Switch1Test(OneTest):
    def initTest(self):
        self.testName = 'Switch1A'
        self.label = " switch times"
        self.clocks = None
        rowTime = 7925.920 * 1e-6
        self.pixTime = 13.920 * 1e-6
        self.delayTime = (0 * rowTime +  0 * self.pixTime)
        
    def setup(self, trigger=None):
        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=20e-9, # recordLength=1000000,
                               triggerPos=20,
                               delayMode=1, delayTime=self.delayTime / 1e-6, delayUnits='us')

        if trigger is None:
            self.scope.setEdgeTrigger(source='ch2', level=1.3, slope='rise', holdoff='10e-6')
        else:
            self.scope.setEdgeTrigger(**trigger)

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
        
    def setup(self, trigger=None):
        self.scope.setAcqMode(numAvg=0)
        self.scope.setSampling(scale=20e-9, # recordLength=1000000,
                               triggerPos=0.2,
                               delayMode=1, delayTime=self.delayTime / 1e-6, delayUnits='us')

        if trigger is None:
            self.scope.setEdgeTrigger(level=1.3, slope='rise', holdoff='10e-6')
        else:
            self.scope.setEdgeTrigger(**trigger)

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
        # print "x %d: %g %g %s %s %s" % (i, x.min(), x.max(), xoffset, xlim, xdatalim) 
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

    plt.ioff()
    fig.show()
    
    return fig, plist

def clockplot(fig, plot, waves, clocks):
    pass


