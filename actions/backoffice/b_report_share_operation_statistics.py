# !/usr/bin/python
# -*- coding:utf-8 -*-

import copy
import json
import traceback

from db.enums import CATEGORY_MEMBER_SHARE_DICT, CATEGORY_MEMBER_SHARE_EXAM_RESULT, CATEGORY_MEMBER_SHARE_FRIEND_FIGHT
from db.models import AdministrativeDivision, MemberShareStatistics
from enums import PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT
from logger import log_utils
from motorengine import ASC
from motorengine.stages import MatchStage, SortStage
from motorengine.stages.group_stage import GroupStage
from motorengine.stages.project_stage import ProjectStage
from tornado.web import url
from web import BaseHandler, decorators
from .utils import parse_condition

logger = log_utils.get_logging()


def adjust_share():
    share_dict = copy.deepcopy(CATEGORY_MEMBER_SHARE_DICT)
    share_dict.pop(CATEGORY_MEMBER_SHARE_FRIEND_FIGHT)
    return share_dict


class ReportShareOperationStatisticsHandler(BaseHandler):
    """分享行为统计"""

    @decorators.render_template('backoffice/reports/share_operation_statistics.html')
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
        share_dict = adjust_share()
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0, 'pie': None, 'line': None}
        category = self.get_argument('category')
        if not category:
            ms = await MemberShareStatistics.aggregate([GroupStage('category', sum={'$sum': 1})]).to_list(None)
            r_dict['pie'] = {
                'legendData': list(set([v for _, v in CATEGORY_MEMBER_SHARE_DICT.items()]))
            }
            seriesData = [{'name': CATEGORY_MEMBER_SHARE_DICT.get(m.id), 'value': m.sum} for m in ms]
            key_list = [m.id for m in ms]
            res_index = ''
            fight_index = ""
            if CATEGORY_MEMBER_SHARE_EXAM_RESULT in key_list and CATEGORY_MEMBER_SHARE_FRIEND_FIGHT in key_list:
                res_index = key_list.index(CATEGORY_MEMBER_SHARE_EXAM_RESULT)
                fight_index = key_list.index(CATEGORY_MEMBER_SHARE_FRIEND_FIGHT)
            elif CATEGORY_MEMBER_SHARE_EXAM_RESULT not in key_list and CATEGORY_MEMBER_SHARE_FRIEND_FIGHT in key_list:
                fight_index = key_list.index(CATEGORY_MEMBER_SHARE_FRIEND_FIGHT)
                seriesData[fight_index]['name'] = CATEGORY_MEMBER_SHARE_EXAM_RESULT
            if res_index != "":
                seriesData[res_index]['value'] += seriesData[fight_index]['value']
                seriesData.remove(seriesData[fight_index])
            r_dict['pie']['seriesData'] = seriesData
            r_dict['code'] = 1
            return r_dict

        try:
            x_axis = self.get_argument('xAxis', '')
            condition_value = self.get_argument('condition_value', {})

            # 特殊处理 fix: http://code.wenjuan.com/WolvesAU/CRSPN/issues/13
            category = int(category)
            c_match = {'category': int(category)}
            if category == CATEGORY_MEMBER_SHARE_EXAM_RESULT:
                c_match = {'category': {'$in': [CATEGORY_MEMBER_SHARE_EXAM_RESULT, CATEGORY_MEMBER_SHARE_FRIEND_FIGHT]}}

            ms = await MemberShareStatistics.aggregate([
                MatchStage(c_match),
                MatchStage(parse_condition(condition_value)),
                ProjectStage(**{
                    'share_dt': {"$dateToString": {"format": "%Y-%m-%d", "date": "$share_dt"}},
                }),
                GroupStage('share_dt', sum={'$sum': 1}),
                SortStage([('_id', ASC)])
            ]).to_list(None)

            if not x_axis:
                x_axis_data = [m.id for m in ms]
                series_data = [m.sum for m in ms]
            else:
                x_axis_data = json.loads(x_axis)
                member_id_map = {m.id: m for m in ms}
                series_data = [member_id_map[data.get('value')].sum if data.get('value') in member_id_map else 0 for
                               data in x_axis_data]

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
    url('/backoffice/reports/share/operation/statistics/', ReportShareOperationStatisticsHandler,
        name='backoffice_reports_share_operation_statistics')
]
