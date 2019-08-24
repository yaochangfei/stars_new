function showTendencyDailyCityMemberTopNChart(result_data) {
    var data_list = init_result_data(result_data);
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
                console.log(datas);
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
        dataZoom: [{
            // startValue: 1,
            start: 55,
            end: 100,
            fillerColor: 'rgba(208,208,208, 0.4)'
        }],
        series: series_list
    };

    var myChartAccuracy = echarts.init(document.getElementById('daily_city_member_topn_chart'));
    myChartAccuracy.clear();
    myChartAccuracy.setOption(option);

    function init_result_data(result_data) {
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
            var result = result_data[i];
            for (var daily_code_o in result) {
                var daily_code = daily_code_o.replace('000000', '');
                xAxis_list.push(daily_code);
                var c_data_list = result[daily_code_o];
                var c_data_list_len = c_data_list.length;
                for (var k = 0; k < 5; k++) {
                    if (k < c_data_list_len) {
                        var c_data = c_data_list[k];
                        var city_name = c_data.city_name;
                        var quantity = c_data.quantity;
                        series_data_dict[k].push({name: city_name, value: quantity})
                    } else {
                        series_data_dict[k].push({name: '', value: ''})
                    }
                }
            }
        }
        return [series_list, xAxis_list]
    }
}