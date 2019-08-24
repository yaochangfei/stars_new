# !/usr/bin/python
# -*- coding:utf-8 -*-
import copy
import datetime
import json
import random
import traceback

from commons.common_utils import get_increase_code
from commons.division_utils import get_matched_division_2_dict
from db import STATUS_USER_ACTIVE, SOURCE_TYPE_MEMBER_SYSTEM, TYPE_DAN_GRADE_ONE, SOURCE_MEMBER_DIAMOND_NOVICE, \
    SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY, TYPE_DAN_GRADE_DICT, SOURCE_MEMBER_DIAMOND_DICT, TYPE_DAN_GRADE_LIST, \
    SOURCE_MEMBER_DIAMOND_PK_ENTRANCE_FEE, TYPE_DAN_GRADE_ELEVEN, STATUS_RESULT_GAME_PK_WIN, \
    STATUS_RESULT_GAME_PK_FAILED, STATUS_RESULT_GAME_PK_TIE_BREAK, STATUS_RESULT_GAME_PK_GIVE_UP, \
    TYPE_STAR_GRADE_FIVE, SEX_MALE, SEX_FEMALE, SEX_NONE, STATUS_USER_INACTIVE, DIMENSION_SUBJECT_DICT, \
    DIMENSION_SUBJECT_LIST, SOURCE_MEMBER_DIAMOND_VAULT_REWARD, ANSWER_LIMIT_NUMBER, \
    SOURCE_MEMBER_DIAMOND_DAILY_SHARE_TIMES_LIMIT, SOURCE_MEMBER_DIAMOND_DAILY_SHARE, \
    STATUS_SUBJECT_DIMENSION_ACTIVE, STATUS_WRONG_SUBJECT_ACTIVE, CATEGORY_NOTICE_FRIENDS_PLAY, STATUS_NOTICE_UNREAD, \
    STATUS_NOTICE_READ, STATUS_SUBJECT_ACTIVE, CATEGORY_MEMBER_NONE, CATEGORY_SUBJECT_BENCHMARK, \
    CATEGORY_SUBJECT_KNOWLEDGE_DICT, KNOWLEDGE_FIRST_LEVEL_DICT, CATEGORY_SUBJECT_GRADUATION, \
    STATUS_GAME_CHECK_POINT_ACTIVE, STATUS_RESULT_CHECK_POINT_WIN
from db.model_utils import do_diamond_reward, update_diamond_reward, get_cache_answer_limit, set_cache_answer_limit, \
    get_cache_share_times, set_cache_share_times
from db.models import Member, MemberDiamondDetail, MemberGameHistory, GameDiamondConsume, Subject, VaultDiamondBank, \
    MemberWrongSubject, GameDiamondReward, SubjectOption, SubjectAccuracyStatistics, \
    SubjectDimension, MemberAccuracyStatistics, MemberFriend, MemberNotice, MemberExamHistory, UploadFiles, \
    MemberStarsAwardHistory, GameMemberSource, GameDanGrade
from enums import KEY_INCREASE_MEMBER_CODE
from logger import log_utils
from motorengine import DESC, ASC, UpdateOne
from motorengine.stages import MatchStage, SampleStage, SortStage, LimitStage, LookupStage
from settings import MINI_APP_ID, MINI_APP_SECRET, SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX
from tasks.instances.task_member_property_statistics import start_task_member_property_statistics
from tornado.httpclient import AsyncHTTPClient
from tornado.web import url
from web import decorators
from web.base import NonXsrfBaseHandler, RestBaseHandler, BaseHandler
from wechat import wechat_utils, API_CODE_EXCHANGE_SESSION_URL

logger = log_utils.get_logging('a_miniapp')


class MiniappAuthViewHandler(NonXsrfBaseHandler):
    @decorators.render_json
    async def post(self):
        r_dict = {'code': 0}
        try:
            args_dict = json.loads(self.request.body)
            auth_code = args_dict.get('auth_code', None)
            user_info = args_dict.get('userInfo', None)
            source = args_dict.get('source', None)
            if auth_code:
                params_dict = {
                    'app_id': MINI_APP_ID,
                    'app_secret': MINI_APP_SECRET,
                    'code': auth_code
                }
                exchange_url = API_CODE_EXCHANGE_SESSION_URL.format(**params_dict)
                http_client = AsyncHTTPClient()
                response = await http_client.fetch(exchange_url, validate_cert=False)
                if response.code == 200:
                    rep_dict = json.loads(response.body)
                    open_id = rep_dict.get('openid')
                    friend_open_id = args_dict.get('friend_open_id', None)
                    session_key = rep_dict.get('session_key')
                    if open_id:
                        member = await Member.find_one(dict(open_id=open_id))
                        if not member:
                            if source is not None:
                                source = await GameMemberSource.find_one({'code': str(source)})
                                source_type = None
                                if source:
                                    source_type = int(source.code)
                            else:
                                source_type = SOURCE_TYPE_MEMBER_SYSTEM

                            # 创建用户
                            member = Member(
                                code=get_increase_code(KEY_INCREASE_MEMBER_CODE),
                                open_id=open_id,
                                source=source_type,
                                status=STATUS_USER_ACTIVE
                            )
                            wechat_info = await self.parse_wechat_info(user_info)
                            member.sex = wechat_info.get('sex')
                            member.province_code = wechat_info.get('province_code')
                            member.city_code = wechat_info.get('city_code')
                            member.avatar = wechat_info.get('avatar') if wechat_info.get('avatar') else '%s://%s%s' % (
                                SERVER_PROTOCOL, SERVER_HOST, self.static_url('images/default/visitor.png'))
                            member.nick_name = wechat_info.get('nick_name') if wechat_info.get('nick_name') else '游客'

                            member.needless['province'] = wechat_info.get('province_name')
                            member.needless['city'] = wechat_info.get('city_name')
                            member.needless['district'] = None

                            member.wechat_info = user_info

                            member.register_datetime = datetime.datetime.now()
                            member.login_datetime = datetime.datetime.now()
                            member.login_times += 1

                            await member.save()

                            # 会员属性统计
                            member = await Member.find_one(dict(open_id=open_id))
                            await start_task_member_property_statistics(member)

                            r_dict['open_id'] = open_id
                            r_dict['session_key'] = session_key
                            r_dict['code'] = 1000
                        else:
                            if member.status == STATUS_USER_INACTIVE:
                                r_dict['code'] = -4
                            else:
                                member.login_datetime = datetime.datetime.now()
                                member.login_times += 1
                                await member.save()

                                r_dict['open_id'] = open_id
                                r_dict['session_key'] = session_key
                                r_dict['code'] = 1000
                        if friend_open_id:
                            friend = await Member.find_one(dict(open_id=friend_open_id))
                            if friend:
                                friend_member = MemberFriend(member_cid=member.cid, friend_cid=friend.cid)
                                await friend_member.save()
                                member_friend = MemberFriend(member_cid=friend.cid, friend_cid=member.cid)
                                await member_friend.save()
                else:
                    r_dict['code'] = -3
            else:
                r_dict['code'] = -2
        except Exception:
            r_dict['code'] = -1
            logger.error(traceback.format_exc())
        return r_dict

    async def parse_wechat_info(self, wechat_info) -> dict:
        result = {}
        if wechat_info:
            gender = wechat_info.get('gender')
            if gender is not None:
                if gender == 1:
                    result['sex'] = SEX_MALE
                elif gender == 2:
                    result['sex'] = SEX_FEMALE
                else:
                    result['sex'] = SEX_NONE
            else:
                result['sex'] = SEX_NONE

            division_dict = {}
            try:
                division_dict = await get_matched_division_2_dict(province_name=wechat_info.get('province'),
                                                                  city_name=wechat_info.get('city'))
            except ValueError:
                pass

            result['province_code'] = division_dict.get('P').get('code') if division_dict.get('P') else None
            result['province_name'] = division_dict.get('P').get('title') if division_dict.get('P') else None
            result['city_code'] = division_dict.get('C').get('code') if division_dict.get('C') else None
            result['city_name'] = division_dict.get('C').get('title') if division_dict.get('C') else None
            result['avatar'] = wechat_info.get('avatarUrl')
            result['nick_name'] = wechat_info.get('nickName')
        return result


class MiniappWechatInfoUpdateViewHandler(RestBaseHandler):
    """
    授权更新用户信息
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            user_info = self.i_args.get('userInfo', None)
            open_id = self.i_args.get('open_id', None)
            if open_id and user_info:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if not member:
                    r_dict['code'] = 1008
                else:
                    orig_member = copy.deepcopy(member)
                    member.nick_name = user_info.get('nickName') if user_info.get('nickName') else '游客'
                    member.avatar = user_info.get('avatarUrl') if user_info.get('avatarUrl') else '%s://%s%s' % (
                        SERVER_PROTOCOL, SERVER_HOST, self.static_url('images/default/visitor.png'))
                    if not member.wechat_info:
                        wechat_info = await self.parse_wechat_info(user_info)
                        member.sex = wechat_info.get('sex')
                        member.province_code = wechat_info.get('province_code')
                        member.city_code = wechat_info.get('city_code')
                        member.needless['province'] = wechat_info.get('province_name')
                        member.needless['city'] = wechat_info.get('city_name')
                        member.needless['district'] = None

                        member.wechat_info = user_info

                        member.updated_dt = datetime.datetime.now()
                        await member.save()

                        # 会员属性统计
                        new_member = await Member.get_by_id(member.oid)
                        await start_task_member_property_statistics(new_member, orig_member)

                    r_dict['code'] = 1000
            else:
                r_dict['code'] = -2
        except Exception:
            r_dict['code'] = -1
            logger.error(traceback.format_exc())
        return r_dict

    async def parse_wechat_info(self, wechat_info) -> dict:
        result = {}
        if wechat_info:
            gender = wechat_info.get('gender')
            if gender is not None:
                if gender == 1:
                    result['sex'] = SEX_MALE
                elif gender == 2:
                    result['sex'] = SEX_FEMALE
                else:
                    result['sex'] = SEX_NONE
            else:
                result['sex'] = SEX_NONE
            division_dict = {}
            try:
                division_dict = await get_matched_division_2_dict(province_name=wechat_info.get('province'),
                                                                  city_name=wechat_info.get('city'))
            except ValueError:
                pass

            result['province_code'] = division_dict.get('P').get('code') if division_dict.get('P') else None
            result['province_name'] = division_dict.get('P').get('title') if division_dict.get('P') else None
            result['city_code'] = division_dict.get('C').get('code') if division_dict.get('C') else None
            result['city_name'] = division_dict.get('C').get('title') if division_dict.get('C') else None
            result['avatar'] = wechat_info.get('avatarUrl')
            result['nick_name'] = wechat_info.get('nickName')
        return result


class MiniappUserInfoGetViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.i_args.get('open_id', None)
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if not member:
                    r_dict['code'] = 1008
                else:
                    user_info = {
                        'educate': member.education,
                        'sex': member.sex - 1 if member.sex else None,
                        'birth': member.age_group,
                        'category': member.category,
                        'address': [
                            member.needless.get('province'),
                            member.needless.get('city'),
                            member.needless.get('district')
                        ],
                    }
                    r_dict['user_info'] = user_info
                    r_dict['code'] = 1000
            else:
                r_dict['code'] = -2
        except Exception:
            r_dict['code'] = -1
            logger.error(traceback.format_exc())
        return r_dict


class MiniappUserInfoUpdateViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            user_info = self.i_args.get('user_info', None)
            open_id = self.i_args.get('open_id', None)
            if open_id and user_info:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if not member:
                    r_dict['code'] = 1008
                else:
                    if user_info:
                        orig_member = copy.deepcopy(member)
                        # 更新用户信息
                        if user_info.get('educate'):
                            try:
                                member.education = int(user_info.get('educate'))
                            except Exception:
                                pass
                        if user_info.get('sex'):
                            try:
                                if int(user_info.get('sex')) == 0:
                                    member.sex = SEX_MALE
                                elif int(user_info.get('sex')) == 1:
                                    member.sex = SEX_FEMALE
                                else:
                                    member.sex = SEX_NONE
                            except Exception:
                                member.sex = SEX_NONE
                        if user_info.get('birth'):
                            try:
                                member.age_group = int(user_info.get('birth'))
                            except Exception:
                                pass
                        try:
                            member.category = int(user_info.get('category')) if user_info.get(
                                'category') else CATEGORY_MEMBER_NONE
                        except Exception:
                            pass
                        province_name = None
                        city_name = None
                        district_name = None
                        if user_info.get('address'):
                            if len(user_info.get('address')) > 0:
                                province_name = user_info.get('address')[0]
                                province_name = province_name.replace('省', '')
                            if len(user_info.get('address')) > 1:
                                city_name = user_info.get('address')[1]
                                city_name = city_name.replace('市', '')
                            if len(user_info.get('address')) > 2:
                                district_name = user_info.get('address')[2]
                                district_name = district_name.replace('区', '').replace('县', '')
                        division_dict = {}
                        try:
                            division_dict = await get_matched_division_2_dict(
                                province_name=province_name, city_name=city_name, district_name=district_name)
                        except ValueError:
                            pass

                        if division_dict:
                            member.province_code = division_dict.get('P').get('code') if division_dict.get(
                                'P') else None
                            member.needless['province'] = division_dict.get('P').get('title') if division_dict.get(
                                'P') else None
                            member.city_code = division_dict.get('C').get('code') if division_dict.get('C') else None
                            member.needless['city'] = division_dict.get('C').get('title') if division_dict.get(
                                'C') else None
                            member.district_code = division_dict.get('D').get('code') if division_dict.get(
                                'D') else None
                            member.needless['district'] = division_dict.get('D').get('title') if division_dict.get(
                                'D') else None
                        member.updated_dt = datetime.datetime.now()
                        await member.save()

                        # 会员属性统计
                        new_member = await Member.get_by_id(member.oid)
                        await start_task_member_property_statistics(new_member, orig_member)

                        r_dict['user_info_completed'] = True
                    r_dict['code'] = 1000
            else:
                r_dict['code'] = -2
        except Exception:
            r_dict['code'] = -1
            logger.error(traceback.format_exc())
        return r_dict


class MiniappHomePageViewHandler(RestBaseHandler):
    """
    主页信息
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.i_args.get('open_id', None)
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    user_info = {
                        'diamond': member.diamond,  # 初始钻石数
                        'dan_grade': TYPE_DAN_GRADE_DICT.get(member.dan_grade),  # 等级
                        'avatar': member.avatar
                    }
                    reward_info = []
                    diamond = member.diamond
                    if diamond is None:
                        member.diamond = 0
                        member.updated_dt = datetime.datetime.now()
                        await member.save()

                    dan_grade = member.dan_grade
                    # 新手奖励
                    if dan_grade is None:
                        dan_grade = TYPE_DAN_GRADE_ONE
                        _, m_diamond = await do_diamond_reward(member, SOURCE_MEMBER_DIAMOND_NOVICE)
                        member.dan_grade = dan_grade
                        member.updated_dt = datetime.datetime.now()
                        if member.diamond is None:
                            member.diamond = m_diamond
                        else:
                            member.diamond = member.diamond + m_diamond
                        await member.save()

                        reward_info.append({
                            'title': SOURCE_MEMBER_DIAMOND_DICT.get(SOURCE_MEMBER_DIAMOND_NOVICE),
                            'diamond_num': m_diamond
                        })
                    else:
                        start_datetime = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                        end_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=99999)
                        count = await MemberDiamondDetail.count({
                            "member_cid": member.cid,
                            "source": SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY,
                            "reward_datetime": {'$lte': end_datetime, '$gte': start_datetime},
                        })
                        if count == 0:
                            _, m_diamond = await do_diamond_reward(member, SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY)
                            member.updated_dt = datetime.datetime.now()
                            if member.diamond is None:
                                member.diamond = m_diamond
                            else:
                                member.diamond = member.diamond + m_diamond
                            await member.save()

                            reward_info.append({
                                'title': SOURCE_MEMBER_DIAMOND_DICT.get(SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY),
                                'diamond_num': m_diamond
                            })
                        # 排行榜奖励
                        rank_reward = await wechat_utils.do_daily_ranking_award(member)

                        if rank_reward:
                            reward_info.append(rank_reward)
                    dan_grade_title = TYPE_DAN_GRADE_DICT.get(dan_grade)
                    # 排位赛在线人数
                    online_member_count = await Member.count(dict(status=STATUS_USER_ACTIVE, open_id={'$ne': None}))
                    game_history_count = await MemberGameHistory.count(
                        filtered={'member_cid': member.cid, 'runaway_index': None})
                    can_friend_share = False
                    if game_history_count > 0:
                        can_friend_share = True
                    user_info['can_friend_share'] = can_friend_share
                    r_dict['code'] = 1000
                    r_dict['diamonds_num'] = member.diamond  # 奖励后的
                    r_dict['online_member_count'] = online_member_count
                    r_dict['reward_info'] = reward_info
                    r_dict['user_info'] = user_info
                else:
                    r_dict['code'] = 1008
            else:
                r_dict['code'] = 1007
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappDanGradeGetViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.i_args.get('open_id', None)
            if open_id:
                member = await Member.find(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    dan_grade = member.dan_grade
                    # 新手奖励
                    if dan_grade is None:
                        dan_grade = TYPE_DAN_GRADE_ONE
                        _, m_diamond = await do_diamond_reward(member, SOURCE_MEMBER_DIAMOND_NOVICE)
                        member.dan_grade = dan_grade
                        member.updated_dt = datetime.datetime.now()
                        if member.diamond is None:
                            member.diamond = m_diamond
                        else:
                            member.diamond = member.diamond + m_diamond
                        await member.save()
                    else:
                        start_datetime = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                        end_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=99999)
                        count = await MemberDiamondDetail.count({
                            "member_cid": member.cid,
                            "source": SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY,
                            "reward_datetime": {'$lte': end_datetime, '$gte': start_datetime},
                        })
                        if count == 0:
                            _, m_diamond = await do_diamond_reward(member, SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY)
                            member.updated_dt = datetime.datetime.now()
                            if member.diamond is None:
                                member.diamond = m_diamond
                            else:
                                member.diamond = member.diamond + m_diamond
                            await member.save()
                    dan_grade_title = TYPE_DAN_GRADE_DICT.get(dan_grade)
                    r_dict['is_member'] = True
                else:
                    dan_grade = TYPE_DAN_GRADE_ONE
                    dan_grade_title = TYPE_DAN_GRADE_DICT.get(dan_grade)
                    r_dict['is_member'] = False
                r_dict['code'] = 1000
                r_dict['dan_grade'] = dan_grade
                r_dict['dan_grade_title'] = dan_grade_title
            else:
                r_dict['code'] = 1007
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappDiamonAmountGetViewHandler(RestBaseHandler):
    """
    获取钻石数量
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.i_args.get('open_id', None)
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    reward_info = []
                    diamond = member.diamond
                    if diamond is None:
                        diamond = 0
                        member.diamond = 0
                        member.updated_dt = datetime.datetime.now()
                        await member.save()

                    dan_grade = member.dan_grade
                    # 新手奖励
                    if dan_grade is None:
                        dan_grade = TYPE_DAN_GRADE_ONE
                        _, m_diamond = await do_diamond_reward(member, SOURCE_MEMBER_DIAMOND_NOVICE)
                        member.dan_grade = dan_grade
                        member.updated_dt = datetime.datetime.now()
                        if member.diamond is None:
                            member.diamond = m_diamond
                            diamond = m_diamond
                        else:
                            member.diamond = member.diamond + m_diamond
                            diamond = member.diamond
                        await member.save()

                        reward_info.append({
                            'title': SOURCE_MEMBER_DIAMOND_DICT.get(SOURCE_MEMBER_DIAMOND_NOVICE),
                            'diamond_num': m_diamond
                        })
                    else:
                        start_datetime = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                        end_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=99999)
                        count = await MemberDiamondDetail.count({
                            "member_cid": member.cid,
                            "source": SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY,
                            "reward_datetime": {'$gte': start_datetime, '$lte': end_datetime},
                        })
                        if count == 0:
                            _, m_diamond = await do_diamond_reward(member, SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY)
                            member.updated_dt = datetime.datetime.now()
                            if member.diamond is None:
                                member.diamond = m_diamond
                                diamond = m_diamond
                            else:
                                member.diamond = member.diamond + m_diamond
                                diamond = member.diamond
                            await member.save()

                            reward_info.append({
                                'title': SOURCE_MEMBER_DIAMOND_DICT.get(SOURCE_MEMBER_DIAMOND_LOGIN_EVERYDAY),
                                'diamond_num': m_diamond
                            })
                        # 排行榜奖励
                        rank_reward = await wechat_utils.do_daily_ranking_award(member)

                        if rank_reward:
                            reward_info.append(rank_reward)
                    dan_grade_title = TYPE_DAN_GRADE_DICT.get(dan_grade)
                    # 排位赛在线人数
                    # online_member_count = await Member.count(dict(status=STATUS_USER_ACTIVE, open_id={'$ne': None}))
                    r_dict['code'] = 1000
                    r_dict['diamonds_num'] = member.diamond
                    # r_dict['online_member_count'] = online_member_count
                    r_dict['dan_grade'] = dan_grade
                    r_dict['dan_grade_title'] = dan_grade_title
                    r_dict['head_url'] = member.avatar
                    r_dict['reward_info'] = reward_info
                else:
                    r_dict['code'] = 1008
            else:
                r_dict['code'] = 1007
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappFightMemberGetViewHandler(RestBaseHandler):
    """
    获取匹配对手数据
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.i_args.get('open_id', None)
            grade_id = self.i_args.get('grade_id', TYPE_DAN_GRADE_ONE)
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    try:
                        if int(grade_id) in TYPE_DAN_GRADE_LIST:
                            # 随机查询出一条数据
                            opponent_base = {}

                            filter_dict = {
                                'open_id': {'$ne': open_id, '$exists': True},
                                'status': STATUS_USER_ACTIVE,
                            }
                            pk_member_list = await Member.aggregate([MatchStage(filter_dict), SampleStage(1)]).to_list(
                                1)

                            if pk_member_list:
                                pk_member = pk_member_list[0]
                                # 判断对手连胜
                                pk_member_continuous_win_times = 0
                                # 当前连胜次数
                                last_pk_list = await MemberGameHistory.aggregate([
                                    MatchStage({'member_cid': pk_member.cid}),
                                    SortStage([('fight_datetime', DESC)]),
                                    LimitStage(1)
                                ]).to_list(1)

                                if last_pk_list and last_pk_list[0].continuous_win_times:
                                    pk_member_continuous_win_times = last_pk_list[0].continuous_win_times

                                opponent_base['nick_name'] = pk_member.nick_name
                                dan_grade = pk_member.dan_grade if pk_member.dan_grade else TYPE_DAN_GRADE_ONE
                                opponent_base['level_name'] = TYPE_DAN_GRADE_DICT.get(dan_grade, '')
                                opponent_base['head_url'] = pk_member.avatar
                                opponent_base['open_id'] = pk_member.open_id
                                opponent_base['city'] = pk_member.needless.get('city', '')
                                opponent_base['continuous_win_times'] = pk_member_continuous_win_times

                                r_dict['code'] = 1000
                                r_dict['opponent_base'] = opponent_base

                                # 判断自己连胜
                                own_continuous_win_times = 0
                                # 当前连胜次数
                                own_last_pk_list = await MemberGameHistory.aggregate([
                                    MatchStage({'member_cid': member.cid}),
                                    SortStage([('fight_datetime', DESC)]),
                                    LimitStage(1)
                                ]).to_list(1)

                                if own_last_pk_list and own_last_pk_list[0].continuous_win_times:
                                    own_continuous_win_times = own_last_pk_list[0].continuous_win_times

                                r_dict['own_base'] = {
                                    'level_name': TYPE_DAN_GRADE_DICT.get(member.dan_grade, ''),
                                    'city': member.needless.get('city', ''),
                                    'nick_name': member.nick_name if member.nick_name else '',
                                    'head_url': member.avatar if member.avatar else '',
                                    'continuous_win_times': own_continuous_win_times
                                }
                                # 入场费
                                diamond_consume = await GameDiamondConsume.find_one(dict(source=grade_id))
                                diamond_consume_quantity = diamond_consume.quantity if diamond_consume.quantity else 0

                                member_diamond = member.diamond if member.diamond else 0
                                member.diamond = member_diamond - diamond_consume_quantity
                                member.updated_dt = datetime.datetime.now()
                                # 入场费记录
                                await update_diamond_reward(member.cid, SOURCE_MEMBER_DIAMOND_PK_ENTRANCE_FEE,
                                                            -diamond_consume_quantity)
                                await member.save()
                            else:
                                r_dict['code'] = 10010
                        else:
                            r_dict['code'] = 1009
                    except ValueError:
                        r_dict['code'] = 1009
                else:
                    r_dict['code'] = 1008
            else:
                r_dict['code'] = 1007
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappGetQuestionListViewHandler(RestBaseHandler):
    """
    获取题目数据和镜像数据
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.i_args.get('open_id', None)
            grade_id = self.i_args.get('grade_id', None)
            opponent_open_id = self.i_args.get('opponent_open_id', None)
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    pk_member = await Member.find_one(dict(open_id=opponent_open_id, status=STATUS_USER_ACTIVE))
                    if pk_member:
                        # 未找到镜像数据则按照规则生成
                        # 按照规则抓取题目code
                        # 匹配段位为-1 当前 +1
                        grade = random.choice([int(grade_id), int(grade_id) - 1, int(grade_id) + 1])
                        if grade < TYPE_DAN_GRADE_ONE:
                            grade = TYPE_DAN_GRADE_ONE
                        if grade > TYPE_DAN_GRADE_ELEVEN:
                            grade = TYPE_DAN_GRADE_ELEVEN
                        question_list = await wechat_utils.get_pk_questions(grade)
                        q_cid_list = [question.cid for question in question_list]
                        # 生成镜像数据
                        opponent = await wechat_utils.generate_image_answers(pk_member, grade_id, q_cid_list)
                        # 处理题目和选项数据病返回
                        question_list = await wechat_utils.deal_questions(q_cid_list)

                        r_dict['opponent'] = opponent
                        r_dict['question_list'] = question_list
                        r_dict['init_own_answers'] = [{'questionid': q_cid} for q_cid in q_cid_list]
                        r_dict['code'] = 1000
                    else:
                        r_dict['code'] = 1008
                else:
                    r_dict['code'] = 1008
            else:
                r_dict['code'] = 1007
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappGetUserInfoViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.i_args.get('open_id', None)
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    user_info = {
                        'integral': member.integral,  # 积分
                        'diamond': member.diamond,  # 钻石数
                        'dan_grade': TYPE_DAN_GRADE_DICT.get(member.dan_grade),  # 等级
                        'highest_win_times': member.highest_win_times if member.highest_win_times else 0,  # 最高连胜
                        'category': member.category,  # 群体
                    }
                    # 胜场数
                    win_amount = await MemberGameHistory.count(dict(status=STATUS_RESULT_GAME_PK_WIN))
                    # 败局数
                    fail_amount = await MemberGameHistory.count(dict(status=STATUS_RESULT_GAME_PK_FAILED))
                    # 平局数
                    draw_amount = await MemberGameHistory.count(dict(status=STATUS_RESULT_GAME_PK_TIE_BREAK))
                    # 逃跑数
                    escape_amount = await MemberGameHistory.count(dict(status=STATUS_RESULT_GAME_PK_GIVE_UP))

                    user_info['win_amount'] = win_amount  # 胜场数
                    user_info['fail_amount'] = fail_amount  # 败局数
                    user_info['draw_amount'] = draw_amount  # 平局数
                    user_info['escape_amount'] = escape_amount  # 逃跑数

                    r_dict['user_info'] = user_info
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1008
            else:
                r_dict['code'] = 1007
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappGetLevelListInfoViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.i_args.get('open_id', None)
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    # 根据当前段位获取段位列表显示信息
                    level_list, _ = await wechat_utils.get_level_list_info(member, pk_status=None, unlock=None)
                    r_dict['code'] = 1000
                    r_dict['level_list'] = level_list
                else:
                    r_dict['code'] = 1008
            else:
                r_dict['code'] = 1007
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappSubmitAnswersViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.i_args.get('open_id', None)
            own = self.i_args.get('own', {})
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    if own:
                        # 处理答案数据，增加答题历史
                        pk_status, unlock, continuous_win_times, correct_list, member_game_history = await wechat_utils.deal_with_own_answers(
                            member, own)
                        if own.get('grade'):
                            if pk_status == STATUS_RESULT_GAME_PK_WIN:
                                member_stars_award_history = MemberStarsAwardHistory()
                                member_stars_award_history.dan_grade = member_game_history.dan_grade
                                member_stars_award_history.member_cid = member.cid
                                member_stars_award_history.quantity = 1
                                member_stars_award_history.award_dt = datetime.datetime.now()
                                await member_stars_award_history.save()
                            end_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59,
                                                                           microsecond=999)
                            current_datetime = datetime.datetime.now()
                            timeout = (end_datetime - current_datetime).seconds
                            set_cache_answer_limit(member.cid, timeout)
                            # 根据pk结果处理信息
                            # level_list, level_list_new = await wechat_utils.get_level_list_info(
                            #     member, pk_status=pk_status, unlock=unlock,
                            #     pk_grade=own.get('grade', TYPE_DAN_GRADE_ONE))
                            level_list, level_list_new = await wechat_utils.get_level_list_info2(
                                member, pk_status=pk_status, unlock=unlock,
                                pk_grade=own.get('grade', TYPE_DAN_GRADE_ONE))

                            # 更新用户pk信息
                            # 存在钻石加减
                            diamond_changes = await wechat_utils.update_member_pk_info(
                                member, pk_status, unlock, own.get('grade', TYPE_DAN_GRADE_ONE))
                            # 判断钻石奖励（首次PK，首次获胜，连胜奖励）, 积分奖励，首次pk，每日首次pk
                            # 放在更新用户pk信息之后
                            _, diamond_reward_amount, diamond_reward_info = await wechat_utils.pk_award(
                                member, pk_status, continuous_win_times)

                            # 判断当前等级是否全部解锁
                            member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                            all_unlock = False
                            if member.dan_grade == TYPE_DAN_GRADE_ELEVEN and member.star_grade >= TYPE_STAR_GRADE_FIVE:
                                all_unlock = True
                            answer_times = await MemberGameHistory.count(
                                {'member_cid': member.cid, 'runaway_index': None})
                            r_dict['code'] = 1000
                            r_dict['all_unlock'] = all_unlock
                            r_dict['level_list'] = level_list
                            r_dict['level_list_new'] = level_list_new
                            r_dict['unlock'] = unlock
                            r_dict['diamond_changes'] = diamond_changes
                            r_dict['diamond_reward_amount'] = diamond_reward_amount
                            r_dict['reward_info'] = diamond_reward_info
                            r_dict['correct_list'] = correct_list
                            r_dict['answer_times'] = answer_times
                        else:
                            source_open_id = self.i_args.get('source_open_id', None)
                            if source_open_id:
                                pk_status = int(own.get('pk_status', STATUS_RESULT_GAME_PK_GIVE_UP))  # pk结果
                                source_member = await Member.find_one(dict(open_id=source_open_id))
                                if source_member:
                                    nick_name = member.nick_name if member.nick_name else '游客'
                                    content = None
                                    if pk_status == STATUS_RESULT_GAME_PK_WIN:
                                        content = '很遗憾，你的好友 %s 在对战中击败了您！' % nick_name
                                    elif pk_status == STATUS_RESULT_GAME_PK_FAILED:
                                        content = '恭喜你，在对战中击败了好友 %s! ' % nick_name
                                    elif pk_status == STATUS_RESULT_GAME_PK_TIE_BREAK:
                                        content = '您的好友 %s 在对战中和你战成了平局! ' % nick_name
                                    if content:
                                        await MemberNotice(
                                            member_cid=source_member.cid,
                                            category=CATEGORY_NOTICE_FRIENDS_PLAY,
                                            content=content).save()
                            game_history_count = await MemberGameHistory.count(
                                filtered={'member_cid': member.cid, 'runaway_index': None})
                            r_dict['can_friend_share'] = False
                            if game_history_count > 0:
                                r_dict['can_friend_share'] = True
                            r_dict['correct_list'] = correct_list
                            r_dict['code'] = 1010
                else:
                    r_dict['code'] = 1008
            else:
                r_dict['code'] = 1007
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappPersonalCenterWebViewHandler(BaseHandler):
    """
    个人中心web view
    """

    @decorators.render_template('wechat/miniapp/personal_center.html')
    async def get(self):
        open_id = self.get_argument('open_id', '')
        avatar = self.get_argument('head_url', '')
        wechat_nick_name = self.get_argument('name', '')
        user_info = {}
        try:
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    user_info = {
                        'wechat_nick_name': member.nick_name if not wechat_nick_name else '-',
                        'avatar': member.avatar if not avatar else avatar,
                        'integral': member.integral,  # 积分
                        'diamond': member.diamond,  # 钻石数
                        'dan_grade': TYPE_DAN_GRADE_DICT.get(member.dan_grade),  # 等级
                        'highest_win_times': member.highest_win_times if member.highest_win_times else 0  # 最高连胜
                    }
                    # 胜场数
                    win_amount = await MemberGameHistory.count(dict(status=STATUS_RESULT_GAME_PK_WIN))
                    # 败局数
                    fail_amount = await MemberGameHistory.count(dict(status=STATUS_RESULT_GAME_PK_FAILED))
                    # 平局数
                    draw_amount = await MemberGameHistory.count(dict(status=STATUS_RESULT_GAME_PK_TIE_BREAK))
                    # 逃跑数
                    escape_amount = await MemberGameHistory.count(dict(status=STATUS_RESULT_GAME_PK_GIVE_UP))

                    chart_data = [
                        {'name': '胜利:%s场' % win_amount, 'value': win_amount},
                        {'name': '失败:%s场' % fail_amount, 'value': fail_amount},
                        {'name': '平局:%s场' % draw_amount, 'value': draw_amount},
                        {'name': '逃跑:%s场' % escape_amount, 'value': escape_amount},
                    ]
                    user_info['win_amount'] = win_amount  # 胜场数
                    user_info['fail_amount'] = fail_amount  # 败局数
                    user_info['draw_amount'] = draw_amount  # 平局数
                    user_info['escape_amount'] = escape_amount  # 逃跑数
                    user_info['pie_chart_data'] = json.dumps(chart_data, ensure_ascii=False)

                    radar_chart_max = []
                    dimension_temp_dict = {}

                    for code, title in DIMENSION_SUBJECT_DICT.items():
                        radar_chart_max.append({
                            'name': title,
                            'max': 100,
                        })
                        dimension_temp_dict[code] = {
                            'total': 0,
                            'win': 0,
                        }

                    cursor = MemberGameHistory.find({'member_cid': member.cid})
                    while await cursor.fetch_next:
                        member_game_history = cursor.next_object()
                        result = member_game_history.result
                        if result:
                            for res in result:
                                subject_cid = res.subject_cid
                                true_answer = res.true_answer
                                if subject_cid:
                                    subject = await Subject.find_one(dict(cid=subject_cid))
                                    if subject.dimension:
                                        dimension_temp_dict[subject.dimension]['total'] += 1
                                        if true_answer:
                                            dimension_temp_dict[subject.dimension]['win'] += 1

                    value_list = []
                    for dimension_code in DIMENSION_SUBJECT_LIST:
                        total = dimension_temp_dict.get(dimension_code, {}).get('total')
                        win = dimension_temp_dict.get(dimension_code, {}).get('win')
                        if total:
                            value_list.append('%.2f' % (win * 100.0 / total))
                        else:
                            value_list.append('0')
                    user_info['radar_chart_max'] = json.dumps(radar_chart_max, ensure_ascii=False)
                    user_info['value_list'] = json.dumps(value_list, ensure_ascii=False)
        except Exception:
            logger.error(traceback.format_exc())

        return locals()


class MiniappPersonalCenterViewHandler(RestBaseHandler):
    """
    个人中心接口
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.i_args.get('open_id', None)
        try:
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    user_info = {
                        'diamond': member.diamond,  # 钻石数
                        'dan_grade': TYPE_DAN_GRADE_DICT.get(member.dan_grade),  # 等级
                        'highest_win_times': member.highest_win_times if member.highest_win_times else 0,  # 最高连胜
                        'wechat_nick_name': member.nick_name,
                        'avatar': member.avatar,
                        'sex': member.sex,
                        'age_group': member.age_group,
                        'education': member.education
                    }
                    # 胜场数
                    win_amount = await MemberGameHistory.count(
                        dict(member_cid=member.cid, status=STATUS_RESULT_GAME_PK_WIN))
                    # 败局数
                    fail_amount = await MemberGameHistory.count(
                        dict(member_cid=member.cid, status=STATUS_RESULT_GAME_PK_FAILED))
                    # 平局数
                    draw_amount = await MemberGameHistory.count(
                        dict(member_cid=member.cid, status=STATUS_RESULT_GAME_PK_TIE_BREAK))
                    # 逃跑数
                    escape_amount = await MemberGameHistory.count(
                        dict(member_cid=member.cid, status=STATUS_RESULT_GAME_PK_GIVE_UP))

                    chart_data = [
                        {'name': '胜利:%s场' % win_amount, 'value': win_amount},
                        {'name': '失败:%s场' % fail_amount, 'value': fail_amount},
                        {'name': '平局:%s场' % draw_amount, 'value': draw_amount},
                        {'name': '逃跑:%s场' % escape_amount, 'value': escape_amount}
                    ]
                    user_info['pie_chart_data'] = json.dumps(chart_data, ensure_ascii=False)

                    radar_chart_max = []
                    dimension_temp_dict = {}

                    for code, title in DIMENSION_SUBJECT_DICT.items():
                        radar_chart_max.append({
                            'name': title,
                            'max': 100,
                        })
                        dimension_temp_dict[code] = {
                            'total': 0.0,
                            'win': 0.0,
                        }

                    subject_dict = {}
                    subject_cursor = Subject.find(dict(record_flag=1))
                    while await subject_cursor.fetch_next:
                        subject_temp = subject_cursor.next_object()
                        if subject_temp:
                            subject_dict[subject_temp.cid] = subject_temp

                    cursor = await MemberGameHistory.find({'member_cid': member.cid}).to_list(None)
                    for member_game_history in cursor:
                        # while await cursor.fetch_next:
                        # member_game_history = cursor.next_object()
                        result = member_game_history.result
                        if result:
                            for res in result:
                                subject_cid = res.get('subject_cid')
                                true_answer = res.get('true_answer')
                                if subject_cid:
                                    # subject = await Subject.find_one(dict(cid=subject_cid))
                                    subject = subject_dict.get(subject_cid)
                                    if subject and subject.dimension:
                                        dimension_temp_dict[subject.dimension]['total'] += 1
                                        if true_answer:
                                            dimension_temp_dict[subject.dimension]['win'] += 1

                    value_list = []
                    for dimension_code in DIMENSION_SUBJECT_LIST:
                        total = dimension_temp_dict.get(dimension_code, {}).get('total')
                        win = dimension_temp_dict.get(dimension_code, {}).get('win')
                        if total:
                            value_list.append('%.2f' % (win * 100.0 / total))
                        else:
                            value_list.append('0.0')
                    user_data_info = {}
                    member_statistics = await MemberAccuracyStatistics.find_one(dict(member_cid=member.cid))
                    if member_statistics:
                        user_data_info['total_times'] = member_statistics.total_times  # 对战总场数
                        user_data_info['win_times'] = member_statistics.win_times  # 对战胜利场数
                        user_data_info['lose_times'] = member_statistics.lose_times  # 对战失败场数
                        user_data_info['escape_times'] = member_statistics.escape_times  # 对战逃跑场数
                        user_data_info['tie_times'] = member_statistics.tie_times  # 对战平局场数
                        user_data_info['total_quantity'] = member_statistics.total_quantity  # 总答题目数
                        user_data_info['correct_quantity'] = member_statistics.correct_quantity  # 答题正确数
                        user_data_info['dimension'] = member_statistics.dimension
                    subject_statistics = await SubjectAccuracyStatistics.find_one(dict(record_flag=1))
                    subject_data_info = {}
                    if subject_statistics:
                        subject_data_info['dimension_dict'] = subject_statistics.dimension
                        subject_data_info['age_group'] = subject_statistics.age_group
                        subject_data_info['education'] = subject_statistics.education
                        subject_data_info['gender'] = subject_statistics.gender

                    # user_info['radar_chart_max'] = radar_chart_max
                    # user_info['value_list'] = value_list
                    r_dict['user_info'] = user_info
                    r_dict['user_data_info'] = user_data_info
                    r_dict['subject_data_info'] = subject_data_info
                    r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappFriendMemberGetViewHandler(RestBaseHandler):
    """
    获取匹配对手数据
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.i_args.get('open_id', None)
            opponent_open_id = self.i_args.get('opponent_open_id', None)
            if open_id and opponent_open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                opponent = await Member.find_one(dict(open_id=opponent_open_id, status=STATUS_USER_ACTIVE))
                if member and opponent:
                    try:
                        # 随机查询出一条数据
                        opponent_base = {}
                        # 判断对手连胜
                        opponent_continuous_win_times = 0
                        # 当前连胜次数
                        last_pk_list = await MemberGameHistory.aggregate([
                            MatchStage({'member_cid': opponent.cid}),
                            SortStage([('fight_datetime', DESC)]),
                            LimitStage(1)
                        ]).to_list(1)

                        if last_pk_list and last_pk_list[0].continuous_win_times:
                            opponent_continuous_win_times = last_pk_list[0].continuous_win_times

                        opponent_base['nick_name'] = opponent.nick_name
                        opponent_base['dan_grade_title'] = TYPE_DAN_GRADE_DICT.get(opponent.dan_grade, '')
                        opponent_base['avatar_url'] = opponent.avatar
                        opponent_base['open_id'] = opponent.open_id
                        opponent_base['city'] = opponent.needless.get('city', '')
                        opponent_base['continuous_win_times'] = opponent_continuous_win_times

                        r_dict['code'] = 1000
                        r_dict['opponent_base'] = opponent_base

                        # 判断自己连胜
                        own_continuous_win_times = 0
                        # 当前连胜次数
                        own_last_pk_list = await MemberGameHistory.aggregate([
                            MatchStage({'member_cid': member.cid}),
                            SortStage([('fight_datetime', DESC)]),
                            LimitStage(1)
                        ]).to_list(1)

                        if own_last_pk_list and own_last_pk_list[0].continuous_win_times:
                            own_continuous_win_times = own_last_pk_list[0].continuous_win_times

                        r_dict['own_base'] = {
                            'dan_grade_title': TYPE_DAN_GRADE_DICT.get(member.dan_grade, ''),
                            'city': member.needless.get('city', ''),
                            'nick_name': member.nick_name if member.nick_name else '',
                            'avatar_url': member.avatar if member.avatar else '',
                            'continuous_win_times': own_continuous_win_times
                        }
                    except ValueError:
                        r_dict['code'] = 1009
                else:
                    r_dict['code'] = 1008
            else:
                r_dict['code'] = 1007
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappGetFirendQuestionListViewHandler(RestBaseHandler):
    """
    获取题目数据和镜像数据
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.i_args.get('open_id', None)
            opponent_open_id = self.i_args.get('opponent_open_id', None)
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                opponent = await Member.find_one(dict(open_id=opponent_open_id, status=STATUS_USER_ACTIVE))
                if member and opponent:
                    opponent, question_list, init_own_answer_list = await wechat_utils.generate_opponent_answers(
                        opponent)
                    r_dict['opponent'] = opponent
                    r_dict['question_list'] = question_list
                    r_dict['init_own_answers'] = init_own_answer_list
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1008
            else:
                r_dict['code'] = 1007
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappRankingListViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            members = await Member.find({'status': STATUS_USER_ACTIVE}).sort(
                [('dan_grade', -1), ('star_grade', -1)]).limit(30).to_list(30)

            rank_list = []
            for member in members:
                all_star = wechat_utils.get_member_all_star(member)
                member_dict = {
                    'wechat_nick_name': member.nick_name,  # 用户名
                    'avatar': member.avatar,  # 头像
                    'all_star': all_star,  # 当前总星数
                    'dan_grade': TYPE_DAN_GRADE_DICT.get(member.dan_grade),  # 等级
                }
                rank_list.append(member_dict)  # 排行榜列表
            r_dict['rank_list'] = rank_list
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappVaultBankAwardViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.i_args.get('open_id', None)
        try:
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    vault_bank_list = await VaultDiamondBank.find({"quantity": {'$ne': None}}).to_list(1)
                    if vault_bank_list:
                        vault_bank = vault_bank_list[0]
                        start_datetime = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                        end_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=999)
                        # 当天获得奖励的次数
                        count = await MemberDiamondDetail.count(
                            {
                                "member_cid": member.cid,
                                "source": SOURCE_MEMBER_DIAMOND_VAULT_REWARD,
                                "reward_datetime": {'$lte': end_datetime, '$gte': start_datetime},
                            }
                        )
                        # 次数限制 0代表无限次
                        if count != 0 and vault_bank.times > 0 and count > vault_bank.times:
                            r_dict['code'] = 1002  # 达到领取上限
                        else:
                            # 获取奖励的最新时间
                            member_diamond_detail = await MemberDiamondDetail.find(
                                {'$and':
                                     [{"member_cid": member.cid},
                                      {"source": SOURCE_MEMBER_DIAMOND_VAULT_REWARD}, ]}

                            ).sort([('reward_datetime', -1)]).limit(1).to_list(1)
                            # 奖励数量
                            quantity = int(vault_bank.quantity)
                            if member_diamond_detail:
                                # 当前时间
                                current_datetime = datetime.datetime.now()
                                # 距上次奖励的时间间隔
                                spacing_seconds = (
                                        current_datetime - member_diamond_detail[0].reward_datetime).seconds
                                # 时间限制
                                seconds = int(vault_bank.minutes) * 60
                                if spacing_seconds >= seconds:
                                    # 时间间隔大于时限 奖励全部
                                    award_member_diamond = quantity
                                else:
                                    # 时间间隔小于时限 奖励按时间计算
                                    need_quantity = (float(quantity) / float(seconds)) * spacing_seconds  # 获得的奖励数量
                                    award_member_diamond = int(need_quantity)
                            else:
                                award_member_diamond = quantity  # 没有领取记录，奖励全部
                            await update_diamond_reward(member.cid, SOURCE_MEMBER_DIAMOND_VAULT_REWARD,
                                                        award_member_diamond)

                            # 钻石数
                            member_diamond = member.diamond
                            member.diamond = member_diamond + award_member_diamond  # +金库奖励的钻石
                            member.updated_dt = datetime.datetime.now()
                            # 金库奖励
                            await member.save()
                            r_dict['remain_seconds'] = int(vault_bank.minutes) * 60  # 剩余奖励时间(初始化)
                            r_dict['total_seconds'] = int(vault_bank.minutes) * 60  # 总时间限制
                            r_dict['can_get_diamond'] = 0  # 可领取钻石（每次点击领取后初始化）
                            r_dict['total_diamond'] = vault_bank.quantity  # 总奖励数量
                            r_dict['member_diamond'] = member_diamond + award_member_diamond  # 用户所有的钻石数
                        r_dict['code'] = 1
                    else:
                        r_dict['code'] = 1001  # 未设置金库
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappVaultBankInfoViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.i_args.get('open_id', None)
        try:
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    vault_bank_list = await VaultDiamondBank.find({"quantity": {'$ne': None}}).to_list(1)
                    if vault_bank_list:
                        vault_bank = vault_bank_list[0]
                        member_diamond_detail = await MemberDiamondDetail.find(
                            {'$and':
                                 [{"member_cid": member.cid},
                                  {"source": SOURCE_MEMBER_DIAMOND_VAULT_REWARD}, ]}

                        ).sort(
                            [('reward_datetime', -1)]).limit(1).to_list(1)  # 获取奖励的时间
                        quantity = int(vault_bank.quantity)  # 奖励数量
                        if member_diamond_detail:
                            # 当前时间
                            current_datetime = datetime.datetime.now()
                            # 距上次奖励的时间间隔
                            spacing_seconds = (
                                    current_datetime - member_diamond_detail[0].reward_datetime).seconds
                            # 时间限制
                            seconds = int(vault_bank.minutes) * 60
                            remain_seconds = seconds - spacing_seconds if seconds > spacing_seconds else 0
                            if spacing_seconds >= seconds:
                                can_get_diamond = quantity
                            else:
                                need_quantity = (float(quantity) / float(seconds)) * spacing_seconds
                                can_get_diamond = int(need_quantity)
                        else:
                            remain_seconds = 0
                            can_get_diamond = quantity
                        r_dict['remain_seconds'] = remain_seconds  # 剩余奖励时间
                        r_dict['total_seconds'] = int(vault_bank.minutes) * 60  # 总时间限制
                        r_dict['can_get_diamond'] = can_get_diamond  # 可领取钻石数量
                        r_dict['total_diamond'] = vault_bank.quantity  # 总奖励数量
                        r_dict['code'] = 1000
                    else:
                        r_dict['code'] = 1001  # 未设置金库
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappAnswerLimitViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.i_args.get('open_id', None)
        try:
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    value = get_cache_answer_limit(member.cid)
                    if value >= ANSWER_LIMIT_NUMBER:
                        r_dict['code'] = 1001
                    else:
                        r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappSubjectWrongStatisticsViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.i_args.get('open_id', None)
        try:
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    # match = MatchStage({'cid': member.cid})
                    subject_wrong_statistics_list = await MemberWrongSubject.find(
                        dict(member_cid=member.cid, status=STATUS_WRONG_SUBJECT_ACTIVE)).sort(
                        [('wrong_dt', DESC)]).limit(10).to_list(10)
                    subject_cid_list = [(subject_wrong.subject_cid, subject_wrong.option_cid) for subject_wrong in
                                        subject_wrong_statistics_list]
                    question_list = await wechat_utils.deal_wrong_questions(subject_cid_list)
                    r_dict['question_list'] = question_list
                    # lookup_subject = LookupStage(Subject, 'cid', 'subject_cid')
                    # lookup_option = LookupStage(SubjectOption, 'cid', 'subject_cid')
                    # subject_wrong_statistics_list = MemberWrongSubject.aggregate([match, lookup_subject])
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1002
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappShareAwardViewHandler(RestBaseHandler):
    """
    分享奖励钻石
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.i_args.get('open_id', None)
        try:
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    reward_info = []
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
                        reward_info.append({
                            'title': SOURCE_MEMBER_DIAMOND_DICT.get(SOURCE_MEMBER_DIAMOND_DAILY_SHARE),
                            'diamond_num': m_diamond
                        })
                    # 用户的钻石
                    r_dict['diamonds_num'] = member.diamond
                    r_dict['reward_info'] = reward_info
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1001
            else:
                r_dict['code'] = 1002
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class MiniappGetDimensionViewHandler(RestBaseHandler):
    """
    获取所有维度信息
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.i_args.get('open_id', None)
        try:
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    subject_dimension_list = await SubjectDimension.find(
                        dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=None)).to_list(None)
                    p_dimension_dict = {}
                    for subject_dimension in subject_dimension_list:
                        p_dimension_dict[subject_dimension.cid] = {}
                        p_dimension_dict[subject_dimension.cid]['code'] = subject_dimension.code
                        p_dimension_dict[subject_dimension.cid]['title'] = subject_dimension.title
                        p_dimension_dict[subject_dimension.cid]['ordered'] = subject_dimension.ordered
                        children = p_dimension_dict[subject_dimension.code]['children'] = {}

                        c_dimension_list = await  SubjectDimension.find(
                            dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=subject_dimension.cid)).to_list(
                            None)
                        if c_dimension_list:
                            for c_dimension in c_dimension_list:
                                children[c_dimension.cid] = {}
                                children[c_dimension.cid]['code'] = c_dimension.code
                                children[c_dimension.cid]['title'] = c_dimension.title
                                children[c_dimension.cid]['ordered'] = c_dimension.ordered

                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1001
            else:
                r_dict['code'] = 1002
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappGetMemberFriendRankingViewHandler(RestBaseHandler):
    """
    获取所有维度信息
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.i_args.get('open_id', None)
        try:
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    member_friend_list = await MemberFriend.find(dict(member_cid=member.cid)).to_list(None)
                    member_friend_cid_list = [member_friend.friend_cid for member_friend in member_friend_list]
                    member_friend_cid_list.append(member.cid)
                    member_cursor = Member.find({
                        'cid': {'$in': member_friend_cid_list}
                    }).sort([('dan_grade', -1), ('star_grade', -1)]).limit(30)
                    rank_list = []
                    while await member_cursor.fetch_next:
                        member_friend = member_cursor.next_object()
                        all_star = wechat_utils.get_member_all_star(member_friend)
                        member_dict = {
                            'wechat_nick_name': member_friend.nick_name,  # 用户名
                            'avatar': member_friend.avatar,  # 头像
                            'all_star': all_star,  # 当前总星数
                            'dan_grade': TYPE_DAN_GRADE_DICT.get(member_friend.dan_grade),  # 等级
                        }
                        rank_list.append(member_dict)  # 排行榜列表
                    r_dict['rank_list'] = rank_list
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1001
            else:
                r_dict['code'] = 1002
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappGetOnlineMemberQuantityViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            quantity = await Member.count(
                {'login_datetime': {'$gte': datetime.datetime.now() - datetime.timedelta(days=7)}})
            r_dict['code'] = 1000
            r_dict['quantity'] = quantity
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappGetMemberNoticeViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.i_args.get('open_id', None)
            member = await Member.find_one(dict(open_id=open_id))
            if member:
                notice_list = await MemberNotice.find(
                    dict(member_cid=member.cid, category=CATEGORY_NOTICE_FRIENDS_PLAY)).sort(
                    [('status', ASC), ('notice_datetime', DESC)]).limit(5).to_list(None)
                msg_list = []
                if notice_list:
                    for notice in notice_list:
                        msg_list.append({
                            'cid': notice.cid,
                            'content': notice.content,
                            'notice_datetime': notice.notice_datetime,
                            'read': False if notice.status == STATUS_NOTICE_UNREAD else True
                        })
                if msg_list:
                    r_dict['code'] = 1000
                    r_dict['msg_list'] = msg_list
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappMemberNoticeReadViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            notice_cid_list = self.i_args.get('notice_cid_list', None)
            if notice_cid_list:
                update_list = []
                for notice_cid in notice_cid_list:
                    update_list.append(UpdateOne({'cid': notice_cid}, {'$set': {'status': STATUS_NOTICE_READ}}))
                if update_list:
                    await MemberNotice.update_many(update_list)
                    r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappGetTestSubject(RestBaseHandler):
    """
    获取基准测试或者毕业测试题库
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        """

        :return:
        """
        question_list = list()
        r_dict = {'code': 0, 'question_list': question_list}

        category = self.i_args.get('category', None)
        if not category:
            return r_dict

        try:
            sort_stage = SortStage([('code', ASC)])
            stage_list = [
                MatchStage({'category_use': int(category), 'status': STATUS_SUBJECT_ACTIVE}),
                LookupStage(SubjectOption, let={'cid': '$cid'},
                            pipeline=[{'$match': {'$expr': {'$and': [{'$eq': ['$subject_cid', '$$cid']}]}}},
                                      sort_stage], as_list_name='options'),
                LookupStage(UploadFiles, 'image_cid', 'cid', 'file_list'),
                sort_stage
            ]

            cursor = Subject.aggregate(stage_list=stage_list)

            while await cursor.fetch_next:
                question = cursor.next_object()

                options = []
                for opt in question.options:
                    options.append({'id': opt.cid, 'title': opt.title, 'true_answer': opt.correct})

                title_picture = question.file_list[0].title if question.file_list else ''
                if title_picture:
                    title_picture_url = '%s://%s%s%s%s' % (SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/',
                                                           title_picture)
                else:
                    title_picture_url = ''

                question = {'id': question.cid,
                            'subject_category': CATEGORY_SUBJECT_KNOWLEDGE_DICT.get(question.category),
                            'title': question.title, 'options': options, 'is_current': False,
                            'title_picture_url': title_picture_url}

                question_list.append(question)

            if question_list:
                question_list[0]['is_current'] = True

            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappTestSubmit(RestBaseHandler):
    """
    提交基准测试或毕业测试
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        """
        input: category
               subject_count
               correct_num
               subjects: (subject_id, owner_answer_id)
        :return:
        """
        r_dict = {'code': 0, 'rank': 0}
        open_id = self.i_args.get('open_id', None)

        if not open_id:
            r_dict['code'] = 1007
            return r_dict

        r_dict['code'] = 1000

        member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
        exam_datetime = datetime.datetime.now()
        category = self.i_args.get('category', None)
        subject_count = self.i_args.get('subject_count', None)
        correct_num = self.i_args.get('correct_num', None)

        answers = self.i_args.get('answers', None)

        try:
            accuracy = int(correct_num) / int(subject_count)

            check_history = await MemberExamHistory.find(
                {'member_cid': member.cid, 'category': int(category)}).to_list(1)
            if check_history:
                history = check_history[0]
            else:
                history = MemberExamHistory(member_cid=member.cid, category=int(category))
            history.exam_datetime = exam_datetime
            history.accuracy = accuracy
            await history.save()

            for s_cid, opt_cid in answers.items():
                match = MatchStage({'cid': s_cid})
                opt_lookup = LookupStage(SubjectOption, 'cid', 'subject_cid', 'options')
                subject = await Subject.aggregate(stage_list=[match, opt_lookup]).to_list(1)

                opt_correct_id = None
                for opt in subject[0].options:
                    if opt.correct:
                        opt_correct_id = opt.cid

                if opt_cid != opt_correct_id:
                    check_subject = await MemberWrongSubject.find(
                        {'member_cid': member.cid, 'subject_cid': s_cid}).to_list(1)
                    if check_subject:
                        wrong_subject = check_subject[0]
                    else:
                        wrong_subject = MemberWrongSubject()

                    wrong_subject.member_cid = member.cid
                    wrong_subject.subject_cid = s_cid
                    wrong_subject.option_cid = opt_cid
                    wrong_subject.wrong_dt = exam_datetime
                    await wrong_subject.save()
                else:
                    subject = await MemberWrongSubject.find(
                        {'member_cid': member.cid, 'subject_cid': s_cid}).to_list(None)
                    for sub in subject:
                        await sub.delete()

            r_dict['rank'] = await self.get_rank(accuracy, category)
        except:
            logger.error(traceback.format_exc())

        return r_dict

    @staticmethod
    async def get_rank(accuracy, category):
        """

        :return:
        """
        count = await MemberExamHistory.count({'category': int(category)})
        if count == 0:
            return 0
        below_num = await MemberExamHistory.count({'category': int(category), 'accuracy': {'$lte': accuracy}})
        return int(below_num / count * 100)


class MiniappGetSubjectResolving(RestBaseHandler):
    """
    获取答案解析
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        """

        :return:
        """
        question_list = []
        r_dict = {'code': 0, 'question_list': question_list}

        open_id = self.i_args.get('open_id', None)
        if not open_id:
            return r_dict

        member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
        question_ids = self.i_args.get('question_ids', [])
        try:
            r_dict['code'] = 1000

            questions_wrong = await self.get_wrong_question(member.cid, question_ids)
            question_correct_ids = set(question_ids) ^ {q.get('id') for q in questions_wrong}

            questions_correct = list()
            if question_correct_ids:
                questions_correct = await self.get_correct_question(question_correct_ids)

            q_wrong_dict = {q.get('id'): q for q in questions_wrong}
            q_correct_dict = {q.get('id'): q for q in questions_correct}

            question_list = []
            for q_cid in question_ids:
                if q_cid in q_wrong_dict.keys():
                    question_list.append(q_wrong_dict.get(q_cid))
                elif q_cid in q_correct_dict.keys():
                    question_list.append(q_correct_dict.get(q_cid))
                else:
                    msg = 'some subject has missing , please check.'
                    logger.error(msg)
                    r_dict = {'code': 0, 'msg': msg}
                    return r_dict

            r_dict['question_list'] = question_list
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict

    @staticmethod
    async def get_correct_percent(subject_cid):
        """

        :param subject_cid:
        :return:
        """
        correct_percent = 0
        # cursor = MemberSubjectStatistics.find({'subject_cid': subject_cid})
        #
        # try:
        #     index = 0
        #     while await cursor.fetch_next:
        #         member = cursor.next_object()
        #         correct_percent += member.accuracy
        #         index += 1

        # if index != 0:
        # return '%.2f %%' % (correct_percent / index)
        from random import randint

        return "%d%%" % randint(70, 99)
        # except Exception:
        #     logger.error(traceback.format_exc())
        # return '0%'

    async def get_wrong_question(self, member_id, question_ids):
        """

        :param member_id:
        :param question_id:
        :return:
        """
        stage_list = [
            MatchStage({'cid': {'$in': question_ids}}),
            LookupStage(SubjectOption, 'cid', 'subject_cid', 'options'),
            LookupStage(MemberWrongSubject, let={'cid': '$cid'}, as_list_name='wrong_subjects', pipeline=[
                {'$match': {
                    '$expr': {'$and': [{'$eq': ['$subject_cid', '$$cid']}, {'$eq': ['$member_cid', member_id]}]}}}
            ]),
            LookupStage(UploadFiles, 'image_cid', 'cid', 'file_list'),
        ]

        subjects = await Subject.aggregate(
            stage_list=stage_list).to_list(None)

        if not subjects:
            return None

        questions = list()
        for subject in subjects:
            question = dict()
            question['id'] = subject.cid
            question['title'] = subject.title
            question['resolving'] = subject.resolving

            options = []
            for opt in subject.options:
                option = {'id': opt.cid, 'title': opt.title, 'true_answer': opt.correct, }
                if subject.wrong_subjects[-1].option_cid == opt.cid:
                    option['show_false'] = 'option_false'
                else:
                    option['show_false'] = ''

                options.append(option)

            question['option_list'] = options
            question['category_name'] = CATEGORY_SUBJECT_KNOWLEDGE_DICT.get(subject.category)
            question['knowledge_first'] = KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_first)
            question['knowledge_second'] = KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_second)
            question['difficulty'] = subject.difficulty
            question['correct_percent'] = await self.get_correct_percent(subject.cid)

            title_picture = subject.file_list[0].title if subject.file_list else ''
            if title_picture:
                title_picture_url = '%s://%s%s%s%s' % (SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/',
                                                       title_picture)
            else:
                title_picture_url = ''

            question['picture_url'] = title_picture_url

            questions.append(question)
        return questions

    async def get_correct_question(self, question_ids):
        """

        :param question_id:
        :return:
        """
        stage_list = [
            MatchStage({'cid': {'$in': question_ids}}),
            LookupStage(SubjectOption, 'cid', 'subject_cid', 'options'),
            LookupStage(UploadFiles, 'image_cid', 'cid', 'file_list'),
        ]

        subjects = await Subject.aggregate(stage_list=stage_list).to_list(None)

        if not subjects:
            return None

        questions = list()
        for subject in subjects:
            question = dict()
            question['id'] = subject.cid
            question['title'] = subject.title
            question['resolving'] = subject.resolving

            options = []
            for opt in subject.options:
                options.append({'id': opt.cid, 'title': opt.title, 'true_answer': opt.correct, 'show_false': ''})

            question['option_list'] = options
            question['category_name'] = CATEGORY_SUBJECT_KNOWLEDGE_DICT.get(subject.category)
            question['knowledge_first'] = KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_first)
            question['knowledge_second'] = KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_second)
            question['difficulty'] = subject.difficulty
            question['correct_percent'] = await self.get_correct_percent(subject.cid)

            title_picture = subject.file_list[0].title if subject.file_list else ''
            if title_picture:
                title_picture_url = '%s://%s%s%s%s' % (SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/',
                                                       title_picture)
            else:
                title_picture_url = ''

            question['picture_url'] = title_picture_url

            questions.append(question)
        return questions


class MiniappCheckUserInfoAndBenchMark(RestBaseHandler):
    """
    检查用户信息是否补全, 检查是否进行过基准测试
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0, 'is_msg_done': False, 'is_benchmark_done': False}
        try:
            open_id = self.i_args.get('open_id', None)
            member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))

            r_dict['code'] = 1000
            if await self._is_msg_completed(member):
                r_dict['is_msg_done'] = True

            if await self._is_benchmark_been_done(member):
                r_dict['is_benchmark_done'] = True
        except Exception:
            r_dict = {'code': 0}
            logger.error(traceback.format_exc())

        return r_dict

    @staticmethod
    async def _is_msg_completed(member):
        """
        检查用户信息是否补全
        :return:
        """
        try:
            if member.age_group and member.education:
                return True
        except Exception:
            logger.error(traceback.format_exc())
        return False

    @staticmethod
    async def _is_benchmark_been_done(member):
        """
        检查是否进行过基准测试
        :return:
        """
        try:
            exam_count = await MemberExamHistory.count(
                {'member_cid': member.cid, 'category': CATEGORY_SUBJECT_BENCHMARK})
            if exam_count > 0:
                return True
        except Exception:
            logger.error(traceback.format_exc())
        return False


class MiniappGetLevelListInfoViewHandler2(RestBaseHandler):
    """
    获取所有关卡
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.i_args.get('open_id', None)
            if open_id:
                member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                if member:
                    # 根据当前段位获取段位列表显示信息
                    level_list, _ = await wechat_utils.get_level_list_info2(member, pk_status=None, unlock=None)
                    r_dict['code'] = 1000
                    r_dict['level_list'] = level_list

                    current_level = member.dan_grade
                    if current_level is None:
                        current_level = TYPE_DAN_GRADE_ONE

                    if current_level >= len(level_list):
                        current_level = len(level_list)
                    elif current_level - 2 <= 0:
                        current_level = 1
                    else:
                        current_level -= 2

                    r_dict['current_level'] = current_level
                else:
                    r_dict['code'] = 1008
            else:
                r_dict['code'] = 1007
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MiniappCheckStageAndGraduation(RestBaseHandler):
    """
    检查毕业测试是否完成
    """

    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0, 'is_stage_cleared': False, 'is_graduation_done': False}
        open_id = self.i_args.get('open_id', None)

        try:
            r_dict['code'] = 1000
            member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))

            if await self.is_stage_clear(member):
                r_dict['is_stage_cleared'] = True

            if await self.is_graduation_done(member):
                r_dict['is_graduation_done'] = True

            return r_dict
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict

    @staticmethod
    async def is_stage_clear(member: Member):
        """检查是否段位通关

        :param member:
        :return:
        """
        dan_grade = await GameDanGrade.find({'status': STATUS_GAME_CHECK_POINT_ACTIVE}).sort([('index', DESC)]).to_list(
            None)

        history = await MemberGameHistory.find_one(
            filtered={'member_cid': member.cid, 'dan_grade': dan_grade[0].index,
                      'status': STATUS_RESULT_CHECK_POINT_WIN, 'record_flag': 1})
        if history:
            return True
        return False

    @staticmethod
    async def is_graduation_done(member):
        """

        :param member:
        :return:
        """
        try:
            if await MemberExamHistory.count({'member_cid': member.cid, 'category': CATEGORY_SUBJECT_GRADUATION}) > 0:
                return True
        except Exception:
            logger.error(traceback.format_exc())

        return False


URL_MAPPING_LIST = [
    url(r'/wechat/miniapp/auth/', MiniappAuthViewHandler, name='wechat_miniapp_auth'),
    url(r'/wechat/miniapp/update/wechat_info/', MiniappWechatInfoUpdateViewHandler,
        name='wechat_miniapp_update_wechat_info'),
    url(r'/wechat/miniapp/home_page/', MiniappHomePageViewHandler, name='wechat_miniapp_home_page'),
    url(r'/wechat/miniapp/get_dan_grade/', MiniappDanGradeGetViewHandler, name='wechat_miniapp_get_dan_grade'),  #
    url(r'/wechat/miniapp/get_diamond_amount/', MiniappDiamonAmountGetViewHandler,
        name='wechat_miniapp_get_diamond_amount'),
    url(r'/wechat/miniapp/get_pk_member/', MiniappFightMemberGetViewHandler, name='wechat_miniapp_get_pk_member'),
    url(r'/wechat/miniapp/get_question_list/', MiniappGetQuestionListViewHandler,
        name='wechat_miniapp_get_question_list'),
    url(r'/wechat/miniapp/get_user_info/', MiniappGetUserInfoViewHandler, name='wechat_miniapp_get_user_info'),
    url(r'/wechat/miniapp/get_level_list_info/', MiniappGetLevelListInfoViewHandler,
        name='wechat_miniapp_get_level_list_info'),
    url(r'/wechat/miniapp/submit_answers/', MiniappSubmitAnswersViewHandler, name='wechat_miniapp_submit_answers'),
    url(r'/wechat/miniapp/personal_center_web/', MiniappPersonalCenterWebViewHandler,
        name='wechat_miniapp_personal_center_web'),
    url(r'/wechat/miniapp/personal_center/', MiniappPersonalCenterViewHandler, name='wechat_miniapp_personal_center'),
    url(r'/wechat/miniapp/update/user_info/', MiniappUserInfoUpdateViewHandler, name='wechat_miniapp_update_user_info'),
    url(r'/wechat/miniapp/get/user_info/', MiniappUserInfoGetViewHandler, name='wechat_miniapp_get_user_detail'),
    url(r'/wechat/miniapp/get_friend_member/', MiniappFriendMemberGetViewHandler,
        name='wechat_miniapp_get_friend_member'),
    url(r'/wechat/miniapp/get_friend_question_list/', MiniappGetFirendQuestionListViewHandler,
        name='wechat_miniapp_get_friend_question_list'),
    url(r'/wechat/miniapp/get_ranking_list/', MiniappRankingListViewHandler, name='wechat_miniapp_get_ranking_list'),
    url(r'/wechat/miniapp/vault_bank_award/', MiniappVaultBankAwardViewHandler, name='wechat_miniapp_vault_bank_award'),
    url(r'/wechat/miniapp/get_vault_bank_info/', MiniappVaultBankInfoViewHandler,
        name='wechat_miniapp_vault_bank_info'),
    url(r'/wechat/miniapp/answer_limit/', MiniappAnswerLimitViewHandler, name='wechat_miniapp_answer_limit'),
    url(r'/wechat/miniapp/subject_wrong_statistics/', MiniappSubjectWrongStatisticsViewHandler,
        name='wechat_miniapp_subject_wrong_statistics'),
    url(r'/wechat/miniapp/share_award/', MiniappShareAwardViewHandler, name='wechat_miniapp_share_award'),
    url(r'/wechat/miniapp/get_dimension/', MiniappGetDimensionViewHandler, name='wechat_miniapp_get_dimension'),
    url(r'/wechat/miniapp/get_member_friend_ranking_list/', MiniappGetMemberFriendRankingViewHandler,
        name='wechat_miniapp_get_member_friend_ranking_list'),
    url(r'/wechat/miniapp/get_online_member_quantity/', MiniappGetOnlineMemberQuantityViewHandler,
        name='wechat_miniapp_get_online_member_quantity'),
    url(r'/wechat/miniapp/get_member_notice/', MiniappGetMemberNoticeViewHandler,
        name='wechat_miniapp_get_member_notice'),
    url(r'/wechat/miniapp/read_member_notice/', MiniappMemberNoticeReadViewHandler,
        name='wechat_miniapp_read_member_notice'),
    url(r'/wechat/miniapp/get_test_subjects/', MiniappGetTestSubject,
        name='wechat_miniapp_get_subjects'),
    url(r'/wechat/miniapp/submit_test_subject/', MiniappTestSubmit, name='wechat_miniapp_submit_test_subject'),
    url(r'/wechat/miniapp/get_subject_resolving/', MiniappGetSubjectResolving,
        name='wechat_miniapp_get_subject_resolving'),
    url(r'/wechat/miniapp/check_userinfo_and_benchmark/', MiniappCheckUserInfoAndBenchMark,
        name='wechat_miniapp_check_userinfo_and_benchmark'),
    url(r'/wechat/miniapp/check_stage_and_graduation/', MiniappCheckStageAndGraduation,
        name='wechat_miniapp_check_stage_and_graduation'),
    url(r'/wechat/miniapp/get_level_list_info2/', MiniappGetLevelListInfoViewHandler2,
        name='wechat_miniapp_get_level_list_info2'),
]
