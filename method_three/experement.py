import socket
try:
    ip = socket.gethostbyname('brd.superproxy.io')
    print(f"DNS resolution successful: {ip}")
except socket.gaierror as e:
    print(f"DNS resolution failed: {e}")