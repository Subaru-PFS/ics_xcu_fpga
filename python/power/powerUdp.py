from collections import OrderedDict
import socket
import time

dataStore = OrderedDict()

UDP_IP = "10.1.1.4"
UDP_PORT = 1025

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP_IPsock.bind((UDP_IP, UDP_PORT))
sock.bind(('', 1025))

def printPower(port):
    if port != '4':
        return

    A = dataStore.get('I%s' % (port), None)
    V = dataStore.get('V%s' % (port), None)

    if A is None or V is None:
        W = None
    else:
        W = float(A) * float(V)

    print("Port %s: %s %s %s" % (port, V, A, W))

while True:
    data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
    now = time.time()

    try:
        data = data.strip()
        key, val = data.split(':')
    except Exception as e:
        print("failed to parse message from %s: %s" % (addr, data))
        continue

    lastVal = dataStore.get(key, None)
    dataStore[key] = val

    if val != lastVal or lastVal is None:
        if key[0] in {'V','I'}:
            printPower(key[1:])
#            print("%0.2f %05s %s    %s" % (now, key, val, lastVal))



