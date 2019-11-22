import os
import time
import functools
import logging
from typing import Callable, Any, Dict, cast

log = logging.getLogger(__name__)

class memoize():
    """ Very simple memoize wrapper

    function decorator: cache lives globally
    method decorator: cache lives inside `obj_instance.__memoize_cache`
    """

    def __init__(self, func: Callable[..., Any] = None, expire_secs: float = 0, obj=None, cache: Dict[Any, Any] = None):
        self.func = func
        self.expire_secs = expire_secs
        self.cache = cache
        if cache is None:
            self.cache = {}
        if self.func is not None:
            functools.update_wrapper(self, func)
        self.obj = obj

    def __get__(self, obj, objtype=None):
        if obj is None:
            # does this ever happen?
            return self.func

        if type(self.cache) is str:
            # user specified name of a property that contains the cache dictionary
            # use this to prevent race conditions from injection below!
            cache = getattr(obj, cast(str, self.cache))
        else:
            # inject cache into the instance, so it doesn't live beyond the scope of the instance
            # without this, memoizing can cause serious unexpected memory leaks
            try:
                cache = obj.__memoize_cache          # pylint: disable=protected-access
            except AttributeError:
                try:
                    cache = obj.__memoize_cache = {}
                except Exception as e:
                    # some objects don't work with injection
                    log.warning("cannot inject cache: '%s', ensure object is a singleton, or pass a cache in!", e)
                    cache = self.cache

        return memoize(self.func, expire_secs=self.expire_secs, cache=cache, obj=obj)

    def __call__(self, *args, **kwargs):
        if self.func is None:
            # this was used as a function style decorator
            # there should be no kwargs
            assert not kwargs
            func = args[0]
            return memoize(func, expire_secs=self.expire_secs, cache=self.cache)

        if self.obj is not None:
            args = (self.obj, *args)

        key = (args, tuple(sorted(kwargs.items())))
        cur_time = time.monotonic()

        if key in self.cache:
            (cresult, ctime) = self.cache[key]
            if not self.expire_secs or cur_time < (ctime + self.expire_secs):
                return cresult

        result = self.func(*args, **kwargs)
        self.cache[key] = (result, cur_time)
        return result

    def clear(self, *args, **kwargs):
        if self.obj is not None:
            args = (self.obj, *args)
        key = (args, tuple(sorted(kwargs.items())))
        self.cache.pop(key, None)

    def get(self, *args, **kwargs):
        if self.obj is not None:
            args = (self.obj, *args)
        key = (args, tuple(sorted(kwargs.items())))
        if key in self.cache:
            return self.cache[key][0]
        return None

    def set(self, *args, _value, **kwargs):
        if self.obj is not None:
            args = (self.obj, *args)
        key = (args, tuple(sorted(kwargs.items())))
        self.cache[key] = (_value, time.monotonic())

def test_memoize1():
    func = lambda *a: (a, os.urandom(32))
    cached = memoize(func, 60)

    a = cached()
    assert cached.get() == a
    b = cached()
    # same vals
    assert a == b

    # clear test
    cached.clear()
    b = cached()
    assert a != b

    # with param test
    p1 = cached(32)

    assert p1[0] == (32,)
    assert p1 != b and p1 != a
    p2 = cached(32)
    p3 = cached(33)

    assert p1 == p2
    assert p3[0] == (33,)

    # clears z only
    cached.clear(32)
    p4 = cached(33)

    assert p3 == p4

    # zero param is still ok
    a = cached()
    assert a == b

    b = cached.get()
    assert a == b

    cached.clear()
    assert cached.get() is None

    cached.set(3, b=4, _value=44)
    assert cached.get(3, b=4) == 44
    assert cached(3, b=4) == 44

def test_memoize2():
    @memoize
    def fun(a):
        return (a, os.urandom(32))

    x = fun(1)
    y = fun(1)
    assert x == y
    z = fun(2)
    assert z != x

    @memoize(expire_secs=3)
    def fun2(a):
        return (a, os.urandom(32))

    x = fun2(1)
    y = fun2(1)
    assert x == y
    z = fun2(2)
    assert z != x


def test_memoize3():
    class Cls:
        @memoize
        def fun(self, a):
            return (a, os.urandom(32))

        @memoize
        def fun2(self):
            return os.urandom(32)

    # different self's
    x = Cls().fun(1)
    y = Cls().fun(1)
    assert x != y

    c = Cls()
    x = c.fun(1)
    assert c.fun.get(1) == x
    assert c.fun.get(1)
    y = c.fun(1)
    assert x == y
    z = c.fun(2)
    assert z != x
    log.debug("no args test")
    m = c.fun2()
    assert m
    assert c.fun2.get() == m


def test_memoize4():
    class Cls:
        foo = {}
        @memoize(cache="foo")
        def fun(self, a):
            return (a, os.urandom(32))

        @memoize(cache="foo")
        def fun2(self):
            return os.urandom(32)

    # different self's
    x = Cls()
    y = x.fun(1)
    assert list(x.foo.values())[0][0] == y
