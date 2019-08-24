# !/usr/bin/python


import datetime

from pymongo import ReadPreference

from caches.redis_utils import RedisCache
from commons.common_utils import datetime2str
from db.models import Member, MemberPropertyStatistics
from enums import KEY_ALLOW_TASK_NEW_MEMBER_PROPERTY_STATISTICS
from tasks.instances.task_member_property_statistics import member_property_statistics


def deal_with_member_property():
    member_list = Member.sync_find(dict(record_flag=1), read_preference=ReadPreference.PRIMARY).batch_size(32)
    count = 1
    for member in member_list:
        if member:
            city_code = complete_member_city_code(member.province_code, member.city_code)
            mps = MemberPropertyStatistics.sync_find_one(
                dict(daily_code=_get_daily_code(member.register_datetime), province_code=member.province_code,
                     city_code=city_code, district_code=member.district_code, gender=member.sex,
                     age_group=member.age_group, education=member.education, source=member.source),
                read_preference=ReadPreference.PRIMARY)
            if not mps:
                mps = MemberPropertyStatistics(
                    daily_code=_get_daily_code(member.register_datetime), province_code=member.province_code,
                    city_code=city_code, district_code=member.district_code, gender=member.sex,
                    age_group=member.age_group, education=member.education, source=member.source
                )
                mps.sync_save()

            member_property_statistics.delay(member)
            print(count, member.nick_name, member.register_datetime)
            count += 1


def _get_daily_code(dt: datetime.datetime):
    """
    获取自然日标识
    :return:
    """
    return datetime2str(dt, date_format='%Y%m%d000000')


def complete_member_city_code(province_code, city_code):
    """
    直辖市city_code变更
    :param province_code:
    :param city_code:
    :return:
    """
    match_code_list = ['110000', '120000', '310000', '500000']
    match_code_dict = {'110000': '110100', '120000': '120100', '310000': '310100', '500000': '500100'}
    if province_code and province_code in match_code_list:
        city_code = match_code_dict.get(province_code)
    return city_code


if __name__ == '__main__':
    RedisCache.delete(KEY_ALLOW_TASK_NEW_MEMBER_PROPERTY_STATISTICS)
    deal_with_member_property()
