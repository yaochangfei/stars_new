# !/usr/bin/python
# -*- coding:utf-8 -*-


class DatabaseNotRegisterError(ValueError):
    """
    数据库未注册错误
    """
    pass


class DocumentFieldRequiredError(ValueError):
    """
    文档域字段值必须错误
    """
    pass


class DocumentFieldTypeError(TypeError):
    """
    文档域字段值类型错误
    """
    pass


class DocumentFieldValueError(TypeError):
    """
    文档域字段值错误
    """
    pass


class DocumentFieldValidateError(ValueError):
    """
    文档域字段值验证不通过错误
    """
    pass


class InvalidDocumentError(Exception):
    """
    无效的数据库文档错误
    """
    pass


class InvalidIndexError(Exception):
    """
    无效的数据库文档错误
    """
    pass


class InvalidFieldError(ValueError):
    """
    无效的字段
    """
    pass
