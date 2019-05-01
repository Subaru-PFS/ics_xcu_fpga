from importlib import reload

from collections import OrderedDict
import logging
import numpy as np
import re

logger = logging.getLogger('clocks')
logger.setLevel(logging.DEBUG)

from . import clockIDs
from functools import reduce

# Danger! This causes much set() work to fail confusingly!
# reload(clockIDs)

class Clocks(object):
    """ Access the FPGA's clocking sequences.

    The FPGA takes a vector of 32-bit words, with the high 17 being a bitmask of 
    signals to set high or low, and the low 15 being the number of clocks to sustain. 
    """

    tickTime = 40e-9

    def __init__(self, tickTime=None, initFrom=None,
                 holdOn=set(), holdOff=set(),
                 logLevel=logging.INFO):

        self.logger = logging.getLogger('clocks')
        self.clear()

        if tickTime is not None:
            self.tickTime = tickTime
        if initFrom is None:
            self.initSet = set()
            self.holdOn = set()
            self.holdOff = set()
            self.setHold(holdOn, holdOff)
        else:
            self.initSet = initFrom.enabled[-1]
            self.holdOff = initFrom.holdOff
            self.holdOn = initFrom.holdOn

            if holdOn or holdOff:
                import pdb; pdb.set_trace()
                raise RuntimeError('confused by overriding inherited held clocks. Will not.')
            
    def clear(self):
        self.enabled = []
        self.ticks = []
        self.sent = False

    def setNames(self, m):
        return sorted([sig.label for sig in m])

    def stateMask(self, m):
        if len(m) is 0:
            return 0
        sm = reduce(int.__or__, [s.mask for s in m])
        return sm

    @property
    def netEnabled(self):
        """ Return self.enabled modified by self.holdOn and self.holdOff """
        
        if not (self.holdOn or self.holdOff):
            return self.enabled

        enabled = self.enabled.copy()
        for i, e in enumerate(enabled):
            enabled[i] |= self.holdOn
            enabled[i] -= self.holdOff

        self.logger.info(f'netEnabled: {self.holdOn}, {self.holdOff}')
        
        return enabled
    
    def setHold(self, holdOn=None, holdOff=None):
        """ Declare certain clocks to be held on or off. 

        Args
        ----
        holdOn, holdOff : None or sets of clockID signal names
        """

        if holdOn is None:
            holdOn = set()
        if holdOff is None:
            holdOff = set()

        self.holdOn = {clockIDs.signalsByName[sigName] for sigName in holdOn}
        self.holdOff = {clockIDs.signalsByName[sigName] for sigName in holdOff}
        
    def genClocks(self):
        enabled = self.netEnabled
        
        if len(self.ticks) != len(enabled)+1:
            raise RuntimeError("the duration of the final opcode state must be known.")

        states = np.zeros(len(enabled), dtype='u4')
        durations = np.zeros(len(enabled), dtype='u2')

        for i in range(len(enabled)):
            duration = self.ticks[i+1] - self.ticks[i]
            states[i] = self.stateMask(enabled[i])
            durations[i] = duration

        return durations, states

    def signalTrace(self, signal, includeInit=True):
        ticks = []
        transitions = []

        enabled = self.netEnabled
        
        if includeInit:
            ticks.append(-1)
            transitions.append(signal in self.initSet)
            lastState = signal in self.initSet
        else:
            lastState = False

        self.logger.debug('%s init:%s %s %s %s',
                          signal, ticks, lastState, transitions, [s.label for s in self.initSet])


        for i in range(len(enabled)):
            newState = signal in enabled[i]
            self.logger.debug('%s new :%s %s %s', signal, self.ticks[i], lastState, newState)
            if newState != lastState or i == 0 or i == len(self.ticks)-1:
                ticks.append(self.ticks[i])
                transitions.append(newState)
                lastState = newState

        if len(enabled) < len(self.ticks):
            ticks.append(self.ticks[-1])
            transitions.append(transitions[-1])

        return ticks, transitions

    def allSignals(self):
        signals = set()
        for e in self.netEnabled:
            signals |= e
            
        return signals

    def printTransitions(self, signals=None):
        if signals is None:
            signals = self.allSignals()
        signals = set(signals)

        for s in signals:
            ticks, states = self.signalTrace(s)
            print("%s: %s %s" % (s.label, ticks, states))

    def genJSON(self, tickDiv=2, cutAfter=20, signals=None,
                includeAll=False, keepGroups=None, title=''):

        enabled = self.netEnabled
        if keepGroups is None:
            keepGroups = set()
        for g in keepGroups:
            if g not in clockIDs.allGroups:
                raise ValueError(f"unknown group {g} not in {clockIDs.allGroups}")
            
        if signals is None:
            signals = set()
            for e in enabled:
                signals |= e
            for gname in keepGroups:
                signals |= clockIDs.allGroups[gname]
            if not includeAll:
                unchanged = set()
                for s in signals:
                    _, transitions = self.signalTrace(s)
                    if np.all([transitions[0] == t for t in transitions[1:]]):
                        if s.group not in keepGroups:
                            unchanged.add(s)
                        
                signals.difference_update(unchanged)
        else:
            signals = set(signals)


        traces = OrderedDict()
        for s in signals:
            traces[s] = []
        
        transitionTicks = set()
        for sig in signals:
            ticks, states = self.signalTrace(sig)
            trace = ''
            lastTick = ticks[0]-1
            lastState = None
            for t_i in range(len(ticks)):
                thisTick = ticks[t_i]
                thisState = states[t_i]

                dticks = (thisTick - lastTick)//tickDiv
                dticks_f = (thisTick - lastTick)/tickDiv
                assert (thisTick <= 0 or dticks > 0), \
                    ("dticks for %s at slot %s, tick %s to %s is non-positive!" % 
                     (sig, t_i, lastTick, thisTick))
                assert (lastTick < 0 or dticks == dticks_f), \
                    ("dticks (%s) for %s at slot %s, tick %s to %s by %s is non-integer!" % 
                     (dticks_f, sig, t_i, lastTick, thisTick, tickDiv))
                    
                trace += '.'*(dticks-1)

                if thisState != lastState:
                    trace += '%d' % (thisState)
                    if thisTick >= 0:
                        transitionTicks.add(thisTick)
                else:
                    trace += '.'
                self.logger.debug("%s: %d tick=%d dtick=%d len=%d (%d)",
                                  sig.label, t_i, ticks[t_i], dticks,
                                  len(trace), len(trace)*tickDiv)
                lastTick = thisTick
                lastState = thisState
            traces[sig] = trace
        transitionTicks.add(ticks[-1])
        transitionTicks = sorted(transitionTicks)
        self.logger.info("transitions at: %s" % (transitionTicks))

        # Collapse long runs with '|'
        #    find next epos from spos where any trace is not '.'
        #    if epos-spos > cutAfter:
        #       traces[spos:epos] = '|'
        spos = 0
        opos = 0
        cutSpans = []
        while spos < len(trace):
            # set spos = next spos where all traces are '.'
            next_s_matches = [re.search('[.]', traces[sig][spos:]) for sig in signals]
            if any([m is None for m in next_s_matches]):
                self.logger.debug('break due to missing spos match at %d: %s', spos, next_s_matches)
                break
            span1 = max([m.start() for m in next_s_matches])
            assert span1 > 0, "next '.' is 0 chars out at %d" % (spos)
            self.logger.debug('moving spos from %d by %d', spos, span1)
            spos += span1
            opos += span1
            
            # set epos = nearest non-dot after spos
            next_e_matches = {sig: re.search('[^.]', traces[sig][spos:]) for sig in signals}
            next_e_pos = [next_e_matches[sig].start()
                          if next_e_matches[sig] is not None
                          else len(traces[sig][spos:]) for sig in signals]
            nextChange = min(next_e_pos)
            epos = spos + nextChange
            self.logger.debug('setting epos to %d = %d + %d', epos, spos, nextChange)

            # if epos - spos >= cutAfter, replace with '|'
            opos += epos - spos
            if epos - spos >= cutAfter:
                self.logger.info('trimming %d to %d', spos, epos)
                for sig in signals:
                    ts = traces[sig]
                    traces[sig] = ts[:spos] + '|' + ts[epos:]
                cutSpans.append([opos, opos+(epos-spos)])
            else:
                spos = epos
                
        json = []
        json.append('{')
        json.append('head: {text: "ns from start %s"},' % (title))
        json.append('signal: [')

        # Patch up cut ends
        if traces[list(signals)[0]][-1] == '|':
            self.logger.info('patching cut ends')
            for sig in signals:
                ts = traces[sig]
                traces[sig] = ts + '.'

        # mark transitions
        edges = []
        label_n = 0
        transitionLabels = ['.']
        otherLabels = ['.']

        # Start with ASCII characters, extend into Unicode if we have to.
        names = [chr(ord('A')+n) for n in range(26)]
        _names = [chr(xc) for xc in range(0x100, 0x2ff)]
        names2 = [n for n in _names if not n.islower()]
        names.extend(names2)

        traceLen = len(traces[list(signals)[0]])
        for c_i in range(1, traceLen):
            isTransition = any([traces[sig][c_i] in '01' for sig in list(traces.keys())])
            if c_i == traceLen-1:
                isTransition = True
            thisName = names[2*label_n]
            otherName = names[2*label_n + 1]
            if isTransition:
                self.logger.info(" trans %d(%s) at %d/%d" % (label_n, thisName, c_i, traceLen))
                transitionLabels.append(thisName)
                otherLabels.append(otherName)
                edges.append("'%s%s'" % (thisName, otherName))
                # edges.append("'%s %d'" % (thisName, transitionTicks[label_n]))
                if label_n == 0:
                    dt = 0
                else:
                    dt = transitionTicks[label_n] - transitionTicks[label_n-1]
                edges.append("'%s %d'" % (otherName, dt * 40))
                edges.append("'%s %d'" % (thisName, transitionTicks[label_n] * 40))
                label_n += 1
            else:
                transitionLabels.append('.')
                otherLabels.append('.')

        transitionLabels = ''.join(transitionLabels)
        otherLabels = ''.join(otherLabels)
        self.logger.info("transitionLabels: %s %s" % (transitionLabels, transitionTicks))

        json.append("{node: '%s'}," % (transitionLabels))

        group = None
        for sig in self.orderForPlot(signals):
            if sig.group != group:
                if group is not None:
                    json.append("],")
                    json.append("{},")
                group = sig.group
                json.append("['%s'," % (group))

            json.append("{name: '%s'," % (sig.label))
            json.append(" wave: '%s'}," % (traces[sig]))

        if group is not None:
            json.append("],")

        json.append("{},")

        json.append("{node: '%s'}," % (otherLabels))
        json.append("],")

        json.append("edge: [" + ",".join(edges) + "],")
        json.append('foot: {text: "ns from previous transition"},')
        json.append("}")
        return "\n".join(json), cutSpans

    def orderForPlot(self, signals):
        def _key(a):
            return a.group, a.order

        return sorted(signals, key=_key)

    def outputAt(self, at, turnOn, mask):
        """ set the given sets of bits at the given time.. 

        Parameters
        ----------
        at : int
           the ticks to run the new state at
        turnOn : iterable of Bits
           the Bits to enable for the new state.
        mask : iterable of Bits
           the Bits we are setting
        """

        # If set last event was for a duration, finish it.
        if len(self.ticks) > len(self.enabled):
            self.enabled.append(self.enabled[-1].copy())

        assert len(self.ticks) == len(self.enabled), \
            "output at time: ticks and enabled lists must have same length"

        # If necessary, define a tick=0 set.
        if len(self.ticks) == 0:
            if self.initSet is not None:
                newSet = self.initSet.copy()
            else:
                newSet = set()
            self.ticks.append(0)
            self.enabled.append(newSet)

        if at < self.ticks[-1]:
            raise ValueError('new at time cannot be before last defined time. (%d vs %d)' %
                             (lastTick, at))

        # if our new time is the same as the last event, modify that in place.
        if at == self.ticks[-1]:
            self.enabled[-1] = self.enabled[-1] - mask
            self.enabled[-1] |= turnOn
        else:
            self.enabled.append(turnOn)
            self.ticks.append(at)

    def outputFor(self, duration, turnOn, mask):
        """ set the given sets of bits for the given duration. 

        Parameters
        ----------
        duration : int
           the number of ticks to run the new state for
        turnOn : iterable of Bits
           the Bits to enable for the new state.
        mask : iterable of Bits
           the Bits we are setting.
        """

        if len(self.ticks) == 0:
            newSet = self.initSet.copy() if self.initSet else set()
            newSet -= mask
            newSet |= turnOn
            self.enabled.append(newSet)
            self.ticks.append(0)

        elif len(self.ticks) == len(self.enabled):
            self.enabled[-1] -= mask
            self.enabled[-1] |= turnOn
        else:
            newSet = self.enabled[-1].copy()
            newSet -= mask
            newSet |= turnOn
            self.enabled.append(newSet)

        self.ticks.append(self.ticks[-1]+duration)

        assert len(self.ticks) == len(self.enabled)+1, \
            "output for time: number of ticks must be one greater than number of sets"

    def changeAt(self, at, turnOn=None, turnOff=None):
        """ turn on and off the given sets of bits at a given time

        Parameters
        ----------
        at : int
           the tick to run the new state at
        turnOff : iterable, optional
           the Bits to turn off for the new state
        turnOn : iterable, optional
           the Bits to turn off for the new state.
        """

        if len(self.enabled) == 0:
            newSet = self.initSet.copy()
        else:
            newSet = self.enabled[-1].copy()

        turnOn = set() if turnOn is None else set(turnOn)
        turnOff = set() if turnOff is None else set(turnOff)
        mask = turnOff | turnOn
        
        newSet -= turnOff
        newSet |= turnOn
        
        self.outputAt(at, newSet, mask)
        self.logger.debug(" at  % 5d to % 5d (%2d/%2d): on=%08x, off=%08x, net=%s",
                          at, self.ticks[-1],
                          len(self.ticks), len(self.enabled),
                          self.stateMask(turnOn),
                          self.stateMask(turnOff),
                          self.setNames(self.enabled[-1]))

    def changeFor(self, duration, turnOn=None, turnOff=None):
        """ turn on and off  the given sets of bits for the given duration. 

        Parameters
        ----------
        duration : int
           the number of ticks to run the new state for
        turnOff : iterable, optional
           the Bits to turn off for the new state
        turnOn : iterable, optional
           the Bits to turn off for the new state.
        """

        if len(self.enabled) == 0:
            newSet = self.initSet.copy()
        else:
            newSet = self.enabled[-1].copy()

        turnOn = set() if turnOn is None else set(turnOn)
        turnOff = set() if turnOff is None else set(turnOff)
        mask = turnOn | turnOff

        newSet -= turnOff
        newSet |= turnOn

        self.outputFor(duration, newSet, mask)
        self.logger.debug(" for % 5d to % 5d (%2d/%2d): on=%08x, off=%08x, net=%s",
                          duration, self.ticks[-1],
                          len(self.ticks), len(self.enabled),
                          self.stateMask(turnOn),
                          self.stateMask(turnOff),
                          self.setNames(self.enabled[-1]))

def genSetClocks(turnOn=None, turnOff=None):
    initClocks = Clocks()
    initClocks.changeFor(duration=2,
                         turnOn=turnOn,
                         turnOff=turnOff)

    ticks, opcodes = initClocks.genClocks()

    return (np.array(ticks, dtype='u2'), 
            np.array(opcodes, dtype='u4'),
            0)

def genRowClocks(ncols, clocksFunc, rowBinning=1):
    """ Instantiate a complete row of clock times and opcodes. 
    """

    ticksList = []
    opcodesList = []

    pre, pix, par = clocksFunc()

    preTicks, opcodes = pre.genClocks()
    ticksList.extend(preTicks)
    opcodesList.extend(opcodes)
    logger.info(f'generating clocks with {pix.holdOff} {pix.holdOn}')
    
    pixTicks, opcodes = pix.genClocks()
    for i in range(len(pixTicks)):
        logger.debug("%6d : 0x%08x" % (pixTicks[i], opcodes[i]))
        for s in pix.holdOff:
            if s.mask & opcodes[i]:
                logger.warn(f'holdoff found in opcodes[{i}]: {s}, 0x%04x 0x%04x' % (s.mask, opcodes[i]))
        
    for i in range(ncols):
        ticksList.extend(pixTicks)
        opcodesList.extend(opcodes)

    parTicks, opcodes = par.genClocks()
    for i in range(rowBinning):
        ticksList.extend(parTicks)
        opcodesList.extend(opcodes)

    allTicks = np.array(ticksList, dtype='u2')
    rowTime = allTicks.sum(dtype='f8') * Clocks.tickTime
    
    return (allTicks, 
            np.array(opcodesList, dtype='u4'),
            rowTime)

