# !/usr/bin/python
# -*- coding:utf-8 -*-



def lazy_property(func):
    """
    修饰器，只在访问的时候才会计算结果。但是一旦被访问后，你希望结果值被缓存起来，不用每次都去计算。
    :param func:
    :return:
    """
    name = '_lazy_' + func.__name__

    @property
    async def lazy(self):
        if hasattr(self, name):
            return getattr(self, name)
        else:

            value = await func(self)
            setattr(self, name, value)
            return value

    return lazy
