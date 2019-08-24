# !/usr/bin/python
# -*- coding:utf-8 -*-

import traceback

from actions.backoffice.race.utils import get_menu
from pymongo import UpdateOne, ASCENDING, ReadPreference
from tornado.web import url

from caches.redis_utils import RedisCache
from commons.page_utils import Paging
from db import STATUS_SUBJECT_CHOICE_RULE_ACTIVE, STATUS_SUBJECT_CHOICE_RULE_INACTIVE, STATUS_SUBJECT_DIMENSION_ACTIVE
from db.models import SubjectChoiceRules, SubjectDimension, RaceSubjectChoiceRules, RaceSubjectBanks
from enums import PERMISSION_TYPE_MINIAPP_RACE_RULES_MANAGEMENT, \
    KEY_PREFIX_EXTRACTING_SUBJECT_RULE, KEY_EXTRACTING_SUBJECT_QUANTITY
from logger import log_utils
from tasks.instances import task_race_subject_extract
from tasks.instances.task_race_subject_extract import start_race_extract_subjects
from web import BaseHandler, decorators, datetime, json

logger = log_utils.get_logging()


class RaceSubjectChoiceruleListViewHandler(BaseHandler):
    @decorators.render_template('backoffice/race/choice_rule/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_RULES_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        if race_cid:
            query_params = {'race_cid': race_cid, 'record_flag': 1, 'parent_cid': {'$in': [None, '']}}

            title = self.get_argument('title', '')
            code = self.get_argument('code', '')
            if title:
                query_params['title'] = {'$regex': title, '$options': 'i'}
            code = self.get_argument('code', '')
            if code:
                query_params['code'] = {'$regex': code, '$options': 'i'}
            per_page_quantity = int(self.get_argument('per_page_quantity', 10))
            to_page_num = int(self.get_argument('page', 1))
            page_url = '%s?page=$page&per_page_quantity=%s&title=%s&code=%s' % (
                self.reverse_url("backoffice_race_subject_choice_rule_list"), per_page_quantity, title, code)
            paging = Paging(page_url, RaceSubjectChoiceRules, current_page=to_page_num,
                            items_per_page=per_page_quantity,
                            sort=['-updated_dt'], **query_params)
            await paging.pager()

            # 检查抽题状态
            cached_extract_dict = RedisCache.hgetall(race_cid)
            cached_process_dict = RedisCache.hgetall(KEY_PREFIX_EXTRACTING_SUBJECT_RULE)
            cached_quantity_dict = RedisCache.hgetall(KEY_EXTRACTING_SUBJECT_QUANTITY)
            for rule in paging.page_items:
                setattr(rule, 'standby', True if cached_extract_dict.get(rule.cid.encode('utf-8')) == b'1' else False)
                in_process = True if cached_process_dict.get(rule.cid.encode('utf-8')) == b'1' else False
                setattr(rule, 'in_process', in_process)

                quantities = cached_quantity_dict.get(rule.cid.encode('utf-8'))
                if in_process:
                    setattr(rule, 'quantities', int(quantities) if quantities else 0)
                else:
                    if quantities is None:
                        quantities = await RaceSubjectBanks.count(dict(rule_cid=rule.cid),
                                                                  read_preference=ReadPreference.PRIMARY)
                        RedisCache.hset(KEY_EXTRACTING_SUBJECT_QUANTITY, rule.cid, quantities)
                        setattr(rule, 'quantities', quantities)
                    else:
                        setattr(rule, 'quantities', int(quantities))
        return locals()


class RaceSubjectChoiceruleAddViewHandler(BaseHandler):
    @decorators.render_template('backoffice/race/choice_rule/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_RULES_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_RULES_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        choice_rule_id = None
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid:
                title = self.get_argument('title', None)
                status = self.get_argument('status', None)  # 状态
                code = self.get_argument('code', None)
                comment = self.get_argument('comment', None)
                if title and code:
                    c_count = await RaceSubjectChoiceRules.count(dict(race_cid=race_cid, record_flag=1, code=code))
                    if c_count > 0:
                        r_dict['code'] = -3
                    else:
                        if status == 'on':
                            status = STATUS_SUBJECT_CHOICE_RULE_ACTIVE
                        else:
                            status = STATUS_SUBJECT_CHOICE_RULE_INACTIVE
                        choice_rule = RaceSubjectChoiceRules(race_cid=race_cid, title=title, code=code)
                        choice_rule.race_cid = race_cid
                        choice_rule.status = status
                        choice_rule.comment = comment if comment else None
                        choice_rule.created_dt = datetime.datetime.now()
                        choice_rule.updated_id = self.current_user.oid
                        choice_rule_id = await choice_rule.save()
                        r_dict['code'] = 1
                else:
                    if not title:
                        r_dict['code'] = -1
                    if not code:
                        r_dict['code'] = -2
        except Exception:
            if choice_rule_id:
                await SubjectChoiceRules.delete_by_ids([choice_rule_id])
            logger.error(traceback.format_exc())
        return r_dict


class RaceSubjectChoiceruleEditViewHandler(BaseHandler):
    @decorators.render_template('backoffice/race/choice_rule/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_RULES_MANAGEMENT)
    async def get(self, choice_rule_cid):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        if race_cid and choice_rule_cid:
            race_choice_rule = await RaceSubjectChoiceRules.find_one(
                filtered={'race_cid': race_cid, 'cid': choice_rule_cid})
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_RULES_MANAGEMENT)
    async def post(self, choice_rule_cid):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid and choice_rule_cid:
                race_choice_rule = await RaceSubjectChoiceRules.find_one(filtered={'cid': choice_rule_cid})
                title = self.get_argument('title', None)
                status = self.get_argument('status', None)  # 状态
                code = self.get_argument('code', None)
                comment = self.get_argument('comment', None)
                if race_choice_rule and title and code:
                    c_count = await RaceSubjectChoiceRules.count(dict(code=code, cid={'$ne': choice_rule_cid}))
                    if c_count > 0:
                        r_dict['code'] = -3
                    else:
                        if status == 'on':
                            status = STATUS_SUBJECT_CHOICE_RULE_ACTIVE
                        else:
                            status = STATUS_SUBJECT_CHOICE_RULE_INACTIVE
                        race_choice_rule.title = title
                        race_choice_rule.code = code
                        race_choice_rule.status = status
                        race_choice_rule.comment = comment if comment else None
                        race_choice_rule.updated_dt = datetime.datetime.now()
                        race_choice_rule.updated_id = self.current_user.oid
                        await race_choice_rule.save()
                        r_dict['code'] = 1
                else:
                    if not title:
                        r_dict['code'] = -1
                    if not code:
                        r_dict['code'] = -2
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceSubjectChoiceruleStatusSwitchViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_RULES_MANAGEMENT)
    async def post(self, choice_rule_cid):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid and choice_rule_cid:
                status = self.get_argument('status', False)
                if status == 'true':
                    status = STATUS_SUBJECT_CHOICE_RULE_ACTIVE
                else:
                    status = STATUS_SUBJECT_CHOICE_RULE_INACTIVE
                race_choice_rule = await RaceSubjectChoiceRules.find_one(
                    filtered={"race_cid": race_cid, 'cid': choice_rule_cid})
                if race_choice_rule:
                    race_choice_rule.status = status
                    race_choice_rule.updated_dt = datetime.datetime.now()
                    race_choice_rule.updated_id = self.current_user.oid
                    await race_choice_rule.save()
                r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceSubjectChoiceruleBatchOperateViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_RULES_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid:
                choice_rule_cid_list = self.get_body_arguments('choice_rule_cid_list[]', [])
                if choice_rule_cid_list:
                    operate = self.get_argument('operate', None)
                    if operate is not None:
                        if int(operate) == 1:
                            update_requests = []
                            for choice_rule_cid in choice_rule_cid_list:
                                update_requests.append(UpdateOne({'cid': choice_rule_cid},
                                                                 {'$set': {'status': STATUS_SUBJECT_CHOICE_RULE_ACTIVE,
                                                                           'updated_dt': datetime.datetime.now(),
                                                                           'updated_id': self.current_user.oid}}))
                            await RaceSubjectChoiceRules.update_many(update_requests)
                        elif int(operate) == 0:
                            update_requests = []
                            for choice_rule_cid in choice_rule_cid_list:
                                update_requests.append(UpdateOne({'cid': choice_rule_cid},
                                                                 {'$set': {
                                                                     'status': STATUS_SUBJECT_CHOICE_RULE_INACTIVE,
                                                                     'updated_dt': datetime.datetime.now(),
                                                                     'updated_id': self.current_user.oid}}))
                            await RaceSubjectChoiceRules.update_many(update_requests)
                        elif int(operate) == -1:
                            await RaceSubjectChoiceRules.delete_many({'cid': {'$in': choice_rule_cid_list}})
                        r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceSubjectChoiceruleDeleteViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_RULES_MANAGEMENT)
    async def post(self, choice_rule_cid):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid and choice_rule_cid:
                race_choice_rule = await RaceSubjectChoiceRules.find_one(
                    filtered={"race_cid": race_cid, 'cid': choice_rule_cid})
                await RaceSubjectBanks.delete_many({"race_cid": race_cid, 'rule_cid': race_choice_rule.cid})
                await race_choice_rule.delete()
                r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceSubjectChoiceruleSettingViewHandler(BaseHandler):
    @decorators.render_template('backoffice/race/choice_rule/setting_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_RULES_MANAGEMENT)
    async def get(self, choice_rule_cid):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        if race_cid:
            race_choice_rule = await RaceSubjectChoiceRules.find_one(
                filtered={'race_cid': race_cid, 'cid': choice_rule_cid})
            dimension_rules = race_choice_rule.dimension_rules
            subject_dimension_list = []
            cid_list = list(dimension_rules.keys())
            field_dict = {'record_flag': 1, 'status': STATUS_SUBJECT_DIMENSION_ACTIVE,
                          'parent_cid': {'$in': ['', None]}}
            sub_dict = {'record_flag': 1, 'status': STATUS_SUBJECT_DIMENSION_ACTIVE}
            all_dimension_list = await SubjectDimension.find(field_dict).sort([('ordered', ASCENDING)]).to_list(None)
            if cid_list:
                field_dict['cid'] = {'$in': cid_list}
            if dimension_rules:
                dimension_list = await SubjectDimension.find(field_dict).sort([('ordered', ASCENDING)]).to_list(None)
                for dimension in dimension_list:
                    subject_dimension_dict = {}
                    sub_dict['parent_cid'] = dimension.cid
                    sub_dimension_list = await SubjectDimension.find(sub_dict).sort([('ordered', ASCENDING)]).to_list(
                        None)
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
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_RULES_MANAGEMENT)
    async def post(self, choice_rule_cid):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid and choice_rule_cid:
                race_choice_rule = await RaceSubjectChoiceRules.find_one(
                    filtered={'race_cid': race_cid, 'cid': choice_rule_cid})
                q_total = self.get_argument('q_total', 0)
                dimension_json = self.get_argument('dimension_json')
                dimension_list = None
                if dimension_json:
                    dimension_list = json.loads(dimension_json)
                if q_total and dimension_list:
                    race_choice_rule.dimension_rules = dimension_list[0]
                    race_choice_rule.quantity = int(q_total)
                    race_choice_rule.updated_dt = datetime.datetime.now()
                    race_choice_rule.updated_id = self.current_user.oid
                    is_valid = await task_race_subject_extract.is_valid_extract_rule(race_choice_rule, race_cid)
                    if is_valid:
                        await race_choice_rule.save()
                        RedisCache.hset(race_cid, race_choice_rule.cid, 1)
                        r_dict['code'] = 1
                    else:
                        r_dict['code'] = 2
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceSubjectChoiceruleAddDimensionViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_RULES_MANAGEMENT)
    async def post(self, choice_rule_cid):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid and choice_rule_cid:
                race_choice_rule = await RaceSubjectChoiceRules.find_one(
                    filtered={'race_cid': race_cid, 'cid': choice_rule_cid})
                dimension_rules = race_choice_rule.dimension_rules
                cid = self.get_argument('cid')
                field_dict = {'record_flag': 1, 'status': STATUS_SUBJECT_DIMENSION_ACTIVE,
                              'parent_cid': {'$in': [None, '']}}
                if cid:
                    field_dict['cid'] = cid
                    sub_dict = {'record_flag': 1, 'status': STATUS_SUBJECT_DIMENSION_ACTIVE, 'parent_cid': cid}
                    dimension = await SubjectDimension.find_one(field_dict)
                    sub_list = await SubjectDimension.find(sub_dict).sort([('ordered', ASCENDING)]).to_list(None)
                    html = self.render_string('backoffice/race/choice_rule/add_dimensions.html',
                                              dimension=dimension, sub_list=sub_list, dimension_rules=dimension_rules)
                    r_dict['html'] = html
                else:
                    r_dict['html'] = ''
                r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceSubjectChoiceruleSelectDimensionViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_RULES_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid:
                cid_list = self.get_arguments('cid_list[]')
                field_dict = {'record_flag': 1, 'status': STATUS_SUBJECT_DIMENSION_ACTIVE,
                              'parent_cid': {'$in': [None, '']}}
                if cid_list:
                    field_dict['cid'] = {'$nin': cid_list}
                dimension_list = await SubjectDimension.find(field_dict).sort([('ordered', ASCENDING)]).to_list(None)
                html = self.render_string('backoffice/race/choice_rule/select_view.html',
                                          dimension_list=dimension_list)
                r_dict['html'] = html
                r_dict['code'] = 1
                if len(dimension_list) == 1:
                    r_dict['code'] = 2
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceSubjectChoiceRuleExtractViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_RULES_MANAGEMENT)
    async def post(self, choice_rule_cid):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid:
                race_choice_rule = await RaceSubjectChoiceRules.find_one(
                    filtered={'race_cid': race_cid, 'cid': choice_rule_cid})
                if race_choice_rule:
                    if RedisCache.hget(KEY_PREFIX_EXTRACTING_SUBJECT_RULE, race_choice_rule.cid) in [b'0', 0, None]:
                        RedisCache.hset(race_cid, race_choice_rule.cid, 0)
                        RedisCache.hset(KEY_PREFIX_EXTRACTING_SUBJECT_RULE, race_choice_rule.cid, 1)
                        start_race_extract_subjects.delay(race_cid, race_choice_rule)
                        r_dict['code'] = 1  # 任务已提交
                    else:
                        r_dict['code'] = -1  # 任务在执行
                else:
                    r_dict['code'] = 2
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/backoffice/race/subject/choice/rule/list/', RaceSubjectChoiceruleListViewHandler,
        name='backoffice_race_subject_choice_rule_list'),
    url(r'/backoffice/race/subject/choice/rule/add/', RaceSubjectChoiceruleAddViewHandler,
        name='backoffice_race_subject_choice_rule_add'),
    url(r'/backoffice/race/subject/choice/rule/edit/([0-9a-zA-Z_]+)/', RaceSubjectChoiceruleEditViewHandler,
        name='backoffice_race_subject_choice_rule_edit'),
    url(r'/backoffice/race/subject/choice/rule/status_switch/([0-9a-zA-Z_]+)/',
        RaceSubjectChoiceruleStatusSwitchViewHandler,
        name='backoffice_race_subject_choice_rule_status_switch'),
    url(r'/backoffice/race/subject/choice/rule/batch_operate/', RaceSubjectChoiceruleBatchOperateViewHandler,
        name='backoffice_race_subject_choice_rule_batch_operate'),
    url(r'/backoffice/race/subject/choice/rule/delete/([0-9a-zA-Z_]+)/', RaceSubjectChoiceruleDeleteViewHandler,
        name='backoffice_race_subject_choice_rule_delete'),
    url(r'/backoffice/race/subject/choice/rule/setting/([0-9a-zA-Z_]+)/', RaceSubjectChoiceruleSettingViewHandler,
        name='backoffice_race_subject_choice_rule_setting'),
    url(r'/backoffice/race/subject/choice/rule/add/dimension/([0-9a-zA-Z_]+)/',
        RaceSubjectChoiceruleAddDimensionViewHandler,
        name='backoffice_race_subject_choice_rule_add_dimension'),
    url(r'/backoffice/race/subject/choice/rule/select/dimension/', RaceSubjectChoiceruleSelectDimensionViewHandler,
        name='backoffice_race_subject_choice_rule_select_dimension'),
    url(r'/backoffice/race/subject/choice/rule/extract/([0-9a-zA-Z_]+)/', RaceSubjectChoiceRuleExtractViewHandler,
        name='backoffice_race_subject_choice_rule_extract'),
]
