# !/usr/bin/python
# -*- coding:utf-8 -*-

from motorengine import BaseDocument
from motorengine.errors import DocumentFieldValidateError
from motorengine.stages.base_stage import BaseStage


class UnwindStage(BaseStage):
    def __init__(self, path, include_array_index='', preserve_null_and_empty_arrays=True):
        self.path = path
        self.include_array_index = include_array_index
        self.preserve_null_and_empty_arrays = preserve_null_and_empty_arrays

    def to_query(self) -> dict:
        if not (self.include_array_index and self.preserve_null_and_empty_arrays):
            query = {
                '$unwind': '$%s' % self.path
            }
        else:
            query = {
                '$unwind': {
                    'path': '$%s' % self.path,
                    'includeArrayIndex': self.include_array_index,
                    'preserveNullAndEmptyArrays': self.preserve_null_and_empty_arrays
                }
            }
        return query

    def adapt(self, metaclass: BaseDocument = None):
        if metaclass:
            self.path = metaclass.get_db_field(self.path)

    def validate(self, metaclass: BaseDocument = None):
        if not isinstance(self.include_array_index, str):
            raise ValueError("'include_array_index' must be a str.")
        if not isinstance(self.preserve_null_and_empty_arrays, bool):
            raise ValueError("'preserve_null_and_empty_arrays' must be a bool.")
        return True
