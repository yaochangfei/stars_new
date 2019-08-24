# !/usr/bin/python
# -*- coding:utf-8 -*-
import json
import os

from enums import KEY_SESSION_USER_MENU
from settings import SITE_ROOT

ALL_MENU_DICT = None


class Menu(object):
    def __init__(self, menu_dict, user=None, p_menu=None):
        if not isinstance(menu_dict, dict):
            raise ValueError('Parameter menu_dict must be type of dict.')
        if p_menu and not isinstance(p_menu, Menu):
            raise ValueError('Parameter p_menu must be a instance of Menu.')

        self.__menu_dict = menu_dict
        self.__user = user

        self.disabled = menu_dict.get('disabled')
        self.code = menu_dict.get('code')
        self.title = menu_dict.get('title')
        self.path = menu_dict.get('path')
        self.context = menu_dict.get('context')
        self.weight = menu_dict.get('weight') if menu_dict.get('weight') else 0
        self.style_name_list = menu_dict.get('style_name_list') if menu_dict.get('style_name_list') else []
        self.flags = menu_dict.get('flags') if menu_dict.get('flags') else []
        self.parent_menu = p_menu
        self.belong_path_list = []
        self.permission_code_list = []
        self.sub_menu_list = []

        self.has_perm = False
        self.is_active = False

    async def build(self):
        # 初始化隶属该菜单的URL
        self._init_belong_path_list()
        # 初始化权限
        self._init_permission()
        # 初始化菜单结构
        await self._init_menu_structure()
        # 菜单是否可见
        await self._init_menu_availability()

    def _init_belong_path_list(self):
        """
        初始化隶属该菜单的URL
        :return:
        """
        if self.__menu_dict:
            if self.path:
                self.belong_path_list.append(self.path)
            if self.__menu_dict.get('belong_path_list'):
                self.belong_path_list.extend(self.__menu_dict.get('belong_path_list'))

    def _init_permission(self):
        """
        初始化菜单权限
        :return:
        """
        if self.__menu_dict.get('permission_code_list'):
            self.permission_code_list.extend(self.__menu_dict.get('permission_code_list'))

    async def _init_menu_structure(self):
        """
        初始化菜单上下结构
        :param menu_dict: 菜单dict
        :param user: 用户
        :return:
        """
        if self.__menu_dict:
            sub_menu_list = self.__menu_dict.get('sub_menu_list')
            if sub_menu_list:
                self.sub_menu_list = []
                for sub_menu in sub_menu_list:
                    if sub_menu:
                        menu = Menu(sub_menu, user=self.__user, p_menu=self)
                        await menu.build()
                        self.sub_menu_list.append(menu)

    async def _init_menu_availability(self):
        """
        确定菜单对用户是的否可见
        :return:
        """
        if self.__user:
            has_perm = await self.__user.has_perm(self.permission_code_list)
            if has_perm:
                self.has_perm = True
                self._init_parent_menu_permission(self)

    def _init_parent_menu_permission(self, menu):
        """
        设置父菜单是否可见
        :param menu: 菜单
        :return:
        """
        if menu and menu.parent_menu:
            menu.parent_menu.has_perm = True
            self._init_parent_menu_permission(menu.parent_menu)

    def check_active_status(self, req_path):
        """
        依据URL检查菜单是否活动
        :param req_path: URL
        :return:
        """
        if self.belong_path_list and req_path:
            for path in self.belong_path_list:
                if path:
                    if self._check_path(path, req_path):
                        return True
        return False

    def _check_path(self, path, req_path):
        """
        检查PATH是否一致
        :param path: 菜单PATH
        :param req_path: 请求PATH
        :return:
        """
        if path and req_path:
            if path.find("(R)") > -1:
                path_cut_ret_list = path.split('/')
                req_path_ret_list = req_path.split('/')
                if len(path_cut_ret_list) == len(req_path_ret_list):
                    for index, val in enumerate(path_cut_ret_list):
                        if val and val == '(R)':
                            path_cut_ret_list[index] = req_path_ret_list[index]
                    if ''.join(path_cut_ret_list) == ''.join(req_path_ret_list):
                        return True
            else:
                if path == req_path:
                    return True
        return False

    def __unicode__(self):
        return u'%s - %s(%s)' % (self.code, self.title, self.weight)


def _read_menu_json(file_path=None):
    """
    读取菜单文件
    :param file_path: 菜单配置文件
    :return:
    """
    json_path = file_path
    if not json_path:
        json_path = os.path.join(SITE_ROOT, 'res', 'menu.json')
        if os.path.exists(json_path):
            json_file = open(json_path, encoding='utf-8')
            try:
                json_s = json_file.read()
                menu_dict = json.loads(json_s)
                if menu_dict:
                    return json.loads(json_s)
            finally:
                json_file.close()
    return None


def _get_top_menu_dicts(menu_key):
    """
    获取顶层菜单
    :param menu_key: 菜单KEY
    :return:
    """
    if menu_key:
        global ALL_MENU_DICT
        if ALL_MENU_DICT is None:
            ALL_MENU_DICT = _read_menu_json()
        if isinstance(ALL_MENU_DICT, dict):
            return ALL_MENU_DICT.get(menu_key)
    return None


async def get_user_menu(request_handler, menu_key='backend'):
    """
    获取有效的用户菜单
    :param request_handler: 请求句柄
    :param menu_key: 菜单KEY
    :return:
    """
    user_menus = request_handler.session.get(KEY_SESSION_USER_MENU)
    if not user_menus:
        user = request_handler.current_user
        if user:
            user_menus = []
            top_menu_dict_list = _get_top_menu_dicts(menu_key)
            if top_menu_dict_list:
                for top_menu_dict in top_menu_dict_list:
                    if top_menu_dict:
                        menu = Menu(top_menu_dict, user)
                        await menu.build()
                        if menu:
                            user_menus.append(menu)
            if user_menus:
                request_handler.session.put(KEY_SESSION_USER_MENU, user_menus)
    if user_menus:
        do_init_menu_active_status(request_handler, user_menus)
        do_init_parent_menu_path(user_menus)
        return user_menus
    return None


# 依据请求初始化菜单激活状态
def do_init_menu_active_status(request_handler, menu_list):
    """
    初始化菜单活动状态
    :param request_handler:
    :param menu_list:
    :return:
    """
    if menu_list:
        req_path = request_handler.request.path
        for menu in menu_list:
            if menu:
                if menu.check_active_status(req_path):
                    do_mark_menu_active_status(menu, req_path)
                do_init_menu_active_status(request_handler, menu.sub_menu_list)


def do_mark_menu_active_status(menu, req_path):
    """
    标记菜单为活动
    :param menu: 菜单
    :param req_path: 请求路径
    :return:
    """
    if menu:
        menu.is_active = True
        parent_menu = menu.parent_menu
        if parent_menu:
            do_mark_menu_active_status(parent_menu, req_path)


def do_init_parent_menu_path(menus):
    """
    初始化父菜单PATH
    :param menus: 有效菜单
    :return:
    """
    if menus:
        for menu in menus:
            if menu.sub_menu_list:
                fir_sub_menu = None
                for sub_menu in menu.sub_menu_list:
                    if sub_menu.has_perm and not sub_menu.disabled:
                        fir_sub_menu = sub_menu
                        break
                if fir_sub_menu and fir_sub_menu.path and not menu.path:
                    menu.path = fir_sub_menu.path
                do_init_parent_menu_path(menu.sub_menu_list)


def get_first_valid_path(user_menus):
    """
    获取用户菜单的第一个有效的PATH
    :param user_menus: 用户菜单
    :return:
    """
    if user_menus:
        for menu in user_menus:
            if menu and menu.has_perm:
                if menu.path:
                    return menu.path
                if menu.sub_menu_list:
                    path = get_first_valid_path(menu.sub_menu_list)
                    if path:
                        return path
    return None


def get_specified_menu(user_menus, code: str = None, context: str = None, flag: str = None):
    menu_list = []
    if not code and not context and not flag:
        raise ValueError('Specify at least one parameter...')
    if user_menus:
        for menu in user_menus:
            num = 0
            if code and menu.code == code:
                num += 1
            if context and menu.context == context:
                num += 1
            if flag and flag in menu.flags:
                num += 1
                menu_list.append(menu)
            if menu.sub_menu_list:
                menu_list.extend(get_specified_menu(menu.sub_menu_list, code, context, flag))

    return menu_list


def remove_menu(request_handler):
    """
    移除缓存菜单
    :param request_handler:
    :return:
    """
    if request_handler:
        request_handler.session.delete(KEY_SESSION_USER_MENU)
        request_handler.session.save()
