# !/usr/bin/python
# -*- coding:utf-8 -*-

from motorengine.base import BaseDocument


class BaseStage(object):

    def to_query(self):
        raise NotImplemented("Function 'to_query' not implemented.")

    def adapt(self, metaclass: BaseDocument = None):
        pass

    def validate(self, metaclass: BaseDocument = None):
        return True
