import numpy

class Signal(object):
    def __init__(self, bit, label, description):
        self.bit = bit
        self.label = label
        self.description = description

    def __str__(self):
        "Signal(%s:%d)" % (self.label, self.bit)

    @property 
    def mask(self):
        return 1 << self.bit

class Clocks(object):
    """ Access the FPGA's clocking sequences.

    The FPGA takes a vector of 32-bit words, with the high 17 being a bitmask of 
    signals to set high or low, and the low 15 being the number of clocks to sustain. 
    """

    def __init__(self, tickTime=40e-9, initFrom=None):
        self.clear()
        self.tickTime = tickTime
        if initFrom is not None:
            self.outputAt(0, initFrom.enabled[-1])

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

        states = numpy.zeros(len(self.enabled), dtype='u4')
        durations = numpy.zeros(len(self.enabled), dtype='u4')

        for i in range(len(self.enabled)):
            duration = self.ticks[i+1] - self.ticks[i]
            states[i] = self.stateMask(self.enabled[i])
            durations[i] = duration

        return states, durations

    def signalTrace(self, signal):
        ticks = [0]
        transitions = [signal in self.enabled[0]]
        lastState = transitions[0]

        found = lastState
        for i in range(len(self.ticks)):
            newState = signal in self.enabled[i]
            if newState != lastState:
                ticks.append(self.ticks[i])
                transitions.append(newState)
                lastState = newState
                found = True

        if not found:
            raise KeyError("signal %r not found" % (signal))

        return ticks, transitions

    def genJSON(self, tickDiv=1, cutAfter=5, selectSignals=None):
        json = []
        json.append('{signal: [')

        if selectSignals is None:
            selectSignals = set()
            for e in self.enabled:
                selectSignals = selectSignals.union(e)
            
        for sig in selectSignals:
            json.append("{name: '%s'," % (sig.label))
            ticks, transitions = self.signalTrace(sig)
            trace = []
            trace.append('%d' % (transitions[0]))
            lastTick = ticks[0]
            for t_i in range(1, len(ticks)):
                thisTick = ticks[t_i]
                thisState = transitions[t_i]

                dticks = thisTick - lastTick
                dticks /= tickDiv
                dticks -= 1
                if dticks > cutAfter:
                    trace.append('.'*cutAfter)
                    trace.append('|')
                else:
                    trace.append('.'*dticks)
                trace.append('%d' % (thisState))
            json.append(" wave: '%s'}," % (''.join(trace)))

        json.append("]}")
        return "\n".join(json)

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
            newSet = set()
        else:
            newSet = self.enabled[-1].copy()

        turnOn = set() if turnOn is None else set(turnOn)
        turnOff = set() if turnOff is None else set(turnOff)
        
        thisSet = newSet.copy()
        newSet.difference_update(turnOff)
        newSet.update(turnOn)
        
        print "  %04x: %08x -> %08x on=%08x, off=%08x" % (at,
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
            newSet = set()
        else:
            newSet = self.enabled[-1].copy()

        turnOn = set() if turnOn is None else set(turnOn)
        turnOff = set() if turnOff is None else set(turnOff)
        
        thisSet = newSet.copy()
        newSet.difference_update(turnOff)
        newSet.update(turnOn)
        
        print "  %04x: %08x -> %08x on=%08x, off=%08x" % (duration,
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
    ticksList.append(ticks)
    opcodesList.append(opcodes)

    ticks, opcodes = pix.genClocks()
    for i in range(ncols):
        ticksList.append(ticks)
        opcodesList.append(opcodes)

    ticks, opcodes = post.genClocks()
    ticksList.append(ticks)
    opcodesList.append(opcodes)

    return ticksList, opcodesList
