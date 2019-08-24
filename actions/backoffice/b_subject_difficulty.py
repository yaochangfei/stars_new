# !/usr/bin/python
# -*- coding:utf-8 -*-

import traceback

from bson import ObjectId
from pymongo import UpdateOne
from tornado.web import url

from actions.v_common import logger
from commons.page_utils import Paging
from db import STATUS_SUBJECT_DIFFICULTY_ACTIVE, STATUS_SUBJECT_DIFFICULTY_INACTIVE
from db.models import SubjectDifficulty
from enums import PERMISSION_TYPE_MINIAPP_SUBJECT_DIFFICULTY_MANAGEMENT
from logger import log_utils
from web import BaseHandler, decorators, datetime

logger = log_utils.get_logging()


class SubjectDifficultyListViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/difficulty/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIFFICULTY_MANAGEMENT)
    async def get(self):
        query_params = {'record_flag': 1}

        sd_title = self.get_argument('sd_title', '')
        if sd_title:
            query_params['title'] = {'$regex': sd_title, '$options': 'i'}
        # 分页 START
        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s' % (
            self.reverse_url("backoffice_subject_difficulty_list"), per_page_quantity)
        paging = Paging(page_url, SubjectDifficulty, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'], **query_params)
        await paging.pager()
        return locals()


class SubjectDifficultyAddViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/difficulty/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIFFICULTY_MANAGEMENT)
    async def get(self):
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIFFICULTY_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        subject_difficulty_id = None
        try:
            title = self.get_argument('title', None)
            status = self.get_argument('status', None)  # 状态
            ordered = self.get_argument('ordered', None)
            comment = self.get_argument('comment', None)
            if title and ordered:
                t_count = await SubjectDifficulty.count(dict(title=title))
                r_count = await SubjectDifficulty.count(dict(ordered=int(ordered)))
                if t_count > 0:
                    r_dict['code'] = -4
                elif r_count > 0:
                    r_dict['code'] = -3
                else:
                    if status == 'on':
                        status = STATUS_SUBJECT_DIFFICULTY_ACTIVE
                    else:
                        status = STATUS_SUBJECT_DIFFICULTY_INACTIVE
                    subject_difficulty = SubjectDifficulty(title=title,
                                                           ordered=int(ordered))
                    subject_difficulty.status = status
                    subject_difficulty.comment = comment if comment else None
                    subject_difficulty.created_id = self.current_user.oid
                    subject_difficulty.updated_id = self.current_user.oid
                    subject_difficulty_id = await subject_difficulty.save()
                    r_dict['code'] = 1
            else:
                if not title:
                    r_dict['code'] = -1
                if not ordered:
                    r_dict['code'] = -2
        except RuntimeError:
            if subject_difficulty_id:
                await SubjectDifficulty.delete_by_ids(subject_difficulty_id)
            logger.error(traceback.format_exc())
        return r_dict


class SubjectDifficultyEditViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/difficulty/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIFFICULTY_MANAGEMENT)
    async def get(self, difficulty_id):
        subject_difficulty = await SubjectDifficulty.get_by_id(difficulty_id)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIFFICULTY_MANAGEMENT)
    async def post(self, difficulty_id):
        r_dict = {'code': 0}
        try:
            subject_difficulty = await SubjectDifficulty.get_by_id(difficulty_id)
            title = self.get_argument('title', None)
            status = self.get_argument('status', None)  # 状态
            ordered = self.get_argument('ordered', None)
            comment = self.get_argument('comment', None)
            if subject_difficulty and title and ordered:
                t_count = await SubjectDifficulty.count(dict(title=title, id={'$ne': ObjectId(difficulty_id)}))
                r_count = await SubjectDifficulty.count(dict(ordered=int(ordered), id={'$ne': ObjectId(difficulty_id)}))
                if t_count > 0:
                    r_dict['code'] = -4
                elif r_count > 0:
                    r_dict['code'] = -3
                else:
                    if status == 'on':
                        status = STATUS_SUBJECT_DIFFICULTY_ACTIVE
                    else:
                        status = STATUS_SUBJECT_DIFFICULTY_INACTIVE
                    subject_difficulty.title = title
                    subject_difficulty.ordered = int(ordered)
                    subject_difficulty.status = status
                    subject_difficulty.comment = comment if comment else None
                    subject_difficulty.updated_dt = datetime.datetime.now()
                    subject_difficulty.updated_id = self.current_user.oid
                    await subject_difficulty.save()
                    r_dict['code'] = 1
            else:
                if not title:
                    r_dict['code'] = -1
                if not ordered:
                    r_dict['code'] = -2
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectDifficultyStatusSwitchViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIFFICULTY_MANAGEMENT)
    async def post(self, difficulty_id):
        r_dict = {'code': 0}
        try:
            status = self.get_argument('status', False)
            if status == 'true':
                status = STATUS_SUBJECT_DIFFICULTY_ACTIVE
            else:
                status = STATUS_SUBJECT_DIFFICULTY_INACTIVE
            subject_difficulty = await SubjectDifficulty.get_by_id(difficulty_id)
            if subject_difficulty:
                subject_difficulty.status = status
                subject_difficulty.updated = datetime.datetime.now()
                subject_difficulty.updated_id = self.current_user.oid
                await subject_difficulty.save()
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectDifficultyBatchOperateViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIFFICULTY_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            subject_difficulty_id_list = self.get_body_arguments('subject_difficulty_id_list[]', [])
            if subject_difficulty_id_list:
                operate = self.get_argument('operate', None)
                if operate is not None:
                    id_list = [ObjectId(subject_id) for subject_id in subject_difficulty_id_list]
                    if int(operate) == 1:
                        update_requests = []
                        for difficulty_id in subject_difficulty_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(difficulty_id)},
                                                             {'$set': {'status': STATUS_SUBJECT_DIFFICULTY_ACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await SubjectDifficulty.update_many(update_requests)
                    elif int(operate) == 0:
                        update_requests = []
                        for difficulty_id in subject_difficulty_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(difficulty_id)},
                                                             {'$set': {'status': STATUS_SUBJECT_DIFFICULTY_INACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await SubjectDifficulty.update_many(update_requests)
                    elif int(operate) == -1:
                        await SubjectDifficulty.delete_many({'_id': {'$in': id_list}})
                    r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectDifficultyDeleteViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DIFFICULTY_MANAGEMENT)
    async def post(self, difficulty_id):
        r_dict = {'code': 0}
        try:
            subject_difficulty = await SubjectDifficulty.get_by_id(difficulty_id)
            await subject_difficulty.delete()
            r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/backoffice/subject/difficulty/list/', SubjectDifficultyListViewHandler,
        name='backoffice_subject_difficulty_list'),
    url(r'/backoffice/subject/difficulty/add/', SubjectDifficultyAddViewHandler,
        name='backoffice_subject_difficulty_add'),
    url(r'/backoffice/subject/difficulty/edit/([0-9a-zA-Z_]+)/', SubjectDifficultyEditViewHandler,
        name='backoffice_subject_difficulty_edit'),
    url(r'/backoffice/subject/difficulty/status_switch/([0-9a-zA-Z_]+)/',
        SubjectDifficultyStatusSwitchViewHandler,
        name='backoffice_subject_difficulty_status_switch'),
    url(r'/backoffice/subject/difficulty/batch_operate/', SubjectDifficultyBatchOperateViewHandler,
        name='backoffice_subject_difficulty_batch_operate'),
    url(r'/backoffice/subject/difficulty/delete/([0-9a-zA-Z_]+)/', SubjectDifficultyDeleteViewHandler,
        name='backoffice_subject_difficulty_delete'),
]
