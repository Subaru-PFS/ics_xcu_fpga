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
                self.setVoltage(vname, val)
        time.sleep(0.25)

    def setVoltage(self, vname, val):
        fee = feeMod.fee
    
        oldVals = [fee.doGet('bias', vname, ch) for ch in 0,1]
        [fee.doSet('bias', vname, val, ch) for ch in 0,1]
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
    
def stdExposures_base(nrows=None, ncols=None, comment=''):
    tweaks = FeeTweaks()
    tweaks.tweakMode('read', OD=-19.0, OG=-4.5)

    ccdFuncs.expSequence(nrows=nrows, ncols=ncols,
                         nwipes=2, 
                         nbias=10, 
                         nendbias=1, 
                         darks=[300,300, 1200], 
                         flats=[10,10,10], 
                         feeControl=tweaks,
                         comment=comment,
                         title='base sequence')

def stdExposures_VOD_VOG(nrows=None, ncols=None,
                         comment=''):
    
    tweaks = FeeTweaks()
    tweaks.tweakMode('read', OD=-19, OG=-4.5)

    ccdFuncs.expSequence(nrows=nrows, ncols=ncols,
                         nwipes=2, 
                         nbias=0, 
                         nendbias=0, 
                         darks=[], 
                         flats=[], 
                         feeControl=tweaks,
                         comment='clearing',
                         title='VOD/VOG tuning')
    
    for VOD in -18, -19, -20, -21:
        for VOG in -4, -4.5, -5:
            tweaks = FeeTweaks()
            tweaks.tweakMode('read', OD=VOD, OG=VOG)

            ccdFuncs.expSequence(nrows=nrows, ncols=ncols,
                                 nwipes=1, 
                                 nbias=1, 
                                 nendbias=0, 
                                 darks=[], 
                                 flats=[1], 
                                 feeControl=tweaks,
                                 comment=comment,
                                 title='VOD/VOG tuning')
            
def stdExposures_allFlats(comment=''):
    tweaks = FeeTweaks()
    tweaks.tweakMode('read', OD=-19.0, OG=-4.5)

    explist = (('wipe', 2),

               ('bias', 0),
               ('flat', 2),
               ('flat', 2),
               ('flat', 4),
               ('flat', 6),
               ('flat', 8),
               ('flat', 8),
               ('flat', 2),

               ('bias', 0),
               ('flat', 10),
               ('flat', 12),
               ('flat', 2),
               
               ('bias', 0),
               ('flat', 14),
               ('flat', 16),
               ('flat', 2),

               ('bias', 0),
              )
    ccdFuncs.expList(explist,
                     feeControl=tweaks,
                     comment='all flats',
                     title='all flats')
        

def stdExposures_wipes(comment=''):
    tweaks = FeeTweaks()
    tweaks.tweakMode('read', OD=-19.0, OG=-4.5)

    explist = (('wipe', 1),

               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('bias', 0),
               ('flat', 10),
               ('bias', 0),
               
               ('flat', 16),
               ('bias', 0)
              )

    ccdFuncs.expList(explist,
                     feeControl=tweaks,
                     comment='wipe tests',
                     title='wipe tests')
