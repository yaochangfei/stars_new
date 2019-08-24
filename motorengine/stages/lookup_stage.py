# !/usr/bin/python
# -*- coding:utf-8 -*-

from typing import Type

from motorengine import BaseDocument, DocumentMetaclass
from motorengine.stages.base_stage import BaseStage


class LookupStage(BaseStage):

    def __init__(self, foreign: Type[BaseDocument], local_field: str = None, foreign_field: str = None,
                 as_list_name=None, let=None, pipeline=None):
        self.foreign = foreign
        self.local_field = local_field
        self.foreign_field = foreign_field
        self.let = let
        self.pipeline = pipeline
        self.as_list_name = as_list_name

    def to_query(self) -> dict:
        as_list = self.as_list_name
        from_collection = getattr(self.foreign, '__collection_name')
        if not as_list:
            as_list = '%s_list' % from_collection.lower().replace('tbl_', '')

        lookup = {
            'from': from_collection,
            'as': as_list
        }

        if self.let:
            lookup['let'] = self.let
            pipeline_list = []
            for pl in self.pipeline:
                if isinstance(pl, dict):
                    pipeline_list.append(pl)
                elif isinstance(pl, BaseStage):
                    pipeline_list.append(pl.to_query())
            lookup['pipeline'] = pipeline_list
        else:
            lookup['localField'] = self.local_field
            lookup['foreignField'] = self.foreign_field

        return {'$lookup': lookup}

    def adapt(self, metaclass: BaseDocument = None):
        if metaclass:
            self.local_field = metaclass.get_db_field(self.local_field)
        if self.foreign:
            self.foreign_field = self.foreign().get_db_field(self.foreign_field)

    def validate(self, metaclass: BaseDocument = None):
        if not isinstance(self.foreign, DocumentMetaclass):
            raise ValueError("'foreign' must be a instance Document.")
        if self.let:
            if not isinstance(self.let, dict):
                raise ValueError("'let' must be a dict.")
            if not self.pipeline or not isinstance(self.pipeline, list):
                raise ValueError("'pipeline' must be a list.")
        return True
