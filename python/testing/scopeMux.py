from __future__ import absolute_import, division, print_function
from builtins import str
from builtins import object
from future. builtins import *
from future.builtins.disabled import *

import io
import logging

import serial

logging.basicConfig()

class ScopeMux(object):
    probe1 = ((1,'C1'), (1,'C4'),
              (2,'C1'), (2,'C4'),
              'M10')
    probe2 = ((1,'C2'), (1,'C5'), (1,'C6'),
              (2,'C2'), (2,'C5'), (2,'C6'),
              'M1', 'M4', 'M7')
    probe3 = ((1,'C7'), (1,'C8'), (1,'C11'),
              (2,'C7'), (2,'C8'), (2,'C11'),
              'M2', 'M5', 'M8')
    probe4 = ((1,'C9'), (1,'C10'),
              (2,'C9'), (2,'C10'),
              'M3', 'M6', 'M9', 'M11')
    
    probes = (probe1, probe2, probe3, probe4)
    probe0s = (101, 111, 201, 211)
    
    def __init__(self, logLevel=logging.INFO,
                 address='socket://scope-mux.pfs:4002'):

        self.logger = logging.getLogger('scopeMux')
        self.logger.setLevel(logLevel)
        self.logger.debug('started logging...')
        
        self.EOL = '\n'
        self.mux = serial.serial_for_url(address, timeout=1.0)
        self.muxIO = io.TextIOWrapper(io.BufferedRWPair(self.mux, self.mux),
                                      line_buffering=True)

    def __del__(self):
        try:
            self.mux.close()
        except:
            pass
        
    def sendOneCommand(self, cmd):
        outStr = cmd + self.EOL
        self.logger.debug('sending: %r', outStr)
        self.muxIO.write(outStr)

        ret = self.muxIO.readline()
        ret = ret.strip()
        self.logger.debug('read   : %r', ret)

        return ret

    def reset(self):
        self.sendOneCommand(u'*RST')
        self.sendOneCommand(u'ROUT:OPEN (@199,299)')
        self.checkAllOpen()
        
    def unpackStatus(self, ret):
        retStates = [int(r) for r in ret.split(',')]
        return retStates

    def reportMux(self, mux):
        muxBase = mux * 100
        ret = self.sendOneCommand(u'ROUT:CLOS? (@%d:%d,%d,%d,%d)' % (muxBase+1, muxBase+20,
                                                                     muxBase+97, muxBase+98, muxBase+99))
        return self.unpackStatus(ret)
    
    def reportProbe(self, probe):
        probeBase = self.probe0s[probe]
        ret = self.sendOneCommand(u'ROUT:CLOS? (@%d:%d)' % (probeBase, probeBase+9))
        return self.unpackStatus(ret)
    
    def reportMuxes(self):
        muxes = []
        for i in 1,2:
            muxes.append(self.reportMux(i))

        return muxes
    
    def reportProbes(self):
        probes = []
        for p_i, p in enumerate(self.probes):
            probeMux = self.reportProbe(p_i)
            probes.append(probeMux)

        return probes
    
    def checkAllOpen(self):
        status = self.reportMuxes()
        if any(status[0]) or any(status[1]):
            raise RuntimeError('some switch is not open after opening all: %s %s' % tuple(status))
        
    def openAll(self):
        relays = []
        for p0 in self.probe0s:
            relays.append('%d:%d' % (p0, p0+10-1))
        relays.append('197,198,199')
        relays.append('297,298,299')
        cmdStr = u'ROUTE:OPEN (@%s)' % (','.join([str(r) for r in relays]))
        self.sendOneCommand(cmdStr)

        self.checkAllOpen()
        
    def setProbes(self, plist, channel=0):
        if not isinstance(plist, (tuple, list)) or len(plist) != 4:
            raise RuntimeError('setProbes requires a list of four probes')

        self.sendOneCommand(u'DISP:TEXT "opening all..."')
        self.openAll()
        
        relays = []
        switches = []
        for p_i, p in enumerate(plist):
            if p[0] == 'C':
                if channel not in {1,2}:
                    raise IndexError('channel must be 1 or 2')
                p = (channel, p)

            muxBlock = self.probes[p_i]
            switch = muxBlock.index(p)
            switches.append(switch)
            relays.append(self.probe0s[p_i] + switch)

        cmdStr = u'ROUTE:CLOSE (@%s)' % (','.join([str(r) for r in relays]))
        ret = self.sendOneCommand(cmdStr)

        dispText = ' '.join([str(s) for s in switches])
        self.sendOneCommand(u'DISP:TEXT "%s"' % (dispText))

        cmdStr = u'ROUTE:CLOSE? (@%s)' % (','.join([str(r) for r in relays]))
        ret = self.sendOneCommand(cmdStr)

        retStates = [int(r) for r in ret.split(',')]
        if retStates != [1,1,1,1]:
            raise RuntimeError('failed to close the right switches: %s' % (str(retStates)))

        return self.reportMuxes()
