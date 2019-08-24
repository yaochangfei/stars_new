# !/usr/bin/python
# -*- coding:utf-8 -*-

from motorengine import BaseDocument
from motorengine.stages.base_stage import BaseStage


class SkipStage(BaseStage):
    def __init__(self, skip_num=0):
        self.skip_num = skip_num

    def to_query(self) -> dict:
        query = {
            '$skip': self.skip_num
        }
        return query

    def validate(self, metaclass: BaseDocument = None):
        if not isinstance(self.skip_num, int):
            raise ValueError("'skip_num' must be a int.")
        return True
