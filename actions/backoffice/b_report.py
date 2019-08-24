# !/usr/bin/python

import copy
import json
from json import JSONDecodeError

import msgpack
from caches.redis_utils import RedisCache
from commons.common_utils import md5
from db.models import UserSearchCondition, SubjectDimension
from enums import REVIEW_REPORT_PERMS_LIST, CHART_COLOR_LIST, KEY_CACHE_REPORT_DOING_NOW
from logger import log_utils
from pymongo import ReadPreference
from pymongo import UpdateOne
from tornado.web import url
from web import BaseHandler, decorators

logger = log_utils.get_logging()


class ReportSearchConditionSetupViewHandler(BaseHandler):
    """
    保存报表检索条件
    """

    @decorators.render_json
    @decorators.permission_required(REVIEW_REPORT_PERMS_LIST)
    async def get(self):
        result = {'code': 0}

        user_cid = self.current_user.cid
        module = int(self.get_argument('module'))
        if user_cid and module:
            usc = await UserSearchCondition.find_one(dict(user_cid=user_cid, module=module),
                                                     read_preference=ReadPreference.PRIMARY)
            if usc:
                invalid_keys = []
                conditions = usc.conditions
                if conditions:
                    for key, value in conditions.items():
                        if not value.get('name'):
                            invalid_keys.append(key)
                    for key in invalid_keys:
                        del conditions[key]
                result['code'] = 1
                result['conditions'] = conditions
        else:
            result['code'] = -1  # 缺少参数

        return result

    @decorators.render_json
    @decorators.permission_required(REVIEW_REPORT_PERMS_LIST)
    async def post(self):
        result = {'code': 0}

        user_cid = self.current_user.cid
        conditions = self.get_argument('conditions')
        module = int(self.get_argument('module'))
        if user_cid and module and conditions is not None:
            try:
                conditions = json.loads(conditions)
                if conditions:
                    conditions, all_next_condition = await self.assign_color(conditions, module)
                    all_conditions = [conditions]
                    if all_next_condition:
                        all_conditions.extend(all_next_condition)
                    for condition in all_conditions:
                        usc = await UserSearchCondition.find_one(dict(user_cid=user_cid, module=module))
                        if not usc:
                            usc = UserSearchCondition(user_cid=user_cid, module=module)
                        usc.conditions = condition
                        await usc.save()
                        module += 1
                    result['code'] = 1
                else:
                    update_request = [UpdateOne(dict(user_cid=user_cid, module=module), {'$set': {'conditions': {}}})]
                    if module == 803:
                        while True:
                            module += 1
                            if module > 811:
                                break
                            update_request.append(
                                UpdateOne(dict(user_cid=user_cid, module=module), {'$set': {'conditions': {}}}))
                    await UserSearchCondition.update_many(update_request)
                    result['code'] = 1

            except JSONDecodeError:
                result['code'] = -2  # 格式错误
        else:
            result['code'] = -1  # 缺少参数

        return result

    @staticmethod
    async def assign_color(conditions: dict, module):
        subject_category_cid = '18114DC7C31B17AE35841CAE833161A2'
        all_next_condition = []
        if conditions:
            used_color = {}
            for index, item in enumerate(conditions.values()):
                if item is not None:
                    name = item['name']
                    if name and index < len(CHART_COLOR_LIST):
                        item['color'] = CHART_COLOR_LIST[index]
                        used_color[md5(name)] = CHART_COLOR_LIST[index]
            if module == 803:
                for i in range(8):
                    next_condition = copy.deepcopy(conditions)
                    for key, val in next_condition.items():
                        if 'condition' in val.keys() and 'dimension' in val['condition']:
                            dimension_str = val['condition']['dimension']
                            dimension = json.loads(dimension_str)
                            if dimension and subject_category_cid in dimension.keys():
                                dimension_cursor = SubjectDimension.find(
                                    dict(parent_cid=subject_category_cid))
                                while await dimension_cursor.fetch_next:
                                    dimension_o = dimension_cursor.next_object()
                                    if dimension_o:
                                        c_name: str = val['name']
                                        c_name = c_name.replace('%s,' % dimension_o.title, '').replace(
                                            dimension_o.title, '')
                                        val['name'] = c_name
                                del dimension[subject_category_cid]
                                val['condition']['dimension'] = json.dumps(dimension, ensure_ascii=False)
                    all_next_condition.append(next_condition)
        return conditions, all_next_condition


class ReportCacheKeyDataGetHandler(BaseHandler):
    """
    获取缓存数据
    """

    @decorators.render_json
    @decorators.permission_required(REVIEW_REPORT_PERMS_LIST)
    async def post(self):
        res_code = {'code': 0}
        cache_key = self.get_argument('cache_key')
        if not cache_key:
            res_code['code'] = -1
            return res_code

        data = RedisCache.get(cache_key)
        if data:
            if data == KEY_CACHE_REPORT_DOING_NOW:
                res_code['code'] = 2
                res_code['cache_key'] = cache_key
                return res_code
            else:
                res_code['data'] = msgpack.unpackb(data, raw=False)
                res_code['code'] = 1
                return res_code
        else:
            res_code['code'] = 2
            logger.warning('The tasks(cache_key: %s) has not been started.' % cache_key)

        return res_code


URL_MAPPING_LIST = [
    url(r'/backoffice/reports/search/condition/setup/', ReportSearchConditionSetupViewHandler,
        name='backoffice_reports_search_condition_setup'),
    url(r'/backoffice/reports/cache_key/get/', ReportCacheKeyDataGetHandler, name='backoffice_reports_cache_key_get')
]
