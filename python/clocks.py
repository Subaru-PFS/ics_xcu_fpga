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

    def __init__(self, tickTime=40e-9, initFrom=None, logLevel=logging.INFO):
        self.clear()
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
            if newState != lastState:
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

    def genJSON(self, tickDiv=2, cutAfter=20, signals=None, includeAll=False):
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
        
        for sig in signals:
            ticks, states = self.signalTrace(sig)
            trace = ''
            lastTick = ticks[0]-1
            lastState = None
            for t_i in range(len(ticks)):
                thisTick = ticks[t_i]
                thisState = states[t_i]

                dticks = (thisTick - lastTick)/tickDiv
                assert (thisTick <= 0 or dticks > 0), "dticks for %s at slot %s, tick %s to %s is non-positive!" % (sig, t_i, lastTick, thisTick)
                assert (dticks == int(dticks)), "dticks for %s at slot %s, tick %s to %s is non-integer!" % (sig, t_i, lastTick, thisTick)
                    
                trace += '.'*(dticks-1)

                if thisState != lastState:
                    trace += '%d' % (thisState)
                else:
                    trace += '.'
                self.logger.debug("%s: %d tick=%d dtick=%d len=%d (%d)",
                                  sig.label, t_i, ticks[t_i], dticks,
                                  len(trace), len(trace)*tickDiv)
                lastTick = thisTick
                lastState = thisState
            traces[sig] = trace

        # Collapse long runs with '|'
        #    find next epos from spos where any trace is not '.'
        #    if epos-spos > cutAfter:
        #       traces[spos:epos] = '|'
        spos = 0
        opos = 0
        cutSpans = []
        orig = traces.copy()
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
            next_e_pos = [next_e_matches[sig].start() if next_e_matches[sig] is not None else len(traces[sig][spos:]) for sig in signals]
            nextChange = min(next_e_pos)
            epos = spos + nextChange
            logging.debug('setting epos to %d = %d + %d', epos, spos, nextChange)

            # if epos - spos >= cutAfter, replace with '|'
            opos += epos - spos
            if epos - spos >= cutAfter:
                logging.debug('trimming %d to %d', spos, epos)
                for sig in signals:
                    ts = traces[sig]
                    traces[sig] = ts[:spos] + '|' + ts[epos:]
                cutSpans.append([opos, opos+(epos-spos)])
            else:
                spos = epos
                
        json = []
        json.append('{signal: [')

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

        if len(cutSpans) > 0:
            nodes = traces[(list(signals))[0]].replace('0','.').replace('1','.')
            edges = 'edge: ['
            cut_n = 0
            while True:
                cut_i = nodes.find('|')
                if cut_i == -1:
                    break
                cutChars = chr(ord('a')+(2*cut_n)) + chr(ord('b')+(2*cut_n))
                nodes = nodes[:cut_i] + cutChars + nodes[cut_i+2:]

                cutLen = cutSpans[cut_n][1] - cutSpans[cut_n][0]
                edges = edges + ("'%s-%s %d'," % (cutChars[0], cutChars[1], cutLen))
                cut_n += 1
            edges = edges + "],"

        if group is not None:
            json.append("],")

        if len(cutSpans) > 0:
            json.append("{},")
            json.append("{node: '%s'}," % (nodes))

        json.append("],")

        if len(cutSpans) > 0:
            json.append(edges)

        json.append("foot: {tick:-1},")
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
        
def genRowClocks(ncols, clocksFunc):
    ticksList = []
    opcodesList = []

    pre, pix, post = clocksFunc()

    ticks, opcodes = pre.genClocks()
    ticksList.extend(ticks)
    opcodesList.extend(opcodes)

    ticks, opcodes = pix.genClocks()
    for i in range(ncols):
        ticksList.extend(ticks)
        opcodesList.extend(opcodes)

    ticks, opcodes = post.genClocks()
    ticksList.extend(ticks)
    opcodesList.extend(opcodes)

    return (np.array(ticksList, dtype='u2'), 
            np.array(opcodesList, dtype='u4'))

