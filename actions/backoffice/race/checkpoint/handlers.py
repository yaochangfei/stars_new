#!/usr/bin/python
# -*- coding:utf-8 -*-

import datetime
import traceback

from pymongo import UpdateOne
from tornado.web import url

from actions.backoffice.race.utils import get_menu
from commons.page_utils import Paging
from db import STATUS_GAME_CHECK_POINT_ACTIVE, STATUS_GAME_CHECK_POINT_INACTIVE, STATUS_SUBJECT_CHOICE_RULE_ACTIVE, \
    STATUS_ACTIVE
from db.models import RaceGameCheckPoint, RaceSubjectChoiceRules, RedPacketRule
from enums import PERMISSION_TYPE_MINIAPP_RACE_LEVEL_MANAGEMENT
from logger import log_utils
from motorengine.stages import MatchStage, LookupStage
from web import decorators
from web.base import BaseHandler

logger = log_utils.get_logging()


class RaceGameChackPointListViewHandler(BaseHandler):
    """
    游戏关卡列表
    """

    @decorators.render_template('backoffice/race/checkpoint/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_LEVEL_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        if race_cid:
            query_params = {'record_flag': 1, 'race_cid': race_cid}
            index = self.get_argument('index', '')
            refer_index = index  # index在前端可能是个关键字,模板语言解析不了
            if index:
                query_params['$or'] = [
                    {"index": int(index)}
                ]
            r_look_stage = LookupStage(RaceSubjectChoiceRules, 'rule_cid', 'cid', 'rule_list')
            # 分页 START
            per_page_quantity = int(self.get_argument('per_page_quantity', 10))
            to_page_num = int(self.get_argument('page', 1))
            page_url = '%s?race_cid=%s&page=$page&per_page_quantity=%s&index=%s' % (
                self.reverse_url("backoffice_race_game_checkpoint_list"), race_cid, per_page_quantity, index)
            paging = Paging(page_url, RaceGameCheckPoint, pipeline_stages=[r_look_stage], current_page=to_page_num,
                            items_per_page=per_page_quantity,
                            sort=['index'], **query_params)
            await paging.pager()
            # 分页 END
        return locals()


class RaceGameChackPointAddViewHandler(BaseHandler):
    """
    新增关卡
    """

    @decorators.render_template('backoffice/race/checkpoint/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_LEVEL_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        if race_cid:
            race_subject_choice_rules_list = await RaceSubjectChoiceRules.find(
                dict(race_cid=race_cid, record_flag=1, status=STATUS_SUBJECT_CHOICE_RULE_ACTIVE)).to_list(None)
            red_rule_list = await RedPacketRule.find(
                dict(race_cid=race_cid, record_flag=1, status=STATUS_ACTIVE)).to_list(None)
            game = await RaceGameCheckPoint.find().to_list(None)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_LEVEL_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        game_checkpoint_id = None
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid:
                index = self.get_argument('index', None)
                alias = self.get_argument('alias', None)
                unlock_quantity = self.get_argument('unlock_quantity', None)
                rule_cid = self.get_argument('rule_cid', None)
                #  红包规则
                redpkt_rule_cid = self.get_argument('red_rule', None)
                rule_subject_quantity = self.get_argument('rule_quantity')
                comment = self.get_argument('comment', None)
                status = self.get_argument('status', None)  # 状态
                answer_limit_quantity = self.get_argument('answer_limit_quantity', '')
                if index and unlock_quantity and rule_subject_quantity and rule_cid:
                    if int(unlock_quantity) > int(rule_subject_quantity):
                        r_dict['code'] = -8
                    else:
                        r_count = await RaceGameCheckPoint.count(
                            dict(race_cid=race_cid, record_flag=1, index=int(index)))
                        if r_count > 0:
                            r_dict['code'] = -6
                        else:
                            if status == 'on':
                                status = STATUS_GAME_CHECK_POINT_ACTIVE
                            else:
                                status = STATUS_GAME_CHECK_POINT_INACTIVE
                            race_game_checkpoint = RaceGameCheckPoint(index=int(index),
                                                                      unlock_quantity=int(unlock_quantity),
                                                                      rule_cid=rule_cid,
                                                                      redpkt_rule_cid=redpkt_rule_cid)
                            race_game_checkpoint.alias = alias
                            race_game_checkpoint.race_cid = race_cid
                            race_game_checkpoint.status = status
                            race_game_checkpoint.comment = comment
                            if answer_limit_quantity:
                                race_game_checkpoint.answer_limit_quantity = answer_limit_quantity

                            race_game_checkpoint.created_id = self.current_user.oid
                            race_game_checkpoint.updated_id = self.current_user.oid
                            game_checkpoint_id = await race_game_checkpoint.save()

                            r_dict['code'] = 1
                else:
                    if not index:
                        r_dict['code'] = -1
                    if not unlock_quantity:
                        r_dict['code'] = -3
                    if not rule_cid:
                        r_dict['code'] = -5
        except RuntimeError:
            if game_checkpoint_id:
                game_checkpoint = await RaceGameCheckPoint.get_by_id(game_checkpoint_id)
                if game_checkpoint:
                    await RaceGameCheckPoint.delete_by_ids([game_checkpoint.oid])
            logger.error(traceback.format_exc())
        return r_dict


class RaceGameChackPointEditViewHandler(BaseHandler):
    """
    编辑关卡
    """

    @decorators.render_template('backoffice/race/checkpoint/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_LEVEL_MANAGEMENT)
    async def get(self, game_checkpoint_cid):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        if race_cid:
            if game_checkpoint_cid:
                match = MatchStage(
                    {'race_cid': race_cid, 'cid': game_checkpoint_cid})
                lookup_rules = LookupStage(RaceSubjectChoiceRules, 'rule_cid', 'cid', 'subject_choice_rules_list')
                lookup_red_rule = LookupStage(RedPacketRule, 'redpkt_rule_cid', 'cid', 'red_rule_list')
                race_game_checkpoint_list = await RaceGameCheckPoint.aggregate([match, lookup_rules]).to_list(None)
                #  关卡和红包规则关联在一起
                race_red_rule_list = await RaceGameCheckPoint.aggregate([match, lookup_red_rule]).to_list(None)
                race_subject_choice_rules_list = await RaceSubjectChoiceRules.find(
                    dict(race_cid=race_cid, status=STATUS_SUBJECT_CHOICE_RULE_ACTIVE)).to_list(None)
                red_rule_list = await RedPacketRule.find(
                    dict(race_cid=race_cid, record_flag=1, status=STATUS_ACTIVE)).to_list(None)
                game_checkpoint = None
                choice_rule = None
                if race_game_checkpoint_list:
                    game_checkpoint = race_game_checkpoint_list[0]
                    if game_checkpoint.subject_choice_rules_list:
                        choice_rule = game_checkpoint.subject_choice_rules_list[0]
                rule_cid = ''
                if race_red_rule_list:
                    red_rule = race_red_rule_list[0]
                    if red_rule.red_rule_list:
                        rule_cid = red_rule.red_rule_list[0]
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_LEVEL_MANAGEMENT)
    async def post(self, game_checkpoint_cid):
        r_dict = {'code': 0}
        game_checkpoint_id = None
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid and game_checkpoint_cid:
                race_game_checkpoint = await RaceGameCheckPoint.find_one(filtered={'cid': game_checkpoint_cid})
                if race_game_checkpoint:
                    index = self.get_argument('index', None)
                    alias = self.get_argument('alias', None)
                    unlock_quantity = self.get_argument('unlock_quantity', None)
                    rule_cid = self.get_argument('rule_cid', None)
                    #  红包规则
                    redpkt_rule_cid = self.get_argument('red_rule', None)
                    rule_subject_quantity = self.get_argument('rule_quantity')
                    comment = self.get_argument('comment', None)
                    status = self.get_argument('status', None)  # 状态
                    answer_limit_quantity = self.get_argument('answer_limit_quantity', '')
                    if index and unlock_quantity and rule_subject_quantity and rule_cid:
                        if int(unlock_quantity) > int(rule_subject_quantity):
                            r_dict['code'] = -8
                        else:
                            r_count = await RaceGameCheckPoint.count(
                                dict(race_cid=race_cid, index=int(index), cid={'$ne': game_checkpoint_cid}))
                            if r_count > 0:
                                r_dict['code'] = -6
                            else:
                                if status == 'on':
                                    status = STATUS_GAME_CHECK_POINT_ACTIVE
                                else:
                                    status = STATUS_GAME_CHECK_POINT_INACTIVE
                                race_game_checkpoint.index = int(index)
                                race_game_checkpoint.alias = alias
                                race_game_checkpoint.unlock_quantity = int(unlock_quantity)
                                race_game_checkpoint.rule_cid = rule_cid
                                race_game_checkpoint.redpkt_rule_cid = redpkt_rule_cid
                                race_game_checkpoint.status = status
                                race_game_checkpoint.comment = comment
                                if answer_limit_quantity:
                                    race_game_checkpoint.answer_limit_quantity = answer_limit_quantity
                                race_game_checkpoint.created_id = self.current_user.oid
                                race_game_checkpoint.updated_id = self.current_user.oid
                                game_checkpoint_id = await race_game_checkpoint.save()
                                r_dict['code'] = 1
                    else:
                        if not index:
                            r_dict['code'] = -1
                        if not unlock_quantity:
                            r_dict['code'] = -3
                        if not rule_cid:
                            r_dict['code'] = -5
        except Exception:
            if game_checkpoint_id:
                await RaceGameCheckPoint.delete_by_ids(game_checkpoint_id)
            logger.error(traceback.format_exc())
        return r_dict


class RaceGameChackPointDeleteViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_LEVEL_MANAGEMENT)
    async def post(self, game_checkpoint_cid):
        race_cid = self.get_argument('race_cid', '')
        r_dict = {'code': 0}
        try:
            if race_cid:
                race_game_checkpoint = await RaceGameCheckPoint.find_one(filtered={'cid': game_checkpoint_cid})
                await race_game_checkpoint.delete()
                r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceGameChackPointStatusSwitchViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_LEVEL_MANAGEMENT)
    async def post(self, game_checkpoint_cid):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid:
                status = self.get_argument('status', False)
                if status == 'true':
                    status = STATUS_GAME_CHECK_POINT_ACTIVE
                else:
                    status = STATUS_GAME_CHECK_POINT_INACTIVE
                race_game_checkpoint = await RaceGameCheckPoint.find_one(filtered={'cid': game_checkpoint_cid})
                if race_game_checkpoint:
                    race_game_checkpoint.status = status
                    race_game_checkpoint.updated_dt = datetime.datetime.now()
                    race_game_checkpoint.updated_id = self.current_user.oid
                    await race_game_checkpoint.save()
                    r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceGameChackPointBatchOperationViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_LEVEL_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid:
                game_checkpoint_cid_list = self.get_body_arguments('game_checkpoint_cid_list[]', [])
                if game_checkpoint_cid_list:
                    operate = self.get_argument('operate', None)
                    if operate is not None:
                        if int(operate) == 1:
                            update_requests = []
                            for game_checkpoint_cid in game_checkpoint_cid_list:
                                update_requests.append(UpdateOne({'cid': game_checkpoint_cid},
                                                                 {'$set': {'status': STATUS_GAME_CHECK_POINT_ACTIVE,
                                                                           'updated_dt': datetime.datetime.now(),
                                                                           'updated_id': self.current_user.oid}}))
                            await RaceGameCheckPoint.update_many(update_requests)
                        elif int(operate) == 0:
                            update_requests = []
                            for game_checkpoint_cid in game_checkpoint_cid_list:
                                update_requests.append(UpdateOne({'cid': game_checkpoint_cid},
                                                                 {'$set': {'status': STATUS_GAME_CHECK_POINT_INACTIVE,
                                                                           'updated_dt': datetime.datetime.now(),
                                                                           'updated_id': self.current_user.oid}}))
                            await RaceGameCheckPoint.update_many(update_requests)
                        elif int(operate) == -1:
                            await RaceGameCheckPoint.delete_many({'cid': {'$in': game_checkpoint_cid_list}})
                r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/backoffice/race/game_checkpoint/list/', RaceGameChackPointListViewHandler,
        name='backoffice_race_game_checkpoint_list'),
    url(r'/backoffice/race/game_checkpoint/add/', RaceGameChackPointAddViewHandler,
        name='backoffice_race_game_checkpoint_add'),
    url(r'/backoffice/race/game_checkpoint/edit/([0-9a-zA-Z_]+)/', RaceGameChackPointEditViewHandler,
        name='backoffice_race_game_checkpoint_edit'),
    url(r'/backoffice/race/game_checkpoint/delete/([0-9a-zA-Z_]+)/', RaceGameChackPointDeleteViewHandler,
        name='backoffice_race_game_checkpoint_delete'),
    url(r'/backoffice/race/game_checkpoint/status_switch/([0-9a-zA-Z_]+)/', RaceGameChackPointStatusSwitchViewHandler,
        name='backoffice_race_game_checkpoint_status_switch'),
    url(r'/backoffice/race/game_checkpoint/batch_operate/', RaceGameChackPointBatchOperationViewHandler,
        name='backoffice_race_game_checkpoint_batch_operate'),

]
