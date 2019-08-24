# !/usr/bin/python
# -*- coding:utf-8 -*-

import traceback

from bson import ObjectId
from pymongo import UpdateOne
from tornado.web import url

from actions.v_common import logger
from commons.page_utils import Paging
from db import STATUS_SUBJECT_CATEGORY_ACTIVE, STATUS_SUBJECT_CATEGORY_INACTIVE
from db.models import SubjectCategory
from enums import PERMISSION_TYPE_MINIAPP_SUBJECT_CATEGORY_MANAGEMENT
from logger import log_utils
from web import BaseHandler, decorators, datetime

logger = log_utils.get_logging()


class SubjectCategoryListViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/category/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_CATEGORY_MANAGEMENT)
    async def get(self):
        query_params = {'record_flag': 1}

        sd_title = self.get_argument('sd_title', '')
        if sd_title:
            query_params['title'] = {'$regex': sd_title, '$options': 'i'}
        # 分页 START
        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s' % (
            self.reverse_url("backoffice_subject_category_list"), per_page_quantity)
        paging = Paging(page_url, SubjectCategory, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'], **query_params)
        await paging.pager()
        return locals()


class SubjectCategoryAddViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/category/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_CATEGORY_MANAGEMENT)
    async def get(self):
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_CATEGORY_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        subject_category_id = None
        try:
            title = self.get_argument('title', None)
            status = self.get_argument('status', None)  # 状态
            comment = self.get_argument('comment', None)
            if title:
                t_count = await SubjectCategory.count(dict(title=title))
                if t_count > 0:
                    r_dict['code'] = -2
                else:
                    if status == 'on':
                        status = STATUS_SUBJECT_CATEGORY_ACTIVE
                    else:
                        status = STATUS_SUBJECT_CATEGORY_INACTIVE
                    subject_category = SubjectCategory(title=title)
                    subject_category.status = status
                    subject_category.comment = comment if comment else None
                    subject_category.created_id = self.current_user.oid
                    subject_category.updated_id = self.current_user.oid
                    subject_category_id = await subject_category.save()
                    r_dict['code'] = 1
            else:
                if not title:
                    r_dict['code'] = -1
        except RuntimeError:
            if subject_category_id:
                await SubjectCategory.delete_by_ids(subject_category_id)
            logger.error(traceback.format_exc())
        return r_dict


class SubjectCategoryEditViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/category/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_CATEGORY_MANAGEMENT)
    async def get(self, subject_category_id):
        subject_category = await SubjectCategory.get_by_id(subject_category_id)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_CATEGORY_MANAGEMENT)
    async def post(self, category_id):
        r_dict = {'code': 0}
        try:
            subject_category = await SubjectCategory.get_by_id(category_id)
            title = self.get_argument('title', None)
            status = self.get_argument('status', None)  # 状态
            comment = self.get_argument('comment', None)
            if subject_category and title:
                t_count = await SubjectCategory.count(dict(title=title, id={'$ne': ObjectId(category_id)}))
                if t_count > 0:
                    r_dict['code'] = -2
                else:
                    if status == 'on':
                        status = STATUS_SUBJECT_CATEGORY_ACTIVE
                    else:
                        status = STATUS_SUBJECT_CATEGORY_INACTIVE
                    subject_category.title = title
                    subject_category.status = status
                    subject_category.comment = comment if comment else None
                    subject_category.updated_dt = datetime.datetime.now()
                    subject_category.updated_id = self.current_user.oid
                    await subject_category.save()
                    r_dict['code'] = 1
            else:
                if not title:
                    r_dict['code'] = -1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectCategoryStatusSwitchViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_CATEGORY_MANAGEMENT)
    async def post(self, category_id):
        r_dict = {'code': 0}
        try:
            status = self.get_argument('status', False)
            if status == 'true':
                status = STATUS_SUBJECT_CATEGORY_ACTIVE
            else:
                status = STATUS_SUBJECT_CATEGORY_INACTIVE
            subject_category = await SubjectCategory.get_by_id(category_id)
            if subject_category:
                subject_category.status = status
                subject_category.updated = datetime.datetime.now()
                subject_category.updated_id = self.current_user.oid
                await subject_category.save()
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectCategoryBatchOperateViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_CATEGORY_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            subject_category_id_list = self.get_body_arguments('subject_category_id_list[]', [])
            if subject_category_id_list:
                operate = self.get_argument('operate', None)
                if operate is not None:
                    id_list = [ObjectId(subject_id) for subject_id in subject_category_id_list]
                    if int(operate) == 1:
                        update_requests = []
                        for category_id in subject_category_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(category_id)},
                                                             {'$set': {'status': STATUS_SUBJECT_CATEGORY_ACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await SubjectCategory.update_many(update_requests)
                    elif int(operate) == 0:
                        update_requests = []
                        for category_id in subject_category_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(category_id)},
                                                             {'$set': {'status': STATUS_SUBJECT_CATEGORY_INACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await SubjectCategory.update_many(update_requests)
                    elif int(operate) == -1:
                        await SubjectCategory.delete_many({'_id': {'$in': id_list}})
                    r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectCategoryDeleteViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_CATEGORY_MANAGEMENT)
    async def post(self, category_id):
        r_dict = {'code': 0}
        try:
            subject_category = await SubjectCategory.get_by_id(category_id)
            await subject_category.delete()
            r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/backoffice/subject/category/list/', SubjectCategoryListViewHandler,
        name='backoffice_subject_category_list'),
    url(r'/backoffice/subject/category/add/', SubjectCategoryAddViewHandler,
        name='backoffice_subject_category_add'),
    url(r'/backoffice/subject/category/edit/([0-9a-zA-Z_]+)/', SubjectCategoryEditViewHandler,
        name='backoffice_subject_category_edit'),
    url(r'/backoffice/subject/category/status_switch/([0-9a-zA-Z_]+)/',
        SubjectCategoryStatusSwitchViewHandler,
        name='backoffice_subject_category_status_switch'),
    url(r'/backoffice/subject/category/batch_operate/', SubjectCategoryBatchOperateViewHandler,
        name='backoffice_subject_category_batch_operate'),
    url(r'/backoffice/subject/category/delete/([0-9a-zA-Z_]+)/', SubjectCategoryDeleteViewHandler,
        name='backoffice_subject_category_delete'),
]
