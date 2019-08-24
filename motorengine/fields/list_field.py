# !/usr/bin/python
# -*- coding:utf-8 -*-

import datetime

from bson import ObjectId

from motorengine.errors import DocumentFieldRequiredError, DocumentFieldTypeError
from motorengine.fields import BaseField


class ListField(BaseField, list):
    """
    用于存储日期时间
    """

    def __init__(self, *args, **kw):
        super(ListField, self).__init__(*args, **kw)

        if not self.default:
            self.default = []

    def validate(self, value):
        if value is None:
            if self.required:
                raise DocumentFieldRequiredError('Field value is required.')
            return True
        if isinstance(value, list):
            return True
        raise DocumentFieldTypeError('Field value must be list type.')

    def is_empty(self, value):
        return value is None or value == []

    def to_bson(self, value=None):
        if value is None:
            return self.default

        return list(value)

    def to_msgpack(self, value):
        try:
            if isinstance(value, list):
                for index, v in enumerate(value):
                    value[index] = self.to_msgpack(v)
            if isinstance(value, dict):
                for k, v in value.items():
                    value[k] = self.to_msgpack(v)
            if isinstance(value, datetime.datetime):
                value = '[DT]%s' % value.strftime('%Y-%m-%d %H:%M:%S.%f')
            if isinstance(value, ObjectId):
                value = '[ID]%s' % str(value)
        except Exception:
            pass
        return value
