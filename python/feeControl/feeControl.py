import serial

class FeeControl(object):
    def __init__(self, ttyName='/dev/ttyS0'):
        self.defineDevice(ttyName)
        self.connectToDevice()

    def defineDevice(self, devName):
        """ """
        pass

    def connectToDevice(self):
        pass
    
