import traceback

from actions.applet import find_member_by_open_id
from actions.v_common import logger
from db.models import RaceMapping, Company
from motorengine.stages.group_stage import GroupStage
from db import STATUS_USER_ACTIVE
from db.models import Member, RaceCheckPointStatistics
from logger import log_utils
from motorengine import DESC
from motorengine.stages import MatchStage, SortStage, LimitStage, LookupStage, ProjectStage
from tornado.web import url
from web import WechatAppletHandler, decorators

logger = log_utils.get_logging()


class AppletRaceCompanyRanking(WechatAppletHandler):
    """
    单位排行榜
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
            rankings = []
            #  找到活动下面的所有的单位
            match_stage = MatchStage({'race_cid': race_cid, 'record_flag': 1})
            group_stage = GroupStage('company_cid', sum={'$sum': 1})

            company_list = await RaceMapping.aggregate(stage_list=[
                match_stage,
                group_stage,
                SortStage([('sum', DESC)])
            ]).to_list(None)
            for company in company_list:
                # 分类
                company_assort = await Company.find_one({'cid': company.id, 'record_flag': 1})

                rank = {
                    'title': company_assort.title if company_assort else '其他',
                    'people_count': company.sum
                }
                rankings.append(rank)
            r_dict = {
                'code': 1000,
                'rankings': rankings
            }
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletRaceRankingMemberHandler(WechatAppletHandler):
    """
    竞赛活动个人排行榜
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        res_dict = {'code': 0}
        try:
            open_id = self.get_i_argument('open_id', '')
            if not open_id:
                res_dict['code'] = 1001
                return res_dict

            member = await find_member_by_open_id(open_id)
            if not member:
                res_dict['code'] = 1002
                return res_dict

            race_cid = self.get_i_argument('race_cid', '')
            if not race_cid:
                res_dict['code'] = 1003
                return res_dict

            stat_list = await RaceCheckPointStatistics.aggregate(stage_list=[
                MatchStage({'race_cid': race_cid}),
                SortStage([('pass_checkpoint_num', DESC), ('correct_num', DESC)]),
                LimitStage(30),
                LookupStage(Member, 'member_cid', 'cid', 'member_list'),
                ProjectStage(**{
                    'nick_name': {'$arrayElemAt': ['$member_list.nick_name', 0]},
                    'avatar': {'$arrayElemAt': ['$member_list.avatar', 0]},
                    'correct_num': '$correct_num',
                    'pass_checkpoint_num': '$pass_checkpoint_num'
                })
            ]).to_list(30)

            res_dict = {
                'code': 1000,
                'rankings': stat_list
            }
        except Exception:
            logger.error(traceback.format_exc())

        return res_dict


class AppletRaceWhereAmIHandler(WechatAppletHandler):
    """
    我的排名
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        res_dict = {'ranking': 0}
        open_id = self.get_i_argument('open_id', '')
        if not open_id:
            res_dict['code'] = 1001
            return res_dict

        member = await find_member_by_open_id(open_id)
        if not member:
            res_dict['code'] = 1002
            return res_dict

        race_cid = self.get_i_argument('race_cid', '')
        if not race_cid:
            res_dict['code'] = 1003
            return res_dict

        try:
            me = await RaceCheckPointStatistics.find_one({'race_cid': race_cid, 'member_cid': member.cid})
            if me:
                num = await RaceCheckPointStatistics.count(
                    {'race_cid': race_cid, 'pass_checkpoint_num': {'$gte': me.pass_checkpoint_num},
                     'correct_num': {'$gte': me.correct_num}})

                res_dict['code'] = 1000
                res_dict['ranking'] = num
                return res_dict
        except Exception:
            logger.error(traceback.format_exc())

        res_dict['code'] = 1000
        return res_dict


URL_MAPPING_LIST = [
    url('/wechat/applet/race/ranking/member/', AppletRaceRankingMemberHandler,
        name='wechat_applet_race_ranking_member'),
    url(r'/wechat/applet/race/ranking/company/', AppletRaceCompanyRanking,
        name='wechat_applet_race_ranking_company'),
    url(r'/wechat/applet/race/where/am/i/', AppletRaceWhereAmIHandler, name='wechat_applet_race_where_am_i')
]
