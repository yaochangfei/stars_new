# !/usr/bin/python
# -*- coding:utf-8 -*-

import traceback

from bson import ObjectId
from pymongo import UpdateOne, ASCENDING, ReadPreference
from tornado.web import url

from caches.redis_utils import RedisCache
from commons.page_utils import Paging
from db import STATUS_SUBJECT_CHOICE_RULE_ACTIVE, STATUS_SUBJECT_CHOICE_RULE_INACTIVE, STATUS_SUBJECT_DIMENSION_ACTIVE
from db.models import SubjectChoiceRules, SubjectDimension, SubjectBanks
from enums import PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT, KEY_EXTRACTING_SUBJECT_RULE, \
    KEY_PREFIX_EXTRACTING_SUBJECT_RULE, KEY_EXTRACTING_SUBJECT_QUANTITY
from logger import log_utils
from tasks.instances import task_subject_extract
from tasks.instances.task_subject_extract import start_extract_subjects
from web import BaseHandler, decorators, datetime, json

logger = log_utils.get_logging()


class SubjectChoiceruleListViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/choice_rule/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT)
    async def get(self):
        query_params = {'record_flag': 1, 'parent_cid': {'$in': [None, '']}}

        title = self.get_argument('title', '')
        code = self.get_argument('code', '')
        if title:
            query_params['title'] = {'$regex': title, '$options': 'i'}
        code = self.get_argument('code', '')
        if code:
            query_params['code'] = {'$regex': code, '$options': 'i'}

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s' % (
            self.reverse_url("backoffice_subject_choice_rule_list"), per_page_quantity)
        paging = Paging(page_url, SubjectChoiceRules, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'], **query_params)
        await paging.pager()

        # 检查抽题状态
        cached_extract_dict = RedisCache.hgetall(KEY_EXTRACTING_SUBJECT_RULE)
        cached_process_dict = RedisCache.hgetall(KEY_PREFIX_EXTRACTING_SUBJECT_RULE)
        cached_quantity_dict = RedisCache.hgetall(KEY_EXTRACTING_SUBJECT_QUANTITY)
        for rule in paging.page_items:
            setattr(rule, 'standby', True if cached_extract_dict.get(rule.cid.encode('utf-8')) == b'1' else False)
            in_process = True if cached_process_dict.get(rule.cid.encode('utf-8')) == b'1' else False
            setattr(rule, 'in_process', in_process)

            quantity = cached_quantity_dict.get(rule.cid.encode('utf-8'))
            if in_process:
                setattr(rule, 'quantity', int(quantity) if quantity else 0)
            else:
                if quantity is None:
                    quantity = await SubjectBanks.count(dict(rule_cid=rule.cid), read_preference=ReadPreference.PRIMARY)
                    RedisCache.hset(KEY_EXTRACTING_SUBJECT_QUANTITY, rule.cid, quantity)
                    setattr(rule, 'quantity', quantity)
                else:
                    setattr(rule, 'quantity', int(quantity))

        return locals()


class SubjectChoiceruleAddViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/choice_rule/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT)
    async def get(self):
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        choice_rule_id = None
        try:
            title = self.get_argument('title', None)
            status = self.get_argument('status', None)  # 状态
            code = self.get_argument('code', None)
            comment = self.get_argument('comment', None)
            if title and code:
                c_count = await SubjectChoiceRules.count(dict(code=code))
                if c_count > 0:
                    r_dict['code'] = -3
                else:
                    if status == 'on':
                        status = STATUS_SUBJECT_CHOICE_RULE_ACTIVE
                    else:
                        status = STATUS_SUBJECT_CHOICE_RULE_INACTIVE
                    choice_rule = SubjectChoiceRules(title=title, code=code)
                    choice_rule.status = status
                    choice_rule.comment = comment if comment else None
                    choice_rule.created_id = self.current_user.oid
                    choice_rule.updated_id = self.current_user.oid
                    choice_rule_id = await choice_rule.save()
                    r_dict['code'] = 1
            else:
                if not title:
                    r_dict['code'] = -1
                if not code:
                    r_dict['code'] = -2
        except RuntimeError:
            if choice_rule_id:
                await SubjectChoiceRules.delete_by_ids(choice_rule_id)
            logger.error(traceback.format_exc())
        return r_dict


class SubjectChoiceruleEditViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/choice_rule/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT)
    async def get(self, choice_rule_id):
        choice_rule = await SubjectChoiceRules.get_by_id(choice_rule_id)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT)
    async def post(self, choice_rule_id):
        r_dict = {'code': 0}
        try:
            choice_rule = await SubjectChoiceRules.get_by_id(choice_rule_id)
            title = self.get_argument('title', None)
            status = self.get_argument('status', None)  # 状态
            code = self.get_argument('code', None)
            comment = self.get_argument('comment', None)
            if choice_rule and title and code:
                c_count = await SubjectChoiceRules.count(dict(code=code, id={'$ne': ObjectId(choice_rule_id)}))
                if c_count > 0:
                    r_dict['code'] = -3
                else:
                    if status == 'on':
                        status = STATUS_SUBJECT_CHOICE_RULE_ACTIVE
                    else:
                        status = STATUS_SUBJECT_CHOICE_RULE_INACTIVE
                    choice_rule.title = title
                    choice_rule.code = code
                    choice_rule.status = status
                    choice_rule.comment = comment if comment else None
                    choice_rule.updated_dt = datetime.datetime.now()
                    choice_rule.updated_id = self.current_user.oid
                    await choice_rule.save()
                    r_dict['code'] = 1
            else:
                if not title:
                    r_dict['code'] = -1
                if not code:
                    r_dict['code'] = -2
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectChoiceruleStatusSwitchViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT)
    async def post(self, choice_rule_id):
        r_dict = {'code': 0}
        try:
            status = self.get_argument('status', False)
            if status == 'true':
                status = STATUS_SUBJECT_CHOICE_RULE_ACTIVE
            else:
                status = STATUS_SUBJECT_CHOICE_RULE_INACTIVE
            choice_rule = await SubjectChoiceRules.get_by_id(choice_rule_id)
            if choice_rule:
                choice_rule.status = status
                choice_rule.updated = datetime.datetime.now()
                choice_rule.updated_id = self.current_user.oid
                await choice_rule.save()
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectChoiceruleBatchOperateViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            choice_rule_id_list = self.get_body_arguments('choice_rule_id_list[]', [])
            if choice_rule_id_list:
                operate = self.get_argument('operate', None)
                if operate is not None:
                    id_list = [ObjectId(subject_id) for subject_id in choice_rule_id_list]
                    if int(operate) == 1:
                        update_requests = []
                        for choice_rule_id in choice_rule_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(choice_rule_id)},
                                                             {'$set': {'status': STATUS_SUBJECT_CHOICE_RULE_ACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await SubjectChoiceRules.update_many(update_requests)
                    elif int(operate) == 0:
                        update_requests = []
                        for choice_rule_id in choice_rule_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(choice_rule_id)},
                                                             {'$set': {'status': STATUS_SUBJECT_CHOICE_RULE_INACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await SubjectChoiceRules.update_many(update_requests)
                    elif int(operate) == -1:
                        await SubjectChoiceRules.delete_many({'_id': {'$in': id_list}})
                    r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectChoiceruleDeleteViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT)
    async def post(self, choice_rule_id):
        r_dict = {'code': 0}
        try:
            choice_rule = await SubjectChoiceRules.get_by_id(choice_rule_id)
            await SubjectBanks.delete_many({'rule_cid': choice_rule.cid})
            await choice_rule.delete()
            r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectChoiceruleSettingViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/choice_rule/setting_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT)
    async def get(self, choice_rule_id):
        choice_rule = await SubjectChoiceRules.get_by_id(choice_rule_id)
        dimension_rules = choice_rule.dimension_rules
        subject_dimension_list = []
        cid_list = list(dimension_rules.keys())
        field_dict = {'record_flag': 1, 'status': STATUS_SUBJECT_DIMENSION_ACTIVE, 'parent_cid': {'$in': ['', None]}}
        sub_dict = {'record_flag': 1, 'status': STATUS_SUBJECT_DIMENSION_ACTIVE}
        all_dimension_list = await SubjectDimension.find(field_dict).sort([('ordered', ASCENDING)]).to_list(None)
        if cid_list:
            field_dict['cid'] = {'$in': cid_list}
        if dimension_rules:
            dimension_list = await SubjectDimension.find(field_dict).sort([('ordered', ASCENDING)]).to_list(None)
            for dimension in dimension_list:
                subject_dimension_dict = {}
                sub_dict['parent_cid'] = dimension.cid
                sub_dimension_list = await SubjectDimension.find(sub_dict).sort([('ordered', ASCENDING)]).to_list(None)
                if sub_dimension_list:
                    subject_dimension_dict['title'] = dimension.title
                    subject_dimension_dict['cid'] = dimension.cid
                    subject_dimension_dict['type'] = dimension.category
                    sub_list = []
                    for sub_dimension in sub_dimension_list:
                        sub_dimension_dict = {}
                        sub_dimension_dict['cid'] = sub_dimension.cid
                        sub_dimension_dict['title'] = sub_dimension.title
                        sub_list.append(sub_dimension_dict)
                    if sub_list:
                        subject_dimension_dict['sub'] = sub_list
                if subject_dimension_dict:
                    subject_dimension_list.append(subject_dimension_dict)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT)
    async def post(self, choice_rule_id):
        r_dict = {'code': 0}
        try:
            choice_rule = await SubjectChoiceRules.get_by_id(choice_rule_id)
            q_total = self.get_argument('q_total', 0)
            dimension_json = self.get_argument('dimension_json')
            dimension_list = None
            if dimension_json:
                dimension_list = json.loads(dimension_json)
            if q_total and dimension_list:
                choice_rule.dimension_rules = dimension_list[0]
                choice_rule.quantity = int(q_total)
                choice_rule.updated = datetime.datetime.now()
                choice_rule.updated_id = self.current_user.oid
                is_valid = await task_subject_extract.is_valid_extract_rule(choice_rule)
                if is_valid:
                    await choice_rule.save()
                    RedisCache.hset(KEY_EXTRACTING_SUBJECT_RULE, choice_rule.cid, 1)
                    r_dict['code'] = 1
                else:
                    r_dict['code'] = 2
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectChoiceruleAddDimensionViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT)
    async def post(self, choice_rule_id):
        r_dict = {'code': 0}
        try:
            choice_rule = await SubjectChoiceRules.get_by_id(choice_rule_id)
            dimension_rules = choice_rule.dimension_rules
            cid = self.get_argument('cid')
            field_dict = {'record_flag': 1, 'status': STATUS_SUBJECT_DIMENSION_ACTIVE,
                          'parent_cid': {'$in': [None, '']}}
            if cid:
                field_dict['cid'] = cid
                sub_dict = {'record_flag': 1, 'status': STATUS_SUBJECT_DIMENSION_ACTIVE, 'parent_cid': cid}
                dimension = await SubjectDimension.find_one(field_dict)
                sub_list = await SubjectDimension.find(sub_dict).sort([('ordered', ASCENDING)]).to_list(None)
                html = self.render_string('backoffice/subjects/choice_rule/add_dimensions.html',
                                          dimension=dimension, sub_list=sub_list, dimension_rules=dimension_rules)
                r_dict['html'] = html
            else:
                r_dict['html'] = ''
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectChoiceruleSelectDimensionViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            cid_list = self.get_arguments('cid_list[]')
            field_dict = {'record_flag': 1, 'status': STATUS_SUBJECT_DIMENSION_ACTIVE,
                          'parent_cid': {'$in': [None, '']}}
            if cid_list:
                field_dict['cid'] = {'$nin': cid_list}
            dimension_list = await SubjectDimension.find(field_dict).sort([('ordered', ASCENDING)]).to_list(None)
            html = self.render_string('backoffice/subjects/choice_rule/select_view.html',
                                      dimension_list=dimension_list)
            r_dict['html'] = html
            r_dict['code'] = 1
            if len(dimension_list) == 1:
                r_dict['code'] = 2
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectChoiceRuleExtractViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/choice_rule/extract_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT)
    async def get(self, choice_rule_id):
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_DRAW_MANAGEMENT)
    async def post(self, choice_rule_id):
        r_dict = {'code': 0}
        try:
            choice_rule = await SubjectChoiceRules.get_by_cid(choice_rule_id)
            if choice_rule:
                if RedisCache.hget(KEY_PREFIX_EXTRACTING_SUBJECT_RULE, choice_rule.cid) in [b'0', 0, None]:
                    times = int(self.get_argument('times', 1))

                    RedisCache.hset(KEY_EXTRACTING_SUBJECT_RULE, choice_rule.cid, 0)
                    RedisCache.hset(KEY_PREFIX_EXTRACTING_SUBJECT_RULE, choice_rule.cid, 1)

                    start_extract_subjects.delay(choice_rule, times)

                    r_dict['code'] = 1  # 任务已提交
                else:
                    r_dict['code'] = -1  # 任务在执行
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/backoffice/subject/choice/rule/list/', SubjectChoiceruleListViewHandler,
        name='backoffice_subject_choice_rule_list'),
    url(r'/backoffice/subject/choice/rule/add/', SubjectChoiceruleAddViewHandler,
        name='backoffice_subject_choice_rule_add'),
    url(r'/backoffice/subject/choice/rule/edit/([0-9a-zA-Z_]+)/', SubjectChoiceruleEditViewHandler,
        name='backoffice_subject_choice_rule_edit'),
    url(r'/backoffice/subject/choice/rule/status_switch/([0-9a-zA-Z_]+)/',
        SubjectChoiceruleStatusSwitchViewHandler,
        name='backoffice_subject_choice_rule_status_switch'),
    url(r'/backoffice/subject/choice/rule/batch_operate/', SubjectChoiceruleBatchOperateViewHandler,
        name='backoffice_subject_choice_rule_batch_operate'),
    url(r'/backoffice/subject/choice/rule/delete/([0-9a-zA-Z_]+)/', SubjectChoiceruleDeleteViewHandler,
        name='backoffice_subject_choice_rule_delete'),
    url(r'/backoffice/subject/choice/rule/setting/([0-9a-zA-Z_]+)/', SubjectChoiceruleSettingViewHandler,
        name='backoffice_subject_choice_rule_setting'),
    url(r'/backoffice/subject/choice/rule/add/dimension/([0-9a-zA-Z_]+)/', SubjectChoiceruleAddDimensionViewHandler,
        name='backoffice_subject_choice_rule_add_dimension'),
    url(r'/backoffice/subject/choice/rule/select/dimension/', SubjectChoiceruleSelectDimensionViewHandler,
        name='backoffice_subject_choice_rule_select_dimension'),

    url(r'/backoffice/subject/choice/rule/extract/([0-9a-zA-Z_]+)/', SubjectChoiceRuleExtractViewHandler,
        name='backoffice_subject_choice_rule_extract')
]
