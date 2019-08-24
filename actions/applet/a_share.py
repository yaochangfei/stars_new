#!/usr/bin/python
# -*- coding:utf-8 -*-
import datetime
import traceback

from actions.applet import find_member_by_open_id
from actions.applet.utils import do_diamond_reward
from db import SOURCE_MEMBER_DIAMOND_DAILY_SHARE_TIMES_LIMIT, SOURCE_MEMBER_DIAMOND_DAILY_SHARE, \
    SOURCE_MEMBER_DIAMOND_DICT
from db.model_utils import get_cache_share_times, set_cache_share_times
from db.models import GameDiamondReward
from logger import log_utils
from web import decorators, WechatAppletHandler

logger = log_utils.get_logging('a_miniapp')


class MiniappShareAwardViewHandler(WechatAppletHandler):
    """ 分享好友奖励会员钻石"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        try:
            if open_id:
                member = await find_member_by_open_id(open_id)
                if member:
                    award_title = ''
                    award_diamonds = ''
                    share_times = await GameDiamondReward.find_one(
                        filtered={'source': SOURCE_MEMBER_DIAMOND_DAILY_SHARE_TIMES_LIMIT})
                    value = get_cache_share_times(member.cid)
                    if value < share_times.quantity:
                        end_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=999)
                        current_datetime = datetime.datetime.now()
                        timeout = (end_datetime - current_datetime).seconds
                        # 分享奖励
                        _, m_diamond = await do_diamond_reward(member, SOURCE_MEMBER_DIAMOND_DAILY_SHARE)
                        # 设置更新已奖励次数
                        set_cache_share_times(member.cid, timeout)
                        if member.diamond is None:
                            member.diamond = m_diamond
                        else:
                            member.diamond = member.diamond + m_diamond
                        await member.save()
                        award_title = SOURCE_MEMBER_DIAMOND_DICT.get(SOURCE_MEMBER_DIAMOND_DAILY_SHARE)
                        award_diamonds = m_diamond
                    # 用户的钻石
                    r_dict['diamonds_num'] = member.diamond
                    r_dict['award_title'] = award_title
                    r_dict['award_diamonds'] = award_diamonds
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1002
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict
