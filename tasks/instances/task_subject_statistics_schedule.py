import traceback
from datetime import datetime

from celery.schedules import crontab
from pymongo import ReadPreference

from caches.redis_utils import RedisCache
from db.models import ReportSubjectStatisticsMiddle
from enums import KEY_CACHE_REPORT_CONDITION
from logger import log_utils
from tasks import app
from tasks.instances.task_subject_statistics import start_split_subject_stat_task

logger = log_utils.get_logging('task_subject_statistics')
app.register_schedule('subject_stat_schedule',
                      'tasks.instances.task_subject_statistics_schedule.start_subject_statistics_schedule',
                      crontab(hour=2, minute=0))


@app.task(bind=True, queue='subject_stat_schedule')
def start_subject_statistics_schedule(self):
    """
    定时启动题目分析任务
    :param self:
    :return:
    """
    try:
        logger.info('START(%s)' % self.request.id)
        category_list = ReportSubjectStatisticsMiddle.sync_distinct('category')

        ReportSubjectStatisticsMiddle().get_sync_collection(read_preference=ReadPreference.PRIMARY).drop()

        task_dt = datetime.now()
        logger.info('-- category -- %s' % str(category_list))
        if not category_list:
            category_list = [
                {'subject_cid': '$subject_cid', 'province_code': '$province_code', 'city_code': '$city_code'}
            ]

        for category in category_list:
            logger.info('-- start -- %s' % str(category))
            RedisCache.hdel(KEY_CACHE_REPORT_CONDITION, str(category))
            start_split_subject_stat_task.delay(category, task_dt)

    except Exception:
        logger.error(str(traceback.format_exc()))

    logger.info(' END (%s)' % self.request.id)
