import micropython
from machine import Pin, Timer


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
seg = tuple((settablePin(i, settablePin.OPEN_DRAIN) for i in seg))

digits = (18, 22, 21, 19)
digits = tuple((settablePin(i, settablePin.OPEN_DRAIN) for i in digits))


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
    }

    def __init__(self, seg, digits):
        self.seg = seg
        self.digits = digits
        self.chars = bytearray(4)
        self.digit_index = 0
        self.dim = 1
        self.count = 0

        self.disp_timer = Timer(0)
        self.disp_timer.init(period=3, mode=Timer.PERIODIC, callback=self._disp)
        self.display("ave ")

    # consider using stm to edit the gpio register in one step.
    @micropython.native
    def _disp(self, p):
        self.count += 1
        if self.count == self.dim:
            self.count = 0
        if self.count > 1:
            for i in range(8):
                self.seg[i].val = 0
            return

        self.digits[self.digit_index].val = 0
        self.digit_index += 1
        self.digit_index &= 3
        for i in range(8):
            self.seg[i].val = self.chars[self.digit_index] >> i & 1
        self.digits[self.digit_index].val = 1

    def display(self, s):
        i = 0
        for char in str(s):
            if char == ".":
                if i:
                    self.chars[i - 1] |= 1 << 7
                    continue
                else:
                    self.chars[i] = 1 << 7
            else:
                self.chars[i] = self.font[char]

            i += 1
            if i == 4:
                break

    @property
    def brightness(self):
        return 5 - self.dim

    @brightness.setter
    def brightness(self, br):
        if br > 4 or br < 0:
            raise ValueError("Brightness is between 4 and 0")
        self.dim = 5 - br
        self.count = 0


seven_seg = SevenSegment(seg, digits)
