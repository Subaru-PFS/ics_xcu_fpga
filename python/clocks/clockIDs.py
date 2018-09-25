class Signal(object):
    def __init__(self, bit, label, description, group=None, order=0):
        self.bit = bit
        self.label = label
        self.description = description
        self.group = group
        self.order = order

    def __str__(self):
        return "Signal(%s:%d)" % (self.label, self.bit)

    def __repr__(self):
        return "Signal(%s,%s,%s,%s,%s)" % (self.bit, self.label,
                                           self.description,
                                           self.group, self.order)
    
    @property 
    def mask(self):
        return 1 << self.bit


CRC = Signal(15, 'CRC', 'CRC Control', group='FPGA', order=0)
P1  = Signal(16, 'P1', 'Parallel 1', group='Parallel', order=0)
P2  = Signal(17, 'P2', 'Parallel 2', group='Parallel', order=1)
P3  = Signal(18, 'P3', 'Parallel 3', group='Parallel', order=2)
TG  = Signal(19, 'TG', 'Transfer Gate', group='Parallel', order=3)

S1  = Signal(20, 'S1', 'Serial 1', group='Serial', order=1)
S2  = Signal(21, 'S2', 'Serial 2', group='Serial', order=2)
RG  = Signal(22, 'RG', 'Reset Gate', group='Serial', order=3)

SW  = Signal(23, 'SW', 'Summing Well', group='Serial', order=4)
DCR = Signal(24, 'DCR', 'DC Restore', group='Serial', order=5)
IR  = Signal(25, 'IR', 'Integrate Reset', group='Serial', order=6)
I_M = Signal(26, 'I_M', 'Integrate Minus', group='Serial', order=7)
I_P = Signal(27, 'I_P', 'Integrate Plus', group='Serial', order=8)

CNV = Signal(28, 'CNV', 'ADC Convert', group='FPGA', order=1)
SCK = Signal(29, 'SCK', 'ADC SCK Burst', group='FPGA', order=2)
DG  = Signal(30, 'DG', 'Dump Gate', group='Serial', order=9)

IRQ = Signal(31, 'IRQ', 'Interrupt')

signals = (P1, P2, P3, TG, CRC, IRQ,
           S1, S2, RG, SW,
           DCR, IR, I_M, I_P, DG,
           CNV, SCK)

signalsByName = {s.label:s for s in signals}
