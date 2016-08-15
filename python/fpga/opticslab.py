import socket
import time

def opticsLabCommand(cmdStr):
    host = '127.0.0.1'
    port = 50000

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        s.send('%s\n' % (cmdStr))
        data = s.recv(1024)
        data = data.strip()
    finally:
        s.close()
        
    return data

def pulseShutter(stime):
    """ Move the cold shutter in or out.

    Args:
       pos : 'in' or 'out'
    """
    t0 = time.time()
    ret = opticsLabCommand('pulse %g' % (stime))
    parts = ret.split()
    if parts[0] != 'OK' or parts[1] != 'pulse':
        raise RuntimeError('something went wrong, got %r' % (ret))

    flux = float(parts[3])
    current = float(parts[4])
    wavelength = float(parts[5])
    slitwidth = float(parts[6])
    t1 = time.time()

    if t1-t0 < stime:
        raise RuntimeError('remote pulseShutter took less than the requested time!')
    
    return stime, flux, current, wavelength, slitwidth

def monoSetWavelength(wave):
    ret = opticsLabCommand('wave %d' % (wave))
    if ret != 'moved to %4.0f' % (wave):
        raise RuntimeError('failed to adjust monochrometer: %r' % (ret))

    return wave

def monoSetSlitwidth(mm):
    """ Set the monochrometer slit width

    Args:
       mm : slit width.
    """
    ret = opticsLabCommand('slit %g' % (mm))
    if ret != 'slit width %1.2f' % (mm):
        raise RuntimeError('failed to adjust slit width: %r' % (ret))
        
    return mm

def monoSetLamp(lamp):
    """ Choose the monochrometer lamp.

    Args:
       lamp : 'arc' or 'qth'
    """
    knownLamps = {'qth', 'arc'}
    if lamp not in knownLamps:
        raise ValueError('%s is not one of: %s' % (lamp, knownLamps))
    ret = opticsLabCommand('lamp %s' % (lamp))
    if (ret != 'lamp %s' % (lamp)) and (ret != 'lamp already is %s' % (lamp)):
        raise RuntimeError('failed to set lamp: %r' % (ret))
        
    return lamp

def fe55(pos):
    """ Move the Fe55 source in or out.

    Args:
       pos : 'in' or 'out'
    """
    knownPositions = {'in', 'out'}
    if pos not in knownPositions:
        raise ValueError('%s is not one of' % (pos, knownPositions))
    ret = opticsLabCommand('iron' % (pos))
    if (ret != 'iron %s' % (pos)):
        raise RuntimeError('failed to move Fe55 source: %r' % (ret))
        
    return pos

def coldShutter(pos):
    """ Move the cold shutter in or out.

    Args:
       pos : 'in' or 'out'
    """
    
    knownPositions = {'in', 'out'}
    if pos not in knownPositions:
        raise ValueError('%s is not one of' % (pos, knownPositions))
    ret = opticsLabCommand('cold' % (pos))
    if (ret != 'cold %s' % (pos)):
        raise RuntimeError('failed to move cold shutter: %r' % (ret))
        
    return pos

