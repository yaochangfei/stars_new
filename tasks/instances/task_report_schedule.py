import json
import traceback

from caches.redis_utils import RedisCache
from celery.schedules import crontab
from enums import KEY_CACHE_REPORT_ECHARTS_CONDITION
from logger import log_utils
from tasks import app
#  这些是定时任务eval执行的任务，不能删除，删除了eval找不到这些要跑的任务
from tasks.instances.task_report_learning_member_quantity import start_statistics_member_quantity, start_statistics_member_time, start_statistics_member_accuracy
from tasks.instances.task_report_learning_situation import start_statistics_learning_situation, start_statistics_quiz_trends, start_statistics_member_active, start_statistics_member_top_n
from tasks.instances.task_report_subject_parameter import start_statistics_subject_quantity
from tasks.instances.task_report_subject_parameter_cross import start_statistics_subject_parameter_cross
from tasks.instances.task_report_subject_parameter_radar import start_statistics_subject_parameter_radar
logger = log_utils.get_logging('task_report_schedule', 'task_report_schedule.log')

app.register_schedule('task_report_schedule',
                      'tasks.instances.task_report_schedule.schedule_report_statistics',
                      crontab(hour=1, minute=00))


@app.task(bind=True, queue='task_report_schedule')
def schedule_report_statistics(self):
    """
    定时任务
    :param self:
    :return:
    """
    logger.info(
        '[SCHEDULE_START] ------ schedule_report_statistics(%s) -----' % self.request.id)
    task_set = RedisCache.smembers(KEY_CACHE_REPORT_ECHARTS_CONDITION)
    for task in task_set:
        try:
            if isinstance(task, bytes):
                task = task.decode('utf-8')
            task_name, cond_json = task.split('%')
            eval(task_name).delay(**json.loads(cond_json))
            logger.info('%s has start.' % task_name)
        except Exception:
            logger.error('[SCHEDULE_ERROR] request_id: %s, task_str: %s, \ntraceback: %s' % (
                self.request.id, task, traceback.format_exc()))

    logger.info(
        '[SCHEDULE_END] ----- schedule_report_statistics(%s) -----' % self.request.id)
