import logging

import uasyncio as asyncio
from secret import wifi_PSK, wifi_SSID

import controller
import hal

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)
loop = asyncio.get_event_loop()


async def boot_screen():
    hal.disp.show("ave ")
    for _ in range(2):
        for i in range(8):
            hal.disp.brightness(i)
            await asyncio.sleep_ms(50)
        for i in range(8):
            hal.disp.brightness(7 - i)
            await asyncio.sleep_ms(50)
    for i in range(hal.config["brightness"]):
        hal.disp.brightness(i)
        await asyncio.sleep_ms(50)


async def set_temp_loop():
    """Test loop for setting temp."""
    for i in range(100):
        hal.disp.show("{0: >3d}*".format(hal.encoder.position))
        await asyncio.sleep(0.1)


async def wifi():
    """Connect to the network."""
    import network

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    while True:
        if not wlan.isconnected():
            logger.info("connecting to network...")
            wlan.connect(wifi_SSID, wifi_PSK)
            while not wlan.isconnected():
                await asyncio.sleep_ms(100)
            logger.info("network config: {}".format(wlan.ifconfig()))
        else:
            await asyncio.sleep(1)


async def main():
    logger.info("Booting up")
    hal.init(loop)
    loop.create_task(wifi())
    await boot_screen()
    logger.info("Awaiting sensor connection.")
    while not hal.rom:
        await asyncio.sleep_ms(100)
    logger.info("Sensor connected!")
    loop.create_task(controller.heat_loop())

    while True:
        if hal.rom:
            logger.info("Sensor connected!")
        while hal.rom:
            for _ in range(5):
                disp_temp = str(hal.temp)[:4]
                if "." not in disp_temp:
                    disp_temp = disp_temp[:3]
                hal.disp.show("{0: >3}*".format(disp_temp))
                await asyncio.sleep(1)
            if controller.time_remaining:
                for _ in range(5):
                    t = controller.time_remaining
                    if t > 3600:
                        t //= 60
                    hal.disp.show("{:02}.{:02}".format(*divmod(t, 60)))
                    await asyncio.sleep(1)
        logger.info("Awaiting sensor connection.")
        while not hal.rom:
            await asyncio.sleep_ms(100)


loop.run_until_complete(main())
