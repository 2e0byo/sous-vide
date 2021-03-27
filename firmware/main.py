import uasyncio as asyncio

from hal import disp


async def boot_screen():
    disp.show("ave ")
    for i in range(8):
        disp.brightness(i)
        await asyncio.sleep(0.1)
        print(i)


loop = asyncio.get_event_loop()
loop.create_task(boot_screen())
try:
    loop.run_forever()
finally:
    loop.close()
