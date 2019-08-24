# !/usr/bin/python
# -*- coding:utf-8 -*-


import copy
import traceback

from bson import ObjectId
from pymongo import UpdateOne
from tornado.web import url

from actions.v_common import logger
from commons.page_utils import Paging
from db import STATUS_SUBJECT_DIMENSION_INACTIVE, STATUS_SUBJECT_DIMENSION_ACTIVE
from db.model_utils import update_subject_sub_dimension_status, do_subject_dimension
from db.models import SubjectDimension, SubjectChoiceRules
from enums import PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT
from logger import log_utils
from web import BaseHandler, decorators, datetime

logger = log_utils.get_logging()


class SubjectDimensionListViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/dimensions/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def get(self):
        query_params = {'record_flag': 1, 'parent_cid': {'$in': [None, '']}}

        sd_title = self.get_argument('sd_title', '')
        if sd_title:
            query_params['title'] = {'$regex': sd_title, '$options': 'i'}
        # 分页 START
        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s' % (
            self.reverse_url("backoffice_subject_dimension_list"), per_page_quantity)
        paging = Paging(page_url, SubjectDimension, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['ordered'], **query_params)
        await paging.pager()
        return locals()


class SubjectDimensionAddViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/dimensions/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def get(self):
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        subject_dimension_id = None
        try:
            code = self.get_argument('code', None)
            title = self.get_argument('title', None)
            category = self.get_argument('category', None)
            status = self.get_argument('status', None)  # 状态
            ordered = self.get_argument('ordered', None)
            comment = self.get_argument('comment', None)
            if code and title and category and ordered:
                c_count = await SubjectDimension.count(dict(code=code, parent_cid={'$in': [None, '']}))
                t_count = await SubjectDimension.count(dict(title=title, parent_cid={'$in': [None, '']}))
                r_count = await SubjectDimension.count(dict(ordered=int(ordered), parent_cid={'$in': [None, '']}))
                if c_count > 0:
                    r_dict['code'] = -7
                elif t_count > 0:
                    r_dict['code'] = -6
                elif r_count > 0:
                    r_dict['code'] = -5
                else:
                    if status == 'on':
                        status = STATUS_SUBJECT_DIMENSION_ACTIVE
                    else:
                        status = STATUS_SUBJECT_DIMENSION_INACTIVE
                    subject_dimension = SubjectDimension(code=code, title=title, category=int(category),
                                                         ordered=int(ordered))
                    subject_dimension.status = status
                    subject_dimension.comment = comment if comment else None
                    subject_dimension.created_id = self.current_user.oid
                    subject_dimension.updated_id = self.current_user.oid
                    subject_dimension_id = await subject_dimension.save()
                    r_dict['code'] = 1
            else:
                if not title:
                    r_dict['code'] = -1
                if not category:
                    r_dict['code'] = -2
                if not ordered:
                    r_dict['code'] = -4
        except RuntimeError:
            if subject_dimension_id:
                await SubjectDimension.delete_by_ids(subject_dimension_id)
            logger.error(traceback.format_exc())
        return r_dict


class SubjectDimensionEditViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/dimensions/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def get(self, dimension_id):
        subject_dimension = await SubjectDimension.get_by_id(dimension_id)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def post(self, dimension_id):
        r_dict = {'code': 0}
        try:
            subject_dimension = await SubjectDimension.get_by_id(dimension_id)
            code = self.get_argument('code', None)
            title = self.get_argument('title', None)
            category = self.get_argument('category', None)
            status = self.get_argument('status', None)  # 状态
            ordered = self.get_argument('ordered', None)
            comment = self.get_argument('comment', None)
            if subject_dimension and title and category and ordered:
                c_count = await SubjectDimension.count(
                    dict(code=code, id={'$ne': ObjectId(dimension_id)}, parent_cid={'$in': [None, '']}))
                t_count = await SubjectDimension.count(
                    dict(title=title, id={'$ne': ObjectId(dimension_id)}, parent_cid={'$in': [None, '']}))
                r_count = await SubjectDimension.count(
                    dict(ordered=int(ordered), id={'$ne': ObjectId(dimension_id)},
                         parent_cid={'$in': [None, '']}))
                if c_count > 0:
                    r_dict['code'] = -7
                elif t_count > 0:
                    r_dict['code'] = -6
                elif r_count > 0:
                    r_dict['code'] = -5
                else:
                    subject_dimension.code = code
                    if status == 'on':
                        status = STATUS_SUBJECT_DIMENSION_ACTIVE
                    else:
                        status = STATUS_SUBJECT_DIMENSION_INACTIVE
                    subject_dimension.title = title
                    subject_dimension.category = int(category)
                    subject_dimension.ordered = int(ordered)
                    subject_dimension.status = status
                    subject_dimension.comment = comment if comment else None
                    subject_dimension.updated_dt = datetime.datetime.now()
                    subject_dimension.updated_id = self.current_user.oid
                    await subject_dimension.save()
                    await update_subject_sub_dimension_status(self.current_user.oid, status, [subject_dimension.cid])
                    r_dict['code'] = 1
            else:
                if not title:
                    r_dict['code'] = -1
                if not category:
                    r_dict['code'] = -2
                if not ordered:
                    r_dict['code'] = -4
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectDimensionStatusSwitchViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def post(self, dimension_id):
        r_dict = {'code': 0}
        try:
            status = self.get_argument('status', False)
            if status == 'true':
                status = STATUS_SUBJECT_DIMENSION_ACTIVE
            else:
                status = STATUS_SUBJECT_DIMENSION_INACTIVE
            subject_dimension = await SubjectDimension.get_by_id(dimension_id)
            if subject_dimension:
                subject_dimension.status = status
                subject_dimension.updated = datetime.datetime.now()
                subject_dimension.updated_id = self.current_user.oid
                await subject_dimension.save()
                await update_subject_sub_dimension_status(self.current_user.oid, status, [subject_dimension.cid])
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectDimensionBatchOperateViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            subject_dimension_id_list = self.get_body_arguments('subject_dimension_id_list[]', [])
            if subject_dimension_id_list:
                operate = self.get_argument('operate', None)
                if operate is not None:
                    status = None
                    id_list = [ObjectId(subject_id) for subject_id in subject_dimension_id_list]
                    if int(operate) == 1:
                        status = STATUS_SUBJECT_DIMENSION_ACTIVE
                        update_requests = []
                        for dimension_id in subject_dimension_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(dimension_id)},
                                                             {'$set': {'status': status,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await SubjectDimension.update_many(update_requests)
                    elif int(operate) == 0:
                        status = STATUS_SUBJECT_DIMENSION_INACTIVE
                        update_requests = []
                        for dimension_id in subject_dimension_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(dimension_id)},
                                                             {'$set': {'status': status,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await SubjectDimension.update_many(update_requests)
                    elif int(operate) == -1:
                        cid_list = await SubjectDimension.distinct('cid', {'_id': {'$in': id_list},
                                                                           'parent_cid': {'$in': [None, '']}})
                        await SubjectDimension.delete_many({'_id': {'$in': id_list}})
                        await SubjectDimension.delete_many({'parent_cid': {'$in': cid_list}})
                    # 状态变更子维度也变更
                    if int(operate) in [1, 0] and status:
                        cid_list = await SubjectDimension.distinct('cid', {'_id': {'$in': id_list},
                                                                           'parent_cid': {'$in': [None, '']}})
                        await update_subject_sub_dimension_status(self.current_user.oid, status, cid_list)
                    r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectDimensionDeleteViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def post(self, dimension_id):
        r_dict = {'code': 0}
        try:
            subject_dimension = await SubjectDimension.get_by_id(dimension_id)
            subject_dimension_cid = copy.deepcopy(subject_dimension.cid)
            await SubjectDimension.delete_many({'parent_cid': subject_dimension.cid})
            await subject_dimension.delete()
            await do_subject_dimension(subject_dimension_cid)
            r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectSubDimensionsListViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/dimensions/sub_dimensions_list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def get(self, dimension_id):
        cid_list = await SubjectDimension.distinct('cid', {'_id': ObjectId(dimension_id)})
        query_params = {'record_flag': 1, 'parent_cid': {'$in': cid_list}}

        sd_title = self.get_argument('sd_title', '')
        if sd_title:
            query_params['title'] = {'$regex': sd_title, '$options': 'i'}
        # 分页 START
        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s' % (
            self.reverse_url("backoffice_subject_sub_dimensions_list", dimension_id), per_page_quantity)
        paging = Paging(page_url, SubjectDimension, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['ordered'], **query_params)
        await paging.pager()
        return locals()


class SubjectSubDimensionsAddViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/dimensions/sub_dimensions_add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def get(self, dimension_id):
        subject_dimension = await SubjectDimension.find_one({'_id': ObjectId(dimension_id)})
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def post(self, dimension_id):
        p_subject_dimension = await SubjectDimension.find_one({'_id': ObjectId(dimension_id)})
        r_dict = {'code': 0}
        sub_dimension_id = None
        try:
            title = self.get_argument('title', None)
            status = self.get_argument('status', None)  # 状态
            ordered = self.get_argument('ordered', None)
            code = self.get_argument('code', None)
            comment = self.get_argument('comment', None)
            if title and ordered and p_subject_dimension and code:
                t_count = await SubjectDimension.count(dict(title=title, parent_cid=p_subject_dimension.cid))
                r_count = await SubjectDimension.count(dict(ordered=int(ordered), parent_cid=p_subject_dimension.cid))
                c_count = await SubjectDimension.count(dict(code=code, parent_cid=p_subject_dimension.cid))
                if c_count > 0:
                    r_dict['code'] = -2
                elif t_count > 0:
                    r_dict['code'] = -6
                elif r_count > 0:
                    r_dict['code'] = -5
                else:
                    if status == 'on':
                        status = STATUS_SUBJECT_DIMENSION_ACTIVE
                    else:
                        status = STATUS_SUBJECT_DIMENSION_INACTIVE
                    subject_dimension = SubjectDimension(title=title, ordered=int(ordered), code=code)
                    subject_dimension.status = status
                    subject_dimension.comment = comment if comment else None
                    subject_dimension.created_id = self.current_user.oid
                    subject_dimension.updated_id = self.current_user.oid
                    subject_dimension.parent_cid = p_subject_dimension.cid
                    sub_dimension_id = await subject_dimension.save()
                    await do_subject_dimension(p_subject_dimension.cid)
                    r_dict['code'] = 1
            else:
                if not title:
                    r_dict['code'] = -1
                if not ordered:
                    r_dict['code'] = -4
        except RuntimeError:
            if sub_dimension_id:
                await SubjectDimension.delete_by_ids(sub_dimension_id)
            logger.error(traceback.format_exc())
        return r_dict


class SubjectSubDimensionsEditViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/dimensions/sub_dimensions_edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def get(self, sub_dimension_id):
        subject_dimension = await SubjectDimension.get_by_id(sub_dimension_id)
        p_subject_dimension = await SubjectDimension.get_by_cid(subject_dimension.parent_cid)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def post(self, sub_dimension_id):
        r_dict = {'code': 0}
        try:
            subject_dimension = await SubjectDimension.get_by_id(sub_dimension_id)
            p_subject_dimension = await SubjectDimension.get_by_cid(subject_dimension.parent_cid)
            title = self.get_argument('title', None)
            status = self.get_argument('status', None)  # 状态
            ordered = self.get_argument('ordered', None)
            comment = self.get_argument('comment', None)
            code = self.get_argument('code', None)
            if subject_dimension and title and ordered and code:
                t_count = await SubjectDimension.count(
                    dict(title=title, id={'$ne': ObjectId(sub_dimension_id)}, parent_cid=p_subject_dimension.cid))
                r_count = await SubjectDimension.count(
                    dict(ordered=int(ordered), id={'$ne': ObjectId(sub_dimension_id)},
                         parent_cid=p_subject_dimension.cid))
                c_count = await SubjectDimension.count(
                    dict(code=code, id={'$ne': ObjectId(sub_dimension_id)}, parent_cid=p_subject_dimension.cid))
                if c_count > 0:
                    r_dict['code'] = -2
                elif t_count > 0:
                    r_dict['code'] = -6
                elif r_count > 0:
                    r_dict['code'] = -5
                else:
                    if status == 'on':
                        status = STATUS_SUBJECT_DIMENSION_ACTIVE
                    else:
                        status = STATUS_SUBJECT_DIMENSION_INACTIVE
                    subject_dimension.title = title
                    subject_dimension.code = code
                    subject_dimension.ordered = int(ordered)
                    subject_dimension.status = status
                    subject_dimension.comment = comment if comment else None
                    subject_dimension.updated = datetime.datetime.now()
                    subject_dimension.updated_id = self.current_user.oid
                    await subject_dimension.save()
                    r_dict['code'] = 1
            else:
                if not title:
                    r_dict['code'] = -1
                if not ordered:
                    r_dict['code'] = -4
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectSubDimensionsStatusSwitchViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def post(self, sub_dimension_id):
        r_dict = {'code': 0}
        try:
            status = self.get_argument('status', False)
            if status == 'true':
                status = STATUS_SUBJECT_DIMENSION_ACTIVE
            else:
                status = STATUS_SUBJECT_DIMENSION_INACTIVE
            subject_dimension = await SubjectDimension.get_by_id(sub_dimension_id)
            if subject_dimension:
                subject_dimension.status = status
                subject_dimension.updated = datetime.datetime.now()
                subject_dimension.updated_id = self.current_user.oid
                await subject_dimension.save()
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectSubDimensionsBatchOperateViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            subject_dimension_id_list = self.get_body_arguments('subject_dimension_id_list[]', [])
            if subject_dimension_id_list:
                operate = self.get_argument('operate', None)
                if operate is not None:
                    id_list = [ObjectId(subject_id) for subject_id in subject_dimension_id_list]
                    if int(operate) == 1:
                        update_requests = []
                        for dimension_id in subject_dimension_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(dimension_id)},
                                                             {'$set': {'status': STATUS_SUBJECT_DIMENSION_ACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await SubjectDimension.update_many(update_requests)
                    elif int(operate) == 0:
                        update_requests = []
                        for dimension_id in subject_dimension_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(dimension_id)},
                                                             {'$set': {'status': STATUS_SUBJECT_DIMENSION_INACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await SubjectDimension.update_many(update_requests)
                    elif int(operate) == -1:
                        if id_list:
                            subject_dimension_id = id_list[0]
                            subject_dimension = await SubjectDimension.find_one(dict(_id=subject_dimension_id))
                            if subject_dimension:
                                p_subject_dimension_cid = subject_dimension.parent_cid
                                await do_subject_dimension(p_subject_dimension_cid)
                        await SubjectDimension.delete_many({'_id': {'$in': id_list}})
                    r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectSubDimensionsDeleteViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIMENSION_MANAGEMENT)
    async def post(self, sub_dimension_id):
        r_dict = {'code': 0}
        try:
            subject_dimension = await SubjectDimension.get_by_id(sub_dimension_id)
            p_subject_dimension_cid = copy.deepcopy(subject_dimension.parent_cid)
            await subject_dimension.delete()
            await do_subject_dimension(p_subject_dimension_cid)
            r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/backoffice/subject/dimension/list/', SubjectDimensionListViewHandler,
        name='backoffice_subject_dimension_list'),
    url(r'/backoffice/subject/dimension/add/', SubjectDimensionAddViewHandler, name='backoffice_subject_dimension_add'),
    url(r'/backoffice/subject/dimension/edit/([0-9a-zA-Z_]+)/', SubjectDimensionEditViewHandler,
        name='backoffice_subject_dimension_edit'),
    url(r'/backoffice/subject/dimension/status_switch/([0-9a-zA-Z_]+)/', SubjectDimensionStatusSwitchViewHandler,
        name='backoffice_subject_dimension_status_switch'),
    url(r'/backoffice/subject/dimension/batch_operate/', SubjectDimensionBatchOperateViewHandler,
        name='backoffice_subject_dimension_batch_operate'),
    url(r'/backoffice/subject/dimension/delete/([0-9a-zA-Z_]+)/', SubjectDimensionDeleteViewHandler,
        name='backoffice_subject_dimension_delete'),
    url(r'/backoffice/subject/sub/dimensions/list/([0-9a-zA-Z_]+)/', SubjectSubDimensionsListViewHandler,
        name='backoffice_subject_sub_dimensions_list'),
    url(r'/backoffice/subject/sub/dimensions/add/([0-9a-zA-Z_]+)/', SubjectSubDimensionsAddViewHandler,
        name='backoffice_subject_sub_dimensions_add'),
    url(r'/backoffice/subject/sub/dimensions/edit/([0-9a-zA-Z_]+)/', SubjectSubDimensionsEditViewHandler,
        name='backoffice_subject_sub_dimensions_edit'),
    url(r'/backoffice/subject/sub/dimensions/status_switch/([0-9a-zA-Z_]+)/',
        SubjectSubDimensionsStatusSwitchViewHandler,
        name='backoffice_subject_sub_dimensions_status_switch'),
    url(r'/backoffice/subject/sub/dimensions/batch_operate/', SubjectSubDimensionsBatchOperateViewHandler,
        name='backoffice_subject_sub_dimensions_batch_operate'),
    url(r'/backoffice/subject/sub/dimensions/delete/([0-9a-zA-Z_]+)/', SubjectSubDimensionsDeleteViewHandler,
        name='backoffice_subject_sub_dimensions_delete'),
]
