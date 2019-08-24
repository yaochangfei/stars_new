import json
import traceback

from actions.backoffice.race.reports.utils import replace_race_other_area
from actions.backoffice.race.utils import get_menu
from actions.backoffice.utils import parse_race_condition
from db import CATEGORY__RACE_COMPANY_PLAYER_ACCURACY, CATEGORY__RACE_COMPANY_PLAYER_QUANTITY, \
    CATEGORY_RACE_COMPANY_CLEARANCE_QUANTITY, STATUS_SUBJECT_DIMENSION_ACTIVE
from db.models import RaceMapping, Company, MemberCheckPointHistory, RaceGameCheckPoint, SubjectDimension, \
    AdministrativeDivision
from enums import PERMISSION_TYPE_MINIAPP_RACE_REPORT_EXECUTION
from logger import log_utils
from motorengine import ASC
from motorengine.stages import MatchStage, SortStage, LookupStage
from motorengine.stages.group_stage import GroupStage
from tornado.web import url
from web import BaseHandler, decorators

logger = log_utils.get_logging()


class RaceReportExecuteComanyAnalysisHandler(BaseHandler):
    """
    活动执行报表
    """

    @decorators.render_template('backoffice/race/execute_reports/CompanyAnalysis.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_REPORT_EXECUTION)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        if race_cid:
            menu_list = await get_menu(self, 'config', race_cid, tag=1)
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
        member_cid_list = await RaceMapping.distinct('member_cid', {'race_cid': race_cid,
                                                                    'company_cid': '3A6E1E81BD02EA321FEAB121D6DCCFDD'})
        num = 0
        for member_cid in member_cid_list:
            history = await MemberCheckPointHistory.find_one(
                {'member_cid': member_cid, 'status': 1, 'check_point_cid': '6F9E3F448F5673CBA7CC7D419F287EF7'})
            if history:
                num += 1
        try:
            category = int(category)
            checkpoint_list = await RaceGameCheckPoint.find({'race_cid': race_cid, 'record_flag': 1}).to_list(None)
            last_checkpoint_cid = ''
            if checkpoint_list:
                last_checkpoint_cid = checkpoint_list[-1].cid
            condition = self.get_argument('condition_value')
            x_axis = self.get_argument('xAxis', '')
            #  根据公司cid来分组
            company_group_stage = GroupStage('company_cid', sum={'$sum': 1})
            sort_stage = SortStage([('_id', ASC)])
            match_stage = MatchStage({'race_cid': race_cid, 'record_flag': 1})
            company_accuracy_group_stage = GroupStage('company_cid', total_correct={'$sum': '$total_correct'},
                                                      total_count={'$sum': '$total_count'})

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
            if category == CATEGORY__RACE_COMPANY_PLAYER_QUANTITY:
                #  各公司的参与人数
                stats = await RaceMapping.aggregate(
                    stage_list=[MatchStage(parse_race_condition(condition)), match_stage, company_group_stage,
                                sort_stage,
                                ]).to_list(None)
                x_axis_data = []
                series_data = [s.sum for s in stats]
                if not x_axis and stats:
                    company_cid_list = [s.id for s in stats if s]
                    #  把公司cid改成公司标题
                    for company_cid in company_cid_list:
                        if company_cid:
                            company = await Company.find_one({'cid': company_cid, 'record_flag': 1})
                            x_axis_data.append(company.title)
                        else:
                            x_axis_data.append(None)
                    x_axis_data, series_data = replace_race_other_area(x_axis_data, series_data)
                else:
                    x_axis_data = json.loads(x_axis)
                    if len(series_data) != len(x_axis_data):
                        series_data = [0 for _ in range(len(x_axis_data))]
                        for s in stats:
                            company = await Company.find_one({'cid': s.id, 'record_flag': 1})
                            title = company.title
                            if title in x_axis_data:
                                index = x_axis_data.index(title)
                                series_data[index] = s.sum
                if not x_axis_data:
                    x_axis_data = ['暂无数据']
                r_dict = {
                    'code': 1,
                    'bar': {
                        'xAxisData': x_axis_data,
                        'seriesData': series_data,
                    }
                }
            if category == CATEGORY__RACE_COMPANY_PLAYER_ACCURACY:
                # 各公司的正确率
                stats = await RaceMapping.aggregate(
                    stage_list=[MatchStage(parse_race_condition(condition)), match_stage, company_accuracy_group_stage,
                                sort_stage]).to_list(
                    None)
                x_axis_data = []
                series_data = [(s.total_correct / s.total_count) * 100 for s in stats if s and s.total_count != 0]
                if not x_axis:
                    company_cid_list = [s.id for s in stats if s]
                    #  把公司cid改成公司标题
                    for company_cid in company_cid_list:
                        if company_cid:
                            company = await Company.find_one({'cid': company_cid, 'record_flag': 1})
                            x_axis_data.append(company.title)
                        else:
                            x_axis_data.append(None)
                    x_axis_data, series_data = replace_race_other_area(x_axis_data, series_data)
                else:
                    x_axis_data = json.loads(x_axis)
                    if len(series_data) != len(x_axis_data):
                        series_data = [0 for _ in range(len(x_axis_data))]
                        for s in stats:
                            company = await Company.find_one({'cid': s.id, 'record_flag': 1})
                            title = company.title
                            if title in x_axis_data and s.total_count != 0:
                                index = x_axis_data.index(title)
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
            if category == CATEGORY_RACE_COMPANY_CLEARANCE_QUANTITY:
                """
                各公司的通关人数
                """
                stats = await RaceMapping.aggregate(
                    stage_list=[MatchStage(parse_race_condition(condition)), match_stage, check_point_lookup,
                                match_checkpoint_stage, company_group_stage, sort_stage]).to_list(None)
                series_data = [s.sum for s in stats if s]
                if not x_axis:
                    x_axis_data = []
                    if not x_axis and stats:
                        company_cid_list = [s.id for s in stats if s]
                        #  把公司cid改成公司标题
                        for company_cid in company_cid_list:
                            if company_cid:
                                company = await Company.find_one({'cid': company_cid, 'record_flag': 1})
                                x_axis_data.append(company.title)
                            else:
                                x_axis_data.append(None)
                    x_axis_data, series_data = replace_race_other_area(x_axis_data, series_data)
                else:
                    x_axis_data = json.loads(x_axis)
                    if len(series_data) != len(x_axis_data):
                        series_data = [0 for _ in range(len(x_axis_data))]
                        for s in stats:
                            company = await Company.find_one({'cid': s.id, 'record_flag': 1})
                            title = company.title
                            if title in x_axis_data:
                                index = x_axis_data.index(title)
                                series_data[index] = s.sum
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
    url('/backoffice/race/execute/report/company/analysis/', RaceReportExecuteComanyAnalysisHandler,
        name='backoffice_race_execute_report_company_analysis'),
]
