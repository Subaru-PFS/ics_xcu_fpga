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

from fpga import SeqPath
from fpga import nbFuncs

from . import pfsScope
from . import scopeMux

reload(pfsScope)
reload(scopeMux)

# Configure the default formatter and logger.
logging.basicConfig(datefmt = "%Y-%m-%d %H:%M:%S",
                    format = "%(asctime)s.%(msecs)03dZ %(name)-16s %(levelno)s %(filename)s:%(lineno)d %(message)s")
logging.getLogger().setLevel(logging.INFO)

waveColors = ('#c0c000', 'cyan', 'magenta', '#00bf00')

class TestRig(object):
    def __init__(self, dirName=None, seqno=None, root='/data/pfseng'):
        self.logger = logging.getLogger('testrig')
        self.logger.setLevel(logging.INFO)

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

    # per-amp bias levels measured with the bench fake CCD, which
    # should always be the same, well within 1%.
    #
    expectedLevels = (6200, 5050, 3725, 2570,
                      6140, 5010, 4000, 2630)
    
    def __init__(self, dewar=None, sequence=None, **argd):
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

        if sequence is None:
            sequence = 'full'

        if sequence == 'full':
            self.sequence = [[0, 0, SanityTest, None],

                             [0, 0, None, 'insert terminators into all amp channels'],
                             [0, 0, OffsetTest, None],
                             [0, 0, ReadnoiseTest, None],
                             # [0, 0, WalkOffsets, None],
                             
                             [0, 0, None, 'switch MUX leads to CCD0, amp 0 (1 is unused)'],
                             [0, 0, V0Test, None],
                             [0, 0, S0Test, None],
                             [0, 0, P0Test, None],

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
                             [0, 0, None, None],
            ]
        elif sequence == 'short':
            self.sequence = [[0, 0, SanityTest, None],
                             [0, 0, OffsetTest, None],
                             [0, 0, ReadnoiseTest, None]]
        else:
            raise RuntimeError('unknown rig type')
        
            
        self.ccd = None
        self.amp = None

        self._frontPage = None
        
    def __str__(self):
        """ describe all our tests and where the test pointer is. """
        
        superStr = TestRig.__str__(self)

        return "%s\n\n%s" % (superStr, self.describeSequence())

    def setSerials(self, PA0=None, ADC=None, CCD0=None, CCD1=None):
        serials = dict(PA0=PA0, ADC=ADC, CCD0=CCD0, CCD1=CCD1)

        self.powerDown()
        self.powerUp()
        time.sleep(1.1)
        
        for s in serials.keys():
            if serials[s] is not None:
                oneCmd('ccd_%s' % (self.dewar), 'fee setSerials %s=%s' % (s, serials[s]))
                
    def setVoltageCalibrations(self, 
                               v3V3M=None, v3V3=None,
                               v5VP=None, v5VN=None, v5VPpa=None, v5VNpa=None,
                               v12VP=None, v12VN=None, v24VN=None, v54VP=None):
        import inspect

        argvals = inspect.getargvalues(inspect.currentframe())
        
        cmdArgs = ["%s=%s" % (arg, argvals.locals[arg]) for arg in argvals.args if arg not in {'self'}]
        oneCmd('ccd_%s' % (self.dewar), 'fee setVoltageCalibrations %s' % (' '.join(cmdArgs)), doPrint=False)
                
    def calibrateFee(self):
        subprocess.call('oneCmd.py ccd_%s fee calibrate' % (self.dewar), shell=True)

    def powerDown(self):
        subprocess.call('oneCmd.py xcu_%s power off fee' % (self.dewar), shell=True)
        time.sleep(1.1)

    def powerUp(self, delay=3.5):
        subprocess.call('oneCmd.py xcu_%s power on fee' % (self.dewar), shell=True)
        time.sleep(delay)
        subprocess.call('oneCmd.py ccd_%s connect controller=fee' % (self.dewar), shell=True)
        time.sleep(1.1)
            
    def burnFee(self):
        feePath = "/home/pfs/fee/current.hex"
        print "downloading fee firmware....."
        self.powerDown()
        subprocess.call('oneCmd.py ccd_%s connect controller=fee' % (self.dewar), shell=True)
        time.sleep(1.1)
        subprocess.call('oneCmd.py xcu_%s power on fee' % (self.dewar), shell=True)
        time.sleep(1.1)
        
        oneCmd('ccd_%s' % (self.dewar), '--level=d fee download pathname="%s"' % (feePath))
        print "done downloading fee firmware, we hope...."

        self.powerDown()
        self.powerUp()
        
    def describeTest(self, seqNum=None, withLeads=True):
        if seqNum is None:
            seqNum = self.seqNum
        ccd, amp, test, comment = self.sequence[seqNum]

        if comment is None and test is None:
            return "Done"

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

    def runTest(self, test=None, noRun=False, trigger=None, **testArgs):
        """ run the current test

        Args
        ----
        test : int
          If set, jump to that test
        noRun : bool
          If True, only print what we would do.
        trigger : dict
          Override the scope trigger for the test. Always is an edge trigger.
          See, say, S0Test for an example, but you need to set:
           source='chN' : the channel (N=1..4)
           level=V : the trigger voltage
           slope='rise'/'fall' : the trigger direction through the level.
        """

        if test is not None:
            self.seqNum = test
        ccd, amp, testClass, comment = self.sequence[self.seqNum]

        if testClass is None:
            if comment is None:
                self.finishFullRig()
                self.seqNum += 1
                return True
            
            print("You need to %s" % (comment))
            self.seqNum += 1
            return True

        test = self._runTest(testClass, ccd, amp, trigger=trigger,
                             comment=comment, noRun=noRun, **testArgs)
        self.seqNum += 1
        
        return test
    
    def _runTest(self, testClass, ccd, amp, trigger=None,
                 comment=None, noRun=False, **testArgs):
        
        test = testClass(self, ccd, amp,
                         dewar=self.dewar,
                         comment=comment)
        if test.leadNames():
            print("configuring MUX for %s%s\n" % (self.describeTest(), ("" if not comment else " (%s)" % comment)))
            self.configMux(ccd, amp, test)

        print("running %s%s\n" % (self.describeTest(withLeads=False), ("" if not comment else " (%s)" % comment)))

        if noRun:
            print("skipping actual scope run!")
            return True

        try:
            if hasattr(test, 'runTest'):
                ret = test.runTest(test, **testArgs)
            else:
                ret = self.scope.runTest(test, trigger=trigger, **testArgs)
        except Exception as e:
            print("test FAILED: %s" % (e))
            return False

        if ret is False:
            print("test FAILED, stopping.")
            return False
        
        test.save()
        ret = test.plot()
        basePath, _ = os.path.splitext(test.fullPath)
        pdfPath = "%s.pdf" % (basePath)

        if isinstance(ret, str):
            self.logger.warn('not yet formatting Markdown output')
        else:
            fig, pl = ret
            if fig is not None:
                fig.savefig(pdfPath)
                print("PDF is at %s" % (pdfPath))

        return test, ret

    def runExtraTest(self, testClass, ccd=0, amp=0, comment=None):
        test = self._runTest(testClass, ccd, amp, comment=comment)
        return test
        
    @property
    def frontPagePath(self):
        return os.path.join(self.dirName, 'frontpage.md')
    
    @property
    def frontPage(self):
        if self._frontPage is None:
            self._frontPage = self._startfrontPage()
        return self._frontPage

    def savefig(self, fig, name, extension='pdf'):
        filePath = os.path.join(self.dirName, "%s.%s" % (name, extension))

        fig.savefig(filePath)
        
    def _startfrontPage(self):
        fname = self.frontPagePath
        f = open(fname, 'w', buffering=1)

        d, testSeq = os.path.split(self.dirName)
        d, testDate = os.path.split(d)
        
        f.write('# DAQ test %s on %s\n\n' % (testSeq, testDate))

        f.write('**Path**: `%s`\n\n' % (self.dirName))
        f.write('**Date**: %s\n\n' % (time.strftime("%Y-%m-%d %H:%M:%S")))
        
        return f

    @property
    def ourPath(self):
        import inspect
        here, _ = os.path.split(inspect.getsourcefile(self.__class__))
        return here
    
    def finishFrontPage(self):
        mdName = self.frontPagePath
        self.frontPage.close()
        self._frontPage = None
        
        pdfName = "%s.pdf" % (os.path.splitext(mdName)[0])
        texName = "%s.tex" % (os.path.splitext(mdName)[0])
        subprocess.call('pandoc -V geometry:margin=0.2in -B %s -s -o %s %s' % (os.path.join(self.ourPath, 'leftTables.tex'),
                                                                               pdfName, mdName), shell=True)
        subprocess.call('pandoc -V geometry:margin=0.2in -B %s -s -o %s %s' % (os.path.join(self.ourPath, 'leftTables.tex'),
                                                                               texName, mdName), shell=True)
        print('RAN pandoc -V geometry:margin=0.2in -B %s -s -o %s %s' % (os.path.join(self.ourPath, 'leftTables.tex'),
                                                                         texName, mdName))
    def finishFullRig(self):
        print("generating full report.... ")
        
        reportPath = os.path.join(self.dirName, 'report-%06d.pdf' % (self.seqno))
        cmd = '(cd %s; pdfjoin --outfile %s frontpage.pdf Readnoise-*.pdf levels.pdf rowcuts.pdf starts.pdf S0*.pdf P0*.pdf V0*.pdf S1*.pdf P1*.pdf P2*.pdf)' % (self.dirName, reportPath)

        subprocess.call(cmd, shell=True)
        print("report is in %s" % (reportPath))
         
    def runBlock(self, test=None, noRun=False, muxOK=True, **testArgs):
        """ run tests until failure or the next MUX reconfiguration

        Args
        ---
        test : int
          If set, jump to that test.
        noRun : bool
          if True, only print what we would do.
        muxOK: bool
          if True and we start at a MUX reconfiguration step, assume
          that the MUX has already been configured, and skip that step.

        """

        if test is not None:
            self.seqNum = test
        plt.close('all')
        
        ccd, amp, testClass, comment2 = self.sequence[self.seqNum]
        if testClass is None and muxOK:
            self.incrTest()

        while True:
            if self.seqNum >= len(self.sequence):
                print("DONE")
                return True
            ccd, amp, testClass, comment2 = self.sequence[self.seqNum]
            if testClass is None:
                if comment2 is None:
                    self.finishFullRig()
                    return True
                print
                print("============= MUX reconfiguration: you need to %s" % (comment2))
                print
                return True

            ret = self.runTest(noRun=noRun, **testArgs)
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
    if doPrint:
        logging.info("cmd: %s" % (fullCmdStr))
        
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
            logging.debug(l.strip())

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
    namps = 8
    
    def ampidx(self, ampid, im=None):
        if im is not None:
            nrows, ncols = im.shape
                
        ampCols = ncols / 8
        return np.arange(ampCols*ampid, ampCols*(ampid+1), dtype='i4')

class FinishUp(OneTest):
    testName = 'FinishUp'
    label = 'Generate full report'
    leads = ''
    timeout = 30

    def runTest(self):
        self.rig.finishFullRig()

    def setup(self, trigger=None):
        pass
    def fetchData(self):
        pass
    
    def save(self, comment=''):
        pass
        
    def plot(self, fitspath=None):
        return None, None

class SanityTest(OneTest):
    testName = 'Sanity'
    label = 'serials and voltages'
    leads = ''
    timeout = 30

    CheckedValue = collections.namedtuple('CheckedValue', ['name', 'value', 'status'])
    
    def initTest(self):
        self.voltages = []
        self.serials = []

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

        for n in 'fee',:
            try:
                flag, asciiVal = getCardValue(cards, 'revision_%s' % (n), self.asciiCnv)
            except KeyError:
                self.serials.append(self.CheckedValue(n, 'missing', 'could not read'))
                continue
            except UnicodeDecodeError:
                flag, rawVal = getCardValue(cards, 'revision_%s' % (n))
                self.serials.append(self.CheckedValue(n, repr(rawVal), 'garbage or has not been set'))
                continue
            self.serials.append(self.CheckedValue(n, asciiVal, 'OK'))
        
        for n in 'fee', 'adc', 'pa0':
            try:
                flag, numVal = getCardValue(cards, 'serial_%s' % (n), self.base10Cnv)
            except KeyError:
                self.serials.append(self.CheckedValue(n, 'missing', 'cannot read'))
                self.logger.warning('could not get serial ID for %s', n)
                continue
            except ValueError:
                flag, rawVal = getCardValue(cards, 'serial_%s' % (n))
                self.serials.append(self.CheckedValue(n, rawVal, 'is not an integer'))
                continue

            if numVal == 2**32 - 1:
                self.serials.append(self.CheckedValue(n, numVal, 'has not been set'))
                continue

            self.serials.append(self.CheckedValue(n, numVal, 'OK'))

        for n in 'ccd0', 'ccd1':
            try:
                flag, asciiVal = getCardValue(cards, 'serial_%s' % (n), self.asciiCnv)
            except KeyError:
                self.serials.append(self.CheckedValue(n, 'missing', 'could not read'))
                continue
            except UnicodeDecodeError:
                flag, rawVal = getCardValue(cards, 'serial_%s' % (n))
                self.serials.append(self.CheckedValue(n, repr(rawVal)[:15], 'garbage or has not been set'))
                continue

            self.serials.append(self.CheckedValue(n, asciiVal, 'OK'))

        haveErrors = False
        for s in self.serials:
            if s.status != 'OK':
                self.logger.critical('MUST set %s serial number with: rig.setSerials(%s=VALUE)',
                                     s.name, s.name.upper())
                haveErrors = True

        return not haveErrors

    def checkVoltages(self, cards):

        Voltage = collections.namedtuple('Voltage', ['name', 'nominal', 'lo', 'hi'])
        vlist = [
            Voltage(name='3v3m', nominal=3.3, lo=0.02, hi=0.02),
            Voltage(name='3v3', nominal=3.3, lo=0.02, hi=0.02),
            Voltage(name='5vp', nominal=5.0, lo=0.02, hi=0.02),
            Voltage(name='5vn', nominal=-5, lo=0.02, hi=0.02),
            Voltage(name='5vppa', nominal=5, lo=0.02, hi=0.02),
            Voltage(name='5vnpa', nominal=-5, lo=0.02, hi=0.02),
            Voltage(name='12vp', nominal=12, lo=0.02, hi=0.02),
            Voltage(name='12vn', nominal=-12, lo=0.02, hi=0.02),
            Voltage(name='24vn', nominal=-24.75, lo=0.01, hi=0.01),
            Voltage(name='54vp', nominal=54.25, lo=0.01, hi=0.01),
        ]

        for v in vlist:
            try:
                flag, numVal = getCardValue(cards, 'voltage_%s' % (v.name), float)
            except KeyError:
                self.voltages.append(self.CheckedValue(v.name, 'missing', 'could not read'))
                continue
            except ValueError:
                flag, rawVal = getCardValue(cards, 'voltage_%s' % (v.name))
                self.voltages.append(self.CheckedValue(v.name, str(rawVal), 'not a valid float'))
                continue

            loLimit = v.nominal - v.nominal*v.lo
            hiLimit = v.nominal + v.nominal*v.hi
            if loLimit > hiLimit:
                loLimit, hiLimit = hiLimit, loLimit
                
            if numVal < loLimit or numVal > hiLimit:
                self.voltages.append(self.CheckedValue(v.name,
                                                       '% 0.3fV (% 0.1fV %+0.1f%%)' % (numVal, v.nominal,
                                                                                       100*(numVal/v.nominal - 1)),
                                                       'out of range [% 0.3fV, % 0.3fV]' % (loLimit, hiLimit)))
                continue

            self.voltages.append(self.CheckedValue(v.name,
                                                   '% 0.3fV (% 0.1fV %+0.1f%%)' % (numVal, v.nominal,
                                                                                   100*(numVal/v.nominal - 1)),
                                                   'OK'))

        try:
            flag, numVal = getCardValue(cards, 'bias_ch0_bb', float)
            if numVal < 9:
                print("################################################################")
                print("   FEE has not been calibrated (VBB=%s). " % (numVal))
                print("   if you want to, run 'rig.calibrateFee()'")
                print("################################################################")
                raise RuntimeError('!!!! FEE has not been calibrated!!!!!')
        except KeyError:
            self.voltages.append(self.CheckedValue('VBB', 'missing', 'could not read'))
        except ValueError:
            flag, rawVal = getCardValue(cards, 'bias_ch0_bb')
            self.voltages.append(self.CheckedValue('VBB', str(rawVal), 'not a valid float'))
        
        haveErrors = False
        for s in self.voltages:
            if s.status != 'OK':
                self.logger.critical('FIX voltage %s', s.name)
                haveErrors = True

        return not haveErrors

    def formatCheckedValues(self):
        lines = []

        nameLen = max([len(s.name) for s in self.serials])
        valueLen = max([len(str(s.value)) for s in self.serials])
        statusLen = max([len(s.status) for s in self.serials])
        
        fmt = "%%-%ds | %%-%ds | %%-%ds" % (nameLen, valueLen, statusLen)
        lines.append('## Serial numbers')
        lines.append('')
        lines.append(fmt % ('Name', 'Value', 'Status'))
        lines.append(fmt % ('-'*nameLen, '-'*valueLen, '-'*statusLen))
        for s in self.serials:
            lines.append(fmt % (s.name, s.value, s.status))

        nameLen = max([len(s.name) for s in self.voltages])
        valueLen = max([len(str(s.value)) for s in self.voltages])
        statusLen = max([len(s.status) for s in self.voltages])
        fmt = "%%-%ds | %%-%ds | %%-%ds" % (nameLen, valueLen, statusLen)
        
        lines.append('')
        lines.append('## Voltages')
        lines.append('')
        lines.append(fmt % ('Name', 'Value', 'Status'))
        lines.append(fmt % ('-'*nameLen, '-'*valueLen, '-'*statusLen))
        for s in self.voltages:
            lines.append(fmt % (s.name, s.value, s.status))
        lines.append('')

        return '\n'.join(lines)
    
    def runTest(self, trigger=None, **testArgs):
        self.rig.powerDown()
        self.rig.powerUp()
        oneCmd('ccd_%s' % (self.dewar), '--level=d fee setMode idle', doPrint=True)
        time.sleep(3)
        
        cards = oneCmd('ccd_%s' % (self.dewar), '--level=d fee status', doPrint=False)
        if 'command echo mismatch' in ' '.join(cards):
            print("################################################################")
            print("  cannot read FEE revision: has FEE firmware been downloaded?")
            print("  if not, please download with 'rig burnFee'")
            print("################################################################")
            return False
    
        ok1 = self.checkSerials(cards)
        ok2 = self.checkVoltages(cards)
        ok = ok1 and ok2
        
        print self.formatCheckedValues()
        print

        mdfile = self.rig.frontPage
        mdfile.write(self.formatCheckedValues())
        mdfile.write('\n')
        mdfile.flush()
        
        return ok
            
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

    def runTest(self, trigger=None, **testArgs):
        ccdName = "ccd_%s" % (self.dewar)
        if 'zeroOffsets' in testArgs:
            oneCmd(ccdName, 'fee setOffsets n=0,0,0,0,0,0,0,0 p=0,0,0,0,0,0,0,0', doPrint=True)
            self.expectedLevels = self.rig.expectedLevels
        else:
            oneCmd(ccdName, 'fee setMode offset')
            self.expectedLevels = [1000]*8
        time.sleep(1.1)
        self.logger.info("calling for a wipe")
        oneCmd(ccdName, 'wipe')
        self.logger.info("done with wipe")
        self.logger.info("calling for a read")
        output = oneCmd(ccdName, 'read bias')

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
        # plt.ioff()

        fakeCcd = FakeCcd()
        
        im = pyfits.getdata(fitspath)
        ampWidth = im.shape[1]//8
        height = im.shape[0]
        
        statCols = np.arange(50, ampWidth-50)
        rows = slice(height//2 - ampWidth//2,height//2 + ampWidth//2)
        fig, gs = nbFuncs.rawAmpGrid(im, fakeCcd,
                                     title=fitspath,
                                     expectedLevels=self.expectedLevels,
                                     cols=statCols, rows=rows)
        levels, devs = nbFuncs.ampStats(im, cols=statCols, rows=rows, ccd=fakeCcd)
        mdfile = self.rig.frontPage
        mdfile.write('## Noise\n')
        mdfile.write('\n')
        mdfile.write('Amp ID | Bias    | Stdev\n')
        mdfile.write('------ | ------- | -----\n')
        fmt = "%-6s | %0.2f | %0.2f\n"
        for i in range(len(levels)):
            mdfile.write(fmt % ('ccd%d/%d' % (i/4, i%4), levels[i], devs[i]))
        mdfile.write('\n')

        row = im.shape[0]//2
        if True:
            cols = np.arange(100)
            f2 = nbFuncs.plotAmps(im, row=row, cols=cols, plotOffset=10, title='row starts, test %d' % (self.rig.seqno))
            self.rig.savefig(f2, 'starts')
        
        cols = np.arange(10,im.shape[1]//8-1)
        f3 = nbFuncs.plotAmps(im, row=row, cols=cols, plotOffset=4, linestyle='-', title='full rows, test %d' % (self.rig.seqno))
        self.rig.savefig(f3, 'levels')

        f4 = nbFuncs.plotAmpRows(im, rows=np.arange(im.shape[0]-20)+10, cols=statCols, plotOffset=3,
                                 title='amp means, test %d' % (self.rig.seqno))
        self.rig.savefig(f4, 'rowcuts')

        #bsIm = geom.normAmpLevels(im, fullCol=True)
        #f5 = nbFuncs.plotAmpRows(bsIm, rows=np.arange(im.shape[0]-20)+10, cols=statCols, plotOffset=1,
        #                         title='overscan-corrected amp means, test %d' % (self.rig.seqno))
        #self.rig.savefig(f5, 'rowcuts_norm')
        
        self.rig.finishFrontPage()
        
        return fig, gs

def calcOffsets(target, current):
    m = np.round((target - current) / 30, 1)
    r = np.round(m * 40.0/57.0)
    
    return m, r


class OffsetTest(OneTest):
    testName = 'SetOffsets'
    label = "setting amp levels to 1000 ADU"
    leads = 'terminators only'
    timeout = 30
    
    def initTest(self):
        pass

    def setup(self, trigger=None):
        pass

    def getPath(self, output):
        for l in output:
            m = re.search('.*filepath=(.*\.fits).*', l)
            if m:
                pathparts = m.group(1)
                fitspath = os.path.join(*pathparts.split(','))
                return fitspath
        return None
        
    def runTest(self, trigger=None,
                nrows=None, ref=None, master=None, walkOffsets=False, checkOffsets=False, **testArgs):
        ccdName = "ccd_%s" % (self.dewar)
        baseMaster = 0 if master is None else master
        baseRef = 0 if ref is None else ref
        if walkOffsets:
            for leg in 'n', 'p':
                for i, v in enumerate(np.linspace(0.0, -399.9, 5)):
                    vlist = [v]*8
                    if leg == 'p':
                        print("====== offset test, ref=%0.2f master=%0.2f" % (v, baseMaster))
                        oneCmd(ccdName, 'fee setOffsets n=%d,%d,%d,%d,%d,%d,%d,%d p=%0.2f,%0.2f,%0.2f,%0.2f,%0.2f,%0.2f,%0.2f,%0.2f'
                               % tuple([baseMaster]*8 + vlist))
                    else:
                        print("====== offset test, ref=%0.2f master=%0.2f" % (baseRef, v))
                        oneCmd(ccdName, 'fee setOffsets p=%d,%d,%d,%d,%d,%d,%d,%d n=%0.2f,%0.2f,%0.2f,%0.2f,%0.2f,%0.2f,%0.2f,%0.2f'
                               % tuple([baseRef]*8 + vlist))

                    time.sleep(1.1)
                    oneCmd(ccdName, 'wipe')
                    if nrows is not None:
                        output = oneCmd(ccdName, 'read bias nrows=%d' % (nrows))
                    else:
                        output = oneCmd(ccdName, 'read bias')

                    fitspath = self.getPath(output)
                    shutil.copy(fitspath, os.path.join(self.rig.dirName,
                                                       os.path.basename(fitspath)))

                    if leg == 'n' and i == 0:
                        im = pyfits.getdata(fitspath)
                        fakeCcd = FakeCcd()
                        means, _ = nbFuncs.ampStats(im, ccd=fakeCcd)
        else:
            oneCmd(ccdName, 'fee setOffsets n=%d,%d,%d,%d,%d,%d,%d,%d p=%d,%d,%d,%d,%d,%d,%d,%d'
                   % tuple([0]*16))
            time.sleep(1.1)
            oneCmd(ccdName, 'wipe')
            nrows = 500
            output = oneCmd(ccdName, 'read bias nrows=%d' % (nrows))
            fitspath = self.getPath(output)
            shutil.copy(fitspath, os.path.join(self.rig.dirName,
                                               os.path.basename(fitspath)))
            im = pyfits.getdata(fitspath)
            fakeCcd = FakeCcd()
            means, _ = nbFuncs.ampStats(im, ccd=fakeCcd, rows=np.arange(10, nrows-20))
            
        if ref is None and master is None:
            m, r = calcOffsets(1000,means)
            print("applying master: %s" % (m))
            print("applying refs  : %s" % (r))

            vlist = tuple(m) + tuple(r)
            oneCmd(ccdName,
                   'fee setOffsets n=%0.2f,%0.2f,%0.2f,%0.2f,%0.2f,%0.2f,%0.2f,%0.2f \
                                   p=%0.2f,%0.2f,%0.2f,%0.2f,%0.2f,%0.2f,%0.2f,%0.2f save'
                   % vlist)
            time.sleep(1.1)
            oneCmd(ccdName, 'fee setMode offset')
            time.sleep(1.1)

            if checkOffsets:
                oneCmd(ccdName, 'wipe')
                output = oneCmd(ccdName, 'read bias')

                fitspath = self.getPath(output)
                shutil.copy(fitspath, os.path.join(self.rig.dirName,
                                                   os.path.basename(fitspath)))
                im = pyfits.getdata(fitspath)
                fakeCcd = FakeCcd()
                means, _ = nbFuncs.ampStats(im, ccd=fakeCcd)
                print("file : %s" % (fitspath))
                print("adjusted means: %s" % (np.round(means, 2)))
        
    def fetchData(self):
        pass
    
    def save(self, comment=''):
        pass
        
    def plot(self, fitspath=None):
        return None, None

class WalkOffsets(OffsetTest):
    testName = "WalkOffsets"
    label = "testing ref and master offset ranges"

    def runTest(self, trigger=None,
                nrows=100, ref=None, master=None, walkOffsets=True, **testArgs):

        return OffsetTest.runTest(self, trigger=trigger,
                                  nrows=nrows, ref=ref, master=master,
                                  walkOffsets=walkOffsets, **testArgs)

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
                       xlim=(-1,10), ylim=(-20,20), 
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


