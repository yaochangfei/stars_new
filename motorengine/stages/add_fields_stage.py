# !/usr/bin/python
# -*- coding:utf-8 -*-


from motorengine import BaseDocument
from motorengine.stages import BaseStage


class AddFieldsStage(BaseStage):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def to_query(self) -> dict:
        query = {
            '$addFields': self.kwargs
        }
        return query

    def adapt(self, metaclass: BaseDocument = None):
        if metaclass:
            self.kwargs = metaclass.map_filter_2_field(self.kwargs)

    def validate(self, metaclass: BaseDocument = None):
        if not self.kwargs:
            raise ValueError("Please specified expression for AddFields pipeline.")
        return True
