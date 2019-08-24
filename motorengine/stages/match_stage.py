# !/usr/bin/python
# -*- coding:utf-8 -*-

from motorengine import BaseDocument
from motorengine.stages.base_stage import BaseStage


class MatchStage(BaseStage):
    def __init__(self, filtered: dict):
        self.match = filtered

    def to_query(self) -> dict:
        query = {
            '$match': self.match
        }
        return query

    def adapt(self, metaclass: BaseDocument = None):
        if metaclass:
            self.match = metaclass.map_filter_2_field(self.match)

    def validate(self, metaclass: BaseDocument = None):
        if not isinstance(self.match, dict):
            raise ValueError("'skip_num' must be a dict.")
        return True
