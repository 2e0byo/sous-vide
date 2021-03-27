import json

import ds18x20
import micropython
import onewire
import uasyncio as asyncio
from machine import PWM, Pin

import PID
import tm1637
from primitives.pushbutton import Pushbutton

config = {"kp": 1, "ki": 0.5, "kd": 0.5}
try:
    with open("config.json") as f:
        config.update(json.load(f))
except OSError:
    pass


class settablePin(Pin):
    @property
    def val(self):
        return self.value() ^ 1

    @val.setter
    def val(self, value):
        self.value(value ^ 1)


relay_pin = Pin(13, Pin.OUT)
relay = PWM(relay_pin, freq=50, duty=0)

seg = (27, 26, 33, 25, 14, 17, 16, 32)
# a, b, c, d, e, f, g,  dp
# seg = tuple((settablePin(i, settablePin.OPEN_DRAIN) for i in seg))

digits = (18, 22, 21, 19)


sensor = Pin(15)
ow = onewire.OneWire(sensor)
ds = ds18x20.DS18X20(ow)


def detect_sensor():
    """
    Detect sensor if attached.

    Returns rom if present else None.
    """
    roms = ds.scan()
    if len(roms) != 1:
        return None
    else:
        return roms[0]


async def read_sensor(rom):
    """Read sensor."""
    ds.convert_temp()
    await asyncio.sleep(0.75)
    return ds.read_temp(rom)


button = Pin(23, Pin.IN, Pin.PULL_UP)
push_flag = None
double_flag = None


def set_push_flag():
    global push_flag
    push_flag = True


def set_double_flag():
    global double_flag
    double_flag = True


button = Pushbutton(button, suppress=True)

rot_left = settablePin(35, settablePin.IN, settablePin.PULL_UP)
rot_right = settablePin(34, settablePin.IN, settablePin.PULL_UP)


class EncoderTimed(object):
    def __init__(self, pin_x, pin_y, reverse, scale):
        self.reverse = reverse
        self.scale = scale
        self.tprev = 0
        self.tlast = 0
        self.forward = True
        self.pin_x = pin_x
        self.pin_y = pin_y
        self._pos = 0
        self.x_interrupt = pin_x.irq(
            handler=self.x_callback, trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING
        )
        self.y_interrupt = pin_y.irq(
            handler=self.y_callback, trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING
        )

    @micropython.native
    def x_callback(self, line):
        self.forward = self.pin_x.value() ^ self.pin_y.value() ^ self.reverse
        self._pos += 1 if self.forward else -1

    @micropython.native
    def y_callback(self, line):
        self.forward = self.pin_x.value() ^ self.pin_y.value() ^ self.reverse ^ 1
        self._pos += 1 if self.forward else -1

    @property
    def position(self):
        return self._pos * self.scale

    @position.setter
    def position(self, pos):
        self._pos = round(pos / self.scale)

    def reset(self):
        self._pos = 0


encoder = EncoderTimed(rot_left, rot_right, False, 1)

disp = tm1637.TM1637Decimal(clk=Pin(16), dio=Pin(17))

pid = PID.PID(config["kp"], config["ki"], config["kd"], 75, None, (0, 1023), False)
