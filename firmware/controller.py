import uasyncio as asyncio

import hal


async def set_param(
    name_, param, max_, min_, step=0.1, timeout=1000, len_=3, formatstr="{0: >3}*"
):
    """
    Set a parameter using the rotary encoder.

    Click to exit.  Times out after timeout ms.
    """

    hal.disp.show(name_)

    old_fns = {}
    old_attrs = ("ff", "fa", "df", "da", "lf", "la")
    for x in old_attrs:
        old_fns[x] = getattr(hal.button, x)

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

    for x in old_attrs:
        setattr(hal.button, x, old_fns[x])

    return val
