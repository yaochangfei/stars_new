# !/usr/bin/python

import json

from db import STATUS_SUBJECT_DIMENSION_ACTIVE, STATUS_SUBJECT_ACTIVE, CATEGORY_SUBJECT_BENCHMARK, \
    CATEGORY_SUBJECT_GRADUATION, CATEGORY_SUBJECT_GENERAL
from db.models import SubjectDimension, Subject
from enums import PERMISSION_TYPE_REPORT_SUBJECT_ANALYZE_MANAGEMENT
from logger import log_utils
from motorengine import ASC
from motorengine.stages import MatchStage, SortStage, LookupStage
from motorengine.stages.group_stage import GroupStage
from motorengine.stages.project_stage import ProjectStage
from tornado.web import url
from web import BaseHandler, decorators

logger = log_utils.get_logging()


class SubjectOverallViewHandler(BaseHandler):
    @decorators.render_template('backoffice/reports/subject_overall_view.html')
    @decorators.permission_required(PERMISSION_TYPE_REPORT_SUBJECT_ANALYZE_MANAGEMENT)
    async def get(self):
        dark_skin = self.get_argument('dark_skin')
        dark_skin = True if dark_skin == 'True' else False
        category_cid, difficulty_cid, knowledge_cid = None, None, None
        subject_dimension_list = await SubjectDimension.find(
            dict(parent_cid=None, status=STATUS_SUBJECT_DIMENSION_ACTIVE)).to_list(None)
        for subject_dimension in subject_dimension_list:
            if subject_dimension:
                if subject_dimension.code == 'CSK001':
                    category_cid = subject_dimension.cid
                if subject_dimension.code == 'CSD001':
                    difficulty_cid = subject_dimension.cid
                if subject_dimension.code == 'CDS001':
                    knowledge_cid = subject_dimension.cid
        knowledge_dimension_list = await SubjectDimension.find(dict(parent_cid=knowledge_cid)).sort(
            [('ordered', ASC)]).to_list(None)
        category_dimension_list = await SubjectDimension.find(dict(parent_cid=category_cid)).sort(
            [('ordered', ASC)]).to_list(None)
        second_dimension_list = await SubjectDimension.find(dict(parent_cid={'$ne': None})).sort(
            [('ordered', ASC)]).to_list(None)

        dimension_mapping = json.dumps({
            second_dimension.cid: second_dimension.parent_cid for second_dimension in second_dimension_list
        })

        match_stage = MatchStage(dict(status=STATUS_SUBJECT_ACTIVE,
                                      category_use={'$nin': [CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION]}))
        group_stage = GroupStage(dict(
            category='$dimension_dict.%s' % category_cid,
            difficulty='$dimension_dict.%s' % difficulty_cid,
            knowledge='$dimension_dict.%s' % knowledge_cid)
        )
        sort_stage = SortStage([('_id.difficulty', ASC), ('_id.knowledge', ASC), ('_id.category', ASC)])
        subject_lookup_stage = LookupStage(
            foreign=Subject,
            let={'difficulty': '$_id.difficulty', 'knowledge': '$_id.knowledge', 'category': '$_id.category'},
            pipeline=[{'$match': {'$expr': {'$and': [
                {'$eq': ['$status', STATUS_SUBJECT_ACTIVE]},
                {'$in': ['$category_use', [CATEGORY_SUBJECT_GENERAL, None]]},
                {'$eq': ['$dimension_dict.%s' % difficulty_cid, '$$difficulty']},
                {'$eq': ['$dimension_dict.%s' % knowledge_cid, '$$knowledge']},
                {'$eq': ['$dimension_dict.%s' % category_cid, '$$category']}
            ]}}}, {
                '$group': {'_id': None, 'count': {'$sum': 1}}
            }],
            as_list_name='quantity_list',
        )
        difficulty_lookup_stage = LookupStage(SubjectDimension, '_id.difficulty', 'cid', 'difficulty_list')
        knowledge_lookup_stage = LookupStage(SubjectDimension, '_id.knowledge', 'cid', 'knowledge_list')
        category_lookup_stage = LookupStage(SubjectDimension, '_id.category', 'cid', 'category_list')
        project_stage = ProjectStage(**{
            '_id': False,
            'm_difficulty': {
                'cid': '$_id.difficulty',
                'code': '$difficulty_list.code',
                'title': '$difficulty_list.title',
                'ordered': '$difficulty_list.ordered'
            },
            'm_knowledge': {
                'cid': '$_id.knowledge',
                'code': '$knowledge_list.code',
                'title': '$knowledge_list.title',
                'ordered': '$knowledge_list.ordered'
            },
            'm_category': {
                'cid': '$_id.category',
                'code': '$category_list.code',
                'title': '$category_list.title',
                'ordered': '$category_list.ordered'

            },
            'count': '$quantity_list.count'})

        subject_cursor = Subject.aggregate([
            match_stage, group_stage, sort_stage, subject_lookup_stage, difficulty_lookup_stage, knowledge_lookup_stage,
            category_lookup_stage, project_stage
        ])

        data: dict = await self.do_generate_data_structs(subject_cursor)

        return locals()

    @staticmethod
    async def do_generate_data_structs(subject_cursor):
        t_data = {}
        if subject_cursor:
            while await subject_cursor.fetch_next:
                subject = subject_cursor.next_object()
                if subject:
                    # 难度
                    d_cid = subject.m_difficulty.cid
                    d_code_list = subject.m_difficulty.code
                    d_code = d_code_list[0] if d_code_list else ''
                    d_title_list = subject.m_difficulty.title
                    d_title = d_title_list[0] if d_title_list else ''
                    d_ordered_list = subject.m_difficulty.ordered
                    d_ordered = d_ordered_list[0] if d_ordered_list else ''
                    if t_data.get(d_cid) is None:
                        t_data[d_cid] = {}
                    t_data[d_cid]['cid'] = d_cid
                    t_data[d_cid]['code'] = d_code
                    t_data[d_cid]['title'] = d_title
                    t_data[d_cid]['ordered'] = d_ordered

                    # 知识维度
                    k_cid = subject.m_knowledge.cid
                    k_code_list = subject.m_knowledge.code
                    k_code = k_code_list[0] if k_code_list else ''
                    k_title_list = subject.m_knowledge.title
                    k_title = k_title_list[0] if k_title_list else ''
                    k_ordered_list = subject.m_knowledge.ordered
                    k_ordered = k_ordered_list[0] if k_ordered_list else ''

                    if t_data[d_cid].get('knowledge') is None:
                        t_data[d_cid]['knowledge'] = {}
                    if t_data[d_cid]['knowledge'].get(k_cid) is None:
                        t_data[d_cid]['knowledge'][k_cid] = {}

                    t_data[d_cid]['knowledge'][k_cid]['cid'] = k_cid
                    t_data[d_cid]['knowledge'][k_cid]['code'] = k_code
                    t_data[d_cid]['knowledge'][k_cid]['title'] = k_title
                    t_data[d_cid]['knowledge'][k_cid]['ordered'] = k_ordered

                    # 学科部类
                    c_cid = subject.m_category.cid
                    c_code_list = subject.m_category.code
                    c_code = c_code_list[0] if c_code_list else ''
                    c_title_list = subject.m_category.title
                    c_title = c_title_list[0] if c_title_list else ''
                    c_ordered_list = subject.m_category.ordered
                    c_ordered = c_ordered_list[0] if c_ordered_list else ''
                    c_count_list = subject.count
                    c_count = c_count_list[0] if c_count_list else 0

                    if t_data[d_cid]['knowledge'][k_cid].get('category') is None:
                        t_data[d_cid]['knowledge'][k_cid]['category'] = {}
                    if t_data[d_cid]['knowledge'][k_cid]['category'].get(c_cid) is None:
                        t_data[d_cid]['knowledge'][k_cid]['category'][c_cid] = {}

                    t_data[d_cid]['knowledge'][k_cid]['category'][c_cid]['cid'] = c_cid
                    t_data[d_cid]['knowledge'][k_cid]['category'][c_cid]['code'] = c_code
                    t_data[d_cid]['knowledge'][k_cid]['category'][c_cid]['title'] = c_title
                    t_data[d_cid]['knowledge'][k_cid]['category'][c_cid]['ordered'] = c_ordered
                    t_data[d_cid]['knowledge'][k_cid]['category'][c_cid]['count'] = c_count

        return t_data


URL_MAPPING_LIST = [
    url(r'/backoffice/reports/subject/overall/', SubjectOverallViewHandler,
        name='backoffice_reports_subject_overall')
]
