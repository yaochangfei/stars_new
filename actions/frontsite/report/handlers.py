import traceback
from datetime import datetime, timedelta

import msgpack
from tornado.web import url

from actions.frontsite.report.utils import do_stat_member_times, do_stat_member_count, do_stat_member_accuracy, \
    get_drill_district_data, get_cache_key, get_special_cache_key
from db import CITY_RACE_CID
from db.models import AdministrativeDivision, \
    RaceMemberEnterInfoStatistic
from enums import PERMISSION_TYPE_MINIAPP_RACE_REPORT_SITUATION, KEY_CACHE_RACE_REPORT_DOWNLOAD
from logger import log_utils
from motorengine import DESC, RedisCache
from motorengine.stages import MatchStage, GroupStage, SortStage
from tasks.instances.task_race_export_data import start_get_export_data
from web import decorators, BaseHandler, datetime2str

logger = log_utils.get_logging()

logger_cache = log_utils.get_logging('race_cache', 'race_cache.log')


class RaceReportMapHandler(BaseHandler):
    """
    地方科协地图模块
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_REPORT_SITUATION)
    async def post(self):
        res_dict = {'code': 0}
        race_cid = self.get_argument('race_cid')
        # 0代表人数，1代表人次
        stat_type = int(self.get_argument('stat_type', 0))
        # race = Race.sync_get_by_cid(race_cid)

        try:
            cache_key = get_cache_key(race_cid, stat_type)
            data = RedisCache.get(cache_key)
            if not data:
                match = {'race_cid': race_cid}
                # 安徽特殊处理，需整合六安数据
                # 弃用，不整合数据
                # if race.province_code == '340000':
                #     match = {'race_cid': {'$in': [race_cid, CITY_RACE_CID]}}
                match_stage = MatchStage(match)
                # 活动分组,具体到市,increase_enter_count人数,enter_times_sum次数
                if stat_type == 0:
                    # 人数
                    group_stage = GroupStage({'province': '$province', 'city': '$city'},
                                             sum={'$sum': '$increase_enter_count'})
                else:
                    group_stage = GroupStage({'province': '$province', 'city': '$city'},
                                             sum={'$sum': '$enter_times'})
                cursor = RaceMemberEnterInfoStatistic.aggregate([
                    match_stage, group_stage, SortStage([('sum', DESC)])
                ])
                res_dict['code'] = 1
                res_dict['data'] = await do_init_map_data(cursor)
                logger_cache.info('cache_key: %s' % cache_key)
                RedisCache.set(cache_key, msgpack.packb(res_dict['data']), 23 * 60 * 60)
            else:
                res_dict['data'] = msgpack.unpackb(data, raw=False)
                res_dict['code'] = 1
            return res_dict
        except Exception:
            logger.error(traceback.format_exc())
            res_dict['code'] = -1
        return res_dict


async def do_init_map_data(cursor):
    """

    :param cursor:
    :return:
    """

    data_map = {}
    while await cursor.fetch_next:
        try:
            data = cursor.next_object()
            prov_name = data.id.get('province').replace('省', '').replace('市', '')
            city_list = data_map.get(prov_name, [])
            city_list.append({'title': data.id.get('city'), 'data': data.sum})
            data_map[prov_name] = city_list

        except StopIteration:
            break

    ret_data = []
    for k, v in data_map.items():
        _v_sum = [_t.get('data') for _t in v]
        _d = {'title': k, 'data': sum(_v_sum), 'city_list': v}
        ret_data.append(_d)
    ret_data.sort(key=lambda x: x.get('data'))
    return ret_data


class RaceReportRankingHandler(BaseHandler):
    """
    地方科协报表排行榜
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_REPORT_SITUATION)
    async def post(self):
        res_dict = {'code': 0}
        choice_time = int(self.get_argument("choice_time", 0))
        group_id = self.get_argument("category", "city")
        race_cid = self.get_argument("race_cid")

        early_monring = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_daily_code = format(early_monring, '%Y%m%d')

        time_match = MatchStage({'daily_code': {'$lt': end_daily_code}})
        if choice_time:
            old_time = early_monring - timedelta(choice_time)
            start_daily_code = format(old_time, '%Y%m%d')
            time_match = MatchStage(
                {'daily_code': {'$gt': start_daily_code, '$lt': end_daily_code}})

        data = []
        try:
            member_times = await do_stat_member_times(race_cid, time_match, group_id, time_num=choice_time)
            member_count = await do_stat_member_count(race_cid, time_match, group_id, time_num=choice_time)
            member_accuracy = await do_stat_member_accuracy(race_cid, time_match, group_id, time_num=choice_time)
            for k in member_times:
                data.append({
                    'name': k,
                    'times': member_times.get(k, 0),
                    'count': member_count.get(k, 0),
                    'accuracy': "%.2f%%" % (member_accuracy.get(k, 0.0) * 100)
                })
        except Exception:
            res_dict['code'] = -1
            logger.error(traceback.format_exc())
            return res_dict

        html = self.render_string('frontsite/report/rank_table.html', data=data)
        if html:
            html = html.decode('utf-8')

        return {'code': 1, 'html': html}


class RaceReportDrillDownHandler(BaseHandler):
    """
    科协报表地图下钻到区
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_REPORT_SITUATION)
    async def post(self):
        res = {'code': 0, 'data_dict': ""}
        try:
            name = self.get_argument("name", "")
            race_cid = self.get_argument("race_cid", "")
            category = self.get_argument('category', '人数')
            area_category = self.get_argument('area_category', '')
            early_morning = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_daily_code = format(early_morning, '%Y%m%d')
            if name and race_cid:
                if category == "人数":
                    city = await AdministrativeDivision.find_one({"title": name})
                    district_title_list = await AdministrativeDivision.distinct('title',
                                                                                {'parent_code': city.code})
                    district_match = MatchStage({"district": {'$in': district_title_list}})
                    data_dict = await do_stat_member_count(race_cid, time_match=MatchStage(
                        {'daily_code': {'$lt': end_daily_code}}), group_id="district",
                                                           name_match=MatchStage({'city': name}),
                                                           district_match=district_match, name=name,
                                                           is_integrate=area_category)

                    #  获取到下钻到区的数据
                    data_list, total = await get_drill_district_data(data_dict, name)
                    res['data_dict'] = {'title': name, "data": total, "city_list": data_list}
                    res['code'] = 1
                else:
                    data_dict = await do_stat_member_times(race_cid, time_match=MatchStage(
                        {'daily_code': {'$lt': end_daily_code}}), group_id="district",
                                                           name_match=MatchStage({'city': name}), name=name,
                                                           is_integrate=area_category)
                    data_list, total = await get_drill_district_data(data_dict, name)
                    res['data_dict'] = {'title': name, "data": total, "city_list": data_list}
                    res['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return res


class RaceReportExportHandler(BaseHandler):
    """
    科协报表导出数据
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_REPORT_SITUATION)
    async def post(self):
        res = {'code': 0, 'complete_situation': False, 'export_title': ''}
        try:
            now = datetime.now()
            export_time = datetime2str(now)
            race_cid = self.get_argument('race_cid', '')
            title = self.get_argument('title', '')
            title = title.strip() if title else ''
            export_title = '{title}科协数据{time}'.format(title=title, time=export_time)
            start_get_export_data.delay(race_cid, title, export_title)
            res['code'] = 1
            res['export_title'] = export_title
        except Exception:
            logger.error(traceback.format_exc())
        return res


class RaceReportSeeResult(BaseHandler):
    """
    查询下载数据是否完成
    """

    @decorators.render_json
    async def post(self):
        res = {'code': 0, 'download_path': ''}
        try:
            export_title = self.get_argument('export_title', '')
            status = RedisCache.hget(KEY_CACHE_RACE_REPORT_DOWNLOAD, export_title)
            download_path = 'static/export/%s.xlsx' % export_title
            if status == b'1':
                res['download_path'] = '/' + download_path
                res['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return res


class RaceTownRankingHandler(BaseHandler):
    """
    乡镇排行榜
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_REPORT_SITUATION)
    async def post(self):
        res_dict = {'code': 0}
        #  六安市的cid，安徽六安和六安市整合
        choice_time = int(self.get_argument("choice_time", 0))
        group_id = self.get_argument("category", "town")
        district_title = self.get_argument('district_title', '')
        midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_daily_code = format(midnight, '%Y%m%d')

        time_match = MatchStage({'daily_code': {'$lt': end_daily_code}})
        if choice_time:
            old_time = midnight - timedelta(choice_time)
            start_daily_code = format(old_time, '%Y%m%d')
            time_match = MatchStage(
                {'daily_code': {'$gt': start_daily_code, '$lt': end_daily_code}})

        data = []
        try:
            if district_title:
                member_times = await do_stat_member_times(CITY_RACE_CID, time_match, group_id,
                                                          district_title=district_title)
                member_count = await do_stat_member_count(CITY_RACE_CID, time_match, group_id,
                                                          district_title=district_title)
                member_accuracy = await do_stat_member_accuracy(CITY_RACE_CID, time_match, group_id,
                                                                district_title=district_title)
                for k in member_times:
                    data.append({
                        'name': k,
                        'times': member_times.get(k, 0),
                        'count': member_count.get(k, 0),
                        'accuracy': "%.2f%%" % (member_accuracy.get(k, 0.0) * 100)
                    })
        except Exception:
            res_dict['code'] = -1
            logger.error(traceback.format_exc())
            return res_dict

        html = self.render_string('frontsite/report/rank_table.html', data=data)
        if html:
            html = html.decode('utf-8')

        return {'code': 1, 'html': html}


class RaceSpecialReportMapHandler(BaseHandler):
    """
    安徽省地方科协
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_REPORT_SITUATION)
    async def post(self):
        res_dict = {'code': 0}
        race_cid = '3040737C97F7C7669B04BC39A660065D'
        # 0代表人数，1代表人次
        stat_type = int(self.get_argument('stat_type', 0))
        user = self.get_current_user()
        region = RedisCache.get(user.login_name)
        #  region  'province' 报表展示市得数据, 'city': 报表展示得是区得数据
        if not region:
            region_code_list = user.manage_region_code_list
            for region_code in region_code_list:
                city_list = await AdministrativeDivision.find({'parent_code': '340000'}).to_list(None)
                total_code_list = [city.code for city in city_list]
                total_code_list.append("340000")
                if region_code in total_code_list:
                    region_code = region_code
                    RedisCache.set(user.login_name, region_code, timeout=24 * 60 * 60)
                    region = region_code
                    break

        try:
            early_morning = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_daily_code = format(early_morning, '%Y%m%d')
            cache_key = get_special_cache_key(race_cid, stat_type)
            data = RedisCache.get(cache_key)
            if region == "340000":
                if not data:
                    match = {'race_cid': race_cid}
                    match_stage = MatchStage(match)
                    # 活动分组,具体到市,increase_enter_count人数,enter_times_sum次数
                    name = "六安市"
                    city = await AdministrativeDivision.find_one({"title": name})
                    district_title_list = await AdministrativeDivision.distinct('title',
                                                                                {'parent_code': city.code})
                    district_match = MatchStage({"district": {'$in': district_title_list}})
                    if stat_type == 0:
                        # 人数
                        group_stage = GroupStage({'province': '$province', 'city': '$city'},
                                                 sum={'$sum': '$increase_enter_count'})
                        city_data_dict = await do_stat_member_count(CITY_RACE_CID, time_match=MatchStage(
                            {'daily_code': {'$lt': end_daily_code}}), group_id="district",
                                                                    name_match=MatchStage({'city': name}),
                                                                    district_match=district_match, name=name)
                    else:
                        group_stage = GroupStage({'province': '$province', 'city': '$city'},
                                                 sum={'$sum': '$enter_times'})
                        city_data_dict = await do_stat_member_times(CITY_RACE_CID, time_match=MatchStage(
                            {'daily_code': {'$lt': end_daily_code}}), group_id="district",
                                                                          name_match=MatchStage({'city': name}),
                                                                          name=name)
                    cursor = RaceMemberEnterInfoStatistic.aggregate([
                        match_stage, group_stage, SortStage([('sum', DESC)])
                    ])
                    city_total_num = sum(list(city_data_dict.values()))
                    res_dict['code'] = 1
                    res_dict['area'] = 'province'
                    prov_data_dict = await do_init_map_data(cursor)
                    city_list = prov_data_dict[0].get('city_list')
                    for index, city_dict in enumerate(city_list):
                        if '六安市' == city_dict.get('title'):
                            data = city_dict['data']
                            data += city_total_num
                            temp = {'title': '六安市', 'data': data}
                            city_list.remove(city_dict)
                            city_list.insert(index, temp)
                            break
                    prov_data_dict[0]['city_list'] = city_list
                    res_dict['data'] = prov_data_dict
                    logger_cache.info('cache_key: %s' % cache_key)
                    RedisCache.set(cache_key, msgpack.packb(res_dict['data']), 23 * 60 * 60)
                else:
                    res_dict['data'] = msgpack.unpackb(data, raw=False)
                    res_dict['area'] = 'province'
                    res_dict['code'] = 1
                return res_dict
            else:
                _city = await AdministrativeDivision.find_one({'code': region})
                if stat_type == 1:
                    name = _city.title
                    data_dict = await do_stat_member_times(race_cid, time_match=MatchStage(
                        {'daily_code': {'$lt': end_daily_code}}), group_id="district",
                                                           name_match=MatchStage({'city': name}), name=name)
                    if name == "六安市":
                        city_count_data_dict = await do_stat_member_times(CITY_RACE_CID, time_match=MatchStage(
                            {'daily_code': {'$lt': end_daily_code}}), group_id="district",
                                                               name_match=MatchStage({'city': name}), name=name)
                        total_times_dict = {}
                        for key, value in data_dict.items():
                            if key not in total_times_dict:
                                total_times_dict[key] = value
                            else:
                                total_times_dict[key] += value
                        for key, value in city_count_data_dict.items():
                            if key not in total_times_dict:
                                total_times_dict[key] = value
                            else:
                                total_times_dict[key] += value
                        data_dict = total_times_dict
                    data_list, total = await get_drill_district_data(data_dict, name)
                    res_dict['data'] = [{'title': name, "data": total, "city_list": data_list}]
                    res_dict['code'] = 1
                    res_dict['area'] = 'city'
                else:
                    name = _city.title
                    city = await AdministrativeDivision.find_one({"title": name})
                    district_title_list = await AdministrativeDivision.distinct('title',
                                                                                {'parent_code': city.code})
                    district_match = MatchStage({"district": {'$in': district_title_list}})
                    data_dict = await do_stat_member_count(race_cid, time_match=MatchStage(
                        {'daily_code': {'$lt': end_daily_code}}), group_id="district",
                                                           name_match=MatchStage({'city': name}),
                                                           district_match=district_match, name=name)
                    if name == "六安市":
                        city_data_dict = await do_stat_member_count(CITY_RACE_CID, time_match=MatchStage(
                            {'daily_code': {'$lt': end_daily_code}}), group_id="district",
                                                                    name_match=MatchStage({'city': name}),
                                                                    district_match=district_match, name=name)
                        total_dict = {}
                        for key, value in data_dict.items():
                            if key not in total_dict:
                                total_dict[key] = value
                            else:
                                total_dict[key] += value
                        for key, value in city_data_dict.items():
                            if key not in total_dict:
                                total_dict[key] = value
                            else:
                                total_dict[key] += value
                        data_dict = total_dict
                    data_list, total = await get_drill_district_data(data_dict, name)
                    res_dict['data'] = [{'title': name, "data": total, "city_list": data_list}]
                    res_dict['code'] = 1
                    res_dict['area'] = 'city'
                return res_dict
        except Exception:
            logger.error(traceback.format_exc())
            res_dict['code'] = -1
        return res_dict


URL_MAPPING_LIST = [
    url(r'/frontsite/report/map/', RaceReportMapHandler, name="frontsite_race_map"),
    url(r'/frontsite/report/rank/', RaceReportRankingHandler, name="frontsite_race_rank"),
    url(r'/frontsite/report/town/rank/', RaceTownRankingHandler, name="frontsite_race_town_rank"),
    url(r'/frontsite/report/drill/down/district/', RaceReportDrillDownHandler,
        name="frontsite_report_drill_down_district"),
    url("/frontsite/report/export/", RaceReportExportHandler, name="frontsite_report_export"),
    url("/frontsite/report/download/see/result/", RaceReportSeeResult, name="frontsite_report_download_see_result"),
    url(r'/frontsite/special/report/map/', RaceSpecialReportMapHandler, name="frontsite_special_race_map")
]
