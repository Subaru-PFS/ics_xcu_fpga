import logging
import re
import sys
import numpy as np

import visa

channelKeys = (
    ('scale', float),
    ('position', float),
    ('coupling', str),
    ('invert', int),
    ('label', str),
    ('volts', float),
    ('offset', float),
)

waveformKeys = (
    ('encdg', str),
    ('xincr', float),
    ('xzero', float),
    ('xunit', str),
    ('ymult', float),
    ('yoff', float),
    ('yzero', float),
    ('yunit', str),

)

triggerKeys = (
    ('mode', str),
)

class KVSet(object):
    def __init(self, name, tipe):
        pass

class PfsCpo(object):
    modes = {'sample', 'average', 'envelope'}

    def __init__(self, host='10.1.1.52'):
        self.logger = logging.getLogger()
        self.host = host
        self.resourceManager = None
        self.scope = None
        self.settings = None

        self.mode = 'sample'
        self.trigger = None

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

        self.flush()

    def flush(self):
        self.settings = None

    def getSettings(self):
        ret = self.query('SET?')
        self.settings = ret.split(';')

    def getScopeStatus(self):
        ret = self.query('*ESR?')
        return int(ret)

    def setChannel(self, channel=None):
        if channel is not None:
            self.write('data:source %s' % channel)

        schannel = self.query('data:source?').strip()
        if channel is not None and schannel != channel.upper():
            raise RuntimeError("Failed to set channel (%s) for reading" % 
                               ('current' if channel is None else channel))
        return schannel

    def setupTransfers(self):
        self.write('data:resolution full')

    def setAcqMode(self, numAvg=1, single=True):
        if numAvg <= 1:
            self.write('acq:mode sample')
            self.dataWidth = 1
        else:
            self.write('acq:numavg %d' % (numAvg))
            self.write('acq:mode average')
            self.dataWidth = 2

        if single:
            self.write('acq:stopAfter seq')
        else:
            self.write('acq:stopAfter runstop')

        
    def query(self, qstr, verbose=logging.INFO):
        self.logger.debug('query send: %s', qstr)
        ret = self.scope.query(qstr)
        self.logger.debug('query recv: %s', ret)

        return ret

    def write(self, wstr, verbose=logging.INFO):
        self.logger.debug('write send: %s', wstr)
        ret = self.scope.write(wstr)
        self.logger.debug('write recv: %s', ret)

        return ret

    def getChannelShape(self, channel=None):
        channel = self.setChannel(channel)

        self.write('data:resolution full')
        self.write('WFMoutpre:byt_nr %d' % (self.dataWidth))
        self.write('WFMoutpre:bn_or msb')

        keys = dict(name=channel)
        for k, ctype in channelKeys:
            query = "%s:%s?" % (channel, k)
            v = self.query(query)
            try:
                keys[k] = ctype(v)
            except:
                keys[k] = None

        for k, ctype in waveformKeys:
            query = "WFMOut:%s?" % (k)
            v = self.query(query)
            try:
                keys[k] = ctype(v)
            except:
                keys[k] = None

        return keys

    def getWaveform(self, channel=None, getEnvelope=False):
        self.setChannel(channel)
        if getEnvelope:
            self.write('WFMoutPRE:composition composite_env')
        else:
            comp = self.query('data:composition:avail?')
            self.write('WFMoutPRE:composition %s' % (comp))

        keys = self.getChannelShape(channel=channel)
        self.logger.debug('query_binary_values...')
        rawdata = self.scope.query_binary_values('CURVE?', 
                                                 'h' if self.dataWidth == 2 else 'b', 
                                                 is_big_endian=True,
                                                 container=np.array)
        self.logger.debug('query_binary_value done')

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

