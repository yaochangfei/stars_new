#!/usr/bin/python


import copy
import traceback
from datetime import datetime

from tornado.web import url

from actions.backoffice.race.utils import get_new_cid, do_copy_subject_refer, do_copy_checkpoint, do_copy_choice_rule, \
    do_copy_subject_bank, do_copy_red_packet_rule, do_copy_company, do_copy_red_packet_box
from commons.common_utils import str2datetime
from commons.page_utils import Paging
from commons.upload_utils import save_upload_file
from db import CATEGORY_RACE_REFER, STATUS_SUBJECT_DIMENSION_ACTIVE, STATUS_SUBJECT_ACTIVE, \
    STATUS_SUBJECT_CHOICE_RULE_ACTIVE, STATUS_GAME_CHECK_POINT_ACTIVE
from db import CATEGORY_UPLOAD_FILE_RACE, STATUS_RACE_INACTIVE, STATUS_USER_ACTIVE
from db.models import Race, AdministrativeDivision, UploadFiles, Role, User, RaceSubjectRefer, RaceSubjectChoiceRules, \
    RaceSubjectBanks, RedPacketItemSetting, Company, RedPacketConf, RedPacketRule
from db.models import SubjectDimension, RaceGameCheckPoint
from enums import PERMISSION_TYPE_MINIAPP_RACE_MANAGEMENT, KEY_SESSION_USER_MENU, \
    PERMISSION_TYPE_MINIAPP_RACE_ADD_OR_EDIT_MANAGEMENT
from logger import log_utils
from motorengine.stages import MatchStage, LookupStage
from web import BaseHandler, decorators, menu_utils

logger = log_utils.get_logging()


class RaceListViewHandler(BaseHandler):
    """
    竞赛活动列表页
    """

    @decorators.render_template('backoffice/race/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_MANAGEMENT)
    async def get(self):
        pipelines = list()
        #  展示当前用户可看的竞赛活动
        user = self.current_user
        #  隐藏了筛选条件，编辑，状态变更等按钮，不是超级管理员的情况下
        button_hide = False
        #  不是超管的情况
        if not user.superuser:
            if PERMISSION_TYPE_MINIAPP_RACE_ADD_OR_EDIT_MANAGEMENT not in user.permission_code_list:
                button_hide = True
            city_title = user.city
            #  省级账号可以看到该省和该省下面所有的市的活动
            province_title = user.province
            try:
                if province_title and not city_title:
                    province = await AdministrativeDivision.find_one({'title': province_title, 'record_flag': 1})
                    if province:
                        #  该省下面的所有市
                        city_list = await AdministrativeDivision.find({'parent_code': province.code}).to_list(None)
                        city_code_list = [city.code for city in city_list if city_list]
                        pipelines.append(MatchStage(
                            {"$or": [{"city_code": {'$in': city_code_list}}, {'province_code': province.code}]}))
                #  市级账号只能看到该市的活动
                elif city_title:
                    city = await AdministrativeDivision.find_one({'title': {'$regex': city_title}, 'record_flag': 1})
                    if city:
                        pipelines.append(MatchStage({"city_code": city.code}))
            except Exception as e:
                logger.error(traceback.format_exc())
        search_keywords = self.get_argument('search_keywords', '')
        search_date = self.get_argument('search_date', '')
        sort_type = int(self.get_argument('sort_type', 1))
        search_province = self.get_argument('search_province', '')
        search_city = self.get_argument('search_city', '')

        page = int(self.get_argument('page', 1))
        per_page_quantity = int(self.get_argument('per_page_quantity', 10))

        if search_keywords:
            pipelines.append(
                MatchStage({'$or': [{'code': {'$regex': search_keywords}}, {'title': {'$regex': search_keywords}}]}))

        if search_date:
            try:
                start_date_str, end_date_str = search_date.split(' - ')
                start_datetime = str2datetime(start_date_str)
                end_datetime = str2datetime(end_date_str)
                pipelines.append(
                    MatchStage({'start_datetime': {'$gte': start_datetime}, 'end_datetime': {'$lte': end_datetime}}))
            except ValueError or TypeError:
                logger.error(traceback.format_exc())
                search_date = ''
        sort_list = []
        if sort_type:
            if int(sort_type) == 1:
                sort_list.append('-start_datetime')

            if int(sort_type) == 2:
                sort_list.append('start_datetime')

        left_pipes = [
            LookupStage(AdministrativeDivision, 'province_code', 'code', 'province_list'),
            LookupStage(AdministrativeDivision, 'city_code', 'code', 'city_list'),
        ]

        try:
            query_param = {'record_flag': 1}
            if search_province:
                query_param['province_code'] = search_province

            if search_city:
                query_param['city_code'] = search_city

            page_url = '%s?page=$page&per_page_quantity=%s&search_keywords=%s&search_date=%s&sort_type=%s&' \
                       'search_province=%s&search_city=%s' % (
                           self.reverse_url("backoffice_race_list"), per_page_quantity, search_keywords, search_date,
                           sort_type, search_province, search_city)
            paging = Paging(page_url, Race, current_page=page, items_per_page=per_page_quantity,
                            pipeline_stages=pipelines,
                            left_pipeline_stages=left_pipes, sort=sort_list, **query_param)
            await paging.pager()

            city_list = None
            if search_province:
                city_list = await AdministrativeDivision.find(dict(parent_code=search_province)).to_list(None)

            province_list = await AdministrativeDivision.find(dict(parent_code=None)).to_list(None)

            now = datetime.now()
        except Exception:
            logger.error(traceback.format_exc())
        return locals()


class RaceAddViewHandler(BaseHandler):
    """
    新增竞赛活动
    """

    @decorators.render_template('backoffice/race/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_ADD_OR_EDIT_MANAGEMENT)
    async def get(self):
        city_list = None
        province_list = await AdministrativeDivision.find(dict(parent_code=None)).to_list(None)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_ADD_OR_EDIT_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        code = self.get_argument('code', '')
        title = self.get_argument('title', '')
        province = self.get_argument('province', '')
        company_enabled = self.get_argument('com', '')
        Mandatory_enabled = self.get_argument('sure', '')
        resolving_enabled = self.get_argument('ans', '')
        mobile_enabled = self.get_argument('tel', '')
        mobile_before_race = self.get_argument("before_tel", '')
        play_quantity = self.get_argument('play_quantity', '')
        redpkt_account = self.get_argument('red_account', '')
        redpkt_start_dt = self.get_argument('red_start', '')
        redpkt_end_dt = self.get_argument('red_end', '')
        city = self.get_argument('city', '')
        start_dt = self.get_argument('start_dt', '')
        end_dt = self.get_argument('end_dt', '')
        guide = self.get_argument('guide', '')

        race = await Race.find_one(filtered={'province_code': province, 'title': title})
        if race:
            r_dict['code'] = -3
            return r_dict
        if not code or not title or not province or not start_dt or not end_dt or not guide:
            r_dict['code'] = -1
            return r_dict

        if await Race.find_one({'code': code}):
            r_dict['code'] = -2
            return r_dict
        try:
            if 0 < len(code) <= 16 and 4 <= len(title) <= 32:
                race = Race()
                race.Mandatory_enabled = True if Mandatory_enabled else False
                race.play_quantity_enabled = True if play_quantity else False
                race.company_enabled = True if company_enabled else False
                race.resolving_enabled = True if resolving_enabled else False
                race.mobile_enabled = True if mobile_enabled else False
                race.mobile_before_race = True if mobile_before_race else False
                if redpkt_account:
                    race.redpkt_account = redpkt_account
                if redpkt_start_dt:
                    race.redpkt_start_dt = datetime.strptime(redpkt_start_dt, "%Y-%m-%d %H:%M:%S")
                if redpkt_start_dt:
                    race.redpkt_end_dt = datetime.strptime(redpkt_end_dt, "%Y-%m-%d %H:%M:%S")
                race.code = code
                race.title = title
                race.province_code = province
                if city:
                    race.city_code = city
                race.start_datetime = datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
                race.end_datetime = datetime.strptime(end_dt, "%Y-%m-%d %H:%M:%S")

                if race.start_datetime >= race.end_datetime:
                    r_dict['code'] = -5
                    return r_dict
                if race.redpkt_start_dt and race.redpkt_end_dt and race.redpkt_start_dt > race.redpkt_end_dt:
                    r_dict['code'] = -6
                    return r_dict
                race.guide = guide

                title_image_id_list = await save_upload_file(self, 'title_image', category=CATEGORY_UPLOAD_FILE_RACE)
                race.image_cid = title_image_id_list[0] if title_image_id_list else None
                await race.save()

                r_dict['code'] = 1
            else:
                r_dict['code'] = -4
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceEditViewHandler(BaseHandler):
    """
    编辑竞赛活动
    """

    @decorators.render_template('backoffice/race/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_ADD_OR_EDIT_MANAGEMENT)
    async def get(self):
        city_list = None
        province_list = await AdministrativeDivision.find(dict(parent_code=None)).to_list(None)

        race_cid = self.get_argument('race_cid', '')
        try:
            race_list = await Race.aggregate(stage_list=[
                MatchStage({'cid': race_cid}),
                LookupStage(UploadFiles, 'image_cid', 'cid', 'image_list')
            ]).to_list(1)

            race = race_list[0] if race_list else None
            city_list = None
            if race.province_code:
                city_list = await AdministrativeDivision.find({'parent_code': race.province_code}).to_list(None)
        except Exception:
            logger.error(traceback.format_exc())

        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_ADD_OR_EDIT_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}

        race_cid = self.get_argument('race_cid', '')
        code = self.get_argument('code', '')
        title = self.get_argument('title', '')
        province = self.get_argument('province', '')
        company_enabled = self.get_argument('com', '')
        Mandatory_enabled = self.get_argument('sure', '')
        resolving_enabled = self.get_argument('ans', '')
        mobile_enabled = self.get_argument('tel', '')
        mobile_before_race = self.get_argument("before_tel", '')
        play_quantity_enabled = self.get_argument('play_quantity', '')
        redpkt_account = self.get_argument('red_account', '')
        print(redpkt_account, '123')
        redpkt_start_dt = self.get_argument('red_start', '')
        redpkt_end_dt = self.get_argument('red_end', '')
        city = self.get_argument('city', '')
        start_dt = self.get_argument('start_dt', '')
        end_dt = self.get_argument('end_dt', '')
        guide = self.get_argument('guide', '')
        town_enable = self.get_argument('town_enable', '')
        count = await Race.count(filtered={'province_code': province, 'title': title})
        if count > 1:
            r_dict['code'] = -3
            return r_dict
        if not code or not title or not province or not start_dt or not end_dt or not guide:
            r_dict['code'] = -1
            return r_dict

        try:
            race = await Race.find_one({'cid': race_cid})
            if not race:
                r_dict['code'] = -2
                return r_dict
            if 0 < len(code) <= 16 and 4 <= len(title) <= 32:
                race.Mandatory_enabled = True if Mandatory_enabled else False
                race.company_enabled = True if company_enabled else False
                race.resolving_enabled = True if resolving_enabled else False
                race.mobile_enabled = True if mobile_enabled else False
                race.play_quantity_enabled = True if play_quantity_enabled else False
                race.mobile_before_race = True if mobile_before_race else False
                race.town_enable = True if town_enable else False
                race.redpkt_account = redpkt_account if redpkt_account else ''
                redkpt_start_time = ""
                redpkt_end_time = ""
                if redpkt_start_dt:
                    redkpt_start_time = datetime.strptime(redpkt_start_dt, "%Y-%m-%d %H:%M:%S")
                if redpkt_end_dt:
                    redpkt_end_time = datetime.strptime(redpkt_end_dt, "%Y-%m-%d %H:%M:%S")
                race.redpkt_start_dt = redkpt_start_time if redkpt_start_time else None
                race.redpkt_end_dt = redpkt_end_time if redpkt_end_time else None
                race.code = code
                race.title = title
                race.province_code = province
                race.city_code = city
                race.start_datetime = datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
                race.end_datetime = datetime.strptime(end_dt, "%Y-%m-%d %H:%M:%S")

                if race.start_datetime >= race.end_datetime:
                    r_dict['code'] = -5
                    return r_dict
                if race.redpkt_start_dt and race.redpkt_end_dt and race.redpkt_start_dt > race.redpkt_end_dt:
                    r_dict['code'] = -6
                    return r_dict
                race.guide = guide

                title_image_id_list = await save_upload_file(self, 'title_image', category=CATEGORY_UPLOAD_FILE_RACE)
                if title_image_id_list:
                    race.image_cid = title_image_id_list[0]
                await race.save()

                r_dict['code'] = 1
            else:
                r_dict['code'] = -4
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


class RaceOwnerAssignHandler(BaseHandler):
    """
    分配竞赛活动管理员
    """

    @decorators.render_template('backoffice/race/pop_assign_owner.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid', '')
        race = await Race.find_one({'cid': race_cid})

        # 查出具有活动管理权限的角色列表
        role_list = await Role.find(
            {'permission_code_list': {'$elemMatch': {'$eq': PERMISSION_TYPE_MINIAPP_RACE_MANAGEMENT}}},
        ).to_list(None)

        assign_user_list = await User.find({
            'status': STATUS_USER_ACTIVE,
            'superuser': False,
            'cid': {'$in': race.owner_list},
        }).to_list(None)

        query_param = {
            'status': STATUS_USER_ACTIVE,
            'superuser': False,
            'cid': {'$nin': race.owner_list},
        }

        if role_list:
            query_param.update({'$or': [
                {'permission_code_list': {'$elemMatch': {'$eq': PERMISSION_TYPE_MINIAPP_RACE_MANAGEMENT}}},
                {'role_code_list': [ro.code for ro in role_list]}
            ]})
        else:
            query_param.update(
                {'permission_code_list': {'$elemMatch': {'$eq': PERMISSION_TYPE_MINIAPP_RACE_MANAGEMENT}}})

        wait_assign_users_list = await User.find(query_param).to_list(None)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        assigned_owner_code_list = self.get_arguments('assigned_owner_code_list[]')

        try:
            user_cid_list = await User.distinct('cid', {'status': STATUS_USER_ACTIVE, 'superuser': False,
                                                        'cid': {'$in': [user_cid for user_cid in
                                                                        assigned_owner_code_list]}})

            race = await Race.find_one({'cid': race_cid})
            race.owner_list = user_cid_list
            await race.save()

            r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class RaceConfigViewHandler(BaseHandler):
    """
    设置
    """

    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_ADD_OR_EDIT_MANAGEMENT)
    async def get(self, race_cid):
        user_menus = self.session.get(KEY_SESSION_USER_MENU)
        if not user_menus:
            self.render('forbidden.html', forbidden_code=1, to_url='/backoffice/')
            return None
        menu_list = menu_utils.get_specified_menu(user_menus, flag='config')
        menu_list.sort(key=lambda menu: menu.weight)

        path = menu_utils.get_first_valid_path(menu_list)
        if not path:
            self.render('forbidden.html', forbidden_code=2, to_url='/backoffice/')
            return None

        self.redirect('%s?%s' % (path, 'race_cid=%s' % race_cid))


class RaceVerifyHandler(BaseHandler):
    """
    校验竞赛活动设置是否正确
    """

    @decorators.render_template('backoffice/race/status_verify.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_MANAGEMENT)
    async def get(self):
        """

        :return:
        """
        race_cid = self.get_argument('race_cid')
        return locals()

    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        """

        :return: {'code': 0 or 1}
                  0: fail
                  1: success
        """
        ret = dict(code=0)
        race_cid = self.get_argument('race_cid', '')
        race = await Race.find_one(filtered={'record_flag': 1, 'cid': race_cid})
        if race.category == CATEGORY_RACE_REFER:
            return {'code': 1, 'dimension': 1, 'subject': 1, 'choice_rules': 1, 'point': 1}

        ret['dimension'] = 1 if await self._verify_dimension() else 0
        ret['subject'] = 1 if await self._verify_subject(race_cid) else 0
        ret['choice_rules'] = 1 if await self._verify_choice_rules(race_cid) else 0
        ret['point'] = 1 if await self._verify_check_point(race_cid) else 0

        ret['code'] = 1
        return ret

    @staticmethod
    async def _verify_dimension():
        """
        检查纬度设置是否正确
        :param race_cid:
        :return:
        """
        try:
            query_dict = {'status': STATUS_SUBJECT_DIMENSION_ACTIVE, 'parent_cid': None}
            parent_dimension_count = await SubjectDimension.count(query_dict)
            query_dict['parent_cid'] = {'$ne': None}
            children_dimension_count = await SubjectDimension.count(query_dict)
            if parent_dimension_count > 0 and children_dimension_count > 1:
                return True
        except:
            logger.error(traceback.format_exc())

        return False

    @staticmethod
    async def _verify_subject(race_cid=None):
        """
        检查题库设置是否正确
        :param race_cid:
        :return:
        """
        try:
            subject_count = await RaceSubjectRefer.count({'race_cid': race_cid, 'status': STATUS_SUBJECT_ACTIVE})
            if subject_count > 0:
                return True
        except:
            logger.error(traceback.format_exc())
        return False

    async def _verify_choice_rules(self, race_cid=None):
        """
        检查抽题规则是否正确
        :param race_cid:
        :return:
        """
        try:
            rules_cids = list()
            query_dict = {'race_cid': race_cid, 'status': STATUS_SUBJECT_CHOICE_RULE_ACTIVE,
                          'dimension_rules': {'$ne': {}}}
            if await self._verify_check_point(race_cid):
                # 如果关卡存在，则查找关卡关联的抽题规则是否正确
                point_cursor = RaceGameCheckPoint.find({'race_cid': race_cid, 'status': STATUS_GAME_CHECK_POINT_ACTIVE})
                while await point_cursor.fetch_next:
                    point = point_cursor.next_object()
                    if point and point.rule_cid:
                        rules_cids.append(point.rule_cid)

                    query_dict['cid'] = {'$in': rules_cids}

            rules_cids = set(rules_cids)  # 去重
            rules_count = await RaceSubjectChoiceRules.count(query_dict)
            if 'cid' in query_dict.keys():
                if rules_count == len(rules_cids):
                    return True
            else:
                if rules_count > 0:
                    return True

            return False

        except:
            logger.error(traceback.format_exc())
            return False

    @staticmethod
    async def _verify_check_point(race_cid=None):
        """
        检查关卡设置是否正确
        :param race_cid:
        :return:
        """
        try:
            points_count = await RaceGameCheckPoint.count(
                {'race_cid': race_cid, 'status': STATUS_GAME_CHECK_POINT_ACTIVE})

            if points_count > 0:
                return True
        except Exception:
            logger.error(traceback.format_exc())
        return False


class RaceStatusEditViewHandler(BaseHandler):
    """
    修改竞赛活动状态
    """

    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_ADD_OR_EDIT_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = {'code': 0}
        race_cid = self.get_argument('race_cid', '')
        status = self.get_argument('target_status')
        if race_cid and status:
            try:
                race = await Race.find_one(filtered={'record_flag': 1, 'cid': race_cid})
                race.status = status
                race.updated_dt = datetime.now()
                await race.save()
                res['code'] = 1
            except Exception:
                logger.error(traceback.format_exc())
        return res


class RaceCopyHandler(BaseHandler):
    """
    竞赛活动复制
    """

    @decorators.render_template('backoffice/race/complete_activity_info.html')
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_ADD_OR_EDIT_MANAGEMENT)
    async def get(self):
        race_cid = self.get_argument('race_cid')
        race = await Race.find_one({'cid': race_cid})
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_ADD_OR_EDIT_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}

        race_cid = self.get_argument('race_cid')
        race = await Race.get_by_cid(race_cid)
        if not race:
            r_dict['code'] = -1
            return r_dict

        code = self.get_argument('code')
        title = self.get_argument('title')
        start_dt = self.get_argument('start_dt')
        end_dt = self.get_argument('end_dt')
        if not code or not title or not start_dt or not end_dt:
            r_dict['code'] = -2
            return r_dict

        if await Race.count(dict(code=code)) > 0:
            r_dict['code'] = -5
            return r_dict

        if await Race.count(dict(title=title)) > 0:
            r_dict['code'] = -6
            return r_dict

        new_cid = get_new_cid()
        try:
            new_race = copy.deepcopy(race)
            new_race.cid = new_cid
            new_race.code = code
            new_race.title = title
            new_race.start_datetime = str2datetime(start_dt)
            new_race.end_datetime = str2datetime(end_dt)
            new_race.status = STATUS_RACE_INACTIVE
            new_race.owner_list = [self.current_user.cid]
            await Race.insert_many([new_race])

            # 开始复制
            await do_copy_subject_refer(race_cid, new_race.cid, self.current_user.cid)
            await do_copy_red_packet_rule(race_cid, new_race.cid, self.current_user.cid)
            await do_copy_choice_rule(race_cid, new_race.cid, self.current_user.cid)
            await do_copy_checkpoint(race_cid, new_race.cid, self.current_user.cid)
            await do_copy_subject_bank(race_cid, new_race.cid, self.current_user.cid)
            await do_copy_company(race_cid, new_race.cid, self.current_user.cid)
            await do_copy_red_packet_box(race_cid, new_race.cid, self.current_user.cid)
            r_dict['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
            await Race.delete_many({'cid': new_cid})
            await RaceSubjectRefer.delete_many({'race_cid': new_cid})
            await RaceSubjectChoiceRules.delete_many({'race_cid': new_cid})
            await RaceSubjectBanks.delete_many({'race_cid': new_cid})
            await RedPacketItemSetting.delete_many({'race_cid': new_cid})
            await Company.delete_many({'race_cid': new_cid})
            await RedPacketConf.delete_many({'race_cid': new_cid})
            await RedPacketRule.delete_many({'race_cid': new_cid})
            await RaceGameCheckPoint.delete_many({'race_cid': new_cid})
        finally:
            pass

        return r_dict


class RaceDeleteHandler(BaseHandler):
    """
    删除竞赛活动
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MINIAPP_RACE_ADD_OR_EDIT_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}

        race_cid = self.get_argument('race_cid', '')
        if not race_cid:
            r_dict['code'] = -1
            return r_dict

        try:
            count = await Race.delete_many({'cid': race_cid, 'start_datetime': {'$gt': datetime.now()}})
            if count > 0:
                await RaceSubjectRefer.delete_many({'race_cid': race_cid})
                await RaceSubjectChoiceRules.delete_many({'race_cid': race_cid})
                await RaceSubjectBanks.delete_many({'race_cid': race_cid})
                r_dict['code'] = 1
            else:
                r_dict['code'] = -2
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


URL_MAPPING_LIST = [
    url(r'/backoffice/race/list/', RaceListViewHandler, name='backoffice_race_list'),
    url(r'/backoffice/race/add/', RaceAddViewHandler, name='backoffice_race_add'),
    url(r'/backoffice/race/edit/', RaceEditViewHandler, name='backoffice_race_edit'),
    url(r'/backoffice/race/owner/assign/', RaceOwnerAssignHandler, name='backoffice_race_owner_assign'),
    url(r'/backoffice/race/verify/', RaceVerifyHandler, name='backoffice_race_verify'),
    url(r'/backoffice/race/status/', RaceStatusEditViewHandler, name='backoffice_race_status'),
    url(r'/backoffice/race/config/([0-9a-zA-Z_]+)/', RaceConfigViewHandler,
        name='backoffice_race_config'),
    url(r'/backoffice/race/copy/', RaceCopyHandler, name='backoffice_race_copy'),
    url(r'/backoffice/race/delete/', RaceDeleteHandler, name='backoffice_race_delete')
]
