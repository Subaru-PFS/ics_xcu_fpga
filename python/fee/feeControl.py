#!/usr/bin/env python

import argparse
import inspect
import logging
import sys
import threading
import time

from collections import OrderedDict

import numpy as np

import astropy.io.fits as fits
import serial

fee = None

def clipFloat(v, ndig=2):
    return np.round(float(v), ndig)

class ModePreset(object):
    def __init__(self, name):
        self.name = name
        self.presets = None

    def __str__(self):
        return ("ModePreset(name=%s, %s)" %
                (self.name,
                 None if self.presets is None else ', '.join(["%s=%s" % (k,v)
                                                              for k,v in self.presets.items()])))

    def define(self, preload=None, force=False, 
               P_off =None, P_on =None,
               S_off =None, S_on =None,
               DG_off=None, DG_on=None,
               SW_off=None, SW_on=None,
               RG_off=None, RG_on=None,
               OG=None,
               RD=None,
               OD=None,
               BB=None):

        if self.presets is not None and not force:
            raise RuntimeError("Mode preset values can only be defined once.")

        argValues = inspect.getargvalues(inspect.currentframe())

        if preload is not None:
            self.presets = preload.presets.copy()
        elif self.presets is None:
            self.presets = OrderedDict()

        for k in argValues.args:
            if k in ('self', 'force', 'preload'):
                continue
            v = argValues.locals[k]
            if v is not None:
                self.presets[k] = v
            else:
                if preload is None:
                    raise RuntimeError("All voltages must be defined for non-preloaded modes")

    def saveToFee(self, fee, channels=(0,1)):
        oldTimeout = fee.device.timeout
        fee.device.timeout = 5.0
        if False and self.preload:
            fee.sendCommandStr('lp,%s' % (self.name))
        for ch in channels:
            for k, v in self.presets.items():
                if v is not None:
                    fee.doSet('bias', k, v, ch)
        fee.sendCommandStr('sp,%s' % (self.name))
        fee.device.timeout = oldTimeout

class FeeSet(object):
    channels = []

    def __init__(self, name, letter, subs=(), 
                 setLetter='s', readLetter='r', getLetter='g',
                 converter=None):
        self.name = name
        self.letter = letter
        self.subs = subs
        self.setLetter = setLetter
        self.readLetter = readLetter
        self.getLetter = getLetter
        self.converter = converter if converter is not None else str

    @property
    def hasAll(self):
        return 'all' in self.subs
        
    def _getCmdString(self, cmdLetter, *parts):
        allParts = ["%s%s" % (cmdLetter, self.letter)]
        allParts.extend(parts)
        return ','.join(allParts)

    def setVal(self, subName, value):
        """ Return the command string for a 'set' function. """

        if not self.setLetter:
            raise RuntimeError("Cannot set %s(%s)!" % (self.name, subName))
        if subName not in self.subs:
            raise RuntimeError("Cannot set unknown %s (%s). Valid=%s" % (self.name, subName,
                                                                         self.subs))
        if value:
            return self._getCmdString(self.setLetter, subName, str(value))
        else:
            return self._getCmdString(self.setLetter, subName)

    def _getVal(self, subName, letter):
        """ Return the command string for a 'get' function. """

        if not letter:
            raise RuntimeError("Cannot get %s(%s)!" % (self.name, subName))

        if subName:
            if subName not in self.subs:
                raise RuntimeError("Cannot get unknown %s (%s) Valid=%s" % (self.name, subName,
                                                                            self.subs))
            return self._getCmdString(letter, subName)
        else:
            return self._getCmdString(letter)

    def getVal(self, subName, channel=None):
        """ Return the command string for a 'get' function. """

        if channel is not None:
            raise RuntimeError("%s sets do not have channels" % (self.name))
        
        return self._getVal(subName, self.getLetter)

    def readVal(self, subName):
        """ Return the command string for a 'read' function. """

        if channel is not None:
            raise RuntimeError("%s sets do not have channels" % (self.name))
        
        return self._getVal(subName, self.readLetter)

    def _ampName(self, ampNum, leg='n'):
        """ Return the FEE controller's name for an amp (just for the so command). 

        Parameters
        ----------
        ampNum - int
           The 0..namps-1 index of an amp.
        leg -- ('n','p')
           Negative or Positive leg. 
        """

        ampNum = int(ampNum)
        return "%d%s,ch%d" % (ampNum%4, leg, ampNum//4)

class FeeChannelSet(FeeSet):
    channels = [0,1]

    def setVal(self, subName, channel, value):
        """ Return the command string for a 'set' function. """

        if not self.setLetter:
            raise RuntimeError("Cannot set %s(%s)!" % (self.name, subName))
        if subName not in self.subs:
            raise RuntimeError("Cannot set unknown %s (%s). Valid=%s" % (self.name, subName,
                                                                         self.subs))
        if channel not in (0,1):
            raise RuntimeError("Channel must be 0 or 1 (%s) for %s(%s)!" % (channel, self.name, subName))
            
        return self._getCmdString(self.setLetter, subName, 'ch%d' % (channel), str(value))

    def _getVal(self, subName, channel, letter):
        """ Return the command string for a 'get' function. """

        if not letter:
            raise RuntimeError("Cannot get %s(%s)!" % (self.name, subName))

        if channel not in (0,1):
            raise RuntimeError("Channel must be 0 or 1 (%s) for %s(%s)!" % (channel, self.name, subName))
            
        if subName not in self.subs:
            raise RuntimeError("Cannot get unknown %s (%s) Valid=%s" % (self.name, subName,
                                                                        self.subs))
        return self._getCmdString(letter, subName, 'ch%d' % (channel))

    def getVal(self, subName, channel):
        """ Return the command string for a 'get' function. """

        return self._getVal(subName, channel, self.getLetter)

    def readVal(self, subName, channel):
        """ Return the command string for a 'read' function. """

        return self._getVal(subName, channel, self.readLetter)

class FeeControl(object):
    def __init__(self, port=None, logLevel=logging.DEBUG, sendImage=None,
                 noConnect=False, noPowerup=False, fpga=None):

        global fee
        
        if port is None:
            port = '/dev/ttyS1'
        self.logger = logging.getLogger()
        self.logger.setLevel(logLevel)
        self.device = None
        self.deviceLock = threading.RLock()
        self.status = OrderedDict()
        self.devConfig = dict(port=port, 
                              baudrate=38400,
                              timeout=2.0)  # The RTD routines need > 0.5s.
        self.devConfig['writeTimeout'] = 2.0 # 10 * 1.0/(self.devConfig['baudrate']/8.0)
        self.EOL = '\n'
        self.ignoredEOL = '\r'

        self.lockConfig()
        self.defineCommands()

        self.defineModes()

        if noConnect is True:
            return
        self.setDevice(port)

        if sendImage is not None:
            self.sendImage(sendImage)
        else:
            if not noPowerup:
                self._powerUp(fpga=fpga)

        fee = self

    def __str__(self):
        return ("FeeControl(port=%s, device=%s)" %
                (self.devConfig['port'],
                 self.device))
    
    def setDevice(self, devName):
        """ """
        self.devName = devName
        self.connectToDevice()

    def connectToDevice(self):
        """ Establish a new connection to the FEE. Any old connection is closed.  """

        if self.device:
            self.device.close()
            self.device = None

        if self.devName:
            self.device = serial.Serial(**self.devConfig)

    def calibrate(self):
        """ Perform all FEE calibrations.

        That is:
          - load the mode voltages.
          - run the CDS calibration
          - run the bias calibration.
        """

        self.saveModesOnFee()
        self.setMode('read')
        time.sleep(1)
        self.raw('cal,CDS')
        self.raw('cal,bias')
        self.setMode('idle')
        
    def _powerUp(self, preset='idle', fpga=None):
        """ Bring the FEE up to a sane and useable configuration. 

        Specifically, and in order: 
          1. mode voltage set (default=idle)
          2. Configure the integrator level (INSTRM-486)
          3. power supplies on
          4. clocks enabled, but idle.
        """

        self.setMode(preset)

        self.sendCommandStr('se,5V,on')
        self.sendCommandStr('se,12V,on')
        self.sendCommandStr('se,24V,on')
        self.sendCommandStr('se,54V,on')
        self.sendCommandStr('se,54V,on')

        if fpga is None:
            self.logger.warn('NO FPGA available to configure I+,I-,IR')
        else:
            from clocks.clockIDs import I_P, I_M, IR
            fpga.setClockLevels(turnOff=[I_P], turnOn=[I_M, IR])
            time.sleep(0.25)
            
        self.sendCommandStr('se,LVDS,on')
        self.sendCommandStr('se,Clks,on')

        self.setMode('offset')
        self.setMode(preset)

        # Finally, enable the preamp feeds.
        self.sendCommandStr('se,PA,on') 
        self.sendCommandStr('se,Vbb0,on')
        self.sendCommandStr('se,Vbb1,on')

        # Send a spurious read, to paper over a device error on the first read.
        self.sendCommandStr('ro,2p,ch1')

    def doGetAll(self, cset):
        pass
    
    def getCommandStatus(self, cset):
        """ Return the values for all of a cset's items.

        Args
        ----
        cset    - one of our ChannelSets, or its name.


        Notes
        -----

        If available, uses the 'all' command to fetch all values in one transaction.
        """
        
        status = OrderedDict()

        if isinstance(cset, str):
            cset = self.commands[cset]
            
        if cset.getLetter is None:
            return status

        try:
            csubs = cset.subs[:]
            csubs.remove('all')
            hasAll = True
        except:
            csubs = cset.subs
            hasAll = False
            
        if cset.channels:
            for chan in cset.channels:
                if hasAll:
                    allVals = self.doGet(cset.name, 'all', chan)
                    if len(allVals) != len(csubs):
                        raise IndexError("getAll returned %d items instead of the required %d" % (len(allVals),
                                                                                                  len(csubs)))
                    allVals = OrderedDict(list(zip(csubs, allVals)))
                else:
                    allVals = OrderedDict()
                    for k in cset.subs:
                        allVals[k] = self.doGet(cset.name, k, chan)
                    
                for k in csubs:       
                    status["%s.ch%d.%s" % (cset.name, chan, k)] = allVals[k]
        else:
            if hasAll:
                allVals = self.doGet(cset.name, 'all')
                if len(allVals) != len(csubs):
                    raise IndexError("getAll returned %d items instead of the required %d" % (len(allVals),
                                                                                              len(cset.subs)))
                allVals = OrderedDict(list(zip(csubs, allVals)))
            else:
                allVals = OrderedDict()
                for k in csubs:
                    allVals[k] = self.doGet(cset.name, k)
                    
            for k in csubs:       
                status["%s.%s" % (cset.name, k)] = allVals[k]

        self.status.update(status)
        return status

    def getAllStatus(self, skip=None):
        newStatus = OrderedDict()

        if skip is None:
            skip = set()
        else:
            skip = set(skip)
    
        for csetName in list(self.commands.keys()):
            t0 = time.time()
            if csetName in skip:
                continue
            cmdStatus = self.getCommandStatus(csetName)
            newStatus.update(cmdStatus)
            t1 = time.time()
            self.logger.debug("get all %s: %0.2fs" % (csetName, t1-t0))
                
        self.status = newStatus
        return self.status

    def getTemps(self):
        """ Return readings from all temperature sensors. 

        Returns:
        FEE, PA, ccd0, ccd1 : float
          If a ccd temp is under range (144.38K), it will be -1
        """
        
        temps = dict()
        rawVals = self.sendCommandStr('rt,all')
        vals = rawVals.split(',')
        for p_i, probe in enumerate(('ccd0', 'ccd1', 'FEE', 'PA')):
            temp = float(vals[p_i])
            temps[probe] = temp if (temp >=0 and temp <= 350) else -1

        return temps
                         
    def powerDown(self):
        """ Bring the FEE down to a sane and stable idle. """

        self.sendCommandStr('se,Clks,off')
        self.sendCommandStr('se,all,off')

    def printStatus(self):
        for k, v in self.status.items():
            print(k, ': ', v)

    def statusAsCards(self, useCache=False):
        if useCache is False:
            self.getAllStatus()
        cards = []
        for k,v in self.status.items():
            c = fits.Card('HIERARCH %s' % (k), v)
            cards.append(c)
                    
        return cards

    def lockConfig(self):
        self.logger.warn('locking firmware configuration')
        self.lockedConfig = True

    def unlockConfig(self):
        self.logger.warn('unlocking firmware configuration')
        self.lockedConfig = False

    def setSerial(self, serialType, serial):
        if serialType not in ('ADC', 'PA0', 'CCD0', 'CCD1'):
            raise RuntimeError("unknown serial number type: %s" % (serialType))

        if self.lockedConfig:
            raise RuntimeError("FEE configuration is locked!")
            
        self.sendCommandStr('ss,%s,%s' % (serialType, serial))
        
    def _defineFullCommand(self, cmdSet):
        """ For a passed commandset, create methods to set&get values."""

        self.commands[cmdSet.name] = cmdSet

    def defineModes(self):
        self.presets = OrderedDict()

        # Note that per JEG, idle mode starts with VBB high.
        # We could add slew logic in the FEE, or have two erase modes,
        # but for now the caller must drive VBB later. See ccdFuncs.wipe()
        # for details.
        self.presets['idle'] = m = ModePreset('idle')
        m.define(OG=6.0, RD=-12.0, OD=-5.0, BB=30.0,
                 P_off = 6.0, P_on = 6.0,
                 S_off = 6.0, S_on = 6.0,
                 DG_off= 6.0, DG_on= 6.0,
                 SW_off= 6.0, SW_on= 6.0,
                 RG_off= 6.0, RG_on= 6.0)

        self.presets['erase'] = m = ModePreset('erase')
        m.define(preload=self.presets['idle'], 
                 BB=0.2)
        if False:               # Not used yet, plus I'm not sure about the name.
            self.presets['fastRev'] = m = ModePreset('fastRev')
            m.define(preload=self.presets['read'], 
                     DG_on=-5.0, DG_off=-5.0,
                     BB=25.0)

        self.presets['read'] = m = ModePreset('read')
        m.define(OG=-4.5, RD=-12.0, OD=-21.0, BB=30.0,
                 P_off = 3.0, P_on = -5.0,
                 S_off = 3.0, S_on = -6.0,
                 DG_off= 5.0, DG_on=  5.0,
                 SW_off= 5.0, SW_on= -6.0,
                 RG_off= 2.0, RG_on= -7.5)

        self.presets['wipe'] = m = ModePreset('wipe')
        m.define(preload=self.presets['read'], 
                 OG=-4.5, RD=-12.0, OD=-21.0, BB=30.0)

        self.presets['expose'] = m = ModePreset('expose')
        m.define(preload=self.presets['read'], 
                 RD=-5.0, OD=-5.0, BB=45.0)


    def saveModesOnFee(self, modes=None):
        """ Save our voltage presets to the FEE. """
        
        if isinstance(modes, str):
            modes = modes,
        if modes is None:
            modes = list(self.presets.keys())
        for m in modes:
            p = self.presets[m]
            p.saveToFee(self)

    def setVoltage(self, mode, name, value, doSet=False):
        """ Change a single voltage in a single mode. """

        if mode is not None:
            m = self.presets[mode]
            kws = dict(name=value, force=True)
            print("kws: %s" % (kws))
            m.define(**kws)

            if doSet:
                m.saveToFee(self)
        else:
            for ch in 0,1:
                old = self.doGet('bias', name, ch)
                self.doSet('bias', name, value, ch)
                new = self.doGet('bias', name, ch)
                self.logger.info("changed ch%d %s from %s to %s" % (ch, name, old, new))

    def setVoltageCalibrations(self, 
                               v3V3M=None, v3V3=None,
                               v5VP=None, v5VN=None, v5VPpa=None, v5VNpa=None,
                               v12VP=None, v12VN=None, v24VN=None, v54VP=None):
        """ Set calibrations for some or all FEE voltages.

        Args:
         channel = 0 or 1
         v3V3M, etc : float or None
         
        """
        import inspect
        
        argspec = inspect.getargspec(self.setVoltageCalibrations)
        argnames = argspec.args[-len(argspec.defaults):]
        argvals = inspect.getargvalues(inspect.currentframe())
        for arg in argnames:
            try:
                argval = argvals.locals[arg]
            except Exception as e:
                raise RuntimeError("no value for %s in %s: %s" % (arg, argvals.locals, e))
                
            if argval is not None:
                vname = arg[1:]
                self.logger.info("setting voltage calibration %s = %s" % (vname, argval))
                self.doSet('voltage', vname, argval)
                
        
    def defineCommands(self):
        self.commands = {}

        self.commands['revision'] = FeeSet('revision', 'r', ['FEE'], 
                                           setLetter=None)
        self.commands['serial'] = FeeSet('serial', 's', ['FEE', 'ADC', 'PA0', 'CCD0', 'CCD1'])

        self.commands['temps'] = FeeSet('temps', 't', 
                                        ['all',
                                         'CCD0', 'CCD1', 'FEE', 'PA'],
                                        getLetter='r',
                                        setLetter=None)
        """
        #define setPowerEn   "se" // must include 0 or 1 for off or on 
        #define getPowerEn   "ge" 
        #define pe_3V3reg   "3V3" 
        #define pe_5Vreg    "5V" 
        #define pe_12Vreg   "12V" 
        #define pe_24Vreg   "24V" 
        #define pe_54Vreg   "54V" 
        #define pe_Preamp   "PA" 
        #define pe_LVDS     "LVDS" 
        #define pe_Vbb0     "Vbb0"// Bias amplifier enable 
        #define pe_Vbb1     "Vbb1"// Bias amplifier enable 
        #define pe_all      "all" 
        #define pe_on     "on" 
        #define pe_off    "off" 
        """
        self.commands['enable'] = FeeSet('enable', 'e', ['all', 
                                                         '3V3','5V','12V','24V','54V',
                                                         'PA','LVDS',
                                                         'Vbb0', 'Vbb1'], 
                                         getLetter=None,)
        """
        //Read/calibrate supply voltages
        #define calSupplyVoltage "cv"   //calibrate voltage channel
        #define getSupplyVoltage "gv"   //read voltage
        #define gv_3V3Micro "3V3M"
        #define gv_3V3Other "3V3"
        #define gv_5Vpos "5VP"
        #define gv_5Vneg "5VN"
        #define gv_5Vpos_pa "5VPpa"
        #define gv_5Vneg_pa "5VNpa"
        #define gv_12Vpos "12VP"
        #define gv_12Vneg "12VN"
        #define gv_24Vneg "24VN"
        #define gv_54Vpos "54VP"
        """
        self.commands['voltage'] = FeeSet('voltage', 'v', 
                                          ['all',
                                           '3V3M','3V3',
                                           '5VP','5VN','5VPpa', '5VNpa',
                                           '12VP', '12VN', '24VN', '54VP'],
                                          converter=clipFloat,
                                          setLetter='c', getLetter='r')
        """
        // Set/Get the CDS offset voltages 
        #define setCDS_OS "so"
        #define getCDS_OS "go"
        #define getCDS_OS "ro"
        # define co_0pos "0p" 
        # define co_0neg "0n" 
        # define co_1pos "1p" 
        # define co_1neg "1n" 
        # define co_2pos "2p" 
        # define co_2neg "2n" 
        # define co_3pos "3p" 
        # define co_3neg "3n"
        #  define co_0 "ch0" 
        #  define co_1 "ch1"
        """
        self.commands['offset'] = FeeChannelSet('offset', 'o', 
                                                ['all',
                                                 '0p','0n','1p','1n',
                                                 '2p','2n','3p','3n'],
                                                converter=clipFloat,
                                                getLetter='r')
        """
        // Set/get the clock Bias Voltages
        #define setClockBias "sb" // COMMAND
        #define getClockBias "gb" 
        #define rdClockBias  "rb" // reads the actual voltage 
        #define cb_Ppos      "P_on" // PARAMETER 1
        #define cb_Pneg      "P_off"
        #define cb_DGpos     "DG_on"
        #define cb_DGneg     "DG_off"
        #define cb_Spos      "S_on"
        #define cb_Sneg      "S_off"
        #define cb_SWpos     "SW_on" // Summing Well
        #define cb_SWneg     "SW_off"
        #define cb_RGpos     "RG_on" // Reset Gate
        #define cb_RGneg     "RG_off"
        #define cb_OG        "OG"
        #define cb_RD        "RD"
        #define cb_OD        "OD"
        #define cb_BB        "BB"
        #   define cb_0         "ch0" // PARAMETER 2
        #   define cb_1         "ch1"
        """
        self.commands['bias'] = FeeChannelSet('bias', 'b', 
                                              ['all',
                                               'P_on','P_off',
                                               'DG_on', 'DG_off',
                                               'S_on', 'S_off',
                                               'SW_on', 'SW_off',
                                               'RG_on', 'RG_off',
                                               'OG', 'RD', 'OD', 'BB'],
                                              converter=clipFloat,
                                              getLetter='r')

        """
        //load/save bias presets

        #define loadDACPresets "lp"
        #define saveDACPresets "sp"
        #define pb_erase       "erase"
        #define pb_read        "read"
        #define pb_expose      "expose"
        #define pb_wipe        "wipe"
        #define pb_idle        "idle"
        #define pb_offset      "offset"
        #define pb_fastRev     "fastRev"
        """
        self.commands['preset'] = FeeSet('preset', 'p', 
                                         ["erase", "read", "expose", "wipe", "idle"],
                                         getLetter=None,
                                         setLetter='l')

    def setFast(self):
        return self.sendCommandStr('sf,fast')
    def setSlow(self):
        return self.sendCommandStr('sf,slow')
        
    def allKeys(self, setName):
        try:
            cmdSet = self.commands[setName]
        except AttributeError as e:
            raise e

        return cmdSet.subs

    def doSet(self, setName, subName, value, channel=None):
        try:
            cmdSet = self.commands[setName]
        except AttributeError as e:
            raise e

        if channel is not None:
            cmdStr = cmdSet.setVal(subName, channel, value)
        else:
            cmdStr = cmdSet.setVal(subName, value)

        return self.sendCommandStr(cmdStr)

    def doGet(self, setName, subName=None, channel=None):
        """  
        """
        
        try:
            cmdSet = self.commands[setName]
        except AttributeError as e:
            raise e

        cmdStr = cmdSet.getVal(subName, channel=channel)
        ret = self.sendCommandStr(cmdStr)

        if subName == 'all':
            retVal = [cmdSet.converter(v) for v in ret.split(',')]
        else:
            retVal = cmdSet.converter(ret)

        return retVal
    
    def raw(self, cmdStr):
        return self.sendCommandStr(cmdStr)

    def sendImage(self, path, verbose=True, doWait=False, sendReboot=False, straightToCode=False,
                  charAtATime=False, cmd=None):
        """ Download an image file to the interlock board. 

        Args
        ----
        path : `str` or `pathlib.Path`
          The .hex file to burn
        doWait : bool
          Whether to wait for a "Bootloader" prompt.
        sendReboot:
          Whether to start by sending a "reboot" command.
        straightToCode:
          Whether to skip all preparation and immediately start sending the .hex lines.
        charAtATime: bool
          Whether to send the image one character at a time (checking the echo) instead
          of one line at a time (also checking the echo.
        cmd : `actorcore.Command`
          The driving command, to which we can send reassuring messages of progress,

        2020-02-17: 
          - For blank FEEs, use straightToCode, which sets doWait=False and sendReboot=False.
          - Otherwise power fee off, call with doWait=True and sendReboot=False, then power fee up.
            The problem is that the FEE firmware hangs if 'reboot' is ever sent a second time after a power up.
          - If you have power-cycled, then calling with sendReboot=True and doWait=False is also OK.
        """

        eol = chr(0x0a)
        ack = chr(0x06) # ; ack='+'
        nak = chr(0x15) # ; name='-'
        lineNumber = 1
        maxRetries = 5

        if straightToCode:
            sendReboot = False
            doWait = False
            
        if sendReboot:
            try:
                ret = self.sendCommandStr('reboot')
            except:
                pass
        time.sleep(0.5)
        
        if doWait:
            self.device.timeout = 5
            ret = self.device.readline()
            retline = ret.decode('latin-1').strip()
            self.logger.info('at wait, recv: %r', retline)
            isBootLoader = 'Bootloader' in retline
            if not isBootLoader:
                raise RuntimeError("not at bootloader prompt (%s)" % (retline))
            isBlank = retline[-1] == 'B'
            self.logger.info('at bootloader: %s (blank=%s), from %r' % (isBootLoader, isBlank, ret))
            if not isBlank:
                self.logger.info('at bootloader, sending *')
                self.device.write(b'*')
        else:
            if not straightToCode:
                self.logger.info('at bootloader, sending *')
                self.device.write(b'*')

        if not straightToCode:
            ret = self.device.readline()
            ret = ret.decode('latin-1').strip()
            self.logger.debug('after * got :%r:', ret)
            if not ret.startswith('*Waiting for Data...'):
                self.logger.info('at bootloader *, got %r' % (ret))
                ret = self.device.readline().decode('latin-1')
                self.logger.debug('after * retry got %r', ret)
                if not ret.startswith('*Waiting for Data...'):
                    raise RuntimeError('could not get *Waiting for Data')

        logLevel = self.logger.level
        # self.logger.setLevel(logging.INFO)
        self.device.timeout = 1.0 # self.devConfig['timeout'] * 100
        strTrans = str.maketrans('', '', '\x11\x13')
        self.logger.info(f'sending image file {path}')
        with open(path, 'rU') as hexfile:
            lines = hexfile.readlines()
            t0 = time.time()
            msg = 'sending image file %s, %d lines' % (path, len(lines))
            self.logger.info(msg)
            if cmd is not None:
                cmd.inform(f'text="{msg}"')
            for l_i, rawl in enumerate(lines):
                hexl = rawl.strip()
                if hexl[0] == ';':
                    continue
                retries = 0
                while True:
                    if verbose and retries > 0:
                        self.logger.warn('resending line %d; try %d' % (lineNumber, 
                                                                        retries))
                    fullLine = hexl+eol
                    if verbose and lineNumber%100 == 1:
                        msg = 'sending line %d / %d' % (lineNumber, len(lines))
                        self.logger.info(msg)
                        if cmd is not None:
                            cmd.inform(f'text="{msg}"')
                            
                    self.logger.debug("sending line %d: %r", lineNumber, fullLine)
                    if charAtATime:
                        retline = self.sendOneLinePerChar(fullLine)
                    else:
                        self.device.write(fullLine.encode('latin-1'))
                        retline = self.device.read(size=len(hexl)+len(eol)+1).decode('latin-1')
                    self.logger.debug('recv %r' % (retline))
                    retline = retline.translate(strTrans)

                    if fullLine != retline[:len(fullLine)]:
                        self.logger.warn("command echo mismatch. sent %r rcvd %r" % (fullLine, retline))
                    ret = retline[-1]
                    lineNumber += 1
                    if ret == ack or hexl == ':00000001FF':
                        break
                    if ret != nak:
                        raise RuntimeError("unexpected response (%r in %r) after sending line %d" %
                                           (ret, retline, lineNumber-1))
                    retries += 1
                    if retries >= maxRetries:
                        raise RuntimeError("too many retries (%d) on line %d" %
                                           (retries, lineNumber-1))

            t1 = time.time()
            
        msg = 'sent image file %s in %0.2f seconds' % (path, t1-t0)
        self.logger.info(msg)
        if cmd is not None:
            cmd.inform(f'text="{msg}"')
            
        time.sleep(1)
        line = self.device.readline().decode('latin-1')
        self.logger.info('recv: %s', line)
        if 'FEE' not in line:
            msg = 'did not get expected FEE line after loading image (%s)' % line
            self.logger.warn(msg)
            if cmd is not None:
                cmd.warn(f'text="{msg}"')

        self.logger.setLevel(logLevel)

    def sendOneLinePerChar(self, strline):
        line = strline.encode('latin-1')
        ret = bytearray(len(line) + 1)
        for c_i in range(len(line)):
            c = line[c_i:c_i+1]
            self.device.write(c)
            # time.sleep(0.001)
            retc = self.device.read(1)
            if c != retc:
                raise RuntimeError('boom: mismatch at %d: sent %r but recv %r' % (c_i,c,retc))
            ret[c_i] = retc[0]
        ackNak = self.device.read(1)
        ret[-1] = ackNak[0]

        return ret.decode('latin-1')
    
    def gobbleInput(self):
        """ Read and drop any buffered input."""
        
        while True:
            ret = self.readResponse()
            if ret == '':
                break
            print("gobbled: ", ret)
                                                        
    def sendCommandStr(self, cmdStr, noTilde=False, EOL=None):
        if EOL is None:
            EOL = self.EOL
        if noTilde:
            fullCmd = "%s%s" % (cmdStr, EOL)
        else:
            fullCmd = "~%s%s" % (cmdStr, EOL)

        writeCmd = fullCmd.encode('latin-1')
        with self.deviceLock:
            self.logger.debug("sending command :%r:" % (fullCmd))
            try:
                self.device.write(writeCmd)
            except serial.writeTimeoutError as e:
                raise
            except serial.SerialException as e:
                raise
            except Exception as e:
                raise

            ret = self.readResponse()
            if ret != fullCmd.strip():
                raise RuntimeError("command echo mismatch. sent :%r: rcvd :%r:" % (fullCmd, ret))
 
            ret = self.readResponse()

        return ret

    def readResponse(self, EOL=None):
        """ Read a single response line, up to the next self.EOL.

        Returns
        -------
        response
           A string, with trailing EOL removed.

        Notes
        -----
        Ignores CRs
        """

        if EOL is None:
            EOL = self.EOL

        response = ""

        while True:
            try:
                c = self.device.read(size=1)
                # self.logger.debug("received char :%r:" % (c))
            except serial.SerialException as e:
                raise
            except serial.portNotOpenError as e:
                raise
            except Exception as e:
                raise

            c = str(c, 'latin-1')
            if c == '':
                self.logger.warn('pyserial device read(1) timed out')

            if self.ignoredEOL is not None and c == self.ignoredEOL:
                self.logger.debug("ignoring %r" % (c))
                continue
            if c in (EOL, ''):
                break
            response += c
                
        self.logger.debug("received :%s:" % (response))
        return response

    def setRaw(self, cmdStr):
        """ Send a raw commmand string. Well we add the ~ and EOL. """
        
        return self.sendCommandStr(cmdStr)

    def getRaw(self, cmdStr):
        """ Send a raw commmand string. Well we add the ~ and EOL. """
        
        return self.sendCommandStr(cmdStr)

    def _ampName(self, ampNum, leg='n'):
        ampNum = int(ampNum)
        channel = ampNum//4
        return "%d%s,ch%d" % (ampNum%4, leg, channel)

    def ampParts(self, ampNum, leg='n'):
        ampNum = int(ampNum)
        channel = ampNum//4
        return "%d%s" % (ampNum%4, leg), channel

    def setMode(self, newMode):
        ret = self.sendCommandStr('lp,%s' % (newMode))
        return ret

    def getMode(self):
        ret = self.sendCommandStr('gp')
        return ret
    
    def setOffsets(self, amps, levels, leg='n', pause=0.0, doSave=True):
        if np.isscalar(levels):
            levels = np.zeros(len(amps),dtype='f4') + levels
        if len(amps) != len(levels):
            raise RuntimeError("require same number of amps (%r) and levels (%r)" % (amps, levels))
        for i, a in enumerate(amps):
            ampName, channel = self.ampParts(a, leg=leg)
            ret = self.doSet('offset', ampName, round(levels[i],2), channel=channel)
            if ret != 'SUCCESS':
                self.logger.info("raw received :%r:" % (ret))
            else:
                self.logger.debug("raw received :%r:" % (ret))
            if not ret.endswith('SUCCESS'):
                raise RuntimeError('setLevels command returned: %s' % (ret))
            if pause > 0:
                time.sleep(pause)

            if doSave:
                self.sendCommandStr('sp,offset')

    def zeroOffsets(self, amps=None, leg=True):
        if amps is None:
            amps = list(range(8))
        levels = [0.0] * len(amps)

        if leg is True:
            legs = ('n','p')
        else:
            legs = leg,
    
        if 'p' in legs:
            self.setOffsets(amps, levels, leg='p')
        if 'n' in legs:
            self.setOffsets(amps, levels, leg='n')

    def setPreset(self, name):
        vset = self.presets[name]
        for ch in 0, 1:
            for k, v in vset.items():
                self.doSet('bias', k, v, ch)

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if isinstance(argv, str):
        argv = argv.split()

    parser = argparse.ArgumentParser(description="Send one or more commands to the FEE controller.",
                                     epilog="At least one command must be specified.\n")

    parser.add_argument('-p', '--port', 
                        type=str, default='/dev/ttyS1',
                        help='the port to use. Currently must be a tty name. Default=%(default)s')
    parser.add_argument('-r', '--raw', action='append',
                        help='a raw command to send. The "~" is automatically prepended.')
    parser.add_argument('--debug', action='store_true',
                        help='show all traffic to the port.')

    args = parser.parse_args(argv)

    logLevel = logging.DEBUG if args.debug else logging.WARN

    fee = FeeControl(logLevel=logLevel)
    if args.raw:
        for rawCmd in args.raw:
            print(fee.getRaw(rawCmd))
    else:
        fee.getAllStatus()
        fee.printStatus()
    
if __name__ == "__main__":
    main()

