# !/usr/bin/python
# -*- coding:utf-8 -*-

from motorengine import BaseDocument
from motorengine.stages import BaseStage


class LimitStage(BaseStage):
    def __init__(self, limit_num=0):
        self.limit_num = limit_num

    def to_query(self) -> dict:
        query = {
            '$limit': self.limit_num
        }
        return query

    def validate(self, metaclass: BaseDocument = None):
        if not isinstance(self.limit_num, int):
            raise ValueError("'limit_num' must be a int.")
        return True
