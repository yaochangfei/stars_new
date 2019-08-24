import copy
import datetime
import json
import traceback
from io import BytesIO
from urllib.parse import quote

from tornado.web import url
from xlsxwriter import Workbook

from actions.backoffice.download_utils import deal_with_data_excel
from commons.common_utils import datetime2str
from db import STATUS_USER_ACTIVE
from db.model_utils import do_different_administrative_division2
from db.models import AdministrativeDivision, MemberLearningDayStatistics, MemberSubjectStatistics, Member
from enums import PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT
from logger import log_utils
from motorengine import ASC
from motorengine.stages import MatchStage, LookupStage, SortStage
from motorengine.stages.add_fields_stage import AddFieldsStage
from motorengine.stages.group_stage import GroupStage
from tasks.utils import get_yesterday
from web import BaseHandler, decorators

logger = log_utils.get_logging()


class ReportLearningSituationExportExcelHandler(BaseHandler):
    """
    学习近况数据导出模块
    """

    @decorators.permission_required(PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        """
        :return:
        """
        time = datetime.datetime.now()
        export_time = datetime2str(time, date_format='%Y-%m-%d %H:%M:%S')
        order = self.get_argument('order', '')
        chart_name = self.get_argument('chart_name', '')
        #  答题活跃度的数据
        data_dict = self.get_argument('data', '')
        data_list = []
        condition_title_list = []
        #  没有筛选条件的总体活跃度
        if data_dict:
            data_dict = json.loads(data_dict)
            condition_title_list = list(data_dict.keys())
            data_list = list(data_dict.values())
            #  有筛选条件的数据
            if '总体活跃度' in condition_title_list:
                position = condition_title_list.index('总体活跃度')
            else:
                position = data_list.index(max(sum(data_list)))
            if len(data_list) > position:
                condition_title_list.remove(condition_title_list[position])
        # 可管理的省份名称
        manage_region_title_list = []
        manage_region_code_list = self.current_user.manage_region_code_list
        if manage_region_code_list:
            for manage_region_code in manage_region_code_list:
                manage_region_province = await AdministrativeDivision.find_one(
                    {'code': manage_region_code, 'record_flag': 1, 'parent_code': None})
                if manage_region_province:
                    manage_region_title_list.append(manage_region_province.title)
                else:
                    manage_region_city = await AdministrativeDivision.find_one(
                        {'code': manage_region_code, 'record_flag': 1})
                    province = await manage_region_city.parent
                    manage_region_title_list.append(province.title)
        try:
            output = BytesIO()
            workbook = Workbook(output, {'in_memory': True})
            title_format = workbook.add_format({'font_size': 12, 'bold': '1', 'valign': 'vcenter', 'align': 'center',
                                                'font_name': 'Microsoft YaHei', 'border': 1})
            data_format = workbook.add_format(
                {'valign': 'vcenter', 'align': 'left', 'font_name': 'Microsoft YaHei', 'border': 1})
            data_center_format = workbook.add_format(
                {'valign': 'vcenter', 'align': 'center', 'font_name': 'Microsoft YaHei', 'border': 1})
            if order == "1" and chart_name:
                pass
            #  公民科学素质学习答题趋势统计
            if order == '2' and chart_name:
                answer_tendency_date = self.get_argument('answer_tendency_date', '')
                answer_tendency_data = self.get_argument('answer_tendency_data', '')
                answer_tendency_data = json.loads(answer_tendency_data)
                answer_tendency_date = json.loads(answer_tendency_date)
                answer_tendency_date = deal_with_data(answer_tendency_date)
                if answer_tendency_date and answer_tendency_data:
                    worksheet = workbook.add_worksheet(name=chart_name)
                    worksheet.merge_range(1, 2, 1, 5, '导出时间' + export_time, cell_format=title_format)
                    worksheet.merge_range(0, 0, 0, 2, chart_name, cell_format=title_format)
                    worksheet.merge_range(1, 0, 1, 1, '筛选条件', cell_format=title_format)
                    worksheet.merge_range(2, 0, 3, 1, '总体答题次数', cell_format=title_format)
                    worksheet.write_string(2, 2, '日期', cell_format=data_format)
                    worksheet.write_string(3, 2, '答题次数', cell_format=data_format)
                    answer_tendency_title = list(answer_tendency_data.keys())
                    answer_data_list = list(answer_tendency_data.values())
                    #  有筛选条件的数据
                    if '总体答题次数' in answer_tendency_title:
                        position = answer_tendency_title.index('总体答题次数')
                    else:
                        position = answer_data_list.index(max(sum(answer_data_list)))
                    if len(answer_data_list) > position:
                        answer_tendency_title.remove(answer_tendency_title[position])
                    for index, date in enumerate(answer_tendency_date):
                        worksheet.write_string(2, 3 + index, date)
                        if '总体答题次数' in list(answer_tendency_data.keys()):
                            worksheet.write_string(3, 3 + index, str(answer_tendency_data['总体答题次数'][index]),
                                                   cell_format=data_center_format)
                        else:
                            max_data_list = max(sum(answer_data_list))
                            worksheet.write_string(3, 2 + order, max_data_list[index - 1],
                                                   cell_format=data_center_format)
                    if answer_tendency_title:
                        #  有筛选条件得数据写入到excel
                        for index, condition_title in enumerate(answer_tendency_title):
                            worksheet.merge_range(2 * (index + 2) + index + 1, 0, 2 * (index + 2) + 2 + index, 1,
                                                  condition_title, cell_format=title_format)
                            worksheet.write_string(2 * (index + 2) + index + 1, 2, '日期', cell_format=data_format)
                            worksheet.write_string(2 * (index + 2) + index + 2, 2, '答题次数', cell_format=data_format)
                            for condition_index, data in enumerate(answer_tendency_data[condition_title]):
                                worksheet.write_string(2 * (index + 2) + index + 2, 2 + condition_index + 1, str(data),
                                                       cell_format=data_format)
                                worksheet.write_string(2 * (index + 2) + index + 1, 2 + condition_index + 1,
                                                       answer_tendency_date[condition_index],
                                                       cell_format=data_format)
            if order == '3' and chart_name and data_dict:
                #  活跃度的导出excel
                worksheet = workbook.add_worksheet(name=chart_name)
                for order in range(1, 31):
                    worksheet.write_string(2, 2 + order, str(order), cell_format=data_center_format)
                    if '总体活跃度' in list(data_dict.keys()):
                        worksheet.write_string(3, 2 + order, data_dict['总体活跃度'][order - 1] + '%',
                                               cell_format=data_center_format)
                    else:
                        max_data_list = max(sum(data_list))
                        worksheet.write_string(3, 2 + order, max_data_list[order - 1] + '%',
                                               cell_format=data_center_format)
                worksheet.merge_range(1, 2, 1, 5, '导出时间' + export_time, cell_format=title_format)
                worksheet.merge_range(0, 0, 0, 2, chart_name, cell_format=title_format)
                worksheet.merge_range(1, 0, 1, 1, '筛选条件', cell_format=title_format)
                worksheet.merge_range(2, 0, 3, 1, '总体活跃度(%)', cell_format=title_format)
                worksheet.write_string(2, 2, '活跃天数', cell_format=data_format)
                worksheet.write_string(3, 2, '活跃度(%)', cell_format=data_format)
                if condition_title_list:
                    #  有筛选条件得数据写入到excel
                    for index, condition_title in enumerate(condition_title_list):
                        worksheet.merge_range(2 * (index + 2) + index + 1, 0, 2 * (index + 2) + 2 + index, 1,
                                              condition_title, cell_format=title_format)
                        worksheet.write_string(2 * (index + 2) + index + 1, 2, '活跃天数', cell_format=data_format)
                        for order in range(1, 31):
                            worksheet.write_string(2 * (index + 2) + index + 1, 2 + order, str(order),
                                                   cell_format=data_format)
                        worksheet.write_string(2 * (index + 2) + index + 2, 2, '活跃度(%)', cell_format=data_format)
                        for condition_index, data in enumerate(data_dict[condition_title]):
                            worksheet.write_string(2 * (index + 2) + index + 2, 2 + condition_index + 1, data,
                                                   cell_format=data_format)
            #  每日参与top5的导出数据
            if order == '4' and chart_name:
                #  每日参与top_5的数据
                stat_category = self.get_argument('stat_category', '')
                top_five_data_list = self.get_argument('top_five_data', '')
                if top_five_data_list:
                    top_five_data_list = json.loads(top_five_data_list)
                date_list = self.get_argument('date', '')
                if date_list:
                    date_list = json.loads(date_list)
                date_list = deal_with_data(date_list)
                if stat_category and top_five_data_list and date_list:
                    data_series_dict, province_and_city_dict = deal_with_data_excel(date_list, top_five_data_list)
                    #  {'江苏': ['南京', '苏州‘], '浙江':['杭州']}
                    total_data_dict = {}
                    #  某个省下面的所有的市 报表中有数据的市
                    city_title_list = []
                    #  报表中省的列表
                    province_title_list = []
                    #  省和市的列表
                    total_title = []
                    show_name_list = []
                    show_data_list = []
                    #  需要添加undefined的省份
                    need_append_undifend_province_list = []
                    for top_five_data in top_five_data_list:
                        temple_data = []
                        temple_name = []
                        for index, data in enumerate(top_five_data):
                            total_title.append(data['name'])
                            if data['name'] and data['value']:
                                temple_name.append({date_list[index]: data['name']})
                                temple_data.append({date_list[index]: data['value']})
                        show_name_list.append(temple_name)
                        show_data_list.append(temple_data)
                    total_title = [title for title in total_title if title]
                    for total in total_title:
                        if ' ' in total:
                            province_title_list.append(total.split(' ')[0])
                            city_title_list.append(total.split(' ')[1])
                            if total.split(' ')[1] == 'undefined':
                                need_append_undifend_province_list.append(total.split(' ')[0])
                    province_title_list = list(set(province_title_list))
                    city_title_list = list(set([city for city in city_title_list if city]))
                    for province_title in province_title_list:
                        total_data_dict[province_title] = city_title_list
                        province = await AdministrativeDivision.find_one({'title': province_title, 'parent_code': None})
                        if province:
                            belong_provice_city_title_list = await AdministrativeDivision.distinct('title', {
                                'parent_code': province.code})
                            total_data_dict[province_title] = list(
                                set(city_title_list) & set(belong_provice_city_title_list))
                            total_data_dict[province_title] = list(
                                set(city_title_list) & set(belong_provice_city_title_list))
                    #  各个省的市的个数
                    length_list = []
                    for index, city_title in enumerate(list(total_data_dict.values())):
                        if list(total_data_dict.keys())[index] in need_append_undifend_province_list:
                            total_data_dict.get(list(total_data_dict.keys())[index]).append('undefined')
                    for index, city_title in enumerate(list(total_data_dict.values())):
                        if city_title:
                            length_list.append(len(city_title))
                    province_length = sum(length_list) + len(list(total_data_dict.values()))
                    if province_length == 0:
                        province_length = 10
                    worksheet = workbook.add_worksheet(name=chart_name + '(' + stat_category + ')')
                    worksheet.merge_range(0, 0, province_length, 0, '每日参与' + stat_category, cell_format=data_format)
                    worksheet.merge_range(1, 1, province_length, 1, '导出时间: ' + export_time, cell_format=data_format)
                    worksheet.merge_range(0, 2, 0, 4, '日期', cell_format=data_center_format)
                    for index, date in enumerate(date_list):
                        worksheet.write_string(0, 5 + index, date, cell_format=data_format)
                    worksheet.merge_range(1, 2, province_length, 2, '省份', cell_format=data_center_format)
                    city_map = {}
                    province_map = {}
                    if total_data_dict:
                        choice_city_title_list = list(total_data_dict.values())
                        for index, data in enumerate(choice_city_title_list):
                            if index == 0:
                                worksheet.merge_range(1, 3, 1 + len(data), 3, list(total_data_dict.keys())[index],
                                                      cell_format=data_center_format)
                            else:
                                worksheet.merge_range(1 + sum(length_list[:index]) + index, 3,
                                                      sum(length_list[:index + 1]) + index + 1, 3,
                                                      list(total_data_dict.keys())[index],
                                                      cell_format=data_center_format)

                            if index == 0:
                                for city_index, city in enumerate(data):
                                    if city == 'undefined':
                                        city = '_'
                                    worksheet.write_string(1, 4, list(total_data_dict.keys())[index],
                                                           cell_format=data_center_format)
                                    worksheet.write_string(2 + city_index, 4, city, cell_format=data_center_format)
                                    worksheet.write_string(1, 5, '6666', cell_format=data_format)
                                    city_map[city] = 2 + city_index
                                    province_map[list(total_data_dict.keys())[index]] = 1
                                    Position(city, 2 + city_index, 4)
                                    Position(list(total_data_dict.keys())[index], 1, 4)
                            else:
                                for city_index, city in enumerate(data):
                                    if city == 'undefined':
                                        city = '_'
                                    worksheet.write_string(sum(length_list[:index]) + index + 1, 4,
                                                           list(total_data_dict.keys())[index],
                                                           cell_format=data_center_format)
                                    worksheet.write_string(sum(length_list[:index]) + index + 2 + city_index, 4, city,
                                                           cell_format=data_center_format)
                                    city_map[city] = sum(length_list[:index]) + 2 + index + city_index
                                    province_map[list(total_data_dict.keys())[index]] = sum(
                                        length_list[:index]) + index + 1
                                    Position(city, sum(length_list[:index]) + 2 + index + city_index, 4)
                                    Position(list(total_data_dict.keys())[index], sum(length_list[:index]) + index + 1,
                                             4)
                        for index, data in enumerate(choice_city_title_list):
                            if index == 0:
                                for key, value in data_series_dict.items():
                                    if key.split(' ')[0] == 'undefined':
                                        position = Position(key.split(' ')[0], city_map['_'], 4)
                                    else:
                                        position = Position(key.split(' ')[0], city_map[key.split(' ')[0]], 4)
                                    if position:
                                        order = date_list.index(key.split(' ')[1])
                                        worksheet.write_number(position.row, 5 + order, int(value))
                            else:
                                for key, value in data_series_dict.items():
                                    if key.split(' ')[0] == 'undefined':
                                        position = Position(key.split(' ')[0], city_map['_'], 4)
                                    else:
                                        position = Position(key.split(' ')[0], city_map[key.split(' ')[0]], 4)
                                    if position:
                                        order = date_list.index(key.split(' ')[1])
                                        worksheet.write_number(position.row, 5 + order, int(value))

                        for order, date in enumerate(date_list):
                            for index, value in enumerate(list(province_map.values())):
                                if index != len(list(province_map.values())) - 1:
                                    first = value + 2
                                    end = list(province_map.values())[index + 1]
                                else:
                                    first = list(province_map.values())[index] + 2
                                    end = province_length + 1
                                col = 5 + order
                                col = convert(col)
                                first = col + str(first)
                                end = col + str(end)
                                worksheet.write_formula(value, 5 + order, '=SUM(' + first + ':' + end + ')')
            #  学习近况的导出数据
            if order == '1' and chart_name:
                #  取前一天凌晨12点之前的数据
                time_match = get_yesterday()
                time_match_stage = MatchStage({'updated_dt': {'$lt': time_match}})
                province_code_list, city_code_list, _ = await do_different_administrative_division2(
                    self.current_user.manage_region_code_list)
                month_stage_list = []
                member_stage_list = []
                accuracy_stage_list = []
                if province_code_list:
                    month_stage_list.append(MatchStage({'province_code': {'$in': province_code_list}}))
                    member_stage_list.append(MatchStage({'province_code': {'$in': province_code_list}}))
                    accuracy_stage_list.append(MatchStage({'province_code': {'$in': province_code_list}}))
                if city_code_list:
                    month_stage_list.append(MatchStage({'city_code': {'$in': city_code_list}}))
                    member_stage_list.append(MatchStage({'city_code': {'$in': city_code_list}}))
                    accuracy_stage_list.append(MatchStage({'city_code': {'$in': city_code_list}}))
                add_fields_stage = AddFieldsStage(t_accuracy={
                    '$cond':
                        {
                            'if': {'$eq': ['$t_total', 0]},
                            'then': 0,
                            'else':
                                {
                                    '$divide': ['$t_correct', '$t_total']
                                }
                        }
                })
                member_stage_list.append(MatchStage({'status': STATUS_USER_ACTIVE}))

                month_group_stage = GroupStage({'province_code': '$province_code', 'created_dt': {
                    "$dateToString": {"format": "%Y-%m", "date": "$created_dt"}}}, sum={'$sum': '$learn_times'})
                lookup_stage = LookupStage(AdministrativeDivision, '_id', 'post_code', 'ad_list')
                member_group_stage = GroupStage({'province_code': '$province_code', 'created_dt': {
                    "$dateToString": {"format": "%Y-%m", "date": "$created_dt"}}}, sum={'$sum': 1})
                accuracy_group_stage = GroupStage({'province_code': '$province_code', 'created_dt': {
                    "$dateToString": {"format": "%Y-%m", "date": "$created_dt"}}}, t_total={'$sum': '$total'},
                                                  t_correct={'$sum': '$correct'})
                group_stage = GroupStage('province_code', t_total={'$sum': '$total'}, t_correct={'$sum': '$correct'})
                month_sort_stage = SortStage([('_id.created_dt', ASC)])
                #  次数
                month_stage_list.extend([time_match_stage, month_group_stage, lookup_stage, month_sort_stage])
                #  人数
                member_stage_list.extend([time_match_stage, member_group_stage, lookup_stage, month_sort_stage])
                accuracy_province_stage_list = copy.deepcopy(accuracy_stage_list)
                accuracy_province_stage_list.extend([time_match_stage, group_stage, lookup_stage, add_fields_stage, month_sort_stage])
                #  省和月份共同筛选的正确率
                accuracy_stage_list.extend([time_match_stage, accuracy_group_stage, lookup_stage, add_fields_stage, month_sort_stage])
                #  只有省的正确率
                month_province_list = MemberLearningDayStatistics.aggregate(month_stage_list)

                member_province_list = Member.aggregate(member_stage_list)
                accuracy_province_list = MemberSubjectStatistics.aggregate(accuracy_stage_list)
                total_accuracy = MemberSubjectStatistics.aggregate(accuracy_province_stage_list)
                month_province_dict = {}
                member_province_dict = {}
                accuracy_province_dict = {}
                date_list = []
                province_title_list = []
                province_map = {}
                member_date_list = []
                accuracy_date_list = []
                # 次数
                while await month_province_list.fetch_next:
                    month_province = month_province_list.next_object()
                    if month_province:
                        province_dt = month_province.id if month_province.id else '000000'
                        province = await AdministrativeDivision.find_one(
                            {'code': province_dt.get('province_code'), 'record_flag': 1, 'parent_code': None})
                        if province_dt.get('created_dt') not in date_list:
                            date_list.append(province_dt.get('created_dt'))
                        province_title = ''
                        if province:
                            province_title = province.title
                        province_title_list.append(province_title)
                        province_title_list = list(set(province_title_list))
                        dt = province_dt.get('created_dt')
                        month_province_dict[province_title + ' ' + dt] = month_province.sum
                #  人数
                while await member_province_list.fetch_next:
                    member_province = member_province_list.next_object()
                    if member_province:
                        member_province_id = member_province.id if member_province.id else ''
                        province = await AdministrativeDivision.find_one(
                            {'code': member_province_id.get('province_code'), 'record_flag': 1, 'parent_code': None})
                        province_title = ''
                        if province:
                            province_title = province.title
                        dt = member_province_id.get('created_dt')
                        if member_province_id.get('created_dt') not in member_date_list:
                            member_date_list.append(member_province_id.get('created_dt'))
                        member_province_dict[province_title + ' ' + dt] = member_province.sum
                #  正确率
                while await accuracy_province_list.fetch_next:
                    accuracy_province = accuracy_province_list.next_object()
                    if accuracy_province:
                        accuracy_province_id = accuracy_province.id if accuracy_province.id else ''
                        province = await AdministrativeDivision.find_one(
                            {'code': accuracy_province_id.get('province_code'), 'record_flag': 1, 'parent_code': None})
                        province_title = ''
                        if province:
                            province_title = province.title
                        dt = accuracy_province_id.get('created_dt')
                        if accuracy_province_id.get('created_dt') not in accuracy_date_list:
                            accuracy_date_list.append(accuracy_province_id.get('created_dt'))
                        if accuracy_province.t_total == 0:
                            accuracy_province_dict[province_title + ' ' + dt] = 0
                        else:
                            accuracy_province_dict[province_title + ' ' + dt] = (
                                                                                            accuracy_province.t_correct / accuracy_province.t_total) * 100
                province_dict = {}
                #  总的题目
                total_quantity_list = []
                #  总的答对题目
                correct_quantity_list = []
                #  总的正确率
                while await total_accuracy.fetch_next:
                    province_stat = total_accuracy.next_object()
                    if province_stat:
                        province_code = province_stat.id if province_stat.id else '000000'
                        total = province_stat.t_total if province_stat.t_total else 0
                        correct = province_stat.t_correct if province_stat.t_correct else 0
                        province = await AdministrativeDivision.find_one(
                            {'code': province_code, 'record_flag': 1, 'parent_code': None})
                        province_title = ''
                        if province:
                            province_title = province.title
                        province_dict[province_title] = round(correct / total * 100 if total > 0 else 0, 2)
                        total_quantity_list.append(total)
                        correct_quantity_list.append(correct)
                #  次数的sheet
                print(date_list)
                worksheet = workbook.add_worksheet(name='次数')
                worksheet.merge_range(0, 0, 0, len(date_list) + 1, '公民参与科学素质学习状况', cell_format=title_format)
                worksheet.write_string(1, 0, '已累计次数', cell_format=data_center_format)
                worksheet.merge_range(1, 2, 1, len(date_list) + 1, '导出时间:' + export_time,
                                      cell_format=data_center_format)
                worksheet.merge_range(2, 0, 3, 0, '省份', cell_format=data_center_format)
                worksheet.merge_range(2, 1, 3, 1, '人数汇总(人)', cell_format=data_center_format)
                worksheet.merge_range(2, 2, 2, 6, '每月新增人数(人)', cell_format=data_center_format)
                insert_excel(date_list, worksheet, data_center_format, province_title_list, province_map,
                             month_province_dict)
                #  人数的sheet
                worksheet = workbook.add_worksheet(name='人数')
                worksheet.merge_range(0, 0, 0, len(member_date_list) + 1, '公民参与科学素质学习状况', cell_format=title_format)
                worksheet.write_string(1, 0, '已累计人数', cell_format=data_center_format)
                worksheet.merge_range(1, 2, 1, len(member_date_list) + 1, '导出时间：' + export_time,
                                      cell_format=data_center_format)
                worksheet.merge_range(2, 0, 3, 0, '省份', cell_format=data_center_format)
                worksheet.merge_range(2, 1, 3, 1, '人数汇总(人/次)', cell_format=data_center_format)
                worksheet.merge_range(2, 2, 2, 6, '每月新增人数(人/次)', cell_format=data_center_format)
                insert_excel(member_date_list, worksheet, data_center_format, province_title_list, province_map,
                             member_province_dict)
                #  正确率的sheet
                worksheet = workbook.add_worksheet(name='正确率')
                total_province_accuracy = round(sum(correct_quantity_list) / sum(total_quantity_list) * 100, 2)
                worksheet.merge_range(0, 0, 0, len(date_list) + 1, '公民参与科学素质学习状况', cell_format=title_format)
                worksheet.merge_range(1, 0, 1, 1, '总体正确率' + str(total_province_accuracy) + '%',
                                      cell_format=data_center_format)
                worksheet.merge_range(1, 2, 1, len(date_list) + 1, '导出时间:' + export_time,
                                      cell_format=data_center_format)
                worksheet.merge_range(2, 0, 3, 0, '省份', cell_format=data_center_format)
                worksheet.merge_range(2, 1, 3, 1, '正确率', cell_format=data_center_format)
                worksheet.merge_range(2, 2, 2, 6, '每月正确率波动(%)', cell_format=data_center_format)
                for index, date in enumerate(accuracy_date_list):
                    worksheet.write_string(3, 2 + index, date, cell_format=data_center_format)
                for index, province_title in enumerate(province_title_list):
                    worksheet.write_string(4 + index, 0, province_title, cell_format=data_center_format)
                    worksheet.write_string(4 + index, 1, str(province_dict[province_title]),
                                           cell_format=data_center_format)
                    province_map[province_title] = 4 + index
                for month_province, value in accuracy_province_dict.items():
                    value = round(value, 2)
                    position = Position(month_province.split(' ')[0], province_map[month_province.split(' ')[0]], 0)
                    order = accuracy_date_list.index(month_province.split(' ')[1])
                    worksheet.write_string(position.row, 2 + order, str(value))
            workbook.close()
            self.set_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.set_header('Content-Disposition',
                            "attachment;filename*=utf-8''{}.xlsx".format(quote(chart_name.encode('utf-8'))))
            self.write(output.getvalue())
            self.finish()
        except Exception:
            logger.error(traceback.format_exc())


class Position(object):
    """
    各个市在excel的位置
    """

    def __init__(self, name, row, col):
        self.row = row
        self.col = col
        self.name = name


def deal_with_data(date_list):
    """
    把20180905转换成18/09/05
    :param date_list:
    :return:
    """
    date_list = [date[2:4] + '/' + date[4:6] + '/' + date[6:] for date in date_list if date]
    return date_list


def convert(num: int = 0):
    _map = {i: chr(ord('A') + i) for i in range(26)}
    if num == 0:
        return _map[num]

    ret_list = list()
    while True:
        if num == 0:
            break
        num, y = divmod(num, 26)
        ret_list.append(y)

    ret_list.reverse()
    temp_list = [r - 1 for r in ret_list[0:-1]]
    temp_list.append(ret_list[-1])
    return ''.join(map(lambda x: _map[x], temp_list))


async def get_month_data(obj):
    """
    得到每个月每个省份的数据
    :param obj:
    :return:
    """
    province_dt = obj.id if obj.id else '000000'
    province = await AdministrativeDivision.find_one(
        {'code': province_dt.get('province_code'), 'record_flag': 1, 'parent_code': None})
    province_title = ''
    if province:
        province_title = province.title
    dt = province_dt.get('created_dt')
    return province_title, dt


def insert_excel(date_list, worksheet, data_center_format, province_title_list, province_map, data_dict):
    """
    将学习近况中每个月每个省的数据插入到excel中
    :return:
    """
    for index, date in enumerate(date_list):
        worksheet.write_string(3, 2 + index, date, cell_format=data_center_format)
    for index, province_title in enumerate(province_title_list):
        worksheet.write_string(4 + index, 0, province_title, cell_format=data_center_format)
        first_num = 2
        first = convert(first_num) + str(5 + index)
        end_num = len(date_list) + 1
        end = convert(end_num) + str(5 + index)
        worksheet.write_formula(4 + index, 1, '=SUM(' + first + ':' + end + ')')

        province_map[province_title] = 4 + index
    for month_province, value in data_dict.items():
        position = Position(month_province.split(' ')[0], province_map[month_province.split(' ')[0]], 0)
        order = date_list.index(month_province.split(' ')[1])
        worksheet.write_number(position.row, 2 + order, int(value))
    total_end = 'B' + str(4 + len(province_title_list))
    worksheet.write_formula(1, 1, '=SUM(B5:' + total_end + ')')


URL_MAPPING_LIST = [
    url(r'/backoffice/reports/learning/situation/export/excel/', ReportLearningSituationExportExcelHandler,
        name='backoffice_reports_learning_situation_export_excel')
]
