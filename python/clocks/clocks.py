from collections import OrderedDict
import logging
import numpy as np
import re

class Signal(object):
    def __init__(self, bit, label, description, group=None, order=0):
        self.bit = bit
        self.label = label
        self.description = description
        self.group = group
        self.order = order

    def __str__(self):
        return "Signal(%s:%d)" % (self.label, self.bit)

    @property 
    def mask(self):
        return 1 << self.bit

class Clocks(object):
    """ Access the FPGA's clocking sequences.

    The FPGA takes a vector of 32-bit words, with the high 17 being a bitmask of 
    signals to set high or low, and the low 15 being the number of clocks to sustain. 
    """

    tickTime = 40e-9
    
    def __init__(self, tickTime=None, initFrom=None, logLevel=logging.INFO):
        self.clear()

        if tickTime is not None:
            self.tickTime = tickTime
        self.initSet = set() if initFrom is None else initFrom.enabled[-1]
        self.logLevel = logLevel
        self.logger = logging.getLogger()

    def clear(self):
        self.enabled = []
        self.ticks = []
        self.sent = False

    def stateMask(self, m):
        if len(m) is 0:
            return 0
        sm = reduce(int.__or__, [s.mask for s in m])
        return sm

    def genClocks(self):
        if len(self.ticks) != len(self.enabled)+1:
            raise RuntimeError("the duration of the final opcode state must be known.")

        states = np.zeros(len(self.enabled), dtype='u4')
        durations = np.zeros(len(self.enabled), dtype='u2')

        for i in range(len(self.enabled)):
            duration = self.ticks[i+1] - self.ticks[i]
            states[i] = self.stateMask(self.enabled[i])
            durations[i] = duration

        return durations, states

    def signalTrace(self, signal, includeInit=True):
        ticks = []
        transitions = []

        if includeInit:
            ticks.append(-1)
            transitions.append(signal in self.initSet)
            found = signal in self.initSet
        else:
            found = False
        logging.debug('%s init:%s %s %s', signal, ticks, transitions, [s.label for s in self.initSet])

        lastState = None
        for i in range(len(self.enabled)):
            newState = signal in self.enabled[i]
            logging.debug('%s new :%s %s %s', signal, self.ticks[i], lastState, newState)
            if newState != lastState or i == len(self.enabled)-1:
                ticks.append(self.ticks[i])
                transitions.append(newState)
                lastState = newState
                found = True

        if not found:
            raise KeyError("signal %r not found" % (signal))

        if len(self.enabled) < len(self.ticks):
            ticks.append(self.ticks[-1])
            transitions.append(transitions[-1])
            
        return ticks, transitions

    def allSignals(self):
        signals = set()
        for e in self.enabled:
            signals = signals.union(e)
        return signals

    def printTransitions(self, signals=None):
        if signals is None:
            signals = self.allSignals()
        signals = set(signals)

        for s in signals:
            ticks, states = self.signalTrace(s)
            print "%s: %s %s" % (s.label, ticks, states)

    def genJSON(self, tickDiv=2, cutAfter=20, signals=None,
                includeAll=False, title=''):
        if signals is None:
            signals = set()
            for e in self.enabled:
                signals = signals.union(e)
            if not includeAll:
                unchanged = set()
                for s in signals:
                    _, transitions = self.signalTrace(s)
                    if np.all([transitions[0] == t for t in transitions[1:]]):
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

                dticks = (thisTick - lastTick)/tickDiv
                dticks_f = (thisTick - lastTick)/float(tickDiv)
                assert (thisTick <= 0 or dticks > 0), ("dticks for %s at slot %s, tick %s to %s is non-positive!" % 
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
                logging.debug('break due to missing spos match at %d: %s', spos, next_s_matches)
                break
            span1 = max([m.start() for m in next_s_matches])
            assert span1 > 0, "next '.' is 0 chars out at %d" % (spos)
            logging.debug('moving spos from %d by %d', spos, span1)
            spos += span1
            opos += span1
            
            # set epos = nearest non-dot after spos
            next_e_matches = {sig: re.search('[^.]', traces[sig][spos:]) for sig in signals}
            next_e_pos = [next_e_matches[sig].start()
                          if next_e_matches[sig] is not None
                          else len(traces[sig][spos:]) for sig in signals]
            nextChange = min(next_e_pos)
            epos = spos + nextChange
            logging.debug('setting epos to %d = %d + %d', epos, spos, nextChange)

            # if epos - spos >= cutAfter, replace with '|'
            opos += epos - spos
            if epos - spos >= cutAfter:
                logging.info('trimming %d to %d', spos, epos)
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
            logging.info('patching cut ends')
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
        _names = [unichr(xc) for xc in range(0x100, 0x1ff)]
        names2 = [n for n in _names if not n.islower()]
        names.extend(names2)

        traceLen = len(traces[list(signals)[0]])
        for c_i in range(1, traceLen):
            isTransition = any([traces[sig][c_i] in '01' for sig in traces.keys()])
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
        def _sort(a, b):
            if a.group == b.group:
                return cmp(a.order, b.order)
            else:
                return cmp(a.group, b.group)

        return sorted(signals, cmp=_sort)

    def outputAt(self, at, setBits):
        """ set the given sets of bits at the given time.. 

        Parameters
        ----------
        at : int
           the ticks to run the new state at
        setBits : iterable of Bits
           the Bits to enable for the new state.
        """

        if len(self.ticks) == 0 and at != 0:
            self.outputAt(0,set())
        self.enabled.append(setBits)
        self.ticks.append(at)

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
        
        thisSet = newSet.copy()
        newSet.difference_update(turnOff)
        newSet.update(turnOn)
        
        self.logger.debug("  %04x: %08x -> %08x on=%08x, off=%08x",
                          at,
                          self.stateMask(thisSet), 
                          self.stateMask(newSet),
                          self.stateMask(turnOn), 
                          self.stateMask(turnOff))
        self.outputAt(at, newSet)
        

    def outputFor(self, duration, setBits):
        """ set the given sets of bits for the given duration. 

        Parameters
        ----------
        duration : int
           the number of ticks to run the new state for
        setBits : iterable of Bits
           the Bits to enable for the new state.
        """

        self.enabled.append(setBits)
        if len(self.ticks) == 0:
            self.ticks.append(0)
        self.ticks.append(self.ticks[-1]+duration)

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
        
        thisSet = newSet.copy()
        newSet.difference_update(turnOff)
        newSet.update(turnOn)
        
        self.logger.debug("  %04x: %08x -> %08x on=%08x, off=%08x",
                          duration,
                          self.stateMask(thisSet), 
                          self.stateMask(newSet),
                          self.stateMask(turnOn), 
                          self.stateMask(turnOff))
        self.outputFor(duration, newSet)
        
def genRowClocks(ncols, clocksFunc, rowBinning=1):
    """ Instantiate a complete row of clock times and opcodes. 
    
    """
    
    ticksList = []
    opcodesList = []

    pre, pix, par = clocksFunc()

    preTicks, opcodes = pre.genClocks()
    ticksList.extend(preTicks)
    opcodesList.extend(opcodes)

    pixTicks, opcodes = pix.genClocks()
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

