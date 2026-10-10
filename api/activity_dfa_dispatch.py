"""Compatibility wake hints only. API workers never launch computations."""
import threading
_wake = threading.Event()


def wake():
    _wake.set()


def start():
    pass


def stop():
    pass
