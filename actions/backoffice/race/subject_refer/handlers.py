#!/usr/bin/python


import datetime
import traceback

from actions.backoffice.race.utils import get_menu
from pymongo import UpdateOne
from tornado.web import url

from commons.page_utils import Paging
from db import STATUS_SUBJECT_ACTIVE, STATUS_SUBJECT_INACTIVE
from db.models import Subject, SubjectOption, UploadFiles, RaceSubjectRefer
from enums import PERMISSION_TYPE_MINIAPP_RACE_SUBJECT_MANAGEMENT, KEY_SESSION_USER_MENU
from logger import log_utils
from motorengine.stages import MatchStage, LookupStage
from web import decorators, menu_utils
from web.base import BaseHandler

logger = log_utils.get_logging()


class RaceSubjectListViewHandler(BaseHandler):
    @decorators.render_template('backoffice/race/refer_subject/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_SUBJECT_MANAGEMENT)
    async def get(self):
        h_lookup_stage = LookupStage(Subject, 'subject_cid', 'cid', 'subject_list')
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        if race_cid:
            query_params = {'race_cid': race_cid}
            kw_name = self.get_argument('kw_name', '')
            kw_difficulty = self.get_argument('kw_difficulty', '')
            category_use = self.get_argument('category_use', '')
            query_subject_params = {}
            if kw_name:
                query_subject_params['$or'] = [
                    {"custom_code": {'$regex': kw_name, '$options': 'i'}},
                    {"title": {'$regex': kw_name, '$options': 'i'}},
                ]
                subject_cid_list = await Subject.distinct('cid', filtered=query_subject_params)
                query_params['$and'] = [
                    {'subject_cid': {'$in': subject_cid_list}}
                ]
            if kw_difficulty:
                query_subject_params['difficulty'] = int(kw_difficulty)
                subject_cid_list = await Subject.distinct('cid', filtered=query_subject_params)
                query_params['$and'] = [
                    {'subject_cid': {'$in': subject_cid_list}}
                ]
            if category_use:
                query_subject_params['category'] = int(category_use)
                subject_cid_list = await Subject.distinct('cid', filtered=query_subject_params)
                query_params['$and'] = [
                    {'subject_cid': {'$in': subject_cid_list}}
                ]

            # 分页 START
            per_page_quantity = int(self.get_argument('per_page_quantity', 10))
            to_page_num = int(self.get_argument('page', 1))
            page_url = '%s?page=$page&per_page_quantity=%s&race_cid=%s&kw_name=%s&kw_difficulty=%s&category_use=%s' % (
                self.reverse_url("backoffice_race_subject_list"), per_page_quantity, race_cid, kw_name,
                kw_difficulty, category_use)
            paging = Paging(page_url, RaceSubjectRefer, current_page=to_page_num, pipeline_stages=[h_lookup_stage],
                            items_per_page=per_page_quantity, **query_params)
            await paging.pager()
            # 分页 END
        return locals()


class RaceReferSubjectListViewHandler(BaseHandler):
    @decorators.render_template('backoffice/race/refer_subject/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_SUBJECT_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        menu_list = await get_menu(self, 'config', race_cid)
        if race_cid:
            r_look_stage = LookupStage(RaceSubjectRefer, 'cid', 'subject_cid', 'race_subject_list')
            #  已经引用过的题目,在引用页面中不展示
            race_refer_cid_list = await RaceSubjectRefer.distinct('subject_cid', filtered={'race_cid': race_cid})
            query_params = {'cid': {'$nin': race_refer_cid_list}}
            kw_name = self.get_argument('kw_name', '')
            kw_difficulty = self.get_argument('kw_difficulty', '')
            category_use = self.get_argument('category_use', '')
            query_params['status'] = STATUS_SUBJECT_ACTIVE
            if kw_name:
                query_params['$or'] = [
                    {"custom_code": {'$regex': kw_name, '$options': 'i'}},
                    {"title": {'$regex': kw_name, '$options': 'i'}},
                    {"code": {'$regex': kw_name, '$options': 'i'}}
                ]
            if kw_difficulty:
                query_params['difficulty'] = int(kw_difficulty)
            if category_use:
                query_params['category'] = int(category_use)

            # 分页 START
            per_page_quantity = int(self.get_argument('per_page_quantity', 10))
            to_page_num = int(self.get_argument('page', 1))
            page_url = '%s?page=$page&per_page_quantity=%s&race_cid=%s&kw_name=%s&kw_difficulty=%s&category_use=%s' % (
                self.reverse_url("backoffice_race_subject_refer_list"), per_page_quantity, race_cid, kw_name,
                kw_difficulty, category_use)
            paging = Paging(page_url, Subject, current_page=to_page_num,
                            items_per_page=per_page_quantity,
                            sort=['custom_code'], **query_params)
            await paging.pager()
            # 分页 END
        return locals()


class RaceSubjectAddViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_SUBJECT_MANAGEMENT)
    async def post(self, subject_cid):
        r_dict = {'code': 0}
        try:
            race_cid = self.get_argument('race_cid', '')
            if race_cid:
                subject = await Subject.find_one(filtered={'cid': subject_cid})
                refer_subject = await RaceSubjectRefer.find_one(
                    filtered={'race_cid': race_cid, 'subject_cid': subject.cid})
                if not refer_subject:
                    refer_subject = RaceSubjectRefer()
                    refer_subject.race_cid = race_cid
                    refer_subject.subject_cid = subject_cid
                    refer_subject.title = subject.title
                    refer_subject.dimension_dict = subject.dimension_dict
                    refer_subject.created_dt = datetime.datetime.now()
                    refer_subject.created_id = self.current_user.oid
                    await refer_subject.save()
                    r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceSubjectDetailViewHandler(BaseHandler):
    @decorators.render_template('backoffice/race/refer_subject/detail_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_SUBJECT_MANAGEMENT)
    async def get(self, subject_id):
        race_cid = self.get_argument('race_cid', '')
        if race_cid:
            menu_list = await get_menu(self, 'config', race_cid)
        match = MatchStage({'cid': subject_id})
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
            difficulty = subject.difficulty
            category = subject.category
            option_list = subject.subject_option_list
            file_list = subject.upload_files_list
            if file_list:
                file_doc = file_list[0]

        return locals()


class RaceSubjectDeleteViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_SUBJECT_MANAGEMENT)
    async def post(self, subject_cid):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid:
                if subject_cid:
                    refer_subject = await RaceSubjectRefer.find_one(
                        filtered={'race_cid': race_cid, 'subject_cid': subject_cid})
                    await refer_subject.delete()
            r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceSubjectStatusSwitchViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_SUBJECT_MANAGEMENT)
    async def post(self, subject_cid):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid:
                status = self.get_argument('status', False)
                if status == 'true':
                    status = STATUS_SUBJECT_ACTIVE
                else:
                    status = STATUS_SUBJECT_INACTIVE
                refer_subject = await RaceSubjectRefer.find_one(
                    filtered={'race_cid': race_cid, 'subject_cid': subject_cid})
                if refer_subject:
                    refer_subject.status = status
                    refer_subject.updated_dt = datetime.datetime.now()
                    refer_subject.updated_id = self.current_user.oid
                    await refer_subject.save()
                r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceSubjectBatchOperationViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_SUBJECT_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid:
                subject_cid_list = self.get_body_arguments('subject_cid_list[]', [])
                if subject_cid_list:
                    operate = self.get_argument('operate', None)
                    if operate is not None:
                        if int(operate) == 1:
                            update_requests = []
                            for subject_cid in subject_cid_list:
                                update_requests.append(UpdateOne({'subject_cid': subject_cid, 'race_cid': race_cid},
                                                                 {'$set': {'status': STATUS_SUBJECT_ACTIVE,
                                                                           'updated_dt': datetime.datetime.now(),
                                                                           'updated_id': self.current_user.oid}}))
                            await RaceSubjectRefer.update_many(update_requests)
                        elif int(operate) == 0:
                            update_requests = []
                            for subject_cid in subject_cid_list:
                                update_requests.append(UpdateOne({'subject_cid': subject_cid, 'race_cid': race_cid},
                                                                 {'$set': {'status': STATUS_SUBJECT_INACTIVE,
                                                                           'updated_dt': datetime.datetime.now(),
                                                                           'updated_id': self.current_user.oid}}))
                            await RaceSubjectRefer.update_many(update_requests)
                        elif int(operate) == 2:
                            subject_list = list()
                            for subject_cid in subject_cid_list:
                                subject = await Subject.find_one(filtered={'cid': subject_cid})
                                refer_subject = await RaceSubjectRefer.find_one(
                                    filtered={'race_cid': race_cid, 'subject_cid': subject.cid})
                                if not refer_subject:
                                    subject_list.append(
                                        RaceSubjectRefer(
                                            race_cid=race_cid,
                                            subject_cid=subject.cid,
                                            title=subject.title,
                                            status=subject.status,
                                            dimension_dict=subject.dimension_dict,
                                            created_dt=datetime.datetime.now(),
                                            created_id=self.current_user.oid
                                        )
                                    )
                            if subject_list:
                                await RaceSubjectRefer.insert_many(subject_list)
                                r_dict['operate'] = operate
                        elif int(operate) == -1:
                            await RaceSubjectRefer.delete_many(
                                filtered={'race_cid': race_cid, 'subject_cid': {'$in': subject_cid_list}})
                r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceSubjectImportViewHandler(BaseHandler):
    """
    题目导入
    """

    @decorators.render_template('backoffice/race/refer_subject/upload_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_SUBJECT_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        return locals()

    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_SUBJECT_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        try:
            if race_cid:
                subject_code = self.get_argument('subject_code')
                subject_code_list = subject_code.split('\r\n')
                subject_code_list = set(subject_code_list)
                subject_import_list = list()
                for subject_code in subject_code_list:
                    subject = await Subject.find_one(
                        filtered={'custom_code': subject_code, 'status': STATUS_SUBJECT_ACTIVE})
                    if subject:
                        refer_subject = await RaceSubjectRefer.find_one(
                            filtered={'race_cid': race_cid, 'subject_cid': subject.cid})
                        if not refer_subject:
                            subject_import_list.append(
                                RaceSubjectRefer(
                                    race_cid=race_cid,
                                    subject_cid=subject.cid,
                                    title=subject.title,
                                    status=subject.status,
                                    dimension_dict=subject.dimension_dict,
                                    created_dt=datetime.datetime.now(),
                                    created_id=self.current_user.oid
                                )
                            )
                if subject_import_list:
                    await RaceSubjectRefer.insert_many(subject_import_list)
                    r_dict['success_import_count'] = len(subject_import_list)
                    r_dict['code'] = 1
                if not subject_import_list:
                    r_dict['code'] = -1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceReferSubjectAllImportHandler(BaseHandler):
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_SUBJECT_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        race_cid = self.get_argument('race_cid', '')
        r_dict = {'code': 0}
        try:
            if race_cid:
                refer_subject_list = []
                exist_refer_subject_list = await RaceSubjectRefer.distinct('subject_cid',
                                                                           filtered={'race_cid': race_cid})
                kw_name = self.get_argument('kw_name', '')
                kw_difficulty = self.get_argument('kw_difficulty', '')
                category_use = self.get_argument('category_use', '')
                query_params = {'status': STATUS_SUBJECT_ACTIVE, 'cid': {'$nin': exist_refer_subject_list}}
                subject_cursor = await Subject.find(filtered=query_params).to_list(None)
                if kw_name:
                    query_params['$or'] = [
                        {"custom_code": {'$regex': kw_name, '$options': 'i'}},
                        {"title": {'$regex': kw_name, '$options': 'i'}},
                        {"code": {'$regex': kw_name, '$options': 'i'}}
                    ]
                if kw_difficulty:
                    query_params['difficulty'] = int(kw_difficulty)
                if category_use:
                    query_params['category'] = int(category_use)
                subject_cursor = Subject.find(filtered=query_params)
                while await subject_cursor.fetch_next:
                    subject = subject_cursor.next_object()
                    if not subject:
                        break
                    refer_subject_list.append(
                        RaceSubjectRefer(
                            race_cid=race_cid,
                            subject_cid=subject.cid,
                            title=subject.title,
                            status=subject.status,
                            dimension_dict=subject.dimension_dict,
                            created_dt=datetime.datetime.now(),
                            created_id=self.current_user.oid
                        )
                    )
                if refer_subject_list:
                    await RaceSubjectRefer.insert_many(refer_subject_list)
                    r_dict['code'] = 1
                else:
                    r_dict['code'] = -1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/backoffice/race/subject/list/', RaceSubjectListViewHandler, name='backoffice_race_subject_list'),
    url(r'/backoffice/race/subject/refer/list/', RaceReferSubjectListViewHandler,
        name='backoffice_race_subject_refer_list'),
    url(r'/backoffice/race/subject/refer/add/([0-9a-zA-Z_]+)/', RaceSubjectAddViewHandler,
        name='backoffice_race_subject_refer_add'),
    url(r'/backoffice/race/subject/detail/([0-9a-zA-Z_]+)/', RaceSubjectDetailViewHandler,
        name='backoffice_race_subject_detail'),
    url(r'/backoffice/race/subject/delete/([0-9a-zA-Z_]+)/', RaceSubjectDeleteViewHandler,
        name='backoffice_race_subject_delete'),
    url(r'/backoffice/race/subject/status_switch/([0-9a-zA-Z_]+)/', RaceSubjectStatusSwitchViewHandler,
        name='backoffice_race_subject_status_switch'),
    url(r'/backoffice/race/subject/batch_operate/', RaceSubjectBatchOperationViewHandler,
        name='backoffice_race_subject_batch_operate'),
    url(r'/backoffice/race/subject/import/', RaceSubjectImportViewHandler, name='backoffice_race_subject_import'),
    url(r'/backoffice/race/subject/all/import/', RaceReferSubjectAllImportHandler,
        name='backoffice_race_subject_all_import')
]
