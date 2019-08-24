#! /usr/bin/python
# -*- coding: utf-8 -*-

import traceback
from tasks import app
from db.models import Member, MemberShareStatistics, SubjectWrongViewedStatistics, SubjectResolvingViewedStatistics, \
    RaceMapping
from logger import log_utils

logger = log_utils.get_logging('task_update_member_info', 'task_update_member_info.log')


@app.task(bind=True, queue="update_memberinfo_in_other_collections")
def update_memberinfo_in_other_collections(self, member=None):
    """
    同步更新某个用户的个人信息到其他表中
    :param member:
    :return:
    """
    if not member:
        raise ValueError('Parameter[member] is missing.')

    if not isinstance(member, Member):
        raise ValueError('"member" must be a instance of member.')

    member_match = {'member_cid': member.cid}

    object_list = [RaceMapping, MemberShareStatistics, SubjectWrongViewedStatistics, SubjectResolvingViewedStatistics]

    try:
        for obj in object_list:
            logger.info(
                'START(%s): Update MemberInfo, Object=%s, member_code=%s ' % (
                    self.request.id, obj.__name__, member.code))
            shares = obj.sync_find(member_match).to_list(None)
            if shares:
                for share_action in shares:
                    share_action.age_group = member.age_group
                    share_action.sex = member.sex
                    share_action.province_code = member.province_code
                    share_action.city_code = member.city_code
                    share_action.education = member.education
                    share_action.category = member.category
                    share_action.sync_save()

            logger.warning(
                'END(%s): [Update MemberInfo],  Object=%s, member_code=%s ' % (
                    self.request.id, obj.__name__, member.code))
    except Exception:
        logger.error(traceback.format_exc())
