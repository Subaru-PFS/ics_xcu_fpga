#!/usr/bin/env python

import argparse
import logging
import serial
import sys

class FeeSet(object):
    def __init__(self, name, letter, subs=(), setLetter='s', getLetter='g'):
        self.name = name
        self.letter = letter
        self.subs = subs
        self.setLetter = setLetter
        self.getLetter = getLetter

    def _genCmdString(self, cmdLetter, *parts):
        allParts = [cmdLetter, self.letter].extend(parts)
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
            
        return self._getCmdString(self.setLetter, subName, channel, value)

    def getVal(self, subName, channel):
        """ Return the command string for a 'get' function. """

        if not self.getLetter:
            raise RuntimeError("Cannot get %s(%s)!" % (self.name, subName))

        if channel not in (0,1):
            raise RuntimeError("Channel must be 0 or 1 %s(%s)!" % (self.name, subName))
            
        if subName not in self.subs:
            raise RuntimeError("Cannot get unknown %s (%s). Valid=%s" % (self.name, subName,
                                                                         self.subs))

        return self._getCmdString(self.getLetter, subName, channel)


class FeeControl(object):
    def __init__(self, ttyName='/dev/ttyS0', logLevel=logging.WARNING):
        self.logger = logging.getLogger()
        self.logger.setLevel(logLevel)
        self.device = None
        self.status = {}
        self.devConfig = dict(port=ttyName, baudrate=9600)
        self.devConfig['writeTimeout'] = 100 * 1.0/(self.devConfig['baudrate']/8)
        self.EOL = '\n'
                              
        self.defineCommands()

        self.setDevice(ttyName)

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
    
    def fetchAll(self):
        return self.sendGetCommand('Revision')

    def defineCommands(self):
        self.commands = {}

        # Read from file....
        self.commands['Revision'] = FeeSet('Revision', 'r', setLetter=None)
        self.commands['Enable'] = FeeSet('Enable', 'e', ['all'])

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
        self.commands['Voltages'] = FeeSet('Voltages', 'v', 
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
        self.commands['Offsets'] = FeeChannelSet('Offsets', 'o', 
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
        self.commands['Presets'] = FeeSet('Presets', 'p', 
                                          ["erase", "read", "expose", "wipe", "offset"],
                                          getLetter='l')

    def sendSetCommand(self, setName, subName, value):
        cmdSet = self.commands[setName]
        cmdStr = cmdSet.setVal(subName, value)

        return self.sendCommandStr(cmdStr)

    def sendGetCommand(self, setName, subName=None):
        cmdSet = self.commands[setName]
        cmdStr = cmdSet.getVal(subName)

        return self.sendCommandStr(cmdStr)

    def sendCommandStr(self, cmdStr):
        fullCmd = "~%s\n" % (cmdStr)

        logging.debug("sending command :%s:" % (fullCmd[:-1]))
        try:
            self.device.write(fullCmd)
        except serial.writeTimeoutError as e:
            raise
        except serial.SerialException as e:
            raise
        except Exception as e:
            raise

        try:
            ret = self.device.read(len(fullCmd))
        except serial.SerialException as e:
            raise
        except serial.portNotOpenError as e:
            raise
        except Exception as e:
            raise
    
        if ret != fullCmd:
            raise RuntimeError("command echo mismatch. sent :%r: rcvd :%r:" % (fullCmd, ret))
 
        return self.readResponse()

    def readResponse(self):
        response = ""

        while True:
            try:
                c = self.device.read(size=1)
            except serial.SerialException as e:
                raise
            except serial.portNotOpenError as e:
                raise
            except Exception as e:
                raise

            response += c
            if c == self.EOL:
                logging.debug("received :%s:" % (response))
                return response

    def setRaw(self, cmdStr):
        """ Send a raw commmand string. Well we add the ~ and EOL. """
        
        print self.sendCommandStr(cmdStr)

    def getRaw(self, cmdStr):
        """ Send a raw commmand string. Well we add the ~ and EOL. """
        
        print self.sendCommandStr(cmdStr)

    def getAll(self):
        pass


def main(argv):
    if isinstance(argv, basestring):
        argv = argv.split()

    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', type=bool)
    parser.add_argument('-r', '--raw', type=str)

    args = parser.parse_args(argv)

    logLevel = logging.DEBUG if args.debug else logging.WARN

    fee = FeeControl(logLevel=logLevel)
    if args.raw:
        print fee.getRaw(args.raw)
    

if __name__ == "__main__":
    main(sys.argv)

