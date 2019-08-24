# !/usr/bin/python

import copy
import datetime
import traceback

from bson import ObjectId
from pymongo import ReadPreference
from tornado.httpclient import AsyncHTTPClient
from tornado.web import url

from actions.applet import find_member_by_open_id
from actions.applet.utils import parse_wechat_info
from commons.common_utils import get_increase_code
from db.enums import CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION, CATEGORY_NOTICE_AWARD, STATUS_RACE_ACTIVE, \
    CATEGORY_MEMBER_SHARE_LIST, CATEGORY_NOTICE_SYSTEM
from db.enums import STATUS_USER_ACTIVE, TYPE_DAN_GRADE_DICT, SOURCE_TYPE_MEMBER_SYSTEM, STATUS_USER_INACTIVE, SEX_NONE, \
    CATEGORY_NOTICE_FRIENDS_PLAY, STATUS_NOTICE_UNREAD, STATUS_NOTICE_READ
from db.models import Member, MemberAccuracyStatistics, SubjectAccuracyStatistics, MemberFriend, \
    MemberNotice, RaceMapping, AdministrativeDivision, Race
from db.models import MemberExamHistory, MemberShareStatistics, PersonalCenterViewedStatistics
from enums import KEY_INCREASE_MEMBER_CODE
from logger import log_utils
from motorengine import ASC, UpdateOne
from motorengine import DESC
from settings import MINI_APP_SECRET, MINI_APP_ID, SERVER_PROTOCOL, SERVER_HOST
from tasks.instances.task_member_property_statistics import start_task_member_property_statistics
from tasks.instances.task_update_member_info import update_memberinfo_in_other_collections
from web import WechatAppletHandler, decorators, json
from wechat import API_CODE_EXCHANGE_SESSION_URL

logger = log_utils.get_logging('a_member', 'a_member.log')


class AppletMemberAuthViewHandler(WechatAppletHandler):
    """微信用户首次使用校验"""

    @decorators.render_json
    async def post(self):
        r_dict = {'code': 0}
        try:
            args_dict = json.loads(self.request.body)
            auth_code = args_dict.get('auth_code', None)
            user_info = args_dict.get('userInfo', {})
            if not user_info:
                user_info = {}

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
                        member = await find_member_by_open_id(open_id)
                        if not member:
                            if source is not None:
                                source_type = str(source)
                            else:
                                source_type = str(SOURCE_TYPE_MEMBER_SYSTEM)
                            # 创建用户
                            member = Member(
                                id=ObjectId(),
                                code=get_increase_code(KEY_INCREASE_MEMBER_CODE),
                                open_id=open_id,
                                source=source_type,
                                status=STATUS_USER_ACTIVE
                            )
                            wechat_info = await parse_wechat_info(user_info)
                            member.sex = int(user_info.get('gender')) if user_info.get('gender') else SEX_NONE

                            member.avatar = wechat_info.get('avatar') if wechat_info.get('avatar') else '%s://%s%s' % (
                                SERVER_PROTOCOL, SERVER_HOST, self.static_url('images/default/visitor.png'))
                            member.nick_name = wechat_info.get('nick_name') if wechat_info.get('nick_name') else '游客'

                            if wechat_info:
                                member.province_code = wechat_info.get('province_code')
                                member.city_code = wechat_info.get('city_code')
                                member.district_code = wechat_info.get('district_code')

                                member.needless['province'] = wechat_info.get('province_name')
                                member.needless['city'] = wechat_info.get('city_name')
                                member.needless['district'] = wechat_info.get('district_name')

                                member.wechat_info = user_info

                            member.register_datetime = datetime.datetime.now()
                            member.login_datetime = datetime.datetime.now()
                            member.login_times += 1

                            await member.save()

                            # 会员属性统计
                            await start_task_member_property_statistics(member)

                            r_dict['open_id'] = open_id
                            r_dict['session_key'] = session_key
                            r_dict['code'] = 1000
                        else:
                            if member.status == STATUS_USER_INACTIVE:
                                r_dict['code'] = 1002
                            else:
                                member.login_datetime = datetime.datetime.now()
                                member.login_times += 1
                                await member.save()

                                r_dict['open_id'] = open_id
                                r_dict['session_key'] = session_key
                                r_dict['code'] = 1000
                        if friend_open_id:
                            friend = await find_member_by_open_id(friend_open_id)
                            if friend:
                                friend_member = MemberFriend(member_cid=member.cid, friend_cid=friend.cid)
                                await friend_member.save()
                                member_friend = MemberFriend(member_cid=friend.cid, friend_cid=member.cid)
                                await member_friend.save()
                else:
                    r_dict['code'] = 1003
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletMemberUpdateViewHandler(WechatAppletHandler):
    """
    更新用户信息
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.get_i_argument('open_id', None)
            user_info = self.get_i_argument('user_info', None)
            if open_id and user_info:
                member = await find_member_by_open_id(open_id)
                if not member:
                    r_dict['code'] = 1002
                else:
                    orig_member = copy.deepcopy(member)
                    wechat_info = await parse_wechat_info(user_info)
                    if user_info.get('address'):
                        member.province_code = wechat_info.get('province_code')
                        member.city_code = wechat_info.get('city_code')
                        member.district_code = wechat_info.get('district_code')

                        member.sex = int(user_info.get('gender')) if user_info.get('gender') else member.sex
                        member.education = int(user_info.get('education')) if user_info.get(
                            'education') else member.education
                        member.age_group = int(user_info.get('age_group')) if user_info.get(
                            'age_group') else member.age_group
                        member.category = int(user_info.get('category')) if user_info.get(
                            'category') else member.category

                        member.needless['province'] = wechat_info.get('province_name')
                        member.needless['city'] = wechat_info.get('city_name')
                        member.needless['district'] = wechat_info.get('district_name')
                        member.wechat_info = user_info
                    else:
                        member.nick_name = user_info.get('nickName') if user_info.get('nickName') else '游客'
                        member.avatar = user_info.get('avatarUrl') if user_info.get('avatarUrl') else '%s://%s%s' % (
                            SERVER_PROTOCOL, SERVER_HOST, self.static_url('images/default/visitor.png'))
                        member.sex = int(user_info.get('gender')) if not member.sex else member.sex
                        member.province_code = wechat_info.get(
                            'province_code') if not member.province_code else member.province_code
                        member.city_code = wechat_info.get('city_code') if not member.city_code else member.city_code
                        member.district_code = wechat_info.get(
                            'district_code') if not member.district_code else member.district_code
                        member.needless['province'] = wechat_info.get('province_name') if not member.needless.get(
                            'province') else member.needless.get('province')
                        member.needless['city'] = wechat_info.get('city_name') if not member.needless.get(
                            'city') else member.needless.get('city')
                        member.needless['district'] = wechat_info.get('district_name') if not member.needless.get(
                            'district') else member.needless.get('district')
                        member.wechat_info = user_info if not member.wechat_info else member.wechat_info

                    member.updated_dt = datetime.datetime.now()
                    await member.save()

                    # 查询是否有分享行为，如有则更新其中的个人信息
                    update_memberinfo_in_other_collections.delay(member)

                    # 会员属性统计
                    new_member = await Member.get_by_id(member.oid)
                    await start_task_member_property_statistics(new_member, orig_member)
                    r_dict['code'] = 1000
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletMemberGetViewHandler(WechatAppletHandler):
    """获取用户信息详情"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.get_i_argument('open_id', None)
            if open_id:
                member = await find_member_by_open_id(open_id)
                if not member:
                    r_dict['code'] = 1002
                else:
                    r_dict.update({
                        'open_id': open_id,
                        'nick_name': member.nick_name,
                        'avatar_url': member.avatar,
                        'gender': member.sex,
                        'category': member.category,
                        'age_group': member.age_group,
                        'education': member.education,
                        'address': [
                            member.needless.get('province'),
                            member.needless.get('city'),
                            member.needless.get('district')
                        ]
                    })
                    r_dict['code'] = 1000
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletMemberGameDetailHandler(WechatAppletHandler):
    """获取用户游戏信息"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        """

        :return:
        """

        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        if not open_id:
            r_dict['code'] = 1007
            return r_dict
        try:
            member = await find_member_by_open_id(open_id)
            if not member:
                r_dict['code'] = 1008
                return r_dict

            # member_statistics = await MemberAccuracyStatistics.find_one({'member_cid': member.cid})

            r_dict.update({
                'open_id': open_id,
                'nick_name': member.nick_name,
                'avatar_url': member.avatar,
                'category': member.category,
                'diamond': member.diamond,
                'dan_grade_index': member.dan_grade,
                'dan_grade_title': TYPE_DAN_GRADE_DICT.get(member.dan_grade),
                'stars': member.star_grade,
                'highest_win_times': member.highest_win_times,
                # 'win_amount': member_statistics.win_times,
                # 'fail_amount': member_statistics.lose_times,
                # 'draw_amount': member_statistics.tie_times,
                # 'escape_amount': member_statistics.escape_times
            })

            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletMemberChartsHandler(WechatAppletHandler):
    """获取个人中心图表信息"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        if not open_id:
            r_dict['code'] = 1001
            return r_dict

        try:
            member = await find_member_by_open_id(open_id)
            if not member:
                r_dict['code'] = 1002
                return r_dict

            member_statistics = await MemberAccuracyStatistics.find_one({'member_cid': member.cid})
            r_dict['result_data'] = {
                # 'total_times': member_statistics.total_times,
                'win_times': getattr(member_statistics, 'win_times', 0),
                'lose_times': getattr(member_statistics, 'lose_times', 0),
                'escape_times': getattr(member_statistics, 'escape_times', 0),
                'tie_times': getattr(member_statistics, 'tie_times', 0),
                'total_quantity': getattr(member_statistics, 'total_quantity', 0),
                'correct_quantity': getattr(member_statistics, 'correct_quantity', 0),
                'dimension': getattr(member_statistics, 'dimension', {})
            }

            subject_accuracy_statistics = await SubjectAccuracyStatistics.find_one()
            age_group = subject_accuracy_statistics.age_group.get(str(member.age_group))
            education = subject_accuracy_statistics.education.get(str(member.education))
            gender = subject_accuracy_statistics.gender.get(str(member.sex))
            r_dict['contrast_data'] = {
                'age_group': age_group,
                'education': education,
                'gender': gender
            }

            pc = await PersonalCenterViewedStatistics.find_one({'member_cid': member.cid})
            if not pc:
                pc = PersonalCenterViewedStatistics(member_cid=member.cid, count=0)

            pc.count += 1
            pc.age_group = member.age_group
            pc.sex = member.sex
            pc.education = member.education
            pc.province_code = member.province_code
            pc.city_code = member.city_code
            await pc.save()

            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletMemberQuantityOnlineViewHandler(WechatAppletHandler):
    """获取在线会员数"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
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


class AppletMemberNoticesViewHandler(WechatAppletHandler):
    """获取会员最新消息通知(最新5条)"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            open_id = self.get_i_argument('open_id', None)
            if open_id:
                member = await find_member_by_open_id(open_id)
                if member:
                    sys_notice = await MemberNotice.find(
                        dict(member_cid=member.cid, category=CATEGORY_NOTICE_SYSTEM,
                             status=STATUS_NOTICE_UNREAD)).to_list(5)
                    msg_list = [{'cid': n.cid, 'content': n.content, 'notice_datetime': n.notice_datetime,
                                 'read': False if n.status == STATUS_NOTICE_UNREAD else True} for n in sys_notice]

                    notice_cursor = MemberNotice.find(
                        dict(member_cid=member.cid, category=CATEGORY_NOTICE_FRIENDS_PLAY),
                        read_preference=ReadPreference.PRIMARY).sort(
                        [('status', ASC), ('notice_datetime', DESC)]).limit(5)
                    while await notice_cursor.fetch_next:
                        notice = notice_cursor.next_object()
                        if notice:
                            msg_list.append({
                                'cid': notice.cid,
                                'content': notice.content,
                                'notice_datetime': notice.notice_datetime,
                                'read': False if notice.status == STATUS_NOTICE_UNREAD else True
                            })
                    r_dict['code'] = 1000
                    r_dict['msg_list'] = msg_list

                    award_msgs = await MemberNotice.find(
                        dict(member_cid=member.cid, category=CATEGORY_NOTICE_AWARD, status=STATUS_NOTICE_UNREAD)).sort(
                        [('status', ASC), ('notice_datetime', DESC)]).to_list(None)

                    award_msg_list = [{
                        'cid': msg.cid,
                        'content': msg.content,
                        'notice_datetime': msg.notice_datetime,
                        'read': False if msg.status == STATUS_NOTICE_UNREAD else True,
                        'race_cid': msg.race_cid,
                        'checkpoint_cid': msg.checkpoint_cid,
                        'msg_type': msg.needless.get('msg_type')
                    } for msg in award_msgs]
                    r_dict['award_msg_list'] = award_msg_list
                else:
                    r_dict['code'] = 1002
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletMemberNoticeReadViewHandler(WechatAppletHandler):
    """ 会员读取消息"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            notice_cid_list = self.get_i_argument('notice_cid_list', None)
            if notice_cid_list:
                update_list = []
                for notice_cid in notice_cid_list:
                    update_list.append(UpdateOne({'cid': notice_cid},
                                                 {'$set': {'status': STATUS_NOTICE_READ}}))
                if update_list:
                    await MemberNotice.update_many(update_list)
                    r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletMemberCheckHandler(WechatAppletHandler):
    """会员信息检查"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0, 'basic_done': False, 'benchmark_done': False,
                  'graduate_done': False, 'address_done': False}
        open_id = self.get_i_argument('open_id')
        if not open_id:
            return r_dict

        member = await find_member_by_open_id(open_id)
        if not member:
            return r_dict

        try:
            if member.age_group and member.education and member.category and member.sex and member.province_code \
                    and member.city_code and member.district_code:
                r_dict['basic_done'] = True
            if await MemberExamHistory.count(
                    {'member_cid': member.cid, 'category': CATEGORY_SUBJECT_BENCHMARK}) > 0:
                r_dict['benchmark_done'] = True
            if await MemberExamHistory.count(
                    {'member_cid': member.cid, 'category': CATEGORY_SUBJECT_GRADUATION}) > 0:
                r_dict['graduate_done'] = True
            if member.auth_address:
                r_dict['address_done'] = True

            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletMemberShareHandler(WechatAppletHandler):
    """分享接口"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id')
        category = self.get_i_argument('category')
        if not open_id:
            r_dict['code'] = 1001
            return r_dict

        category = int(category)
        if category not in CATEGORY_MEMBER_SHARE_LIST:
            r_dict['code'] = 1003
            return r_dict

        member = await find_member_by_open_id(open_id)
        if not member:
            r_dict['code'] = 1002
            return r_dict

        try:
            share = MemberShareStatistics(member_cid=member.cid, share_dt=datetime.datetime.now())
            if category:
                share.category = category
            share.age_group = member.age_group
            share.sex = member.sex
            share.province_code = member.province_code
            share.city_code = member.city_code
            share.education = member.education
            await share.save()
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletMemberActivityCheckHandler(WechatAppletHandler):
    """
    检查会员有无可以参加的活动
    用于小程序引导展示
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id')
        if not open_id:
            r_dict['code'] = 1001
            return r_dict

        member = await find_member_by_open_id(open_id)
        if not member:
            r_dict['code'] = 1002
            return r_dict

        r_dict['certain_activity'] = False
        r_dict['possible_activity'] = False
        r_dict['redpacket_enable'] = False

        try:
            r_dict['code'] = 1000

            if member.auth_address:
                city_name = member.auth_address.get('city')
                key = 'certain_activity'
                city = await AdministrativeDivision.find_one({'title': city_name, 'parent_code': {'$ne': None}})
                city_code = city.code
                prov_code = city.parent_code

            else:
                if member.province_code and member.city_code:
                    key = 'possible_activity'
                    city = await AdministrativeDivision.find_one({'code': member.city_code})
                    city_name = city.title
                    city_code = member.city_code
                    prov_code = member.province_code
                else:
                    raise ValueError('member (%s) has not attr (province_code, city_code) ' % str(member.id))

            city_races = await Race.distinct('cid', {'city_code': city_code, 'status': STATUS_RACE_ACTIVE,
                                                     'end_datetime': {'$gt': datetime.datetime.now()},
                                                     'start_datetime': {'$lt': datetime.datetime.now()}})
            prov_races = await Race.distinct('cid',
                                             {'province_code': prov_code, 'city_code': {'$in': [None, '']},
                                              'status': STATUS_RACE_ACTIVE,
                                              'end_datetime': {'$gt': datetime.datetime.now()},
                                              'start_datetime': {'$lt': datetime.datetime.now()}})

            race_cids = list(set(prov_races + city_races))
            entered_races = await RaceMapping.distinct('race_cid',
                                                       {'member_cid': member.cid,
                                                        'race_cid': {'$in': race_cids}})

            if len(race_cids) > len(entered_races):
                r_dict[key] = True
                r_dict['city'] = city_name
                if await Race.count(
                        {'cid': {'$in': list(set(race_cids) - set(entered_races))},
                         'redpkt_start_dt': {'$ne': None, '$lte': datetime.datetime.now()},
                         'redpkt_end_dt': {'$ne': None, '$gte': datetime.datetime.now()}}) > 0:
                    r_dict['redpacket_enable'] = True

                return r_dict

        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


URL_MAPPING_LIST = [
    url(r'/wechat/applet/member/auth/', AppletMemberAuthViewHandler, name='wechat_applet_member_auth'),
    url(r'/wechat/applet/member/game/detail/', AppletMemberGameDetailHandler, name='wechat_applet_member_game_detail'),
    url(r'/wechat/applet/member/check/', AppletMemberCheckHandler, name='wechat_applet_member_check'),
    url(r'/wechat/applet/member/charts/', AppletMemberChartsHandler, name='wechat_applet_member_charts'),
    url(r'/wechat/applet/member/quantity/online/', AppletMemberQuantityOnlineViewHandler,
        name='wechat_applet_member_quantity_online'),
    url(r'/wechat/applet/member/notices/', AppletMemberNoticesViewHandler, name='wechat_applet_member_notices'),
    url(r'/wechat/applet/member/notice/read/', AppletMemberNoticeReadViewHandler,
        name='wechat_applet_member_notice_read'),
    url(r'/wechat/applet/member/update/', AppletMemberUpdateViewHandler, name='wechat_applet_member_update'),
    url(r'/wechat/applet/member/get/', AppletMemberGetViewHandler, name='wechat_applet_member_get'),
    url(r'/wechat/applet/member/share/', AppletMemberShareHandler, name='wechat_applet_member_share'),
    url(r'/wechat/applet/member/activity/check/', AppletMemberActivityCheckHandler,
        name='wechat_applet_member_activity_check')
]
