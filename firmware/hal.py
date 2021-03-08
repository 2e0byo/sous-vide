import micropython
import utime
from machine import Pin, Timer, disable_irq, enable_irq


class settablePin(Pin):
    @property
    def val(self):
        return self.value() ^ 1

    @val.setter
    def val(self, value):
        self.value(value ^ 1)


relay_pin = settablePin(13, settablePin.OUT)

seg = (27, 26, 33, 25, 14, 17, 16, 32)
# a, b, c, d, e, f, g,  dp
# seg = tuple((settablePin(i, settablePin.OPEN_DRAIN) for i in seg))

digits = (18, 22, 21, 19)


sensor = settablePin(15)

button = settablePin(23, settablePin.IN, settablePin.PULL_UP)
rot_left = settablePin(35, settablePin.IN, settablePin.PULL_UP)
rot_right = settablePin(34, settablePin.IN, settablePin.PULL_UP)


class SevenSegment:

    font = {
        " ": 0,
        "0": 63,
        "1": 6,
        "2": 91,
        "3": 79,
        "4": 102,
        "5": 109,
        "6": 125,
        "7": 7,
        "8": 127,
        "9": 111,
        "a": 119,
        "b": 124,
        "c": 57,
        "d": 94,
        "e": 121,
        "f": 113,
        "g": 61,
        "h": 118,
        "i": 48,
        "j": 14,
        "k": 112,
        "l": 56,
        "m": 84,
        "n": 84,
        "o": 92,
        "p": 115,
        "q": 103,
        "r": 80,
        "s": 109,
        "t": 120,
        "u": 28,
        "v": 28,
        "w": 28,
        "x": 64,
        "y": 110,
        "z": 91,
        "-": 64,
    }

    def __init__(self, seg, digits):
        self.seg = seg
        self.seg_pins = tuple((settablePin(i, settablePin.OPEN_DRAIN) for i in seg))
        self.digits = digits

        self.digits_pins = tuple(
            (settablePin(i, settablePin.OPEN_DRAIN) for i in digits)
        )
        self.chars = [0, 0, 0, 0]
        self.digit_index = 0
        self.dim = 1
        self.count = 0

        self._compute_masks()
        self.display("ave ")

        self.disp_timer = Timer(0)
        self.disp_timer.init(period=1, mode=Timer.PERIODIC, callback=self._disp)

    def _compute_masks(self):
        self.font_masks = {}

        for k, v in self.font.items():
            lower_mask = 0
            upper_mask = 0
            for i in range(8):
                if self.seg[i] < 31:
                    if v & 1 << i:
                        lower_mask |= 1 << self.seg[i]
                else:
                    if v & 1 << i:
                        upper_mask |= 1 << (self.seg[i] - 32)
            self.font_masks[k] = (lower_mask, upper_mask)

        self.lower_digit_masks = []
        self.upper_digit_masks = []
        for v in self.digits:
            if v < 31:
                self.lower_digit_masks.append(1 << v)
            else:
                self.upper_digit_masks.append(1 << v - 32)

        lower_mask = 0
        upper_mask = 0
        for i in range(8):
            if self.seg[i] < 31:
                lower_mask |= 1 << self.seg[i]
            else:
                upper_mask |= 1 << (self.seg[i] - 32)
        self.lower_mask = lower_mask
        self.upper_mask = upper_mask

        self.lower_dp_mask = 1 << self.seg[-1] if self.seg[-1] < 31 else 0
        self.upper_dp_mask = 1 << self.seg[-1] - 32 if self.seg[-1] > 31 else 0

    @micropython.native
    def _disp(self, p):
        irq = disable_irq()
        # self.count += 1
        # if self.count == self.dim:
        #     self.count = 0
        # if self.count > 1:
        #     for i in range(8):
        #         self.seg_pins[i].val = 0
        #     return
        self._viper_set(self.lower_digit_masks[self.digit_index])
        self.digit_index += 1
        self.digit_index &= 3
        self._viper_disp(*self.chars[self.digit_index])
        self._viper_unset(self.lower_digit_masks[self.digit_index])
        enable_irq(irq)

    # @staticmethod
    @micropython.viper
    def _viper_disp(self, lower_mask: int, upper_mask: int):
        GPIO = ptr32(0x3FF44004)  # noqa
        # mask = int(0x5ECE0000)
        mask = int(self.lower_mask)
        GPIO[1] = mask
        GPIO[2] = lower_mask
        # gpio[2] = int(lower_mask & mask)
        GPIO = ptr32(0x3FF44010)  # noqa
        # mask = int(0x6)
        mask = int(self.upper_mask)
        GPIO[1] = mask
        GPIO[2] = upper_mask
        # GPIO[2] = int(~upper_mask & mask)

    @staticmethod
    @micropython.viper
    def _viper_set(mask: int):
        GPIO = ptr32(0x3FF44004)  # noqa
        GPIO[1] = mask

    @staticmethod
    @micropython.viper
    def _viper_unset(mask: int):
        GPIO = ptr32(0x3FF44004)  # noqa
        GPIO[2] = mask

    def display(self, s):
        i = 0
        for char in str(s):
            if char == ".":
                if i:
                    lower = self.chars[i - 1][0] | self.lower_dp_mask
                    upper = self.chars[i - 1][1] | self.upper_dp_mask
                    self.chars[i - 1] = (lower, upper)
                    continue
                else:
                    lower = self.lower_dp_mask
                    upper = self.upper_dp_mask
                    self.chars[i] = (lower, upper)
            else:
                self.chars[i] = self.font_masks[char]

            i += 1
            if i == 4:
                break
        self.count = 0

    @property
    def brightness(self):
        return 5 - self.dim

    @brightness.setter
    def brightness(self, br):
        if br > 4 or br < 0:
            raise ValueError("Brightness is between 4 and 0")
        self.dim = 5 - br
        self.count = 0


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

    def reset(self):
        self._pos = 0


seven_seg = SevenSegment(seg, digits)
encoder = EncoderTimed(rot_left, rot_right, False, 1)

while True:
    seven_seg.display("{:4}".format(encoder.position))
    utime.sleep(0.5)


@micropython.viper
def set_gpio(mask: int):
    GPIO_BASE = ptr32(0x3F404000)  # noqa
    GPIO_BASE[1] = mask


@micropython.viper
def unset_gpio(mask: int):
    GPIO = ptr32(0x3FF44004)
    GPIO[2] = mask


@micropython.viper
def get_gpios() -> int:
    GPIO = ptr32(0x3FF44004)
    return int(GPIO_BASE[0x8])


@micropython.viper
def viperbop():
    GPIO = ptr32(0x3FF44004)
    while True:
        GPIO[1] = 1 << 22
        GPIO[2] = 1 << 22


@micropython.viper
def lower(gs):
    GPIO = ptr32(0x3FF44004)
    mask = 0x5ECE0000
    GPIO[1] = int(gs & mask)
    GPIO[2] = int(~gs & mask)


# @micropython.viper
# def upper(gs):
#     GPIO = ptr32(0x3FF44010)
#     mask = 0x6
#     GPIO[1] = int(gs & mask)
#     GPIO[2] = int(~gs & mask)
