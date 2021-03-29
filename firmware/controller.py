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

    old_fns = hal.save_button_fns()

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
    await flash_disp()
    hal.restore_button_fns(old_fns)

    hal.display_lock = False
    return val


async def flash_disp():
    brightness = hal.disp.brightness()
    for _ in range(2):
        hal.disp.brightness(0)
        await asyncio.sleep(0.1)
        hal.disp.brightness(brightness)
        await asyncio.sleep(0.1)


async def heat_loop():
    global heat_enabled
    while True:
        if heat_enabled and hal.rom:
            hal.pid.set_auto_mode(True)
        while heat_enabled and hal.rom:
            val = hal.pid(hal.temp)
            hal.relay.duty(round(val))
            await asyncio.sleep(hal.period)
        hal.pid.set_auto_mode(False)
        hal.relay.duty(0)
        await asyncio.sleep(0.1)


async def _manual_start_controller():
    global heat_enabled
    hal.encoder.position = hal.temp * 10
    hal.pid.setpoint = await set_param("set ", 75, 100, 30)
    hal.config["setpoint"] = hal.pid.setpoint
    hal.persist_config()
    heat_enabled = True


def manual_start_controller(loop):
    loop.create_task(_manual_start_controller())


def start_controller():
    global heat_enabled
    heat_enabled = True


def stop_controller():
    global heat_enabled
    heat_enabled = False


async def _toggle():
    global heat_enabled
    heat_enabled = False if heat_enabled else True
    if not heat_enabled:
        hal.relay.duty(0)
    before = hal.display_lock
    hal.display_lock = True
    hal.disp.show("On  " if heat_enabled else "Off ")
    await flash_disp()
    hal.display_lock = before


def manual_toggle(loop):
    loop.create_task(_toggle())


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
        while not time_remaining or not heat_enabled:
            await asyncio.sleep(1)
        while time_remaining and heat_enabled:
            time_remaining -= 1
            if time_remaining == 0:
                await hal.sound()
            await asyncio.sleep(1)


def start_countdown(secs):
    global time_remaining
    time_remaining = secs


def stop_countdown():
    global time_remaining
    time_remaining = None


def init(loop):
    loop.create_task(heat_loop())
    loop.create_task(countdown_loop())
