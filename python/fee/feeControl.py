#!/usr/bin/env python

import argparse
import logging
import serial
import sys
import time

class FeeSet(object):
    def __init__(self, name, letter, subs=(), setLetter='s', getLetter='g'):
        self.name = name
        self.letter = letter
        self.subs = subs
        self.setLetter = setLetter
        self.getLetter = getLetter

    def _getCmdString(self, cmdLetter, *parts):
        allParts = ["%s%s" % (cmdLetter, self.letter)]
        allParts.extend(parts)
        #print "%r : %r : %r : %r" % (cmdLetter, self.letter, parts, allParts)
        return ','.join(allParts)

    def setVal(self, subName, value):
        """ Return the command string for a 'set' function. """

        if not self.setLetter:
            raise RuntimeError("Cannot set %s(%s)!" % (self.name, subName))
        if subName not in self.subs:
            raise RuntimeError("Cannot set unknown %s (%s). Valid=%s" % (self.name, subName,
                                                                         self.subs))
        if value:
            return self._getCmdString(self.setLetter, subName, value)
        else:
            return self._getCmdString(self.setLetter, subName)

    def getVal(self, subName):
        """ Return the command string for a 'get' function. """

        if not self.getLetter:
            raise RuntimeError("Cannot get %s(%s)!" % (self.name, subName))

        if subName:
            if subName not in self.subs:
                raise RuntimeError("Cannot get unknown %s (%s). Valid=%s" % (self.name, subName,
                                                                             self.subs))
            return self._getCmdString(self.getLetter, subName)
        else:
            return self._getCmdString(self.getLetter)

    def ampName(self, ampNum, leg='n'):
        """ Return the FEE controller's name for an amp (just for the so command). 

        Parameters
        ----------
        ampNum - int
           The 0..namps-1 index of an amp.
        leg -- ('n','p')
           Negative or Positive leg. 
        """

        ampNum = int(ampNum)
        return "%d%s,ch%d" % (ampNum%4, leg, ampNum/4)

class FeeChannelSet(FeeSet):
    def setVal(self, subName, channel, value):
        """ Return the command string for a 'set' function. """

        if not self.setLetter:
            raise RuntimeError("Cannot set %s(%s)!" % (self.name, subName))
        if subName not in self.subs:
            raise RuntimeError("Cannot set unknown %s (%s). Valid=%s" % (self.name, subName,
                                                                         self.subs))
        if channel not in (0,1):
            raise RuntimeError("Channel must be 0 or 1 %s(%s)!" % (self.name, subName))
            
        return self._getCmdString(self.setLetter, subName, 'ch%d' % channel, value)

    def getVal(self, subName, channel):
        """ Return the command string for a 'get' function. """

        if not self.getLetter:
            raise RuntimeError("Cannot get %s(%s)!" % (self.name, subName))

        if channel not in (0,1):
            raise RuntimeError("Channel must be 0 or 1 %s(%s)!" % (self.name, subName))
            
        if subName not in self.subs:
            raise RuntimeError("Cannot get unknown %s (%s). Valid=%s" % (self.name, subName,
                                                                         self.subs))

        return self._getCmdString(self.getLetter, subName, 'ch%d' % channel)


class FeeControl(object):
    def __init__(self, port=None, logLevel=logging.DEBUG):
        if port is None:
            port = '/dev/ttyS0'
        self.logger = logging.getLogger()
        self.logger.setLevel(logLevel)
        self.device = None
        self.status = {}
        self.devConfig = dict(port=port, baudrate=9600)
        self.devConfig['writeTimeout'] = 100 * 1.0/(self.devConfig['baudrate']/8)
        self.EOL = '\r'
        self.ignoredEOL = '\n'
        self.defineCommands()

        self.setDevice(port)

    def setDevice(self, devName):
        """ """
        self.devName = devName
        self.connectToDevice()

    def connectToDevice(self, noCheck=False):
        """ Establish a new connection to the FEE. Any old conection is closed. By default the revision is fetched. """

        if self.device:
            self.device.close()
            self.device = None

        if self.devName:
            self.device = serial.Serial(**self.devConfig)
    
        if not noCheck:
            ret = self.fetchAll()
            print "connected to FEE, revision %s" % (ret)
    
    def powerUp(self):
        """ Bring the FEE up to a sane and useable configuration. Specifically: power supplies on and set for readout. """

        print self.sendCommandStr('se,all,on')
        print self.sendCommandStr('se,Clks,on')
        print self.sendCommandStr('lp,read')

    def powerDown(self):
        """ Bring the FEE down to a sane and stable idle. """

        print self.sendCommandStr('se,all,off')
        print self.sendCommandStr('se,Clks,off')


    def fetchAll(self):
        return self.sendCommandStr('gr')

    def _defineFullCommand(self, cmdSet):
        """ For a passed commandset, create methods to set&get values."""

        self.commands[cmdSet.name] = cmdSet

    def defineCommands(self):
        self.commands = {}

        # Read from file....
        self.commands['revision'] = FeeSet('revision', 'r', setLetter=None)

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
                                                         'Vbb0', 'Vbb1'])
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
                                          ['3V3M','3V3',
                                           '5VP','5VN','5VPpa', '5VNpa',
                                           '12VP', '12VN', '24VN', '54VP',
                                           'all'], 
                                          setLetter='c')
        """
        // Set/Get the CDS offset voltages 
        #define setCDS_OS "so"
        #define getCDS_OS "go"
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
                                                ['0p','1p','2p','3p',
                                                 '0n','1n','2n','3n'])
        """
        //load/save bias presets

        #define loadDACPresets "lp"
        #define saveDACPresets "sp"
        #define pb_erase "erase"
        #define pb_read "read"
        #define pb_expose "expose"
        #define pb_wipe "wipe"
        #define po_offset "offset"
        """
        self.commands['preset'] = FeeSet('preset', 'p', 
                                         ["erase", "read", "expose", "wipe", "offset"],
                                         getLetter='l')

    def doSet(self, setName, subName, value):
        try:
            cmdSet = self.commands[system]
        except AttributeError as e:
            raise

        return cmdSet.subs

    def doSet(self, setName, subName, value, channel=None):
        try:
            cmdSet = self.commands[setName]
        except AttributeError as e:
            raise e

        if channel is not None:
            cmdStr = cmdSet.setVal(subName, value, channel)
        else:
            cmdStr = cmdSet.setVal(subName, value)

        return self.sendCommandStr(cmdStr)

    def doGet(self, setName, subName=None, channel=None):
        try:
            cmdSet = self.commands[setName]
        except AttributeError as e:
            raise e

        if channel is not None:
            cmdStr = cmdSet.getVal(subName, channel)
        else:
            cmdStr = cmdSet.getVal(subName)

        return self.sendCommandStr(cmdStr)

    def raw(self, cmdStr):
        return self.sendCommandStr(cmdStr)

    def sendCommandStr(self, cmdStr):
        fullCmd = "~%s%s" % (cmdStr, self.EOL)

        logging.debug("sending command :%r:" % (fullCmd))
        try:
            self.device.write(fullCmd)
        except serial.writeTimeoutError as e:
            raise e
        except serial.SerialException as e:
            raise e
        except Exception as e:
            raise e

  
        ret = self.readResponse()
        if ret != fullCmd.strip():
            raise RuntimeError("command echo mismatch. sent :%r: rcvd :%r:" % (cmdStr, ret))
 
        return self.readResponse()

    def readResponse(self):
        """ Read a single response line, up to the next self.EOL.

        Returns
        -------
        response
           A string, with trailing EOL removed.

        Notes
        -----
        Ignores CRs
        """

        response = ""

        while True:
            try:
                c = self.device.read(size=1)
                # logging.debug("received char :%r:" % (c))
            except serial.SerialException as e:
                raise
            except serial.portNotOpenError as e:
                raise
            except Exception as e:
                raise

            if self.ignoredEOL is not None and c == self.ignoredEOL:
                logging.debug("ignoring %r" % (c))
                continue
            if c == self.EOL:
                # if response.startswith('X')
                break
            response += c
                
        logging.debug("received :%s:" % (response))
        return response

    def setRaw(self, cmdStr):
        """ Send a raw commmand string. Well we add the ~ and EOL. """
        
        return self.sendCommandStr(cmdStr)

    def getRaw(self, cmdStr):
        """ Send a raw commmand string. Well we add the ~ and EOL. """
        
        return self.sendCommandStr(cmdStr)

    def getAll(self):
        pass

    def ampName(self, ampNum, leg='n'):
        ampNum = int(ampNum)
        channel = ampNum/4
        return "%d%s,ch%d" % (ampNum%4, leg, channel)

    def setLevels(self, amps, levels, leg='n', pause=0.0):
        if len(amps) != len(levels):
            raise RuntimeError("require same number of amps (%r) and levels (%r)" % (amps, levels))
        for i, a in enumerate(amps):
            cmd = 'so,%s,%4d' % (self.ampName(a, leg=leg), 
                                 levels[i])
            ret = self.raw(cmd)
            if ret != 'SUCCESS':
                logging.info("raw received :%r:" % (ret))
            else:
                logging.debug("raw received :%r:" % (ret))
            if not ret.endswith('SUCCESS'):
                raise RuntimeError('setLevels command %s returned: %s' % (cmd, ret))
            if pause > 0:
                time.sleep(pause)
            # print "set level with: %s" % (cmd)

    def zeroLevels(self, amps=None, leg=True):
        if amps is None:
            amps = range(8)
        levels = [0.0] * len(amps)

        if leg is True:
            legs = ('n','p')
        else:
            legs = leg,
    
        if 'p' in legs:
            self.setLevels(amps, levels, leg='p')
        if 'n' in legs:
            self.setLevels(amps, levels, leg='n')

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if isinstance(argv, basestring):
        argv = argv.split()

    parser = argparse.ArgumentParser(description="Send one or more commands to the FEE controller.",
                                     epilog="At least one command must be specified.\n")

    parser.add_argument('-p', '--port', 
                        type=str, default='/dev/ttyS0',
                        help='the port to use. Currently must be a tty name. Default=%(default)s')
    parser.add_argument('-r', '--raw', action='append',
                        help='a raw command to send. The "~" is automatically prepended.')
    parser.add_argument('--debug', action='store_true',
                        help='show all traffic to the port.')

    args = parser.parse_args(argv)

    logLevel = logging.DEBUG if args.debug else logging.WARN

    if not (args.raw):
        parser.print_help()
        parser.exit(1)

    fee = FeeControl(logLevel=logLevel)
    for rawCmd in args.raw:
        print fee.getRaw(rawCmd)
    
if __name__ == "__main__":
    main()

