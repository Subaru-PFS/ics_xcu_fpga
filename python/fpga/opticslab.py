import logging
import socket
import time

"""
### COMMAND SET, as of 2017-08-18

## to change wavelength
# monoCommand( 'wave 650' ) where the number is wavelength in nanometers
# monoCommand( 'wave ?' ) query current wavelength


## to change slit width
# monoCommand( 'slit 5' ) where the number is slit width in millimeters uswe 0.5 - 5
# monoCommand( 'slit ?' ) query slit width
## switch lamp -- switches mono mirror and input shutter
# monoCommand( 'lamp arc' ) switches to arc lamp
# monoCommand( 'lamp qth' ) switches to qth lamp
# monoCommand( 'lamp ?') query current lamp
# monoCommand( 'lamp state' ) query lamp on or off


## to open the shutter indefinitely
# monoCommand( 'open' )
## to close an open shutter
# monoCommand( 'close' )
## to pulse the shutter open
# monoCommand( 'pulse 5' ) where the number is the duration in seconds
# returns
# "OK %s %s %g %g %g %g" % (command, number, current, flux, WAVELENGTH, SLITWIDTH))




## remote power on for lamp
# monoCommand( 'pon') power on
# monoCommand( 'poff') power off




## thorlabs filter wheel
# monoCommand( 'filter n' ) n filter numbers 1 - 6
# monoCommand( 'filter ?' ) query current filter



## Fe 55
# monoCommand( 'fe55 n') n angle to move iron source to 0 - 90 in degrees
# monoCommand( 'fe55 home') move source out of way
# monoCommand( 'fe55 ?') query current angle



## SMB
# monoCommand( 'temp' ) return detector temperature

"""

logger = logging.getLogger('opticsLab')
logger.setLevel(logging.DEBUG)


def opticsLabCommand(cmdStr, timeout=30.0):
    host = 'tron.pfs'
    port = 50000

    try:
        s = socket.create_connection((host, port), 3.0)
    except:
        raise

    t0 = time.time()
    try:
        s.settimeout(timeout)
        s.send('%s\n' % (cmdStr))
        data = s.recv(1024)
        data = data.strip()
    finally:
        s.close()
    t1 = time.time()

    logger.debug("cmd: %r dt=%0.2f", cmdStr, t1-t0)
    
    return data

def query(system, valType):
    ret = opticsLabCommand('%s ?' % (system), timeout=1.0)
    _, val = ret.split()
    if _ != system:
        raise RuntimeError("unexpected response to %s query: %s" % (system, ret))
    return valType(val)
    
def pulseShutter(stime):
    """ Open the shutter for a given time.

    Args:
       pos : 'in' or 'out'
    """
    t0 = time.time()
    ret = opticsLabCommand('pulse %g' % (stime), max(10, stime+6))
    
    parts = ret.split()
    if len(parts) != 7 or parts[0] != 'OK' or parts[1] != 'pulse':
        raise RuntimeError('something went wrong, got %r' % (ret))

    # "OK %s %s %g %g %g %g\n" % (command, number, current, flux, WAVELENGTH, SLITWIDTH)

    current = float(parts[3])
    flux = float(parts[4])
    wavelength = float(parts[5])
    slitwidth = float(parts[6])
    t1 = time.time()

    # Give the PC clock some slack.
    if (t1-t0 + 0.02) < stime:
        raise RuntimeError('remote pulseShutter took less than the requested time! (%g < %g)' % (t1-t0, stime))
    
    return stime, flux, current, wavelength, slitwidth

def getWavelength():
    return query('wave', float)

def getSlitwidth():
    return query('slit', float)

def getFilter():
    return query('filter', int)

def getLamp():
    return query('lamp', str)

def getTemp():
    return query('temp', float)

def setup(arm, wavelength=None, flux=None):
    """ """

    if arm == 'blue':
        lamp = 'arc'
        if wavelength == 5500 and flux == 10:
            slitWidth = 1.0
            filter = 'ND4'
        elif wavelength == 5500 and flux == 1000:
            slitWidth = 0.5
            filter = 'ND2'
        else:
            raise KeyError("unknown preset configuration, sorry.")
    elif arm == 'red':
        raise KeyError("no presets for red yet, sorry.")
    else:
        raise KeyError('unknown arm')

    if getLamp() != lamp:
        raise RuntimeError("the lamp must be set outside of the .setup function")
    if opticsLabCommand('lamp state') != 'lamp on':
        raise RuntimeError('the lamp is not on.')
    
    setSlitwidth(slitWidth)
    setWavelength(wavelength)
    setFilter(filter)

filters = ('Invalid', 'None', 'ND1', 'ND2', 'ND3', 'ND4', 'ND5')

def setFilter(filt):
    """ Set the filter in the beam.

    Args
    ----
    filt : int or string
      If a string, resolves to the known filters:
        %s
    """ % (str(filters))
    
    if isinstance(filt, str):
        slot = filters.index(filt)
    else:
        slot = filt
        
    currSlot = getFilter()
    if slot == currSlot:
        return slot

    if slot < 1 or slot > 6:
        raise KeyError("filter slots are 1..6")
    
    ret = opticsLabCommand('filter %d' % (slot), timeout=10.0)
    if ret != 'filter %d' % (slot):
        raise RuntimeError('failed to move filter: %r' % (ret))

    return slot

def setWavelength(wave):
    """ Set the monochrometer central wavelength

    Args:
       wavelength : int
         If > 2000, treated as Angstroms, else nm.

    Returns:
       wwavelength, in nm.

    """
    if wave > 2000:
        wave = wave // 10
        
    ret = opticsLabCommand('wave %d' % (wave), timeout=5.0)
    if ret != 'wave %4.0f' % (wave):
        raise RuntimeError('failed to adjust monochrometer: %r' % (ret))

    return wave

def setSlitwidth(mm):
    """ Set the monochrometer slit width

    Args:
       mm : slit width.
    """
    ret = opticsLabCommand('slit %g' % (mm), timeout=10.0)
    if ret != 'slit %1.2f' % (mm):
        raise RuntimeError('failed to adjust slit width: %r' % (ret))
        
    return mm

def setLamp(lamp):
    """ Choose the monochrometer lamp.

    Args:
       lamp : 'arc' or 'qth'
    """
    knownLamps = {'qth', 'arc'}
    if lamp not in knownLamps:
        raise ValueError('%s is not one of: %s' % (lamp, knownLamps))
    ret = opticsLabCommand('lamp %s' % (lamp), timeout=10.0)
    if (ret != 'lamp %s' % (lamp)) and (ret != 'lamp already is %s' % (lamp)):
        raise RuntimeError('failed to set lamp: %r' % (ret))
        
    return lamp

def fe55(pos, angle=45):
    """ Move the Fe55 source in or out.

    Args:
       pos : 'in' or 'out'
       angle : float (optional)

    """
    knownPositions = {'in':0, 'out':angle}
    
    if pos not in knownPositions:
        raise ValueError('%s is not one of' % (pos, knownPositions.keys()))
    reqPos = knownPositions[pos]
    ret = opticsLabCommand('fe55' % (reqPos))
    if (ret != 'fe55 %d' % (reqPos)):
        raise RuntimeError('failed to move Fe55 source: %r' % (ret))
        
    return reqPos

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

