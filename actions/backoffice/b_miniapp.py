# !/usr/bin/python
# -*- coding:utf-8 -*-
import traceback

import datetime

from tornado.web import url

from commons.page_utils import Paging
from db import SOURCE_MEMBER_DIAMOND_NOVICE, SOURCE_MEMBER_DIAMOND_FIRST_PK, SOURCE_MEMBER_DIAMOND_FIRST_WIN, \
    SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY, SOURCE_MEMBER_DIAMOND_WIN_STREAK_TIMES, \
    SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_START, SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_APPEND, \
    SOURCE_MEMBER_DIAMOND_USER_RETURN, TYPE_DAN_GRADE_ONE, TYPE_DAN_GRADE_THIRD, TYPE_DAN_GRADE_TWO, \
    TYPE_DAN_GRADE_FOUR, TYPE_DAN_GRADE_FIVE, TYPE_DAN_GRADE_SIX, TYPE_DAN_GRADE_SEVEN, TYPE_DAN_GRADE_EIGHT, \
    TYPE_DAN_GRADE_NINE, TYPE_DAN_GRADE_TEN, TYPE_DAN_GRADE_ELEVEN, SOURCE_MEMBER_DIAMOND_ADMIN_UPDATE, \
    SOURCE_MEMBER_DIAMOND_DAILY_SHARE_TIMES_LIMIT, SOURCE_MEMBER_DIAMOND_DAILY_SHARE, \
    SOURCE_MEMBER_DIAMOND_DAILY_RANKING_VALUE_LIMIT, SOURCE_MEMBER_DIAMOND_DAILY_RANKING
from db.models import Member, GameDiamondReward, GameDiamondConsume, MemberDiamondDetail, VaultDiamondBank
from enums import PERMISSION_TYPE_MINIAPP_GAME_DIAMOND_MANAGEMENT
from logger import log_utils
from web import decorators
from web.base import BaseHandler

logger = log_utils.get_logging()


class DiamondListViewHandler(BaseHandler):
    @decorators.render_template('backoffice/diamond/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DIAMOND_MANAGEMENT)
    async def get(self):
        query_params = {'record_flag': 1}

        kw_name = self.get_argument('kw_name', '')
        kw_nickname = self.get_argument('kw_nickname', '')
        if kw_name:
            query_params['$or'] = [
                {"code": {'$regex': kw_name, '$options': 'i'}},
                {"name": {'$regex': kw_name, '$options': 'i'}}
            ]
        if kw_nickname:
            query_params['nick_name'] = {'$regex': kw_nickname, '$options': 'i'}
        # 分页 START
        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&kw_name=%s&kw_nickname=%s' % (
            self.reverse_url("backoffice_diamond_list"), per_page_quantity, kw_name, kw_nickname)
        paging = Paging(page_url, Member, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'], **query_params)
        await paging.pager()
        # 分页 END
        return locals()


class DiamondAwardViewHandler(BaseHandler):
    @decorators.render_template('backoffice/diamond/award_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DIAMOND_MANAGEMENT)
    async def get(self):
        diamond_reward_list = await GameDiamondReward.find(dict(record_flag=1)).to_list(None)
        diamond_reward_dict = {}
        if diamond_reward_list:
            for diamond_reward in diamond_reward_list:
                if diamond_reward:
                    diamond_reward_dict[diamond_reward.source] = diamond_reward.quantity
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DIAMOND_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            novices_reward = self.get_argument('novices_reward')
            first_pk = self.get_argument('first_pk')
            first_win = self.get_argument('first_win')
            login_everyday = self.get_argument('login_everyday')
            starting_times = self.get_argument('starting_times')
            starting_award = self.get_argument('starting_award')
            append_award = self.get_argument('append_award')
            user_return = self.get_argument('user_return')

            share_times_limit = self.get_argument('share_times_limit')
            share_award = self.get_argument('share_award')
            ranking_limit = self.get_argument('ranking_limit')
            ranking_award = self.get_argument('ranking_award')
            if not novices_reward:
                r_dict['code'] = -1
            elif not first_pk:
                r_dict['code'] = -2
            elif not first_win:
                r_dict['code'] = -3
            elif not login_everyday:
                r_dict['code'] = -4
            elif not starting_times:
                r_dict['code'] = -5
            elif not starting_award:
                r_dict['code'] = -6
            elif not append_award:
                r_dict['code'] = -7
            elif not user_return:
                r_dict['code'] = -8
            elif not share_times_limit:
                r_dict['code'] = -9
            elif not share_award:
                r_dict['code'] = -10
            elif not ranking_limit:
                r_dict['code'] = -11
            elif not ranking_award:
                r_dict['code'] = -12
            else:
                category_list = {
                    (novices_reward, SOURCE_MEMBER_DIAMOND_NOVICE), (first_pk, SOURCE_MEMBER_DIAMOND_FIRST_PK),
                    (first_win, SOURCE_MEMBER_DIAMOND_FIRST_WIN),
                    (login_everyday, SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY),
                    (starting_times, SOURCE_MEMBER_DIAMOND_WIN_STREAK_TIMES),
                    (starting_award, SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_START),
                    (append_award, SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_APPEND),
                    (user_return, SOURCE_MEMBER_DIAMOND_USER_RETURN),
                    (share_times_limit, SOURCE_MEMBER_DIAMOND_DAILY_SHARE_TIMES_LIMIT),
                    (share_award, SOURCE_MEMBER_DIAMOND_DAILY_SHARE),
                    (ranking_limit, SOURCE_MEMBER_DIAMOND_DAILY_RANKING_VALUE_LIMIT),
                    (ranking_award, SOURCE_MEMBER_DIAMOND_DAILY_RANKING)

                }
                if category_list:
                    await GameDiamondReward.delete_many({'record_flag': 1})
                    for category in category_list:
                        if category:
                            dmr = GameDiamondReward(source=category[1], quantity=int(category[0]))
                            dmr.created_id = self.current_user.oid
                            dmr.updated_id = self.current_user.oid
                            await dmr.save()
                    r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class DiamondConsumeViewHandler(BaseHandler):
    @decorators.render_template('backoffice/diamond/consume_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DIAMOND_MANAGEMENT)
    async def get(self):
        diamond_consume_list = await GameDiamondConsume.find(dict(record_flag=1)).to_list(None)
        diamond_consume_dict = {}
        if diamond_consume_list:
            for diamond_consume in diamond_consume_list:
                if diamond_consume:
                    diamond_consume_dict[diamond_consume.source] = diamond_consume.quantity
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DIAMOND_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            type_dan_grade_one = self.get_argument('type_dan_grade_one')
            type_dan_grade_two = self.get_argument('type_dan_grade_two')
            type_dan_grade_third = self.get_argument('type_dan_grade_third')
            type_dan_grade_four = self.get_argument('type_dan_grade_four')
            type_dan_grade_five = self.get_argument('type_dan_grade_five')
            type_dan_grade_six = self.get_argument('type_dan_grade_six')
            type_dan_grade_seven = self.get_argument('type_dan_grade_seven')
            type_dan_grade_eight = self.get_argument('type_dan_grade_eight')
            type_dan_grade_nine = self.get_argument('type_dan_grade_nine')
            type_dan_grade_ten = self.get_argument('type_dan_grade_ten')
            type_dan_grade_eleven = self.get_argument('type_dan_grade_eleven')
            if not type_dan_grade_one:
                r_dict['code'] = -1
            elif not type_dan_grade_two:
                r_dict['code'] = -2
            elif not type_dan_grade_third:
                r_dict['code'] = -3
            elif not type_dan_grade_four:
                r_dict['code'] = -4
            elif not type_dan_grade_five:
                r_dict['code'] = -5
            elif not type_dan_grade_six:
                r_dict['code'] = -6
            elif not type_dan_grade_seven:
                r_dict['code'] = -7
            elif not type_dan_grade_eight:
                r_dict['code'] = -8
            elif not type_dan_grade_nine:
                r_dict['code'] = -9
            elif not type_dan_grade_ten:
                r_dict['code'] = -10
            elif not type_dan_grade_eleven:
                r_dict['code'] = -11
            else:
                category_list = [
                    (type_dan_grade_one, TYPE_DAN_GRADE_ONE),
                    (type_dan_grade_two, TYPE_DAN_GRADE_TWO),
                    (type_dan_grade_third, TYPE_DAN_GRADE_THIRD),
                    (type_dan_grade_four, TYPE_DAN_GRADE_FOUR),
                    (type_dan_grade_five, TYPE_DAN_GRADE_FIVE),
                    (type_dan_grade_six, TYPE_DAN_GRADE_SIX),
                    (type_dan_grade_seven, TYPE_DAN_GRADE_SEVEN),
                    (type_dan_grade_eight, TYPE_DAN_GRADE_EIGHT),
                    (type_dan_grade_nine, TYPE_DAN_GRADE_NINE),
                    (type_dan_grade_ten, TYPE_DAN_GRADE_TEN),
                    (type_dan_grade_eleven, TYPE_DAN_GRADE_ELEVEN)
                ]
                if category_list:
                    await GameDiamondConsume.delete_many({'record_flag': 1})
                    for category in category_list:
                        if category:
                            dmr = GameDiamondConsume(source=category[1], quantity=int(category[0]))
                            dmr.created_id = self.current_user.oid
                            dmr.updated_id = self.current_user.oid
                            await dmr.save()
                    r_dict['code'] = 1

        except RuntimeError:
            logger.error(traceback.format_exc())

        return r_dict


class DiamondEditViewHandler(BaseHandler):
    """
    管理员修改钻石
    """

    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DIAMOND_MANAGEMENT)
    @decorators.render_template('backoffice/diamond/edit_view.html')
    async def get(self):
        member_id = self.get_argument('member_id')
        return locals()

    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DIAMOND_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = {'code': 0}
        member_id = self.get_argument('member_id')
        action = self.get_argument('action')
        value = self.get_argument('value')
        content = self.get_argument('content')
        if member_id and action and value:
            member = await Member.get_by_id(member_id)
            if member:
                try:
                    current_diamond = member.diamond
                    diamond_change = 0
                    if action == 'plus':
                        current_diamond += int(value)
                        diamond_change = int(value)
                    elif action == 'minus':
                        current_diamond -= int(value)
                        diamond_change = -int(value)
                    member.diamond = current_diamond
                    member.updated_dt = datetime.datetime.now()
                    member.updated_id = self.current_user.oid
                    await member.save()

                    # 新增操作记录
                    diamond_record = MemberDiamondDetail()
                    diamond_record.member_cid = member.cid
                    diamond_record.diamond = diamond_change
                    diamond_record.source = SOURCE_MEMBER_DIAMOND_ADMIN_UPDATE
                    diamond_record.reward_datetime = datetime.datetime.now()
                    diamond_record.content = content
                    diamond_record.created_id = self.current_user.oid
                    diamond_record.updated_id = self.current_user.oid

                    await diamond_record.save()
                    res['code'] = 1
                except Exception:
                    logger.error(traceback.format_exc())
        else:
            res['code'] = -1
        return res


class DiamondDetailViewHandler(BaseHandler):
    """
    用户钻石明细
    """

    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DIAMOND_MANAGEMENT)
    @decorators.render_template('backoffice/diamond/detail_view.html')
    async def get(self):
        member_id = self.get_argument('member_id')
        search_source = self.get_argument('search_source', '')
        search_datetime = self.get_argument('search_datetime', '')

        member = await Member.get_by_id(member_id)
        query_param = {
            'member_cid': member.cid
        }
        if search_source:
            query_param['source'] = int(search_source)
        if search_datetime:
            start = datetime.datetime.strptime(search_datetime, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
            end = datetime.datetime.strptime(search_datetime, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query_param['reward_datetime'] = {'$lt': end, '$gt': start}

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&search_source=%s&search_datetime=%s&member_id=%s' % \
                   (self.reverse_url("backoffice_diamond_detail"), per_page_quantity, search_source, search_datetime,
                    member_id)
        paging = Paging(page_url, MemberDiamondDetail, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'], **query_param)
        await paging.pager()

        return locals()


class DiamondBankViewHandler(BaseHandler):
    """
    金库设置
    """

    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DIAMOND_MANAGEMENT)
    @decorators.render_template('backoffice/bank/bank_view.html')
    async def get(self):
        bank_list = await VaultDiamondBank.find(dict(record_flag=1)).to_list(None)
        bank = bank_list[0] if bank_list else {}
        return locals()

    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DIAMOND_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        r_dict = {'code': 0}
        try:
            minutes = self.get_argument('minutes', '')
            quantity = self.get_argument('quantity', '')
            times = int(self.get_argument('times', 0))
            if not minutes:
                r_dict['code'] = -1
            elif not quantity:
                r_dict['code'] = -2
            bank = VaultDiamondBank()
            bank.quantity = quantity
            bank.minutes = minutes
            bank.times = times
            await VaultDiamondBank.delete_many({'record_flag': 1})
            await bank.save()
            r_dict = {'code': 1}
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


URL_MAPPING_LIST = [
    url(r'/backoffice/diamond/list/', DiamondListViewHandler, name='backoffice_diamond_list'),
    url(r'/backoffice/diamond/award/', DiamondAwardViewHandler, name='backoffice_diamond_award'),
    url(r'/backoffice/diamond/consume/', DiamondConsumeViewHandler, name='backoffice_diamond_consume'),
    url(r'/backoffice/diamond/edit/', DiamondEditViewHandler, name='backoffice_diamond_edit'),
    url(r'/backoffice/diamond/detail/', DiamondDetailViewHandler, name='backoffice_diamond_detail'),
    url(r'/backoffice/bank/view/', DiamondBankViewHandler, name='backoffice_bank_view')
]
