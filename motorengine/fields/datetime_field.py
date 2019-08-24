# !/usr/bin/python
# -*- coding:utf-8 -*-

from datetime import datetime

from motorengine.errors import DocumentFieldRequiredError, DocumentFieldTypeError
from motorengine.fields import BaseField

FORMAT = '%Y-%m-%d %H:%M:%S'


class DateTimeField(BaseField):
    """
    用于存储日期时间
    """

    def __init__(self, tz=None, *args, **kw):
        super(DateTimeField, self).__init__(*args, **kw)

        self.tz = tz

    def validate(self, value):
        if value is None:
            if self.required:
                raise DocumentFieldRequiredError('Field value is required.')
            return True

        if callable(value):
            value = value()

        if isinstance(value, datetime):
            return True

        raise DocumentFieldTypeError('Field value must be datetime.datetime type.')

    def to_bson(self, value=None):
        if value is None:
            if callable(self.default):
                return self.default()
            return self.default

        if callable(value):
            value = value()

        if isinstance(value, str):
            value = datetime.strptime(value, FORMAT)

        return self.ensure_timezone(value)

    def ensure_timezone(self, value):
        if value.tzinfo is None and self.tz is not None:
            return value.replace(tzinfo=self.tz)

        if value.tzinfo is not None and self.tz != value.tzinfo:
            return value.astimezone(self.tz)

        return value

    def to_msgpack(self, value):
        if isinstance(value, datetime):
            return '[DT]%s' % value.strftime('%Y-%m-%d %H:%M:%S.%f')
        return value
