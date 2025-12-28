import sched
import time
import threading
from uuid import uuid4


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Scheduler(metaclass=Singleton):
    def __init__(self):
        self._scheduler = sched.scheduler(time.time, time.sleep)
        self._runner = threading.Thread(target=self.loop, daemon=True)
        self._runner.start()

    def loop(self):
        s = self._scheduler
        while True:
            s.run()

    def schedule(self, delay_in_seconds, func, *, args=(), kwargs={}):
        return self._scheduler.enter(
            delay_in_seconds, 1, func, argument=args, kwargs=kwargs
        )

    def cancel(self, event):
        self._scheduler.cancel(event)


class TaskManager(metaclass=Singleton):
    def __init__(self):
        self.scheduler = Scheduler()
        self._events = {}

    def schedule_task(self, delay_in_seconds, func, *args, **kwargs):
        event = self.scheduler.schedule(
            delay_in_seconds, func, args=args, kwargs=kwargs
        )
        event_id = str(uuid4())
        self._events[event_id] = event

        return event_id

    def clear_all_tasks(self):
        for event_id in list(self._events.keys()):
            self.cancel_task(event_id)

    def cancel_task(self, event_id):
        e = self._events.get(event_id)

        if e is not None:
            try:
                self.scheduler.cancel(e)
            except ValueError:
                pass
            finally:
                del self._events[event_id]
