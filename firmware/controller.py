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
        disp_val = str(val)[: len_ + 1] if "." in str(val) else str(val)[len_]
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
            print(val)
            await asyncio.sleep(0.1)
        hal.pid.set_auto_mode(False)
        hal.relay.duty(0)
        await asyncio.sleep(0.1)


async def start_controller():
    global heat_enabled
    hal.encoder.position = hal.temp * 10
    hal.pid.setpoint = await set_param("set ", 75, 100, 30)
    heat_enabled = True
