# !/usr/bin/python
# -*- coding:utf-8 -*-
from motorengine import BaseDocument
from motorengine.stages import BaseStage


class ProjectStage(BaseStage):

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.project = {}

    def to_query(self) -> dict:
        query = {
            '$project': self.project
        }
        return query

    def adapt(self, metaclass: BaseDocument = None):
        if metaclass:
            self.kwargs = metaclass.map_filter_2_field(self.kwargs)
        self.project.update(self.kwargs)

    def validate(self, metaclass: BaseDocument = None):
        return True
