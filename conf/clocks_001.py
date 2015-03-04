from clocks import Signal, Clocks

CRC = Signal(15, 'CRC', 'CRC Control')
P1  = Signal(16, 'P1', 'Parallel 1')
P2  = Signal(17, 'P2', 'Parallel 2')
P3  = Signal(18, 'P3', 'Parallel 3')

TG  = Signal(19, 'TG', 'Transfer Gate')
S1  = Signal(20, 'S1', 'Serial 1')
S2  = Signal(21, 'S2', 'Serial 2')
RG  = Signal(22, 'RG', 'Reset Gate')

SW  = Signal(23, 'SW', 'Summing Well')
DCR = Signal(24, 'DCR', 'DC Restore')
IR  = Signal(25, 'IR', 'Integrate Reset')
I_M = Signal(26, 'I_M', 'Integrate Minus')

I_P = Signal(27, 'I_P', 'Integrate Plus')
CNV = Signal(28, 'CNV', 'ADC Convert')
SCK = Signal(29, 'SCK', 'ADC SCK Burst')
DG  = Signal(30, 'DG', 'Drain Gate')

IRQ = Signal(31, 'IRQ', 'Interrupt')

signals = (P1, P2, P3, TG, CRC, IRQ,
           S1, S2, RG, SW,
           DCR, IR, I_M, I_P, DG,
           CNV, SCK)

def standardClocks(tickTime=40e-9):
    pre = Clocks(tickTime)
    pre.changeFor(duration=120,
                  turnOn= [P2,TG,S1,RG,SW,CNV,DG])
    
    pix = Clocks(tickTime, initFrom=pre)
    pix.changeFor(duration=16,
                  turnOff=[S1,RG],
                  turnOn= [S2,DCR,IR,SCK])

    pix.changeFor(duration=8,
                  turnOff=[SCK],
                  turnOn= [RG])

    pix.changeFor(duration=8,
                  turnOff=[S2,SW,IR],
                  turnOn= [S1])

    pix.changeFor(duration=4,
                  turnOff=[DCR])

    pix.changeFor(duration=4,
                  turnOff=[CNV])

    pix.changeFor(duration=120,
                  turnOn= [I_M])

    pix.changeFor(duration=8,
                  turnOff=[I_M],
                  turnOn= [SW])

    pix.changeFor(duration=120,
                  turnOn=[I_P])

    pix.changeFor(duration=4,
                  turnOff=[I_P])

    pix.changeFor(duration=56,
                  turnOn= [CNV])

    post = Clocks(tickTime, initFrom=pix)
    post.changeFor(duration=1000,
                   turnOff=[RG],
                   turnOn= [P1,DCR])

    post.changeFor(duration=1000,
                   turnOff=[P2,TG],
                   turnOn= [CRC])

    post.changeFor(duration=1000,
                   turnOff=[CRC],
                   turnOn= [P3])

    post.changeFor(duration=1000,
                   turnOff=[P1])

    post.changeFor(duration=1000,
                   turnOn= [P2,TG])

    post.changeFor(duration=1000,
                   turnOn= [P3])

    post.changeFor(duration=50,
                   turnOn= [RG])

    post.changeFor(duration=2,
                   turnOff= [DCR])

    return pre, pix, post
