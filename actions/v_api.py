# !/usr/bin/python
# -*- coding:utf-8 -*-
import json
import traceback
from tornado.web import url
from caches.redis_utils import RedisCache
from commons.common_utils import get_random_str, md5
from db import STATUS_USER_ACTIVE
from db.models import User, AppMember, Tvs, Films
from logger import log_utils
from web import decorators, NonXsrfBaseHandler, WechatAppletHandler
from bson import ObjectId
from commons.common_utils import get_increase_code
from enums import KEY_INCREASE_MEMBER_CODE
from actions.applet import find_app_member_by_cid
from motorengine import ASC, DESC
from motorengine.stages import MatchStage, LookupStage, SortStage, SkipStage
from motorengine.stages.limit_stage import LimitStage
import datetime, random
from commons import msg_utils
import re

logger = log_utils.get_logging()


class AccessTokenGetViewHandler(NonXsrfBaseHandler):
    """
    获取Access Token
    """

    @decorators.render_json
    async def post(self):
        r_dict = {'code': 0}
        try:
            args = json.loads(self.request.body.decode('utf-8'))
            access_id = self.get_argument('access_key_id')
            if not access_id:
                access_id = args.get('access_key_id')
            access_secret = self.get_argument('access_key_secret')
            if not access_secret:
                access_secret = args.get('access_key_secret')
            if access_id and access_secret:
                token = await self.generate_new_token(access_id, access_secret)
                if token:
                    r_dict['code'] = 1000
                    r_dict['token'] = token
                else:
                    r_dict['code'] = 1001  # access_key_id、access_key_secret 无效
            else:
                r_dict['code'] = 1002  # access_key_id、access_key_secret 为空
        except RuntimeError:
            logger.error(traceback.format_exc())

        return r_dict

    async def generate_new_token(self, access_id, access_secret):
        """
        生成新的TOKEN
        :param access_id: ACCESS KEY ID
        :param access_secret: ACCESS KEY SECRET
        :return:
        """
        if access_id and access_secret:
            count = await User.count(dict(access_secret_id=access_id, access_secret_key=access_secret,
                                          status=STATUS_USER_ACTIVE))
            if count > 0:
                token = get_random_str(32)
                key = md5(token)
                RedisCache.set(key, token, 60 * 60 * 2)
                return token
        return None


class MemberAuthViewHandler(WechatAppletHandler):
    """app用户首次使用--创建虚拟用户"""

    @decorators.render_json
    async def post(self):
        r_dict = {'code': 0}
        try:
            args_dict = json.loads(self.request.body)
            uuid = args_dict.get('uuid', None)
            # device_id = args_dict.get('device_id', None)
            device_info = args_dict.get('device_info', {})
            member_cid = args_dict.get('member_cid', None)
            if member_cid:

                member = await find_app_member_by_cid(member_cid)
                if not member:
                    r_dict['code'] = 1001  # app传递用户cid不对
                else:
                    r_dict['member_cid'] = member_cid
                    if member.is_register and member.is_login:
                        r_dict['is_login'] = 1
                    else:
                        r_dict['is_login'] = 0
                    r_dict['code'] = 1000
            else:
                # app端没有登陆信息
                if uuid:
                    count = await AppMember.count(dict(uuid=uuid))
                    if count > 0:
                        member = await AppMember.find_one(dict(uuid=uuid, is_register=0))
                        if member:
                            r_dict['member_cid'] = member.cid
                            r_dict['is_login'] = 0
                            r_dict['code'] = 1000
                        else:
                            r_dict['code'] = 1003  # 有注册用户，但是没有虚拟用户
                    else:
                        member = AppMember(id=ObjectId(),
                                           code=get_increase_code(KEY_INCREASE_MEMBER_CODE), uuid=uuid,
                                           )
                        member.device_info = device_info
                        await member.save()
                        r_dict['member_cid'] = member.cid
                        r_dict['is_login'] = 0
                        r_dict['code'] = 1000

                else:
                    r_dict['code'] = 1002  # uuid或者device_id为空

        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MemberInfoViewHandler(WechatAppletHandler):
    """获取用户信息"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            member_cid = self.get_i_argument('member_cid', None)
            if member_cid:
                member = await find_app_member_by_cid(member_cid)
                if not member:
                    r_dict['code'] = 1002  # 没有匹配到用户
                else:
                    r_dict.update({
                        'member_cid': member_cid,
                        'nick_name': member.nick_name,
                        'head_picture': member.head_picture,
                        'code': member.code

                    })
                    r_dict['code'] = 1000
            else:
                r_dict['code'] = 1001  # member_cid为空
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class TvsLatestGetViewHandler(WechatAppletHandler):
    """获取最新的电视剧列表"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            member_cid = self.get_i_argument('member_cid', None)
            if member_cid:
                member = await find_app_member_by_cid(member_cid)
                if not member:
                    r_dict['code'] = 1002  # 没有匹配到用户
                else:
                    tvs = await Tvs.find(dict(year='2019')).to_list(None)
                    r_dict['tvs'] = tvs
                    r_dict['code'] = 1000
            else:
                r_dict['code'] = 1001  # member_cid为空
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class FilmsLatestGetViewHandler(WechatAppletHandler):
    """获取最新的电影列表"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            pageNum = int(self.get_i_argument('pageNum', 1))
            size = int(self.get_i_argument('size', 10))
            skip = (pageNum - 1) * size if (pageNum - 1) * size > 0 else 0
            filter_dict = {
                'db_mark': {'$ne': ''},
                'release_time': {'$ne': ''}
            }

            match = MatchStage(filter_dict)
            skip = SkipStage(skip)
            sort = SortStage([('release_time', DESC)])
            limit = LimitStage(int(size))
            count = await Films.count({'db_mark': {'$ne': ''},
                                       'release_time': {'$ne': ''}})
            films = await Films.aggregate([match, sort, skip, limit]).to_list(None)
            new_films = []
            for film in films:
                new_films.append({
                    'id': str(film.id),
                    'name': film.name,
                    'pic_url': film.pic_url,
                    'db_mark': film.db_mark,
                    'actor': film.actor,
                    'source_nums': len(film.download),
                    'release_time': film.release_time.strftime('%Y/%m/%d')
                })
            r_dict['films'] = new_films
            r_dict['count'] = count
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        print(r_dict)
        return r_dict


class FilmsScoreGetViewHandler(WechatAppletHandler):
    """获取评价最高的电影列表"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:

            pageNum = int(self.get_i_argument('pageNum', 1))
            size = int(self.get_i_argument('size', 10))
            search_type = self.get_i_argument('search_type', 'all')
            skip = (pageNum - 1) * size if (pageNum - 1) * size > 0 else 0
            filter_dict = {
                'db_mark': {'$ne': ''},
                'release_time': {'$ne': ''}
            }
            dif_time = 0
            if search_type == 'week':
                dif_time = 7
            elif search_type == 'month':
                dif_time = 30
            elif search_type == 'year':
                dif_time = 365
            if dif_time:
                show_time = datetime.datetime.now().replace(hour=0, minute=0, second=0,
                                                            microsecond=0) - datetime.timedelta(days=dif_time)
                filter_dict = {
                    'db_mark': {'$ne': ''},
                    'release_time': {'$ne': '', '$gte': show_time}
                }

            match = MatchStage(filter_dict)
            skip = SkipStage(skip)
            sort = SortStage([('db_mark', DESC)])
            limit = LimitStage(int(size))
            count = await Films.count({'db_mark': {'$ne': ''},
                                       'release_time': {'$ne': ''}})
            films = await Films.aggregate([match, sort, skip, limit]).to_list(None)
            new_films = []
            for film in films:
                new_films.append({
                    'id': str(film.id),
                    'name': film.name,
                    'pic_url': film.pic_url,
                    'db_mark': film.db_mark,
                    'actor': film.actor,
                    'source_nums': len(film.download),
                    'release_time': film.release_time.strftime('%Y/%m/%d')
                })
            r_dict['films'] = new_films
            r_dict['count'] = count
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class FilmsDetailGetViewHandler(WechatAppletHandler):
    """获取电影详情页面"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            film_id = self.get_i_argument('film_id', None)
            if film_id:
                film = await Films.get_by_id(oid=film_id)
                if film:
                    r_dict['film'] = film
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1002
            else:
                r_dict['code'] = 1001
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class SourceSearchGetViewHandler(WechatAppletHandler):
    """app-电影，电视等搜索"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            search_name = self.get_i_argument('search_name', None)

            if search_name:
                r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class BannersGetViewHandler(WechatAppletHandler):
    """首页banner图获取"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            search_name = self.get_i_argument('search_name', None)

            if search_name:
                r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class FilmsPersonalRecommendGetViewHandler(WechatAppletHandler):
    """电影个性推荐"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:

            pageNum = int(self.get_i_argument('pageNum', 1))
            member_cid = self.get_i_argument('member_cid', None)
            if not member_cid:
                r_dict['code'] = 1001
                return r_dict
            if pageNum == 1:
                exclude_list = []
                RedisCache.delete('%s_film_recommend' % member_cid)
            else:
                exclude_list = RedisCache.smembers('film_recommend')
                if isinstance(exclude_list, (list, set)):
                    exclude_list = list(exclude_list)

            # print(pageNum,exclude_list)
            # print(type(exclude_list))
            size = int(self.get_i_argument('size', 10))
            filter_dict = {
                'db_mark': {'$ne': ''},
                'release_time': {'$ne': ''},
                'oid': {'$nin': exclude_list}
            }
            match = MatchStage(filter_dict)
            films = await Films.aggregate([match]).to_list(None)
            if films:
                films = random.sample(films, size)
            new_films = []
            id_list = []
            for film in films:
                id_list.append(str(film.id))

                if len(film.label) > 0:
                    label = film.label[0:3]
                else:
                    label = []
                articulation = ''
                if len(film.download) > 0:
                    d_name = film.download[0].get('downloadname', '')
                    if d_name:
                        d_name = d_name.upper()
                        if '720' in d_name:
                            articulation = '720P'
                        elif '1080' in d_name:
                            articulation = '1080P'
                        elif '2K' in d_name:
                            articulation = '2K'
                        elif '4K' in d_name:
                            articulation = '4K'
                        elif 'BD' in d_name:
                            articulation = 'BD'
                        elif 'HD' in d_name:
                            articulation = 'HD'
                        elif 'TS' in d_name:
                            articulation = 'TS'
                new_films.append({
                    'id': str(film.id),
                    'name': film.name,
                    'pic_url': film.pic_url,
                    'db_mark': film.db_mark,
                    'actor': film.actor,
                    'label': label,
                    'source_nums': len(film.download),
                    'release_time': film.release_time.strftime('%Y/%m/%d'),
                    'articulation': articulation,
                    'recommend_info': '123456789'
                })
            r_dict['films'] = new_films
            if id_list:
                # print(id_list)
                RedisCache.sadd('%s_film_recommend' % member_cid, id_list)
                # print(RedisCache.smembers('film_recommend'))
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MobileValidateViewHandler(WechatAppletHandler):
    """
    发送验证码
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            mobile = self.get_i_argument('mobile', '')
            ret = re.match(r"^1\d{10}$", mobile)
            if mobile:
                has_send_count = RedisCache.get(mobile + '_count')
                # 同一手机号码每天限制发送验证码10次（成功）
                if has_send_count and int(has_send_count) >= 10:
                    r_dict['code'] = 1004
                    return r_dict
                _, verify_code = msg_utils.send_digit_verify_code_new(mobile, valid_sec=600)
                if verify_code:
                    if has_send_count:
                        has_send_count = int(has_send_count) + 1
                    else:
                        has_send_count = 1
                    today = datetime.datetime.strptime(str(datetime.date.today()), "%Y-%m-%d")
                    tomorrow = today + datetime.timedelta(days=1)
                    now = datetime.datetime.now()
                    RedisCache.set(mobile + '_count', has_send_count, (tomorrow - now).seconds)

                    r_dict['code'] = 1000
                    logger.info('mobile:%s,verify_code:%s' % (mobile, verify_code))
                else:
                    r_dict['code'] = 1003  # 验证码发送失败
                if not ret:
                    r_dict['code'] = 1002  # 手机号码格式不对
            else:
                r_dict['code'] = 1001  # 手机号为空
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class SubmitMobileValidateViewHandler(WechatAppletHandler):
    """
    提交手机号码，提交验证码注册用户或者登陆
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        member_cid = self.get_i_argument('member_cid', None)
        mobile = self.get_i_argument('mobile', None)
        v_code = self.get_i_argument('v_code', '')
        if not member_cid:
            r_dict['code'] = 1001
            return r_dict

        member = await find_app_member_by_cid(member_cid)
        if not member:
            r_dict['code'] = 1002
        if not mobile:
            r_dict['code'] = 1003
            return r_dict
        try:
            if msg_utils.check_digit_verify_code(mobile, v_code):
                r_dict['code'] = 1000
            else:
                r_dict['code'] = 1004
                return r_dict
            count = await AppMember.count({'mobile': mobile})
            if count == 0:
                new_member = AppMember(id=ObjectId(),
                                       code=get_increase_code(KEY_INCREASE_MEMBER_CODE), uuid=member.uuid,
                                       mobile=mobile,
                                       )
                new_member.is_register = 1
                new_member.is_login = 1
                await new_member.save()

                r_dict['member_cid'] = new_member.cid
            else:
                r_dict['member_cid'] = member.cid

            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/api/get/token/', AccessTokenGetViewHandler, name='api_get_token'),
    url(r'/api/member/auth/', MemberAuthViewHandler, name='api_member_auth'),
    url(r'/api/member/info/', MemberInfoViewHandler, name='api_member_info'),
    url(r'/api/tvs/latest/', TvsLatestGetViewHandler, name='api_tvs_latest'),
    url(r'/api/films/latest/', FilmsLatestGetViewHandler, name='api_films_latest'),
    url(r'/api/films/score/', FilmsScoreGetViewHandler, name='api_films_score'),
    url(r'/api/films/detail/', FilmsDetailGetViewHandler, name='api_films_detail'),
    url(r'/api/source/search/', SourceSearchGetViewHandler, name='api_source_search'),
    url(r'/api/banners/get/', BannersGetViewHandler, name='api_banner_get'),
    url(r'/api/films/personal_recommend/', FilmsPersonalRecommendGetViewHandler, name='api_films_personal_recommend'),
    url(r'/api/send/msg/mobile/validate/', MobileValidateViewHandler, name='api_send_msg_mobile_validate'),
    url(r'/api/submit/mobile/validate/', SubmitMobileValidateViewHandler, name='api_submit_mobile_validate'),
]
