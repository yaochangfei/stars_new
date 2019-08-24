import os
import traceback
from datetime import datetime

import xlsxwriter

from caches.redis_utils import RedisCache
from enums import KEY_CACHE_RACE_REPORT_DOWNLOAD
from logger import log_utils
from settings import SITE_ROOT
from tasks import app
from tasks.utils import write_sheet_enter_data, write_sheet_daily_increase_people

logger = log_utils.get_logging('task_race_export_data', 'task_race_export_data.log')


@app.task(bind=True, queue='race_export_data')
def start_get_export_data(self, race_cid, title, export_title):
    """启动任务

    :param self:
    :param race_cid:
    :param title:
    :param export_title:
    :return:
    """
    logger.info('[START] race_export_data(%s), title=(%s)' % (self.request.id, title))
    try:
        #  准备中
        RedisCache.hset(KEY_CACHE_RACE_REPORT_DOWNLOAD, export_title, 2)
        export_name = os.path.join(SITE_ROOT, 'static/export/%s.xlsx' % export_title)
        logger.info('middle')
        workbook = xlsxwriter.Workbook(export_name)
        now = datetime.now()
        daily_code = format(now, '%Y%m%d')
        pre_match = {'daily_code': {'$lte': daily_code}}
        write_sheet_enter_data(workbook, race_cid, '每日参与人数', pre_match=pre_match, count_type='$enter_count')
        # write_sheet_daily_increase_people(workbook, race_cid, '每日新增参与人数', pre_match=pre_match)
        write_sheet_enter_data(workbook, race_cid, '每日新增参与人数', pre_match=pre_match, count_type='$increase_enter_count')
        write_sheet_enter_data(workbook, race_cid, '每日参与人次', pre_match=pre_match,
                               count_type='$enter_times')
        # write_sheet_enter_data(workbook, race_cid, '每日通关人数', pre_match={'updated_dt': {'$lte': now}},
        #                        count_type='$pass_num')
        workbook.close()

    except Exception:
        logger.info(traceback.format_exc())

    logger.info('[ END ] race_export_data(%s), title=(%s)' % (self.request.id, title))
    #  完成
    RedisCache.hset(KEY_CACHE_RACE_REPORT_DOWNLOAD, export_title, 1)
