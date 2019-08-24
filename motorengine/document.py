# !/usr/bin/python
# -*- coding:utf-8 -*-
import copy
import hashlib
import uuid

from bson import ObjectId
from logger import log_utils
from motorengine import ASC, MotorEngineDB
from motorengine.base import BaseDocument
from motorengine.cache import CacheEngine
from motorengine.errors import InvalidDocumentError
from pymongo import IndexModel, DeleteOne, ReplaceOne, UpdateOne, ReadPreference

logger = log_utils.get_logging('document', 'document.log')


class AsyncDocument(BaseDocument):

    def __init__(self, **kwargs):
        super(AsyncDocument, self).__init__(**kwargs)

    @classmethod
    def switch_async_db(cls, db_name=None):
        """
        切换数据库
        :param db_name:
        :return:
        """
        if db_name is None or (db_name and isinstance(db_name, str)):
            setattr(cls, '__db_name', db_name)

    def get_async_collection(self, read_preference=None):
        """
        获取数据库集合对象
        :return:
        """
        db = MotorEngineDB().get_database(getattr(self, '__db_name'))
        # 初始化缓存
        if CacheEngine.enable == 0:
            CacheEngine.switch_db(db)
            CacheEngine.initialize()
        # 获取连接
        collection = db[getattr(self, '__collection_name')]
        if read_preference:
            collection = collection.with_options(read_preference=read_preference)
        setattr(collection, 'mapping_class', self.__class__)
        return collection

    async def save(self, session=None, **kwargs):
        """
        保存--如果待保存Document包含属性_id，这执行更新操作，否则执行更新操作
        :param session: 会话
        :return: 已保存数据主键ID
        """

        _c = getattr(self, '__collection_name')
        if _c and _c == 'TBL_MEMBER':
            source = getattr(self, 'source')
            if source and isinstance(source, int):
                setattr(self, 'source', str(source))
                logger.info(
                    'The source of (%s) is %s, will be change type from %s to str' % (self.__class__, source, type(source)))

        save_doc = self.result_2_dict()
        oid = save_doc.get('_id')
        if oid:
            await self.get_async_collection().update_one(
                {'_id': oid}, {'$set': save_doc}, upsert=True, session=session, **kwargs)
        else:
            if '_id' in save_doc.keys():
                del save_doc['_id']
            insert_result = await self.get_async_collection().insert_one(save_doc, session=session, **kwargs)
            if insert_result:
                oid = insert_result.inserted_id
        # 清除缓存
        if self.__cached:
            CacheEngine.delete(oid)
        return oid

    @classmethod
    async def insert_many(cls, documents, custom_oid=False, session=None, **kwargs):
        """
        批量插入
        :param documents: 实现当前类的实例列表
        :param custom_oid : 是否使用对象指定的OID
        :param session: 会话
        :return: 插入数据的主键ID列表
        """
        if not isinstance(documents, (list, tuple)):
            raise TypeError("'documents' must be a list or tuple.")
        be_insert_docs = []
        for document in documents:
            if not isinstance(document, cls):
                raise ValueError("'documents' can only contain objects with type of %s" % document.__class__)
            save_dict = document.result_2_dict()
            try:
                if not custom_oid:
                    save_dict.pop('_id')
            except KeyError:
                pass
            be_insert_docs.append(save_dict)
        if be_insert_docs:
            result = await cls().get_async_collection().insert_many(be_insert_docs, session=session, **kwargs)
            if result:
                return result.inserted_ids
        return []

    async def delete(self, session=None, **kwargs):
        """
        删除
        :param session: 会话
        :return:
        """
        save_dict = self.result_2_dict()
        if '_id' not in save_dict.keys():
            raise InvalidDocumentError('Not a valid database record.')
        result = await self.get_async_collection().delete_one(
            {'_id': ObjectId(save_dict.get('_id'))}, session=session, **kwargs)
        if result and result.deleted_count == 1:
            # 清除缓存
            if self.__cached:
                CacheEngine.delete(getattr(self, 'oid'))
            return True
        return False

    @classmethod
    async def delete_by_ids(cls, ids, session=None, **kwargs):
        """
        依据ID删除记录
        :param ids: ID列表
        :param session: 会话
        :return:
        """
        if not isinstance(ids, (list, tuple)):
            raise TypeError("'ids' must be a list or tuple.")
        bulk_requests, tmp_id_list = [], []
        for oid in ids:
            tmp_id_list.append(str(oid))
            bulk_requests.append(DeleteOne({'_id': ObjectId(oid) if isinstance(oid, str) else oid}))
        if bulk_requests:
            clazz = cls()
            result = await clazz.get_async_collection().bulk_write(bulk_requests, session=session, **kwargs)
            if result:
                # 清除缓存
                if clazz.__cached:
                    CacheEngine.delete_many(tmp_id_list)
                return result.deleted_count
        return 0

    @classmethod
    def find(cls, filtered=None, read_preference=None, session=None, **kwargs):
        """
        查询&创建游标（MotorEngineCursor），参数参考Pymongo的find()
        :param filtered
        :param read_preference
        :param session: 会话
        :return: 游标
        """
        clazz = cls()
        return clazz.get_async_collection(read_preference).find(
            filter=clazz.map_filter_2_field(filtered), session=session, **kwargs)

    @classmethod
    def aggregate(cls, stage_list=None, read_preference=None, session=None, **kwargs):
        """
        管道查询，参数参考Pymongo的aggregate()
        :param stage_list:
        :param read_preference
        :param session: 会话
        :param kwargs:
        :return:
        """
        clazz = cls()
        pipelines = []
        if stage_list:
            for stage in stage_list:
                stage.validate(clazz)
                stage.adapt(clazz)
                pipelines.append(stage.to_query())
        return clazz.get_async_collection(read_preference).aggregate(
            pipeline=pipelines, session=session, **kwargs)

    @classmethod
    async def find_one(cls, filtered=None, read_preference=None, session=None, **kwargs):
        """
        查找单个Document，参数参考Pymongo的find_one()
        :param filtered: 检索条件
        :param read_preference
        :param session: 会话
        :param kwargs:
        :return:
        """
        clazz = cls()
        return clazz.result_2_obj(
            await clazz.get_async_collection(read_preference).find_one(
                filter=clazz.map_filter_2_field(filtered), session=session, **kwargs))

    @classmethod
    async def get_by_id(cls, oid, read_preference=None, session=None, **kwargs):
        """
        依据主键_id获取Document
        :param oid: 记录主键（_id）
        :param read_preference
        :param session: 会话
        :return:
        """
        if isinstance(oid, ObjectId):
            oid = str(oid)
        result, clazz = None, cls()
        if clazz.__cached:
            result = clazz.result_2_obj(CacheEngine.get(oid))
        if not result and clazz:
            result = clazz.result_2_obj(
                await clazz.get_async_collection(read_preference).find_one(
                    filter=clazz.map_filter_2_field({'_id': ObjectId(oid)}), session=session, **kwargs))
            if result and clazz.__cached:
                CacheEngine.set(oid, result)
        return result

    @classmethod
    async def get_by_cid(cls, cid, read_preference=None, session=None, **kwargs):
        """
        依据主键_id获取Document
        :param cid:
        :param read_preference:
        :param session:
        :param kwargs:
        :return:
        """
        result, clazz = None, cls()
        if clazz.__cached:
            result = clazz.result_2_obj(CacheEngine.get(cid))
        if not result and clazz:
            collection = clazz.get_async_collection(read_preference)
            if collection:
                result = clazz.result_2_obj(
                    await collection.find_one(clazz.map_filter_2_field({'cid': cid}), session=session, **kwargs))
                if result and clazz.__cached:
                    CacheEngine.set(cid, result)
        return result

    @classmethod
    async def get_or_create(cls, filtered=None, read_preference=None, session=None, **kwargs):
        """
        **DEPRECATED**
        依据参数获取或创建Document
        :param filtered: 检索条件
        :param read_preference:
        :param session:
        :param kwargs:
        :return:
        """
        clazz = cls()
        collection = clazz.get_async_collection(read_preference)
        if collection:
            clazz.map_filter_2_field(filtered)
            bean = await clazz.find_one(filtered, session=session, **kwargs)
            if not bean:
                replacement = copy.deepcopy(filtered)
                if '_id' in replacement.keys():
                    replacement.pop('_id')
                if 'cid' not in replacement.keys():
                    replacement['cid'] = hashlib.md5(str(uuid.uuid1()).encode('utf-8')).hexdigest().upper()
                return await clazz.get_by_id(
                    (await collection.insert_one(replacement, session=session)).inserted_id, session=session)
            return bean
        return None

    @classmethod
    async def count(cls, filtered=None, read_preference=None, session=None, **kwargs) -> int:
        """
        统计数量
        :param filtered: 检索条件
        :param read_preference
        :param session: 会话
        :param kwargs:
        :return:
        """
        clazz = cls()
        return await clazz.get_async_collection(read_preference).count_documents(
            filter=clazz.map_filter_2_field(filtered), session=session, **kwargs)

    @classmethod
    async def distinct(cls, key, filtered=None, read_preference=None, session=None, **kwargs) -> list:
        """
        依据KEY去重
        :param key: 去重字段
        :param filtered: 筛选条件
        :param read_preference
        :param session: 会话
        :return:
        """
        clazz = cls()
        fields_mapping = clazz.field_mappings
        if key in fields_mapping.keys():
            field_type = fields_mapping[key]
            key = field_type.db_field if field_type.db_field else key
        return await clazz.get_async_collection(read_preference).distinct(
            key, filter=clazz.map_filter_2_field(filtered), session=session, **kwargs)

    @classmethod
    async def delete_many(cls, filtered, session=None, **kwargs) -> int:
        """
        删除多条记录
        :param filtered: 筛选条件
        :param session: 会话
        :return:
        """
        if not filtered:
            raise ValueError('Lack filter conditions, please specified.')
        clazz = cls()
        t_filtered = clazz.map_filter_2_field(filtered)
        oid_list = []
        if clazz.__cached:
            oid_list = [str(oid) for oid in await clazz.distinct('_id', t_filtered)]
        result = await clazz.get_async_collection().delete_many(filter=t_filtered, session=session, **kwargs)
        if result:
            if clazz.__cached:
                CacheEngine.delete_many(list(oid_list))
            return result.deleted_count
        return 0

    @classmethod
    async def update_many(cls, requests, session=None, **kwargs):
        """
        批量更新
        :param requests: 操作请求
        :param session: 会话
        :return:
        """
        if not requests:
            raise ValueError('Lack requests, please specified.')
        for request in requests:
            if not isinstance(request, (UpdateOne, ReplaceOne)):
                raise TypeError("'requests' value must be instance ReplaceOne.")
        clazz = cls()
        result = await clazz.get_async_collection().bulk_write(requests, session=session, **kwargs)
        if result:
            if clazz.__cached:
                obj_list = await clazz.get_async_collection().aggregate([
                    {'$match': {'$or': [request._filter for request in requests]}},
                    {'$group': {'_id': '$_id'}}]).to_list(None)
                CacheEngine.delete_many(list([obj.id for obj in obj_list]))
            return result.modified_count
        return 0

    @classmethod
    async def update_many_by_filtered(cls, filtered: dict = None, update: dict = None, force: bool = False,
                                      session=None, **kwargs):
        """更新多个文档

        :param filtered: 筛选条件
        :param update:   更新操作 $set, $unset, $rename
                         参考: https://docs.mongodb.com/manual/reference/operator/update/
        :param force     由于filtered == {} 时,将会更新整个数据表, 属于高危操作,
                         因此限制只有在使用force设置时,才允许更新, 要求使用者必须清楚自己的操作
        :param session:  会话
        :param kwargs:   可使用的其他参数
                         upsert=False, array_filters=None,
                         bypass_document_validation=False, collation=None
        :return:
        """
        if not update:
            return 0

        if filtered is {} and not force:
            # 尝试更新整个数据表, 确未指定强制操作时返回0
            return 0

        clazz = cls()
        filter = clazz.map_filter_2_field(filtered)
        update = clazz.map_filter_2_field(update)
        result = await clazz.get_async_collection().update_many(filter, update, session=session, **kwargs)
        if result:
            if clazz.__cached:
                oid_list = await clazz.get_async_collection(read_preference=ReadPreference.PRIMARY) \
                    .distinct('_id', filter, session)
                CacheEngine.delete_many(oid_list)
            return result.modified_count
        return 0

    @classmethod
    async def create_indexes(cls, session=None, **kwargs):
        """
        创建索引
        :param session: 会话
        :return: 索引名称列表
        """
        if hasattr(cls, '__indexes'):
            clazz = cls()
            indexes = getattr(clazz, '__indexes')
            if isinstance(indexes, list):
                index_list = clazz.__create_indexes_structure(indexes)
                index_model_list = []
                for index in index_list:
                    if isinstance(index, list):
                        index_model_list.append(IndexModel(index))
                    else:
                        index_model_list.append(IndexModel([index]))
                if index_model_list:
                    return await clazz.get_async_collection().create_indexes(
                        index_model_list, session=session, **kwargs)
        return []

    def __create_indexes_structure(self, indexes):
        """
        解析并创建索引结构
        :param indexes: 书写的索引结构
        :return:
        """
        if isinstance(indexes, str):
            return self.get_db_field(indexes), ASC
        if isinstance(indexes, tuple):
            index_field = self.get_db_field(indexes[0])
            sort_way = ASC
            if len(indexes) > 1:
                sort_way = indexes[1]
            return index_field, sort_way
        if isinstance(indexes, list):
            index_tuple_list = []
            for index in indexes:
                index_tuple_list.append(self.__create_indexes_structure(index))
            return index_tuple_list

    @classmethod
    def client(cls):
        """
        顺序操作的会话
        :return:
        """
        return MotorEngineDB().client(async=True)

    @property
    def __cached(self):
        return CacheEngine.enable == 1


class SyncDocument(BaseDocument):

    def __init__(self, **kwargs):
        super(SyncDocument, self).__init__(**kwargs)

    @classmethod
    def switch_sync_db(cls, db_name=None):
        """
        切换数据库（数据库必须已注册）
        :param db_name:
        :return:
        """
        if db_name is None or (db_name and isinstance(db_name, str)):
            setattr(cls, '__db_name', db_name)

    def get_sync_collection(self, read_preference=None):
        """
        获取集合对象
        :return:
        """
        db = MotorEngineDB().get_database(getattr(self, '__db_name'), async=False)
        # 初始化缓存
        if CacheEngine.enable == 0:
            CacheEngine.switch_db(db)
            CacheEngine.initialize()

        collection = db[getattr(self, '__collection_name')]
        if read_preference:
            collection = collection.with_options(read_preference=read_preference)
        setattr(collection, 'mapping_class', self.__class__)
        return collection

    def sync_save(self, session=None, **kwargs):
        """
        保存--如果待保存Document包含属性_id，这执行更新操作，否则执行更新操作
        :return: 已保存数据主键ID
        """
        save_doc = self.result_2_dict()
        oid = save_doc.get('_id')
        if oid:
            self.get_sync_collection().update_one(
                {'_id': oid}, {'$set': save_doc}, upsert=True, session=session, **kwargs)
        else:
            if '_id' in save_doc.keys():
                del save_doc['_id']
            insert_result = self.get_sync_collection().insert_one(save_doc, session=session, **kwargs)
            if insert_result:
                oid = insert_result.inserted_id
        # 清除缓存
        if self.__cached:
            CacheEngine.delete(oid)
        return oid

    @classmethod
    def sync_insert_many(cls, documents, custom_oid=False, session=None, **kwargs):
        """
        批量插入
        :param documents: 实现当前类的实例列表
        :param custom_oid : 是否使用对象指定的OID
        :param session: 会话
        :return: 插入数据的主键ID列表
        """
        if not isinstance(documents, (list, tuple)):
            raise TypeError("'documents' must be a list or tuple.")
        be_insert_docs = []
        for document in documents:
            if not isinstance(document, cls):
                raise ValueError("'documents' can only contain objects with type of %s" % document.__class__)
            save_dict = document.result_2_dict()
            try:
                if not custom_oid:
                    save_dict.pop('_id')
            except KeyError:
                pass
            be_insert_docs.append(save_dict)
        if be_insert_docs:
            result = cls().get_sync_collection().insert_many(be_insert_docs, session=session, **kwargs)
            if result:
                return result.inserted_ids
        return []

    def sync_delete(self, session=None, **kwargs):
        """
        删除
        :return:
        """
        save_dict = self.result_2_dict()
        if '_id' not in save_dict.keys():
            raise InvalidDocumentError('Not a valid database record.')
        result = self.get_sync_collection().delete_one(
            {'_id': ObjectId(save_dict.get('_id'))}, session=session, **kwargs)
        if result and result.deleted_count == 1:
            # 清除缓存
            if self.__cached:
                CacheEngine.delete(getattr(self, 'oid'))
            return True
        return False

    @classmethod
    def sync_delete_by_ids(cls, ids, session=None, **kwargs):
        if not isinstance(ids, (list, tuple)):
            raise TypeError("'ids' must be a list or tuple.")
        bulk_requests, tmp_oid_list = [], []
        for oid in ids:
            bulk_requests.append(DeleteOne({'_id': ObjectId(oid) if isinstance(oid, str) else oid}))
            tmp_oid_list.append(str(oid))
        if bulk_requests:
            clazz = cls()
            result = clazz.get_sync_collection().bulk_write(bulk_requests, session=session, **kwargs)
            if result:
                # 清除缓存
                if clazz.__cached:
                    CacheEngine.delete_many(tmp_oid_list)
                return result.deleted_count
        return 0

    @classmethod
    def sync_find(cls, filtered=None, read_preference=None, session=None, **kwargs):
        """
        查询&创建游标（MotorEngineCursor），参数参考PyMongo的find()
        :param kwargs:
        :param filtered
        :param read_preference
        :param session: 会话
        :return: 游标
        """
        clazz = cls()
        return clazz.get_sync_collection(read_preference).find(
            clazz.map_filter_2_field(filtered), session=session, **kwargs)

    @classmethod
    def sync_aggregate(cls, stage_list=None, read_preference=None, session=None, **kwargs):
        clazz, pipelines = cls(), []
        if stage_list:
            for stage in stage_list:
                stage.validate(clazz)
                stage.adapt(clazz)
                pipelines.append(stage.to_query())
        return clazz.get_sync_collection(read_preference).aggregate(pipelines, session=session, **kwargs)

    @classmethod
    def sync_find_one(cls, filtered=None, read_preference=None, session=None, **kwargs):
        """
        查找单个Document，参数参考Pymongo的find_one()
        :param filtered: 检索条件
        :param read_preference
        :param session: 会话
        :param kwargs:
        :return:
        """
        clazz = cls()
        return clazz.result_2_obj(
            clazz.get_sync_collection(read_preference).find_one(
                clazz.map_filter_2_field(filtered), session=session, **kwargs))

    @classmethod
    def sync_get_by_id(cls, oid, read_preference=None, session=None, **kwargs):
        """
        依据主键_id获取Document
        :param oid: 记录主键（_id）
        :param read_preference
        :param session: 会话
        :return:
        """
        if isinstance(oid, ObjectId):
            oid = str(oid)
        result, clazz = None, cls()
        if clazz.__cached:
            result = clazz.result_2_obj(CacheEngine.get(oid))
        if not result and clazz:
            result = clazz.result_2_obj(
                clazz.get_sync_collection(read_preference).find_one(
                    clazz.map_filter_2_field({'_id': ObjectId(oid)}), session=session, **kwargs))
            if result and clazz.__cached:
                CacheEngine.set(oid, result)
        return result

    @classmethod
    def sync_get_by_cid(cls, cid, read_preference=None, session=None, **kwargs):
        """
        依据主键_id获取Document
        :param cid: 记录主键（cid）
        :param read_preference:
        :param session:
        :param kwargs
        :return:
        """
        result, clazz = None, cls()
        if clazz.__cached:
            result = clazz.result_2_obj(CacheEngine.get(cid))
        if not result and clazz:
            collection = clazz.get_sync_collection(read_preference)
            if collection:
                result = clazz.result_2_obj(
                    collection.find_one(clazz.map_filter_2_field({'cid': cid}), session=session, **kwargs))
                if result and clazz.__cached:
                    CacheEngine.set(cid, result)
        return result

    @classmethod
    def sync_get_or_create(cls, filtered=None, read_preference=None, session=None, **kwargs):
        """
        依据参数获取或创建Document
        :param filtered: 检索条件
        :param read_preference:
        :param session:
        :param kwargs:
        :return:
        """
        clazz = cls()
        collection = clazz.get_sync_collection(read_preference)
        if collection:
            clazz.map_filter_2_field(filtered)
            bean = clazz.sync_find_one(filtered, session=session, **kwargs)
            if not bean:
                replacement = copy.deepcopy(filtered)
                if '_id' in replacement.keys():
                    replacement.pop('_id')
                if 'cid' not in replacement.keys():
                    replacement['cid'] = hashlib.md5(str(uuid.uuid1()).encode('utf-8')).hexdigest().upper()
                return clazz.sync_get_by_id(collection.insert_one(replacement, session=session).inserted_id,
                                            session=session)
            return bean
        return None

    @classmethod
    def sync_count(cls, filtered=None, read_preference=None, session=None, **kwargs) -> int:
        """
        统计数量，参数参考Pymongo的count_documents()
        :param filtered: 检索条件
        :param read_preference
        :param session: 会话
        :param kwargs:
        :return:
        """
        clazz = cls()
        return clazz.get_sync_collection(read_preference).count_documents(
            clazz.map_filter_2_field(filtered), session=session, **kwargs)

    @classmethod
    def sync_distinct(cls, key, filtered=None, read_preference=None, session=None, **kwargs) -> list:
        """
        依据KEY去重
        :param key:
        :param filtered:
        :param read_preference
        :param session: 会话
        :param kwargs:
        :return:
        """
        clazz = cls()
        fields_mapping = clazz.field_mappings
        if key in fields_mapping.keys():
            field_type = fields_mapping[key]
            if field_type:
                key = field_type.db_field if field_type.db_field else key
        return clazz.get_sync_collection(read_preference).distinct(
            key, clazz.map_filter_2_field(filtered), session=session, **kwargs)

    @classmethod
    def sync_delete_many(cls, filtered, session=None, **kwargs) -> int:
        if not filtered:
            raise ValueError('Lack filter conditions, please specified.')
        clazz = cls()
        t_filtered = clazz.map_filter_2_field(filtered)
        oid_list = []
        if clazz.__cached:
            oid_list = [str(oid) for oid in clazz.sync_distinct('_id', t_filtered)]
        result = clazz.get_sync_collection().delete_many(t_filtered, session=session, **kwargs)
        if result:
            if clazz.__cached:
                CacheEngine.delete_many(list(oid_list))
            return result.deleted_count
        return 0

    @classmethod
    def sync_update_many(cls, requests, session=None, **kwargs):
        if not requests:
            raise ValueError('Lack requests, please specified.')
        for request in requests:
            if not isinstance(request, (UpdateOne, ReplaceOne)):
                raise TypeError("'requests' value must be instance ReplaceOne.")
        clazz = cls()
        result = clazz.get_sync_collection().bulk_write(requests, session=session, **kwargs)
        if result:
            upserted_ids = result.upserted_ids
            if clazz.__cached:
                CacheEngine.delete_many(list([str(oid) for oid in upserted_ids]))
            return result.modified_count
        return 0

    @classmethod
    def sync_update_many_by_filtered(cls, filtered: dict = None, update: dict = None, force: bool = False,
                                     session=None, **kwargs):
        """更新多个文档

        :param filtered: 筛选条件
        :param update:   更新操作 $set, $unset, $rename
                         参考: https://docs.mongodb.com/manual/reference/operator/update/
        :param force     由于filtered == {} 时,将会更新整个数据表, 属于高危操作,
                         因此限制只有在使用force设置时,才允许更新, 要求使用者必须清楚自己的操作
        :param session:  会话
        :param kwargs:   可使用的其他参数
                         upsert=False, array_filters=None,
                         bypass_document_validation=False, collation=None
        :return:
        """
        if not update:
            return 0

        if filtered is {} and not force:
            # 尝试更新整个数据表, 确未指定强制操作时返回0
            return 0

        clazz = cls()
        filter = clazz.map_filter_2_field(filtered)
        update = clazz.map_filter_2_field(update)
        result = clazz.get_sync_collection().update_many(filter, update, session=session, **kwargs)
        if result:
            if clazz.__cached:
                oid_list = clazz.get_sync_collection(read_preference=ReadPreference.PRIMARY) \
                    .distinct('_id', filter, session)
                CacheEngine.delete_many(oid_list)
            return result.modified_count
        return 0

    @classmethod
    def sync_create_indexes(cls, session=None, **kwargs):
        """
        创建索引
        :return: 索引名称列表
        """
        if hasattr(cls, '__indexes'):
            clazz = cls()
            indexes = getattr(clazz, '__indexes')
            if isinstance(indexes, list):
                index_list = clazz.__create_indexes_structure(indexes)
                index_model_list = []
                for index in index_list:
                    if isinstance(index, list):
                        index_model_list.append(IndexModel(index))
                    else:
                        index_model_list.append(IndexModel([index]))
                if index_model_list:
                    return clazz.get_sync_collection().create_indexes(index_model_list, session=session, **kwargs)
        return []

    def __create_indexes_structure(self, indexes):
        """
        解析并创建索引结构
        :param indexes: 书写的索引结构
        :return:
        """
        if isinstance(indexes, str):
            return self.get_db_field(indexes), ASC
        if isinstance(indexes, tuple):
            index_field = self.get_db_field(indexes[0])
            sort_way = ASC
            if len(indexes) > 1:
                sort_way = indexes[1]
            return index_field, sort_way
        if isinstance(indexes, list):
            index_tuple_list = []
            for index in indexes:
                index_tuple_list.append(self.__create_indexes_structure(index))
            return index_tuple_list

    @classmethod
    def sync_client(cls):
        """
        顺序操作的会话
        :return:
        """
        return MotorEngineDB().client(async=False)

    @property
    def __cached(self):
        return CacheEngine.enable == 1
