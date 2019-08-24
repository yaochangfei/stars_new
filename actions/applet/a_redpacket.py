#!/usr/bin/python


import asyncio
import json
import time
import traceback
from datetime import datetime
from json import JSONDecodeError

from actions.applet import find_member_by_open_id
from actions.applet.utils import async_request, get_lottery_table, async_add_notice, generate_rid, deal_param, \
    parse_rid, \
    clear_lottery_notice
from caches.redis_utils import RedisCache
from db import RESULT_RACE_LOTTERY_LOSE, RESULT_RACE_LOTTERY_WIN, \
    STATUS_REDPACKET_NOT_AWARDED, STATUS_REDPACKET_AWARDED, REDPACKET_REQUEST_STATUS_ERROR, \
    REDPACKET_REQUEST_STATUS_EMPTY, REDPACKET_REQUEST_STATUS_SUCCESS, \
    STATUS_READPACKET_ISSUE_SUCCESS, CATEGORY_NOTICE_AWARD, STATUS_NOTICE_UNREAD, STATUS_NOTICE_READ, TYPE_MSG_DRAW, \
    RESULT_RACE_LOTTERY_OUT_OF_TIME, RESULT_RACE_LOTTERY_LOSE_LATE, STATUS_ACTIVE, STATUS_GAME_CHECK_POINT_ACTIVE, \
    CATEGORY_REDPACKET_RULE_LOTTERY, CATEGORY_REDPACKET_RULE_DIRECT, STATUS_RESULT_CHECK_POINT_WIN
from db.models import RedPacketItemSetting, RedPacketLotteryHistory, \
    RedPacketBasicSetting, MemberNotice, Race, AdministrativeDivision, RedPacketRule, RaceGameCheckPoint, RedPacketBox, \
    MemberCheckPointHistory
from enums import KEY_RACE_LOTTERY_RESULT
from logger import log_utils
from pymongo import ReadPreference
from settings import REDPACKET_PLATFORM_AUTH_URL, REDPACKET_PLATFORM_HOST
from tasks.instances.task_get_lottery_result import get_lottery_result
from tasks.instances.task_lottery_queuing import start_lottery_queuing
from tornado.web import url
from web import WechatAppletHandler, decorators

logger = log_utils.get_logging('a_redpacket', 'a_redpacket.log')


class AppletLotteryTurntableGet(WechatAppletHandler):
    """
    获取抽奖转盘
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0, 'lottery_history': False, 'explain': '最终解释权归科普所所有'}
        open_id = self.get_i_argument('open_id')
        race_cid = self.get_i_argument('race_cid')
        checkpoint_cid = self.get_i_argument('checkpoint_cid')
        if not (open_id and race_cid and checkpoint_cid):
            r_dict['code'] = 1001
            return r_dict

        try:
            checkpoint = await RaceGameCheckPoint.find_one(
                {'cid': checkpoint_cid, 'status': STATUS_GAME_CHECK_POINT_ACTIVE, 'record_flag': 1})

            rule_cid = checkpoint.redpkt_rule_cid
            redpkt_rule = await RedPacketRule.find_one({'cid': rule_cid, 'status': STATUS_ACTIVE})
            if not redpkt_rule:
                r_dict['code'] = 1002
                return r_dict

            basic = await RedPacketBasicSetting.find_one({'race_cid': race_cid, 'rule_cid': rule_cid})
            item_table, err_index = await get_lottery_table(rule_cid)
            r_dict['prize_list'] = item_table
            r_dict['err_index'] = err_index
            r_dict['rule'] = basic.guide if basic else ''

            lottery_history = await RedPacketLotteryHistory.find_one(
                {'open_id': open_id, 'race_cid': race_cid, 'rule_cid': rule_cid, 'record_flag': 1})
            if lottery_history:
                r_dict['lottery_history'] = True

            # 最终解释权归科普所所有
            race = await Race.find_one({'cid': race_cid})

            ad_code = race.province_code
            if race.city_code:
                ad_code = race.city_code

            region = await AdministrativeDivision.find_one({'code': ad_code})
            if region:
                r_dict['explain'] = "最终解释权归%s科协所有" % region.title

            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletLotteryLaunch(WechatAppletHandler):
    """
    请求一次抽奖
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id')
        race_cid = self.get_i_argument('race_cid')
        checkpoint_cid = self.get_i_argument('checkpoint_cid')
        if not open_id or not race_cid or not checkpoint_cid:
            r_dict['code'] = 1001
            return r_dict

        member = await find_member_by_open_id(open_id)
        if not member:
            r_dict['code'] = 1002
            return r_dict

        checkpoint = await RaceGameCheckPoint.find_one(
            {'cid': checkpoint_cid, 'status': STATUS_GAME_CHECK_POINT_ACTIVE})
        if not checkpoint:
            r_dict['code'] = 1003
            return r_dict

        #
        # # 检查是否通关
        # is_clear = await is_stage_clear(member, race_cid)
        # if not is_clear:
        #     r_dict['code'] = 1003
        #     return r_dict

        try:
            rule_cid = checkpoint.redpkt_rule_cid
            rule = await RedPacketRule.find_one({'cid': rule_cid})

            async def lottery():
                basic_setting = await RedPacketBasicSetting.find_one({'rule_cid': rule_cid, 'record_flag': 1},
                                                                     read_preference=ReadPreference.PRIMARY)

                prize_list, err_index = await get_lottery_table(rule_cid)

                history = await MemberCheckPointHistory.find_one(
                    {'member_cid': member.cid, 'check_point_cid': checkpoint_cid,
                     'status': STATUS_RESULT_CHECK_POINT_WIN}, read_preference=ReadPreference.PRIMARY)
                if not history:
                    r_dict['code'] = 1005
                    return r_dict

                redpkt_box = await RedPacketBox.find_one(
                    {'member_cid': member.cid, 'checkpoint_cid': checkpoint_cid, 'record_flag': 1})
                if redpkt_box:
                    if redpkt_box.award_cid:
                        item = await RedPacketItemSetting.find_one({'cid': redpkt_box.award_cid})  # 该奖励的配置信息

                        r_dict['result'] = RESULT_RACE_LOTTERY_WIN
                        r_dict['reward_msg'] = '您已经抽过奖了, 获得奖品为[ %s ].' % item.title
                        r_dict['reward_position'] = prize_list.index(item.title)
                        await clear_lottery_notice(member.cid, checkpoint_cid)

                    else:
                        r_dict['result'] = RESULT_RACE_LOTTERY_LOSE
                        r_dict['reward_msg'] = '您已经在此关抽过奖了, 上一次没有中奖'
                        r_dict['reward_position'] = err_index

                    await clear_lottery_notice(member.cid, checkpoint_cid)
                    return r_dict

                result = RedisCache.hget(KEY_RACE_LOTTERY_RESULT.format(checkpoint_cid), member.cid)
                if result is not None:
                    # 数据库被人为清除过
                    r_dict['code'] = 1004
                    return r_dict

                start_lottery_queuing.delay(member.cid, race_cid, rule, checkpoint_cid)
                t1 = time.time()
                while time.time() - t1 <= 5:
                    result = RedisCache.hget(KEY_RACE_LOTTERY_RESULT.format(checkpoint_cid), member.cid)
                    if result:
                        break
                    await asyncio.sleep(1)

                if result is None:
                    r_dict['result'] = RESULT_RACE_LOTTERY_OUT_OF_TIME
                    r_dict['reward_msg'] = '网络异常, 请稍后重新尝试抽奖.'
                    return r_dict

                result = int(result.decode('utf-8'))
                if result == RESULT_RACE_LOTTERY_LOSE:
                    r_dict['result'] = RESULT_RACE_LOTTERY_LOSE
                    r_dict['reward_msg'] = basic_setting.fail_msg
                    r_dict['reward_position'] = err_index

                    await clear_lottery_notice(member.cid, checkpoint_cid)
                    return r_dict

                if result == RESULT_RACE_LOTTERY_LOSE_LATE:
                    r_dict['result'] = RESULT_RACE_LOTTERY_LOSE
                    r_dict['reward_msg'] = basic_setting.over_msg
                    r_dict['reward_position'] = err_index

                    await clear_lottery_notice(member.cid, checkpoint_cid)
                    return r_dict

                if result == RESULT_RACE_LOTTERY_WIN:
                    r_dict['result'] = RESULT_RACE_LOTTERY_WIN
                    redpacket = await RedPacketBox.find_one(
                        {'member_cid': member.cid, 'checkpoint_cid': checkpoint_cid,
                         'draw_status': STATUS_REDPACKET_NOT_AWARDED}, read_preference=ReadPreference.PRIMARY)
                    redpacket_item = await RedPacketItemSetting.find_one({'cid': redpacket.award_cid})

                    r_dict['reward_msg'] = redpacket.award_msg
                    r_dict['reward_position'] = prize_list.index(redpacket_item.title)

                    await async_add_notice(member_cid=member.cid, race_cid=race_cid, checkpoint_cid=checkpoint_cid,
                                           redpkt_box=redpacket, msg_type=TYPE_MSG_DRAW)
                    await clear_lottery_notice(member.cid, checkpoint_cid)
                    return r_dict

            async def deal_normal():
                start_lottery_queuing.delay(member.cid, race_cid, rule, checkpoint_cid)

            r_dict['code'] = 1000
            if rule.category == CATEGORY_REDPACKET_RULE_LOTTERY:
                await lottery()

            if rule.category == CATEGORY_REDPACKET_RULE_DIRECT:
                await deal_normal()

        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletDrawReward(WechatAppletHandler):
    """
    领取奖励
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0, 'pick_url': None, 'rid': None}

        try:
            open_id = self.get_i_argument('open_id')
            checkpoint_cid = self.get_i_argument('checkpoint_cid')

            member = await find_member_by_open_id(open_id)
            if not (open_id and member):
                r_dict['code'] = 1001
                return r_dict

            if not checkpoint_cid:
                r_dict['code'] = 1002
                return r_dict

            redpacket = await RedPacketBox.find_one(
                {'member_cid': member.cid, 'checkpoint_cid': checkpoint_cid,
                 'record_flag': 1}, read_preference=ReadPreference.PRIMARY)
            if not redpacket:
                r_dict['code'] = 1007
                return r_dict

            if redpacket.draw_status == STATUS_REDPACKET_AWARDED:
                notice_list = await MemberNotice.find(
                    {'member_cid': member.cid, 'category': CATEGORY_NOTICE_AWARD, 'checkpoint_cid': checkpoint_cid},
                    read_preference=ReadPreference.PRIMARY).to_list(None)
                for notice in notice_list:
                    if notice.status == STATUS_NOTICE_UNREAD:
                        notice.status = STATUS_NOTICE_READ
                        await notice.save()

                r_dict['code'] = 1006
                logger.info('member_cid [%s], has already picked.' % member.cid)
                return r_dict

            if not redpacket.award_cid:
                # 奖品已经发完
                r_dict['code'] = 1000
                r_dict['tip_msg'] = redpacket.award_msg
                return r_dict

            rid = generate_rid(redpacket.race_cid, member.cid, redpacket.cid)
            data = {
                'rid': rid,
                'pay_amount': redpacket.award_amount * 100,  # 数据库存储单位为(元), 这里需换算为(分)
                'desc': redpacket.award_msg
            }

            race = await Race.get_by_cid(redpacket.race_cid)
            data = deal_param(REDPACKET_PLATFORM_AUTH_URL, method='POST', redpkt_account=race.redpkt_account, **data)

            redpacket.request_dt = datetime.now()
            redpacket.redpkt_rid = rid
            res = await async_request(REDPACKET_PLATFORM_HOST + REDPACKET_PLATFORM_AUTH_URL, method='POST',
                                      data=json.dumps(data))

            res_dict = {}
            try:
                res_dict = json.loads(res)
            except JSONDecodeError:
                pass

            if res_dict.get('code') == 2001:
                redpacket.draw_status = STATUS_REDPACKET_AWARDED
                redpacket.issue_status = STATUS_READPACKET_ISSUE_SUCCESS

                redpacket.sync_save()

                notice_list = MemberNotice.sync_find(
                    {'member_cid': member.cid, 'category': CATEGORY_NOTICE_AWARD, 'status': STATUS_NOTICE_UNREAD,
                     'checkpoint_cid': redpacket.checkpoint_cid, 'record_flag': 1}).to_list(None)

                for notice in notice_list:
                    notice.status = STATUS_NOTICE_READ
                    notice.sync_save()

                logger.error('RedPacket(cid: %s) %s' % (redpacket.cid, res_dict.get('errmsg')))
                r_dict['code'] = 1003
                return r_dict

            if res_dict.get('code') != 0:
                # 红包平台请求错误
                redpacket.request_status = REDPACKET_REQUEST_STATUS_ERROR
                redpacket.error_msg = res_dict.get('errmsg')
                await redpacket.save()

                r_dict['code'] = 1003
                logger.error('request RedPacket Platform failed, reason is %s' % res_dict.get('errmsg'))
                return r_dict

            if res_dict.get('status') == 404:
                # 余额不足
                redpacket.request_status = REDPACKET_REQUEST_STATUS_EMPTY
                redpacket.error_msg = res_dict.get('errmsg')
                await redpacket.save()

                r_dict['code'] = 1004
                return r_dict

            redpacket.request_status = REDPACKET_REQUEST_STATUS_SUCCESS
            redpacket.issue_status = res_dict.get('status')
            redpacket.error_msg = res_dict.get('errmsg')
            await redpacket.save()

            r_dict['pick_url'] = res_dict.get('pick_url')
            r_dict['rid'] = rid
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletQueryAwardResult(WechatAppletHandler):
    """
    查询抽奖结果
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}

        try:
            open_id = self.get_i_argument('open_id')
            rid = self.get_i_argument('rid')
            if not open_id:
                r_dict['code'] = 1001
                return r_dict

            if not rid:
                r_dict['code'] = 1002
                return r_dict

            member = await find_member_by_open_id(open_id)
            _, _, reward_cid = parse_rid(rid)

            get_lottery_result.delay(member, reward_cid, rid)
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/wechat/lottery/table/get/', AppletLotteryTurntableGet, name='wechat_lottery_table_get'),
    url(r'/wechat/lottery/launch/', AppletLotteryLaunch, name='wechat_lottery_launch'),
    url(r'/wechat/lottery/reward/draw/', AppletDrawReward, name='wechat_lottery_reward_draw'),
    url(r'/wechat/lottery/result/query/', AppletQueryAwardResult, name='wechat_lottery_result_query')
]
