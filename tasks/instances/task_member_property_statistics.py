# !/usr/bin/python
# -*- coding:utf-8 -*-


import datetime
import time
import traceback

from motorengine import DocumentFieldTypeError
from pymongo import ReadPreference

from caches.redis_utils import RedisCache
from commons.common_utils import datetime2str
from db import SEX_NONE, TYPE_AGE_GROUP_NONE, TYPE_EDUCATION_NONE, SOURCE_TYPE_MEMBER_SYSTEM
from db.models import Member, MemberPropertyStatistics
from enums import KEY_ALLOW_TASK_NEW_MEMBER_PROPERTY_STATISTICS
from logger import log_utils
from tasks import app
from tasks.config import task_time_limit

logger = log_utils.get_logging('task_member_property_statistics', 'task_member_property_statistics.log')


async def start_task_member_property_statistics(member: Member, orig_member: Member = None):
    try:
        if not isinstance(member, Member):
            raise ValueError('"member" must be a instance of member.')
        if orig_member and not isinstance(orig_member, Member):
            raise ValueError('"orig_member" must be a instance of member.')
        if member == orig_member:
            raise ValueError('"member" and "before_member" must be different instance.')

        # START: 会员属性数据统计
        daily_code = _get_daily_code(member.register_datetime)
        city_code = complete_member_city_code(member.province_code, member.city_code)
        mps = await MemberPropertyStatistics.find_one(
            dict(daily_code=daily_code, province_code=member.province_code, city_code=city_code,
                 district_code=member.district_code, gender=member.sex, age_group=member.age_group,
                 education=member.education, source=member.source),
            read_preference=ReadPreference.PRIMARY)
        if not mps:
            # 创建会员属性统计记录
            mps = MemberPropertyStatistics(
                daily_code=daily_code, province_code=member.province_code, city_code=city_code,
                district_code=member.district_code, gender=member.sex, age_group=member.age_group,
                education=member.education, source=member.source)
            try:
                await mps.save()
            except DocumentFieldTypeError:
                logger.warning("may be type(source) == 'int', source: %s. try save again." % mps.source)
                mps.source = str(mps.source)
                await mps.save()
        if mps:
            # 添加任务
            return member_property_statistics.delay(member, orig_member)
        # END: 会员属性数据统计

    except Exception:
        logger.error(traceback.format_exc())
    return None


@app.task(bind=True, queue='member_property_statistics')
def member_property_statistics(self, member: Member, orig_member: Member = None):
    result = {'code': 0}
    if member and allowed_process(KEY_ALLOW_TASK_NEW_MEMBER_PROPERTY_STATISTICS):
        try:
            logger.info(
                'START MEMBER_PROPERTY_STATISTICS(%s): member_code=%s' % (
                    self.request.id if self.request.id else '-', member.code))
            # 处理旧统计数据
            if orig_member:
                orig_daily_code = _get_daily_code(orig_member.register_datetime)
                orig_city_code = complete_member_city_code(orig_member.province_code, orig_member.city_code)
                orig_mps = MemberPropertyStatistics.sync_find_one(
                    dict(daily_code=orig_daily_code, province_code=orig_member.province_code,
                         city_code=orig_city_code, district_code=orig_member.district_code,
                         gender=orig_member.sex, age_group=orig_member.age_group, education=orig_member.education,
                         source=orig_member.source),
                    read_preference=ReadPreference.PRIMARY)
                if orig_mps and orig_mps.quantity > 0:
                    orig_mps.quantity -= 1
                    orig_mps.source = str(orig_mps.source)
                    orig_mps.sync_save()
            # 纳入新统计
            daily_code = _get_daily_code(member.register_datetime)
            city_code = complete_member_city_code(member.province_code, member.city_code)
            mps = MemberPropertyStatistics.sync_find_one(
                dict(daily_code=daily_code, province_code=member.province_code, city_code=city_code,
                     district_code=member.district_code, gender=member.sex if member.sex else SEX_NONE,
                     age_group=member.age_group if member.age_group else TYPE_AGE_GROUP_NONE,
                     education=member.education if member.education else TYPE_EDUCATION_NONE,
                     source=member.source if member.source else SOURCE_TYPE_MEMBER_SYSTEM),
                read_preference=ReadPreference.PRIMARY)
            if mps:
                mps.quantity += 1
                mps.updated_dt = datetime.datetime.now()
                mps.source = str(mps.source)
                mps.sync_save()
            logger.info(
                'END MEMBER_PROPERTY_STATISTICS(%s): result_code=%s' % (
                    self.request.id if self.request.id else '-', result.get('code')))
        except ValueError:
            trace_i = traceback.format_exc()
            result['msg'] = trace_i
            logger.error(trace_i)
        finally:
            release_process(KEY_ALLOW_TASK_NEW_MEMBER_PROPERTY_STATISTICS)

    return result


def _get_daily_code(dt: datetime.datetime):
    """
    获取自然日标识
    :return:
    """
    return datetime2str(dt, date_format='%Y%m%d000000')


def allowed_process(key: str):
    """
    是否允许开始处理数据
    :return:
    """
    if key:
        while True:
            cache_value = RedisCache.get(key)
            if cache_value in [None, '0', 0]:
                RedisCache.set(key, 1, task_time_limit)
                return True
            else:
                time.sleep(0.05)
    return False


def release_process(key: str):
    """
    释放任务锁
    :param key:
    :return:
    """
    if key:
        RedisCache.delete(key, )
        return True
    return False


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
