import sys
import traceback

from db.models import MemberDailyDimensionStatistics
from initialize.report.init_member_subject_statistics_sub import create_model


def get_model_by_index(index):
    """

    :param index:
    :return:
    """
    if index == -1:
        return MemberDailyDimensionStatistics
    else:
        return create_model(MemberDailyDimensionStatistics, index)


def merge_statistics(first_model, second_model, skip_num, limit_num):
    """

    :param first_model:
    :param second_model:
    :return:
    """

    cursor = second_model.sync_find().skip(skip_num).limit(limit_num).batch_size(128)
    for index, data in enumerate(cursor):
        try:
            param = {'daily_code': data.daily_code, 'member_cid': data.member_cid, 'dimension': data.dimension,
                     'province_code': data.province_code, 'city_code': data.city_code,
                     'district_code': data.district_code, 'gender': data.gender, 'age_group': data.age_group,
                     'education': data.education}

            source = first_model.sync_find_one(param)
            if not source:
                source = first_model(**param)
                source.dimension = data.dimension

            source.subject_total_quantity += data.subject_total_quantity
            source.subject_correct_quantity += data.subject_correct_quantity
            source.sync_save()

            print(index, data.cid)
        except Exception:
            print(traceback.format_exc())


if __name__ == '__main__':
    first = int(sys.argv[1])
    secon = int(sys.argv[2])
    skip_num = int(sys.argv[3])
    limit_num = int(sys.argv[4])

    merge_statistics(get_model_by_index(first), get_model_by_index(secon), skip_num, limit_num)


# python initialize/report/daily/merge_stat.py 12 13 26000 10000 > merge_stat_sub_12_13.2.log > 2>&1 &
# python initialize/report/daily/merge_stat.py 12 13 36000 10000 > merge_stat_sub_12_13.3.log > 2>&1 &
# python initialize/report/daily/merge_stat.py 12 13 46000 10000 > merge_stat_sub_12_13.4.log > 2>&1 &
# python initialize/report/daily/merge_stat.py 12 13 56000 10000 > merge_stat_sub_12_13.5.log > 2>&1 &
#
# python initialize/report/daily/merge_stat.py 14 15 26000 10000 > merge_stat_sub_14_15.2.log > 2>&1 &
# python initialize/report/daily/merge_stat.py 14 15 36000 10000 > merge_stat_sub_14_15.3.log > 2>&1 &
# python initialize/report/daily/merge_stat.py 14 15 46000 10000 > merge_stat_sub_14_15.4.log > 2>&1 &
# python initialize/report/daily/merge_stat.py 14 15 56000 10000 > merge_stat_sub_14_15.5.log > 2>&1 &
#
# python initialize/report/daily/merge_stat.py 16 17 26000 10000 > merge_stat_sub_16_17.2.log > 2>&1 &
# python initialize/report/daily/merge_stat.py 16 17 36000 10000 > merge_stat_sub_16_17.3.log > 2>&1 &
# python initialize/report/daily/merge_stat.py 16 17 46000 10000 > merge_stat_sub_16_17.4.log > 2>&1 &
# python initialize/report/daily/merge_stat.py 16 17 56000 10000 > merge_stat_sub_16_17.5.log > 2>&1 &
#
# python initialize/report/daily/merge_stat.py 18 19 26000 10000 > merge_stat_sub_18_19.2.log > 2>&1 &
# python initialize/report/daily/merge_stat.py 18 19 36000 10000 > merge_stat_sub_18_19.3.log > 2>&1 &
# python initialize/report/daily/merge_stat.py 18 19 46000 10000 > merge_stat_sub_18_19.4.log > 2>&1 &
# python initialize/report/daily/merge_stat.py 18 19 56000 10000 > merge_stat_sub_18_19.5.log > 2>&1 &
#
# python initialize/report/daily/merge_stat.py 20 21 26000 10000 > merge_stat_sub_20_21.2.log > 2>&1 &