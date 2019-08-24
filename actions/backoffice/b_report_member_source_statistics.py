# !/usr/bin/python
# -*- coding:utf-8 -*-

import json
import traceback
from io import BytesIO
from urllib.parse import quote

from db import STATUS_MEMBER_SOURCE_ACTIVE
from db.models import AdministrativeDivision, GameMemberSource, Member
from enums import PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT
from logger import log_utils
from motorengine import ASC
from motorengine.stages import MatchStage, SortStage
from motorengine.stages.group_stage import GroupStage
from motorengine.stages.project_stage import ProjectStage
from tornado.web import url
from web import BaseHandler, decorators
from xlsxwriter import Workbook
from .utils import parse_condition

logger = log_utils.get_logging()


def adjust_source(source_dict):
    """
    调整来源
    fix: http://code.wenjuan.com/WolvesAU/CRSPN/issues/10
    fix: http://code.wenjuan.com/WolvesAU/CRSPN/issues/13
    :param source_dict:
    :return:
    """
    if '2' in source_dict:
        source_dict.pop('2')
    if '1' in source_dict:
        source_dict.pop('1')
    if '6' in source_dict:
        source_dict.pop('6')
    source_dict['126'] = '调查扫码'

    direct_scan = ['2', '3', 'CA755167DEA9AA89650D11C10FAA5413', '160631F26D00F7A2DC56DAE2A0C4AF12',
                   'F742E0C7CA5F7E175844478D74484C29']
    for code in direct_scan:
        if code in source_dict:
            source_dict.pop(code)
    source_dict['3'] = '直接扫码'

    sort_list = ['126', '3', '4', '5']
    sort_dict = {}
    for k in sort_list:
        sort_dict[k] = source_dict.pop(k)

    sort_dict.update(source_dict)
    return sort_dict


class ReportMemberSourceStatisticsHandler(BaseHandler):
    """用户来源统计"""

    @decorators.render_template('backoffice/reports/member_source_statistics.html')
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

        source_list = await GameMemberSource.find({'status': STATUS_MEMBER_SOURCE_ACTIVE}).sort('code').to_list(None)
        source_dict = {source.code: source.title for source in source_list}
        # fix: http://code.wenjuan.com/WolvesAU/CRSPN/issues/13
        source_dict = adjust_source(source_dict)

        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0, 'line': None}
        category = self.get_argument('category')
        condition = self.get_argument('condition_value')
        x_axis = self.get_argument('xAxis', '')

        if not category:
            member_list = await Member.aggregate(
                stage_list=[GroupStage('source', sum={'$sum': 1})]).to_list(None)
            member_source = {m.id: m.sum for m in member_list}

            # fix: 特殊处理，将旧版线上数据与扫码数据合并
            # 详见： http://code.wenjuan.com/WolvesAU/CRSPN/issues/10
            # 最新定制：调查扫码(线上扫码-6、线下扫码-1)
            member_source['126'] = member_source.get('1', 0) + member_source.get('6', 0)
            # 直接扫码
            member_source['direct_scan'] = member_source.get('2', 0) + \
                                           member_source.get('CA755167DEA9AA89650D11C10FAA5413', 0) + \
                                           member_source.get('160631F26D00F7A2DC56DAE2A0C4AF12', 0) + \
                                           member_source.get('F742E0C7CA5F7E175844478D74484C29', 0)

            source_list = await GameMemberSource.find({'status': STATUS_MEMBER_SOURCE_ACTIVE}).to_list(None)
            source_dict = {source.code: source.title for source in source_list}
            source_dict = adjust_source(source_dict)

            r_dict = {
                'code': 1,
                'pie': {
                    'legendData': [v for _, v in source_dict.items()],
                    'seriesData': [{'name': name, 'value': member_source.get(code)} for code, name in
                                   source_dict.items()]
                }
            }

            return r_dict

        try:
            # fix: 特殊处理，将旧版线上数据与扫码数据合并
            # 详见： http://code.wenjuan.com/WolvesAU/CRSPN/issues/10
            source_match = {'source': category}
            if category == '126':
                source_match = {'source': {'$in': list('16')}}
            elif category == '3':
                source_match = {
                    'source': {'$in': ['2', '3', 'CA755167DEA9AA89650D11C10FAA5413', '160631F26D00F7A2DC56DAE2A0C4AF12',
                                       'F742E0C7CA5F7E175844478D74484C29']}}

            member_list = await Member.aggregate([ProjectStage(**{'_id': '$id',
                                                                  'created_dt':
                                                                      {"$dateToString": {"format": "%Y-%m-%d",
                                                                                         "date": "$created_dt"}},
                                                                  'source': '$source',
                                                                  'province_code': '$province_code',
                                                                  'city_code': '$city_code',
                                                                  'sex': '$sex',
                                                                  'age': '$age_group',
                                                                  'education': '$education'}),
                                                  MatchStage(parse_condition(condition)),
                                                  MatchStage(source_match),
                                                  GroupStage('created_dt', sum={'$sum': 1}),
                                                  SortStage([('_id', ASC)]), ]).to_list(None)
            if not x_axis:
                x_axis_data = [m.id for m in member_list]
                series_data = [m.sum for m in member_list]
            else:
                x_axis_data = json.loads(x_axis)
                member_id_map = {m.id: m for m in member_list}
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


class ReportLineChartExportExcelHandler(BaseHandler):
    """
    数据导出模块
    """

    @decorators.permission_required(PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT)
    async def get(self):
        """
        :return:
        """
        r_dict = {'code': 0}
        chart_name = self.get_argument('chart_name', '')
        x_axis_y_axis_name = self.get_argument('x_axis_y_axis_name', '')
        x_axis_y_axis_name = ' ' * 10 + x_axis_y_axis_name.replace('-', '\n')
        data = self.get_argument('data', '')

        if not chart_name or not data:
            return r_dict

        try:
            output = BytesIO()
            workbook = Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet(name=chart_name)
            format_diag = workbook.add_format(
                {'diag_type': 2, 'align': 'center', 'valign': 'vcenter', 'border': 1})  # 单元格对角线
            title_format = workbook.add_format({'font_size': 12, 'bold': '1', 'valign': 'vcenter', 'align': 'center',
                                                'font_name': 'Microsoft YaHei', 'border': 1})
            data_format = workbook.add_format(
                {'valign': 'vcenter', 'align': 'left', 'font_name': 'Microsoft YaHei', 'border': 1})

            data = json.loads(data)
            xAxis = data.get('xAxis', [])
            series = data.get('series', {})
            worksheet.merge_range(0, 0, 0, len(xAxis), chart_name, cell_format=title_format)
            worksheet.write_string(1, 0, x_axis_y_axis_name, cell_format=format_diag)
            #  活动报表正确率的横座标是列表里面是字典,需要把字典里面的value拿出来
            race_report_accuracy = []
            if isinstance(xAxis[0], dict):
                for name in xAxis:
                    race_report_accuracy.append(list(name.values())[0])
            if race_report_accuracy:
                worksheet.write_row(1, 1, race_report_accuracy, cell_format=data_format)
            else:
                worksheet.write_row(1, 1, xAxis, cell_format=data_format)
            transform = 0
            if race_report_accuracy:
                transform = 1
            for index, key in enumerate(series):
                worksheet.write_string(2 + index, 0, key, data_format)
                worksheet.write_row(2 + index, 1, save_two_bit(series[key], transform), data_format)
            workbook.close()

            self.set_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.set_header('Content-Disposition',
                            "attachment;filename*=utf-8''{}.xlsx".format(quote(chart_name.encode('utf-8'))))
            self.write(output.getvalue())
            self.finish()
        except Exception:
            logger.error(traceback.format_exc())


class RaceReportExportExcelHandler(BaseHandler):
    """
    柱状图数据导出模块
    """

    @decorators.permission_required(PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT)
    async def get(self):
        """
        :return:
        """
        r_dict = {'code': 0}
        chart_name = self.get_argument('chart_name', '')
        x_axis_y_axis_name = self.get_argument('x_axis_y_axis_name', '')
        x_axis_y_axis_name = ' ' * 10 + x_axis_y_axis_name.replace('-', '\n')
        data = self.get_argument('data', '')

        if not chart_name or not data:
            return r_dict

        try:
            output = BytesIO()
            workbook = Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet(name=chart_name)
            format_diag = workbook.add_format(
                {'diag_type': 2, 'align': 'center', 'valign': 'vcenter', 'border': 1})  # 单元格对角线
            title_format = workbook.add_format({'font_size': 12, 'bold': '1', 'valign': 'vcenter', 'align': 'center',
                                                'font_name': 'Microsoft YaHei', 'border': 1})
            data_format = workbook.add_format(
                {'valign': 'vcenter', 'align': 'left', 'font_name': 'Microsoft YaHei', 'border': 1})

            data = json.loads(data)
            xAxis = data.get('xAxis', [])
            series = data.get('series', {})
            worksheet.merge_range(0, 0, 0, len(xAxis), chart_name, cell_format=title_format)
            worksheet.write_string(1, 0, x_axis_y_axis_name, cell_format=format_diag)
            worksheet.write_row(1, 1, xAxis, cell_format=data_format)
            data_list = []
            series_data = list(series.values())[0]
            if series_data:
                data_list = [series[:-1] for series in series_data]
            for index, key in enumerate(series):
                worksheet.write_string(2 + index, 0, key, data_format)
                worksheet.write_row(2 + index, 1, data_list, data_format)
            workbook.close()

            self.set_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.set_header('Content-Disposition',
                            "attachment;filename*=utf-8''{}.xlsx".format(quote(chart_name.encode('utf-8'))))
            self.write(output.getvalue())
            self.finish()
        except Exception:
            logger.error(traceback.format_exc())


class ReportLearnOperateExportHandler(BaseHandler):
    """
    用户行为中学习行为导出数据
    """

    @decorators.permission_required(PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT)
    async def get(self):
        """
        :return:
        """
        r_dict = {'code': 0}
        chart_name = self.get_argument('chart_name', '')
        data = self.get_argument('data', '')
        category = self.get_argument('x_axis_y_axis_name', '')
        if not chart_name or not data:
            return r_dict

        try:
            output = BytesIO()
            workbook = Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet(name=chart_name)
            title_format = workbook.add_format({'font_size': 12, 'bold': '1', 'valign': 'vcenter', 'align': 'center',
                                                'font_name': 'Microsoft YaHei', 'border': 1})
            data_format = workbook.add_format(
                {'valign': 'vcenter', 'align': 'center', 'font_name': 'Microsoft YaHei', 'border': 1})
            data = json.loads(data)
            xAxis = data.get('xAxis', [])
            series = data.get('series', {})
            condition_name_list = list(series.keys())
            wrong_count_data_list = list(series.values())
            study_count = [list(data.values())[0] for data in xAxis]
            worksheet.merge_range(0, 0, 0, len(xAxis), chart_name, cell_format=title_format)
            worksheet.write_string(1, 0, '筛选条件', cell_format=title_format)
            worksheet.write_string(1, 1, category, cell_format=title_format)

            for index, condition_name in enumerate(condition_name_list):
                if index == 0:
                    worksheet.merge_range(2, 0, 3, 0, condition_name, data_format)
                    for wrong_index, wrong_data in enumerate(wrong_count_data_list[index]):
                        if wrong_index < len(study_count):
                            worksheet.write_string(2, 1 + wrong_index, str(study_count[wrong_index]))
                            worksheet.write_string(3, 1 + wrong_index, wrong_data)

                else:
                    worksheet.merge_range(2 * (index + 1) + index, 0, 2 * (index + 1) + index + 1, 0, condition_name,
                                          data_format)
                    for wrong_index, wrong_data in enumerate(wrong_count_data_list[index]):
                        worksheet.write_string(2 * (index + 1) + index, 1 + wrong_index, str(study_count[wrong_index]))
                        worksheet.write_string(2 * (index + 1) + index + 1, 1 + wrong_index, wrong_data)
            workbook.close()

            self.set_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.set_header('Content-Disposition',
                            "attachment;filename*=utf-8''{}.xlsx".format(quote(chart_name.encode('utf-8'))))
            self.write(output.getvalue())
            self.finish()
        except Exception:
            logger.error(traceback.format_exc())


class ReportMemberSourceExportExcelHandler(BaseHandler):
    """
    导入行为导出excel
    """

    @decorators.permission_required(PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT)
    async def post(self):
        """
        :return:
        """
        r_dict = {'code': 0}
        chart_name = self.get_argument('chart_name', '')
        data = self.get_argument('data', '')

        if not chart_name or not data:
            return r_dict

        try:
            output = BytesIO()
            workbook = Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet(name=chart_name)
            title_format = workbook.add_format({'font_size': 12, 'bold': '1', 'valign': 'vcenter', 'align': 'center',
                                                'font_name': 'Microsoft YaHei', 'border': 1})
            data_format = workbook.add_format(
                {'valign': 'vcenter', 'align': 'center', 'font_name': 'Microsoft YaHei', 'border': 1})

            data = json.loads(data)
            xAxis = data.get('xAxis', [])
            series = data.get('series', {})
            date_list = [list(date.values())[0] for date in xAxis]
            date_list = [date[2:] for date in date_list]
            data_list = list(series.values())
            condition_name_list = list(series.keys())
            worksheet.merge_range(0, 0, 0, len(xAxis), chart_name, cell_format=title_format)
            worksheet.write_string(1, 0, '筛选条件', cell_format=title_format)
            worksheet.write_string(1, 0, '日期', cell_format=title_format)
            for index, condition_name in enumerate(condition_name_list):
                if index == 0:
                    worksheet.merge_range(2, 0, 3, 0, condition_name, data_format)
                    for wrong_index, data in enumerate(data_list[index]):
                        if wrong_index < len(date_list):
                            worksheet.write_string(2, 1 + wrong_index, date_list[wrong_index])
                            worksheet.write_string(3, 1 + wrong_index, str(data))

                else:
                    worksheet.merge_range(2 * (index + 1) + index, 0, 2 * (index + 1) + index + 1, 0, condition_name,
                                          data_format)
                    for wrong_index, data in enumerate(data_list[index]):
                        worksheet.write_string(2 * (index + 1) + index, 1 + wrong_index, str(date_list[wrong_index]))
                        worksheet.write_string(2 * (index + 1) + index + 1, 1 + wrong_index, str(data))
            workbook.close()
            self.set_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.set_header('Content-Disposition',
                            "attachment;filename*=utf-8''{}.xlsx".format(quote(chart_name.encode('utf-8'))))
            self.write(output.getvalue())
            self.finish()
        except Exception:
            logger.error(traceback.format_exc())


def save_two_bit(accuracy_data_list, transform=1):
    """
    把带有百分号的字符串保存成两位小数
    :param accuracy_data_list:
    :param transform
    :return:
    """
    if transform:
        data_list = []
        for accuracy_data in accuracy_data_list:
            if isinstance(accuracy_data, str):
                accuracy_data = str(round(float(accuracy_data[:-1]), 2)) + "%"
                data_list.append(accuracy_data)
    else:
        data_list = accuracy_data_list
    return data_list


URL_MAPPING_LIST = [
    url(r'/backoffice/reports/member/source/statistics/', ReportMemberSourceStatisticsHandler,
        name='backoffice_reports_member_source_statistics'),
    url(r'/backoffice/reports/line_chart/export/excel/', ReportLineChartExportExcelHandler,
        name='backoffice_reports_line_chart_export_excel'),
    url(r'/backoffice/race/reports/export/excel/', RaceReportExportExcelHandler,
        name='backoffice_race_reports__export_excel'),
    url(r'/backoffice/reports/learn/operate/export/excel/', ReportLearnOperateExportHandler,
        name='backoffice_reports_learn_operate_export_excel'),
    url(r'/backoffice/reports/member/source/export/excel/', ReportMemberSourceExportExcelHandler,
        name='backoffice_reports_member_source_export_excel'),
]
