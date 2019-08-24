# !/usr/bin/python
# -*- coding:utf-8 -*-

from motorengine.stages.base_stage import BaseStage


class CountStage(BaseStage):

    def to_query(self) -> dict:
        query = {
            '$count': 'count'
        }
        return query
