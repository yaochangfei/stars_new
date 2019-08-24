import os
import traceback
import datetime

from celery.schedules import crontab

from db.models import Race
from initialize.export.export_member_statistic import export_race
from initialize.export.export_race_one_week_info import export_race_one_week_excel
from initialize.export.gene_race_middle import generate_total
from initialize.incremental.member_statistic import task_one_day, get_date_range, clear_redis_cache
from logger import log_utils
from services.email_service import send_instant_mail
from tasks import app
from settings import SITE_ROOT
from tasks.instances.task_member_statistics_single import start_single_member_statistics

logger = log_utils.get_logging('member_stat_schedule', 'member_stat_schedule.log')
app.register_schedule('member_stat_schedule',
                      'tasks.instances.task_member_statistics_schedule.start_member_statistics_schedule',
                      crontab(hour=1, minute=30))


@app.task(bind=True, queue='member_stat_schedule')
def start_member_statistics_schedule(self):
    """
    定时启动每日会员统计
    :param self:
    :return:
    """
    mail_send_to = ['shuai.xu@idiaoyan.com', 'tw.lu@idiaoyan.com', 'yan.zhao@idiaoyan.com',
                    'chy.wang@idiaoyan.com', 'jian.zhou@idiaoyan.com', 'lf.weng@idiaoyan.com']
    copy_to = ['jian.zhou@idiaoyan.com']
    task_start_dt = datetime.datetime.now()
    pre_date = task_start_dt - datetime.timedelta(days=1)
    daily_code = format(pre_date, '%Y%m%d')
    logger.info('START(%s) at %s' % (self.request.id, task_start_dt))
    try:
        race_cid_list = Race.sync_distinct('cid', {'status': 1})
        for race_cid in race_cid_list:
            if race_cid == '160631F26D00F7A2DC56DAE2A0C4AF12':
                continue
            logger.info('START RACE : %s' % race_cid)
            clear_redis_cache(race_cid)
            task_one_day(race_cid, daily_code)
            logger.info('END RACE : %s' % race_cid)

        file_list = []
        for race_cid in race_cid_list:
            if race_cid == '160631F26D00F7A2DC56DAE2A0C4AF12':
                continue
            title = export_race(race_cid)
            file_list.append(os.path.join(SITE_ROOT, title))
        send_instant_mail(mail_to=mail_send_to, subject='会员信息%s' % daily_code, copy_to=copy_to,
                          content='上面的附件是截止到%s的会员导出数据,请注意查收！' % daily_code,
                          attachments=file_list)
        # 中间表B表
        generate_total(pre_date)
        excel_title_list = export_race_one_week_excel()
        logger.info(excel_title_list)
        send_instant_mail(mail_to=mail_send_to, subject='一周数据', copy_to=copy_to,
                          content='上面的附件是正在举行的四个活动截止到%s的一周数据，请各位查收！' % daily_code,
                          attachments=excel_title_list)

    except Exception:
        logger.error(str(traceback.format_exc()))

    task_end_dt = datetime.datetime.now()

    logger.info('END(%s) at %s' % (self.request.id, task_end_dt))
    logger.info('Cost Of Task: %s' % (task_end_dt - task_start_dt))


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


if __name__ == '__main__':
    file = os.path.join(SITE_ROOT, '2019年六安市公民科学素质大擂台_会员信息_2019-07-29.xlsx')
    print(send_instant_mail(mail_to=['jian.zhou@idiaoyan.com'], subject='附件邮件22',
                            content='这仅仅是一个测试！',
                            attachments=[file]))
    # start_member_statistics_schedule()
    # 六安 CA755167DEA9AA89650D11C10FAA5413 贵州 F742E0C7CA5F7E175844478D74484C29
    # 安徽 3040737C97F7C7669B04BC39A660065D 扬州 DF1EDC30F120AEE93351A005DC97B5C1
