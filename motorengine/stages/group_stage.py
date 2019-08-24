# !/usr/bin/python
# -*- coding:utf-8 -*-


from motorengine import BaseDocument
from motorengine.stages import BaseStage


class GroupStage(BaseStage):
    def __init__(self, group_field, **kwargs):
        self.group_field = group_field
        self.kwargs = kwargs

    def to_query(self) -> dict:
        if isinstance(self.group_field, dict):
            self.kwargs['_id'] = self.group_field
        else:
            self.kwargs['_id'] = '$%s' % self.group_field
        query = {
            '$group': self.kwargs
        }
        return query

    def adapt(self, metaclass: BaseDocument = None):
        if metaclass:
            self.kwargs = metaclass.map_filter_2_field(self.kwargs)

    def validate(self, metaclass: BaseDocument = None):
        if self.group_field and not isinstance(self.group_field, (str, dict)):
            raise ValueError("'group_field' must be a str.")
        return True
