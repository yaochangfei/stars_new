import traceback
from datetime import datetime

from tornado.web import url

from actions.applet import find_member_by_open_id
from db import STATUS_GAME_CHECK_POINT_ACTIVE, STATUS_USER_ACTIVE, TEMP_LIU_AN_COMPANY_LIST, \
    TEMP_LIU_AN_YU_AN_COMPANY_LIST, STATUS_RACE_INACTIVE
from db.models import RaceGameCheckPoint, Race, Member, RaceMapping, AdministrativeDivision
from enums import KEY_CACHE_WECHAT_TOWN
from logger import log_utils
from web import WechatAppletHandler, decorators, RedisCache, json

logger = log_utils.get_logging()


class AppletRaceMobileShowHandler(WechatAppletHandler):
    """
    检查是否需要展示填写个人手机号码信息弹框
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        res_dict = {'code': 0, 'show_mobile_pop': False}
        open_id = self.get_i_argument('open_id')
        checkpoint_cid = self.get_i_argument('checkpoint_cid')
        if not (open_id and checkpoint_cid):
            res_dict['code'] = 1001
            return res_dict

        try:
            res_dict['code'] = 1000
            checkpoint = await RaceGameCheckPoint.get_by_cid(checkpoint_cid)
            if not checkpoint:
                res_dict['code'] = 1002
                return res_dict

            race = await Race.get_by_cid(checkpoint.race_cid)
            if not race.mobile_enabled:
                return res_dict

            count = await RaceGameCheckPoint.count(
                {'race_cid': checkpoint.race_cid, 'status': STATUS_GAME_CHECK_POINT_ACTIVE,
                 'index': {'$gt': checkpoint.index}, 'record_flag': 1})

            if count > 0:
                return res_dict

            member = await find_member_by_open_id(open_id)
            race_mapping = await RaceMapping.find_one(
                {'race_cid': race.cid, 'member_cid': member.cid, 'record_flag': 1})
            if not race_mapping.mobile:
                res_dict['show_mobile_pop'] = True
                return res_dict
        except Exception:
            logger.error(traceback.format_exc())
        return res_dict


class AppletMobileBeforeRaceShowHandler(WechatAppletHandler):
    """
    检查进入活动之前是否需要展示填写个人手机号码信息弹框
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        res_dict = {'code': 0, 'show_mobile_before_race_pop': False}
        open_id = self.get_i_argument('open_id')
        race_cid = self.get_i_argument('race_cid')
        if not (open_id and race_cid):
            res_dict['code'] = 1001
            return res_dict
        try:
            member = await find_member_by_open_id(open_id)
            if not member:
                res_dict['code'] = 1002
                return res_dict
            race = await Race.find_one({'cid': race_cid, 'record_flag': 1})
            if not race:
                res_dict['code'] = 1003
                return res_dict
            race_mapping = await RaceMapping.find_one(
                {'member_cid': member.cid, 'race_cid': race_cid, 'record_flag': 1})
            if race.mobile_before_race:
                #  活动中有配置填写手机号码并且没有填写过手机号码的
                if not race_mapping:
                    if race.mobile_before_race:
                        res_dict["show_mobile_before_race_pop"] = True
                    res_dict['code'] = 1000
                else:
                    if not race_mapping.mobile:
                        res_dict["show_mobile_before_race_pop"] = True
                    res_dict['code'] = 1000
            else:
                res_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return res_dict


class AppletTwoDimensionalCodeCheckRace(WechatAppletHandler):
    """
    二维码判断是否可以进去活动
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        race_cid = self.get_i_argument("race_cid", '')
        open_id = self.get_i_argument("open_id", '')
        auth_address = self.get_i_argument("auth_address", '')
        res_dict = {'code': 0, 'can_enter_race': False, 'redirect_auth': False}
        try:
            if not (race_cid and open_id):
                res_dict['code'] = 1001
                return res_dict
            race = await Race.find_one({'cid': race_cid, 'record_flag': 1})
            if not race:
                res_dict['code'] = 1002
                return res_dict

            if race.status == STATUS_RACE_INACTIVE or race.end_datetime < datetime.now():
                res_dict['code'] = 1003
                return res_dict

            if race.start_datetime > datetime.now():
                res_dict['code'] = 1004
                return res_dict

            member = await find_member_by_open_id(open_id)
            if not auth_address:
                if member:
                    auth_address = member.auth_address
                    await member.save()
                else:
                    pass
            else:
                member.auth_address = auth_address
                await member.save()

            prov = await AdministrativeDivision.find_one({'title': auth_address.get('province'), 'parent_code': None})
            city = ""
            if auth_address.get('city'):
                city = await AdministrativeDivision.find_one(
                    {'title': auth_address.get('city'), 'parent_code': {'$ne': None}})
            #  省级活动
            if race.province_code and not race.city_code and prov:
                if prov.code == race.province_code:
                    res_dict['can_enter_race'] = True
            #  市级活动
            elif race.city_code and city:
                if city.code == race.city_code:
                    res_dict['can_enter_race'] = True
            res_dict['code'] = 1000
            if not res_dict['can_enter_race']:
                show_address = '{pro}{city}'.format(pro=auth_address.get('province', ''),
                                                    city=auth_address.get('city', ''))

                res_dict['address_show'] = show_address
        except Exception:
            logger.error(traceback.format_exc())
        return res_dict


class AppletRaceTownInfoCheckHandler(WechatAppletHandler):
    """
    是否弹出乡镇或单位弹框
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        res_dict = {'code': 0}
        try:
            open_id = self.get_i_argument("open_id")
            race_cid = self.get_i_argument("race_cid")
            if not (open_id and race_cid):
                res_dict['code'] = 1001
                return res_dict

            member = await find_member_by_open_id(open_id)
            if not member.auth_address:
                res_dict['code'] = 1002
                res_dict['msg'] = 'the member has no auth_address.'
                return res_dict

            race = await Race.get_by_cid(race_cid)
            if not race:
                res_dict['code'] = 1003
                res_dict['msg'] = 'no race.'
                return res_dict

            mapping = await RaceMapping.find_one({'race_cid': race_cid, 'member_cid': member.cid})

            show = False
            if race.town_enable:
                if not mapping:
                    show = True
                else:
                    if not mapping.company_cid and not mapping.auth_address.get('town'):
                        show = True

            res_dict = {
                'code': 1000,
                'show': show
            }
        except Exception:
            logger.error(traceback.format_exc())

        return res_dict


class AppletRaceTownInfoGetHandler(WechatAppletHandler):
    """
    获取下拉乡镇信息
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        res_dict = {'code': 0, 'data': {}}
        try:
            race_cid = self.get_i_argument('race_cid')
            race = await Race.find_one({'cid': race_cid})
            if not race:
                res_dict['code'] = 1001
                return res_dict

            data = RedisCache.hget(KEY_CACHE_WECHAT_TOWN, race_cid)
            if data:
                data = data.decode('utf-8')
                return json.loads(data)

            if race.city_code:
                dist_list = await AdministrativeDivision.find({'level': 'D', 'parent_code': race.city_code}).sort(
                    'created_dt').to_list(
                    None)
            elif race.province_code:
                city_list = await AdministrativeDivision.find(
                    {'level': 'C', 'parent_code': race.province_code}).to_list(None)
                dist_list = await AdministrativeDivision.find(
                    {'level': 'D', 'parent_code': {'$in': [c.code for c in city_list]}}).sort('created_dt').to_list(
                    None)
            else:
                res_dict['code'] = 1002
                return res_dict

            dist_code_map = {d.code: d.title for d in dist_list}
            res_dict['data']['dist_list'] = list(dist_code_map.values())
            res_dict['data']['town_dict'] = {}
            for code, title in dist_code_map.items():
                town_list = await AdministrativeDivision.distinct('title', {'level': 'T', 'parent_code': code})

                # http://code.wenjuan.com/WolvesAU/CRSPN/issues/15
                if title == '金安区':
                    town_list.extend(TEMP_LIU_AN_COMPANY_LIST)

                if title == '裕安区':
                    town_list.extend(TEMP_LIU_AN_YU_AN_COMPANY_LIST)

                res_dict['data']['town_dict'][title] = town_list

            res_dict['code'] = 1000
            RedisCache.hset(KEY_CACHE_WECHAT_TOWN, race_cid, json.dumps(res_dict))
        except Exception:
            logger.error(traceback.format_exc())

        return res_dict


class AppletRaceTownInfoSubmitHandler(WechatAppletHandler):
    """
    提交乡镇信息
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        res_dict = {'code': 0}
        try:
            open_id = self.get_i_argument("open_id")
            race_cid = self.get_i_argument("race_cid")
            if not (open_id and race_cid):
                res_dict['code'] = 1001
                return res_dict

            member = await find_member_by_open_id(open_id)
            if not member:
                res_dict['code'] = 1002
                return res_dict

            if not member.auth_address:
                res_dict['code'] = 1003
                return res_dict

            town = self.get_i_argument('town')
            if not town:
                res_dict['code'] = 1005
                return res_dict

            district = self.get_i_argument('district')
            if not district:
                res_dict['code'] = 1006
                return res_dict

            mapping = await RaceMapping.find_one({'member_cid': member.cid, 'race_cid': race_cid, 'record_flag': 1})
            if not mapping:
                mapping = RaceMapping(race_cid=race_cid, member_cid=member.cid)
                mapping.province_code = member.province_code
                mapping.city_code = member.city_code
                mapping.district_code = member.district_code
                mapping.age_group = member.age_group
                mapping.sex = member.sex
                mapping.category = member.category
                mapping.education = member.education

            if not mapping.auth_address:
                mapping.auth_address = member.auth_address

            mapping.auth_address['town'] = town
            mapping.auth_address['district'] = district

            await mapping.save()
            res_dict['code'] = 1000
            return res_dict
        except Exception:
            logger.error(traceback.format_exc())


URL_MAPPING_LIST = [
    url('/wechat/race/mobile/show/', AppletRaceMobileShowHandler, name='wechat_race_mobile_show'),
    url('/wechat/mobile/before/race/show/', AppletMobileBeforeRaceShowHandler, name='wechat_mobile_before_race_show'),
    url('/wechat/two/dimensional/code/check/race/', AppletTwoDimensionalCodeCheckRace,
        name='wechat_two_dimensional_code_check_race'),
    url('/wechat/race/town/info/check/', AppletRaceTownInfoCheckHandler, name='wechat_race_town_info_check'),
    url('/wechat/race/town/info/get/', AppletRaceTownInfoGetHandler, name='wechat_race_town_info_get'),
    url('/wechat/race/town/info/submit/', AppletRaceTownInfoSubmitHandler, name='wechat_race_town_info_submit')
]
