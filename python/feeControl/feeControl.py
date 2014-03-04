import argparse
import logging
import serial

class FeeSet(object):
    def __init__(self, name, letter, subs=(), setCmd='s', getCmd='g'):
        self.name = name
        self.letter = letter
        self.subs = subs
        self.statusCache = {}
        self.setCmd = setCmd
        self.getCmd = getCmd

    def setVal(self, subName, value=None):
        if not self.setCmd:
            raise RuntimeError("Cannot set %s(%s)!" % (self.name, subName))
        if subName not in self.subs:
            raise RuntimeError("Cannot set unknown %s (%s). Valid=%s" % (self.name, subName,
                                                                         self.subs))
        if value:
            return "s%s,%s,%s" % (self.letter, subName, value)
        else:
            return "s%s,%s" % (self.letter, subName)

    def getVal(self, subName=None):
        if not self.getCmd:
            raise RuntimeError("Cannot get %s(%s)!" % (self.name, subName))

        if subName:
            if subName not in self.subs:
                raise RuntimeError("Cannot get unknown %s (%s). Valid=%s" % (self.name, subName,
                                                                             self.subs))
            return "g%s,%s" % (self.letter, subName)
        else:
            return "g%s" % (self.letter)

    def fetchStatus(self):
        if not self.getCmd:
            return dict()
        for sub in subs:
            
    def status(self, useCache=False):
        if not useCache:
            self.statusCache = {}
        if not self.statusCache:
            self.statusCache = self.fetchStatus()

        return self.statusCache
        
class FeeControl(object):
    def __init__(self, ttyName='/dev/ttyS0', logLevel=logging.DEBUG):
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
        self.commands['Revision'] = FeeSet('Revision', 'r', setCmd=None)
        self.commands['PowerEnable'] = FeeSet('PowerEnable', 'e', ['all'])

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
                                            '12VP', '12VN', '24VN', '54VP'], 
                                           setCmd='c')

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
                                          getCmd='l')

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

    
def test1():
    fee = FeeControl()
