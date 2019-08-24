# !/usr/bin/python
# -*- coding:utf-8 -*-

import json
import traceback

from tornado.web import url

from db.enums import CATEGORY_MEMBER_LEARN_SUBJECT_WRONG, CATEGORY_MEMBER_LEARN_SUBJECT_RESOLVING_TREND, \
    CATEGORY_MEMBER_LEARN_SUBJECT_RESOLVING_VIEWED, CATEGORY_MEMBER_LEARN_SUBJECT_PERSONAL_CENTER
from db.models import AdministrativeDivision, SubjectWrongViewedStatistics, SubjectResolvingViewedStatistics, \
    PersonalCenterViewedStatistics
from enums import PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT
from logger import log_utils
from motorengine import ASC
from motorengine.stages import MatchStage, SortStage, LimitStage
from motorengine.stages.group_stage import GroupStage
from web import BaseHandler, decorators
from .utils import parse_condition

logger = log_utils.get_logging()


class ReportLearnOperationStatisticsHandler(BaseHandler):
    """学习行为统计"""

    @decorators.render_template('backoffice/reports/learn_operation_statistics.html')
    @decorators.permission_required(PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT)
    async def get(self):
        dark_skin = self.get_argument('dark_skin')
        dark_skin = True if dark_skin == 'True' else False
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

        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0, 'line': None}
        category = self.get_argument('category')
        if not category:
            return r_dict

        try:
            category = int(category)
            condition = self.get_argument('condition_value')
            x_axis = self.get_argument('xAxis', '')

            stats = None  # 统计结果

            if category == CATEGORY_MEMBER_LEARN_SUBJECT_WRONG:
                stats = await SubjectWrongViewedStatistics.aggregate(stage_list=[
                    MatchStage(parse_condition(condition)),
                    GroupStage('count', sum={'$sum': 1}),
                    SortStage([('_id', ASC)]),
                    LimitStage(6)
                ]).to_list(None)

            if category == CATEGORY_MEMBER_LEARN_SUBJECT_RESOLVING_VIEWED:
                stats = await SubjectResolvingViewedStatistics.aggregate(stage_list=[
                    MatchStage(parse_condition(condition)),
                    GroupStage('member_cid', sum={'$sum': 1}),
                    GroupStage('sum', sum={'$sum': 1}),
                    SortStage([('_id', ASC)]),
                    LimitStage(6)
                ]).to_list(None)

            if category == CATEGORY_MEMBER_LEARN_SUBJECT_RESOLVING_TREND:
                stats = await SubjectResolvingViewedStatistics.aggregate(stage_list=[
                    MatchStage(parse_condition(condition)),
                    MatchStage({'wrong_count': {'$gt': 0}}),
                    GroupStage('wrong_count', sum={'$sum': 1}),
                    SortStage([('_id', ASC)]),
                    LimitStage(6)
                ]).to_list(None)

            if category == CATEGORY_MEMBER_LEARN_SUBJECT_PERSONAL_CENTER:
                stats = await PersonalCenterViewedStatistics.aggregate(stage_list=[
                    MatchStage(parse_condition(condition)),
                    GroupStage('count', sum={'$sum': 1}),
                    SortStage([('_id', ASC)]),
                    LimitStage(6)
                ]).to_list(None)

            member_count = sum([s.sum for s in stats])
            if not x_axis:
                x_axis_data = [s.id for s in stats]
                if member_count == 0:
                    series_data = [0] * len(x_axis_data)
                else:
                    series_data = [s.sum / member_count * 100 for s in stats]
            else:
                x_axis_data = json.loads(x_axis)
                stat_id_map = {s.id: s for s in stats}
                if member_count == 0:
                    series_data = [0] * len(x_axis_data)
                else:

                    series_data = [stat_id_map[data.get('value')].sum / member_count * 100 if data.get('value') in stat_id_map else 0 for data in
                                   x_axis_data]

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


URL_MAPPING_LIST = [
    url('/backoffice/reports/learn/operation/statistics/', ReportLearnOperationStatisticsHandler,
        name='backoffice_reports_learn_operation_statistics')
]
