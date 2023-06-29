import logging
import sys
import time
import numpy as np

import pyvisa as visa

def qstr(s):
    if len(s) > 2 and s[0] in '"\'' and s[-1] in '"\'':
        return s[1:-1]
    else:
        return s

def xfloat(s):
    try:
        return float(s)
    except:
        return np.nan

def xint(s):
    try:
        return int(s)
    except:
        return None

            
channelKeys = (
    ('scale', xfloat),
    ('position', xfloat),
    ('coupling', qstr),
    ('invert', xint),
    ('label', qstr),
    ('volts', xfloat),
    ('offset', xfloat),
)

waveformKeys = (
    ('encdg', qstr),
    ('xincr', xfloat),
    ('xzero', xfloat),
    ('xunit', qstr),
    ('ymult', xfloat),
    ('yoff', xfloat),
    ('yzero', xfloat),
    ('yunit', qstr),
)

acqKeys = (
)

triggerKeys = (
    ('a:mode', qstr),
    ('a:type', qstr),
    ('a:edge:source', qstr),
    ('a:edge:coupling', qstr),
    ('a:edge:slope', qstr),
    ('a:level', xfloat),
    ('a:holdoff', xfloat),
    ('a:holdoff:time', xfloat),
)

class KVSet(object):
    def __init(self, name, tipe):
        pass

class PfsCpo(object):
    modes = {'sample', 'average', 'envelope'}

    def __init__(self, host='10.1.1.52', debug=False):
        self.logger = logging.getLogger('scope')
        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)
        
        self.host = host
        self.resourceManager = None
        self.scope = None
        self.settings = None

        self.mode = 'sample'
        self.triggerAfter = None

        self.connect()

    def __del__(self):
        if self.scope is not None:
            sys.stderr.write('closing scope connection....\n')
            self.scope.close()

    def __str__(self):
        return "PfsCpo(host=%s, scope=%s)" % (self.host,
                                              self.scope)

    def connect(self):
        if not self.resourceManager:
            self.resourceManager = visa.ResourceManager('@py')
        self.scope = self.resourceManager.open_resource('TCPIP.*::%s::INSTR' % (self.host))
        self.scope.timeout = 10000
        self.getScopeStatus()
        self.write('*RST')
        self.logger.info('Scope is: %s', self.scope.query('*IDN?'))
                         
        self.flush()

    def reconnect(self):
        if self.scope is not None:
            self.scope.close()
            del self.scope
            self.scope = None
        self.connect()

    def reset(self):
        self.write('*RST')
        self.logger.info('Scope is: %s', self.scope.query('*IDN?'))

        self.flush()

    def flush(self):
        self.settings = None

    def getSettings(self):
        ret = self.query('SET?')
        self.settings = ret.split(';')

    def getScopeStatus(self):
        while True:
            ret = self.query('*ESR?')
            code = int(ret)
            if code == 0:
                return 0
            ret = self.query('evmsg?')
            self.logger.warn(f'error {code}: {ret}')
            

    def setChannel(self, channel=None):
        if channel is not None:
            self.write('sel:%s on' % channel)
            self.write('data:source %s' % channel)

        schannel = self.query('data:source?').strip()
        if channel is not None and schannel != channel.upper():
            raise RuntimeError("Failed to set channel (%s) for reading" % 
                               ('current' if channel is None else channel))
        return schannel

    def setProbes(self):
        """ set default probes. """

        for channel in 1,2,3,4:
            self.write('ch%d:coupling dc' % (channel))
            self.write('ch%d:invert off' % (channel))
            self.write('ch%d:probe:gain 0.1' % (channel))
            self.write('sel:ch%d on' % (channel))

    def setupTransfers(self):
        self.write('data:resolution full')

    def setLabel(self, channel, label):
        if isinstance(channel, basestring):
            channel = channel[-1]
        self.write('ch%d:label "%s"' % (channel, label))

    def setLabels(self, labels, comment=None):
        if len(labels) != 4:
            raise RuntimeError("Can only set exactly four channel labels (not %d)" %
                               (len(labels)))
        for i, l in enumerate(labels):
            self.setLabel(i+1, l)
            
    def setAcqMode(self, numAvg=1, single=True):
        if numAvg <= 1:
            self.write('acq:mode sample')
            self.write('acq:numavg 1')
            self.dataWidth = 1
        else:
            self.write('acq:mode average')
            self.write('acq:numavg %d' % (numAvg))
            self.dataWidth = 2

        if single:
            self.write('acq:stopAfter seq')
        else:
            self.write('acq:stopAfter runstop')
        
    def setManualTrigger(self, after=None):
        self.write('trig:a:edge:source ext')
        self.triggerAfter = after

    def setEdgeTrigger(self, source='ch1', coupling='dc', slope='rise', 
                       level=None, holdoff='900e-9', after=None):

        if level is None:
            raise RuntimeError("must specify a trigger level")

        self.triggerAfter = None

        self.write('trig:a:mode normal')
        self.write('trig:a:type edge')
        self.write('trig:a:level %s' % (level))
        self.write('trig:a:edge:source %s' % (source))
        self.write('trig:a:edge:coupling %s' % (coupling))
        self.write('trig:a:edge:slope %s' % (slope))
        self.write('trig:a:holdoff:time %s' % (holdoff))
        self.write('trig:a:level:%s %s' % (source, level))

    def setSampling(self, scale='1e-6', pos=50, triggerPos=20, 
                    delayMode='on', delayTime=0, delayUnits='s',
                    recordLength=100000, npoints=None):
        if delayMode not in {'on', 'off'}:
            raise ValueError('delayMode must be on or off')

        if npoints is None:
            npoints = recordLength

        self.write('horiz:delay:mode %s' % (delayMode))
        if delayUnits == 'us':
            delayTime /= 1e6
        elif delayUnits == 'ms':
            delayTime /= 1e3
        elif delayUnits == 'ns':
            delayTime /= 1e9
        elif delayUnits != 's':
            raise RuntimeError(f'unknown delayUnits {delayUnits}')
        self.write('horiz:delay:time %s' % (delayTime))
        self.write('horiz:scale %s' % (scale))
        self.write('horiz:pos %s' % (pos))
        self.write('horiz:trigger:pos %s' % (triggerPos))
        self.write('horiz:record %s' % (recordLength))
        self.write('data:start 0')
        self.write('data:stop %s' % (npoints))

    def setWaveform(self, channel, label, 
                    scale=1.0, pos=0, offset=0,
                    coupling='dc', invert='off'):

        self.write('ch%d:scale %s' % (channel, scale))
        self.write('ch%d:pos %s' % (channel, pos))
        self.write('ch%d:offset %s' % (channel, offset))
        self.write('ch%d:label "%s"' % (channel, label))
        self.write('ch%d:coupling %s' % (channel, coupling))
        self.write('ch%d:invert %s' % (channel, invert))

    def query(self, qstr, verbose=logging.INFO):
        self.logger.debug('query send: %r', qstr)
        ret = self.scope.query(qstr)
        self.logger.debug('query recv: %r', ret)

        return ret

    def write(self, wstr, verbose=logging.INFO):
        self.logger.debug('write send: %r', wstr)
        ret = self.scope.write(wstr)
        self.logger.debug('write recv: %r', ret)

        return ret

    def getKeySet(self, queryPrefix, keys):
        output = dict()
        for k, ctype in keys:
            query = "%s:%s?" % (queryPrefix, k)
            v = self.query(query)
            v = v.strip()
            # self.logger.info("%s: %s -> %s", k, ctype, v)
            try:
                output[k] = ctype(v)
                # self.logger.info("%s: %s -> %s", k, v, ctype(v))
            except:
                output[k] = None
                
        return output
    
    def getChannelShape(self, channel=None):
        channel = self.setChannel(channel)

        self.write('data:resolution full')
        self.write('data:composition composite_yt')
        self.write('WFMoutpre:byt_nr %d' % (self.dataWidth))
        self.write('WFMoutpre:byt_or msb')
        self.write('WFMoutpre:encdg bin')

        keys = dict(name=channel)
        keys.update(self.getKeySet(channel, channelKeys))
        keys.update(self.getKeySet('WFMOut', waveformKeys))

        return keys

    def busyWait(self, timeout=30.0, loopTime=0.25, debug=False):
        t1 = t0 = time.time()
        
        while (t1-t0 < timeout):
            busy = self.query('busy?')
            t1 = time.time()
            if debug:
                self.logger.warn("busy after %0.4fs %s" % (t1-t0, busy))
            if int(busy) == 0:
                return
            if t1-t0 > timeout:
                raise RuntimeError('timeout waiting for operation end')

    def runTest(self, test, debug=False, trigger=None, **testArgs):
        self.logger.info('running test %s', test.testName)
        self.getScopeStatus()
        test.setup(trigger=trigger)

        self.logger.info('starting test %s (timer=%s)', test.testName, self.triggerAfter)
        self.getScopeStatus()

        self.write('acq:state run')
        if self.triggerAfter is not None:
            self.logger.info('waiting for end of %s sec trigger', self.triggerAfter)
            time.sleep(self.triggerAfter)
            self.logger.info('forcing trigger')
            self.write('trigger force')

        if hasattr(test, 'triggerCB'):
            self.logger.info('calling test trigger...')
            test.triggerCB()
            
        self.logger.info('waiting for end of test %s', test.testName)
        timeout = test.timeout if hasattr(test, 'timeout') else 30.0
        self.getScopeStatus()
        self.busyWait(timeout=timeout)

        self.logger.info('fetching data for test %s', test.testName)

        startLevel = self.logger.level
        self.logger.setLevel(20)
        test.fetchData()
        self.logger.setLevel(startLevel)
    
        self.logger.info('finished test %s', test.testName)

        return test
        
    def getWaveform(self, channel=None, getEnvelope=False):
        self.setChannel(channel)
        if getEnvelope:
            self.write('WFMoutPRE:composition composite_env')
        else:
            comp = self.query('data:composition:avail?').split(',')
            self.write('WFMoutPRE:composition %s' % (comp[0]))

        keys = self.getChannelShape(channel=channel)
        self.logger.debug('query_binary_values...')
        oldTimeout = self.scope.timeout
        self.scope.timeout = 30000
        startLevel = self.logger.level
        self.getScopeStatus()
        # self.logger.setLevel(20)
        try:
            rawdata = self.scope.query_binary_values('CURVE?', 
                                                     'h' if self.dataWidth == 2 else 'b', 
                                                     is_big_endian=True,
                                                     expect_termination=False,
                                                     container=np.array)
            self.logger.debug('query_binary_value done')
        except visa.VisaIOError:
            self.getScopeStatus()
        finally:
            self.scope.timeout = oldTimeout
            self.logger.setLevel(startLevel)

        keys['rawdata'] = rawdata
        keys['data'] = keys['yzero'] + keys['ymult'] * (rawdata - keys['yoff'])
        if not getEnvelope:
            x1 = keys['xzero'] + len(keys['data'])*keys['xincr']
            keys['x'] = np.linspace(keys['xzero'], x1, num=len(keys['data'])) 

        return keys

    def getWaveforms(self, channels=None):
        waves = dict()
        for ci in range(1,5):
            channelName = "ch%d" % ci
            wave = self.getWaveform(channel=channelName)
            waves[channelName] = wave

        return waves


    def saveWaveforms(self, waves, fname):
        import pickle
        
        with open(fname, 'w+') as pf:
            pickle.dump(waves, pf)

    def pquery(self, q):
        ret = self.query(q).strip()
        print("%s: %s" % (q, ret))

        return ret
    
