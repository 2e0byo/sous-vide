import time

import machine
import uasyncio as asyncio


class AlarmRTC(machine.RTC):
    """RTC implementing the alarm fns."""

    def __init__(self):
        self._alarms = {}
        asyncio.get_event_loop().create_task(self._alarm_loop())
        super().__init__()

    @staticmethod
    async def run_fn(fn):
        fn()

    async def _alarm_loop(self):
        """Alarm loop to trigger fns if required."""
        while True:
            now = time.time()
            for _, alarm in self._alarms.items():
                if alarm[0] == now:
                    if alarm[1]:
                        if type(alarm[1]).__name__ == "funcion":
                            asyncio.get_event_loop().create_task(self.run_fn(alarm[1]))
                        else:
                            asyncio.get_event_loop().create_task(alarm[1]())
                    if alarm[2]:
                        alarm[0] = time.time() + alarm[2]
            await asyncio.sleep(1)  # 1s precision

    def alarm(self, id: int, time, *, repeat=False):
        """
        Set the RTC alarm.

        Args:
          id: int: the id of the alarm
          time: either *seconds* in the future or a datetimetuple.
          *: other args, included for compatibility but silently ignored.
          repeat:  (Default value = False) whether to repeat on elapse.

        Returns:
        """
        try:
            time = time.time() + int(time)
            periodic = int(time) if repeat else False
        except TypeError:
            time = time.mktime(time)
            periodic = False
        self._alarms[int(id)] = (time, None, periodic)

    def alarm_left(self, alarm_id: int = 0):
        """

        Args:
          alarm_id: int: alarm in question. (Default value = 0)

        Returns:
          time in s to the alarm.
        """
        return self._alarms[int(alarm_id)][0] - time.time()

    def cancel(self, alarm_id=0):
        """
        Cancel an alarm.

        Fails silently.
        """
        try:
            del self._alarms[alarm_id]
        except KeyError:
            pass

    def irq(self, alarm_id, handler=None):
        """Set handler for alarm."""
        self._alarms[int(id)][1] = handler
