# !/usr/bin/python
# -*- coding:utf-8 -*-

from motorengine import BaseDocument
from motorengine.stages.base_stage import BaseStage


class SampleStage(BaseStage):
    def __init__(self, size=1):
        self.size = size

    def to_query(self) -> dict:
        query = {
            '$sample': {
                'size': self.size
            }
        }
        return query

    def validate(self, metaclass: BaseDocument = None):
        if not isinstance(self.size, int):
            raise ValueError("'size' must be a int.")
        if self.size < 1:
            raise ValueError("'size' must be > 0.")
        return True
