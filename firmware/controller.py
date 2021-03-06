import time

import uasyncio as asyncio
import ulogging as logging

import hal
from autotune import PIDAutotune

logger = logging.getLogger(__name__)
heat_enabled = False

autotuner = PIDAutotune(60, 1023, out_min=0, out_max=1023, time=time.time)
tuned = False
generated_params = []


async def autotune_loop(temp):
    global heat_enabled
    global generated_params
    global tuned
    tuned = False
    generated_params = []
    before = heat_enabled
    heat_enabled = False
    tuned = False
    autotuner._setpoint = temp
    logger.info("Starting autotune loop")
    while not tuned:
        tuned = autotuner.run(hal.temp)
        state = autotuner.state
        hal.relay.duty(int(autotuner.output))
        await asyncio.sleep(5)
        if (s := autotuner.state) != state:
            logger.info(s)
    hal.relay.duty(0)
    heat_enabled = before
    if tuned == "cancelled":
        logger.info("Cancelling autotune")
        return
    _params = []
    for rule in autotuner.tuning_rules:
        params = autotuner.get_pid_parameters(rule)
        logger.info("rule {} yielded {}".format(rule, params))
        _params.append(params)
    generated_params = _params
    assert generated_params, "Params not populated for some reason."


def autotune(temp):
    asyncio.get_event_loop().create_task(autotune_loop(temp))


async def set_param(
    name_, param, max_, min_, step=0.1, timeout=1000, len_=3, formatstr="{0: >3}*"
):
    """
    Set a parameter using the rotary encoder.

    Click to exit.  Times out after timeout ms.
    """
    hal.display_lock = True
    if name_:
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
    while not hal.temp:
        await asyncio.sleep(1)
    while True:
        if heat_enabled and hal.rom:
            hal.pid.set_auto_mode(True)
        while heat_enabled and hal.rom:
            _duty = hal.relay.duty()
            val = round(hal.pid(hal.temp))
            if val != _duty:
                logger.debug("pid yields: {}".format(val))
                logger.debug(hal.pid.components)
            hal.relay.duty(val)
            await asyncio.sleep(10)
        hal.pid.set_auto_mode(False)
        hal.relay.duty(0)
        while not heat_enabled:
            await asyncio.sleep(0.1)


async def beep_at_temperature():
    direction = -1 if hal.temp > hal.pid.setpoint else 1
    while (hal.pid.setpoint - hal.temp) * direction > 0:
        await asyncio.sleep(15)
    await hal.sound()


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
    hal.pid.auto_mode = True
    asyncio.get_event_loop().create_task(beep_at_temperature())


def stop_controller():
    global heat_enabled
    heat_enabled = False
    hal.relay.duty(0)
    hal.pid.auto_mode = False
    hal.pid.reset()


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
    hours = await set_param(None, 0, 23, 0, formatstr="{:0>2}.00", step=1)
    mins = await set_param(
        None, 0, 59, 0, formatstr="{:02}".format(hours) + ".{:0>2}", step=1
    )
    time_remaining = hours * 3600 + mins * 60
    hal.rtc.cancel(0)
    hal.rtc.alarm(0, time_remaining)
    hal.rtc.irq(0, hal.sound)


def manual_start_countdown(loop):
    loop.create_task(_manual_start_countdown())


def start_countdown(secs):
    hal.rtc.cancel(0)
    hal.rtc.alarm(0, secs)
    hal.rtc.irq(0, hal.sound)


def stop_countdown():
    hal.rtc.cancel(0)


def init(loop):
    loop.create_task(heat_loop())
