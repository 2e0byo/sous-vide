import json

import ds18x20
import micropython
import onewire
import uasyncio as asyncio
import ulogging as logging
from machine import PWM, Pin

import PID
import tm1637
from alarm_rtc import AlarmRTC
from primitives.pushbutton import Pushbutton

logger = logging.getLogger(__name__)
config = {"Kp": 1, "Ki": 0.5, "Kd": 0.5, "brightness": 6, "setpoint": 75, "freq": 0.005}
try:
    with open("config.json") as f:
        config.update(json.load(f))
except OSError:
    pass

avg = 15
temp_reset = False


def persist_config():
    with open("config.json", "w") as f:
        f.write(json.dumps(config))


class settablePin(Pin):
    @property
    def val(self):
        return self.value() ^ 1

    @val.setter
    def val(self, value):
        self.value(value ^ 1)


display_lock = False

relay_pin = Pin(13, Pin.OUT)


class softPWM:
    def __init__(self, pin, freq=0.005, duty=0):
        self.pin = pin
        self.pin.off()
        self._duty = duty
        self._period = None
        self.freq(freq)
        self._reset = False
        asyncio.get_event_loop().create_task(self._loop())

    def freq(self, f=None):
        if f:
            self._period = round(1000 / (f * 1023))
            self._reset = True
        return 1023000 / self._period

    def duty(self, d=None):
        if d is not None:
            if d < 0 or d > 1023:
                raise Exception("Duty must be between 0 and 1023")
            old_duty = self._duty
            self._duty = d
            if self._duty != old_duty:
                self._reset = True
        return self._duty

    async def _loop(self):
        count = 0
        while True:
            if count == self._duty:
                self.pin.off()
            count += 1
            if count > 1023 or self._reset:
                self._reset = False
                count = 0
                if self._duty:
                    self.pin.on()
            await asyncio.sleep_ms(self._period)


relay = softPWM(relay_pin, freq=config["freq"], duty=0)
period = relay._period
buzzer = PWM(Pin(12), duty=0, freq=440)
alarm_flag = False


def save_button_fns():
    old_fns = {}
    old_attrs = ("_ff", "_fa", "_df", "_da", "_lf", "_la")
    for x in old_attrs:
        try:
            old_fns[x] = getattr(button, x)
        except AttributeError:
            old_fns[x] = ()
    return old_fns


def restore_button_fns(old_fns):
    button.double_func(old_fns["_df"], old_fns["_da"])
    button.long_func(old_fns["_lf"], old_fns["_la"])
    button.release_func(old_fns["_ff"], old_fns["_fa"])


def stop_alarm():
    global alarm_flag
    alarm_flag = False


async def sound(alarm_id=None):
    global alarm_flag
    alarm_flag = True
    old_fns = save_button_fns()
    button.double_func(stop_alarm)
    button.long_func(stop_alarm)
    button.release_func(stop_alarm)
    duty = 16
    while alarm_flag:
        if duty < 512:
            duty += 32
        for i in range(4):
            buzzer.duty(duty)
            await asyncio.sleep_ms(50)
            buzzer.duty(0)
            await asyncio.sleep_ms(50)
        await asyncio.sleep(1)
    restore_button_fns(old_fns)
    if alarm_id is not None:
        rtc.cancel(alarm_id)


seg = (27, 26, 33, 25, 14, 17, 16, 32)
# a, b, c, d, e, f, g,  dp
# seg = tuple((settablePin(i, settablePin.OPEN_DRAIN) for i in seg))

digits = (18, 22, 21, 19)


sensor = Pin(15)
ow = onewire.OneWire(sensor)
ds = ds18x20.DS18X20(ow)
rom = None
temp = None


def detect_sensor():
    """
    Detect sensor if attached.

    Returns rom if present else None.
    """
    try:
        roms = ds.scan()
    except Exception as e:
        logger.debug("detect_sensor raised exception {}".format(e))
        return None
    no_roms = len(roms)
    if no_roms > 1:
        logger.debug("detected {} sensors attached; aborting".format(no_roms))
    if no_roms != 1:
        return None
    else:
        return roms[0]


async def read_sensor(rom):
    """Read sensor."""
    ds.convert_temp()
    await asyncio.sleep_ms(750)
    return ds.read_temp(rom)


async def temp_loop():
    global rom
    global temp
    global temp_reset
    global avg
    temps = []
    while True:
        while not (rom := detect_sensor()):
            logger.debug("No sensor found")
            await asyncio.sleep_ms(200)
        try:
            temps = [await read_sensor(rom)] * avg
        except Exception as e:
            logger.debug("read_sensor raised exception {}".format(e))
            rom = None
        i = 0
        while rom and not temp_reset:
            try:
                temps[i] = await read_sensor(rom)
                logger.debug("Got {}".format(temps[i]))
                temp = sum(temps) / avg
            except (onewire.OneWireError, Exception) as e:
                logger.debug("read_sensor raised exception {}.".format(e))
                rom = None
            await asyncio.sleep_ms(250)
            i += 1
            i %= avg
        temp_reset = False


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

pid = PID.PID(
    config["Kp"],
    config["Ki"],
    config["Kd"],
    config["setpoint"],
    sample_time=None,
    output_limits=(0, 1023),
    proportional_on_measurement=False,
    error_map=None,
)

rtc = AlarmRTC()


def init(loop):
    loop.create_task(temp_loop())
