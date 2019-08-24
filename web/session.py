# !/usr/bin/python
# -*- coding:utf-8 -*-
import hashlib
import uuid

import pickle
from pickle import UnpicklingError

from caches.redis_utils import RedisCache
from commons.common_utils import sha256, h_mac

KEY_SESSION_ID = '_session_id'
KEY_SESSION_KEY = '_session_key'


class SessionData(object):
    def __init__(self, session_id, session_key):
        self.session_id = session_id
        self.session_key = session_key
        self.__data = None

    def put(self, name, value=None):
        """
        设置值
        :param name: 键
        :param value: 值
        :return:
        """
        if not isinstance(name, str):
            raise KeyError('The parameter must be a instance of str')
        if self.__data is None:
            self.__data = {}
        self.__data[name] = value

    def get(self, name):
        """
        获取值
        :param name: 键
        :return: 值
        """
        if not isinstance(name, str):
            raise KeyError('The parameter must be a instance of str')
        if self.__data is None:
            return None
        return self.__data.get(name)

    def delete(self, name):
        if not isinstance(name, str):
            raise KeyError('The parameter must be a instance of str')
        if self.__data and name in self.__data.keys():
            del self.__data[name]

    @property
    def all_data(self):
        if self.__data:
            return self.__data
        return {}


class Session(object):
    def __init__(self, session_manager, request_handler):
        self.session_manager = session_manager
        self.request_handler = request_handler
        self.__session_data = self._get_session_data()

    def _get_session_data(self):
        data = None
        try:
            data = self.session_manager.get(self.request_handler)
        except RuntimeError:
            pass
        return data

    @property
    def session_id(self):
        return self.__session_data.session_id

    @property
    def session_key(self):
        return self.__session_data.session_key

    @property
    def all_data(self):
        return self.__session_data.all_data

    def get(self, name):
        if not isinstance(name, str):
            raise KeyError('The parameter must be a instance of str')
        return self.__session_data.get(name)

    def put(self, name, value=None):
        self.__session_data.put(name, value)
        return self

    def delete(self, name):
        self.__session_data.delete(name)
        return self

    def drop(self):
        self.session_manager.delete(self.request_handler, self.session_id)

    def save(self):
        self.session_manager.set(self.request_handler, self)


class SessionManager(object):
    def __init__(self, secret, timeout=1800):
        self.secret = secret
        self.timeout = timeout

    def _fetch(self, session_id):
        try:
            raw_data = RedisCache.get(session_id)
            if raw_data not in [None, '', 'None']:
                RedisCache.set(session_id, raw_data, self.timeout)
                return pickle.loads(raw_data)
            else:
                RedisCache.delete(session_id)
        except (TypeError, UnpicklingError):
            pass
        return {}

    def get(self, request_handler=None):
        if request_handler is None:
            session_id = None
            session_key = None
        else:
            session_id = request_handler.get_secure_cookie(KEY_SESSION_ID)
            session_key = request_handler.get_secure_cookie(KEY_SESSION_KEY)
        session_exists = True
        if session_id is None:
            session_exists = False
            hash_str = '{0}-{1}'.format(self.secret, str(uuid.uuid4()).upper())
            session_id = sha256(hash_str).encode('utf-8')
            session_key = h_mac(session_id, self.secret, hashlib.sha256).encode('utf-8')
        if session_exists:
            check_key = h_mac(session_id, self.secret, hashlib.sha256).encode('utf-8')
            if not session_key == check_key:
                raise RuntimeError('The session is illegal...')
        session = SessionData(session_id, session_key)
        if session_exists:
            session_data = self._fetch(session_id)
            for key, data in session_data.items():
                session.put(key, data)
        return session

    def set(self, request_handler, session):
        request_handler.set_secure_cookie(KEY_SESSION_ID, session.session_id)
        request_handler.set_secure_cookie(KEY_SESSION_KEY, session.session_key)
        session_data = pickle.dumps(session.all_data, pickle.HIGHEST_PROTOCOL)
        RedisCache.set(session.session_id, session_data, self.timeout)

    def delete(self, request_handler, session_id):
        request_handler.clear_cookie(KEY_SESSION_ID)
        request_handler.clear_cookie(KEY_SESSION_KEY)
        RedisCache.delete(session_id)
