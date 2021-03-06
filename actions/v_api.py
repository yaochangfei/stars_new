# !/usr/bin/python
# -*- coding:utf-8 -*-
import json
import traceback
from tornado.web import url
from caches.redis_utils import RedisCache
from commons.common_utils import get_random_str, md5
from db import STATUS_USER_ACTIVE, LIKE_STATUS_ACTIVE, LIKE_STATUS_INACTIVE, COLLECTION_STATUS_ACTIVE, \
    COLLECTION_STATUS_INACTIVE
from db.models import User, AppMember, Tvs, Films, MyCollection, MyLike, HotSearch
from logger import log_utils
from web import decorators, NonXsrfBaseHandler, WechatAppletHandler
from bson import ObjectId
from commons.common_utils import get_increase_code
from enums import KEY_INCREASE_MEMBER_CODE
from actions.applet import find_app_member_by_cid
from motorengine import ASC, DESC
from motorengine.stages import MatchStage, LookupStage, SortStage, SkipStage, SampleStage
from motorengine.stages.limit_stage import LimitStage
import datetime, random
from commons import msg_utils, api_utils
import re
from pymongo import UpdateOne
import time

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
                    r_dict['m_type'] = member.m_type if member.m_type else ''
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
                        'mobile': member.mobile if member.mobile else '',
                        'm_type': member.m_type if member.m_type else ''
                    })
                    r_dict['code'] = 1000
            else:
                r_dict['code'] = 1001  # member_cid为空
        except Exception:
            logger.error(traceback.format_exc())
        print(r_dict)
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
                # if len(film.label) > 0:
                #     label = film.label[0:3]
                # else:
                #     label = []
                new_films.append({
                    'id': str(film.id),
                    'name': film.name,
                    'pic_url': film.pic_url,
                    'db_mark': film.db_mark,
                    'actor': film.actor,
                    'source_nums': len(film.download),
                    'release_time': film.release_time.strftime('%Y-%m-%d'),
                    # 'recommend_info': '这部神片值得一看。',
                    'recommend_info': film.recommend_info if film.recommend_info else '这部神片值得一看。',
                    # 'label': label
                    'label': api_utils.get_show_source_label(film),
                    's_type': 'film'

                })
            r_dict['films'] = new_films
            r_dict['count'] = count
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        print('latest')
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
                # if len(film.label) > 0:
                #     label = film.label[0:3]
                # else:
                #     label = []
                new_films.append({
                    'id': str(film.id),
                    'name': film.name,
                    'pic_url': film.pic_url,
                    'db_mark': film.db_mark,
                    'actor': film.actor,
                    'source_nums': len(film.download),
                    'release_time': film.release_time.strftime('%Y-%m-%d'),
                    # 'recommend_info': '这部神片值得一看。',
                    'recommend_info': film.recommend_info if film.recommend_info else '这部神片值得一看。',
                    # 'label': label
                    'label': api_utils.get_show_source_label(film),
                    's_type': 'film'
                })
            r_dict['films'] = new_films
            r_dict['count'] = count
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        print('score')
        print(r_dict)
        return r_dict


class FilmsDetailGetViewHandler(WechatAppletHandler):
    """获取电影详情页面"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            film_id = self.get_i_argument('film_id', None)
            member_cid = self.get_i_argument('member_cid', None)
            if not member_cid:
                r_dict['code'] = 1001  # member_cid为空
                return r_dict
            if film_id:
                film = await Films.get_by_id(oid=film_id)
                if film:
                    my_collect = await MyCollection.find_one(
                        {'status': COLLECTION_STATUS_ACTIVE, 'member_cid': member_cid, 'source_id': film_id})
                    my_like = await MyLike.find_one(
                        {'status': LIKE_STATUS_ACTIVE, 'member_cid': member_cid, 'source_id': film_id})
                    if my_like:
                        r_dict['my_like'] = 1
                    else:
                        r_dict['my_like'] = 0
                    if my_collect:
                        r_dict['my_collect'] = 1
                    else:
                        r_dict['my_collect'] = 0
                    film.stage_photo = [k['img_url'] for k in film.stage_photo] if film.stage_photo else []
                    r_dict['film'] = film
                    r_dict['s_type'] = 'film'
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1003
            else:
                r_dict['code'] = 1002
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
            member_cid = self.get_i_argument('member_cid', None)
            if not member_cid:
                r_dict['code'] = 1001  # member_cid为空
                return r_dict
            if not search_name:
                r_dict['code'] = 1002  # 检索名称为空
                return r_dict
            pageNum = int(self.get_i_argument('pageNum', 1))
            size = int(self.get_i_argument('size', 10))
            skip = (pageNum - 1) * size if (pageNum - 1) * size > 0 else 0
            filter_dict = {
                'db_mark': {'$ne': ''},
                'release_time': {'$ne': ''},
                'status': 1,
                '$or': [{'name': {'$regex': search_name}},
                        {'actor': {'$regex': search_name}},
                        {'director': {'$regex': search_name}},
                        {'label': {'$regex': search_name}},
                        ]
            }
            match = MatchStage(filter_dict)
            skip = SkipStage(skip)
            sort = SortStage([('db_mark', DESC)])
            limit = LimitStage(int(size))
            films_count = await Films.count(filter_dict)
            films = await Films.aggregate([match, sort, skip, limit]).to_list(None)
            new_films = []
            for film in films:
                new_films.append({
                    'id': str(film.id),
                    'name': film.name,
                    'pic_url': film.pic_url,
                    's_type': 'film',
                    'stage_photo': [k['img_url'] for k in film.stage_photo][0:4] if film.stage_photo else []
                })
            r_dict['films'] = new_films
            r_dict['films_count'] = films_count
            tvs_count = await Tvs.count(filter_dict)
            tvs = await Tvs.aggregate([match, sort, skip, limit]).to_list(None)
            new_tvs = []
            for tv in tvs:
                new_tvs.append({
                    'id': str(tv.id),
                    'name': tv.name,
                    'pic_url': tv.pic_url,
                    's_type': 'tv',
                    'stage_photo': [k['img_url'] for k in tv.stage_photo][0:4] if tv.stage_photo else []
                })
            r_dict['tvs'] = new_tvs
            r_dict['tvs_count'] = tvs_count
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
            banners = []
            films = await Films.find(dict(status=1, banner_status=1)).to_list(None)
            for film in films:
                banners.append({
                    'id': str(film.oid),
                    'banner_pic': film.banner_pic,
                    's_type': 'film'
                })
            tvs = await Tvs.find(dict(status=1, banner_status=1)).to_list(None)
            for tv in tvs:
                banners.append({
                    'id': str(tv.oid),
                    'banner_pic': tv.banner_pic,
                    's_type': 'tv'
                })
            r_dict['banners'] = banners[:5]
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
                exclude_list = RedisCache.smembers('%s_film_recommend' % member_cid)
                if isinstance(exclude_list, (list, set)):
                    exclude_list = list(exclude_list)
            size = int(self.get_i_argument('size', 10))
            filter_dict = {
                'db_mark': {'$ne': ''},
                'release_time': {'$ne': ''},
                'oid': {'$nin': exclude_list}
            }
            match = MatchStage(filter_dict)
            sample = SampleStage(size)
            films = await Films.aggregate([match, sample]).to_list(None)
            new_films = []
            id_list = []
            for film in films:
                id_list.append(str(film.id))
                new_films.append({
                    'id': str(film.id),
                    'name': film.name,
                    'pic_url': film.pic_url,
                    'db_mark': film.db_mark,
                    'actor': film.actor,
                    'label': api_utils.get_show_source_label(film),
                    'source_nums': len(film.download),
                    'release_time': film.release_time.strftime('%Y-%m-%d'),
                    'articulation': api_utils.get_show_source_articulation(film),
                    'recommend_info': film.recommend_info if film.recommend_info else '这部神片值得一看。',
                    's_type': 'film',
                    'stage_photo': [k['img_url'] for k in film.stage_photo][0:4] if film.stage_photo else []
                })
            r_dict['films'] = new_films
            if id_list:
                RedisCache.sadd('%s_film_recommend' % member_cid, id_list)
            r_dict['code'] = 1000
            print('recommend')
            print(r_dict)
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
            if not msg_utils.check_digit_verify_code(mobile, v_code):
                r_dict['code'] = 1004
                return r_dict
            phone_member = await AppMember.find_one({'mobile': mobile})
            if not phone_member:
                new_member = AppMember(id=ObjectId(),
                                       code=get_increase_code(KEY_INCREASE_MEMBER_CODE), uuid=member.uuid,
                                       mobile=mobile,
                                       )
                new_member.is_register = 1
                new_member.is_login = 1
                await new_member.save()
                r_dict['m_type'] = new_member.m_type if new_member.m_type else ''
                r_dict['member_cid'] = new_member.cid
            else:
                r_dict['member_cid'] = phone_member.cid
                r_dict['m_type'] = phone_member.m_type if phone_member.m_type else ''

            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MemberInfoUpdateViewHandler(WechatAppletHandler):
    """更新用户头像昵称信息"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            member_cid = self.get_i_argument('member_cid', None)
            m_type = self.get_i_argument('m_type', None)

            if member_cid and m_type:
                member = await find_app_member_by_cid(member_cid)
                if not member:
                    r_dict['code'] = 1002  # 没有匹配到用户
                else:
                    member.m_type = m_type
                    await member.save()
                    RedisCache.delete(member_cid)  # 头像信息更新清除redis缓存
                    r_dict['code'] = 1000
            else:
                r_dict['code'] = 1001  # member_cid 或者 m_type为空
        except Exception:
            logger.error(traceback.format_exc())
        print(r_dict)
        return r_dict


class HotSearchListViewHandler(WechatAppletHandler):
    """热门搜索信息列表"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            hot_search_list = await HotSearch.find(dict(status=1)).to_list(None)
            r_dict['hot_search_list'] = hot_search_list
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        print(r_dict)
        return r_dict


class SourceCollectViewHandler(WechatAppletHandler):
    """
    收藏资源(包括电影，电视等)
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            member_cid = self.get_i_argument('member_cid', None)
            source_id = self.get_i_argument('source_id', None)
            s_type = self.get_i_argument('s_type', None)
            if member_cid and source_id and s_type:
                member = await find_app_member_by_cid(member_cid)
                if not member:
                    r_dict['code'] = 1002  # 没有匹配到用户
                else:
                    if not member.is_register:
                        r_dict['code'] = 1003  # 用户未登陆不能收藏资源
                        return r_dict
                    my_collection = await MyCollection.find_one(dict(member_cid=member_cid, source_id=source_id))
                    if my_collection:
                        if my_collection.status == COLLECTION_STATUS_ACTIVE:
                            my_collection.status = COLLECTION_STATUS_INACTIVE
                        else:
                            my_collection.status = COLLECTION_STATUS_ACTIVE
                    else:
                        my_collection = MyCollection(member_cid=member_cid, source_id=source_id,
                                                     status=COLLECTION_STATUS_ACTIVE)
                        my_collection.s_type = s_type
                    await my_collection.save()
                    r_dict['status'] = my_collection.status  # 1代表收藏 0代表取消收藏
                    r_dict['code'] = 1000
            else:
                r_dict['code'] = 1001  # member_cid为空，或者资源id为空，或者资源类型为空
        except Exception:
            logger.error(traceback.format_exc())
        print(r_dict)
        return r_dict


class SourceLikeViewHandler(WechatAppletHandler):
    """
    点赞资源(包括电影，电视等)
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            member_cid = self.get_i_argument('member_cid', None)
            source_id = self.get_i_argument('source_id', None)
            s_type = self.get_i_argument('s_type', None)
            if member_cid and source_id and s_type:
                member = await find_app_member_by_cid(member_cid)
                if not member:
                    r_dict['code'] = 1002  # 没有匹配到用户
                else:
                    if not member.is_register:
                        r_dict['code'] = 1003  # 用户未登陆不能点赞
                        return r_dict
                    my_like = await MyLike.find_one(dict(member_cid=member_cid, source_id=source_id))
                    if my_like:
                        if my_like.status == LIKE_STATUS_ACTIVE:
                            my_like.status = LIKE_STATUS_INACTIVE
                        else:
                            my_like.status = LIKE_STATUS_ACTIVE
                    else:
                        my_like = MyLike(member_cid=member_cid, source_id=source_id,
                                         status=LIKE_STATUS_ACTIVE)
                        my_like.s_type = s_type
                    await my_like.save()
                    r_dict['status'] = my_like.status  # 1代表 点赞 0代表取消点赞
                    r_dict['code'] = 1000
            else:
                r_dict['code'] = 1001  # member_cid为空，或者资源id为空，或者资源类型为空
        except Exception:
            logger.error(traceback.format_exc())
        print(r_dict)
        return r_dict


class MyCollectListViewHandler(WechatAppletHandler):
    """
    我的收藏列表(包括电影，电视等)
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            member_cid = self.get_i_argument('member_cid', None)
            pageNum = int(self.get_i_argument('pageNum', 1))
            size = int(self.get_i_argument('size', 10))
            skip = (pageNum - 1) * size if (pageNum - 1) * size > 0 else 0
            if member_cid:
                member = await find_app_member_by_cid(member_cid)
                if not member:
                    r_dict['code'] = 1002  # 没有匹配到用户
                else:
                    if not member.is_register:
                        r_dict['code'] = 1003  # 用户未登陆不展示收藏列表
                        return r_dict
                    filter_dict = {
                        'member_cid': member_cid,
                        'status': COLLECTION_STATUS_ACTIVE
                    }
                    match = MatchStage(filter_dict)
                    skip = SkipStage(skip)
                    sort = SortStage([('updated_dt', DESC)])
                    limit = LimitStage(int(size))
                    my_collect_list = await MyCollection.aggregate([match, sort, skip, limit]).to_list(None)
                    show_my_list = []
                    for my_collect in my_collect_list:
                        if my_collect.s_type == 'film':
                            film = await Films.find_one({'_id': ObjectId(my_collect.source_id)})
                            show_my_list.append(
                                {'id': str(film.id), 'name': film.name,
                                 'pic_url': film.pic_url, 's_type': 'film',
                                 'db_mark': film.db_mark,
                                 'actor': film.actor,
                                 'source_nums': len(film.download),
                                 'release_time': film.release_time.strftime('%Y-%m-%d'),
                                 'recommend_info': film.recommend_info if film.recommend_info else '这部神片值得一看。',
                                 'label': api_utils.get_show_source_label(film)
                                 })
                        elif my_collect.s_type == 'tv':
                            tv = await Tvs.find_one({'_id': ObjectId(my_collect.source_id)})
                            show_my_list.append(
                                {'id': str(tv.id), 'name': tv.name,
                                 'pic_url': tv.pic_url, 's_type': 'tv',
                                 'db_mark': tv.db_mark,
                                 'actor': tv.actor,
                                 'source_nums': len(tv.download),
                                 'release_time': tv.release_time.strftime('%Y-%m-%d'),
                                 'recommend_info': tv.recommend_info if tv.recommend_info else '这部神剧值得一看。',
                                 'label': api_utils.get_show_source_label(tv),
                                 'set_num': tv.set_num if tv.set_num else ''
                                 })
                    r_dict['my_collect_list'] = show_my_list
                    r_dict['code'] = 1000
            else:
                r_dict['code'] = 1001  # member_cid为空
        except Exception:
            logger.error(traceback.format_exc())
        print(r_dict)
        return r_dict


class SourceMoreSearchGetViewHandler(WechatAppletHandler):
    """app-电影，电视等搜索 更多"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            search_name = self.get_i_argument('search_name', None)
            member_cid = self.get_i_argument('member_cid', None)
            s_type = self.get_i_argument('s_type', None)
            if not member_cid:
                r_dict['code'] = 1001  # member_cid为空
                return r_dict
            if not search_name:
                r_dict['code'] = 1002  # 检索名称为空
                return r_dict
            if not s_type:
                r_dict['code'] = 1003  # 资源类型为空
                return r_dict
            pageNum = int(self.get_i_argument('pageNum', 1))
            size = int(self.get_i_argument('size', 10))
            skip = (pageNum - 1) * size if (pageNum - 1) * size > 0 else 0
            filter_dict = {
                'db_mark': {'$ne': ''},
                'release_time': {'$ne': ''},
                'status': 1,
                '$or': [{'name': {'$regex': search_name}},
                        {'actor': {'$regex': search_name}},
                        {'director': {'$regex': search_name}},
                        {'label': {'$regex': search_name}},
                        ]
            }
            match = MatchStage(filter_dict)
            skip = SkipStage(skip)
            sort = SortStage([('db_mark', DESC)])
            limit = LimitStage(int(size))
            if s_type == 'film':
                films = await Films.aggregate([match, sort, skip, limit]).to_list(None)
                new_films = []
                for film in films:
                    new_films.append({
                        'id': str(film.id),
                        'name': film.name,
                        'pic_url': film.pic_url,
                        'stage_photo': [k['img_url'] for k in film.stage_photo][0:4] if film.stage_photo else [],
                        's_type': 'film',
                        'label': api_utils.get_show_source_label(film),
                        'articulation': api_utils.get_show_source_articulation(film),
                        'db_mark': film.db_mark,
                        'actor': film.actor,
                        'source_nums': len(film.download),
                        'release_time': film.release_time.strftime('%Y-%m-%d'),
                        'recommend_info': film.recommend_info if film.recommend_info else '这部神片值得一看。'
                    })
                r_dict['sources'] = new_films
            elif s_type == 'tv':
                tvs = await Tvs.aggregate([match, sort, skip, limit]).to_list(None)
                new_tvs = []
                for tv in tvs:
                    new_tvs.append({
                        'id': str(tv.id),
                        'name': tv.name,
                        'pic_url': tv.pic_url,
                        'stage_photo': [k['img_url'] for k in tv.stage_photo][0:4] if tv.stage_photo else [],
                        's_type': 'tv',
                        'label': api_utils.get_show_source_label(tv),
                        'articulation': api_utils.get_show_source_articulation(tv),
                        'db_mark': tv.db_mark,
                        'actor': tv.actor,
                        'source_nums': len(tv.download),
                        'release_time': tv.release_time.strftime('%Y-%m-%d'),
                        'recommend_info': '这部神剧值得一看。'
                    })
                r_dict['sources'] = new_tvs

            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class SourceSearchRelatedGetViewHandler(WechatAppletHandler):
    """app-搜索关联词"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            search_name = self.get_i_argument('search_name', None)
            member_cid = self.get_i_argument('member_cid', None)
            if not member_cid:
                r_dict['code'] = 1001  # member_cid为空
                return r_dict
            if not search_name:
                r_dict['code'] = 1002  # 检索名称为空
                return r_dict
            pageNum = int(self.get_i_argument('pageNum', 1))
            size = int(self.get_i_argument('size', 20))
            skip = (pageNum - 1) * size if (pageNum - 1) * size > 0 else 0
            filter_dict = {
                'db_mark': {'$ne': ''},
                'release_time': {'$ne': ''},
                'status': 1,
                'name': {'$regex': '^%s' % search_name}

            }
            match = MatchStage(filter_dict)
            skip = SkipStage(skip)
            sort = SortStage([('db_mark', DESC)])
            limit = LimitStage(int(size))
            films = await Films.aggregate([match, sort, skip, limit]).to_list(None)
            sources = []
            for film in films:
                sources.append(film.name)
            tvs = await Tvs.aggregate([match, sort, skip, limit]).to_list(None)
            for tv in tvs:
                sources.append(tv.name)
            r_dict['names'] = sources[:20]
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class MyCollectDeleteViewHandler(WechatAppletHandler):
    """
    删除收藏（1个或多个）
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            member_cid = self.get_i_argument('member_cid', None)
            source_ids = self.get_i_argument('source_ids', None)
            if member_cid and source_ids:
                member = await find_app_member_by_cid(member_cid)
                if not member:
                    r_dict['code'] = 1002  # 没有匹配到用户
                else:
                    if not member.is_register:
                        r_dict['code'] = 1003  # 用户未登陆不展示收藏列表
                        return r_dict
                    source_ids = source_ids.split(',')
                    update_requests = []
                    for source_id in source_ids:
                        update_requests.append(UpdateOne({'member_cid': member_cid, 'source_id': source_id},
                                                         {'$set': {'status': COLLECTION_STATUS_INACTIVE,
                                                                   'updated_dt': datetime.datetime.now()}}))
                    if update_requests:
                        await MyCollection.update_many(update_requests)
                        r_dict['code'] = 1000
            else:
                if not member_cid:
                    r_dict['code'] = 1001  # member_cid为空
                if not source_ids:
                    r_dict['code'] = 1004  # source_ids为空
        except Exception:
            logger.error(traceback.format_exc())
        print(r_dict)
        return r_dict


URL_MAPPING_LIST = [
    url(r'/api/get/token/', AccessTokenGetViewHandler, name='api_get_token'),
    url(r'/api/member/auth/', MemberAuthViewHandler, name='api_member_auth'),
    url(r'/api/member/info/', MemberInfoViewHandler, name='api_member_info'),
    url(r'/api/films/latest/', FilmsLatestGetViewHandler, name='api_films_latest'),
    url(r'/api/films/score/', FilmsScoreGetViewHandler, name='api_films_score'),
    url(r'/api/films/detail/', FilmsDetailGetViewHandler, name='api_films_detail'),
    url(r'/api/source/search/', SourceSearchGetViewHandler, name='api_source_search'),
    url(r'/api/banners/get/', BannersGetViewHandler, name='api_banner_get'),
    url(r'/api/films/personal_recommend/', FilmsPersonalRecommendGetViewHandler, name='api_films_personal_recommend'),
    url(r'/api/send/msg/mobile/validate/', MobileValidateViewHandler, name='api_send_msg_mobile_validate'),
    url(r'/api/submit/mobile/validate/', SubmitMobileValidateViewHandler, name='api_submit_mobile_validate'),
    url(r'/api/member/info/update/', MemberInfoUpdateViewHandler, name='api_member_info_update'),
    url(r'/api/hot/search/list/', HotSearchListViewHandler, name='api_hot_search_list'),
    url(r'/api/source/collect/', SourceCollectViewHandler, name='api_source_collect'),
    url(r'/api/source/like/', SourceLikeViewHandler, name='api_source_like'),
    url(r'/api/my/collect/list/', MyCollectListViewHandler, name='api_my_collect_list'),
    url(r'/api/source/more_search/', SourceMoreSearchGetViewHandler, name='api_source_more_search'),
    url(r'/api/source/search_related/', SourceSearchRelatedGetViewHandler, name='api_source_search_related'),
    url(r'/api/my/collect/delete/', MyCollectDeleteViewHandler, name='api_my_collect_delete'),
]
