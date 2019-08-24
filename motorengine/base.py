# !/usr/bin/python
# -*- coding:utf-8 -*-


import copy
import hashlib
import uuid

from bson import ObjectId

from motorengine import DocumentMetaclass
from motorengine.errors import DocumentFieldValidateError


class BaseDocument(metaclass=DocumentMetaclass):
    def __init__(self, **kwargs):
        for f_key, f_type in self.field_mappings.items():
            if kwargs and f_key in kwargs.keys():
                setattr(self, f_key, kwargs.get(f_key))
            else:
                setattr(self, f_key, copy.deepcopy(f_type.default))
        if 'id' in kwargs.keys() and not getattr(self, 'oid'):
            setattr(self, 'oid', ObjectId(kwargs.get('id')))
        setattr(self, 'cid', hashlib.md5(str(uuid.uuid1()).encode('utf-8')).hexdigest().upper())

    @property
    def oid(self):
        """
        返回字段主键(_id)字符串标识
        :return:
        """
        _id = getattr(self, 'id', None)
        if _id:
            return str(_id)
        return None

    @property
    def field_mappings(self):
        """
        获取字段映射关系
        :return:
        """
        return getattr(self, '__mappings')

    def validate_field(self):
        """
        验证域字段有效性
        :return:
        """
        mapping = self.field_mappings
        n = 0
        for field_name, field_type in mapping.items():
            if hasattr(self, field_name):
                value = getattr(self, field_name)
            else:
                value = field_type.to_bson(field_type.default)
            v = field_type.validate(value)
            if not v:
                raise DocumentFieldValidateError('Field %s value validate against.' % field_name)
            n += 1
        if n == 0:
            raise DocumentFieldValidateError('Do not contain any valid database fields.')
        return True

    def get_db_field(self, clazz_field):
        """
        依据类字段名获取数据库字段
        :param clazz_field: 类字段名
        :return:
        """
        if isinstance(clazz_field, str):
            ft = self.field_mappings.get(clazz_field)
            if ft and ft.db_field:
                return ft.db_field
        return clazz_field

    @classmethod
    def is_db_field(cls, field):
        """
        判断给予的字符串是否为数据表字段
        :param field:
        :return:
        """
        mappings = cls().field_mappings
        if field in mappings.keys():
            return True
        else:
            for field_name, field_type in mappings.items():
                if field == field_type.db_field:
                    return True
        return False

    def result_2_dict(self):
        """
        将文档转换成字典
        :return:
        """
        mapping = self.field_mappings
        if mapping and self.validate_field():
            result = {}
            for field_name, field_type in mapping.items():
                fn = field_type.db_field
                if not fn:
                    fn = field_name
                if fn == '_id':
                    if hasattr(self, field_name):
                        value = getattr(self, field_name)
                        if value:
                            result[fn] = field_type.to_bson(value)
                else:
                    if hasattr(self, field_name):
                        result[fn] = field_type.to_bson(getattr(self, field_name))
                    else:
                        result[fn] = field_type.to_bson()
            return result
        return {}

    def result_2_obj(self, result):
        """
        将文档转换成对象Model
        :param result:
        :return:
        """
        if isinstance(result, dict):
            for field_name, field_type in self.field_mappings.items():
                fn = field_type.db_field
                if not fn:
                    fn = field_name
                if result.get(fn) is None:
                    setattr(self, field_name, result.get(fn, copy.deepcopy(field_type.default)))
                else:
                    setattr(self, field_name, result.get(fn))
            return self
        return result

    def map_filter_2_field(self, filtered):
        """
        映射查询字段为数据库字段
        :param filtered:
        :return:
        """
        if isinstance(filtered, dict):
            rf_list = []
            for k, v in filtered.items():
                db_field = self.get_db_field(k)
                if not db_field == k:
                    rf_list.append((k, db_field))
            if rf_list:
                for t in rf_list:
                    filtered[t[1]] = filtered.pop(t[0])
        return filtered
