# !/usr/bin/python
# -*- coding:utf-8 -*-
from urllib.parse import quote_plus

from motorengine import AsyncIOMotorEngineClient, DatabaseNotRegisterError, SyncIOMongoClient

_DEFAULT_DB_NAME = None
_ASYNC_DATABASES = {}
_SYNC_DATABASES = {}


def register_database(db_name, address_list, async=True, auth_db_name=None, user_name=None, password=None,
                      default=False, **options):
    """
    注册数据库
    :param db_name: 数据库名称
    :param address_list: 数据库地址列表（含端口）
    :param async: 异步操作数据
    :param auth_db_name: 用于验证用户的DB
    :param user_name: 数据库用户名
    :param password: 数据库密码
    :param default: 是否为默认数据库
    :param options: 数据库连接参数
    :return:
    """
    global _DEFAULT_DB_NAME
    global _ASYNC_DATABASES
    global _SYNC_DATABASES

    db_dict = _ASYNC_DATABASES if async else _SYNC_DATABASES
    if not db_dict.get(db_name):
        if async:
            client = AsyncIOMotorEngineClient(
                _get_connection_uri(address_list, auth_db=auth_db_name, user_name=user_name, password=password,
                                    **options), cached_option=options.get('cached_option'))
        else:
            client = SyncIOMongoClient(
                _get_connection_uri(address_list, auth_db=auth_db_name, user_name=user_name, password=password,
                                    **options), cached_option=options.get('cached_option'))
        if client:
            if default:
                _DEFAULT_DB_NAME = db_name
            database = client[db_name]
            if database:
                if async:
                    _ASYNC_DATABASES[db_name] = database
                else:
                    _SYNC_DATABASES[db_name] = database
    return True


def get_registered_databases(async=True):
    """
    获取所有已注册数据库
    :param async: 异步操作数据库
    :return:
    """
    if async:
        return _ASYNC_DATABASES
    return _SYNC_DATABASES


def get_database(db_name=None, async=True):
    """
    获取数据库连接
    :param db_name: 数据库名称
    :param async: 异步操作数据库
    :return: db_name为空返回默认数据库
    """
    _db_name = db_name if db_name else _DEFAULT_DB_NAME
    if async:
        db = _ASYNC_DATABASES.get(_db_name)
    else:
        db = _SYNC_DATABASES.get(_db_name)
    if not db:
        raise DatabaseNotRegisterError('Database %s unregistered.' % _db_name)
    return db


def get_default_database_name():
    """
    获取默认数据库名
    :return:
    """
    return _DEFAULT_DB_NAME


def is_register(db_name=None, async=True):
    """
    数据库是否已经注册
    :param db_name:
    :param async:
    :return:
    """
    try:
        if get_database(db_name=db_name, async=async):
            return True
    except DatabaseNotRegisterError:
        pass
    return False


def _get_connection_uri(address_list, auth_db=None, user_name=None, password=None, **options):
    """
    获取数据库连接URI
    :param address_list: 数据库地址列表
    :param auth_db: 检验数据库
    :param user_name: 数据库用户名
    :param password: 数据库密码
    :param options: 连接选项(https://docs.mongodb.com/manual/reference/connection-string/#connections-connection-options)
    :return:
    """
    c_uri = None
    if address_list:
        if not options.get('replicaSet'):
            options.pop('replicaSet')
        if len(address_list) > 1 and not options.get('replicaSet'):
            raise ValueError('replicaSet must be include in parameter options .')
        address_comp = _get_address_component(address_list)
        options_comp = _get_options_component(options)
        if not auth_db and user_name and password:
            auth_db = 'admin'
        if auth_db:
            auth_comp = _get_auth_component(user_name, password)
            c_uri = 'mongodb://%s%s/%s%s' % (auth_comp, address_comp, auth_db, options_comp)
        else:
            c_uri = 'mongodb://%s/%s' % (address_comp, options_comp)
    return c_uri


def _get_auth_component(user_name=None, password=None):
    """
    获取数据库校验位
    :param user_name: 用户名
    :param password: 密码
    :return: 字符串
    """
    if (user_name and not password) or (not user_name and password):
        raise ValueError('Both user_name and password must be empty or not empty at the same time.')
    if user_name and password:
        if not isinstance(user_name, str) or not isinstance(password, str):
            raise ValueError('Both user_name and password must be instance of str.')
        return '%s:%s@' % (quote_plus(user_name), quote_plus(password))
    return ''


def _get_address_component(address_list):
    """
    获取数据库服务器地址位
    :param address_list: 数据库服务器地址列表
    :return:
    """
    address_component = '127.0.0.1:27017'
    if address_list:
        address_component = ','.join(address_list)
    return address_component


def _get_options_component(options):
    """
    获取数据库连接选项位
    :param options: 数据库连接参数
    :return:
    """
    options_component = ''
    if options:
        for key, val in options.items():
            if not key == 'cached_option':
                options_component += "%s=%s&" % (key, val)
        options_component = '?' + options_component[:-1]
    return options_component
