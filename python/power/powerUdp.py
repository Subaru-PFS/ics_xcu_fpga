from collections import OrderedDict
import socket
import time

dataStore = OrderedDict()

UDP_IP = "10.1.1.4"
UDP_PORT = 1025

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP_IPsock.bind((UDP_IP, UDP_PORT))
sock.bind(('', 1025))

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
    if val != lastVal:
        print("%0.2f %05s %s    %s" % (now, key, val, lastVal))

    dataStore[key] = val


