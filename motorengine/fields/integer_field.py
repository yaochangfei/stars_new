# !/usr/bin/python
# -*- coding:utf-8 -*-
from motorengine.errors import DocumentFieldRequiredError, DocumentFieldTypeError, DocumentFieldValueError
from motorengine.fields import BaseField


class IntegerField(BaseField):
    """
    用于存储整型
    """

    def __init__(self, min_value=None, max_value=None, choice=None, *args, **kw):
        self.__validate_choice(choice)

        super(IntegerField, self).__init__(*args, **kw)

        self.min_value = min_value
        self.max_value = max_value
        self.choice = choice

    def __validate_choice(self, value):
        if value is None:
            return True

        if not value:
            raise ValueError("'choice' cannot be empty.")

        if not isinstance(value, list):
            raise ValueError("'choice' must be list type.")

        for v in value:
            if not isinstance(v, int):
                raise ValueError("'choice' values must be all int type.")

    def validate(self, value):
        if value is None:
            if self.required:
                raise DocumentFieldRequiredError('Field value is required.')
            return True

        try:
            value = int(value)
        except ValueError:
            raise DocumentFieldTypeError('Field value must be int type.')

        if self.min_value is not None and value < self.min_value:
            raise DocumentFieldValueError("Field value must >= 'min_value'.")

        if self.max_value is not None and value > self.max_value:
            raise DocumentFieldValueError("Field value must <= 'max_value'.")

        return True

    def to_bson(self, value=None):
        if value is None:
            return self.default
        return int(value)
