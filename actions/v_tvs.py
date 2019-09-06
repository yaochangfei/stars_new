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
from commons import api_utils
import re
import time

logger = log_utils.get_logging()


class TvsLatestGetViewHandler(WechatAppletHandler):
    """获取最新的电视剧列表"""

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
            count = await Tvs.count({'db_mark': {'$ne': ''},
                                     'release_time': {'$ne': ''}})
            tvs = await Tvs.aggregate([match, sort, skip, limit]).to_list(None)
            new_tvs = []
            for tv in tvs:
                new_tvs.append({
                    'id': str(tv.id),
                    'name': tv.name,
                    'pic_url': tv.pic_url,
                    'db_mark': tv.db_mark,
                    'actor': tv.actor,
                    'source_nums': len(tv.download),
                    'release_time': tv.release_time.strftime('%Y-%m-%d'),
                    'label': api_utils.get_show_source_label(tv),
                    'recommend_info': '这部神剧值得一看。',
                    'set_num': tv.set_num if tv.set_num else '',
                    's_type': 'tv'
                })
            r_dict['tvs'] = new_tvs
            r_dict['count'] = count
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        print('latest')
        print(r_dict)
        return r_dict


class TvsScoreGetViewHandler(WechatAppletHandler):
    """获取评价最高的电视剧列表"""

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
            count = await Tvs.count({'db_mark': {'$ne': ''},
                                     'release_time': {'$ne': ''}})
            tvs = await Tvs.aggregate([match, sort, skip, limit]).to_list(None)
            new_tvs = []
            for tv in tvs:
                new_tvs.append({
                    'id': str(tv.id),
                    'name': tv.name,
                    'pic_url': tv.pic_url,
                    'db_mark': tv.db_mark,
                    'actor': tv.actor,
                    'source_nums': len(tv.download),
                    'release_time': tv.release_time.strftime('%Y-%m-%d'),
                    'label': api_utils.get_show_source_label(tv),
                    'recommend_info': '这部神剧值得一看。',
                    'set_num': tv.set_num if tv.set_num else '',
                    's_type': 'tv'
                })
            r_dict['tvs'] = new_tvs
            r_dict['count'] = count
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        print('score')
        print(r_dict)
        return r_dict


class TvsDetailGetViewHandler(WechatAppletHandler):
    """获取电视剧详情页面"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            tv_id = self.get_i_argument('tv_id', None)
            member_cid = self.get_i_argument('member_cid', None)
            if not member_cid:
                r_dict['code'] = 1001  # member_cid为空
                return r_dict
            if tv_id:
                tv = await Tvs.get_by_id(oid=tv_id)
                if tv:
                    my_collect = await MyCollection.find_one(
                        {'status': COLLECTION_STATUS_ACTIVE, 'member_cid': member_cid, 'source_id': tv_id})
                    my_like = await MyLike.find_one(
                        {'status': LIKE_STATUS_ACTIVE, 'member_cid': member_cid, 'source_id': tv_id})
                    if my_like:
                        r_dict['my_like'] = 1
                    else:
                        r_dict['my_like'] = 0
                    if my_collect:
                        r_dict['my_collect'] = 1
                    else:
                        r_dict['my_collect'] = 0
                    r_dict['tv'] = tv
                    r_dict['s_type'] = 'tv'
                    r_dict['code'] = 1000
                else:
                    r_dict['code'] = 1003
            else:
                r_dict['code'] = 1002
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class TvsPersonalRecommendGetViewHandler(WechatAppletHandler):
    """电视剧个性推荐"""

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
                RedisCache.delete('%s_tv_recommend' % member_cid)
            else:
                exclude_list = RedisCache.smembers('%s_tv_recommend' % member_cid)
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
            tvs = await Tvs.aggregate([match, sample]).to_list(None)
            new_tvs = []
            id_list = []
            for tv in tvs:
                id_list.append(str(tv.id))

                # if len(tv.label) > 0:
                #     label = tv.label[0:3]
                # else:
                #     label = []
                # articulation = ''
                # if len(tv.download) > 0:
                #     d_name = tv.download[0].get('downloadname', '')
                #     if d_name:
                #         d_name = d_name.upper()
                #         if '720' in d_name:
                #             articulation = '720P'
                #         elif '1080' in d_name:
                #             articulation = '1080P'
                #         elif '2K' in d_name:
                #             articulation = '2K'
                #         elif '4K' in d_name:
                #             articulation = '4K'
                #         elif 'BD' in d_name:
                #             articulation = 'BD'
                #         elif 'HD' in d_name:
                #             articulation = 'HD'
                #         elif 'TS' in d_name:
                #             articulation = 'TS'
                new_tvs.append({
                    'id': str(tv.id),
                    'name': tv.name,
                    'pic_url': tv.pic_url,
                    'db_mark': tv.db_mark,
                    'actor': tv.actor,
                    # 'label': label,
                    'label': api_utils.get_show_source_label(tv),
                    'source_nums': len(tv.download),
                    'release_time': tv.release_time.strftime('%Y-%m-%d'),
                    # 'articulation': articulation,
                    'articulation': api_utils.get_show_source_articulation(tv),
                    'recommend_info': '这部神剧值得一看。',
                    'set_num': tv.set_num if tv.set_num else '',
                    's_type': 'tv'
                })
            r_dict['tvs'] = new_tvs
            if id_list:
                RedisCache.sadd('%s_tv_recommend' % member_cid, id_list)
            r_dict['code'] = 1000
            print('recommend')
            print(r_dict)
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/api/tvs/latest/', TvsLatestGetViewHandler, name='api_tvs_latest'),
    url(r'/api/tvs/score/', TvsScoreGetViewHandler, name='api_tvs_score'),
    url(r'/api/tvs/detail/', TvsDetailGetViewHandler, name='api_tvs_detail'),
    url(r'/api/tvs/personal_recommend/', TvsPersonalRecommendGetViewHandler, name='api_tvs_personal_recommend'),

]
