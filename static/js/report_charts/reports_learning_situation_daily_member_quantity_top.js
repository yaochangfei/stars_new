function showSituationDailyMemberQuantityTopChart(result_data, choice_type) {
    var data_list = init_result_data(result_data, choice_type);
    var series_list = data_list[0];
    var xAxis_list = data_list[1];
    var option = {
        title: {
            text: '',
            left: 'center',
            y: 20,
            textStyle: {
                fontSize: 16,
                fontWeight: 'normal',
                color: '#373737'
            }
        },
        legend: {
            data: ['每日城市新会员Top 5'],
            show: false
        },
        toolbox: {
            show: false,
            feature: {
                saveAsImage: {}
            },
            right: 20
        },
        //  颜色
        color: ["#7cb5ec", "#a0d368", "#f7a35b", "#8085e9", "#f15c80"],
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross',
                crossStyle: {
                    color: '#989898',
                    type: 'dotted'
                },
                lineStyle: {
                    type: 'dotted'
                }
            },
            formatter: function (datas) {
                var res = datas[0].axisValue + '<br/>';
                for (var i = 0, length = datas.length; i < length; i++) {
                    if (datas[i].data.name !== "" && datas[i].data.name !== null) {
                        res += datas[i].marker + datas[i].data.name + '：' + datas[i].data.value + '<br/>';
                    }
                }
                return res
            },
            borderRadius: 0,
            position: ['35%', 10],
            borderWidth: 0,
            borderRadius: 2,
            textStyle: {
                color: '#fff',
                lineHeight: 12,
                fontSize: 12
            },
            backgroundColor: 'rgba(72,84,101, 0.8)',
            padding: 10
        },
        xAxis: {
            data: xAxis_list,
            axisLine: {
                lineStyle: {
                    color: '#989898',
                    width: 1
                }
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                textStyle: {
                    color: '#989898'
                }
            }
        },
        yAxis: {
            splitLine: {
                show: false
            },
            axisLine: {
                lineStyle: {
                    color: '#989898',
                    width: 1
                }
            },
            axisLabel: {
                textStyle: {
                    color: '#989898'
                }
            },
            axisTick: {
                show: false
            }
        },
        series: series_list
    };
    option.dataZoom = dataZoom;
    var myChart = echarts.getInstanceByDom(document.getElementById('daily_city_member_topn_chart'));
    if (myChart === undefined || myChart === null || myChart === "") {
        myChart = echarts.init(document.getElementById('daily_city_member_topn_chart'));
    } else {
        myChart.dispose();
        myChart = echarts.init(document.getElementById('daily_city_member_topn_chart'));
    }
    myChart.clear();
    myChart.setOption(option);

    function init_result_data(result_data, choice_type) {
        var series_list = [];
        var series_data_dict = {};
        var xAxis_list = [];
        for (var m = 0; m < 5; m++) {
            series_data_dict[m] = [];
            series_list.push({
                type: 'bar',
                data: series_data_dict[m]
            })
        }
        for (var i = 0; i < result_data.length; i++) {
            var result_list = result_data[i];
            if (choice_type === 2) {
                result_list.sort(function (a, b) {
                    return b.times - a.times

                });
            }
            var result_list_len = result_list.length;
            if (result_list_len > 0) {
                var daily_code = result_list[0].date;
                xAxis_list.push(daily_code);
            }
            for (var j = 0; j < 5; j++) {
                if (j < result_list_len) {
                    var result = result_list[j];

                    var city_name = result.title;
                    if (choice_type === 1) {
                        var quantity = result.quantity;
                        series_data_dict[j].push({name: result.province_title +' '+city_name, value: quantity})
                    } else if (choice_type === 2) {
                        var times = result.times;
                        series_data_dict[j].push({name: result.province_title +' '+city_name, value: times})
                    }

                } else {
                    series_data_dict[j].push({name: '', value: ''})
                }
            }
        }
        return [series_list, xAxis_list]
    }
}

function init_top_result_data(result_data, choice_type) {
    var series_list = [];
    var series_data_dict = {};
    for (var m = 0; m < 5; m++) {
        series_data_dict[m] = [];
        series_list.push({
            type: 'bar',
            data: series_data_dict[m]
        })
    }
    for (var i = 0; i < result_data.length; i++) {
        var result_list = result_data[i];
        if (choice_type === 2) {
            result_list.sort(function (a, b) {
                return b.times - a.times

            });
        }
        var result_list_len = result_list.length;
        for (var j = 0; j < 5; j++) {
            if (j < result_list_len) {
                var result = result_list[j];

                var city_name = result.title;
                if (choice_type === 1) {
                    var quantity = result.quantity;
                    series_data_dict[j].push({name: result.province_title +' '+ city_name, value: quantity})
                } else if (choice_type === 2) {
                    var times = result.times;
                    series_data_dict[j].push({name: result.province_title +' '+city_name, value: times})
                }

            } else {
                series_data_dict[j].push({name: '', value: ''})
            }
        }

    }
    return series_list
}

