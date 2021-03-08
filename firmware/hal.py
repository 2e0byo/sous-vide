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

chars = bytearray(4)

for i in range(1, 4):
    digits[i].val = 0


# def disp(char, dp=False):
#     segs = font[str(char)] | dp << 7
#     for i in range(8):
#         seg[i].val = segs >> i & 1


digit_index = 0
dim = 2
count = 0


@micropython.native
def disp(p):
    global digit_index  # , count
    digits[digit_index].val = 0
    digit_index += 1
    digit_index &= 3
    for i in range(8):
        seg[i].val = chars[digit_index] >> i & 1
    digits[digit_index].val = 1


def display(s: str):
    global chars
    i = 0
    for char in s:
        if char == ".":
            if i:
                chars[i - 1] |= 1 << 7
                continue
            else:
                chars[i] = 1 << 7
        else:
            chars[i] = font[char]

        i += 1
        if i == 4:
            break


disp_timer = Timer(0)
disp_timer.init(period=5, mode=Timer.PERIODIC, callback=disp)
display("hi  ")
