import datetime
import json
import traceback
from io import BytesIO
from urllib.parse import quote

from tornado.web import url
from xlsxwriter import Workbook

from actions.v_common import logger
from commons.common_utils import datetime2str
from enums import PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT
from web import BaseHandler, decorators


class ReportStudyAnalysisExportExcelHandler(BaseHandler):
    """
    题库参数数据导出模块
    """

    @decorators.permission_required(PERMISSION_TYPE_REPORT_EXECUTIVE_DIRECT_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        order = self.get_argument('order', '')
        chart_name = self.get_argument('chart_name', '')
        time = datetime.datetime.now()
        export_time = datetime2str(time, date_format='%Y-%m-%d %H:%M:%S')
        try:
            output = BytesIO()
            workbook = Workbook(output, {'in_memory': True})
            title_format = workbook.add_format({'font_size': 12, 'bold': '1', 'valign': 'vcenter', 'align': 'center',
                                                'font_name': 'Microsoft YaHei', 'border': 1})
            data_format = workbook.add_format(
                {'valign': 'vcenter', 'align': 'left', 'font_name': 'Microsoft YaHei', 'border': 1})
            data_center_format = workbook.add_format(
                {'valign': 'vcenter', 'align': 'center', 'font_name': 'Microsoft YaHei', 'border': 1})
            #  公民素质答题数量
            if order == "1" and chart_name:
                #  答题正确分布的数据字典
                subject_quantity_data_dict = self.get_argument('answer_subject_quantity_data', '')
                # 横坐标题目数量的列表
                answer_subject_xAxis_list = self.get_argument('answer_subject_xAxis_list', '')
                if subject_quantity_data_dict and answer_subject_xAxis_list:
                    worksheet = workbook.add_worksheet(name=chart_name)
                    worksheet.merge_range(1, 2, 1, 10, '导出时间' + export_time, cell_format=title_format)
                    worksheet.merge_range(0, 0, 0, 10, chart_name, cell_format=title_format)
                    worksheet.merge_range(1, 0, 1, 1, '筛选条件', cell_format=title_format)
                    worksheet.merge_range(2, 0, 3, 1, '总体答题次数', cell_format=title_format)
                    worksheet.write_string(2, 2, '答对题目数', cell_format=data_format)
                    worksheet.write_string(3, 2, '答对题目分布（%）', cell_format=data_format)
                    subject_quantity_data_dict = json.loads(subject_quantity_data_dict)
                    answer_subject_xAxis_list = json.loads(answer_subject_xAxis_list)
                    subject_quantity_title = list(subject_quantity_data_dict.keys())
                    subject_quantity_title = [subject_quantity for subject_quantity in subject_quantity_title if
                                              subject_quantity]
                    subject_quantity_data = list(subject_quantity_data_dict.values())
                    #  有筛选条件的数据
                    if '全体人群答对题目分布' in subject_quantity_title:
                        position = subject_quantity_title.index('全体人群答对题目分布')
                    else:
                        position = subject_quantity_data.index(max(sum(subject_quantity_data)))
                    if len(subject_quantity_data) > position:
                        subject_quantity_title.remove(subject_quantity_title[position])
                    for index, subject_quantity in enumerate(answer_subject_xAxis_list):
                        worksheet.write_string(2, 3 + index, subject_quantity)
                        if '全体人群答对题目分布' in list(subject_quantity_data_dict.keys()):
                            worksheet.write_string(3, 3 + index, str(subject_quantity_data_dict['全体人群答对题目分布'][index]),
                                                   cell_format=data_center_format)
                        else:
                            max_data_list = max(sum(subject_quantity_data))
                            worksheet.write_string(3, 2 + order, max_data_list[index - 1],
                                                   cell_format=data_center_format)
                    if subject_quantity_title:
                        #  有筛选条件得数据写入到excel
                        for index, condition_title in enumerate(subject_quantity_title):
                            worksheet.merge_range(2 * (index + 2) + index + 1, 0, 2 * (index + 2) + 2 + index, 1,
                                                  condition_title, cell_format=title_format)
                            worksheet.write_string(2 * (index + 2) + index + 1, 2, '答对题目数', cell_format=data_format)
                            worksheet.write_string(2 * (index + 2) + index + 2, 2, '答对题目分布（%）', cell_format=data_format)
                            for condition_index, data in enumerate(subject_quantity_data_dict[condition_title]):
                                worksheet.write_string(2 * (index + 2) + index + 2, 2 + condition_index + 1, str(data),
                                                       cell_format=data_format)
                                worksheet.write_string(2 * (index + 2) + index + 1, 2 + condition_index + 1,
                                                       answer_subject_xAxis_list[condition_index],
                                                       cell_format=data_format)
            #  公民科学素质雷达图
            if order == "2" and chart_name:
                #  公民科学素质雷达图的数据列表
                radar_title_list = self.get_argument('radar_title_list', '')
                # 横坐标题目数量的列表
                radar_data_list = self.get_argument('radar_data_list', '')
                #  雷达图展示的文本
                text_list = self.get_argument('text_list', '')
                if radar_title_list and radar_data_list and text_list:
                    worksheet = workbook.add_worksheet(name=chart_name)
                    worksheet.merge_range(1, 2, 1, 10, '导出时间' + export_time, cell_format=title_format)
                    worksheet.merge_range(0, 0, 0, 10, chart_name, cell_format=title_format)
                    worksheet.merge_range(1, 0, 1, 1, '筛选条件', cell_format=title_format)
                    worksheet.merge_range(2, 0, 3, 1, '全部正确率', cell_format=title_format)
                    worksheet.write_string(2, 2, '学科部落', cell_format=data_format)
                    worksheet.write_string(3, 2, '正确率(%)', cell_format=data_format)
                    radar_title_list = json.loads(radar_title_list)
                    radar_data_list = json.loads(radar_data_list)
                    text_list = json.loads(text_list)
                    first_radar_data = radar_data_list[0]
                    #  有筛选条件的数据
                    if '全部正确率' in radar_title_list:
                        position = radar_title_list.index('全部正确率')
                    else:
                        sum_list = []
                        for radar_data in radar_data_list:
                            radar_data = [float(radar) for radar in radar_data]
                            sum_list.append(sum(radar_data))
                        position = sum_list.index(max(sum_list))
                    if len(radar_data_list) > position:
                        radar_title_list.remove(radar_title_list[position])
                        first_radar_data = radar_data_list[position]
                        radar_data_list.remove(radar_data_list[position])
                    for order, text in enumerate(text_list):
                        worksheet.write_string(2, 3 + order, text, cell_format=data_center_format)
                        worksheet.write_string(3, 3 + order, first_radar_data[order], cell_format=data_center_format)
                    #  有筛选条件的
                    for index, condition_title in enumerate(radar_title_list):
                        worksheet.merge_range(2 * (index + 2) + index + 1, 0,
                                              2 * (index + 2) + 2 + index, 1,
                                              condition_title, cell_format=title_format)
                        worksheet.write_string(2 * (index + 2) + index + 1, 2, '学科部落',
                                               cell_format=data_format)
                        for order, text in enumerate(text_list):
                            worksheet.write_string(2 * (index + 2) + index + 1, 3 + order, text_list[order],
                                                   cell_format=data_format)
                        worksheet.write_string(2 * (index + 2) + index + 2, 2, '正确率(%)',
                                               cell_format=data_format)
                        worksheet.write_string(2 * (index + 2) + index + 2, 2, '正确率(%)',
                                               cell_format=data_format)
                        for order, radar_data in enumerate(radar_data_list[index]):
                            worksheet.write_string(2 * (index + 2) + index + 2, 3 + order, radar_data,
                                                   cell_format=data_format)
            #  统计——科学素质题库参数比较分析
            if order == "3" and chart_name:
                #  难度的标题
                difficulty_title = self.get_argument('difficulty_title', '')
                # 难度的数据
                difficulty_param_dict = self.get_argument('difficulty_param_dict', '')
                difficulty_xAxis = self.get_argument('difficulty_xAxis', '')

                #  维度
                knowledge_title = self.get_argument('knowledge_title', '')
                knowledge_param_dict = self.get_argument('knowledge_param_dict', '')
                knowledge_xAxis = self.get_argument('knowledge_xAxis', '')
                #  难度和维度混合的数据
                difficulty_knowledge_title = self.get_argument('difficulty_knowledge_title', '')
                difficulty_knowledge_dict = self.get_argument('difficulty_knowledge_dict', '')
                if difficulty_title and difficulty_param_dict and difficulty_xAxis and knowledge_title and knowledge_param_dict and knowledge_xAxis and difficulty_knowledge_title and difficulty_knowledge_dict:
                    worksheet = workbook.add_worksheet(name=difficulty_title)
                    worksheet.merge_range(1, 2, 1, 7, '导出时间' + export_time, cell_format=title_format)
                    worksheet.merge_range(0, 0, 0, 7, chart_name, cell_format=title_format)
                    worksheet.merge_range(1, 0, 1, 1, '筛选条件', cell_format=title_format)
                    worksheet.merge_range(2, 0, 3, 1, '全部正确率', cell_format=title_format)
                    worksheet.write_string(2, 2, '难度', cell_format=data_format)
                    worksheet.write_string(3, 2, '正确率(%)', cell_format=data_format)
                    difficulty_param_dict = json.loads(difficulty_param_dict)
                    difficulty_param_title = list(difficulty_param_dict.keys())
                    difficulty_param_data = list(difficulty_param_dict.values())
                    difficulty_xAxis = json.loads(difficulty_xAxis)
                    #  有筛选条件的数据
                    if '总体正确率' in difficulty_param_title:
                        position = difficulty_param_title.index('总体正确率')
                    else:
                        position = difficulty_param_data.index(max(sum(difficulty_param_data)))
                    if len(difficulty_param_data) > position:
                        difficulty_param_title.remove(difficulty_param_title[position])

                    for index, title in enumerate(difficulty_xAxis):
                        worksheet.write_string(2, 3 + index, title)
                        if '总体正确率' in list(difficulty_param_dict.keys()):
                            worksheet.write_string(3, 3 + index, difficulty_param_dict['总体正确率'][index],
                                                   cell_format=data_center_format)
                        else:
                            max_data_list = max(sum(difficulty_param_data))
                            worksheet.write_string(3, 2 + order, max_data_list[index - 1],
                                                   cell_format=data_center_format)
                    if difficulty_param_title:
                        #  有筛选条件得数据写入到excel
                        for index, condition_title in enumerate(difficulty_param_title):
                            worksheet.merge_range(2 * (index + 2) + index + 1, 0, 2 * (index + 2) + 2 + index, 1,
                                                  condition_title, cell_format=title_format)
                            worksheet.write_string(2 * (index + 2) + index + 1, 2, '难度', cell_format=data_format)
                            worksheet.write_string(2 * (index + 2) + index + 2, 2, '答对题目分布（%）', cell_format=data_format)
                            for condition_index, data in enumerate(difficulty_param_dict[condition_title]):
                                worksheet.write_string(2 * (index + 2) + index + 2, 2 + condition_index + 1, str(data),
                                                       cell_format=data_format)
                                worksheet.write_string(2 * (index + 2) + index + 1, 2 + condition_index + 1,
                                                       difficulty_xAxis[condition_index],
                                                       cell_format=data_format)

                    worksheet = workbook.add_worksheet(name=knowledge_title)
                    worksheet.merge_range(1, 2, 1, 5, '导出时间' + export_time, cell_format=title_format)
                    worksheet.merge_range(0, 0, 0, 5, chart_name, cell_format=title_format)
                    worksheet.merge_range(1, 0, 1, 1, '筛选条件', cell_format=title_format)
                    worksheet.merge_range(2, 0, 3, 1, '全部正确率', cell_format=title_format)
                    worksheet.write_string(2, 2, '知识维度', cell_format=data_format)
                    worksheet.write_string(3, 2, '答对题目分布(%)', cell_format=data_format)
                    knowledge_param_dict = json.loads(knowledge_param_dict)
                    knowledge_param_title = list(knowledge_param_dict.keys())
                    knowledge_param_data = list(knowledge_param_dict.values())
                    knowledge_xAxis = json.loads(knowledge_xAxis)
                    #  有筛选条件的数据
                    if '总体正确率' in knowledge_param_title:
                        position = knowledge_param_title.index('总体正确率')
                    else:
                        position = knowledge_param_data.index(max(sum(knowledge_param_data)))
                    if len(knowledge_param_data) > position:
                        knowledge_param_title.remove(knowledge_param_title[position])
                    for index, title in enumerate(knowledge_xAxis):
                        worksheet.write_string(2, 3 + index, title)
                        if '总体正确率' in list(knowledge_param_dict.keys()):
                            worksheet.write_string(3, 3 + index, knowledge_param_dict['总体正确率'][index],
                                                   cell_format=data_center_format)
                        else:
                            max_data_list = max(sum(knowledge_param_data))
                            worksheet.write_string(3, 2 + order, max_data_list[index - 1],
                                                   cell_format=data_center_format)
                    if knowledge_param_title:
                        #  有筛选条件得数据写入到excel
                        for index, condition_title in enumerate(knowledge_param_title):
                            worksheet.merge_range(2 * (index + 2) + index + 1, 0, 2 * (index + 2) + 2 + index, 1,
                                                  condition_title, cell_format=title_format)
                            worksheet.write_string(2 * (index + 2) + index + 1, 2, '知识维度', cell_format=data_format)
                            worksheet.write_string(2 * (index + 2) + index + 2, 2, '答对题目分布(%)', cell_format=data_format)
                            for condition_index, data in enumerate(knowledge_param_dict[condition_title]):
                                worksheet.write_string(2 * (index + 2) + index + 2, 2 + condition_index + 1, str(data),
                                                       cell_format=data_format)
                                worksheet.write_string(2 * (index + 2) + index + 1, 2 + condition_index + 1,
                                                       knowledge_xAxis[condition_index],
                                                       cell_format=data_format)
                    #  难度和维度混合的数据
                    worksheet = workbook.add_worksheet(name=difficulty_knowledge_title)
                    worksheet.merge_range(1, 2, 1, 5, '导出时间' + export_time, cell_format=title_format)
                    worksheet.merge_range(0, 0, 0, 5, chart_name, cell_format=title_format)
                    worksheet.merge_range(1, 0, 1, 1, '筛选条件', cell_format=title_format)
                    worksheet.write_string(2, 0, '知识维度', cell_format=data_center_format)
                    worksheet.write_string(2, 1, '难度', cell_format=data_center_format)
                    difficulty_knowledge_dict = json.loads(difficulty_knowledge_dict)
                    title_list = list(difficulty_knowledge_dict.keys())
                    #  题目难度的title
                    difficulty_title_list = list(list(difficulty_knowledge_dict.values())[0].keys())
                    total_data_list = []
                    for index, title in enumerate(title_list):
                        total_data_list.append(list(list(difficulty_knowledge_dict.values())[index].values()))
                        worksheet.merge_range(3 + index, 0, 3 + index, 1, title, cell_format=data_center_format)
                    for index, difficulty_title in enumerate(difficulty_title_list):
                        worksheet.write_string(2, 2 + index, difficulty_title, cell_format=data_center_format)
                    for index, data_list in enumerate(total_data_list):
                        for order, data in enumerate(data_list):
                            worksheet.write_string(3 + index, 2 + order, str(data) + '%',
                                                   cell_format=data_center_format)
            workbook.close()
            self.set_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.set_header('Content-Disposition',
                            "attachment;filename*=utf-8''{}.xlsx".format(quote(chart_name.encode('utf-8'))))
            self.write(output.getvalue())
            self.finish()
        except Exception:
            logger.error(traceback.format_exc())


URL_MAPPING_LIST = [
    url(r'/backoffice/reports/subject/analysis/export/excel/', ReportStudyAnalysisExportExcelHandler,
        name='backoffice_reports_learning_situation_export_excel')
]
