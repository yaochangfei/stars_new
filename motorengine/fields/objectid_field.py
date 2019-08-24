# !/usr/bin/python
# -*- coding:utf-8 -*-

from bson import ObjectId

from motorengine.fields import BaseField


class ObjectIdField(BaseField):
    """
    用于存储数据库Document主键
    """

    def __init__(self):
        super(ObjectIdField, self).__init__(db_field='_id', required=False, default=None)

    def validate(self, value):
        return value is None or isinstance(value, ObjectId)

    def to_msgpack(self, value):
        if isinstance(value, ObjectId):
            return '[ID]%s' % str(value)
        return value
