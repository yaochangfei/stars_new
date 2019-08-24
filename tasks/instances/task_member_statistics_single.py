import traceback

from db.models import Race
from initialize.incremental.member_statistic import task_one_day, get_date_range, clear_redis_cache
from logger import log_utils
from tasks import app

logger = log_utils.get_logging('member_stat_schedule', 'member_stat_schedule_single.log')


@app.task(bind=True, queue='single_member_statistic')
def start_single_member_statistics(self, race_cid, daily_code):
    """
    每日会员统计任务
    :param self:
    :param race_cid:
    :param daily_code:
    :return:
    """
    logger.info('START(%s): Begin member_statistic, daily_code is %s' % (self.request.id, daily_code))
    try:
        task_one_day(race_cid, daily_code)
    except Exception:
        logger.error(traceback.format_exc())
    logger.info(' END (%s): Finish member_statistic, daily_code is %s' % (self.request.id, daily_code))


def deal_history_data(race_cid):
    """
    用于生成中间表处理历史数据(截止到昨天)
    :return:
    """
    race = Race.sync_find_one({'cid': race_cid})
    daily_code_list = get_date_range(race.start_datetime)
    print(daily_code_list)
    clear_redis_cache(race_cid)
    for daily_code in daily_code_list:
        start_single_member_statistics.delay(race_cid, daily_code)

