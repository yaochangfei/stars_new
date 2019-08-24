# !/usr/bin/python
# -*- coding:utf-8 -*-
import traceback

from datetime import datetime
from tornado import gen
from tornado.web import url

from commons.page_utils import Paging
from db.models import Member, MemberIntegralDetail, MemberIntegralSource
from enums import PERMISSION_TYPE_INTEGRAL_QUERY_MANAGEMENT, PERMISSION_TYPE_INTEGRAL_AWARD_MANAGEMENT,\
    PERMISSION_TYPE_INTEGRAL_EXCHANGE_MANAGEMENT
from db import SOURCE_MEMBER_INTEGRAL_ADMIN_UPDATE, SOURCE_MEMBER_INTEGRAL_LIST, SOURCE_MEMBER_INTEGRAL_NOVICE, \
    SOURCE_MEMBER_INTEGRAL_PII, \
    SOURCE_MEMBER_INTEGRAL_FIRST_SURVEY, SOURCE_MEMBER_INTEGRAL_FIRST_KNOWLEDGE_PK, \
    SOURCE_MEMBER_INTEGRAL_LOGIN_EVERYDAY, SOURCE_MEMBER_INTEGRAL_EVERY_SURVEY, \
    SOURCE_MEMBER_INTEGRAL_KNOWLEDGE_PK_EVERYDAY, SOURCE_MEMBER_INTEGRAL_USER_RETURN
from logger import log_utils
from web import decorators
from web.base import BaseHandler

integral_logger = log_utils.get_logging()


class IntegralListViewHandler(BaseHandler):
    """
    积分查询
    """

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_QUERY_MANAGEMENT)
    @decorators.render_template('backoffice/integral/list_view.html')
    async def get(self):

        search_account = self.get_argument('search_account', '')
        search_nickname = self.get_argument('search_nickname', '')

        query_param = {}
        and_query_param = [{'record_flag': 1}]
        if search_nickname:
            and_query_param.append({'nick_name': {'$regex': search_nickname}})
        if search_account:
            and_query_param.append({'$or': [{'code': {'$regex': search_account}}]})

        if and_query_param:
            query_param['$and'] = and_query_param

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&search_account=%s&search_nickname=%s' % \
                   (self.reverse_url("backoffice_integral_list"), per_page_quantity, search_account, search_nickname)
        paging = Paging(page_url, Member, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'], **query_param)
        await paging.pager()

        return locals()


class IntegralEditViewHandler(BaseHandler):
    """
    管理员修改积分
    """

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_QUERY_MANAGEMENT)
    @decorators.render_template('backoffice/integral/edit_view.html')
    async def get(self):
        member_id = self.get_argument('member_id', '')

        return {'member_id': member_id}

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_QUERY_MANAGEMENT)
    @decorators.render_json
    async def post(self):

        res = dict(code=0)

        member_id = self.get_argument('member_id', '')
        action = self.get_argument('action', '')
        value = self.get_argument('value', '')
        content = self.get_argument('content', '')

        if member_id and action and value:

            member = await Member.get_by_id(member_id)

            if member:

                try:
                    current_integral = member.integral

                    integral_change = 0

                    if action == 'plus':
                        current_integral += int(value)
                        integral_change = int(value)
                    elif action == 'minus':
                        current_integral -= int(value)
                        integral_change = -int(value)

                    member.updated_dt = datetime.now()
                    member.updated_id = self.current_user.oid
                    member.integral = current_integral
                    await member.save()

                    # 新增操作记录
                    integral_record = MemberIntegralDetail()
                    integral_record.member_cid = member.cid
                    integral_record.integral = integral_change
                    integral_record.source = SOURCE_MEMBER_INTEGRAL_ADMIN_UPDATE
                    integral_record.reward_datetime = datetime.now()
                    integral_record.content = content
                    integral_record.created_id = self.current_user.oid
                    integral_record.updated_id = self.current_user.oid

                    await integral_record.save()

                    res['code'] = 1

                except RuntimeError:
                    integral_logger.error(traceback.format_exc())

        else:
            res['code'] = -1

        return res


class IntegralDetailViewHandler(BaseHandler):
    """
    用户积分明细
    """

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_QUERY_MANAGEMENT)
    @decorators.render_template('backoffice/integral/detail_view.html')
    async def get(self):
        member_id = self.get_argument('member_id', '')

        member = await Member.get_by_id(member_id)

        search_source = self.get_argument('search_source', '')
        search_datetime = self.get_argument('search_datetime', '')

        query_param = {
            'member_cid': member.cid
        }
        if search_source:
            query_param['source'] = int(search_source)
        if search_datetime:
            start = datetime.strptime(search_datetime, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
            end = datetime.strptime(search_datetime, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query_param['reward_datetime'] = {
                '$lt': end,
                '$gt': start,
            }

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&search_source=%s&search_datetime=%s&member_id=%s' % \
                   (self.reverse_url("backoffice_integral_detail"), per_page_quantity, search_source, search_datetime,
                    member_id)
        paging = Paging(page_url, MemberIntegralDetail, current_page=to_page_num,
                        items_per_page=per_page_quantity, sort=['-updated_dt'], **query_param)

        await paging.pager()

        return locals()


class IntegralRewardViewHandler(BaseHandler):
    """
    积分奖励设置
    """

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_AWARD_MANAGEMENT)
    @decorators.render_template('backoffice/integral/reward_view.html')
    async def get(self):
        integral_reward_dict = dict()

        for source in SOURCE_MEMBER_INTEGRAL_LIST:
            reward = await MemberIntegralSource.find_one(filtered={'source': source})
            if reward is not None:
                integral_reward_dict[source] = reward.integral

        return {'integral_reward_dict': integral_reward_dict}

    @decorators.permission_required(PERMISSION_TYPE_INTEGRAL_AWARD_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = dict(code=0)

        novice = self.get_argument('novice', '')
        pii = self.get_argument('pii', '')
        first_survey = self.get_argument('first_survey', '')
        first_pk = self.get_argument('first_pk', '')
        login_everyday = self.get_argument('login_everyday', '')
        every_survey = self.get_argument('every_survey', '')
        pk_every_day = self.get_argument('pk_every_day', '')
        user_return = self.get_argument('user_return', '')
        attr_dict = {
            SOURCE_MEMBER_INTEGRAL_NOVICE: novice,
            SOURCE_MEMBER_INTEGRAL_PII: pii,
            SOURCE_MEMBER_INTEGRAL_FIRST_SURVEY: first_survey,
            SOURCE_MEMBER_INTEGRAL_FIRST_KNOWLEDGE_PK: first_pk,
            SOURCE_MEMBER_INTEGRAL_LOGIN_EVERYDAY: login_everyday,
            SOURCE_MEMBER_INTEGRAL_EVERY_SURVEY: every_survey,
            SOURCE_MEMBER_INTEGRAL_KNOWLEDGE_PK_EVERYDAY: pk_every_day,
            SOURCE_MEMBER_INTEGRAL_USER_RETURN: user_return,
        }
        try:
            for source, val in attr_dict.items():
                try:
                    integral = int(val)
                except ValueError:
                    continue
                else:
                    member_integral_source = await MemberIntegralSource.find_one(filtered={'source': source})
                    if member_integral_source is None:
                        member_integral_source = MemberIntegralSource()
                    member_integral_source.source = source
                    member_integral_source.integral = integral
                    member_integral_source.updated_dt = datetime.now()
                    member_integral_source.updated_id = self.current_user.oid
                    await member_integral_source.save()
            res['code'] = 1
        except RuntimeError:
            integral_logger.error(traceback.format_exc())

        return res


URL_MAPPING_LIST = [
    url(r'/backoffice/integral/list/', IntegralListViewHandler, name='backoffice_integral_list'),
    url(r'/backoffice/integral/edit/', IntegralEditViewHandler, name='backoffice_integral_edit'),
    url(r'/backoffice/integral/detail/', IntegralDetailViewHandler, name='backoffice_integral_detail'),
    url(r'/backoffice/integral/reward/', IntegralRewardViewHandler, name='backoffice_integral_reward'),
]
