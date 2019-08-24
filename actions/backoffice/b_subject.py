# !/usr/bin/python
# -*- coding:utf-8 -*-

import datetime
# 2018/4/23 10:54
# Samuel Linning Zhang
import json
import re
import traceback
from io import BytesIO

import xlrd
from bson import ObjectId
from pymongo import UpdateOne
from tornado.web import url
from xlsxwriter import Workbook

from commons.common_utils import get_increase_code
from commons.page_utils import Paging
from commons.upload_utils import save_upload_file, drop_disk_file_by_cid
from db import STATUS_SUBJECT_ACTIVE, STATUS_SUBJECT_INACTIVE, CATEGORY_UPLOAD_FILE_IMG_SUBJECT, \
    KNOWLEDGE_FIRST_LEVEL_DICT, KNOWLEDGE_SECOND_LEVEL_DICT, STATUS_SUBJECT_DIMENSION_ACTIVE
from db.enums import CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION
from db.model_utils import set_subject_choice_rules_redis_value
from db.models import Subject, SubjectOption, UploadFiles, SubjectDimension, RaceSubjectRefer
from enums import PERMISSION_TYPE_MINIAPP_SUBJECT_MANAGEMENT, KEY_INCREASE_SUBJECT_CODE, \
    KEY_INCREASE_SUBJECT_OPTION_CODE
from logger import log_utils
from motorengine import ASC
from motorengine.stages import MatchStage, LookupStage
from web import decorators
from web.base import BaseHandler

logger = log_utils.get_logging()


class SubjectListViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_MANAGEMENT)
    async def get(self):
        subject_dimension_list = await SubjectDimension.find(
            dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=None)).sort('created_dt').to_list(None)
        for subject_dimension in subject_dimension_list:
            sub_subject_dimension = await  SubjectDimension.find(
                dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=subject_dimension.cid)).sort(
                'created_dt').to_list(None)
            subject_dimension.sub_subject_dimension_list = []
            if sub_subject_dimension:
                subject_dimension.sub_subject_dimension_list = sub_subject_dimension
        dimension_dict = {}
        query_params = {'record_flag': 1}

        subject_dimension_cid_str = self.get_argument('subject_dimension_cid_list', '')

        subject_dimension_cid_list = subject_dimension_cid_str.split(',')
        kw_name = self.get_argument('kw_name', '')
        kw_difficulty = self.get_argument('kw_difficulty', '')
        kw_category = self.get_argument('kw_category', '')
        kw_status = self.get_argument('kw_status', '')
        category_use = self.get_argument('category_use', '')
        if subject_dimension_cid_list:
            for temp in subject_dimension_cid_list:
                if temp:
                    dimension_cid, sub_dimension_cid = temp.split('_')
                    dimension_dict[dimension_cid] = sub_dimension_cid
                    if dimension_cid and sub_dimension_cid:
                        query_params['dimension_dict.%s' % dimension_cid] = sub_dimension_cid
        if kw_name:
            query_params['$or'] = [
                {"custom_code": {'$regex': kw_name, '$options': 'i'}},
                {"title": {'$regex': kw_name, '$options': 'i'}},
                {"code": {'$regex': kw_name, '$options': 'i'}}
            ]
        # if kw_difficulty:
        #     query_params['difficulty'] = int(kw_difficulty)
        # if kw_category:
        #     query_params['category'] = int(kw_category)
        if kw_status:
            query_params['status'] = int(kw_status)

        if category_use:
            if category_use == '1':
                query_params['category_use'] = {'$nin': [CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION]}
            else:
                query_params['category_use'] = int(category_use)

        # 分页 START
        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&subject_dimension_cid_list=%s&kw_name=%s&kw_status=%s&category_use=%s' % (
            self.reverse_url("backoffice_subject_list"), per_page_quantity, subject_dimension_cid_str, kw_name,
            kw_status, category_use)
        paging = Paging(page_url, Subject, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['custom_code'], **query_params)
        await paging.pager()
        # 分页 END
        return locals()


class SubjectAddViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_MANAGEMENT)
    async def get(self):
        subject_dimension_list = await SubjectDimension.find(
            dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=None)).to_list(None)
        for subject_dimension in subject_dimension_list:
            sub_subject_dimension = await  SubjectDimension.find(
                dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=subject_dimension.cid)).to_list(None)
            subject_dimension.sub_subject_dimension_list = []
            if sub_subject_dimension:
                subject_dimension.sub_subject_dimension_list = sub_subject_dimension
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        subject_id = None
        try:
            title = self.get_argument('title', None)
            option_str = self.get_argument('option_list', None)
            option_list = json.loads(option_str) if option_str else []
            # difficulty = self.get_argument('difficulty', None)
            # category = self.get_argument('category', None)
            content = self.get_argument('content', None)
            status = self.get_argument('status', None)  # 状态
            knowledge_first = self.get_argument('knowledge_first', None)
            knowledge_second = self.get_argument('knowledge_second', None)
            category_use = self.get_argument('category_use', None)
            resolving = self.get_argument('resolving', None)
            subject_dimension_list = self.get_arguments('subject_dimension')
            custom_code = self.get_argument('custom_code', None)
            if title and len(option_list) >= 2 and resolving and custom_code:
                c_count = await Subject.count(dict(custom_code=custom_code))
                if c_count > 0:
                    r_dict['code'] = -10
                else:
                    if status == 'on':
                        status = STATUS_SUBJECT_ACTIVE
                    else:
                        status = STATUS_SUBJECT_INACTIVE
                    image_cid = None
                    image_cid_list = await save_upload_file(self, 'image', category=CATEGORY_UPLOAD_FILE_IMG_SUBJECT)
                    if image_cid_list:
                        image_cid = image_cid_list[0]

                    code = get_increase_code(KEY_INCREASE_SUBJECT_CODE)
                    # subject = Subject(code=code, title=title, difficulty=int(difficulty), category=int(category))
                    subject = Subject(code=code, title=title)
                    subject.custom_code = custom_code
                    subject.image_cid = image_cid
                    subject.status = status
                    subject.content = content
                    subject.created_id = self.current_user.oid
                    subject.updated_id = self.current_user.oid
                    subject.resolving = resolving
                    knowledge_first = int(knowledge_first) if knowledge_first else None
                    knowledge_second = int(knowledge_second) if knowledge_second else None
                    subject.knowledge_first = knowledge_first
                    subject.knowledge_second = knowledge_second
                    subject.category_use = int(category_use) if category_use else None
                    subject_dimension_dict = {}
                    if subject_dimension_list:
                        for subject_dimension in subject_dimension_list:
                            try:
                                subject_dimension_cid, sub_subject_dimension_cid = subject_dimension.split('_')
                                subject_dimension_dict[subject_dimension_cid] = sub_subject_dimension_cid
                            except ValueError as e:
                                if subject_dimension != 'DFKX':
                                    raise e

                    subject.dimension_dict = subject_dimension_dict
                    # 冗余信息
                    if not isinstance(subject.needless, dict):
                        subject.needless = {}
                    subject.needless['option_quantity'] = len(option_list)

                    if option_list:
                        subject_id = await subject.save()
                        for index, option_dict in enumerate(option_list):
                            if option_dict:
                                so = SubjectOption(subject_cid=subject.cid, code=str(index + 1),
                                                   title=option_dict.get('content'),
                                                   correct=option_dict.get('is_correct'))
                                so.sort = str(index + 1)
                                so.created_id = self.current_user.oid
                                so.updated_id = self.current_user.oid
                                await so.save()

                        await set_subject_choice_rules_redis_value(1)
                        r_dict['code'] = 1
            else:
                if not title:
                    r_dict['code'] = -1
                # if not difficulty:
                #     r_dict['code'] = -4
                # if not category:
                #     r_dict['code'] = -5
                if not resolving:
                    r_dict['code'] = -8
                if not option_list and len(option_list) < 2:
                    r_dict['code'] = -6
                if not custom_code:
                    r_dict['code'] = -9
                if not category_use:
                    r_dict['code'] = -11
        except Exception as e:
            if subject_id:
                subject = await Subject.get_by_id(subject_id)
                if subject:
                    await Subject.delete_by_ids([subject.oid])
                    await Subject.delete_many({'code': subject.code})
            logger.error(traceback.format_exc())
        return r_dict


class SubjectEditViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_MANAGEMENT)
    async def get(self, subject_id):
        match = MatchStage({'_id': ObjectId(subject_id)})
        lookup_option = LookupStage(SubjectOption, 'cid', 'subject_cid')
        lookup_files = LookupStage(UploadFiles, 'image_cid', 'cid')
        subject_list = await Subject.aggregate([match, lookup_option, lookup_files]).to_list(None)

        subject = {}
        option_list = {}
        file_doc = {}
        if subject_list:
            subject = subject_list[0]
            option_list = subject.subject_option_list
            file_list = subject.upload_files_list
            if file_list:
                file_doc = file_list[0]

        subject_dimension_list = await SubjectDimension.find(
            dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=None)).to_list(None)
        for subject_dimension in subject_dimension_list:
            sub_subject_dimension = await  SubjectDimension.find(
                dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=subject_dimension.cid)).to_list(None)
            subject_dimension.sub_subject_dimension_list = []
            if sub_subject_dimension:
                subject_dimension.sub_subject_dimension_list = sub_subject_dimension

        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_MANAGEMENT)
    async def post(self, subject_id):
        r_dict = {'code': 0}
        try:
            subject = await Subject.get_by_id(subject_id)
            if subject:
                title = self.get_argument('title', None)
                option_str = self.get_argument('option_list', None)
                option_list = json.loads(option_str) if option_str else []

                # difficulty = self.get_argument('difficulty', None)
                # category = self.get_argument('category', None)
                content = self.get_argument('content', None)
                status = self.get_argument('status', None)  # 状态
                image_cid = self.get_argument('image_cid', None)  # 状态
                knowledge_first = self.get_argument('knowledge_first', None)
                knowledge_second = self.get_argument('knowledge_second', None)
                category_use = self.get_argument('category_use', None)
                resolving = self.get_argument('resolving', None)
                subject_dimension_list = self.get_arguments('subject_dimension')
                custom_code = self.get_argument('custom_code', None)
                if title and len(option_list) >= 2 and resolving and custom_code:
                    c_count = await Subject.count(dict(custom_code=custom_code, id={'$ne': ObjectId(subject_id)}))
                    if c_count > 0:
                        r_dict['code'] = -10
                    else:
                        if status == 'on':
                            status = STATUS_SUBJECT_ACTIVE
                        else:
                            status = STATUS_SUBJECT_INACTIVE
                        if not image_cid:
                            if self.request.files:
                                image_cid_list = await save_upload_file(self, 'image', file_cid=subject.image_cid,
                                                                        category=CATEGORY_UPLOAD_FILE_IMG_SUBJECT)
                                if image_cid_list:
                                    image_cid = image_cid_list[0]
                            else:
                                image_cid = None
                                if subject.image_cid:
                                    await UploadFiles.delete_many({'cid': subject.image_cid})
                        subject.title = title
                        # subject.difficulty = int(difficulty)
                        # subject.category = int(category)
                        subject.image_cid = image_cid
                        subject.custom_code = custom_code
                        subject.status = status
                        subject.content = content
                        subject.updated_id = self.current_user.oid
                        subject.updated_dt = datetime.datetime.now()
                        subject.resolving = resolving
                        subject.knowledge_first = int(knowledge_first) if knowledge_first else None
                        subject.knowledge_second = int(knowledge_second) if knowledge_second else None
                        subject.category_use = int(category_use) if category_use else None
                        subject_dimension_dict = {}
                        if subject_dimension_list:
                            for subject_dimension in subject_dimension_list:
                                try:
                                    subject_dimension_cid, sub_subject_dimension_cid = subject_dimension.split('_')
                                    subject_dimension_dict[subject_dimension_cid] = sub_subject_dimension_cid
                                except ValueError as e:
                                    if subject_dimension != 'DFKX':
                                        raise e

                        subject.dimension_dict = subject_dimension_dict
                        ret_list = []
                        subject_cid = subject.cid
                        option_code_list = []
                        temp_code_list = []
                        for option in option_list:
                            if option:
                                option_code = option.get('code', None)
                                if option_code:
                                    temp_code_list.append(option_code)
                        max_code = int(temp_code_list[-1])

                        for index, option in enumerate(option_list):
                            if option:
                                is_correct = option.get('is_correct')
                                if subject_cid:
                                    option_code = option.get('code', None)
                                    if not option_code:
                                        option_code = max_code + 1
                                        max_code += 1
                                    ret, option_code = await self.update_option(subject_cid, str(option_code),
                                                                                option.get('content'),
                                                                                is_correct=is_correct, index=index + 1)
                                    ret_list.append(ret)
                                    if option_code:
                                        option_code_list.append(option_code)
                        await SubjectOption.delete_many(
                            {'code': {'$nin': option_code_list}, 'subject_cid': subject_cid})
                        if not ret_list and len(ret_list) < 2:
                            r_dict['code'] = -6
                        # 冗余信息
                        subject.needless['option_quantity'] = len(ret_list)
                        await subject.save()
                        await set_subject_choice_rules_redis_value(1)
                        r_dict['code'] = 1
                else:
                    if not title:
                        r_dict['code'] = -1
                    # if not difficulty:
                    #     r_dict['code'] = -4
                    # if not category:
                    #     r_dict['code'] = -5
                    if not resolving:
                        r_dict['code'] = -8
                    if not custom_code:
                        r_dict['code'] = -9
                    if not category_use:
                        r_dict['code'] = -11
        except RuntimeError:
            if subject_id:
                await Subject.delete_by_ids(subject_id)
            logger.error(traceback.format_exc())
        return r_dict

    async def update_option(self, subject_cid, option_code, option_title, is_correct=False, index=1):
        try:
            # if not option_code:
            #     option_code = str(get_increase_code(KEY_INCREASE_SUBJECT_OPTION_CODE, begin=1))
            subject_option = await SubjectOption.find_one(dict(subject_cid=subject_cid, code=option_code))
            if subject_option:
                subject_option.title = option_title
                subject_option.correct = is_correct
                subject_option.sort = index
                subject_option.updated_id = self.current_user.oid
                subject_option.updated_dt = datetime.datetime.now()
                await subject_option.save()
            else:
                subject_option = SubjectOption(subject_cid=subject_cid, code=option_code,
                                               title=option_title,
                                               correct=is_correct)
                subject_option.sort = index
                subject_option.created_id = self.current_user.oid
                subject_option.updated_id = self.current_user.oid
                await subject_option.save()
        except Exception:
            logger.error(traceback.format_exc())
        return True, option_code


class SubjectDetailViewHandler(BaseHandler):
    @decorators.render_template('backoffice/subjects/detail_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_MANAGEMENT)
    async def get(self, subject_id):
        match = MatchStage({'_id': ObjectId(subject_id)})
        lookup_option = LookupStage(SubjectOption, 'cid', 'subject_cid')
        lookup_files = LookupStage(UploadFiles, 'image_cid', 'cid')

        subject_list = await Subject.aggregate([match, lookup_option, lookup_files]).to_list(None)

        subject = {}
        option_fir_doc = {}
        option_sec_doc = {}
        option_thr_doc = {}
        option_fur_doc = {}
        file_doc = {}
        if subject_list:
            subject = subject_list[0]
            option_list = subject.subject_option_list
            file_list = subject.upload_files_list
            if file_list:
                file_doc = file_list[0]
        subject_dimension_list = await SubjectDimension.find(
            dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=None)).to_list(None)
        for subject_dimension in subject_dimension_list:
            sub_subject_dimension = await  SubjectDimension.find(
                dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=subject_dimension.cid)).to_list(None)
            subject_dimension.sub_subject_dimension_list = []
            if sub_subject_dimension:
                subject_dimension.sub_subject_dimension_list = sub_subject_dimension

        return locals()


class SubjectDeleteViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_MANAGEMENT)
    async def post(self, subject_id):
        r_dict = {'code': 0}
        try:
            subject = await Subject.get_by_id(subject_id)
            await SubjectOption.delete_many({'subject_cid': subject.cid})
            image_cid = subject.image_cid
            if image_cid:
                await drop_disk_file_by_cid(cid_list=image_cid)
            await subject.delete()
            await set_subject_choice_rules_redis_value(1)

            r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectStatusSwitchViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_MANAGEMENT)
    async def post(self, subject_id):
        r_dict = {'code': 0}
        try:
            status = self.get_argument('status', False)
            if status == 'true':
                status = STATUS_SUBJECT_ACTIVE
            else:
                status = STATUS_SUBJECT_INACTIVE
            subject = await Subject.get_by_id(subject_id)
            if subject:
                subject.status = status
                subject.updated = datetime.datetime.now()
                subject.updated_id = self.current_user.oid
                await subject.save()

                if status == STATUS_SUBJECT_INACTIVE:
                    await RaceSubjectRefer.update_many_by_filtered({'subject_cid': subject.cid},
                                                       {'$set': {'status': STATUS_SUBJECT_INACTIVE,
                                                                 'updated_dt': datetime.datetime.now(),
                                                                 'updated_id': self.current_user.cid}
                                                        })

            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectBatchOperationViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            subject_id_list = self.get_body_arguments('subject_id_list[]', [])
            if subject_id_list:
                operate = self.get_argument('operate', None)
                if operate is not None:
                    subject_id_list = [ObjectId(subject_id) for subject_id in subject_id_list]
                    if int(operate) == 1:
                        update_requests = []
                        for subject_id in subject_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(subject_id)},
                                                             {'$set': {'status': STATUS_SUBJECT_ACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await Subject.update_many(update_requests)
                    elif int(operate) == 0:
                        update_requests = []
                        for subject_id in subject_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(subject_id)},
                                                             {'$set': {'status': STATUS_SUBJECT_INACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await Subject.update_many(update_requests)

                        subject_cid_list = await Subject.distinct('cid', {'_id': {'$in': subject_id_list}})

                        await RaceSubjectRefer.update_many_by_filtered({'subject_cid': {'$in': subject_cid_list}},
                                                           {'$set': {'status': STATUS_SUBJECT_INACTIVE,
                                                                     'updated_dt': datetime.datetime.now(),
                                                                     'updated_id': self.current_user.cid}
                                                            })

                    elif int(operate) == -1:
                        image_cid_list = await Subject.distinct('image_cid', {'_id': {'$in': subject_id_list},
                                                                              'image_cid': {'$ne': None}})
                        subject_cid_list = await Subject.distinct('cid', {'_id': {'$in': subject_id_list}})
                        await Subject.delete_many({'_id': {'$in': subject_id_list}})
                        await SubjectOption.delete_many({'subject_cid': {'$in': subject_cid_list}})
                        await drop_disk_file_by_cid(image_cid_list)
                        await set_subject_choice_rules_redis_value(1)
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class SubjectImportViewHandler(BaseHandler):
    """
    题目导入
    """

    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_MANAGEMENT)
    @decorators.render_template('backoffice/subjects/upload_view.html')
    async def get(self):
        return locals()

    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        r_dict = {'code': 0}
        try:
            if self.request.files:
                import_files_meta = self.request.files['file']
                if import_files_meta:
                    code = await self.__subject_import_excel(import_files_meta[0]['body'])
                    r_dict['code'] = code
                    if code == 1:
                        await set_subject_choice_rules_redis_value(1)
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict

    async def __subject_import_excel(self, excel_file_content):
        result_code = 1
        custom_code_list = await Subject.distinct('custom_code', {'record_flag': 1})
        book = xlrd.open_workbook(file_contents=excel_file_content)
        sheet = book.sheet_by_index(0)
        subject_list = []
        subject_option_list = []
        row_list = []
        k_first_dict = dict(zip(KNOWLEDGE_FIRST_LEVEL_DICT.values(), KNOWLEDGE_FIRST_LEVEL_DICT.keys()))
        k_second_dict = dict(zip(KNOWLEDGE_SECOND_LEVEL_DICT.values(), KNOWLEDGE_SECOND_LEVEL_DICT.keys()))

        # 维度信息
        field_dict = {'record_flag': 1, 'status': STATUS_SUBJECT_DIMENSION_ACTIVE, 'parent_cid': {'$in': ['', None]}}
        all_dimension_list = await SubjectDimension.find(field_dict).to_list(None)
        sub_dict = dict(record_flag=1, status=STATUS_SUBJECT_DIMENSION_ACTIVE)
        subject_dimension_dict = {}
        for subject_dimension in all_dimension_list:
            sub_dict['parent_cid'] = subject_dimension.cid
            sub_dimension_list = await SubjectDimension.find(sub_dict).to_list(None)
            if sub_dimension_list:
                subject_dimension_dict[subject_dimension.cid] = sub_dimension_list

        # 按顺序得到表头对应的维度cid（如果题目表头除维度之外有增减，3就随之改变）
        cid_list = []
        title_list = []
        is_empty = 0
        for ind, col in enumerate(sheet.row_values(0)):
            if col:
                title_list.append(col)
            if 3 < ind < (len(all_dimension_list) + 4):
                if not col:
                    is_empty = 1
                flag = 1
                for dimension in all_dimension_list:
                    if dimension.title == str(self.__get_replace_data(col, 2)):
                        flag = 2
                        cid_list.append(dimension.cid)
                        break
                if flag == 1:
                    continue
            if (ind < len(cid_list) + 8) and not col:
                is_empty = 1

        # 判断表头是否正确（如果题目表头除维度之外有增减，8就随之改变）
        if not (len(cid_list) + 8) == len(title_list) or len(cid_list) < 1 or is_empty:
            result_code = 2
            return result_code

        for rownum in range(1, sheet.nrows):
            row_list.append([col for col in sheet.row_values(rownum)])

        if row_list:
            for i, row_data in enumerate(row_list):
                is_exist = 0

                # 题目ID
                custom_code = str(self.__get_replace_data(row_data[1], 2))
                if not custom_code or len(custom_code) > 20 or len(custom_code) < 5:
                    continue
                else:
                    reg = re.compile(r'^[a-zA-Z0-9]*$')
                    if not bool(reg.match(custom_code)):
                        continue
                    if custom_code not in custom_code_list:
                        subject = Subject()
                        subject_code = str(get_increase_code(KEY_INCREASE_SUBJECT_CODE))
                        subject.code = subject_code
                        subject.custom_code = custom_code
                        subject.status = STATUS_SUBJECT_ACTIVE
                        custom_code_list.append(custom_code)
                    else:
                        subject = await Subject.find_one(dict(custom_code=custom_code))
                        # await SubjectOption.delete_many({'subject_cid': subject.cid})
                        subject.updated_dt = datetime.datetime.now()
                        is_exist = 1

                # 一级知识点
                subject.knowledge_first = self.__get_replace_data(row_data[2], 1, data_dict=k_first_dict)

                # 二级知识点
                subject.knowledge_second = self.__get_replace_data(row_data[3], 1, data_dict=k_second_dict)

                # 知识维度
                dimension_dict = {}
                is_wrong = 0
                end_dimension_len = 4 + len(cid_list)
                for index in range(4, end_dimension_len):
                    c_code = self.__get_replace_data(row_data[index], 2)
                    cid = cid_list[index - 4]
                    if cid and c_code:
                        sub_list = subject_dimension_dict.get(cid)
                        if sub_list:
                            is_wrong = 0
                            for sub_dimension in sub_list:
                                if sub_dimension.code == c_code:
                                    is_wrong = 1
                                    dimension_dict[cid] = sub_dimension.cid
                                    break
                            if not is_wrong:
                                result_code = 3
                                is_wrong = 0
                                break
                if dimension_dict and is_wrong:
                    subject.dimension_dict = dimension_dict
                else:
                    continue

                # 答案解析
                resolving = self.__get_replace_data(row_data[end_dimension_len], 2)
                if not resolving:
                    continue
                else:
                    subject.resolving = resolving

                # 题目
                title = self.__get_replace_data(row_data[end_dimension_len + 1], 2)
                if not title:
                    continue
                else:
                    subject.title = title

                # 答案
                count = 0
                if not row_data[end_dimension_len + 2]:
                    continue
                else:
                    if not row_data[end_dimension_len + 2].strip().isalpha() or len(
                            row_data[end_dimension_len + 2].strip()) > 1:
                        continue
                    count = ord(row_data[end_dimension_len + 2].strip().upper()) - 64

                if (count + end_dimension_len + 2) > len(row_data):
                    continue
                else:
                    if not row_data[count + end_dimension_len + 2]:
                        continue
                # 选项
                num = 0
                tmp_option_list = await SubjectOption.find({'subject_cid': subject.cid}).sort([('sort', ASC)]).to_list(
                    None)
                for index in range(end_dimension_len + 3, len(row_data)):
                    if row_data[index]:
                        option_title = self.__get_replace_data(row_data[index], 2)
                        if not option_title:
                            continue
                        else:
                            sort = index - (end_dimension_len + 2)
                            a_index = sort - 1
                            update, subject_option = False, None
                            if tmp_option_list:
                                if len(tmp_option_list) > a_index:
                                    subject_option = tmp_option_list[a_index]
                                    update = True
                            if subject_option is None:
                                subject_option = SubjectOption(
                                    code=str(get_increase_code(KEY_INCREASE_SUBJECT_OPTION_CODE)))

                            if isinstance(option_title, (float, int)):
                                option_title = str(option_title)

                            subject_option.title = option_title
                            subject_option.sort = sort
                            if sort == count:
                                subject_option.correct = True
                            else:
                                subject_option.correct = False
                            subject_option.subject_code = subject.code
                            subject_option.subject_cid = subject.cid
                            if update:
                                subject_option.updated_dt = datetime.datetime.now()
                                subject_option.updated_id = self.current_user.oid
                                subject_option.needless = {}
                                await subject_option.save()
                            else:
                                subject_option_list.append(subject_option)
                            num += 1
                subject.needless = {'option_quantity': num}
                if is_exist:
                    await subject.save()
                else:
                    subject_list.append(subject)
                    if len(subject_list) == 500:
                        await  Subject.insert_many(subject_list)
                        subject_list = []
                    if len(subject_option_list) == 500:
                        await SubjectOption.insert_many(subject_option_list)
                        subject_option_list = []
            if subject_list:
                await Subject.insert_many(subject_list)
            if subject_option_list:
                await SubjectOption.insert_many(subject_option_list)
        return result_code

    def __get_replace_data(self, data, data_type, data_dict=None):
        if not data:
            return None
        if isinstance(data, float):
            data = int(data)
            data = str(data)
        if isinstance(data, str):
            data = data.replace('\n', '').replace(' ', '')
        if data_type == 1:
            if not data_dict.get(data):
                return None
            else:
                return data_dict.get(data)
        else:
            return data


class SubjectDownloadTemplatetViewHandler(BaseHandler):
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_SUBJECT_MANAGEMENT)
    async def get(self):
        try:
            # 根据需求生成excel模板
            filename = 'subject_template_%s.xlsx' % datetime.datetime.now().strftime('%Y%m%d%H%M')
            sheet_name1 = '题目导入模板'
            sheet_name2 = '维度对照表'
            options = {'sheet_name1': sheet_name1, 'sheet_name2': sheet_name2}
            subject_dimension_list = await SubjectDimension.find(
                dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=None)).to_list(None)
            subject_column_list = []
            for subject_dimension in subject_dimension_list:
                subject_column_list.append(subject_dimension.title)

            data_list = []
            for subject_dimension in subject_dimension_list:
                temp_dict = {}
                temp_dict['title'] = subject_dimension.title
                temp_dict['sub_data'] = []
                sub_subject_dimension_list = await  SubjectDimension.find(
                    dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=subject_dimension.cid)).to_list(None)
                for sub_subject_dimension in sub_subject_dimension_list:
                    sub_tmp_dict = {}
                    if sub_subject_dimension:
                        sub_tmp_dict['title'] = sub_subject_dimension.title
                        sub_tmp_dict['code'] = sub_subject_dimension.code
                    temp_dict['sub_data'].append(sub_tmp_dict)
                data_list.append(temp_dict)

            first_column_list = self.__get_column_list(subject_column_list)
            second_colum_list = [u'维度名称', u'子维度名称', '编号']
            work_book = self.__create_common_excel(first_column_list, second_colum_list, data_list=data_list,
                                                   options=options)
            self.set_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.set_header('Content-Disposition', 'attachment; filename=' + filename)
            self.write(work_book)
            self.finish()
        except Exception as e:
            logger.error(str(e))

    def __get_column_list(self, column_list_middle):
        """
        拼接列名
        :param column_list_middle: 动态列名
        :return:
        """
        column_list_start = [u'Order', u'题目ID', u'一级知识点', u'二级知识点']
        column_list_end = [u'答案解析', u'题目', u'答案（大写字母）', u'选项']
        column_list = column_list_start + column_list_middle + column_list_end
        return column_list

    def __create_common_excel(self, first_column_list, second_column_list, data_list, options={}):
        """
        生成excel 模板
        :param first_column_list: 题目列名
        :param second_column_list: 维度对照表列明
        :param data_list: 维度数据
        :param options:
        :return:
        """
        output = BytesIO()
        workbook = Workbook(output, {'in_memory': True})
        # sheet 1名称
        worksheet_subject = workbook.add_worksheet(options['sheet_name1'] if 'sheet_name1' in options else None)
        line_index = 0  # 起始line
        first_column_num = len(first_column_list)  # 列总数
        worksheet_subject.set_column(0, first_column_num - 1, 14)
        column_format = workbook.add_format({'bold': '1', 'valign': 'vcenter', 'align': 'center',
                                             'font_name': 'Microsoft YaHei'})
        worksheet_subject.set_row(line_index, 20, column_format)
        for index, column in enumerate(first_column_list):
            if column == u'选项':
                worksheet_subject.merge_range(line_index, index, line_index, index + 4, data=column,
                                              cell_format=column_format)
            else:
                worksheet_subject.write_string(line_index, index, column, column_format)
        worksheet_subject.write_string(1, 0, '1', column_format)
        worksheet_subject.write_string(1, 1, '200201904150026', column_format)
        worksheet_subject.write_string(1, 2, '科学观念', column_format)
        worksheet_subject.write_string(1, 3, '从自然本身理解自然', column_format)
        worksheet_subject.write_string(1, 4, '1', column_format)
        worksheet_subject.write_string(1, 5, '3', column_format)
        worksheet_subject.write_string(1, 6, '4', column_format)
        worksheet_subject.write_string(1, 7, '娱乐时尚，穿着品味', column_format)
        worksheet_subject.write_string(1, 8, '最高的娱乐品味是什么？', column_format)
        worksheet_subject.write_string(1, 9, 'E', column_format)
        worksheet_subject.write_string(1, 10, '衣服', column_format)
        worksheet_subject.write_string(1, 11, '背包', column_format)
        worksheet_subject.write_string(1, 12, '鞋子', column_format)
        worksheet_subject.write_string(1, 13, '手表', column_format)
        worksheet_subject.write_string(1, 14, '以上全是', column_format)
        # sheet 2 维度对照表
        worksheet_dimension = workbook.add_worksheet(options['sheet_name2'] if 'sheet_name2' in options else None)
        secod_column_num = len(second_column_list)  # 列总数
        worksheet_dimension.set_column(0, secod_column_num - 1, 14)
        worksheet_dimension.set_row(line_index, 20, column_format)
        for index, column in enumerate(second_column_list):
            worksheet_dimension.write_string(line_index, index, column, column_format)

        data_format = workbook.add_format({'valign': 'vcenter', 'align': 'center',
                                           'font_name': 'Microsoft YaHei'})
        row = 1
        for data in data_list:
            title = data.get('title')
            sub_data_list = data.get('sub_data')
            row_merge = 1
            if sub_data_list:
                row_merge = len(sub_data_list)
                for index, sub_data in enumerate(sub_data_list):
                    sub_title = sub_data.get('title')
                    sub_code = sub_data.get('code')
                    worksheet_dimension.write_string(row + index, 1, sub_title, data_format)
                    worksheet_dimension.write_string(row + index, 2, sub_code, data_format)
            if row_merge > 1:
                worksheet_dimension.merge_range(row, 0, row + row_merge - 1, 0, title, data_format)
            else:
                worksheet_dimension.write_string(row, 0, title, data_format)
            row += row_merge
        # 　一级知识点
        first_knowledge_length = len(KNOWLEDGE_FIRST_LEVEL_DICT)
        worksheet_dimension.merge_range(row, 0, row + first_knowledge_length - 1, 0, '一级知识点', data_format)
        for index, first_knowledge in enumerate(list(KNOWLEDGE_FIRST_LEVEL_DICT.values())):
            worksheet_dimension.merge_range(row + index, 1, row + index, 2, first_knowledge, data_format)
        #  二级知识点
        second_knowledge_length = len(KNOWLEDGE_SECOND_LEVEL_DICT)
        worksheet_dimension.merge_range(row + first_knowledge_length, 0,
                                        row + first_knowledge_length + second_knowledge_length - 1, 0, '二级知识点',
                                        data_format)
        for index, second_knowledge in enumerate(list(KNOWLEDGE_SECOND_LEVEL_DICT.values())):
            worksheet_dimension.merge_range(row + first_knowledge_length + index, 1, row + first_knowledge_length + index, 2,second_knowledge, data_format)
        workbook.close()
        return output.getvalue()


URL_MAPPING_LIST = [
    url(r'/backoffice/subject/list/', SubjectListViewHandler, name='backoffice_subject_list'),
    url(r'/backoffice/subject/add/', SubjectAddViewHandler, name='backoffice_subject_add'),
    url(r'/backoffice/subject/edit/([0-9a-zA-Z_]+)/', SubjectEditViewHandler, name='backoffice_subject_edit'),
    url(r'/backoffice/subject/detail/([0-9a-zA-Z_]+)/', SubjectDetailViewHandler, name='backoffice_subject_detail'),
    url(r'/backoffice/subject/delete/([0-9a-zA-Z_]+)/', SubjectDeleteViewHandler, name='backoffice_subject_delete'),
    url(r'/backoffice/subject/status_switch/([0-9a-zA-Z_]+)/', SubjectStatusSwitchViewHandler,
        name='backoffice_subject_status_switch'),
    url(r'/backoffice/subject/batch_operate/', SubjectBatchOperationViewHandler,
        name='backoffice_subject_batch_operate'),
    url(r'/backoffice/subject/import/', SubjectImportViewHandler, name='backoffice_subject_import'),
    url(r'/backoffice/subject/download_template/', SubjectDownloadTemplatetViewHandler,
        name='backoffice_subject_download_template')

]
