# !/usr/bin/python
# -*- coding:utf-8 -*-

import traceback
from datetime import datetime

from tornado.web import url

from commons.common_utils import get_random_str
from commons.page_utils import Paging
from db import STATUS_ROLE_ACTIVE, STATUS_ROLE_INACTIVE
from enums import PERMISSION_TYPE_ROLE_MANAGEMENT, ALL_BACKOFFICE_ASSIGNABLE_PERMISSION_TYPE_DICT, \
    PERMISSION_TYPE_SYSTEM_DOCKING_MANAGEMENT
from db.models import Role, User
from logger import log_utils
from web import BaseHandler, decorators

logger = log_utils.get_logging()


class RoleListViewHandler(BaseHandler):

    @decorators.render_template('backoffice/roles/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_ROLE_MANAGEMENT)
    async def get(self):
        query_params = {'record_flag': 1}

        # 分页 START
        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s' % (self.reverse_url("backoffice_role_list"), per_page_quantity)
        paging = Paging(page_url, Role, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'], **query_params)
        await paging.pager()
        # 分页 END

        return locals()


class RoleAddViewHandler(BaseHandler):

    @decorators.render_template('backoffice/roles/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_ROLE_MANAGEMENT)
    async def get(self):
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_ROLE_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            code = self.get_argument('code')
            title = self.get_argument('title')
            content = self.get_argument('content')
            status = self.get_argument('status')
            if code and title:
                r_count = await Role.count(dict(code=code))
                if r_count > 0:
                    r_dict['code'] = -3
                else:
                    if status == 'on':
                        status = STATUS_ROLE_ACTIVE
                    else:
                        status = STATUS_ROLE_INACTIVE

                    role = Role(code=code, title=title, status=status)
                    role.content = content
                    role.created_id = self.current_user.oid
                    role.updated_id = self.current_user.oid
                    role.needless = {'user_amount': 0}
                    role_id = await role.save()
                    if role_id:
                        r_dict['code'] = 1
            else:
                if not code:
                    r_dict['code'] = -1
                elif not title:
                    r_dict['code'] = -2
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RoleEditViewHandler(BaseHandler):

    @decorators.render_template('backoffice/roles/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_ROLE_MANAGEMENT)
    async def get(self, role_id):
        role = await Role.get_by_id(role_id)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_ROLE_MANAGEMENT)
    async def post(self, role_id):
        r_dict = {'code': 0}
        try:
            role = await Role.get_by_id(role_id)
            if role:
                title = self.get_argument('title', None)
                content = self.get_argument('content', None)
                status = self.get_argument('status', None)
                if title:
                    if status == 'on':
                        status = STATUS_ROLE_ACTIVE
                    else:
                        status = STATUS_ROLE_INACTIVE
                    role.title = title
                    role.content = content
                    role.status = status
                    role.updated_dt = datetime.now()
                    role.updated_id = self.current_user.oid
                    await role.save()

                    r_dict['code'] = 1
                else:
                    if not title:
                        r_dict['code'] = -2
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class RoleDeleteViewHandler(BaseHandler):

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_ROLE_MANAGEMENT)
    async def post(self, role_id):
        r_dict = {'code': 0}
        try:
            await Role.delete_by_ids([role_id])
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class RoleAssignPermissionViewHandler(BaseHandler):

    @decorators.render_template('backoffice/roles/perm_assign_view.html')
    @decorators.permission_required(PERMISSION_TYPE_ROLE_MANAGEMENT)
    async def get(self, role_id):
        role = await Role.get_by_id(role_id)
        sort_perm_list = sorted(ALL_BACKOFFICE_ASSIGNABLE_PERMISSION_TYPE_DICT.keys())
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_ROLE_MANAGEMENT)
    async def post(self, role_id):
        r_dict = {'code': 0}
        try:
            perm_code_list = self.get_body_arguments('perm_code_list[]', [])
            role = await Role.get_by_id(role_id)
            if role:
                role.permission_code_list = perm_code_list
                role.updated_dt = datetime.now()
                role.updated_id = self.current_user.oid
                await role.save()

                # 用户接入权限
                user_list = User.find(dict(role_code_list={'$in': [role.code]}))
                async for user in user_list:
                    if PERMISSION_TYPE_SYSTEM_DOCKING_MANAGEMENT in perm_code_list and (
                            not user.access_secret_id or not user.access_secret_key):
                        user.access_secret_id = get_random_str(32)
                        user.access_secret_key = get_random_str(64)
                    if PERMISSION_TYPE_SYSTEM_DOCKING_MANAGEMENT not in perm_code_list and \
                            PERMISSION_TYPE_SYSTEM_DOCKING_MANAGEMENT not in user.permission_code_list:
                        user.access_secret_id = None
                        user.access_secret_key = None
                    user.updated_dt = datetime.now()
                    user.updated_id = self.current_user.oid

                    await user.save()
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class RoleStatusSwitchViewHandler(BaseHandler):

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_ROLE_MANAGEMENT)
    async def post(self, role_id):
        r_dict = {'code': 0}
        try:
            status = self.get_argument('status', False)
            if status == 'true':
                status = STATUS_ROLE_ACTIVE
            else:
                status = STATUS_ROLE_INACTIVE
            role = await Role.get_by_id(role_id)
            if role:
                role.status = status
                role.updated_dt = datetime.now()
                role.updated_id = self.current_user.oid
                await role.save()
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/backoffice/role/list/', RoleListViewHandler, name='backoffice_role_list'),
    url(r'/backoffice/role/add/', RoleAddViewHandler, name='backoffice_role_add'),
    url(r'/backoffice/role/edit/([0-9a-zA-Z_]+)/', RoleEditViewHandler, name='backoffice_role_edit'),
    url(r'/backoffice/role/delete/([0-9a-zA-Z_]+)/', RoleDeleteViewHandler, name='backoffice_role_delete'),
    url(r'/backoffice/role/perm_assign/([0-9a-zA-Z_]+)/', RoleAssignPermissionViewHandler,
        name='backoffice_role_perm_assign'),
    url(r'/backoffice/role/status_switch/([0-9a-zA-Z_]+)/', RoleStatusSwitchViewHandler,
        name='backoffice_role_status_switch')
]
