import json
import traceback
from collections import deque
from json import JSONDecodeError

from pymongo import UpdateOne
from tornado.web import url
import time
from actions.backoffice.race.redpkt_rule.utils import generate_awards_by_config
from actions.backoffice.race.utils import get_menu
from commons.page_utils import Paging
from db import STATUS_ACTIVE, STATUS_INACTIVE, CATEGORY_REDPACKET_RULE_LOTTERY, CATEGORY_REDPACKET_RULE_DIRECT, \
    STATUS_REDPACKET_AWARDED, CATEGORY_REDPACKET_RULE_DICT
from db.models import RedPacketRule, RedPacketItemSetting, RedPacketConf, RedPacketBasicSetting, RedPacketEntry, Race, \
    RedPacketBox, Member, RaceGameCheckPoint
from enums import PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT
from logger import log_utils
from motorengine import DESC
from motorengine.stages import LookupStage, MatchStage, SortStage, ProjectStage
from motorengine.stages.group_stage import GroupStage
from web import BaseHandler, decorators

logger = log_utils.get_logging()


class RedPacketRuleListViewHandler(BaseHandler):
    """
    红包规则列表页面
    """

    @decorators.render_template('backoffice/race/redpkt_rule/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        title = self.get_argument('title', '')
        code = self.get_argument('code', '')

        query_params = {'race_cid': race_cid}
        if title:
            query_params['title'] = {'$regex': title, '$options': 'i'}
        code = self.get_argument('code', '')
        if code:
            query_params['code'] = {'$regex': code, '$options': 'i'}

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))

        page_url = '%s?page=$page&per_page_quantity=%s&code=%s&title=%s' % (
            self.reverse_url("backoffice_race_redpkt_rule_list"), per_page_quantity, code, title)

        paging = Paging(page_url, RedPacketRule, current_page=to_page_num, items_per_page=per_page_quantity,
                        left_pipeline_stages=[LookupStage(RedPacketItemSetting, 'cid', 'rule_cid', 'lottery_setting'),
                                              LookupStage(RedPacketConf, 'cid', 'rule_cid', 'redpacket_conf')],
                        sort=['-updated_dt'], **query_params)

        await paging.pager()
        return locals()


class RedPacketRuleAddViewHandler(BaseHandler):
    """
    新增红包规则
    """

    @decorators.render_template('backoffice/race/redpkt_rule/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def post(self):
        ret_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        code = self.get_argument('code', '')
        title = self.get_argument('title', '')
        category = self.get_argument('category', '')
        comment = self.get_argument('comment', '')
        status = self.get_argument('status', '')

        if not code:
            ret_dict['code'] = -1
            return ret_dict

        if not title:
            ret_dict['code'] = -2
            return ret_dict

        if not category:
            ret_dict['code'] = -3
            return ret_dict

        try:
            rule = await RedPacketRule.find_one({'race_cid': race_cid, 'code': code})
            if rule:
                ret_dict['code'] = -4
                return ret_dict

            await RedPacketRule(race_cid=race_cid, code=code, title=title, category=int(category), comment=comment,
                                status=STATUS_ACTIVE if status == 'true' else STATUS_INACTIVE).save()
            ret_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())

        return ret_dict


class RedPacketRuleEditViewHandler(BaseHandler):
    """
    编辑红包规则
    """

    @decorators.render_template('backoffice/race/redpkt_rule/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def get(self, rule_cid):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        rule = await RedPacketRule.find_one({'cid': rule_cid})

        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def post(self, rule_cid):
        ret_dict = {'code': 0}
        code = self.get_argument('code', '')
        title = self.get_argument('title', '')
        category = self.get_argument('category', '')
        comment = self.get_argument('comment', '')
        status = self.get_argument('status', '')

        if not code:
            ret_dict['code'] = -1
            return ret_dict

        if not title:
            ret_dict['code'] = -2
            return ret_dict

        if not category:
            ret_dict['code'] = -3
            return ret_dict

        try:
            rule = await RedPacketRule.find_one({'cid': rule_cid})
            if not rule:
                ret_dict['code'] = -4
                return ret_dict

            rule.code = code
            rule.title = title
            rule.category = int(category)
            rule.comment = comment
            rule.status = STATUS_ACTIVE if status == 'true' else STATUS_INACTIVE
            await rule.save()

            ret_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())

        return ret_dict


class RedPacketRuleDeleteHandler(BaseHandler):
    """
    删除红包规则
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def post(self):
        ret_dict = {'code': 0}
        rule_cid = self.get_argument('rule_cid', '')
        if not rule_cid:
            ret_dict['code'] = -1
            return ret_dict

        try:
            rule = await RedPacketRule.find_one({'cid': rule_cid})
            if not rule:
                ret_dict['code'] = -2
                return ret_dict

            await RedPacketBasicSetting.delete_many({'rule_cid': rule_cid})
            await RedPacketItemSetting.delete_many({'rule_cid': rule_cid})
            await RedPacketConf.delete_many({'rule_cid': rule_cid})
            await rule.delete()
            ret_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return ret_dict


class RedPacketRuleSwitchHandler(BaseHandler):
    """
    更改红包规则状态
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def post(self):
        ret_dict = {'code': 0}
        rule_cid = self.get_argument('rule_cid', '')
        target_status = self.get_argument('target_status', '')
        if not rule_cid:
            ret_dict['code'] = -1
            return ret_dict

        try:
            rule = await RedPacketRule.find_one({'cid': rule_cid})
            if not rule:
                ret_dict['code'] = -2
                return ret_dict

            rule.status = STATUS_ACTIVE if target_status == 'true' else STATUS_INACTIVE
            await rule.save()
            ret_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return ret_dict


class RedPacketRuleBatchOperationHandler(BaseHandler):
    """
    批量操作红包规则
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def post(self):
        ret_dict = {'code': 0}
        operate = self.get_argument('operate', '')
        rule_json = self.get_argument('rule_cids', '')
        if not rule_json:
            ret_dict['code'] = -1
            return ret_dict

        try:
            operate = int(operate)
            rule_cids = json.loads(rule_json)

            if operate == -1:
                await RedPacketRule.delete_many({'cid': {'$in': rule_cids}})
                await RedPacketBasicSetting.delete_many({'rule_cid': {'$in': rule_cids}})
                await RedPacketItemSetting.delete_many({'rule_cid': {'$in': rule_cids}})
                await RedPacketConf.delete_many({'rule_cid': {'$in': rule_cids}})

            if operate == 0:
                await RedPacketRule.update_many(
                    [UpdateOne({'cid': cid}, {'$set': {'status': STATUS_INACTIVE}}) for cid in rule_cids])

            if operate == 1:
                await RedPacketRule.update_many(
                    [UpdateOne({'cid': cid}, {'$set': {'status': STATUS_ACTIVE}}) for cid in rule_cids])

            ret_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return ret_dict


class RedPacketRuleConfigHandler(BaseHandler):
    """
    红包配置
    """

    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def get(self):
        try:
            race_cid = self.get_argument('race_cid', '')
            rule_cid = self.get_argument('rule_cid', '')
            if not rule_cid:
                raise ValueError('There is no rule_cid in RedPacketRuleConfigHandler.get() .')

            rule = await RedPacketRule.find_one({'cid': rule_cid, 'record_flag': 1})
            if rule.category == CATEGORY_REDPACKET_RULE_LOTTERY:
                self.redirect(self.reverse_url('backoffice_race_lottery_setting') + '?race_cid=%s&rule_cid=%s' % (
                    race_cid, rule_cid))
                return

            if rule.category == CATEGORY_REDPACKET_RULE_DIRECT:
                self.redirect(self.reverse_url('backoffice_race_redpkt_direct') + '?race_cid=%s&rule_cid=%s' % (
                    race_cid, rule_cid))
                return
        except Exception:
            logger.error(traceback.format_exc())


class RedPacketDirectHandler(BaseHandler):
    """
    直接发放
    """

    @decorators.render_template('backoffice/race/redpkt_rule/red_packet_direct.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        rule_cid = self.get_argument('rule_cid', '')
        red_conf = ''
        red_conf = await RedPacketConf.find_one({'race_cid': race_cid, 'rule_cid': rule_cid, 'record_flag': 1})

        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def post(self):
        # 红包的类型
        r_dict = {'code': 0}
        try:
            # 红包的类型
            red_category = self.get_argument('red_form', '')
            race_cid = self.get_argument('race_cid', '')
            # 红包规则cid
            rule_cid = self.get_argument('rule_cid', '')
            account = self.get_argument('account', '')
            count = self.get_argument('count', '')
            top_limit = self.get_argument('top_limit', '')
            bless_language = self.get_argument('bless_language', '')
            over_limit = self.get_argument('over_limit', '')
            if red_category and race_cid and account and count and top_limit and bless_language and over_limit and rule_cid:
                old_red_packet_conf = await RedPacketConf.find_one(
                    {'race_cid': race_cid, 'rule_cid': rule_cid, 'record_flag': 1})
                red_packet_conf = RedPacketConf(race_cid=race_cid, rule_cid=rule_cid)
                red_packet_conf.category = int(red_category)
                red_packet_conf.top_limit = int(top_limit)
                red_packet_conf.quantity = int(count)
                red_packet_conf.total_amount = float(account)
                red_packet_conf.amount = float(account) / int(count)
                red_packet_conf.msg = bless_language
                red_packet_conf.over_msg = over_limit
                red_packet_conf_oid = await red_packet_conf.save()
                #  当新配置保存好了就可以删除旧的配置
                if red_packet_conf_oid and old_red_packet_conf:
                    await old_red_packet_conf.delete()

                await generate_awards_by_config(red_packet_conf)
                r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RedPacketRuleModifyCheckHandler(BaseHandler):
    """
    检查红包规则是否可以被修改
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def post(self):
        ret_dict = {'code': 0}
        rule_cid_json = self.get_argument('rule_cid', '')

        if not rule_cid_json:
            ret_dict['code'] = -1
            return ret_dict

        try:
            rule_cids = json.loads(rule_cid_json)
        except TypeError:
            rule_cids = [rule_cid_json]
        except JSONDecodeError:
            rule_cids = [rule_cid_json]

        try:
            item_cids = await RedPacketItemSetting.distinct('cid', {'rule_cid': {'$in': rule_cids}})
            if not item_cids:
                conf = await RedPacketConf.find_one({'rule_cid': {'$in': rule_cids}})
                if conf:
                    item_cids.append(conf.cid)

            count = await RedPacketEntry.count({'open_id': {'$ne': None}, 'award_cid': {'$in': item_cids}})
            if count > 0:
                ret_dict['can_modify'] = False
            else:
                ret_dict['can_modify'] = True
        except Exception:
            logger.error(traceback.format_exc())
        return ret_dict


class RedPacketRuleGenerateAwardsHandler(BaseHandler):
    """
    生成奖池
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def post(self):
        res_dict = {'code': 0}
        rule_cid = self.get_argument('rule_cid')
        if not rule_cid:
            res_dict['code'] = -1
            return res_dict

        rule = await RedPacketRule.get_by_cid(rule_cid)
        if not rule:
            res_dict['code'] = -2
            return res_dict

        if rule.category == CATEGORY_REDPACKET_RULE_LOTTERY:
            settings = await RedPacketItemSetting.find({'rule_cid': rule.cid, 'record_flag': 1})

        if rule.category == CATEGORY_REDPACKET_RULE_DIRECT:
            config = await RedPacketConf.find({'rule_cid': rule.cid, 'record_flag': 1})


class RedPacketSeeLotteryResultHandler(BaseHandler):
    """
    查看抽奖结果
    """

    @decorators.render_template('backoffice/race/redpkt_rule/lottery_result.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_LOTTERY_DRAW_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        put_out_form = self.get_argument('put_out_form', '')
        red_packet_item = self.get_argument('red_packet_item', '')
        if race_cid:
            # 抽奖总览
            race = await Race.find_one({'cid': race_cid, 'record_flag': 1})
            #  找到该活动下面的所有rule_cid
            #  已经发放的红包个数
            already_put_red_packet_amount_list = await RedPacketBox.aggregate([MatchStage(
                {'race_cid': race_cid,
                 'draw_status': STATUS_REDPACKET_AWARDED,
                 'member_cid': {'$ne': None},
                 'award_cid': {'$ne': None},
                 'record_flag': 1}), GroupStage(None, sum={'$sum': '$award_amount'},
                                                quantity={'$sum': 1})]).to_list(None)
            #  抽奖详情
            kw_word = self.get_argument('kw_word', '')
            #  奖项标题
            item_title = self.get_argument('item_title', '')
            stage_list = [
                LookupStage(Member, 'member_cid', 'cid', 'member_list'),
                LookupStage(RaceGameCheckPoint, 'checkpoint_cid', 'cid', 'checkpoint_list'),
                LookupStage(RedPacketItemSetting, 'award_cid', 'cid', 'setting_list'),
                LookupStage(RedPacketConf, 'award_cid', 'cid', 'conf_list'),
                ProjectStage(**{
                    'member_cid': '$member_cid',
                    'nick_name': {'$arrayElemAt': ['$member_list.nick_name', 0]},
                    'checkpoint': {'$arrayElemAt': ['$checkpoint_list.alias', 0]},
                    'category': {'$cond': {'if': {'$ne': ['$setting_list', list()]}, 'then': '抽奖形式', 'else': '直接发放'}},
                    'detail': {'$cond': {'if': {'$ne': ['$setting_list', list()]},
                                         'then': {'$arrayElemAt': ['$setting_list.title', 0]},
                                         'else': {'$arrayElemAt': ['$conf_list.category', 0]}}},
                    'award_amount': '$award_amount',
                    'draw_dt': '$draw_dt',
                    'award_cid': '$award_cid'
                }),
            ]
            query_dict = {}
            if kw_word:
                query_dict['$or'] = [
                    {'nick_name': {'$regex': kw_word, '$options': 'i'}},
                    {'member_cid': {'$regex': kw_word, '$options': 'i'}},
                    {'checkpoint': {'$regex': kw_word, '$options': 'i'}},
                ]
            if put_out_form:
                query_dict['category'] = put_out_form
            if red_packet_item and put_out_form != CATEGORY_REDPACKET_RULE_DICT.get(CATEGORY_REDPACKET_RULE_DIRECT):
                query_dict['detail'] = red_packet_item
            query = MatchStage(query_dict)
            stage_list.append(query)
            query_match_dict = {
                "race_cid": race_cid,
                'draw_status': STATUS_REDPACKET_AWARDED,
                'member_cid': {'$ne': None},
                'award_cid': {'$ne': None},
                'record_flag': 1}
            per_page_quantity = int(self.get_argument('per_page_quantity', 10))
            to_page_num = int(self.get_argument('page', 1))
            page_url = '%s?page=$page&per_page_quantity=%s&race_cid=%s&kw_name=%s&put_out_form=%s' % (
                self.reverse_url("backoffice_race_redpkt_rule_see_result"), per_page_quantity, race_cid, kw_word,
                put_out_form)
            paging = Paging(page_url, RedPacketBox, current_page=to_page_num,
                            pipeline_stages=stage_list, sort=['award_amount'],
                            items_per_page=per_page_quantity, **query_match_dict)
            await paging.pager()

            #  抽奖形式的奖项列表
            lottery_item_list = await RedPacketItemSetting.distinct('title', {'race_cid': race_cid, 'record_flag': 1})
        return locals()

URL_MAPPING_LIST = [
    url('/backoffice/race/redpkt_rule/list/', RedPacketRuleListViewHandler, name='backoffice_race_redpkt_rule_list'),
    url('/backoffice/race/redpkt_rule/add/', RedPacketRuleAddViewHandler, name='backoffice_race_redpkt_rule_add'),
    url('/backoffice/race/redpkt_rule/edit/([0-9a-zA-Z_]+)/', RedPacketRuleEditViewHandler,
        name='backoffice_race_redpkt_rule_edit'),
    url('/backoffice/race/redpkt_rule/delete/', RedPacketRuleDeleteHandler, name='backoffice_race_redpkt_rule_delete'),
    url('/backoffice/race/redpkt_rule/switch/', RedPacketRuleSwitchHandler, name='backoffice_race_redpkt_rule_switch'),
    url('/backoffice/race/redpkt_rule/batch_op/', RedPacketRuleBatchOperationHandler,
        name='backoffice_race_redpkt_rule_batch_op'),
    url('/backoffice/race/redpkt_rule/config/', RedPacketRuleConfigHandler, name='backoffice_race_redpkt_rule_config'),
    url('/backoffice/race/redpkt_rule/direct/', RedPacketDirectHandler, name='backoffice_race_redpkt_direct'),
    url('/backoffice/race/redpkt_rule/modify/check/', RedPacketRuleModifyCheckHandler,
        name='backoffice_race_redpkt_rule_modify_check'),
    url('/backoffice/race/redpkt_rule/see/result/', RedPacketSeeLotteryResultHandler,
        name='backoffice_race_redpkt_rule_see_result'),
]
