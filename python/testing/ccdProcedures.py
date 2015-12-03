import time

import fee.feeControl as feeMod
import fpga.ccdFuncs as ccdFuncs

reload(ccdFuncs)

class FeeTweaks(object):
    """ Interpose into fee.setMode() to override bias voltages after
        mode has been loaded from PROM.
            """
    
    def __init__(self):
        self.modes = dict()

    def setMode(self, mode):
        fee = feeMod.fee
    
        print "setting mode: ", mode
        fee.setMode(mode)
        if mode in self.modes:
            for vname, val in self.modes[mode].iteritems():
                self.setVoltage(None, vname, val)
        time.sleep(0.25)

    def setVoltage(self, mode, vname, val):

        if mode is not None:
            raise RuntimeError("tweaked modes can only set runtime voltages")
        
        fee = feeMod.fee
    
        oldVals = [fee.doGet('bias', vname, ch) for ch in 0,1]
        [fee.doSet('bias', vname, val, ch) for ch in 0,1]
        time.sleep(0.25)
        newVals = [fee.doGet('bias', vname, ch) for ch in 0,1]
        print("%s %0.1f,%0.1f -> %0.1f,%0.1f (%0.1f)" %
              (vname, oldVals[0], oldVals[1], newVals[0], newVals[1], val))

    def tweakMode(self, mode, doClear=True, **kws):
        if doClear:
            self.modes[mode] = dict()
        for k, v in kws.iteritems():
            self.modes[mode][k] = v

def stdExposures_biases(nwipes=1,
                        nbias=10,
                        feeControl=None,
                        comment=''):

    ccdFuncs.expSequence(nwipes=nwipes, 
                         nbias=nbias,
                         feeControl=feeControl,
                         comment=comment,
                         title='%d biases' % (nbias))
    
def stdExposures_base(nrows=None, ncols=None, comment='base exposures'):
    tweaks = FeeTweaks()

    ccdFuncs.expSequence(nrows=nrows, ncols=ncols,
                         nwipes=0, 
                         nbias=20, 
                         nendbias=1, 
                         darks=[300,300,300, 1200, 3600], 
                         flats=[], 
                         feeControl=tweaks,
                         comment=comment,
                         title='base sequence')

def stdExposures_VOD_VOG(nrows=None, ncols=None,
                         comment='VOD/VOG tuning'):
    
    tweaks = FeeTweaks()

    ccdFuncs.expSequence(nrows=nrows, ncols=ncols,
                         nwipes=0, 
                         nbias=6, 
                         flats=[], 
                         feeControl=tweaks,
                         comment=comment,
                         title='pre-VOD/VOG tuning biases')
            
    for VOD in -21, -22:
        for VOG in -4.5, -5:
            tweaks = FeeTweaks()
            tweaks.tweakMode('read', OD=VOD, OG=VOG)

            ccdFuncs.expSequence(nrows=nrows, ncols=ncols,
                                 nwipes=0, 
                                 nbias=0, 
                                 flats=[3,3], 
                                 feeControl=tweaks,
                                 comment=comment,
                                 title='VOD/VOG tuning (%0.1f, %0.1f)' % (VOD, VOG))
            
def stdExposures_allFlats(comment='all flats'):
    tweaks = FeeTweaks()

    explist = (('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('flat', 2),
               ('flat', 2),
               ('flat', 4),
               ('flat', 4),
               ('flat', 6),
               ('flat', 8),
               ('flat', 8),
               ('flat', 2),
               
               ('bias', 0),
               ('flat', 12),
               ('flat', 16),
               ('flat', 16),
               ('flat', 2),
               
               ('bias', 0),
               ('flat', 24),
               ('flat', 32),
               ('flat', 2),
               
               ('bias', 0),
               ('flat', 48),
               ('flat', 64),
               ('flat', 64),
               ('flat', 2),
               
               ('bias', 0),
               ('flat', 96),
               ('flat', 128),
               ('flat', 2),
               
               ('bias', 0),
               ('flat', 160),
               ('flat', 160),
               ('flat', 2),
               
               ('bias', 0),
               ('flat', 192),
               ('flat', 256),
               ('flat', 2),
               
               ('bias', 0))
    
    ccdFuncs.expList(explist,
                     feeControl=tweaks,
                     comment=comment,
                     title='all flats')
    

def stdExposures_wipes(comment=''):
    tweaks = FeeTweaks()

    explist = (('wipe', 1),
               
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('flat', 10),
               ('bias', 0),
               
               ('flat', 16),
               ('bias', 0))

    ccdFuncs.expList(explist,
                     feeControl=tweaks,
                     comment='wipe tests',
                     title='wipe tests')
