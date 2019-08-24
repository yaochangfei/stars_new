import traceback

from actions.applet import find_member_by_open_id
from tornado.web import url

from actions.v_common import logger
from commons.msg_utils import check_digit_verify_code
from db import STATUS_USER_ACTIVE, STATUS_UNIT_MANAGER_ACTIVE
from db.models import Race, Member, Company, RaceMapping
from web import WechatAppletHandler, decorators


class AppletSubmitCompanyHandler(WechatAppletHandler):
    """
    提交单位信息
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        race_cid = self.get_i_argument('race_cid', None)
        company_cid = self.get_i_argument('company_cid', None)
        if not race_cid:
            r_dict['code'] = 1001
            return r_dict
        member = await find_member_by_open_id(open_id)
        if not member:
            r_dict['code'] = 1002
            return r_dict
        company = await Company.find_one({'cid': company_cid, 'record_flag': 1})
        if not company:
            r_dict['code'] = 1003
            return r_dict
        try:
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
                mapping.company_cid = company_cid
            else:
                mapping.company_cid = company_cid

            if not mapping.auth_address:
                mapping.auth_address = member.auth_address

            await mapping.save()
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletCompanyListHandler(WechatAppletHandler):
    """
    活动单位列表
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        race_cid = self.get_i_argument('race_cid', None)
        if not race_cid:
            r_dict['code'] = 1001
            return r_dict
        member = await find_member_by_open_id(open_id)
        if not member:
            r_dict['code'] = 1002
            return r_dict
        try:
            company_title_list = []
            company_dict = {}
            company_list = await Company.find(
                {'race_cid': race_cid, 'record_flag': 1, "status": STATUS_UNIT_MANAGER_ACTIVE}).to_list(None)
            if company_list:
                for company in company_list:
                    company_title_list.append(company.title)
                    company_dict[company.title] = company.cid
            r_dict['code'] = 1000
            r_dict['company_title_list'] = company_title_list
            r_dict['company_dict'] = company_dict
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletRaceTelHandler(WechatAppletHandler):
    """
    填写手机号弹窗提示
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        race_cid = self.get_i_argument('race_cid', None)
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
            if race.mobile_enabled:
                r_dict['mobile_enabled'] = True
            if race_map and race_map.mobile:
                r_dict['mobile_enabled'] = False
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletRaceSubmitMobilHandler(WechatAppletHandler):
    """
    提交手机号码
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        race_cid = self.get_i_argument('race_cid', None)
        mobile = self.get_i_argument('mobile', None)
        v_code = self.get_i_argument('v_code', '')
        if not race_cid:
            r_dict['code'] = 1001
            return r_dict
        member = await find_member_by_open_id(open_id)
        if not member:
            r_dict['code'] = 1002
            return r_dict
        if not mobile:
            r_dict['code'] = 1003
            return r_dict
        try:
            mapping = await RaceMapping.find_one({'member_cid': member.cid, 'race_cid': race_cid, 'record_flag': 1})
            if not mapping:
                mapping = RaceMapping(race_cid=race_cid, member_cid=member.cid)
                mapping.province_code = member.province_code
                mapping.city_code = member.city_code
                mapping.district_code = member.district_code
                mapping.mobile = mobile
            else:
                mapping.mobile = mobile
            mapping.auth_address = member.auth_address

            member.mobile = mobile
            if check_digit_verify_code(mobile, v_code):
                r_dict['code'] = 1000
                await member.save()
                await mapping.save()
            else:
                r_dict['code'] = 1004
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletRaceWhetherCompanyRankingHandler(WechatAppletHandler):
    """
    是否有单位排行榜
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        race_cid = self.get_i_argument('race_cid', None)
        if not race_cid:
            r_dict['code'] = 1001
            return r_dict
        member = await find_member_by_open_id(open_id)
        if not member:
            r_dict['code'] = 1002
            return r_dict
        try:
            race = await Race.find_one({'cid': race_cid, 'record_flag': 1})
            if race.company_enabled:
                r_dict['has_company_ranking'] = True
            r_dict['code'] = 1000
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class AppletSubmitMobilBeforeRaceHandler(WechatAppletHandler):
    """
    提交进入活动之前填写的手机号码
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id', None)
        race_cid = self.get_i_argument('race_cid', None)
        mobile = self.get_i_argument('mobile', None)
        v_code = self.get_i_argument('v_code', '')
        if not race_cid:
            r_dict['code'] = 1001
            return r_dict
        member = await find_member_by_open_id(open_id)
        if not member:
            r_dict['code'] = 1002
            return r_dict
        if not mobile:
            r_dict['code'] = 1003
            return r_dict
        try:
            if check_digit_verify_code(mobile, v_code):
                r_dict['code'] = 1000
            else:
                r_dict['code'] = 1004
                return r_dict

            mapping = await RaceMapping.find_one({'member_cid': member.cid, 'race_cid': race_cid, 'record_flag': 1})
            if not mapping:
                mapping = RaceMapping(race_cid=race_cid, member_cid=member.cid)
                mapping.province_code = member.province_code
                mapping.city_code = member.city_code
                mapping.district_code = member.district_code
                mapping.mobile = mobile
            else:
                mapping.mobile = mobile
            mapping.auth_address = member.auth_address
            await mapping.save()

            member.mobile = mobile
            await member.save()
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/wechat/applet/race/company/submit/', AppletSubmitCompanyHandler,
        name='wechat_applet_race_company_submit'),
    url(r'/wechat/applet/race/company/list/', AppletCompanyListHandler,
        name='wechat_applet__race_company_list'),
    url(r'/wechat/applet/race/mobile/', AppletRaceTelHandler,
        name='wechat_applet__race_mobile'),
    url(r'/wechat/applet/race/mobile/submit/', AppletRaceSubmitMobilHandler,
        name='wechat_applet__race_mobile_submit'),
    url(r'/wechat/applet/mobile/before/race/submit/', AppletSubmitMobilBeforeRaceHandler,
        name='wechat_applet_mobile_race_submit'),
    url(r'/wechat/applet/race/whether/company/ranking/', AppletRaceWhetherCompanyRankingHandler,
        name='wechat_applet__race_whether_company_ranking'),
]
