import traceback
from io import BytesIO
from urllib.parse import quote

from tornado.web import url
from xlsxwriter import Workbook

from enums import PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT
from logger import log_utils
from web import BaseHandler, decorators, json

logger = log_utils.get_logging()


class ReportStudyEffectsExportExcelHandler(BaseHandler):
    """
    数据导出模块
    """

    @decorators.permission_required(PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        """
        :return:
        """
        #  9个报表的所有数据的字典
        data = self.get_argument('data', '')
        chart_type = self.get_argument('chart_type', '')
        if data:
            data = json.loads(data)
        data_list = data.get('series')
        if data_list and len(data_list) > 9:
            data_list = data_list[:9]
        chart_name_list = self.get_argument('chart_name_list', '')
        if chart_name_list:
            chart_name_list = json.loads(chart_name_list)
        try:
            output = BytesIO()
            workbook = Workbook(output, {'in_memory': True})
            if data_list and chart_name_list:
                if chart_type == '1':
                    chart_type = '自然日'
                else:
                    chart_type = '学习日'
                #  遍历拿到的报表名称和报表对应的数据
                chart_name_list = chart_name_list
                for chart_data, chart_name in zip(data_list, chart_name_list):
                    worksheet = workbook.add_worksheet(name=chart_name + '(' + chart_type + ')')
                    format_diag = workbook.add_format(
                        {'diag_type': 2, 'align': 'center', 'valign': 'vcenter', 'border': 1})  # 单元格对角线
                    title_format = workbook.add_format({'font_size': 12, 'bold': '1', 'valign': 'vcenter', 'align': 'center',
                                                        'font_name': 'Microsoft YaHei', 'border': 1})
                    data_format = workbook.add_format(
                        {'valign': 'vcenter', 'align': 'left', 'font_name': 'Microsoft YaHei', 'border': 1})
                    # 每个报表的所有的的数据
                    all_data_list = list(chart_data.values())
                    #  没有筛选条件的数据
                    total_data_list = []
                    #  没有筛选条件的日期和正确率数据
                    date_list = []
                    accuracy_list = []
                    #  有筛选条件的报表日期数据和正确率数据
                    if all_data_list:
                        total_data_list = all_data_list[0]
                    for data in total_data_list:
                        date_list.append(data[0])
                        accuracy_list.append(data[1] + '%')
                    if chart_type == "自然日":
                        date_list = deal_with_data(date_list)
                    #  报表中存在筛选条件的情况下
                    total_choice_date_list = []
                    total_choice_data_list = []
                    if len(all_data_list) > 1:
                        for choice_data in all_data_list[1:]:
                            #  有筛选条件的报表日期数据和正确率数据
                            choice_condition_date = []
                            choice_condition_data = []
                            for index, data in enumerate(choice_data):
                                choice_condition_date.append(data[0])
                                choice_condition_data.append(data[1] + '%')
                            if chart_type == "自然日":
                                choice_condition_date = deal_with_data(choice_condition_date)
                            total_choice_date_list.append(choice_condition_date)
                            total_choice_data_list.append(choice_condition_data)
                    for index, choice_condition in enumerate(list(chart_data.keys())):
                        if index == 0:
                            worksheet.merge_range(0, 0, 0, 1, chart_name + '(' + chart_type + ')', cell_format=title_format)
                            worksheet.write_string(1, 0, '筛选条件', cell_format=title_format)
                            worksheet.write_string(1, 2, '日期', cell_format=title_format)
                            worksheet.merge_range(2, 0, 3, 1, choice_condition + '%', cell_format=title_format)
                            for data_index, date in enumerate(date_list):
                                worksheet.write_string(2, 1 + data_index + 1, date, data_format)
                                worksheet.write_string(3, 1 + data_index + 1, accuracy_list[data_index], data_format)
                        else:
                            worksheet.merge_range(2 * (index + 1) + index, 0, 2 * (index + 1) + 1 + index, 1, choice_condition, cell_format=title_format)
                            for choice_date_index, choice_date in enumerate(total_choice_date_list[index-1]):

                                worksheet.write_string(2 * (index + 1) + index, 1 + choice_date_index + 1, choice_date, data_format)
                                worksheet.write_string(2 * (index + 1) + 1 + index, 1 + choice_date_index + 1, total_choice_data_list[index-1][choice_date_index], data_format)
                workbook.close()
                self.set_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                self.set_header('Content-Disposition',
                                "attachment;filename*=utf-8''{}.xlsx".format(quote(('科普所学习效果报表' + '(' + chart_type + ')').encode('utf-8'))))
                self.write(output.getvalue())
                self.finish()
        except Exception:
            logger.error(traceback.format_exc())


def deal_with_data(date_list):
    """
    把20180905转换成18/09/05
    :param date_list:
    :return:
    """
    date_list = [date[2:4] + '/' + date[4:6] + '/' + date[6:] for date in date_list if date]
    return date_list


URL_MAPPING_LIST = [
    url(r'/backoffice/reports/study/effects/export/excel/', ReportStudyEffectsExportExcelHandler,
        name='backoffice_reports_study_effects_export_excel')
]