# !/usr/bin/python
# -*- coding:utf-8 -*-

from motorengine import ASC, DESC, BaseDocument
from motorengine.stages.base_stage import BaseStage


class SortStage(BaseStage):
    def __init__(self, sort_tuple_list):
        self.sorts = sort_tuple_list

    def to_query(self) -> dict:
        query = {
            '$sort': self.__to_sort_dict()
        }
        return query

    def __to_sort_dict(self):
        sort_dict = {}
        for sort_tuple in self.sorts:
            if sort_tuple:
                sort_key = sort_tuple[0]
                sort_type = ASC
                if len(sort_tuple) > 1:
                    sort_type = sort_tuple[1]
                    if sort_type not in [ASC, DESC]:
                        sort_type = ASC
                sort_dict[sort_key] = sort_type
        return sort_dict

    def adapt(self, metaclass: BaseDocument = None):
        sort = []
        for sort_tuple in self.sorts:
            if sort_tuple:
                st = list(sort_tuple)
                st[0] = metaclass.get_db_field(st[0])
                sort.append(tuple(st))

    def validate(self, metaclass: BaseDocument = None):
        if not isinstance(self.sorts, list):
            raise ValueError("class SortStage's init can only accept list type parameter.")
        for sort_tuple in self.sorts:
            if not isinstance(sort_tuple, (list, tuple)):
                raise ValueError("Sort parameters only support list or tuple types.")
        return True
