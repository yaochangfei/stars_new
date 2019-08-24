# !/usr/bin/python
# -*- coding:utf-8 -*-
from datetime import datetime

from tornado.web import url

from commons import menu_utils
from commons.common_utils import md5
from db import STATUS_USER_ACTIVE
from db.models import User
from enums import KEY_SESSION_USER
from web import BaseHandler, decorators


class LoginHandler(BaseHandler):
    @decorators.render_template('backoffice/login.html')
    async def get(self):
        return locals()

    @decorators.render_json
    async def post(self):
        r_dict = {}
        login_name = self.get_argument('login_name')
        login_password = self.get_argument('login_password')
        if login_name and login_password:
            user = await User.find_one(dict(login_name=login_name, status=STATUS_USER_ACTIVE))
            if user:
                if md5(login_password) == user.login_password:
                    # 用户放入Session
                    self.session.put(KEY_SESSION_USER, user)

                    user_menu = await menu_utils.get_user_menu(self)
                    redirect_url = menu_utils.get_first_valid_path(user_menu)

                    if not redirect_url:
                        # 没有权限访问
                        # 跳到个人信息页面
                        redirect_url = '/backoffice/account/'

                    user.login_datetime = datetime.now()
                    user.login_times = user.login_times + 1
                    await user.save()

                    self.session.save()

                    r_dict['code'] = 1
                    r_dict['url'] = redirect_url
                else:
                    # 用户密码有误
                    r_dict['code'] = -4
            else:
                # 用户不存在
                r_dict['code'] = -3
        else:
            if not login_name:
                # 用户名未输入
                r_dict['code'] = -1
            elif not login_password:
                # 用户密码未输入
                r_dict['code'] = -2
        return r_dict


class LogoutHandler(BaseHandler):
    async def get(self):
        self.current_user = None
        self.clear_cookie('_xsrf')
        self.session.drop()
        self.redirect(self.reverse_url('backoffice_index'))


class AccountHandler(BaseHandler):
    @decorators.authenticated
    @decorators.render_template('backoffice/account/account_view.html')
    async def get(self):
        edit_account = await User.get_by_id(self.current_user.oid)
        return locals()

    @decorators.authenticated
    @decorators.render_json
    async def post(self):
        res = dict(code=0)

        account_id = self.get_argument('account_id', '')
        origin_pwd = self.get_argument('origin_pwd', '')
        new_pwd = self.get_argument('new_pwd', '')
        new_pwd_confirm = self.get_argument('new_pwd_confirm', '')
        # avatar = self.request.files['avatar']  # 头像暂时空

        if account_id and new_pwd and origin_pwd and new_pwd_confirm:

            if new_pwd_confirm != new_pwd:
                res['code'] = -2
            else:
                account = await User.get_by_id(account_id)
                if not account or account.login_password != md5(origin_pwd):
                    res['code'] = -3
                elif account.login_password == md5(new_pwd):
                    res['code'] = -4
                else:
                    account.login_password = md5(new_pwd)
                    account.updated_dt = datetime.now()
                    account.update_id = self.current_user.oid
                    await account.save()
                    res['code'] = 1

        else:
            res['code'] = -1

        return res


URL_MAPPING_LIST = [
    url(r'/backoffice/login/', LoginHandler, name='backoffice_login'),
    url(r'/backoffice/logout/', LogoutHandler, name='backoffice_logout'),
    url(r'/backoffice/account/', AccountHandler, name='backoffice_account'),
]
