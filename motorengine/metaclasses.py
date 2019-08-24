# !/usr/bin/python
# -*- coding:utf-8 -*-
import re

from motorengine.errors import InvalidIndexError
from motorengine.fields import BaseField, ObjectIdField, StringField


class DocumentMetaclass(type):

    def __new__(mcs, name, bases, attributes):
        if name in ['BaseDocument', 'AsyncDocument', 'SyncDocument']:
            return super(DocumentMetaclass, mcs).__new__(mcs, name, bases, attributes)
        mappings = {'id': ObjectIdField(), 'cid': StringField()}
        indexes = []
        for key, val in attributes.items():
            if isinstance(val, BaseField) and not isinstance(val, ObjectIdField):
                # print('Found mapping: %s ==> %s' % (key, val))
                mappings[key] = val
        for k, v in mappings.items():
            attributes[k] = v.to_bson(v.default)
            # attributes.pop(k)
        if '_indexes' in attributes:
            _indexes = attributes.pop('_indexes')
            if isinstance(_indexes, list):
                indexes.extend(_indexes)
        # 处理父类
        if bases:
            for base in bases:
                if isinstance(base, DocumentMetaclass):
                    if hasattr(base, '__mappings'):
                        b_mappings = getattr(base, '__mappings')
                        if 'id' in b_mappings.keys():
                            b_mappings.pop('id')
                        # print('Found mapping:%s: ' % b_mappings)
                        mappings.update(b_mappings)
                    if hasattr(base, '__indexes'):
                        _indexes = getattr(base, '__indexes')
                        if isinstance(_indexes, list):
                            indexes.extend(_indexes)
        # 检查索引
        if mappings and indexes:
            mcs._check_indexes(mappings, indexes)

        attributes['__db_name'] = None
        attributes['__collection_name'] = mcs._get_collection_name(name)
        attributes['__mappings'] = mappings
        attributes['__indexes'] = indexes

        return super(DocumentMetaclass, mcs).__new__(mcs, name, bases, attributes)

    @staticmethod
    def _get_collection_name(clazz_name: str) -> str or None:
        if clazz_name:
            c_name = '_'.join(re.findall(r'[A-Z][a-z]*', ''.join([s for s in clazz_name if s.isalpha()])))
            return ('%s_%s' % ('tbl', c_name)).upper()
        return None

    @staticmethod
    def _check_indexes(mappings, indexes) -> bool:
        if isinstance(mappings, dict) and isinstance(indexes, list):
            f_keys = mappings.keys()
            for index in indexes:
                if isinstance(index, (list, tuple)):
                    if index[0] not in f_keys:
                        raise InvalidIndexError("%s not a valid field." % index[0])
                else:
                    if index not in f_keys:
                        raise InvalidIndexError("%s not a valid field." % index)

        return True
