function init_result_data_dimension(result_data, series_name, line_color) {
    var xAxis_data_list = [];
    var series_list = [];
    var series_data = [];
    for (var i = 0; i < result_data.length; i++) {
        var result = result_data[i];
        for (var key in result) {
            xAxis_data_list.push(key);
            var value = result[key];
            var total = value.total;
            var correct = value.correct;
            var accuracy = 0;
            if (total > 0) {
                accuracy = (correct / total * 100).toFixed(2);
            }
            var member_times = Math.ceil(total / 8);
            series_data.push([key, accuracy, member_times])
        }
    }
    var temp_dict = {
        name: series_name,
        type: 'line',
        data: series_data,
        symbol: 'emptyCircle',
        symbolSize: 1,
        itemStyle: {
            color: line_color
        },
        lineStyle: {
            width: 2,
            color: line_color
        }
    };
    series_list.push(temp_dict);
    return [xAxis_data_list, temp_dict]
}

function showTendencyDimensionAccuracy(result_data, dom_id, series_name, line_color) {
    var data_list = init_result_data_dimension(result_data, series_name, line_color);
    var xAxis_data_list = data_list[0];
    var series_dict = data_list[1];
    var myChart = echarts.getInstanceByDom(document.getElementById(dom_id));
    if (myChart === undefined || myChart === null || myChart === "") {
        myChart = echarts.init(document.getElementById(dom_id));
    }
    var option = myChart.getOption();
    if (option) {
        var series_list = option.series;
        var legend_data_list = option.legend[0].data;
        if (legend_data_list.indexOf(series_name) < 0) {
            series_list.push(series_dict);
            legend_data_list.push(series_name);
            option.series = series_list;
            option.legend[0].data = legend_data_list;
            option.series.sort(sort_xAixs_desc)
        }
    } else {
        option = {
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
                data: [series_name],
                show: false
            },
            toolbox: {
                show: false,
                feature: {
                    saveAsImage: {}
                },
                right: 20
            },
            color: ["#7cb5ec"],
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
                padding: 10,
                formatter: function (datas) {
                    var res = datas[0].axisValue + '<br/>';
                    for (var i = 0, length = datas.length; i < length; i++) {
                        if (datas[i].data.name !== "" && datas[i].data.name !== null) {
                            res += datas[i].marker + datas[i].seriesName + '：' + datas[i].value[1] + '%' + ' 人次: ' + datas[i].value[2] + '<br/>';
                        }
                    }
                    return res
                }
            },
            xAxis: {
                type: 'category',
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
                    formatter: '{value} %',
                    textStyle: {
                        color: '#989898'
                    }
                },
                axisTick: {
                    show: false
                },
                min: function (value) {
                    var min_value =  Math.floor(value.min);
                    if(min_value <= 10){
                        return 0
                    }else if(min_value <= 20){
                        return 10
                    }else{
                        var extra_num = min_value % 10;
                        return min_value - 10 - extra_num
                    }
                },
                max: function (value) {
                    var max_value =  Math.floor(value.max);
                    if(max_value >= 90){
                        return 100
                    }else if(max_value >= 80){
                        return 90
                    }else{
                        var extra_num = max_value % 10;
                        return max_value + 20 - extra_num
                    }
                },
                interval: 10
            },
            series: [series_dict]
        };
        option.dataZoom = dataZoom
    }
    myChart.clear();
    myChart.setOption(option);

}
