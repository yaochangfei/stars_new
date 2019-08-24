# !/usr/bin/python
# -*- coding:utf-8 -*-
import traceback

from datetime import datetime

from bson import ObjectId
from pymongo import UpdateOne
from tornado.web import url

from commons.page_utils import Paging
from db import STATUS_QUESTIONNAIRE_ACTIVE
from db.models import Questionnaire
from enums import PERMISSION_TYPE_QUESTIONNAIRE_RELEASE_MANAGEMENT
from logger import log_utils
from web import decorators
from web.base import BaseHandler

logger = log_utils.get_logging()


class QuestionnaireListViewHandler(BaseHandler):
    """
    问卷列表
    """

    @decorators.render_template('backoffice/questionnaires/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_RELEASE_MANAGEMENT)
    async def get(self):
        search_title = self.get_argument('search_title', '')

        query_param = {}
        and_query_param = [{'record_flag': 1}]
        if search_title:
            and_query_param.append({'title': {'$regex': search_title}})
        if and_query_param:
            query_param['$and'] = and_query_param

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&search_title=%s' % (
            self.reverse_url("backoffice_questionnaire_list"), per_page_quantity, search_title)
        paging = Paging(page_url, Questionnaire, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'], **query_param)
        await paging.pager()

        return locals()


class QuestionnaireAddViewHandler(BaseHandler):
    """
    发布问卷
    """

    @decorators.render_template('backoffice/questionnaires/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_RELEASE_MANAGEMENT)
    async def get(self):
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_RELEASE_MANAGEMENT)
    async def post(self):
        res = {'code': 0}
        code = self.get_argument('code')
        title = self.get_argument('title')
        url = self.get_argument('url')
        report_url = self.get_argument('report_url')
        download_url = self.get_argument('download_url')
        process_url = self.get_argument('process_url')
        status = int(self.get_argument('status', STATUS_QUESTIONNAIRE_ACTIVE))
        if title and url and status and code:
            try:
                # 校验问卷编号
                exist_count = await Questionnaire.count(dict(code=code))
                if exist_count:
                    res['code'] = -2
                else:
                    questionnaire = Questionnaire(code=code, title=title)
                    questionnaire.url = url
                    questionnaire.report_url = report_url
                    questionnaire.download_url = download_url
                    questionnaire.process_url = process_url
                    questionnaire.status = status
                    questionnaire.created_id = self.current_user.oid
                    questionnaire.updated_id = self.current_user.oid

                    questionnaire_id = await questionnaire.save()

                    res['code'] = 1
                    res['questionnaire_id'] = questionnaire_id
            except Exception:
                logger.error(traceback.format_exc())
        else:
            res['code'] = -1
        return res


class QuestionnaireStatusEditViewHandler(BaseHandler):
    """
    修改问卷状态
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_RELEASE_MANAGEMENT)
    async def post(self):
        res = {'code': 0}
        questionnaire_ids = self.get_arguments('questionnaire_ids[]')
        target_status = self.get_argument('target_status')
        if questionnaire_ids and target_status:
            try:
                update_requests = []
                for questionnaire_id in questionnaire_ids:
                    update_requests.append(UpdateOne({'_id': ObjectId(questionnaire_id)},
                                                     {'$set': {'status': int(target_status),
                                                               'updated_dt': datetime.now(),
                                                               'updated_id': self.current_user.oid}}))
                if update_requests:
                    modified_count = await Questionnaire.update_many(update_requests)
                    res['code'] = 1
                    res['modified_count'] = modified_count
            except Exception:
                logger.error(traceback.format_exc())
        return res


class QuestionnaireDeleteViewHandler(BaseHandler):
    """
    删除问卷
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_RELEASE_MANAGEMENT)
    async def post(self):
        res = {'code': 0}
        questionnaire_ids = self.get_arguments('questionnaire_ids[]')
        if questionnaire_ids:
            try:
                await Questionnaire.delete_by_ids(questionnaire_ids)
                res['code'] = 1
            except Exception:
                logger.error(traceback.format_exc())

        return res


URL_MAPPING_LIST = [
    url(r'/backoffice/questionnaire/list/', QuestionnaireListViewHandler, name='backoffice_questionnaire_list'),
    url(r'/backoffice/questionnaire/add/', QuestionnaireAddViewHandler, name='backoffice_questionnaire_add'),
    url(r'/backoffice/questionnaire/status/', QuestionnaireStatusEditViewHandler,
        name='backoffice_questionnaire_status'),
    url(r'/backoffice/questionnaire/delete/', QuestionnaireDeleteViewHandler, name='backoffice_questionnaire_delete')
]
