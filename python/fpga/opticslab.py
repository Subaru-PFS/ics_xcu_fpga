from past.builtins import basestring

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



def opticsLabCommand(cmdStr, timeout=60.0, dumbFix=False):
    host = 'tron.pfs'
    port = 50000

    if dumbFix:
        fixConnection()

    try:
        s = socket.create_connection((host, port), 3.0)
    except:
        raise

    t0 = time.time()
    try:
        s.settimeout(timeout)
        s.send(('%s\n' % (cmdStr)).encode('latin-1'))
        time.sleep(0.1)
        data = s.recv(1024)
        data = data.strip().decode('latin-1')
    finally:
        s.close()
    t1 = time.time()

    logger.debug("cmd: %r dt=%0.2f", cmdStr, t1-t0)
    
    return data

def query(system, valType):
    ret = opticsLabCommand('%s ?' % (system), timeout=1.0, dumbFix=False)
    _, val = ret.split(None, 2)
    if _ != system:
        raise RuntimeError("unexpected response to %s query: %s" % (system, ret))
    return valType(val)


def fixConnection(nAttempt=0, maxAttempt=5, timeBetweenAttempt=2):
    try:
        query('wave', float)
    except:
        if nAttempt<maxAttempt:
            time.sleep(timeBetweenAttempt)
            return fixConnection(nAttempt+1)
        raise

def pulseShutter(stime):
    """ Open the shutter for a given time.

    Args:
       pos : 'in' or 'out'
    """
    t0 = time.time()
    ret = opticsLabCommand('pulse %g' % (stime), max(10, stime+10))
    
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

def getFe55():
    return query('fe55', int)

def getTemp():
    return query('temp', float)

def getPower():
    """ Fetch the state of the lamp controller. 

    Returns:
      onTime : float
        how many seconds the lamp has been powered up. 0 if off.
    """
    ret = opticsLabCommand('lamp state', timeout=2.0)

    parts = ret.split()
    if parts[0] != 'lamp':
        raise RuntimeError('failed to control power: %r' % (ret))
        
    return float(parts[-1])
    
def setup(arm, wavelength=None, flux=None, clearFe55=True, lamp=None):
    """Set up the optics lab visible illuminator to some pre-baked configurations. 

    In simplest terms, we provide ~10 adu/s and ~1000 adu/s
    configurations. These are only valid for certain wavelengths; QE
    tests will need to do their own configuration.

    Args
    ----
    arm : 'red' or 'blue'
    wavelength : `int`
      The target wavelength. Currently only 550 or 800: the defaults
    flux : `int`
      The desired flux, in ADU/s. Currently only 10 and 1000
    clearFe55 : `bool`
      Whether to actively take the Fe55 source out of the way. Takes a few seconds.
    lamp : `arc` or `qth`
      Override the default lamps (Xe arc for blue, quartz for red).
      The quartz lamp has died, and we do have a valid configuration
      for using Xe on the red side, at 800nm.

    """

    if arm == 'blue':
        if lamp is None:
            lamp = 'arc'
        elif lamp != 'arc':
            raise ValueError('blue lamp must be the Xe arc')
        
        if wavelength is None:
            wavelength = 550

        slitWidth = 1.0
        if wavelength == 550 and flux == 10:
            filter = 'ND3'
            slitWidth = 1.17
        elif wavelength == 550 and flux == 1000:
            filter = 'None'
            slitWidth = 1.11
            
        else:
            raise KeyError("unknown preset configuration, sorry.")
    elif arm == 'red':
        if lamp is None:
            lamp = 'qth'

        if lamp == 'arc':
            if wavelength is None:
                wavelength = 800
            if wavelength == 800 and flux == 10:
                slitWidth = 1.1
                filter = 'ND4'
            elif wavelength == 800 and flux == 1000:
                slitWidth = 1.0
                filter = 'None'
        elif lamp == 'qth':
            if wavelength is None:
                wavelength = 800
            if wavelength == 800 and flux == 10:
                slitWidth = 1.75
                filter = 'ND4'
            elif wavelength == 800 and flux == 1000:
                slitWidth = 1.75
                filter = 'None'
        
        else:
            raise KeyError("unknown preset configuration, sorry. Look at the code.")

    else:
        raise KeyError('unknown arm')

    if clearFe55:
        setFe55('home')
    setSlitwidth(slitWidth)
    setWavelength(wavelength)
    setFilter(filter)

    if getLamp() != lamp:
        raise RuntimeError("the lamp must be set outside of the .setup function")
    power = getPower()
    if power == 0:
        raise RuntimeError('the lamp is not on.')
    if power < 900:
        raise RuntimeError(f'the lamp has not been warmed for 15 min ({900-power} seconds left).')

filters = ('Invalid', 'None', 'ND1', 'ND2', 'ND3', 'ND4', 'ND5')

def setFilter(filt):
    """ Set the filter in the beam.

    Args
    ----
    filt : int or string
      If a string, resolves to the known filters:
        %s
    """ % (str(filters))
    
    if isinstance(filt, basestring):
        slot = filters.index(filt)
    else:
        slot = filt
        
    currSlot = getFilter()
    if slot == currSlot:
        return slot

    if slot < 1 or slot > 6:
        raise KeyError("filter slots are 1..6:%s"%slot)
    
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

def setPower(onOff):
    """ Turn the lamp on or off

    Args:
       onOff : bool
    """

    if onOff == 'on':
        onOff = True
    if onOff == 'off':
        onOff = False

    command = 'pon' if onOff else 'poff'
    opticsLabCommand(command, timeout=2.0)
    
    return getPower()

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

def setFe55(pos):
    """ Move the Fe55 source in or out.

    Args:
       pos : 'home' or 0..90

    """
    
    if pos != 'home':
        if (int(pos) < 0 or int(pos) > 90):
            raise ValueError('%s is not home or 0..90' % (pos))
    
    if pos == 'home':
        pos = 0
    
    ret = opticsLabCommand('fe55 %s' % (pos))

    if pos == 0 and ret != 'fe55  0':
        raise RuntimeError('failed to home Fe55 source: %r' % (ret))
    elif (ret != 'fe55 %2d' % (pos)):
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

