# !/usr/bin/python
# -*- coding:utf-8 -*-

import collections
import copy
import traceback
import os
from datetime import datetime

from bson import ObjectId
from pymongo import UpdateOne
from tornado.web import url

from commons.common_utils import md5, get_random_str, get_increase_code
from commons.page_utils import Paging
from db import STATUS_USER_ACTIVE, STATUS_ROLE_ACTIVE
from db.model_utils import get_administrative_division
from enums import PERMISSION_TYPE_USER_MANAGEMENT, ALL_BACKOFFICE_ASSIGNABLE_PERMISSION_TYPE_DICT, \
    PERMISSION_TYPE_SYSTEM_DOCKING_MANAGEMENT, KEY_INCREASE_USER, REVIEW_REPORT_PERMS_LIST
from db.models import User, Role, AdministrativeDivision, Films,Tvs
from logger import log_utils
from web import BaseHandler, decorators
from services import obs_service

logger = log_utils.get_logging()


class TvListViewHandler(BaseHandler):
    """
    电视剧列表
    """

    @decorators.render_template('backoffice/tvs/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def get(self):
        search_name = self.get_argument('search_name', '')

        query_param = {}
        and_query_param = [{'db_mark': {'$ne': ''}},
                           {'release_time': {'$ne': ''}}]

        if search_name:
            and_query_param.append({'$or': [{'name': {'$regex': search_name}},
                                            {'actor': {'$regex': search_name}},
                                            {'director': {'$regex': search_name}},
                                            {'label': {'$regex': search_name}},
                                            ]})

        if and_query_param:
            query_param['$and'] = and_query_param

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&search_name=%s' % \
                   (self.reverse_url("backoffice_tv_list"), per_page_quantity, search_name)
        paging = Paging(page_url, Tvs, current_page=to_page_num, items_per_page=per_page_quantity, **query_param)
        await paging.pager()

        return locals()


class TvEditViewHandler(BaseHandler):
    """
    编辑电视剧
    """

    @decorators.render_template('backoffice/tvs/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def get(self, tv_id):
        tv = await Tvs.get_by_id(tv_id)

        return {'tv': tv}

    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    @decorators.render_json
    async def post(self, tv_id):
        res = {'code': 0}
        tv= await Tvs.get_by_id(tv_id)
        banner_files = self.request.files['banner_pic']
        if banner_files:
            banner_file = banner_files[0]
            banner_file_name = banner_file.filename
            print(datetime.now())
            # resp = obs_service.upload_file_to_obs(banner_file, banner_file_name)
            local_path, f_name = obs_service.upload_file_to_local(banner_file, banner_file_name)
            print(datetime.now())
            print(local_path, f_name)
            resp = obs_service.upload_file_to_obs(local_path, f_name)
            # film.banner_pic = resp
            # await film.save()
            # res['code']=1
            # 上传成功
            if resp.status < 300:
                tv.banner_pic = resp.body.objectUrl
                if tv.al_name == '':
                    tv.al_name = []
                await tv.save()
                res['code'] = 1
            else:
                # 上传失败
                res['code'] = -1

            if os.path.exists(local_path):
                os.remove(local_path)
        else:
            res['code'] = -2
        return res


class TvStatusEditViewHandler(BaseHandler):
    """
    修改电视剧状态
    """

    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = {'code': 0}
        tv_ids = self.get_arguments('manager_ids[]')
        target_status = self.get_argument('target_status')

        if tv_ids and target_status:
            try:
                update_requests = []
                for tv_id in tv_ids:
                    update_requests.append(UpdateOne({'_id': ObjectId(tv_id)},
                                                     {'$set': {'status': int(target_status),
                                                               'updated_dt': datetime.now(),
                                                               'updated_id': self.current_user.oid}}))
                if update_requests:
                    modified_count = await Tvs.update_many(update_requests)
                    res['code'] = 1
                    res['modified_count'] = modified_count
            except Exception:
                logger.error(traceback.format_exc())
        return res


class TvBannerStatusEditViewHandler(BaseHandler):
    """
    修改电视剧是否banner状态
    """

    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = {'code': 0}
        tv_ids = self.get_arguments('manager_ids[]')
        target_status = self.get_argument('target_status')

        if tv_ids and target_status:
            try:
                update_requests = []
                for tv_id in tv_ids:
                    update_requests.append(UpdateOne({'_id': ObjectId(tv_id)},
                                                     {'$set': {'banner_status': int(target_status),
                                                               'updated_dt': datetime.now(),
                                                               'updated_id': self.current_user.oid}}))
                if update_requests:
                    modified_count = await Tvs.update_many(update_requests)
                    res['code'] = 1
                    res['modified_count'] = modified_count
            except Exception:
                logger.error(traceback.format_exc())
        return res





URL_MAPPING_LIST = [
    url(r'/backoffice/tv/list/', TvListViewHandler, name='backoffice_tv_list'),
    url(r'/backoffice/tv/edit/([0-9a-zA-Z_]+)/', TvEditViewHandler, name='backoffice_tv_edit'),
    url(r'/backoffice/tv/status/', TvStatusEditViewHandler, name='backoffice_tv_status'),
    url(r'/backoffice/tv/banner_status/', TvBannerStatusEditViewHandler, name='backoffice_tv_banner_status'),

]
