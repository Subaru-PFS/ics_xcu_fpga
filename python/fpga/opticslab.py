import socket
import time

def pulseShutter(stime, wavelength=None):
    host = '127.0.0.1'
    port = 10101

    t0 = time.time()
    print "pulsing shutter for %g seconds..." % (stime)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    if wavelength is None:
        s.send('shut %g\n' % (stime))
    else:
        s.send('shut %g %g\n' % (stime, wavelength))
        
    data = s.recv(1024)
    if data[:2] != 'OK':
        raise RuntimeError('something went wrong, got %s' % (data))
    flux = float(data.split()[-1])
    current = float(data.split()[-2])
    t1 = time.time()

    if t1-t0 < stime:
        raise RuntimeError('remote pulseShutter took less than the requested time!')
    
    s.close()
    
    return stime, flux, current, flux*stime

def monoSetWavelength(wave):
    host = '127.0.0.1'
    port = 50000
    
    print "setting wavelength to %g..." % (wave)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    s.send('wave %d\n' % (wave))
    data = s.recv(1024)
    s.close()

    if data != 'moved to %4d' % (wave):
        raise RuntimeError('failed to adjust monochrometer: %s' % (data))

    return wave

def monoSetSlitwidth(mm):
    host = '127.0.0.1'
    port = 50000
    
    print "setting slit width to %g mm..." % (mm)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    s.send('slit %g\n' % (mm))
    data = s.recv(1024)
    s.close()
    
    return data

def monoSetLamp(lampID):
    host = '127.0.0.1'
    port = 50000
    
    print "setting lamp to %s..." % (lampID)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    s.send('lamp %d\n' % (lampID))
    data = s.recv(1024)
    s.close()
    
    return data

