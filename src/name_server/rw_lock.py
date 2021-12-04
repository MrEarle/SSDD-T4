from threading import Semaphore
from typing import Tuple


class RWLock:
    def __init__(self) -> None:
        self.rw = Semaphore(1)
        self.mutex = Semaphore(1)

        self.readers = 0

    def enter_write(self):
        self.rw.acquire()

    def exit_write(self):
        self.rw.release()

    def enter_read(self):
        self.mutex.acquire()
        self.readers += 1
        if self.readers == 1:
            self.rw.acquire()
        self.mutex.release()

    def exit_read(self):
        self.mutex.acquire()
        self.readers -= 1
        if self.readers == 0:
            self.rw.release()
        self.mutex.release()


class Reader:
    def __init__(self, rwlock: RWLock) -> None:
        self.rwlock = rwlock

    def __enter__(self):
        self.rwlock.enter_read()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.rwlock.exit_read()


class Writer:
    def __init__(self, rwlock: RWLock) -> None:
        self.rwlock = rwlock

    def __enter__(self):
        self.rwlock.enter_write()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.rwlock.exit_write()


def get_rwlock() -> Tuple[Reader, Writer]:
    rwlock = RWLock()
    return Reader(rwlock), Writer(rwlock)
