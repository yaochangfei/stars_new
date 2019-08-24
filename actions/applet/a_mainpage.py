#! /usr/bin/python

import datetime
import json
import traceback

from actions.applet import find_member_by_open_id
from caches.redis_utils import RedisCache
from db import STATUS_USER_ACTIVE, TYPE_DAN_GRADE_ONE, SOURCE_MEMBER_DIAMOND_NOVICE, \
    SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY, SOURCE_MEMBER_DIAMOND_DICT
from db.enums import SOURCE_MEMBER_DIAMOND_VAULT_REWARD
from db.model_utils import do_diamond_reward
from db.models import Member, MemberGameHistory, VaultDiamondBank, MemberDiamondDetail
from enums import KEY_CACHE_WECHAT_AD_DIVISION, KEY_CACHE_APPLET_ONLINE_MEMBER
from logger import log_utils
from motorengine import DESC
from settings import SITE_ROOT
from tornado.web import url
from web import decorators, WechatAppletHandler
from wechat import wechat_utils
from .utils import get_dan_grade_by_index

logger = log_utils.get_logging('a_mainpage')


class AppletMainPageDetailHandler(WechatAppletHandler):
    """获取主页信息"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id')
        if not open_id:
            r_dict['code'] = 1001
            return r_dict

        try:
            member = await find_member_by_open_id(open_id)
            origin_diamond = member.diamond
            member_quantity = RedisCache.get(KEY_CACHE_APPLET_ONLINE_MEMBER)
            if not member_quantity:
                member_quantity = await Member.count(dict(status=STATUS_USER_ACTIVE, open_id={'$ne': None}))
                RedisCache.set(KEY_CACHE_APPLET_ONLINE_MEMBER, member_quantity, timeout=5 * 60)
            else:
                member_quantity = int(member_quantity)
            r_dict['online_member_count'] = member_quantity
            r_dict['can_friend_share'] = True if (await MemberGameHistory.count(
                {'member_cid': member.cid, 'runaway_index': None})) > 0 else False

            reward_info = []
            if not member.dan_grade:  # 新手奖励
                member.dan_grade = TYPE_DAN_GRADE_ONE
                _, m_diamond = await do_diamond_reward(member, SOURCE_MEMBER_DIAMOND_NOVICE)

                reward_info.append({
                    'title': SOURCE_MEMBER_DIAMOND_DICT.get(SOURCE_MEMBER_DIAMOND_NOVICE),
                    'diamond_num': m_diamond
                })

            # 每日登录奖励
            start_datetime = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=99999)
            count = await MemberDiamondDetail.count({
                "member_cid": member.cid,
                "source": SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY,
                "reward_datetime": {'$lte': end_datetime, '$gte': start_datetime},
            })
            if count == 0:
                _, m_diamond = await do_diamond_reward(member, SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY)

                reward_info.append({
                    'title': SOURCE_MEMBER_DIAMOND_DICT.get(SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY),
                    'diamond_num': m_diamond
                })

            # 排行榜奖励
            rank_reward = await wechat_utils.do_daily_ranking_award(member)
            if rank_reward:
                reward_info.append(rank_reward)

            r_dict['reward_info'] = reward_info
            r_dict['origin_diamond'] = origin_diamond
            r_dict['final_diamond'] = member.diamond
            r_dict['avatar_url'] = member.avatar
            r_dict['dan_grade_title'] = await get_dan_grade_by_index(member.dan_grade)
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletVaultBankAwardHandler(WechatAppletHandler):
    """
    领取金库奖励
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id')
        if not open_id:
            r_dict['code'] = 1001
            return r_dict

        try:
            member = await find_member_by_open_id(open_id)
            if not member:
                r_dict['code'] = 1002
                return r_dict

            vault_bank = await VaultDiamondBank.find_one({"quantity": {'$ne': None}})
            if not vault_bank:
                r_dict['code'] = 1003
                return r_dict

            second_limit = vault_bank.minutes * 60
            start_datetime = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=999)
            count = await MemberDiamondDetail.count({
                "member_cid": member.cid,
                "source": SOURCE_MEMBER_DIAMOND_VAULT_REWARD,
                "reward_datetime": {'$lte': end_datetime, '$gte': start_datetime},
            })

            if count != 0 and 0 < vault_bank.times < count:
                r_dict['code'] = 1004  # 达到领取上限
                return r_dict

            # 最近一次获取奖励的记录
            member_diamond_detail = await MemberDiamondDetail.find(
                {"member_cid": member.cid, "source": SOURCE_MEMBER_DIAMOND_VAULT_REWARD}).sort(
                [('reward_datetime', DESC)]).limit(1).to_list(1)

            if not member_diamond_detail:
                award_member_diamond = vault_bank.quantity
            else:
                member_diamond_detail = member_diamond_detail[0]
                # 距离上一次领取奖励的时间差
                spacing_seconds = (datetime.datetime.now() - member_diamond_detail.reward_datetime).seconds
                if spacing_seconds >= second_limit:
                    award_member_diamond = vault_bank.quantity
                else:
                    need_quantity = (vault_bank.quantity / second_limit) * spacing_seconds  # 获得的奖励数量
                    award_member_diamond = int(need_quantity)

            diamond_detail = MemberDiamondDetail(member_cid=member.cid, diamond=award_member_diamond,
                                                 source=SOURCE_MEMBER_DIAMOND_VAULT_REWARD)
            diamond_detail.reward_datetime = datetime.datetime.now()
            diamond_detail.content = SOURCE_MEMBER_DIAMOND_DICT.get(SOURCE_MEMBER_DIAMOND_VAULT_REWARD)
            await diamond_detail.save()

            member.diamond = member.diamond + award_member_diamond  # +金库奖励的钻石
            member.updated_dt = datetime.datetime.now()
            await member.save()

            r_dict = {
                'code': 1000,
                'remain_seconds': second_limit,
                'total_seconds': second_limit,
                'can_get_diamond': 0,
                'total_diamond': vault_bank.quantity,
                'member_diamond': member.diamond
            }
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletVaultBankSyncHandler(WechatAppletHandler):
    """
    同步金库状态
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id')
        if not open_id:
            r_dict['code'] = 1001
            return r_dict

        try:
            member = await find_member_by_open_id(open_id)
            if not member:
                r_dict['code'] = 1002
                return r_dict

            vault_bank = await VaultDiamondBank.find_one({"quantity": {'$ne': None}})
            if not vault_bank:
                r_dict['code'] = 1003
                return r_dict

            second_limit = vault_bank.minutes * 60
            member_diamond_detail = await MemberDiamondDetail.find(
                {"member_cid": member.cid, "source": SOURCE_MEMBER_DIAMOND_VAULT_REWARD}).sort(
                [('reward_datetime', DESC)]).limit(1).to_list(1)

            if not member_diamond_detail:
                remain_seconds = 0
                can_get_diamond = vault_bank.quantity
            else:
                member_diamond_detail = member_diamond_detail[0]
                spacing_seconds = (datetime.datetime.now() - member_diamond_detail.reward_datetime).seconds
                remain_seconds = second_limit - spacing_seconds
                if remain_seconds <= 0:
                    remain_seconds = 0
                    can_get_diamond = vault_bank.quantity
                else:
                    need_quantity = (vault_bank.quantity / second_limit) * spacing_seconds  # 获得的奖励数量
                    can_get_diamond = int(need_quantity)

            r_dict = {
                'code': 1000,
                'remain_seconds': remain_seconds,
                'total_seconds': second_limit,
                'can_get_diamond': can_get_diamond,
                'total_diamond': vault_bank.quantity,
            }
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletAdministrativeDivisionGetHandler(WechatAppletHandler):
    """
    获取行政区划json数据
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        ret = RedisCache.get(KEY_CACHE_WECHAT_AD_DIVISION)
        if ret:
            ret = json.loads(ret)
            return ret

        ret = {'code': 0, 'province_list': [], 'city_area_dict': {}}
        try:
            with open(SITE_ROOT + '/res/division.json', 'r') as f:
                data = json.load(f)

            data = data.get('division')
            for prov in data:
                p_code = prov.get('code')
                ret['province_list'].append({'code': p_code, 'name': prov.get('name')})
                city_area_dict = ret['city_area_dict'].get(p_code)
                if not city_area_dict:
                    city_area_dict = []

                for city in prov.get('cell'):
                    city_area_dict.append({'code': city.get('code'), 'name': city.get('name')})
                    for dist in city.get('cell'):
                        city_area_dict.append({'code': dist.get('code'), 'name': dist.get('name')})

                ret['city_area_dict'][p_code] = city_area_dict
                ret['code'] = 1

                RedisCache.set(KEY_CACHE_WECHAT_AD_DIVISION, json.dumps(ret))
        except Exception:
            logger.error(traceback.format_exc())

        return ret


URL_MAPPING_LIST = [
    url(r'/wechat/applet/mainpage/detail/', AppletMainPageDetailHandler, name='wechat_applet_mainpage_detail'),
    url(r'/wechat/applet/vault_bank/award/', AppletVaultBankAwardHandler, name='wechat_applet_vault_bank_award'),
    url(r'/wechat/applet/vault_bank/sync/', AppletVaultBankSyncHandler, name='wechat_applet_vault_bank_sync'),
    url(r'/wechat/applet/administrative_division/get/', AppletAdministrativeDivisionGetHandler,
        name='wechat_applet_administrative_division_get')
]
