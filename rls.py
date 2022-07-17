"""
Credit: https://stackoverflow.com/a/46255794/16775319
"""
import asyncio
from collections import deque


class RateLimitingSemaphore:
    def __init__(self, qps_limit, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.qps_limit = qps_limit

        # The number of calls that are queued up, waiting for their turn.
        self.queued_calls = 0

        # The times of the last N executions, where N=qps_limit - this should allow us to calculate the QPS within the
        # last ~ second. Note that this also allows us to schedule the first N executions immediately.
        self.call_times = deque()

    async def __aenter__(self):
        self.queued_calls += 1
        while True:
            cur_rate = 0
            if len(self.call_times) == self.qps_limit:
                if self.loop.time() - self.call_times[0] != 0:
                    cur_rate = len(self.call_times) / (self.loop.time() - self.call_times[0])
                else:
                    cur_rate = len(self.call_times) / (self.loop.time() + 0.000001 - self.call_times[0])
            if cur_rate < self.qps_limit:
                break
            interval = 1. / self.qps_limit
            elapsed_time = self.loop.time() - self.call_times[-1]
            await asyncio.sleep(self.queued_calls * interval - elapsed_time)
        self.queued_calls -= 1

        if len(self.call_times) == self.qps_limit:
            self.call_times.popleft()
        self.call_times.append(self.loop.time())

    async def __aexit__(self, exc_type, exc, tb):
        pass