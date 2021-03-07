from machine import Pin

relay_pin = Pin(13, Pin.OUT)

disp = [14, 27, 26,25,33,32,18,17]
disp = [Pin(i, Pin.OUT) for i in disp]
digits = [22,21,19,16]
digits = [Pin(i, Pin.OUT for i in digits)]

sensor = Pin(15)

button = Pin(23, Pin.IN, Pin.PULL_UP)
rot_left = Pin(35, Pin.IN, Pin.PULL_UP)
rot_right = Pin(34, Pin.IN, Pin.PULL_UP)
