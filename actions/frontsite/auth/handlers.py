import traceback

from tornado.web import url

from caches.redis_utils import RedisCache
from commons.common_utils import md5
from db import STATUS_RACE_ACTIVE
from db.models import User, AdministrativeDivision, Race
from enums import PERMISSION_TYPE_MINIAPP_RACE_REPORT_SITUATION, \
    KEY_SESSION_USER
from logger import log_utils
from web import decorators, BaseHandler

logger = log_utils.get_logging()


class RaceLoginViewHandler(BaseHandler):
    """
    科协登录页面
    """

    @decorators.render_template('frontsite/auth/login.html')
    async def get(self):
        return locals()

    @decorators.render_json
    async def post(self):
        r_dict = {'code': 0}
        try:
            username = self.get_argument('username', '')
            password = self.get_argument('password', '')
            if username and password:
                user = await User.find_one({'login_name': username})
                if not user:
                    r_dict['code'] = -1  # 没有用户
                    return r_dict
                if PERMISSION_TYPE_MINIAPP_RACE_REPORT_SITUATION not in user.permission_code_list:
                    r_dict['code'] = -2  # 该用户没有查看权限
                    return r_dict
                if md5(password) != user.login_password:
                    r_dict['code'] = -3  # 密码不正确
                    return r_dict
                if not (user.province or user.city):
                    r_dict['code'] = -5
                    return r_dict
                self.session.put(KEY_SESSION_USER, user)
                self.session.save()
                r_dict['code'] = 1
            else:
                r_dict['code'] = -4
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceSeeReportListViewHandler(BaseHandler):
    """
    报告列表页面
    """

    @decorators.render_template('frontsite/report/index.html')
    async def get(self):
        user = self.get_current_user()
        #  session过期，跳转到登录页面
        if not user:
            return self.redirect(self.reverse_url('frontsite_race_login'))

        if user.province:
            region_name = user.province.replace('省', '').replace('市', '')
            _city = None
            _prov = await AdministrativeDivision.find_one(
                {'title': {'$regex': region_name}, 'parent_code': None})
        else:
            _city = await AdministrativeDivision.find_one({'title': {'$regex': user.city}})
            _prov = await AdministrativeDivision.find_one({'code': _city.parent_code})
            region_name = _prov.title.replace('省', '').replace('市', '')

        if _city:
            map_code_dict = {_city.title.replace('市', ''): _city.code}
        else:
            map_list = await AdministrativeDivision.find({'parent_code': _prov.code}).to_list(None)
            map_code_dict = {m.title.replace('市', ''): m.code for m in map_list}

        race = await Race.find_one(
            {'province_code': _prov.code, 'city_code': _city.code if _city else {'$in': [None, '']},
             'status': STATUS_RACE_ACTIVE,
             'record_flag': 1})
        race_cid = race.cid if race else None

        return locals()


class RaceLogoutHandler(BaseHandler):
    async def get(self):
        self.current_user = None
        self.clear_cookie('_xsrf')
        self.session.drop()
        self.redirect(self.reverse_url('frontsite_race_login'))


class RaceSpecialLoginViewHandler(BaseHandler):
    """
    安徽科协账号登录页面
    """

    @decorators.render_template('frontsite/auth/special_login.html')
    async def get(self):
        return locals()

    @decorators.render_json
    async def post(self):
        r_dict = {'code': 0}
        try:
            username = self.get_argument('username', '')
            password = self.get_argument('password', '')
            if username and password:
                user = await User.find_one({'login_name': username})
                if not user:
                    r_dict['code'] = -1  # 没有用户
                    return r_dict
                if PERMISSION_TYPE_MINIAPP_RACE_REPORT_SITUATION not in user.permission_code_list:
                    r_dict['code'] = -2  # 该用户没有查看权限
                    return r_dict
                if md5(password) != user.login_password:
                    r_dict['code'] = -3  # 密码不正确
                    return r_dict
                if not (user.province or user.city):
                    r_dict['code'] = -5
                    return r_dict
                #  可管理地区
                region_code_list = user.manage_region_code_list
                is_enter = False
                for region_code in region_code_list:
                    city_list = await AdministrativeDivision.find({'parent_code': '340000'}).to_list(None)
                    total_code_list = [city.code for city in city_list]
                    total_code_list.append("340000")
                    if region_code in total_code_list:
                        is_enter = True
                if not is_enter:
                    r_dict['code'] = -6
                    return r_dict

                self.session.put(KEY_SESSION_USER, user)
                self.session.save()
                r_dict['code'] = 1
            else:
                r_dict['code'] = -4
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceSeeSpecialReportListViewHandler(BaseHandler):
    """
    安徽报告列表页面
    """

    @decorators.render_template('frontsite/report/special_index.html')
    async def get(self):
        user = self.get_current_user()
        #  session过期，跳转到登录页面
        if not user:
            return self.redirect(self.reverse_url('frontsite_race_special_login'))
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
        if region == "340000":
            _prov = await AdministrativeDivision.find_one(
                {'code': "340000", 'parent_code': None})
            region_name = _prov.title.replace('省', '').replace('市', '')
            area_category = 'province'
            _city = None
        else:
            area_category = 'city'
            _city = await AdministrativeDivision.find_one({'code': region})
            _prov = await AdministrativeDivision.find_one({'code': _city.parent_code})
            region_name = _city.title.replace('省', '')

        if _city:
            map_code_dict = {_city.title.replace('市', ''): _city.code}
        else:
            map_list = await AdministrativeDivision.find({'parent_code': _prov.code}).to_list(None)
            map_code_dict = {m.title.replace('市', ''): m.code for m in map_list}

        race = await Race.find_one(
            {'province_code': _prov.code, 'city_code': _city.code if _city else {'$in': [None, '']},
             'status': STATUS_RACE_ACTIVE,
             'record_flag': 1})
        race_cid = race.cid if race else None
        return locals()


URL_MAPPING_LIST = [
    url(r'/frontsite/race/login/', RaceLoginViewHandler, name="frontsite_race_login"),
    url(r'/frontsite/race/see/report/', RaceSeeReportListViewHandler, name="frontsite_race_see_report"),
    url(r'/frontsite/race/login/out/', RaceLogoutHandler, name="frontsite_race_login_out"),
    url(r'/frontsite/race/special/login/', RaceSpecialLoginViewHandler, name="frontsite_race_special_login"),
    url(r'/frontsite/race/see/special/report/', RaceSeeSpecialReportListViewHandler,
        name="frontsite_race_see_special_report")
]
