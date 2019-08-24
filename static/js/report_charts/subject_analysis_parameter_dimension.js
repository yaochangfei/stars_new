function shoeSubjectAnalysiParameterDimension(result_data, dom_id, title, series_name, chart_color) {
    var data_list = init_result_data_single_dimension(result_data, series_name, chart_color);
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
            option.legend[0].data = legend_data_list
        }
    } else {
        option = {//, "#a0d368", "#f7a35b", "#8085e9", "#f15c80"
            color: ["#7cb5ec"],
            title: {
                text: title,
                left: 'center',
                y: 20,
                textStyle: {
                    fontSize: 16,
                    fontWeight: 'normal',
                    color: dimension_text_x_color
                }
            },
            legend: {
                data: [series_name],
                show: false
            },
            grid: {
                borderWidth: 0
            },
            tooltip: {
                trigger: 'item'
            },
            toolbox: {
                show: false,
                feature: {
                    saveAsImage: {}
                },
                right: 20
            },
            calculable: true,
            xAxis: {
                type: 'category',
                data: xAxis_data_list,
                axisTick: {
                    show: false
                },
                axisLabel: {
                    interval: 0,
                    textStyle: {
                        color: '#989898'
                    }
                },
                axisLine: {
                    lineStyle: {
                        color: '#989898',
                        width: 1
                    }
                },
                splitLine: {show: false}
            },
            yAxis: {
                type: 'value',
                axisLabel: {
                    formatter: '{value} %',
                    textStyle: {
                        color: '#989898'
                    }
                },
                axisTick: {
                    show: false
                },
                axisLine: {
                    lineStyle: {
                        color: '#989898',
                        width: 1
                    }
                },
                splitLine: {show: false}
            },
            series: [series_dict]
        }
    }
    myChart.clear();
    myChart.setOption(option);
}

function init_result_data_single_dimension(result_data, series_name, chart_color) {
    var xAxis_data_list = [];
    var series_list = [];
    var series_data = [];
    result_data.sort(function (a, b) {
        return a.ordered - b.ordered
    });
    for (var i = 0; i < result_data.length; i++) {
        var result = result_data[i];
        xAxis_data_list.push(result.title);
        var total = result.total;
        var correct = result.correct;
        var accuracy = 0;
        if (total > 0) {
            accuracy = (correct / total * 100).toFixed(2);
        }
        series_data.push(accuracy)
    }
    var temp_dict = {
        'data': series_data,
        'name': series_name,
        'type': 'bar',
        'barMaxWidth': '40%',
        'barGap': '0%',
        'label': {
            'show': true,
            'position': 'top',
            'textStyle': {
                'color': dimension_text_x_color
            },
        },
        'itemStyle': {
            color: chart_color
        },
    };
    series_list.push(temp_dict);
    return [xAxis_data_list, temp_dict]
}