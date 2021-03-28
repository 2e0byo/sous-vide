import uasyncio as asyncio

import hal

heat_enabled = False
time_remaining = False


async def set_param(
    name_, param, max_, min_, step=0.1, timeout=1000, len_=3, formatstr="{0: >3}*"
):
    """
    Set a parameter using the rotary encoder.

    Click to exit.  Times out after timeout ms.
    """
    hal.display_lock = True
    hal.disp.show(name_)
    await asyncio.sleep(0.5)

    old_fns = {}
    old_attrs = ("_ff", "_fa", "_df", "_da", "_lf", "_la")
    for x in old_attrs:
        try:
            old_fns[x] = getattr(hal.button, x)
        except AttributeError:
            old_fns[x] = ()

    inactive_ms = 0
    hal.button.release_func(hal.set_push_flag)
    hal.button.double_func(hal.set_double_flag)
    hal.encoder.position = param / step

    while (inactive_ms < timeout) and not hal.push_flag:
        val = hal.encoder.position * step
        hal.encoder.position = max(min_, min(val, max_)) / step
        val = hal.encoder.position * step
        disp_val = str(val)[: len_ + 1] if "." in str(val) else str(val)[:len_]
        hal.disp.show(formatstr.format(disp_val))
        await asyncio.sleep(0.1)

    hal.push_flag = False
    brightness = hal.disp.brightness()
    for _ in range(2):
        hal.disp.brightness(0)
        await asyncio.sleep(0.1)
        hal.disp.brightness(brightness)
        await asyncio.sleep(0.1)

    hal.button.double_func(old_fns["_df"], old_fns["_da"])
    hal.button.long_func(old_fns["_lf"], old_fns["_la"])
    for x in old_attrs:
        setattr(hal.button, x, old_fns[x])

    hal.display_lock = False
    return val


async def heat_loop():
    global heat_enabled
    while True:
        if heat_enabled:
            hal.pid.set_auto_mode(True)
        while heat_enabled:
            rom = hal.detect_sensor()
            temp = await hal.read_sensor(rom)
            val = hal.pid(temp)
            hal.relay.duty(round(val))
            await asyncio.sleep(0.1)
        hal.pid.set_auto_mode(False)
        hal.relay.duty(0)
        await asyncio.sleep(0.1)


async def _manual_start_controller():
    global heat_enabled
    hal.encoder.position = hal.temp * 10
    hal.pid.setpoint = await set_param("set ", 75, 100, 30)
    heat_enabled = True


def manual_start_controller(loop):
    loop.create_task(_manual_start_controller())


def start_controller():
    global heat_enabled
    heat_enabled = True


def stop_controller():
    global heat_enabled
    heat_enabled = False


async def _manual_start_countdown():
    global time_remaining
    hours = await set_param("hrs ", 0, 23, 0, formatstr="{:0>2}.00", step=1)
    mins = await set_param(
        "mins", 0, 59, 0, formatstr="{:02}".format(hours) + ".{:0>2}", step=1
    )
    time_remaining = hours * 3600 + mins * 60


def manual_start_countdown(loop):
    loop.create_task(_manual_start_countdown())


async def countdown_loop():
    global time_remaining
    while True:
        while not time_remaining:
            await asyncio.sleep(1)
        while time_remaining:
            time_remaining -= 1
            if time_remaining == 0:
                print("ring ring ring ring ring")  # implement alarm here


def start_countdown(secs):
    global time_remaining
    time_remaining = secs


def stop_countdown():
    global time_remaining
    time_remaining = None


def init(loop):
    loop.create_task(heat_loop())
    loop.create_task(countdown_loop())
