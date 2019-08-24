import traceback
from datetime import datetime

from actions.applet import find_member_by_open_id
from tornado.web import url

from db import STATUS_USER_ACTIVE, STATUS_RACE_ACTIVE
from db.models import Member, Race, UploadFiles, RaceMapping, AdministrativeDivision, Company, \
    ReportRacePeopleStatistics, RaceMemberEnterInfoStatistic
from logger import log_utils
from motorengine import DESC, ASC
from motorengine.stages import MatchStage, LookupStage, SortStage, GroupStage
from settings import SERVER_PROTOCOL, SERVER_HOST
from settings import STATIC_URL_PREFIX
from web import WechatAppletHandler, decorators
from caches.redis_utils import RedisCache

logger = log_utils.get_logging('race', 'race.log')


class AppletActivityListViewHandler(WechatAppletHandler):
    """
    获取活动列表
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0, 'race_list': []}
        open_id = self.get_i_argument('open_id', None)
        auth_address = self.get_i_argument('address_dict')
        try:
            member = await find_member_by_open_id(open_id)
            if not member:
                r_dict['code'] = 1001
                return r_dict

            if auth_address:
                member.auth_address = auth_address
                await member.save()

            auth_address = member.auth_address
            if not auth_address:
                logger.error('member has no auth_address. member_dict: %s' % str(member.__dict__))
                r_dict['code'] = 1002
                return r_dict

            # sort_rule: 1) local, 2)time
            race_list = await Race.aggregate(stage_list=[
                MatchStage({'record_flag': 1, 'status': STATUS_RACE_ACTIVE}),
                LookupStage(AdministrativeDivision, 'province_code', 'code', 'province_list'),
                LookupStage(AdministrativeDivision, 'city_code', 'code', 'city_list'),
                LookupStage(UploadFiles, 'image_cid', 'cid', 'image_list'),
                SortStage([('start_datetime', ASC), ('end_datetime', DESC)])
            ]).to_list(None)

            prov = await AdministrativeDivision.find_one({'title': auth_address.get('province'), 'parent_code': None})
            city = await AdministrativeDivision.find_one(
                {'title': auth_address.get('city'), 'parent_code': {'$ne': None}})
            r_dict['code'] = 1000

            # 本地，活动进行中
            race_local_ing = list()
            race_others = list()
            for race in race_list:
                if race.start_datetime <= datetime.now() <= race.end_datetime and race.province_code == prov.code:
                    if not race.city_code or race.city_code == city.code:
                        race = await self.deal_race(race, prov, city)
                        race_local_ing.append(race)
                    else:
                        race = await self.deal_race(race, prov, city)
                        race_others.append(race)
                else:
                    race = await self.deal_race(race, prov, city)
                    race_others.append(race)

            r_dict['race_list'] = race_local_ing + race_others
        except Exception:
            logger.error(traceback.format_exc())
            logger.error('-- member_dict : %s' % str(member.__dict__))

        r_dict['race_list'].sort(key=lambda x: x.get('status'))
        r_dict['origin_address'] = auth_address.get('city') if auth_address else None
        return r_dict

    @staticmethod
    async def deal_race(race, province, city):
        """

        :param race:
        :param province:
        :param city
        :return:
        """

        race_dict = {'race_cid': race.cid, 'status': 1, 'title_img_url': '', 'area': '', 'is_local': True}
        if race.start_datetime > datetime.now():
            # 未开始
            race_dict['status'] = 0

        if race.end_datetime < datetime.now():
            # 已结束
            race_dict['status'] = 2

        if (race.city_code and race.city_code != city.code) or (race.province_code != province.code):
            race_dict['is_local'] = False

        if race.image_list:
            upload_file = race.image_list[0]
            title_img_url = '%s://%s%s%s%s' % (
                SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/', upload_file.title)
            race_dict['title_img_url'] = title_img_url

        if race.province_list:
            race_dict['area'] = race.province_list[0].title
        if race.city_list:
            race_dict['area'] += '-' + race.city_list[0].title
        #  去除脏数据
        if not race.city_code:
            #  省级活动
            prov = AdministrativeDivision.sync_find_one({'code': race.province_code})
            city_list = AdministrativeDivision.sync_find({'parent_code': prov.code}).to_list(None)
            city_title_list = [city.title for city in city_list]
            city_code_list = [city.code for city in city_list]
            district_title_list = AdministrativeDivision.sync_distinct("title",
                                                                       {'parent_code': {'$in': city_code_list}})
        else:
            city = AdministrativeDivision.sync_find_one({'code': race.city_code})
            city_title_list = [city.title]
            district_title_list = AdministrativeDivision.sync_distinct("title", {'parent_code': city.code})
        start_daily_code = format(race.start_datetime, '%Y%m%d')
        if race.cid != "DF1EDC30F120AEE93351A005DC97B5C1":
            cache_key = '{race_cid}-PEOPLE_COUNT'.format(race_cid=race.cid)
            data = RedisCache.get(cache_key)
            if data:
                race_dict['people_count'] = int(data)
            else:
                cursor = RaceMemberEnterInfoStatistic.aggregate([
                    MatchStage(
                        {'race_cid': race.cid, 'daily_code': {'$gte': start_daily_code},
                         'city': {'$in': city_title_list},
                         'district': {'$in': district_title_list}}),
                    GroupStage('race_cid', sum={'$sum': '$increase_enter_count'})
                ])
                count = 0
                while await cursor.fetch_next:
                    try:
                        info = cursor.next_object()
                        count = info.sum
                    except StopIteration:
                        break
                race_dict['people_count'] = count
                RedisCache.set(cache_key, count, 60 * 60)
        else:
            # 扬州显示次数
            cache_key = '{race_cid}-PEOPLE_COUNT'.format(race_cid=race.cid)
            data = RedisCache.get(cache_key)
            if data:
                race_dict['people_count'] = int(data)
            else:
                cursor = RaceMemberEnterInfoStatistic.aggregate([
                    MatchStage(
                        {'race_cid': race.cid, 'daily_code': {'$gte': start_daily_code},
                         'city': {'$in': city_title_list},
                         'district': {'$in': district_title_list}}),
                    GroupStage('race_cid', sum={'$sum': '$enter_times'})
                ])
                count = 0
                while await cursor.fetch_next:
                    try:
                        info = cursor.next_object()
                        count = info.sum
                    except StopIteration:
                        break
                race_dict['people_count'] = count
                RedisCache.set(cache_key, count, 60 * 60)

        race_dict['show_play_quantity'] = race.play_quantity_enabled
        race_dict['title'] = race.title
        return race_dict


class AppletRaceCompanyHandler(WechatAppletHandler):
    """
    判断是否要弹窗单位信息
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        race_cid = self.get_i_argument('race_cid', None)
        r_dict['company_enabled'] = False
        r_dict['must_choice'] = False
        if not race_cid:
            r_dict['code'] = 1001
            return r_dict
        member = await find_member_by_open_id(open_id)
        if not member:
            r_dict['code'] = 1002
            return r_dict
        try:
            race = await Race.find_one({'cid': race_cid, 'record_flag': 1})
            race_map = await RaceMapping.find_one({'member_cid': member.cid, 'race_cid': race_cid, 'record_flag': 1})
            if race.company_enabled:
                company_list = await Company.find({'race_cid': race_cid, 'record_flag': 1}).to_list(None)
                if company_list:
                    r_dict['company_enabled'] = True
                if race.Mandatory_enabled:
                    r_dict['must_choice'] = True
            #  如果已经选择过公司了则不弹窗提示
            if race_map and race_map.company_cid:
                r_dict['company_enabled'] = False
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletRaceGuidePageHandler(WechatAppletHandler):
    """
    活动规则页面
    """

    @decorators.render_template('backoffice/race/wechat_race_guide.html')
    async def get(self):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid')
        if not race_cid:
            r_dict['code'] = 1001
            return r_dict

        race = await Race.find_one({'cid': race_cid, 'record_flag': 1})
        return locals()


URL_MAPPING_LIST = [
    url(r'/wechat/applet/mainpage/race/list/', AppletActivityListViewHandler,
        name='wechat_applet_main_page_race_list'),
    url(r'/wechat/applet/mainpage/race/guide/', AppletRaceGuidePageHandler, name='wechat_applet_mainpage_race_guide'),
    url(r'/wechat/applet/mainpage/race/company/', AppletRaceCompanyHandler, name='wechat_applet_mainpage_race_company')
]
