# !/usr/bin/python
# -*- coding:utf-8 -*-


from bson import DEFAULT_CODEC_OPTIONS
from motor import version
from motor.core import AgnosticClient, AgnosticBaseProperties, AgnosticDatabase, AgnosticCommandCursor, \
    AgnosticCollection, AgnosticCursor, AgnosticLatentCommandCursor, AgnosticChangeStream, AgnosticClientSession, \
    _LatentCursor
from motor.frameworks import asyncio
from motor.metaprogramming import create_class_with_framework, AsyncRead, motor_coroutine, unwrap_args_session, \
    unwrap_kwargs_session
from pymongo import MongoClient, ASCENDING, DESCENDING, WriteConcern, ReadPreference
from pymongo.change_stream import ChangeStream
from pymongo.client_session import ClientSession
from pymongo.collection import Collection
from pymongo.command_cursor import CommandCursor, RawBatchCommandCursor
from pymongo.cursor import Cursor, CursorType, RawBatchCursor
from pymongo.database import Database
from pymongo.driver_info import DriverInfo
from pymongo.errors import InvalidOperation, CollectionInvalid, ConfigurationError

ASC = ASCENDING
DESC = DESCENDING


class FacadeO(dict):
    """
    用于封装数据库查询结果集，不建议自己调用
    """

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    # def __setattr__(self, name, value):
    #     raise AttributeError("FacadeO cannot allowed update use 'SET'.")

    def __delattr__(self, name):
        raise AttributeError("FacadeO attribute cannot allowed delete.")

    def __setitem__(self, name, value):
        raise AttributeError("FacadeO cannot allowed update.")

    def __delitem__(self, name):
        raise AttributeError("FacadeO attribute cannot allowed delete.")

    def get(self, name, default=None):
        raise AttributeError("FacadeO no attribute 'GET'.")

    def pop(self, name, default=None):
        raise AttributeError("FacadeO attribute cannot allowed pop.")

    def popitem(self):
        raise AttributeError("FacadeO attribute cannot allowed pop.")

    def __missing__(self, name):
        raise AttributeError("FacadeO no attribute '%s'." % name)

    def update(self, E=None, **F):
        raise AttributeError("FacadeO cannot allowed update.")

    @property
    def oid(self):
        if hasattr(self, '_id'):
            return str(self._id)
        raise AttributeError("FacadeO no attribute '_id'.")


class MotorEngineClient(AgnosticClient):
    __motor_class_name__ = 'MotorEngineClient'
    __delegate_class__ = MongoClient

    def __init__(self, *args, **kwargs):
        # 设置缓存属性
        if 'cached_option' in kwargs:
            self.cached_option = kwargs.pop('cached_option')
        if 'io_loop' in kwargs:
            io_loop = kwargs.pop('io_loop')
            self._framework.check_event_loop(io_loop)
        else:
            io_loop = self._framework.get_event_loop()

        kwargs.setdefault('connect', False)
        kwargs.setdefault('driver', DriverInfo('Motor', version, self._framework.platform_info()))

        delegate = self.__delegate_class__(*args, **kwargs)
        super(AgnosticBaseProperties, self).__init__(delegate)
        self.io_loop = io_loop

    def get_io_loop(self):
        return self.io_loop

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(
                "%s has no attribute %r. To access the %s database, use client['%s']." % (
                    self.__class__.__name__, name, name, name))
        return self[name]

    def __getitem__(self, name):
        db_class = create_class_with_framework(MotorEngineDatabase, self._framework, self.__module__)
        return db_class(self, name)

    def wrap(self, obj):
        if obj.__class__ == Database:
            db_class = create_class_with_framework(MotorEngineDatabase, self._framework, self.__module__)
            return db_class(self, obj.name, _delegate=obj)
        elif obj.__class__ == CommandCursor:
            command_cursor_class = create_class_with_framework(AgnosticCommandCursor, self._framework, self.__module__)
            return command_cursor_class(obj, self)
        elif obj.__class__ == ClientSession:
            session_class = create_class_with_framework(AgnosticClientSession, self._framework, self.__module__)
            return session_class(obj, self)


class MotorEngineDatabase(AgnosticDatabase):
    __motor_class_name__ = 'MotorEngineDatabase'
    __delegate_class__ = Database

    def __init__(self, client, name, **kwargs):
        self._client = client
        delegate = kwargs.get('_delegate') or Database(client.delegate, name, **kwargs)

        super(AgnosticBaseProperties, self).__init__(delegate)

    @property
    def client(self):
        return self._client

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError("%s has no attribute %r. To access the %s collection, use database['%s']." % (
                self.__class__.__name__, name, name, name))
        return self[name]

    def __getitem__(self, name):
        collection_class = create_class_with_framework(MotorEngineCollection, self._framework, self.__module__)
        return collection_class(self, name)

    def __call__(self, *args, **kwargs):
        database_name = self.delegate.name
        client_class_name = self._client.__class__.__name__
        if database_name == 'open_sync':
            raise TypeError("%s.open_sync() is unnecessary Motor 0.2, see changelog for details." % client_class_name)

        raise TypeError("MotorEngineDatabase object is not callable. "
                        "If you meant to call the '%s' method on a %s object "
                        "it is failing because no such method exists." % (database_name, client_class_name))

    def wrap(self, collection):
        cls = create_class_with_framework(MotorEngineCollection, self._framework, self.__module__)
        return cls(self, collection.name, _delegate=collection)

    def get_io_loop(self):
        return self._client.get_io_loop()


class MotorEngineCollection(AgnosticCollection):
    __motor_class_name__ = 'MotorEngineCollection'
    __delegate_class__ = Collection

    _async_aggregate = AsyncRead(attr_name='aggregate')
    _async_aggregate_raw_batches = AsyncRead(attr_name='aggregate_raw_batches')
    _async_list_indexes = AsyncRead(attr_name='list_indexes')

    def __init__(self, database, name, codec_options=None, read_preference=None, write_concern=None, read_concern=None,
                 _delegate=None):
        db_class = create_class_with_framework(MotorEngineDatabase, self._framework, self.__module__)

        if not isinstance(database, db_class):
            raise TypeError("First argument to MotorEngineCollection must be MotorEngineDatabase, not %r" % database)

        delegate = _delegate or Collection(
            database.delegate, name, codec_options=codec_options, read_preference=read_preference,
            write_concern=write_concern, read_concern=read_concern)

        super(AgnosticBaseProperties, self).__init__(delegate)
        self.database = database

    def __getattr__(self, name):
        if name.startswith('_'):
            full_name = "%s.%s" % (self.name, name)
            raise AttributeError(
                "%s has no attribute %r. To access the %s collection, use database['%s']." % (
                    self.__class__.__name__, name, full_name, full_name))
        return self[name]

    def __getitem__(self, name):
        collection_class = create_class_with_framework(MotorEngineCollection, self._framework, self.__module__)
        return collection_class(self.database, self.name + '.' + name)

    def __call__(self, *args, **kwargs):
        raise TypeError(
            "MotorEngineCollection object is not callable. "
            "If you meant to call the '%s' method on a MotorCollection object "
            "it is failing because no such method exists." % self.delegate.name)

    def find(self, *args, **kwargs):
        if 'callback' in kwargs:
            raise InvalidOperation("Pass a callback to each, to_list, or count, not to find.")

        cursor = self.delegate.find(*unwrap_args_session(args), **unwrap_kwargs_session(kwargs))
        cursor_class = create_class_with_framework(MotorEngineCursor, self._framework, self.__module__)

        return cursor_class(cursor, self)

    def aggregate(self, pipeline, **kwargs):
        cursor_class = create_class_with_framework(MotorEngineLatentCommandCursor, self._framework, self.__module__)
        return cursor_class(self, self._async_aggregate, pipeline, **unwrap_kwargs_session(kwargs))

    def watch(self, pipeline=None, full_document='default', resume_after=None,
              max_await_time_ms=None, batch_size=None, collation=None,
              start_at_operation_time=None, session=None):
        cursor_class = create_class_with_framework(AgnosticChangeStream, self._framework, self.__module__)
        return cursor_class(self, pipeline, full_document, resume_after, max_await_time_ms, batch_size, collation,
                            start_at_operation_time, session)

    def list_indexes(self, session=None):
        cursor_class = create_class_with_framework(AgnosticLatentCommandCursor, self._framework, self.__module__)
        return cursor_class(self, self._async_list_indexes, session=session)

    def wrap(self, obj):
        if obj.__class__ is Collection:
            return self.__class__(self.database, obj.name, _delegate=obj)
        elif obj.__class__ is Cursor:
            return MotorEngineCursor(obj, self)
        elif obj.__class__ is CommandCursor:
            command_cursor_class = create_class_with_framework(AgnosticCommandCursor, self._framework, self.__module__)
            return command_cursor_class(obj, self)
        elif obj.__class__ is ChangeStream:
            change_stream_class = create_class_with_framework(AgnosticChangeStream, self._framework, self.__module__)
            return change_stream_class(obj, self)
        else:
            return obj

    def get_io_loop(self):
        return self.database.get_io_loop()


class MotorEngineCursor(AgnosticCursor):
    __motor_class_name__ = 'MotorEngineCursor'
    __delegate_class__ = Cursor

    _Cursor__die = AsyncRead()

    def rewind(self):
        """Rewind this cursor to its unevaluated state."""
        self.delegate.rewind()
        self.started = False
        return self

    def clone(self):
        """Get a clone of this cursor."""
        return self.__class__(self.delegate.clone(), self.collection)

    def next_object(self):
        if not self._buffer_size():
            return None
        return _query_result_2_object(
            self.collection.mapping_class if hasattr(self.collection, 'mapping_class') else None, next(self.delegate))

    def _to_list(self, length, the_list, to_list_future, get_more_result):
        try:
            result = get_more_result.result()
            collection = self.collection
            fix_outgoing = collection.database.delegate._fix_outgoing

            if length is None:
                n = result
            else:
                n = min(length, result)

            mapping_class = self.collection.mapping_class if hasattr(self.collection, 'mapping_class') else None
            for _ in range(n):
                result = _query_result_2_object(mapping_class, self._data().popleft())
                the_list.append(fix_outgoing(result, collection))

            reached_length = (length is not None and len(the_list) >= length)
            if reached_length or not self.alive:
                to_list_future.set_result(the_list)
            else:
                self._framework.add_future(
                    self.get_io_loop(), self._get_more(), self._to_list, length, the_list, to_list_future)
        except Exception as exc:
            to_list_future.set_exception(exc)

    def __copy__(self):
        return self.__class__(self.delegate.__copy__(), self.collection)

    def __deepcopy__(self, memo):
        return self.__class__(self.delegate.__deepcopy__(memo), self.collection)

    def _query_flags(self):
        return self.delegate._Cursor__query_flags

    def _data(self):
        return self.delegate._Cursor__data

    def _clear_cursor_id(self):
        self.delegate._Cursor__id = 0

    def _close_exhaust_cursor(self):
        if self.delegate._Cursor__exhaust:
            manager = self.delegate._Cursor__exhaust_mgr
            if manager.sock:
                manager.sock.close()

            manager.close()

    def _killed(self):
        return self.delegate._Cursor__killed

    @motor_coroutine
    def _close(self):
        yield self._framework.yieldable(self._Cursor__die())


class _MotorEngineLatentCursor(object):
    alive = True
    _CommandCursor__data = []
    _CommandCursor__id = None
    _CommandCursor__killed = False
    cursor_id = None

    def clone(self):
        return _MotorEngineLatentCursor()

    def rewind(self):
        pass


class MotorEngineLatentCommandCursor(AgnosticCommandCursor):
    __motor_class_name__ = 'MotorEngineLatentCommandCursor'

    def __init__(self, collection, start, *args, **kwargs):
        super(self.__class__, self).__init__(_LatentCursor(), collection)
        self.start = start
        self.args = args
        self.kwargs = kwargs

    def batch_size(self, batch_size):
        self.kwargs['batchSize'] = batch_size
        return self

    def next_object(self):
        if not self._buffer_size():
            return None
        return _query_result_2_object(
            self.collection.mapping_class if hasattr(self.collection, 'mapping_class') else None, next(self.delegate))

    def _get_more(self):
        if not self.started:
            self.started = True
            original_future = self._framework.get_future(self.get_io_loop())
            future = self.start(*self.args, **self.kwargs)
            self.start = self.args = self.kwargs = None
            self._framework.add_future(self.get_io_loop(), future, self._on_started, original_future)
            return original_future
        return super(self.__class__, self)._get_more()

    def _on_started(self, original_future, future):
        try:
            pymongo_cursor = future.result()
            self.delegate = pymongo_cursor
        except Exception as exc:
            original_future.set_exception(exc)
        else:
            if self.delegate._CommandCursor__data or not self.delegate.alive:
                original_future.set_result(len(self.delegate._CommandCursor__data))
            else:
                future = super(self.__class__, self)._get_more()
                self._framework.chain_future(future, original_future)

    def _to_list(self, length, the_list, future, get_more_result):
        try:
            result = get_more_result.result()
            collection = self.collection
            fix_outgoing = collection.database.delegate._fix_outgoing

            if length is None:
                n = result
            else:
                n = min(length, result)

            mapping_class = self.collection.mapping_class if hasattr(self.collection, 'mapping_class') else None
            for _ in range(n):
                result = _query_result_2_object(mapping_class, self._data().popleft())
                the_list.append(fix_outgoing(result, collection))

            reached_length = (length is not None and len(the_list) >= length)
            if reached_length or not self.alive:
                future.set_result(the_list)
            else:
                self._framework.add_future(
                    self.get_io_loop(), self._get_more(), self._to_list, length, the_list, future)
        except Exception as exc:
            future.set_exception(exc)


class SyncMongoClient(MongoClient):
    def __init__(self, host=None, port=None, document_class=dict, tz_aware=None, connect=None, **kwargs):
        if 'cached_option' in kwargs:
            self.cached_option = kwargs.pop('cached_option')

        super(SyncMongoClient, self).__init__(host=host, port=port, document_class=document_class, tz_aware=tz_aware,
                                              connect=connect, **kwargs)

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(
                "SyncMongoClient has no attribute %r. To access the %s database, use client[%r]." % (name, name, name))

        return self.__getitem__(name)

    def __getitem__(self, name):
        return SyncMongoDatabase(self, name)


class SyncMongoDatabase(Database):
    def __init__(self, client, name, codec_options=None, read_preference=None,
                 write_concern=None, read_concern=None):
        super(SyncMongoDatabase, self).__init__(client, name, codec_options=codec_options,
                                                read_preference=read_preference,
                                                write_concern=write_concern, read_concern=read_concern)

    def __getitem__(self, name):
        return SyncMongoCollection(self, name)

    def get_collection(self, name, codec_options=None, read_preference=None, write_concern=None, read_concern=None):
        return SyncMongoCollection(self, name, False, codec_options, read_preference, write_concern, read_concern)

    def _collection_default_options(self, name, **kargs):
        wc = (self.write_concern
              if self.write_concern.acknowledged else WriteConcern())
        return self.get_collection(
            name, codec_options=DEFAULT_CODEC_OPTIONS, read_preference=ReadPreference.PRIMARY, write_concern=wc)

    def create_collection(self, name, codec_options=None,
                          read_preference=None, write_concern=None,
                          read_concern=None, session=None, **kwargs):
        with self.__client._tmp_session(session) as s:
            if name in self.collection_names(session=s):
                raise CollectionInvalid("collection %s already exists" % name)

            return SyncMongoCollection(self, name, True, codec_options, read_preference, write_concern, read_concern,
                                       session=s, **kwargs)


class SyncMongoCollection(Collection):
    def __init__(self, db, name, create=False, codec_options=None,
                 read_preference=None, write_concern=None, read_concern=None,
                 session=None, **kwargs):
        super(SyncMongoCollection, self).__init__(db, name, create=create, codec_options=codec_options,
                                                  read_preference=read_preference, write_concern=write_concern,
                                                  read_concern=read_concern, session=session, **kwargs)
        self.__database = db
        self.__name = name

    def with_options(self, codec_options=None, read_preference=None, write_concern=None, read_concern=None):
        return SyncMongoCollection(self.__database, self.__name, False, codec_options or self.codec_options,
                                   read_preference or self.read_preference, write_concern or self.write_concern,
                                   read_concern or self.read_concern)

    def find(self, *args, **kwargs):
        return SyncMongoCursor(self, *args, **kwargs)

    def find_raw_batches(self, *args, **kwargs):
        if "session" in kwargs:
            raise ConfigurationError(
                "find_raw_batches does not support sessions")

        return SyncMongoRawBatchCursor(self, *args, **kwargs)

    def aggregate(self, pipeline, session=None, **kwargs):
        with self.__database.client._tmp_session(session, close=False) as s:
            return self._aggregate(pipeline, SyncMongoCommandCursor, kwargs.get('batchSize'), session=s,
                                   explicit_session=session is not None, **kwargs)

    def _aggregate(self, pipeline, cursor_class, first_batch_size, session,
                   explicit_session, **kwargs):
        return super(SyncMongoCollection, self)._aggregate(pipeline, cursor_class, first_batch_size, session,
                                                           explicit_session, **kwargs)

    def aggregate_raw_batches(self, pipeline, **kwargs):
        if "session" in kwargs:
            raise ConfigurationError(
                "aggregate_raw_batches does not support sessions")
        return self._aggregate(pipeline, SyncMongoRawBatchCommandCursor, 0, None, False, **kwargs)


class SyncMongoCursor(Cursor):
    def __init__(self, collection, filter=None, projection=None, skip=0, limit=0, no_cursor_timeout=False,
                 cursor_type=CursorType.NON_TAILABLE, sort=None, allow_partial_results=False, oplog_replay=False,
                 modifiers=None, batch_size=0, manipulate=True, collation=None, hint=None, max_scan=None,
                 max_time_ms=None, max=None, min=None, return_key=False, show_record_id=False, snapshot=False,
                 comment=None, session=None):
        super(SyncMongoCursor, self).__init__(collection, filter=filter, projection=projection, skip=skip,
                                              limit=limit, no_cursor_timeout=no_cursor_timeout,
                                              cursor_type=cursor_type, sort=sort,
                                              allow_partial_results=allow_partial_results,
                                              oplog_replay=oplog_replay, modifiers=modifiers, batch_size=batch_size,
                                              manipulate=manipulate, collation=collation, hint=hint, max_scan=max_scan,
                                              max_time_ms=max_time_ms, max=max, min=min, return_key=return_key,
                                              show_record_id=show_record_id, snapshot=snapshot, comment=comment,
                                              session=session)

    def __iter__(self):
        return self

    def next(self):
        return _query_result_2_object(
            self.collection.mapping_class if hasattr(self.collection, 'mapping_class') else None,
            super(SyncMongoCursor, self).next())

    def to_list(self, length):
        result_list = []
        try:
            while True:
                result_list.append(self.next())
                if length and len(result_list) == length:
                    break
        except StopIteration:
            pass
        return result_list

    __next__ = next


class SyncMongoRawBatchCursor(RawBatchCursor):
    def __init__(self, *args, **kwargs):
        super(SyncMongoRawBatchCursor, self).__init__(*args, **kwargs)

    def __iter__(self):
        return self

    def next(self):
        return _query_result_2_object(
            self.collection.mapping_class if hasattr(self.collection, 'mapping_class') else None,
            super(SyncMongoRawBatchCursor, self).next())

    def to_list(self, length):
        result_list = []
        try:
            while True:
                result_list.append(self.next())
                if length and len(result_list) == length:
                    break
        except StopIteration:
            pass
        return result_list


class SyncMongoCommandCursor(CommandCursor):
    def __init__(self, collection, cursor_info, address, retrieved=0, batch_size=0, max_await_time_ms=None,
                 session=None, explicit_session=False):
        super(SyncMongoCommandCursor, self).__init__(collection, cursor_info, address, retrieved=retrieved,
                                                     batch_size=batch_size, max_await_time_ms=max_await_time_ms,
                                                     session=session, explicit_session=explicit_session)
        self.collection = collection

    def __iter__(self):
        return self

    def next(self):
        return _query_result_2_object(
            self.collection.mapping_class if hasattr(self.collection, 'mapping_class') else None,
            super(SyncMongoCommandCursor, self).next())

    def to_list(self, length):
        result_list = []
        try:
            while True:
                result_list.append(self.next())
                if length and len(result_list) == length:
                    break
        except StopIteration:
            pass
        return result_list

    __next__ = next


class SyncMongoRawBatchCommandCursor(RawBatchCommandCursor):
    def __init__(self, collection, cursor_info, address, retrieved=0, batch_size=0, max_await_time_ms=None,
                 session=None, explicit_session=False):
        super(SyncMongoRawBatchCommandCursor, self).__init__(collection, cursor_info, address, retrieved=retrieved,
                                                             batch_size=batch_size, max_await_time_ms=max_await_time_ms,
                                                             session=session, explicit_session=explicit_session)

    def __iter__(self):
        return self

    def next(self):
        return _query_result_2_object(
            self.collection.mapping_class if hasattr(self.collection, 'mapping_class') else None,
            super(RawBatchCommandCursor, self).next())

    def to_list(self, length):
        result_list = []
        try:
            while True:
                result_list.append(self.next())
                if length and len(result_list) == length:
                    break
        except StopIteration:
            pass
        return result_list

    __next__ = next


def _query_result_2_object(clazz, row):
    """
    查询结果转换成对象
    :param cursor: 游标对象
    :param row: 行结果
    :return:
    """
    if clazz and isinstance(row, dict):
        obj = clazz()
        f_mappings = getattr(obj, '__mappings')
        for field_name, field_type in f_mappings.items():
            fn = field_type.db_field if field_type.db_field else field_name
            if fn in row.keys():
                setattr(obj, field_name, row.pop(fn))
            else:
                setattr(obj, field_name, field_type.to_bson())
        if row:
            for field_name, field_value in row.items():
                if isinstance(field_value, dict):
                    setattr(obj, field_name, FacadeO(field_value))
                elif isinstance(field_value, list):
                    for index, fv in enumerate(field_value):
                        if isinstance(fv, dict):
                            field_value[index] = FacadeO(fv)
                    setattr(obj, field_name, field_value)
                else:
                    setattr(obj, field_name, field_value)
        return obj
    return row


def create_asyncio_class(cls):
    return create_class_with_framework(cls, asyncio, 'motorengine.core')


AsyncIOMotorEngineClient = create_asyncio_class(MotorEngineClient)
AsyncIOMotorEngineDatabase = create_asyncio_class(MotorEngineDatabase)
AsyncIOMotorEngineCollection = create_asyncio_class(MotorEngineCollection)
AsyncIOMotorEngineCursor = create_asyncio_class(MotorEngineCursor)
AsyncIOMotorEngineLatentCommandCursor = create_asyncio_class(MotorEngineLatentCommandCursor)

SyncIOMongoClient = SyncMongoClient
SyncIOMongoDatabase = SyncMongoDatabase
SyncIOMongoCollection = SyncMongoCollection
SyncIOMongoCursor = SyncMongoCursor
SyncIOMongoRawBatchCursor = SyncMongoRawBatchCursor
SyncIOMongoCommandCursor = SyncMongoCommandCursor
SyncIOMongoRawBatchCommandCursor = SyncMongoRawBatchCommandCursor
