# !/usr/bin/python
# -*- coding:utf-8 -*-

from motorengine.errors import DocumentFieldRequiredError, DocumentFieldTypeError
from motorengine.fields import BaseField


class BooleanField(BaseField):
    """
    用于存储布尔型
    """

    def __init__(self, *args, **kw):
        super(BooleanField, self).__init__(*args, **kw)

    def validate(self, value):
        if value is None:
            if self.required:
                raise DocumentFieldRequiredError('Field value is required.')
            return True

        if isinstance(value, bool):
            return True

        raise DocumentFieldTypeError('Field value must be bool type.')

    def to_bson(self, value=None):
        if value is None:
            return self.default
        return bool(value)
