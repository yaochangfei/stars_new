import datetime

import settings
from commons.common_utils import datetime2str
from services.email_service import send_instant_mail


def early_warning_empty(task_name, cache_key, param, error_msg):
    """

    :param task_name:
    :param cache_key:
    :param param:
    :param error_msg:
    :return:
    """
    content = 'host=%s,[ERROR] task_name=(%s), time=(%s): cache_key=%s, param=%s\n %s' % (
        settings.SERVER_HOST, task_name, datetime2str(datetime.datetime.now()), cache_key, str(param),
        error_msg)

    send_instant_mail(mail_to=['lf.weng@idiaoyan.com', 'yan.zhao@idiaoyan.com'],
                      subject='学习之旅报表任务失败', content=content)


def early_warning(question_oid, task_name, cache_key, param, error_msg):
    """

    :param task_name:
    :param question_oid:
    :param cache_key:
    :param param:
    :param error_msg:
    :return:
    """
    content = 'host=%s,[ERROR] %s=(%s), time=(%s): cache_key=%s, param=%s\n %s' % (
        settings.SERVER_HOST, task_name, question_oid, datetime2str(datetime.datetime.now()), cache_key, str(param),
        error_msg)

    send_instant_mail(mail_to=['lf.weng@idiaoyan.com', 'yan.zhao@idiaoyan.com'],
                      subject='学习之旅报表任务失败', content=content)
