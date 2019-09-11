#!/usr/bin/python



from logger import log_utils
from tasks import app

logger = log_utils.get_logging('task_lottery')


@app.task(bind=True, queue='task_distribute_reaward')
def start_distribute_reaward(self, open_id, race_cid):
    logger.info('START(%s): lottery queuing, member_id=%s ' % (self.request.id, open_id))
