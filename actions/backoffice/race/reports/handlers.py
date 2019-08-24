import json
import traceback

from actions.backoffice.race.reports.utils import replace_race_other_area, deal_with_series_data, \
    deal_with_important_people
from actions.backoffice.race.utils import get_menu
from actions.backoffice.utils import parse_race_condition
from db import CATEGORY__RACE_AREA_PLAYER_ACCURACY, CATEGORY__RACE_AREA_PLAYER_QUANTITY, \
    CATEGORY_RACE_AREA_CLEARANCE_QUANTITY, CATEGORY_RACE_AREA_IMPORTANT_QUANTITY, \
    CATEGORY_RACE_AREA_IMPORTANT_PLAYER_ACCURACY, CATEGORY_MEMBER_DICT, STATUS_SUBJECT_DIMENSION_ACTIVE
from db.models import Race, RaceMapping, MemberCheckPointHistory, RaceGameCheckPoint, AdministrativeDivision, \
    SubjectDimension, ReportRacePeopleStatistics
from enums import PERMISSION_TYPE_MINIAPP_RACE_REPORT_SITUATION
from logger import log_utils
from motorengine import ASC, DESC
from motorengine.stages import MatchStage, LookupStage, SortStage
from motorengine.stages.group_stage import GroupStage
from tornado.web import url
from web import BaseHandler, decorators

logger = log_utils.get_logging()


class RaceReportAreaAnalysisHandler(BaseHandler):
    """
    活动区域报表
    """

    @decorators.render_template('backoffice/race/reports/AreaAnalysis.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_REPORT_SITUATION)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'report', race_cid, tag=1)
        region_code_list = []
        manage_region_code_list = self.current_user.manage_region_code_list
        ad_cursor = AdministrativeDivision.find({'code': {'$in': self.current_user.manage_region_code_list}})
        while await ad_cursor.fetch_next:
            ad = ad_cursor.next_object()
            if ad:
                if ad.level == 'P':
                    region_code_list.append('[p]%s' % ad.code)
                elif ad.level == 'C':
                    region_code_list.append('[c]%s' % ad.code)
                elif ad.level == 'D':
                    region_code_list.append('[d]%s' % ad.code)
        subject_dimension_list = await SubjectDimension.aggregate(
            [MatchStage(dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=None)),
             LookupStage(SubjectDimension, 'cid', 'parent_cid', 'sub_subject_dimension_list')]).to_list(None)
        return locals()

    @decorators.render_json
    async def post(self):
        race_cid = self.get_argument('race_cid', '')
        r_dict = {'code': 0, 'line': None}
        category = self.get_argument('category')
        if not category:
            return r_dict

        try:
            category = int(category)
            condition = self.get_argument('condition_value')
            x_axis = self.get_argument('xAxis', '')
            race = await Race.find_one({'cid': race_cid, 'record_flag': 1})
            checkpoint_list = await RaceGameCheckPoint.find({'race_cid': race_cid, 'record_flag': 1}).to_list(None)
            last_checkpoint_cid = ''
            sort_stage = SortStage([('_id', ASC)])
            if checkpoint_list:
                last_checkpoint_cid = checkpoint_list[-1].cid
            if not race.city_code:
                # 省级活动， 按照市来区分
                group_stage = GroupStage('auth_address.city', sum={'$sum': 1})
                match_stage = MatchStage({'race_cid': race_cid, 'record_flag': 1})
                group_partake_accuracy = GroupStage('auth_address.city', total_correct={'$sum': '$total_correct'},
                                                    total_count={'$sum': '$total_count'})
                important_player_group_stage = GroupStage('category', sum={'$sum': 1})
                important_player_accuracy = GroupStage('category', total_correct={'$sum': '$total_correct'},
                                                       total_count={'$sum': '$total_count'})
                important_match_stage = MatchStage({'category': {'$ne': 0}, 'race_cid': race_cid, 'record_flag': 1})
                check_point_lookup = LookupStage(
                    MemberCheckPointHistory, let={'primary_cid': '$member_cid'},
                    as_list_name='history_list',
                    pipeline=[
                        {
                            '$match': {

                                '$expr': {
                                    '$and': [
                                        {'$eq': ['$member_cid', '$$primary_cid']},
                                        {'$eq': ['$status', 1]},
                                        {'$eq': ['$check_point_cid', last_checkpoint_cid]}
                                    ]
                                }

                            }
                        },
                        {'$match': {
                            'history_list': {'$ne': []}
                        }}

                    ]
                )
                match_checkpoint_stage = MatchStage({'history_list': {'$ne': []}})
            else:
                #  市级活动， 按照区来分组
                group_stage = GroupStage('auth_address.district', sum={'$sum': 1})
                match_stage = MatchStage({'race_cid': race_cid, 'record_flag': 1})
                group_partake_accuracy = GroupStage('auth_address.district', total_correct={'$sum': '$total_correct'},
                                                    total_count={'$sum': '$total_count'})
                important_player_group_stage = GroupStage('category', sum={'$sum': 1})
                important_player_accuracy = GroupStage('category', total_correct={'$sum': '$total_correct'},
                                                       total_count={'$sum': '$total_count'})
                important_match_stage = MatchStage({'category': {'$ne': 0}, 'race_cid': race_cid, 'record_flag': 1})
                check_point_lookup = LookupStage(
                    MemberCheckPointHistory, let={'primary_cid': '$member_cid'},
                    as_list_name='history_list',
                    pipeline=[
                        {'$match': {
                            '$expr': {
                                '$and': [
                                    {'$eq': ['$member_cid', '$$primary_cid']},
                                    {'$eq': ['$status', 1]},
                                    {'$eq': ['$check_point_cid', last_checkpoint_cid]}
                                ]
                            }

                        }
                        },
                    ]

                )
                match_checkpoint_stage = MatchStage({'history_list': {'$ne': []}})
            if category == CATEGORY__RACE_AREA_PLAYER_QUANTITY:
                #  各区参与人数
                stats = await RaceMapping.aggregate(
                    stage_list=[MatchStage(parse_race_condition(condition)), match_stage, group_stage,
                                sort_stage]).to_list(None)
                series_data = [s.sum for s in stats]
                if not x_axis:
                    x_axis_data = [s.id for s in stats if s]
                    x_axis_data, series_data = replace_race_other_area(x_axis_data, series_data, is_sort=True)
                else:
                    x_axis_data = json.loads(x_axis)
                    series_data = await deal_with_series_data(stats, x_axis_data, series_data)
                if not x_axis_data:
                    x_axis_data = ['暂无数据']
                r_dict = {
                    'code': 1,
                    'bar': {
                        'xAxisData': x_axis_data,
                        'seriesData': series_data
                    }
                }
            if category == CATEGORY__RACE_AREA_PLAYER_ACCURACY:
                # 各区参与正确率
                stats = await RaceMapping.aggregate(
                    stage_list=[MatchStage(parse_race_condition(condition)), match_stage, group_partake_accuracy,
                                sort_stage]).to_list(None)

                # series_data = [(s.total_correct / s.total_count) * 100 for s in stats if s and s.total_count != 0]
                series_data = []
                for s in stats:
                    if s and s.total_count == 0:
                        series_data.append(0)
                    elif s and s.total_count != 0:
                        series_data.append((s.total_correct / s.total_count) * 100)
                if not x_axis:
                    x_axis_data = [s.id for s in stats if s]
                    x_axis_data, series_data = replace_race_other_area(x_axis_data, series_data)
                else:
                    x_axis_data = json.loads(x_axis)
                    if len(series_data) != len(x_axis_data):
                        series_data = [0 for _ in range(len(x_axis_data))]
                        for s in stats:
                            if s.id in x_axis_data and s.total_count != 0:
                                index = x_axis_data.index(s.id)
                                series_data[index] = (s.total_correct / s.total_count) * 100
                if not x_axis_data:
                    x_axis_data = ['暂无数据']
                r_dict = {
                    'code': 1,
                    'line': {
                        'xAxisData': x_axis_data,
                        'seriesData': series_data
                    }
                }
            if category == CATEGORY_RACE_AREA_CLEARANCE_QUANTITY:
                """
                各区通关人数
                """
                stats = await RaceMapping.aggregate(
                    stage_list=[MatchStage(parse_race_condition(condition)), match_stage, check_point_lookup,
                                match_checkpoint_stage, group_stage,
                                sort_stage]).to_list(None)
                series_data = [s.sum for s in stats if s]
                if not x_axis:
                    x_axis_data = [s.id for s in stats if s]
                    x_axis_data, series_data = replace_race_other_area(x_axis_data, series_data, is_sort=True)
                else:
                    x_axis_data = json.loads(x_axis)
                    series_data = await deal_with_series_data(stats, x_axis_data, series_data)
                if not x_axis_data:
                    x_axis_data = ['暂无数据']
                r_dict = {
                    'code': 1,
                    'bar': {
                        'xAxisData': x_axis_data,
                        'seriesData': series_data
                    }
                }
            if category == CATEGORY_RACE_AREA_IMPORTANT_QUANTITY:
                """
                重点人群参与人数
                """
                stats = await RaceMapping.aggregate(
                    stage_list=[MatchStage(parse_race_condition(condition)), important_match_stage,
                                important_player_group_stage,
                                sort_stage]).to_list(None)
                series_data = [s.sum for s in stats if s]
                if not x_axis:
                    x_axis_data = [s.id for s in stats if s]
                    none_index = ''
                    if None in x_axis_data:
                        none_index = x_axis_data.index(None)
                    if (none_index or none_index == 0) and series_data:
                        x_axis_data[none_index] = '其他'
                        x_axis_data[none_index], x_axis_data[-1] = x_axis_data[-1], x_axis_data[none_index]
                        series_data[none_index], series_data[-1] = series_data[-1], series_data[none_index]
                    for index, x_axis in enumerate(x_axis_data):
                        if x_axis not in ['其他', None]:
                            x_axis_data[index] = CATEGORY_MEMBER_DICT[x_axis]
                else:
                    x_axis_data = json.loads(x_axis)
                    series_data = await deal_with_important_people(stats, x_axis_data, series_data)
                if not x_axis_data:
                    x_axis_data = ['暂无数据']
                r_dict = {
                    'code': 1,
                    'bar': {
                        'xAxisData': x_axis_data,
                        'seriesData': series_data
                    }
                }
            if category == CATEGORY_RACE_AREA_IMPORTANT_PLAYER_ACCURACY:
                #  重点人群正确率
                stats = await RaceMapping.aggregate(
                    stage_list=[MatchStage(parse_race_condition(condition)), important_match_stage,
                                important_player_accuracy, sort_stage]).to_list(None)

                series_data = [(s.total_correct / s.total_count) * 100 for s in stats if s and s.total_count != 0]
                if not x_axis:
                    x_axis_data = [s.id for s in stats if s]
                    none_index = ''
                    if None in x_axis_data:
                        none_index = x_axis_data.index(None)
                    if (none_index or none_index == 0) and series_data:
                        x_axis_data[none_index] = '其他'
                        x_axis_data[none_index], x_axis_data[-1] = x_axis_data[-1], x_axis_data[none_index]
                        series_data[none_index], series_data[-1] = series_data[-1], series_data[none_index]
                    for index, x_axis in enumerate(x_axis_data):
                        if x_axis not in ['其他', None]:
                            x_axis_data[index] = CATEGORY_MEMBER_DICT[x_axis]

                else:
                    x_axis_data = json.loads(x_axis)
                    if len(series_data) != len(x_axis_data):
                        series_data = [0 for _ in range(len(x_axis_data))]
                        for s in stats:
                            if CATEGORY_MEMBER_DICT[s.id] in x_axis_data and s.total_count != 0:
                                index = x_axis_data.index(CATEGORY_MEMBER_DICT[s.id])
                                series_data[index] = (s.total_correct / s.total_count) * 100
                if len(x_axis_data) == 1 and None in x_axis_data:
                    x_axis_data = ['其他']
                if not x_axis_data:
                    x_axis_data = ['暂无数据']
                r_dict = {
                    'code': 1,
                    'line': {
                        'xAxisData': x_axis_data,
                        'seriesData': series_data
                    }
                }
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceReportPeopleQuantityStatisticsHander(BaseHandler):
    """
    活动报表-（参与人数/通关人数）
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_REPORT_SITUATION)
    async def post(self):
        r_dict = {'code': 0}

        race_cid = self.get_argument('race_cid', '')
        condition = self.get_argument('condition_value')
        group_type = self.get_argument('group_type', 'date')
        count_pass = self.get_argument('count_pass')
        if count_pass:
            sum_value = '$pass_num'
        else:
            sum_value = '$people_num'

        pre_data = self.get_argument('pre_data')
        query = {'race_cid': race_cid, 'record_flag': 1}
        if pre_data:
            pre_data: dict = json.loads(pre_data)
            query.update(pre_data)
        match_stage = MatchStage(query)
        stage_list = [match_stage, MatchStage(parse_race_condition(condition))]
        sort_stage = SortStage([('sum', DESC)])

        group_id = None
        if group_type == 'date':
            group_id = 'daily_code'
            sort_stage = SortStage([('_id', ASC)])
        if group_type == 'province':
            group_id = 'province'
        if group_type == 'city':
            group_id = 'city'
        if group_type == 'district':
            group_id = 'district'

        group_stage = GroupStage(group_id, sum={'$sum': sum_value})
        stage_list += [group_stage, sort_stage]

        try:

            stats = await ReportRacePeopleStatistics.aggregate(stage_list).to_list(None)
            series_data = [s.sum for s in stats]

            x_axis_data = [s.id for s in stats if s]
            if not x_axis_data:
                x_axis_data = ['暂无数据']
            r_dict = {
                'code': 1,
                'bar': {
                    'xAxisData': x_axis_data,
                    'seriesData': series_data
                }
            }
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


URL_MAPPING_LIST = [
    url('/backoffice/race/reports/area/analysis/', RaceReportAreaAnalysisHandler,
        name='backoffice_race_reports_area_analysis'),
    url('/backoffice/race/reports/people/quantity/', RaceReportPeopleQuantityStatisticsHander,
        name='backoffice_race_reports_people_quantity'),
]
