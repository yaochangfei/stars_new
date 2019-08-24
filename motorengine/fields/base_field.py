# !/usr/bin/python
# -*- coding:utf-8 -*-


class BaseField(object):
    """
    这个类是所有Field类的基础，不建议直接调用
    """

    def __init__(self, db_field=None, required=False, default=None):
        if not isinstance(required, bool):
            raise ValueError("Parameter 'required' must be type bool.")
        self.db_field = db_field
        self.required = required
        self.default = default

    def validate(self, value):
        return True

    def is_empty(self, value):
        return value is None

    def to_bson(self, value=None):
        if value is None:
            return self.default
        return value

    def to_msgpack(self, value):
        return value

