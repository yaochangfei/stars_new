# !/usr/bin/python
# -*- coding:utf-8 -*-


import datetime
import json
import traceback
from io import BytesIO

import msgpack
from tornado.web import url
from xlsxwriter import Workbook

from caches.redis_utils import RedisCache
from commons.common_utils import md5, datetime2str
from commons.page_utils import Paging
from db import STATUS_SUBJECT_DIMENSION_ACTIVE, STATUS_SUBJECT_STATISTICS_END, STATUS_SUBJECT_ACTIVE, \
    CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION, STATUS_SUBJECT_INACTIVE
from db.model_utils import get_administrative_division, do_different_administrative_division, \
    do_different_administrative_division2
from db.models import MemberSubjectStatistics, Subject, SubjectOption, SubjectDimension, AdministrativeDivision, \
    ReportSubjectStatisticsMiddle
from enums import PERMISSION_TYPE_REPORT_SUBJECT_ANALYZE_MANAGEMENT, \
    PERMISSION_TYPE_REPORT_SUBJECT_PARAMETER_MANAGEMENT, KEY_CACHE_REPORT_CONDITION, \
    PERMISSION_TYPE_REPORT_SUBJECT_ANALYZE_EXPORT, KEY_CACHE_REPORT_DOING_NOW
from logger import log_utils
from motorengine import ASC
from motorengine.stages import LookupStage, SortStage, MatchStage
from motorengine.stages.group_stage import GroupStage
from motorengine.stages.project_stage import ProjectStage
from tasks.instances.task_report_subject_parameter_cross import start_statistics_subject_parameter_cross
from tasks.instances.task_report_subject_parameter_radar import start_statistics_subject_parameter_radar
from tasks.instances.task_subject_statistics import start_split_subject_stat_task
from web import BaseHandler, decorators

logger = log_utils.get_logging('subject_analysis', 'subject_analysis.log')


class SubjectAnalysisListViewHandler(BaseHandler):
    @decorators.render_template('backoffice/reports/subject_analysis_view.html')
    @decorators.permission_required(PERMISSION_TYPE_REPORT_SUBJECT_ANALYZE_MANAGEMENT)
    async def get(self):
        show_export_btn = PERMISSION_TYPE_REPORT_SUBJECT_ANALYZE_EXPORT in self.current_user.permission_code_list

        s_province = self.get_argument('province', '')
        s_city = self.get_argument('city', '')
        s_age_group = self.get_argument('age_group', '')
        s_gender = self.get_argument('gender', '')
        s_education = self.get_argument('education', '')
        sort = int(self.get_argument('sort', 1))
        per_page_quantity = int(self.get_argument('per_page_quantity', 50))
        to_page_num = int(self.get_argument('page', 1))

        # 行政信息
        json_ad = json.dumps(await get_administrative_division(), ensure_ascii=False)

        subject_dimension_list = await SubjectDimension.aggregate([
            MatchStage({'parent_cid': None}),
            SortStage([('ordered', ASC)]),
            LookupStage(SubjectDimension, 'cid', 'parent_cid', 'sub_list')
        ]).to_list(None)

        dimension_dict = {}
        for dimension in subject_dimension_list:
            t_dimension = self.get_argument(dimension.cid, '')
            if t_dimension:
                dimension_dict['%s' % dimension.cid] = t_dimension

        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_SUBJECT_ANALYZE_MANAGEMENT)
    async def post(self):
        res_code = {'code': 0, 'msg': ''}
        subject_dimension_list = await SubjectDimension.aggregate([
            MatchStage({'parent_cid': None}),
            SortStage([('ordered', ASC)]),
            LookupStage(SubjectDimension, 'cid', 'parent_cid', 'sub_list')
        ]).to_list(None)

        search_arguments = {}

        match_dict = {}
        m_province_code_list, m_city_code_list, _ = await do_different_administrative_division2(
            self.current_user.manage_region_code_list)
        if m_province_code_list:
            match_dict['province_code'] = {'$in': m_province_code_list}
        if m_city_code_list:
            match_dict['city_code'] = {'$in': m_city_code_list}

        # 维度信息
        dimension_dict = {}
        for dimension in subject_dimension_list:
            t_dimension = self.get_argument(dimension.cid, '')
            if t_dimension:
                dimension_dict['%s' % dimension.cid] = t_dimension
            search_arguments[dimension.cid] = t_dimension

        query_params = {}
        s_province = self.get_argument('province', '')
        if s_province:
            query_params['province_code'] = s_province
        search_arguments['province'] = s_province

        s_city = self.get_argument('city', '')
        if s_city:
            query_params['city_code'] = s_city
        search_arguments['city'] = s_city

        s_age_group = self.get_argument('age_group', '')
        if s_age_group:
            query_params['age_group'] = int(s_age_group)
        search_arguments['age_group'] = s_age_group

        s_gender = self.get_argument('gender', '')
        if s_gender:
            query_params['gender'] = int(s_gender)
        search_arguments['gender'] = s_gender

        s_education = self.get_argument('education', '')
        if s_education:
            query_params['education'] = int(s_education)
        search_arguments['education'] = s_education

        try:
            category = parse_search_params(query_params)
            category_list = await ReportSubjectStatisticsMiddle.distinct('category')

            result = RedisCache.hget(KEY_CACHE_REPORT_CONDITION, str(category))
            logger.info('CATEGORY: %s, result is %s' % (str(category), result))

            if result is None:
                res_code['msg'] = '数据截至日期为：当前时间'
                start_split_subject_stat_task.delay(category, datetime.datetime.now())
                param_dict = await self.do_paging_from_member_subject_statistics(match_dict, query_params,
                                                                                 dimension_dict,
                                                                                 search_arguments)
            else:
                result = int(result.decode())
                if result == STATUS_SUBJECT_STATISTICS_END:
                    param_dict = await self.do_paging_from_report_subject_statistics_middle(category, match_dict,
                                                                                            query_params,
                                                                                            dimension_dict,
                                                                                            search_arguments)

                    item = param_dict.get('paging').page_items
                    if item:
                        res_code['msg'] = '数据截至日期为：%s' % datetime2str(item[0].task_dt)
                else:
                    res_code['msg'] = '数据截至日期为：当前时间'
                    param_dict = await self.do_paging_from_member_subject_statistics(match_dict, query_params,
                                                                                     dimension_dict,
                                                                                     search_arguments)
            param_dict.update(locals())
            param_dict.pop('self')
            html = self.render_string('backoffice/reports/subject_analysis_table_list.html', **param_dict).decode(
                'utf-8')

            res_code['code'] = 1
            res_code['html'] = self.render_string('backoffice/reports/subject_analysis_table_list.html',
                                                  **param_dict).decode('utf-8')
        except Exception:
            logger.error(traceback.format_exc())
        return res_code

    async def do_paging_from_member_subject_statistics(self, match_dict, query_params, dimension_dict,
                                                       search_arguments):
        """

        :param match_dict:
        :param query_params:
        :param dimension_dict:
        :param search_arguments:
        :return:
        """
        subject_dimension_list = await SubjectDimension.aggregate([
            MatchStage({'parent_cid': None}),
            SortStage([('ordered', ASC)]),
            LookupStage(SubjectDimension, 'cid', 'parent_cid', 'sub_list')
        ]).to_list(None)

        match_dict = {}
        search_arguments = {}

        # 地方科协不会开放此权限，因此显示全部省份数据
        # m_province_code_list, m_city_code_list, _ = await do_different_administrative_division2(
        #     self.current_user.manage_region_code_list)
        # if m_province_code_list:
        #     match_dict['province_code'] = {'$in': m_province_code_list}
        # if m_city_code_list:
        #     match_dict['city_code'] = {'$in': m_city_code_list}

        # 维度信息
        dimension_dict = {}
        for dimension in subject_dimension_list:
            t_dimension = self.get_argument(dimension.cid, '')
            if t_dimension:
                dimension_dict['%s' % dimension.cid] = t_dimension
            search_arguments[dimension.cid] = t_dimension

        # 默认只显示，状态启用，并且不是基准测试或毕业测试的题目
        match_dimension = {'$and': [
            {'status': STATUS_SUBJECT_ACTIVE},
            {'category_use': {
                '$nin': [CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION]}}
        ]}
        if dimension_dict:
            match_dimension['$and'].extend([{'dimension_dict.%s' % k: v} for k, v in dimension_dict.items()])

        subject_cid_list = await Subject.distinct('cid', match_dimension)
        if subject_cid_list:
            match_dict['subject_cid'] = {'$in': subject_cid_list}

        query_params = {}
        s_province = self.get_argument('province', '')
        if s_province:
            query_params['province_code'] = s_province
        search_arguments['province'] = s_province

        s_city = self.get_argument('city', '')
        if s_city:
            query_params['city_code'] = s_city
        search_arguments['city'] = s_city

        s_age_group = self.get_argument('age_group', '')
        if s_age_group:
            query_params['age_group'] = int(s_age_group)
        search_arguments['age_group'] = s_age_group

        s_gender = self.get_argument('gender', '')
        if s_gender:
            query_params['gender'] = int(s_gender)
        search_arguments['gender'] = s_gender

        s_education = self.get_argument('education', '')
        if s_education:
            query_params['education'] = int(s_education)
        search_arguments['education'] = s_education

        manage_stage = MatchStage(match_dict)
        query_stage = MatchStage(query_params)
        group_stage = GroupStage('subject_cid', t_total={'$sum': '$total'}, t_correct={'$sum': '$correct'})
        project_stage = ProjectStage(
            total='$t_total', correct='$t_correct',
            percent={
                '$cond': {
                    'if': {'$eq': ['$t_total', 0]},
                    'then': 0,
                    'else': {
                        '$divide': ['$t_correct', '$t_total']
                    }
                }
            }
        )

        s_lookup_stage = LookupStage(Subject, '_id', 'cid', 'subject_list')
        so_lookup_stage = LookupStage(SubjectOption, '_id', 'subject_cid', 'subject_option_list')

        not_null_match = MatchStage({
            'subject_list': {'$ne': []},
            'subject_option_list': {'$ne': []}
        })

        final_project = ProjectStage(**{
            'custom_code': {'$arrayElemAt': ['$subject_list.custom_code', 0]},
            'code': {'$arrayElemAt': ['$subject_list.code', 0]},
            'title': {'$arrayElemAt': ['$subject_list.title', 0]},
            'subject_list': '$subject_list',
            'subject_option_list': '$subject_option_list',
            'dimension': {'$arrayElemAt': ['$subject_list.dimension_dict', 0]},
            'total': '$total',
            'correct': '$correct',
            'percent': '$percent'
        })

        sort_list = []
        sort = self.get_argument('sort')
        if sort:
            sort = int(sort)
        else:
            sort = 1

        search_arguments['sort'] = sort
        if sort == 1:
            sort_list.append('-percent')
        elif sort == 2:
            sort_list.append('percent')
        elif sort == 3:
            sort_list.append('-total')
        elif sort == 4:
            sort_list.append('total')
        elif sort == 5:
            sort_list.append('-code')
        elif sort == 6:
            sort_list.append('code')
        # 分页 START
        per_page_quantity = int(self.get_argument('per_page_quantity', 50))
        to_page_num = int(self.get_argument('page', 1))

        page_url = '%s?page=$page&per_page_quantity=%s' % (
            self.reverse_url("backoffice_reports_subject_analysis_list"),
            per_page_quantity) + '&sort=%s&' % sort + '&'.join(
            ['='.join((key, str(search_arguments.get(key)))) for key in sorted(search_arguments.keys())])
        paging = Paging(
            page_url, MemberSubjectStatistics, current_page=to_page_num, items_per_page=per_page_quantity,
            pipeline_stages=[manage_stage, query_stage, group_stage, project_stage, s_lookup_stage, so_lookup_stage,
                             not_null_match, final_project],
            sort=sort_list)
        await paging.pager()
        for temp_item in paging.page_items:
            option_dict = dict()
            if not temp_item.subject_option_list:
                pass
            else:
                for opt in temp_item.subject_option_list:
                    option_dict[opt.sort] = {'title': opt.title, 'correct': opt.correct}

            setattr(temp_item, 'option_dict', option_dict)

        return locals()

    async def do_paging_from_report_subject_statistics_middle(self, category, match_dict: dict, query_params: dict,
                                                              dimension_dict: dict, search_arguments: dict):
        """

        :param category:
        :param match_dict:
        :param query_params:
        :param dimension_dict:
        :param search_arguments:
        :return:
        """

        # 默认只显示，状态启用，并且不是基准测试或毕业测试的题目
        match_dimension = {'$and': [
            {'status': STATUS_SUBJECT_ACTIVE},
            {'category_use': {
                '$nin': [CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION]}}
        ]}
        if dimension_dict:
            match_dimension['$and'].extend([{'dimension_dict.%s' % k: v} for k, v in dimension_dict.items()])

        subject_cid_list = await Subject.distinct('cid', match_dimension)
        if subject_cid_list:
            match_dict['subject_cid'] = {'$in': subject_cid_list}

        region_match = {}
        for k, v in match_dict.items():
            region_match['condition.%s' % k] = v

        query_dict = {'category': category}
        for k, v in query_params.items():
            query_dict['condition.%s' % k] = v

        if dimension_dict:
            for k, v in dimension_dict.items():
                query_dict['dimension.%s' % k] = v

        match_region = MatchStage(region_match)
        query_stage = MatchStage(query_dict)
        group_stage = GroupStage('condition.subject_cid',
                                 custom_code={'$first': '$custom_code'},
                                 code={'$first': '$code'},
                                 title={'$first': '$title'},
                                 task_dt={'$first': '$task_dt'},
                                 option_dict={'$first': '$option_dict'},
                                 dimension={'$first': '$dimension'},
                                 total={'$sum': '$total'},
                                 correct={'$sum': '$correct'}
                                 )

        final_project = ProjectStage(**{
            'custom_code': 1,
            'code': 1,
            'title': 1,
            'task_dt': 1,
            'option_dict': 1,
            'dimension': 1,
            'total': 1,
            'correct': 1,
            'percent': {
                '$cond': {
                    'if': {'$eq': ['$total', 0]},
                    'then': 0,
                    'else': {
                        '$divide': ['$correct', '$total']
                    }
                }
            }
        })

        sort_list = list()
        sort = int(self.get_argument('sort', 1))
        if sort == 1:
            sort_list.append('-percent')
        elif sort == 2:
            sort_list.append('percent')
        elif sort == 3:
            sort_list.append('-total')
        elif sort == 4:
            sort_list.append('total')
        elif sort == 5:
            sort_list.append('-code')
        elif sort == 6:
            sort_list.append('code')

        per_page_quantity = int(self.get_argument('per_page_quantity', 50))
        to_page_num = int(self.get_argument('page', 1))

        page_url = '%s?page=$page&per_page_quantity=%s' % (
            self.reverse_url("backoffice_reports_subject_analysis_list"), per_page_quantity) + '&sort=%s&' % sort + \
                   '&'.join(
                       ['='.join((key, str(search_arguments.get(key)))) for key in sorted(search_arguments.keys())])
        paging = Paging(
            page_url, ReportSubjectStatisticsMiddle, current_page=to_page_num, items_per_page=per_page_quantity,
            pipeline_stages=[match_region, query_stage, group_stage, final_project], sort=sort_list)
        await paging.pager()

        return locals()


class SubjectAnalysisExportViewHandler(BaseHandler):
    @decorators.permission_required(PERMISSION_TYPE_REPORT_SUBJECT_ANALYZE_MANAGEMENT)
    async def post(self):
        try:
            output = BytesIO()
            workbook = Workbook(output, {'in_memory': True})
            sheet_accuracy = workbook.add_worksheet(name='题目正确率统计')

            title_format = workbook.add_format({'font_size': 12, 'bold': '1', 'valign': 'vcenter', 'align': 'left',
                                                'font_name': 'Microsoft YaHei'})
            data_format = workbook.add_format({'valign': 'vcenter', 'align': 'left', 'font_name': 'Microsoft YaHei'})
            percent_format = workbook.add_format({'valign': 'vcenter', 'align': 'left', 'font_name': 'Microsoft YaHei'})
            percent_format.set_num_format('0.00%')

            sheet_accuracy.set_column(0, 0, 6)
            sheet_accuracy.set_column(1, 1, 24)
            sheet_accuracy.set_column(2, 2, 12)
            sheet_accuracy.set_column(3, 3, 64)
            sheet_accuracy.set_column(4, 4, 36)
            sheet_accuracy.set_column(5, 7, 12)
            # 标题
            sheet_accuracy.write_row(0, 0, data=['序号', '题目ID', '题号', '题目标题', '正确答案', '总作答次数', '正确次数', '正确率'],
                                     cell_format=title_format)

            index = 1  # 起始行
            report_data = await self.__do_get_report_data()
            if report_data:
                while await report_data.fetch_next:
                    data = report_data.next_object()
                    if data:
                        sheet_accuracy.set_row(index, cell_format=title_format)

                        sheet_accuracy.write_number(index, 0, index, data_format)
                        # 题目属性
                        subject = data.subject_list[0] if data.subject_list else None
                        if subject:
                            sheet_accuracy.write_string(index, 1, subject.custom_code if subject.custom_code else '-',
                                                        data_format)
                            sheet_accuracy.write_string(index, 2, subject.code if subject.code else '-', data_format)
                            sheet_accuracy.write_string(index, 3, subject.title if subject.title else '-',
                                                        data_format)
                            # 选项属性
                            for opt in data.subject_option_list:
                                if opt.correct:
                                    sheet_accuracy.write_string(index, 4,
                                                                '%s、%s' % (opt.sort, opt.title) if opt.title else '-',
                                                                data_format)
                            correct = data.correct if data.correct else 0
                            total = data.total if data.total else 0
                            sheet_accuracy.write_number(index, 5, total, data_format)
                            sheet_accuracy.write_number(index, 6, correct, data_format)
                            sheet_accuracy.write(index, 7, correct / total if total > 0 else 0, percent_format)
                            index += 1
            workbook.close()

            self.set_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.set_header('Content-Disposition', 'attachment; filename=%s' % (
                    'subject_accuracy_statistics_%s.xlsx' % datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')))
            self.write(output.getvalue())
            self.finish()
        except Exception:
            logger.error(traceback.format_exc())

    async def __do_get_report_data(self):
        subject_dimension_list = await SubjectDimension.aggregate([
            MatchStage({'parent_cid': None}),
            SortStage([('ordered', ASC)]),
            LookupStage(SubjectDimension, 'cid', 'parent_cid', 'sub_list')
        ]).to_list(None)

        match_dict = {}
        search_arguments = {}

        # 地方科协不会开放此权限，因此导出全部省份数据
        # m_province_code_list, m_city_code_list, _ = await do_different_administrative_division2(
        #     self.current_user.manage_region_code_list)
        # if m_province_code_list:
        #     match_dict['province_code'] = {'$in': m_province_code_list}
        # if m_city_code_list:
        #     match_dict['city_code'] = {'$in': m_city_code_list}

        # 维度信息
        dimension_dict = {}
        for dimension in subject_dimension_list:
            t_dimension = self.get_argument(dimension.cid, '')
            if t_dimension:
                dimension_dict['%s' % dimension.cid] = t_dimension
            search_arguments[dimension.cid] = t_dimension

        # 默认只显示，状态启用，并且不是基准测试或毕业测试的题目
        match_dimension = {'$and': [
            {'status': STATUS_SUBJECT_ACTIVE},
            {'category_use': {
                '$nin': [CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION]}}
        ]}
        if dimension_dict:
            match_dimension['$and'].extend([{'dimension_dict.%s' % k: v} for k, v in dimension_dict.items()])

        subject_cid_list = await Subject.distinct('cid', match_dimension)
        if subject_cid_list:
            match_dict['subject_cid'] = {'$in': subject_cid_list}

        query_params = {}
        s_province = self.get_argument('province', '')
        if s_province:
            query_params['province_code'] = s_province
        search_arguments['province'] = s_province

        s_city = self.get_argument('city', '')
        if s_city:
            query_params['city_code'] = s_city
        search_arguments['city'] = s_city

        s_age_group = self.get_argument('age_group', '')
        if s_age_group:
            query_params['age_group'] = int(s_age_group)
        search_arguments['age_group'] = s_age_group

        s_gender = self.get_argument('gender', '')
        if s_gender:
            query_params['gender'] = int(s_gender)
        search_arguments['gender'] = s_gender

        s_education = self.get_argument('education', '')
        if s_education:
            query_params['education'] = int(s_education)
        search_arguments['education'] = s_education

        manage_stage = MatchStage(match_dict)
        query_stage = MatchStage(query_params)
        group_stage = GroupStage('subject_cid', t_total={'$sum': '$total'}, t_correct={'$sum': '$correct'})
        project_stage = ProjectStage(
            total='$t_total', correct='$t_correct',
            percent={
                '$cond': {
                    'if': {'$eq': ['$t_total', 0]},
                    'then': 0,
                    'else': {
                        '$divide': ['$t_correct', '$t_total']
                    }
                }
            }
        )

        s_lookup_stage = LookupStage(Subject, '_id', 'cid', 'subject_list')
        so_lookup_stage = LookupStage(SubjectOption, '_id', 'subject_cid', 'subject_option_list')

        not_null_match = MatchStage({
            'subject_list': {'$ne': []},
            'subject_option_list': {'$ne': []}
        })

        final_project = ProjectStage(**{
            'custom_code': {'$arrayElemAt': ['$subject_list.custom_code', 0]},
            'code': {'$arrayElemAt': ['$subject_list.code', 0]},
            'title': {'$arrayElemAt': ['$subject_list.title', 0]},
            'subject_list': '$subject_list',
            'subject_option_list': '$subject_option_list',
            'dimension': {'$arrayElemAt': ['$subject_list.dimension_dict', 0]},
            'total': '$total',
            'correct': '$correct',
            'percent': '$percent'
        })

        sort_list = []
        sort = self.get_argument('sort')
        if sort:
            sort = int(sort)
        else:
            sort = 1

        search_arguments['sort'] = sort
        if sort == 1:
            sort_list.append('-percent')
        elif sort == 2:
            sort_list.append('percent')
        sort_list.append('-total')

        return MemberSubjectStatistics.aggregate([
            manage_stage, query_stage, group_stage, project_stage, s_lookup_stage, so_lookup_stage, not_null_match,
            final_project
        ])


class ReportSubjectAnalysisParameterViewHandler(BaseHandler):
    """
    题库参数
    """

    @decorators.render_template('backoffice/reports/subject_analysis_parameter_view.html')
    @decorators.permission_required(PERMISSION_TYPE_REPORT_SUBJECT_PARAMETER_MANAGEMENT)
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


class ReportSubjectAnalysisDimensionViewHandler(BaseHandler):
    """
    获取维度正确率
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_SUBJECT_PARAMETER_MANAGEMENT)
    async def post(self):
        result = {'code': 0}
        try:
            root_dimension_code = self.get_argument('root_dimension_code')
            if not root_dimension_code:
                result['code'] = -1
                return result

            province_code_list = self.get_arguments('province_code_list[]')
            city_code_list = self.get_arguments('city_code_list[]')
            gender_list = self.get_arguments('gender_list[]')
            age_group_list = self.get_arguments('age_group_list[]')
            education_list = self.get_arguments('education_list[]')

            m_province_code_list, m_city_code_list, _ = await do_different_administrative_division(
                self.current_user.manage_region_code_list)

            dimension = await SubjectDimension.find_one(dict(code=root_dimension_code,
                                                             status=STATUS_SUBJECT_DIMENSION_ACTIVE))
            cache_key = do_generate_cache_key('_RESULT_LT_SUBJECT_DIMENSION_STATISTIC',
                                              root_dimension_code=root_dimension_code,
                                              province_code_list=province_code_list,
                                              city_code_list=city_code_list,
                                              gender_list=gender_list, age_group_list=age_group_list,
                                              education_list=education_list,
                                              m_province_code_list=m_province_code_list,
                                              m_city_code_list=m_city_code_list)
            data = RedisCache.get(cache_key)
            if data is None:
                start_statistics_subject_parameter_radar.delay(cache_key, root_dimension_code, m_city_code_list,
                                                               province_code_list, city_code_list, gender_list,
                                                               age_group_list, education_list)
                result['code'] = 2
                result['cache_key'] = cache_key
            elif data == KEY_CACHE_REPORT_DOING_NOW:
                result['code'] = 2
                result['cache_key'] = cache_key
            else:
                result['title'] = dimension.title
                result['data'] = msgpack.unpackb(data, raw=False)
                result['code'] = 1
        except TypeError:
            result['code'] = 2
            result['cache_key'] = cache_key
        except Exception:
            logger.error(traceback.format_exc())
        for data in result.get('data', []):
            if not data.get("title"):
                result['data'].remove(data)
        return result


class ReportSubjectAnalysisDimensionCrossViewHandler(BaseHandler):
    """
    获取维度正确率
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_SUBJECT_PARAMETER_MANAGEMENT)
    async def post(self):
        result = {'code': 0}
        try:
            main_dimension_code = self.get_argument('primary_dimension_code')
            second_dimension_code = self.get_argument('second_dimension_code')
            if not main_dimension_code or not second_dimension_code:
                result['code'] = -1
                return result

            province_code_list = self.get_arguments('province_code_list[]')
            city_code_list = self.get_arguments('city_code_list[]')
            gender_list = self.get_arguments('gender_list[]')
            age_group_list = self.get_arguments('age_group_list[]')
            education_list = self.get_arguments('education_list[]')
            _, m_city_code_list, _ = await do_different_administrative_division2(
                self.current_user.manage_region_code_list)

            cache_key = do_generate_cache_key('_RESULT_LT_SUBJECT_DIMENSION_CROSS_STATISTIC',
                                              main_dimension_code=main_dimension_code,
                                              second_dimension_code=second_dimension_code,
                                              province_code_list=province_code_list,
                                              city_code_list=city_code_list,
                                              gender_list=gender_list,
                                              age_group_list=age_group_list,
                                              education_list=education_list,
                                              m_city_code_list=m_city_code_list)
            data = RedisCache.get(cache_key)
            if data is None:
                start_statistics_subject_parameter_cross.delay(cache_key=cache_key,
                                                               main_dimension_code=main_dimension_code,
                                                               second_dimension_code=second_dimension_code,
                                                               m_city_code_list=m_city_code_list,
                                                               province_code_list=province_code_list,
                                                               city_code_list=city_code_list,
                                                               gender_list=gender_list, age_group_list=age_group_list,
                                                               education_list=education_list)
                result['code'] = 2
                result['cache_key'] = cache_key
            elif data == KEY_CACHE_REPORT_DOING_NOW:
                result['code'] = 2
                result['cache_key'] = cache_key
            else:
                result['data'] = msgpack.unpackb(data, raw=False)
                result['code'] = 1
        except TypeError:
            result['code'] = 2
            result['cache_key'] = cache_key
        except Exception:
            logger.error(traceback.format_exc())

        return result


def do_generate_cache_key(prefix: str, **kwargs):
    """
    生成缓存key
    :param prefix:
    :param kwargs:
    :return:
    """
    if prefix:
        v_list, v_str = [], ''
        if kwargs:
            for k, v in kwargs.items():
                v_list.append('(%s:%s)' % (k, v))
            if v_list:
                v_str = ''.join(v_list)

        return '%s_%s' % (prefix, md5(v_str))
    return prefix


def parse_search_params(search_params: dict = None):
    """
    将查询关键字解析为condition
    :param search_params:
    :return:
    """
    condition = {'subject_cid': '$subject_cid', 'province_code': '$province_code', 'city_code': '$city_code'}
    for k in search_params:
        condition[k] = '$%s' % k

    return condition


URL_MAPPING_LIST = [
    url(r'/backoffice/reports/subject/analysis/list/', SubjectAnalysisListViewHandler,
        name='backoffice_reports_subject_analysis_list'),
    url(r'/backoffice/reports/subject/analysis/export/', SubjectAnalysisExportViewHandler,
        name='backoffice_reports_subject_analysis_export'),
    url(r'/backoffice/reports/subject/analysis/parameter/', ReportSubjectAnalysisParameterViewHandler,
        name='backoffice_reports_subject_analysis_parameter'),
    url(r'/backoffice/reports/subject/analysis/dimension/', ReportSubjectAnalysisDimensionViewHandler,
        name='backoffice_reports_subject_analysis_dimension'),
    url(r'/backoffice/reports/subject/analysis/dimension/cross/', ReportSubjectAnalysisDimensionCrossViewHandler,
        name='backoffice_reports_subject_analysis_dimension_cross'),
]
