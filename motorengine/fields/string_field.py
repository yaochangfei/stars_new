# !/usr/bin/python
# -*- coding:utf-8 -*-
from motorengine.errors import DocumentFieldRequiredError, DocumentFieldTypeError, DocumentFieldValueError
from motorengine.fields import BaseField


class StringField(BaseField):
    """
    用于存储文本
    """

    def __init__(self, max_length=None, min_length=0, *args, **kw):
        super(StringField, self).__init__(*args, **kw)

        if max_length and min_length > max_length:
            raise DocumentFieldValueError('min_length not allowed greater than max_length.')

        self.max_length = max_length
        self.min_length = min_length

    def validate(self, value):
        if value is None:
            if self.required:
                raise DocumentFieldRequiredError('Field value is required.')
            return True

        if isinstance(value, str):
            if self.max_length is None:
                return True
            else:
                if self.min_length <= len(value) <= self.max_length:
                    return True
                else:
                    raise DocumentFieldValueError(
                        "Field value length must >= min_length and <= 'max_length'. value is [%s]" % value)

        raise DocumentFieldTypeError('%s Field value must be str type.' % value)

    def is_empty(self, value=None):
        if value is None:
            return self.default
        return value
