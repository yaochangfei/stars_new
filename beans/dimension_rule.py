# !/usr/bin/python
# -*- coding:utf-8 -*-


import itertools

from commons.common_utils import md5
from db import STATUS_SUBJECT_ACTIVE, CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION
from db.models import Subject, RaceSubjectRefer
from motorengine.stages import MatchStage, SampleStage


class DimensionConditionO(object):
    def __init__(self, cid, value=None):
        self.cid = cid
        self.value = value

    def __repr__(self):
        return 'DimensionConditionO(cid=%s, value=%s)' % (self.cid, self.value)


class DimensionRuleO(object):

    def __init__(self, cid, category, subject_quantity):
        self.cid = cid
        self.category = category
        self.subject_quantity = subject_quantity
        self.sampling_condition_list = []

    def append_sampling_condition(self, dc: DimensionConditionO):
        if not isinstance(dc, DimensionConditionO):
            raise ValueError('Accept only [DimensionConditionO] type.')
        self.sampling_condition_list.append(dc)

    def __repr__(self):
        return 'DimensionRuleO(cid=%s, category=%s, subject_quantity=%s, sampling_condition_list=%s)' % (
            self.cid, self.category, self.subject_quantity, self.sampling_condition_list)


class SubjectFilterO(object):
    def __init__(self):
        self.__condition_list = []
        self.__option_condition_list = []
        self.__operate_map = {}

        self.sample_quantity = 1

    def __adapt_operate_map(self):
        for index, conditions in enumerate(self.__condition_list):
            self.__operate_map[index] = {}
            if conditions:
                self.__operate_map[index]['Q'] = []
                equal = True
                prev = None
                max_quantity = 1
                for condition in conditions:
                    # 判断是否相等
                    if prev:
                        if not condition[1] == prev:
                            equal = False
                    prev = condition[1]
                    # 填充查询条件
                    spilt_conditions = condition[0].split('->')
                    self.__operate_map[index]['Q'].append((spilt_conditions[0], spilt_conditions[1], int(condition[1])))
                    # 获取最大值
                    if condition[1] > max_quantity:
                        max_quantity = int(condition[1])
                if not equal:
                    self.__operate_map[index]['Q'].sort(key=lambda data: data[2])
                    self.__operate_map[index]['Q'].reverse()
                self.__operate_map[index]['equal'] = equal
                self.__operate_map[index]['max'] = max_quantity

    def __sampling_from_db(self):
        """
        从数据库获取样本
        :return:
        """
        result_list = []
        operate_map = self.operate_map
        if operate_map:
            for k, v in operate_map.items():
                if v.get('equal'):
                    # 维度抽取数量相等
                    length = v.get('max')
                    union_subject_list = self.__query([(p[0], p[1]) for p in v.get('Q')], length=length)
                    if not union_subject_list:
                        return []
                    if len(union_subject_list) < v.get('max'):
                        return []
                    result_list.append(([subject.cid for subject in union_subject_list],))
                else:
                    # 维度抽取数量不相等
                    union_subject_list = []
                    length = v.get('max')
                    query_q = v.get('Q')[0]
                    subject_list = self.__query([(query_q[0], query_q[1])], length=length)
                    if not subject_list:
                        return []

                    for i in range(len(v.get('Q')[1:])):
                        union_subject_list.append([])

                    for index, frag in enumerate(v.get('Q')[1:]):
                        for subject in subject_list:
                            if subject.dimension_dict.get(frag[0]) == frag[1]:
                                union_subject_list[index].append(subject)

                    if [] in union_subject_list:
                        return []
                    for index, frag in enumerate(v.get('Q')[1:]):
                        if len(union_subject_list[index]) < frag[2]:
                            return []
                    # 组合
                    for index, frag in enumerate(v.get('Q')[1:]):
                        result_list.append(([subject.cid for subject in union_subject_list[index]],))
        else:
            union_subject_list = self.__query(length=self.sample_quantity)
            result_list.append(([subject.cid for subject in union_subject_list],))
        return result_list

    async def __async_sampling_from_db(self):
        """
        从数据库获取样本
        :return:
        """
        result_list = []
        operate_map = self.operate_map
        if operate_map:
            for k, v in operate_map.items():
                if v.get('equal'):
                    # 维度抽取数量相等
                    length = v.get('max')
                    union_subject_list = await self._async_query([(p[0], p[1]) for p in v.get('Q')], length=length)
                    if not union_subject_list:
                        return []
                    if len(union_subject_list) < v.get('max'):
                        return []
                    result_list.append([subject.cid for subject in union_subject_list])
                else:
                    # 维度抽取数量不相等
                    union_subject_list = []
                    length = v.get('max')
                    query_q = v.get('Q')[0]
                    subject_list = await self._async_query([(query_q[0], query_q[1])], length=length)
                    if not subject_list:
                        return []
                    for i in range(len(v.get('Q')[1:])):
                        union_subject_list.append([])
                    for index, frag in enumerate(v.get('Q')[1:]):
                        for subject in subject_list:
                            if subject.dimension_dict.get(frag[0]) == frag[1]:
                                union_subject_list[index].append(subject)
                    if [] in union_subject_list:
                        return []
                    for index, frag in enumerate(v.get('Q')[1:]):
                        if len(union_subject_list[index]) < frag[2]:
                            return []
                    # 组合
                    for index, frag in enumerate(v.get('Q')[1:]):
                        result_list.append([subject.cid for subject in union_subject_list[index]])
        else:
            union_subject_list = await self._async_query(length=self.sample_quantity)
            result_list.append([subject.cid for subject in union_subject_list])
        return result_list

    def __query(self, dimension_cid_pair_list: list = None, length=6):
        query_params = {
            'status': STATUS_SUBJECT_ACTIVE,
            'category_use': {'$nin': [CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION]}
        }
        if self.__option_condition_list:
            for option_condition in self.__option_condition_list:
                query_params['dimension_dict.%s' % option_condition[0]] = {'$in': option_condition[1]}

        if dimension_cid_pair_list:
            for dimension_cid_pair in dimension_cid_pair_list:
                query_params['dimension_dict.%s' % dimension_cid_pair[0]] = dimension_cid_pair[1]

        match_stage = MatchStage(query_params)
        sample_stage = SampleStage(length)
        return Subject.sync_aggregate([match_stage, sample_stage]).to_list(None)

    async def _async_query(self, dimension_cid_pair_list: list = None, length=4):
        """
        异步查询
        :param dimension_cid_pair_list:
        :param length:
        :return:
        """
        query_params = {
            'status': STATUS_SUBJECT_ACTIVE,
            'category_use': {'$nin': [CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION]}
        }
        if self.__option_condition_list:
            for option_condition in self.__option_condition_list:
                query_params['dimension_dict.%s' % option_condition[0]] = {'$in': option_condition[1]}

        if dimension_cid_pair_list:
            for dimension_cid_pair in dimension_cid_pair_list:
                query_params['dimension_dict.%s' % dimension_cid_pair[0]] = dimension_cid_pair[1]

        match_stage = MatchStage(query_params)
        sample_stage = SampleStage(length)
        return await Subject.aggregate([match_stage, sample_stage]).to_list(None)

    @property
    def grouped_subject_cid_list(self):
        result_list = self.__sampling_from_db()
        if result_list:
            result_list = itertools.product(*result_list)
            for result in result_list:
                subject_list = []
                self.unwind_result_list(subject_list, result)
                if subject_list:
                    yield subject_list

    async def subject_group_quantity(self):
        result_list = await self.__async_sampling_from_db()
        return len(result_list)

    def unwind_result_list(self, subject_list, result_list):
        if isinstance(result_list, (tuple, list)):
            if subject_list is None:
                subject_list = []
            for result in result_list:
                if isinstance(result, (tuple, list)):
                    self.unwind_result_list(subject_list, result)
                else:
                    subject_list.append(result)

    def extend_option_condition_list(self, option_condition_list):
        if option_condition_list:
            self.__option_condition_list.extend(option_condition_list)

    def append_condition(self, conditions: list):
        if conditions:
            condition_list = [(list(d.keys())[0], d.get(list(d.keys())[0])) for d in conditions]
            condition_list.sort(key=lambda data: data[0])
            self.__condition_list.append([(condition[0], condition[1]) for condition in condition_list])

    @property
    def union_id(self):
        if self.__condition_list:
            return md5(str(self.__condition_list))
        return None

    @property
    def operate_map(self):
        if not self.__operate_map:
            self.__adapt_operate_map()
        return self.__operate_map

    def __repr__(self):
        return str(self.__condition_list)

    def __str__(self):
        return str(self.__condition_list)


class RaceSubjectFilterO(object):
    """
    竞赛活动抽题
    """

    def __init__(self, race_cid):
        if not race_cid:
            raise Exception('there is no race_cid in race_subject_extract.')

        self.__condition_list = []
        self.__option_condition_list = []
        self.__operate_map = {}
        self.race_cid = race_cid

        self.sample_quantity = 1

    def __adapt_operate_map(self):
        for index, conditions in enumerate(self.__condition_list):
            self.__operate_map[index] = {}
            if conditions:
                self.__operate_map[index]['Q'] = []
                equal = True
                prev = None
                max_quantity = 1
                for condition in conditions:
                    # 判断是否相等
                    if prev:
                        if not condition[1] == prev:
                            equal = False
                    prev = condition[1]
                    # 填充查询条件
                    spilt_conditions = condition[0].split('->')
                    self.__operate_map[index]['Q'].append((spilt_conditions[0], spilt_conditions[1], int(condition[1])))
                    # 获取最大值
                    if condition[1] > max_quantity:
                        max_quantity = int(condition[1])
                if not equal:
                    self.__operate_map[index]['Q'].sort(key=lambda data: data[2])
                    self.__operate_map[index]['Q'].reverse()
                self.__operate_map[index]['equal'] = equal
                self.__operate_map[index]['max'] = max_quantity

    def __sampling_from_db(self):
        """
        从数据库获取样本
        :return:
        """
        result_list = []
        operate_map = self.operate_map
        if operate_map:
            for k, v in operate_map.items():
                if v.get('equal'):
                    # 维度抽取数量相等
                    length = v.get('max')
                    union_subject_list = self.__query([(p[0], p[1]) for p in v.get('Q')], length=length)
                    if not union_subject_list:
                        return []
                    if len(union_subject_list) < v.get('max'):
                        return []
                    result_list.append(([subject.cid for subject in union_subject_list],))
                else:
                    # 维度抽取数量不相等
                    union_subject_list = []
                    length = v.get('max')
                    query_q = v.get('Q')[0]
                    subject_list = self.__query([(query_q[0], query_q[1])], length=length)
                    if not subject_list:
                        return []

                    for i in range(len(v.get('Q')[1:])):
                        union_subject_list.append([])

                    for index, frag in enumerate(v.get('Q')[1:]):
                        for subject in subject_list:
                            if subject.dimension_dict.get(frag[0]) == frag[1]:
                                union_subject_list[index].append(subject)

                    if [] in union_subject_list:
                        return []
                    for index, frag in enumerate(v.get('Q')[1:]):
                        if len(union_subject_list[index]) < frag[2]:
                            return []
                    # 组合
                    for index, frag in enumerate(v.get('Q')[1:]):
                        result_list.append(([subject.cid for subject in union_subject_list[index]],))
        else:
            union_subject_list = self.__query(length=self.sample_quantity)
            result_list.append(([subject.cid for subject in union_subject_list],))
        return result_list

    async def __async_sampling_from_db(self):
        """
        从数据库获取样本
        :return:
        """
        result_list = []
        operate_map = self.operate_map
        if operate_map:
            for k, v in operate_map.items():
                if v.get('equal'):
                    # 维度抽取数量相等
                    length = v.get('max')
                    union_subject_list = await self._async_query([(p[0], p[1]) for p in v.get('Q')], length=length)
                    if not union_subject_list:
                        return []
                    if len(union_subject_list) < v.get('max'):
                        return []
                    result_list.append([subject.cid for subject in union_subject_list])
                else:
                    # 维度抽取数量不相等
                    union_subject_list = []
                    length = v.get('max')
                    query_q = v.get('Q')[0]
                    subject_list = await self._async_query([(query_q[0], query_q[1])], length=length)
                    if not subject_list:
                        return []
                    for i in range(len(v.get('Q')[1:])):
                        union_subject_list.append([])
                    for index, frag in enumerate(v.get('Q')[1:]):
                        for subject in subject_list:
                            if subject.dimension_dict.get(frag[0]) == frag[1]:
                                union_subject_list[index].append(subject)
                    if [] in union_subject_list:
                        return []
                    for index, frag in enumerate(v.get('Q')[1:]):
                        if len(union_subject_list[index]) < frag[2]:
                            return []
                    # 组合
                    for index, frag in enumerate(v.get('Q')[1:]):
                        result_list.append([subject.cid for subject in union_subject_list[index]])
        else:
            union_subject_list = await self._async_query(length=self.sample_quantity)
            result_list.append([subject.cid for subject in union_subject_list])
        return result_list

    def __query(self, dimension_cid_pair_list: list = None, length=6):
        if not self.race_cid:
            raise Exception('there is no race_cid in race_subject_extract.')
        query_params = {
            'status': STATUS_SUBJECT_ACTIVE,
            'race_cid': self.race_cid
        }
        if self.__option_condition_list:
            for option_condition in self.__option_condition_list:
                query_params['dimension_dict.%s' % option_condition[0]] = {'$in': option_condition[1]}

        if dimension_cid_pair_list:
            for dimension_cid_pair in dimension_cid_pair_list:
                query_params['dimension_dict.%s' % dimension_cid_pair[0]] = dimension_cid_pair[1]

        match_stage = MatchStage(query_params)
        sample_stage = SampleStage(length)
        return RaceSubjectRefer.sync_aggregate([match_stage, sample_stage]).to_list(None)

    async def _async_query(self, dimension_cid_pair_list: list = None, length=4):
        """
        异步查询
        :param dimension_cid_pair_list:
        :param length:
        :return:
        """
        query_params = {
            'status': STATUS_SUBJECT_ACTIVE,
            'race_cid': self.race_cid,
        }
        if self.__option_condition_list:
            for option_condition in self.__option_condition_list:
                query_params['dimension_dict.%s' % option_condition[0]] = {'$in': option_condition[1]}

        if dimension_cid_pair_list:
            for dimension_cid_pair in dimension_cid_pair_list:
                query_params['dimension_dict.%s' % dimension_cid_pair[0]] = dimension_cid_pair[1]

        match_stage = MatchStage(query_params)
        sample_stage = SampleStage(length)
        return await RaceSubjectRefer.aggregate([match_stage, sample_stage]).to_list(None)

    @property
    def grouped_subject_cid_list(self):
        result_list = self.__sampling_from_db()
        if result_list:
            result_list = itertools.product(*result_list)
            for result in result_list:
                subject_list = []
                self.unwind_result_list(subject_list, result)
                if subject_list:
                    yield subject_list

    async def subject_group_quantity(self):
        result_list = await self.__async_sampling_from_db()
        return len(result_list)

    def unwind_result_list(self, subject_list, result_list):
        if isinstance(result_list, (tuple, list)):
            if subject_list is None:
                subject_list = []
            for result in result_list:
                if isinstance(result, (tuple, list)):
                    self.unwind_result_list(subject_list, result)
                else:
                    subject_list.append(result)

    def extend_option_condition_list(self, option_condition_list):
        if option_condition_list:
            self.__option_condition_list.extend(option_condition_list)

    def append_condition(self, conditions: list):
        if conditions:
            condition_list = [(list(d.keys())[0], d.get(list(d.keys())[0])) for d in conditions]
            condition_list.sort(key=lambda data: data[0])
            self.__condition_list.append([(condition[0], condition[1]) for condition in condition_list])

    @property
    def union_id(self):
        if self.__condition_list:
            return md5(str(self.__condition_list))
        return None

    @property
    def operate_map(self):
        if not self.__operate_map:
            self.__adapt_operate_map()
        return self.__operate_map

    def __repr__(self):
        return str(self.__condition_list)

    def __str__(self):
        return str(self.__condition_list)
