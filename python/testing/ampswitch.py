#!/usr/bin/env python

from builtins import range
from builtins import object
import argparse
import logging
import time

from pyModbusTCP.client import ModbusClient

class AmpSwitch(object):
    def __init__(self, host, port=502, switches=(), debug=False):
        """ """

        self.host = host
        self.port = port
        self.debug = debug
        self.switches = switches

        self.dev = None

        self.connect()

    def __str__(self):
        return "AmpSwitch(host=%s, port=%s, dev=%s>" % (self.host,
                                                        self.port,
                                                        self.dev)
    def setDebug(self, state):
        self.debug = state
        self.connect()
        
    def close(self):
        if self.dev is not None:
            self.dev.close()
            self.dev = None

    def connect(self):
        """ (re-) establish a connection to the device. """

        if self.dev is None:
            self.dev = ModbusClient()
            self.dev.debug(self.debug)
            self.dev.host(self.host)
            self.dev.port(self.port)

        if self.dev.is_open():
            return True

        ret = self.dev.open()
        if not ret:
            raise RuntimeError("failed to connect to %s:%s" % (self.host,
                                                               self.port))

        return True

    def readCoils(self):
        """ Return the state of all our switches. """

        self.connect()

        regs = self.dev.read_coils(0, 16)
        return regs

    def setCoils(self, on=(), off=()):
        """Turn on and off a given set of switches. 

        Argunents
        ---------

        on, off : list-like, or a single integer.

        Notes:
        ------

        The off set is executed first. . There is a command to change
        all switchees at once, but I have not made it work yet.

        """
        self.connect()

        if isinstance(on, int):
            on = on,
        if isinstance(off, int):
            off = off,

        regs0 = self.readCoils()
        regs1 = regs0[:]
        for c in off:
            ret = self.dev.write_single_coil(c, False)
            regs1[c] = False
        for c in on:
            ret = self.dev.write_single_coil(c, True)
            regs1[c] = True
        
        # ret = self.dev.write_multiple_registers(0, regs1)
        ret = self.readCoils()
        return ret

    def chooseCoil(self, n):
        return self.setCoils(on=n, off=list(range(16)))
