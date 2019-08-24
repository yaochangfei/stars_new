# !/usr/bin/python
# -*- coding:utf-8 -*-


import traceback

from tornado.web import url

from commons.common_utils import timestamp2str, timestamp2datetime
from db.models import DockingStatistics, Subject
from logger import log_utils
from web import RestBaseHandler, decorators

logger = log_utils.get_logging()


class DockingStatisticsDayDataGetViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            query_timestamp = self.i_args.get('query_timestamp', None)
            if query_timestamp:
                query_timestamp = int(query_timestamp)
            else:
                query_timestamp = self.client_timestamp

            docking_code = timestamp2str(query_timestamp, date_format='%Y%m%d000000')

            data_list = []
            ds_cursor = DockingStatistics.find(dict(docking_code=docking_code))
            while await ds_cursor.fetch_next:
                ds = ds_cursor.next_object()
                if ds:
                    data = self.ds_2_dict(ds)
                    if data:
                        data_list.append(data)
            r_dict['code'] = 1000
            r_dict['data_list'] = data_list
        except RuntimeError:
            r_dict['code'] = -1
            logger.error(traceback.format_exc())
        return r_dict

    def ds_2_dict(self, ds: DockingStatistics):
        result = {}
        if ds:
            result['code'] = ds.member_code
            result['province_code'] = ds.province_code
            result['city_code'] = ds.city_code
            result['sex'] = ds.sex
            result['age_group'] = ds.age_group
            result['education'] = ds.education
            result['total_times'] = ds.total_times
            result['total_subject_quantity'] = ds.total_subject_quantity
            result['total_subject_correct_quantity'] = ds.total_subject_correct_quantity
            result['correct_quantity_detail'] = ds.correct_quantity_detail
            result['subjects_detail'] = ds.subjects_detail
            result['dimension_detail'] = ds.dimension_detail
        return result


class DockingStatisticsSubjectGetViewHandler(RestBaseHandler):
    @decorators.render_json
    @decorators.restful_validation
    async def post(self):
        r_dict = {'code': 0}
        try:
            query_timestamp = self.i_args.get('query_timestamp', None)
            query_all = self.i_args.get('query_all', None)
            data_list = []
            if query_all:
                subject_cursor = Subject.find(dict(record_flag=1))
            else:
                if query_timestamp:
                    query_timestamp = int(query_timestamp)
                else:
                    query_timestamp = self.client_timestamp
                query_time = timestamp2datetime(query_timestamp)
                subject_cursor = Subject.find({
                    '$and': [
                        {"record_flag": 1},
                        {"updated_dt": {'$gte': query_time}},
                    ]
                })
            while await subject_cursor.fetch_next:
                subject = subject_cursor.next_object()
                if subject:
                    data = self.subject_2_dict(subject)
                    if data:
                        data_list.append(data)
            r_dict['code'] = 1000
            r_dict['data_list'] = data_list
        except RuntimeError:
            r_dict['code'] = -1
            logger.error(traceback.format_exc())
        return r_dict

    def subject_2_dict(self, subject: Subject):
        result = {}
        if subject:
            result['code'] = subject.code
            result['custom_code'] = subject.custom_code
            result['cid'] = subject.cid
            result['title'] = subject.title
            result['subject_type'] = subject.category
            result['difficulty'] = subject.difficulty
            result['knowledge'] = subject.dimension
            result['dimension_dict'] = subject.dimension_dict
        return result


URL_MAPPING_LIST = [
    url(r'/api/statistics/day_data/get/', DockingStatisticsDayDataGetViewHandler, name='api_statistics_day_data_get'),
    url(r'/api/statistics/subject/get/', DockingStatisticsSubjectGetViewHandler, name='api_statistics_subject_get')
]
