#!/usr/bin/python
# -*- coding:utf-8 -*-

import datetime
import traceback

from bson import ObjectId
from pymongo import UpdateOne
from tornado.web import url

from commons.page_utils import Paging
from commons.upload_utils import save_upload_file, drop_disk_file_by_cid
from db import STATUS_GAME_DAN_GRADE_ACTIVE, STATUS_GAME_DAN_GRADE_INACTIVE, STATUS_SUBJECT_CHOICE_RULE_ACTIVE, \
    CATEGORY_UPLOAD_FILE_IMG_GAME_DAN_GRADE
from db.models import UploadFiles, GameDanGrade, SubjectChoiceRules
from enums import PERMISSION_TYPE_MINIAPP_GAME_DAN_GRADE_MANAGEMENT
from settings import SERVER_PROTOCOL, SERVER_HOST
from logger import log_utils
from motorengine.stages import MatchStage, LookupStage
from settings import STATIC_URL_PREFIX
from web import decorators
from web.base import BaseHandler

logger = log_utils.get_logging()


class DanGradeListViewHandler(BaseHandler):
    """
    游戏段位列表
    """

    @decorators.render_template('backoffice/dan_grade/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DAN_GRADE_MANAGEMENT)
    async def get(self):
        query_params = {'record_flag': 1}
        dan_grade_name = self.get_argument('dan_grade_name', '')
        if dan_grade_name:
            query_params['$or'] = [
                {"title": {'$regex': dan_grade_name, '$options': 'i'}}
            ]
        # 分页 START
        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&dan_grade_name=%s' % (
            self.reverse_url("backoffice_dan_grade_list"), per_page_quantity,dan_grade_name)
        paging = Paging(page_url, GameDanGrade,
                        pipeline_stages=[LookupStage(UploadFiles, 'thumbnail', 'cid', 'image_list')],
                        current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['index'], **query_params)
        await paging.pager()
        # 分页 END
        #  段位缩略图的字典 在第几个位置有图片
        thumbnail_dict = dict()
        for index, thumbnail in enumerate(paging.page_items):
            if thumbnail.image_list:
                title_img_url = '%s://%s%s%s%s' % (
                    SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/', thumbnail.image_list[0].title)
                thumbnail_dict[index] = title_img_url
        print(thumbnail_dict)
        return locals()


class DanGradeAddViewHandler(BaseHandler):
    """
    新增段位
    """

    @decorators.render_template('backoffice/dan_grade/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DAN_GRADE_MANAGEMENT)
    async def get(self):
        subject_choice_rules_list = await SubjectChoiceRules.find(
            dict(status=STATUS_SUBJECT_CHOICE_RULE_ACTIVE)).to_list(None)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DAN_GRADE_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        game_dan_grade_id = None
        try:
            index = self.get_argument('index', None)
            title = self.get_argument('title', None)
            unlock_stars = self.get_argument('unlock_stars', None)
            # quantity = self.get_argument('quantity', None)
            rule_cid = self.get_argument('rule_cid', None)
            content = self.get_argument('content', None)
            status = self.get_argument('status', None)  # 状态
            if index and title and unlock_stars  and rule_cid:
                r_count = await GameDanGrade.count(dict(index=int(index)))
                t_count = await GameDanGrade.count(dict(title=title))
                if r_count > 0:
                    r_dict['code'] = -6
                elif t_count > 0:
                    r_dict['code'] = -7
                else:
                    if status == 'on':
                        status = STATUS_GAME_DAN_GRADE_ACTIVE
                    else:
                        status = STATUS_GAME_DAN_GRADE_INACTIVE
                    image_cid = None
                    image_cid_list = await save_upload_file(self, 'image',
                                                            category=CATEGORY_UPLOAD_FILE_IMG_GAME_DAN_GRADE)
                    if image_cid_list:
                        image_cid = image_cid_list[0]
                    game_dan_grade = GameDanGrade(index=int(index), title=title, unlock_stars=int(unlock_stars),
                                                  rule_cid=rule_cid)
                    game_dan_grade.thumbnail = image_cid
                    game_dan_grade.status = status
                    game_dan_grade.content = content
                    game_dan_grade.created_id = self.current_user.oid
                    game_dan_grade.updated_id = self.current_user.oid
                    game_dan_grade_id = await game_dan_grade.save()
                    r_dict['code'] = 1
            else:
                if not index:
                    r_dict['code'] = -1
                if not title:
                    r_dict['code'] = -2
                if not unlock_stars:
                    r_dict['code'] = -3
                # if not quantity:
                #     r_dict['code'] = -4
                if not rule_cid:
                    r_dict['code'] = -5
        except RuntimeError:
            if game_dan_grade_id:
                game_dan_grade = await GameDanGrade.get_by_id(game_dan_grade_id)
                if game_dan_grade:
                    await GameDanGrade.delete_by_ids([game_dan_grade.oid])
            logger.error(traceback.format_exc())
        return r_dict


class DanGradeEditViewHandler(BaseHandler):
    """
    编辑段位
    """

    @decorators.render_template('backoffice/dan_grade/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DAN_GRADE_MANAGEMENT)
    async def get(self, dan_grade_id):
        match = MatchStage({'_id': ObjectId(dan_grade_id)})
        lookup_files = LookupStage(UploadFiles, 'thumbnail', 'cid')
        lookup_rules = LookupStage(SubjectChoiceRules, 'rule_cid', 'cid')
        dan_grade_list = await GameDanGrade.aggregate([match, lookup_files, lookup_rules]).to_list(None)
        subject_choice_rules_list = await SubjectChoiceRules.find(
            dict(status=STATUS_SUBJECT_CHOICE_RULE_ACTIVE)).to_list(None)
        dan_grade = None
        file_doc = None
        choice_rule = None
        if dan_grade_list:
            dan_grade = dan_grade_list[0]
            file_list = dan_grade.upload_files_list
            if file_list:
                file_doc = file_list[0]
            if dan_grade.subject_choice_rules_list:
                choice_rule = dan_grade.subject_choice_rules_list[0]
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DAN_GRADE_MANAGEMENT)
    async def post(self, dan_grade_id):
        r_dict = {'code': 0}
        try:
            game_dan_grade = await GameDanGrade.get_by_id(dan_grade_id)
            if game_dan_grade:
                index = self.get_argument('index', None)
                title = self.get_argument('title', None)
                unlock_stars = self.get_argument('unlock_stars', None)
                # quantity = self.get_argument('quantity', None)
                rule_cid = self.get_argument('rule_cid', None)
                content = self.get_argument('content', None)
                status = self.get_argument('status', None)  # 状态
                image_cid = self.get_argument('image_cid', None)
                if index and title and unlock_stars  and rule_cid:
                    r_count = await GameDanGrade.count(dict(index=int(index), id={'$ne': ObjectId(dan_grade_id)}))
                    t_count = await GameDanGrade.count(dict(title=title, id={'$ne': ObjectId(dan_grade_id)}))
                    if r_count > 0:
                        r_dict['code'] = -6
                    elif t_count > 0:
                        r_dict['code'] = -7
                    else:
                        if status == 'on':
                            status = STATUS_GAME_DAN_GRADE_ACTIVE
                        else:
                            status = STATUS_GAME_DAN_GRADE_INACTIVE
                        if not image_cid:
                            if self.request.files:
                                image_cid_list = await save_upload_file(self, 'image',
                                                                        file_cid=game_dan_grade.thumbnail,
                                                                        category=CATEGORY_UPLOAD_FILE_IMG_GAME_DAN_GRADE)
                                if image_cid_list:
                                    image_cid = image_cid_list[0]
                            else:
                                image_cid = None
                                if game_dan_grade.thumbnail:
                                    await UploadFiles.delete_many({'cid': game_dan_grade.thumbnail})
                        game_dan_grade.index = int(index)
                        game_dan_grade.title = title
                        game_dan_grade.unlock_stars = int(unlock_stars)
                        # game_dan_grade.quantity = int(quantity)
                        game_dan_grade.rule_cid = rule_cid
                        game_dan_grade.thumbnail = image_cid
                        game_dan_grade.status = status
                        game_dan_grade.content = content
                        game_dan_grade.created_id = self.current_user.oid
                        game_dan_grade.updated_id = self.current_user.oid
                        await game_dan_grade.save()
                        r_dict['code'] = 1
                else:
                    if not index:
                        r_dict['code'] = -1
                    if not title:
                        r_dict['code'] = -2
                    if not unlock_stars:
                        r_dict['code'] = -3
                    # if not quantity:
                    #     r_dict['code'] = -4
                    if not rule_cid:
                        r_dict['code'] = -5
        except RuntimeError:
            if dan_grade_id:
                await GameDanGrade.delete_by_ids(dan_grade_id)
            logger.error(traceback.format_exc())
        return r_dict


class DanGradeDeleteViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DAN_GRADE_MANAGEMENT)
    async def post(self, dan_grade_id):
        r_dict = {'code': 0}
        try:
            game_dan_grade = await GameDanGrade.get_by_id(dan_grade_id)
            image_cid = game_dan_grade.thumbnail
            if image_cid:
                await drop_disk_file_by_cid(cid_list=image_cid)
            await game_dan_grade.delete()
            r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class DanGradeStatusSwitchViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DAN_GRADE_MANAGEMENT)
    async def post(self, dan_grade_id):
        r_dict = {'code': 0}
        try:
            status = self.get_argument('status', False)
            if status == 'true':
                status = STATUS_GAME_DAN_GRADE_ACTIVE
            else:
                status = STATUS_GAME_DAN_GRADE_INACTIVE
            game_dan_grade = await GameDanGrade.get_by_id(dan_grade_id)
            if game_dan_grade:
                game_dan_grade.status = status
                game_dan_grade.updated = datetime.datetime.now()
                game_dan_grade.updated_id = self.current_user.oid
                await game_dan_grade.save()
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class DanGradeBatchOperationViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_GAME_DAN_GRADE_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            game_dan_grade_id_list = self.get_body_arguments('dan_grade_id_list[]', [])
            if game_dan_grade_id_list:
                operate = self.get_argument('operate', None)
                if operate is not None:
                    game_dan_grade_id_list = [ObjectId(game_dan_grade_id) for game_dan_grade_id in
                                              game_dan_grade_id_list]
                    if int(operate) == 1:
                        update_requests = []
                        for game_dan_grade_id in game_dan_grade_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(game_dan_grade_id)},
                                                             {'$set': {'status': STATUS_GAME_DAN_GRADE_ACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await GameDanGrade.update_many(update_requests)
                    elif int(operate) == 0:
                        update_requests = []
                        for game_dan_grade_id in game_dan_grade_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(game_dan_grade_id)},
                                                             {'$set': {'status': STATUS_GAME_DAN_GRADE_INACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await GameDanGrade.update_many(update_requests)
                    elif int(operate) == -1:
                        image_cid_list = await GameDanGrade.distinct('image_cid',
                                                                     {'_id': {'$in': game_dan_grade_id_list},
                                                                      'image_cid': {'$ne': None}})
                        await GameDanGrade.delete_many({'_id': {'$in': game_dan_grade_id_list}})
                        await drop_disk_file_by_cid(image_cid_list)
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/backoffice/dan_grade/list/', DanGradeListViewHandler, name='backoffice_dan_grade_list'),
    url(r'/backoffice/dan_grade/add/', DanGradeAddViewHandler, name='backoffice_dan_grade_add'),
    url(r'/backoffice/dan_grade/edit/([0-9a-zA-Z_]+)/', DanGradeEditViewHandler, name='backoffice_dan_grade_edit'),
    url(r'/backoffice/dan_grade/delete/([0-9a-zA-Z_]+)/', DanGradeDeleteViewHandler,
        name='backoffice_dan_grade_delete'),
    url(r'/backoffice/dan_grade/status_switch/([0-9a-zA-Z_]+)/', DanGradeStatusSwitchViewHandler,
        name='backoffice_dan_grade_status_switch'),
    url(r'/backoffice/dan_grade/batch_operate/', DanGradeBatchOperationViewHandler,
        name='backoffice_dan_grade_batch_operate'),

]
