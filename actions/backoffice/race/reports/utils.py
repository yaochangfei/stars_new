from db import CATEGORY_MEMBER_DICT


def replace_race_other_area(x_axis_data, series_data, none_index='', is_sort = False):
    """
    将None替换成其他区并且把它放在最后
    :param x_axis_data:
    :param series_data:
    :param none_index
    :return:
    """
    if None in x_axis_data:
        none_index = x_axis_data.index(None)
    if none_index or none_index == 0:
        x_axis_data[none_index] = '其他'
        x_axis_data[none_index], x_axis_data[-1] = x_axis_data[-1], x_axis_data[none_index]
        if series_data:
            series_data[none_index], series_data[-1] = series_data[-1], series_data[none_index]
    #  柱状图是需要排序得
    if is_sort:
        bubble_sort(series_data, x_axis_data)
    return x_axis_data, series_data


async def deal_with_series_data(stats, x_axis_data, series_data):
    """
    筛选结果可能导致某一个区的数据没有 所以可能导致数据出错
    :param x_axis_data:
    :param stats
    :param series_data:
    :return:
    """
    if len(series_data) != len(x_axis_data):
        series_data = [0 for _ in range(len(x_axis_data))]
        for s in stats:
            if s.id in x_axis_data:
                index = x_axis_data.index(s.id)
                series_data[index] = s.sum
    return series_data


async def deal_with_important_people(stats, x_axis_data, series_data):
    """
    筛选结果可能导致某一个区的数据没有 所以可能导致数据出错 处理重点人群的
    :param x_axis_data:
    :param sum_way:
    :param stats
    :param series_data:
    :return:
    """
    if len(series_data) != len(x_axis_data):
        series_data = [0 for _ in range(len(x_axis_data))]
        for s in stats:
            if CATEGORY_MEMBER_DICT[s.id] in x_axis_data:
                index = x_axis_data.index(CATEGORY_MEMBER_DICT[s.id])
                series_data[index] = s.sum
    return series_data


#  冒泡排序
def swap(list1, i, j):
    """定义一个交换元素的方法，方便后面调用。"""
    temp = list1[i]
    list1[i] = list1[j]
    list1[j] = temp


def bubble_sort(list1, list2):
    """
    冒泡排序，时间复杂度O(n^2)
    """
    length = len(list1)
    for i in range(length):
        j = length - 2
        while j >= i:
            if list1[j] < list1[j + 1]:
                swap(list2, j, j + 1)
                swap(list1, j, j + 1)
            j -= 1
