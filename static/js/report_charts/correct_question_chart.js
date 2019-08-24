function showCorrectQuestionChart(result_data, series_name, chart_color) {
    var xAxis_list = get_xAxis(result_data);
    var series_list = get_series(result_data, series_name, chart_color);
    var myChart = echarts.getInstanceByDom(document.getElementById('correct_question_chart'));
    if (myChart === undefined || myChart === null || myChart === "") {
        myChart = echarts.init(document.getElementById('correct_question_chart'));
    }
    var series_name_list = [series_name];
    if (series_name === "全体人群答对题目分布") {
        series_name_list.push("正太分布")
    }
    var option = myChart.getOption();
    if (option) {
        var option_series_list = option.series;
        var new_series_list = option_series_list.concat(series_list);
        option.series = new_series_list;

        var legend_data_list = option.legend[0].data;
        if (legend_data_list.indexOf(series_name) < 0) {
            legend_data_list.push(series_name);
            if (series_name === "全体人群答对题目分布") {
                legend_data_list.push("正太分布")
            }
            option.legend[0].data = legend_data_list;
        }

    } else {
        option = {
            //, "#a0d368", "#f7a35b", "#8085e9", "#f15c80"
            color: ["#7cb5ec"],
            title: {
                subtext: '',
                left: 'center',
                y: 10,
                subtextStyle: {
                    color: '#373737',
                    fontSize: 16
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
                data: xAxis_list,
                axisTick: {
                    show: false
                },
                axisLabel: {
                    interval: 0,
                    // rotate: -30,
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
            series: series_list
        };
    }
    myChart.clear();
    myChart.setOption(option, {'notMerge': true});

    function get_xAxis(result_data) {
        var xAxis_list = [];
        if (result_data) {
            for (var key in result_data) {
                if (key === 0 || key === '0') continue;
                xAxis_list.push(key + '题')
            }
        }
        console.log(xAxis_list);
        return xAxis_list
    }

}


function get_series(result_data, series_name, chart_color) {
    var value_list = [];
    var quantity_sum = 0;
    var series_list = [];
    var key_list = [];
    var bar_data_list = [];
    var line_data_list = [];
    if (result_data) {
        for (var key in result_data) {
            var value = result_data[key];
            quantity_sum += value;
            if (key === 0 || key === '0') continue;
            value_list.push(value);
            key_list.push(key);
        }
        if (value_list && quantity_sum) {
            for (var i = 0; i < value_list.length; i++) {
                line_data_list.push(((value_list[i] * 100 / quantity_sum) + 10).toFixed(2));
                bar_data_list.push((value_list[i] * 100 / quantity_sum).toFixed(2));
            }
        }
    }
    var line_series = {
        'data': line_data_list,
        'name': '',
        'type': 'line',
        'smooth': true,
        'symbol': 'none',
        'itemStyle': {
            'normal': {
                'color': "#7CB5EC"
            }
        }
    };
    series_list.push({
        name: series_name,
        data: bar_data_list,
        type: 'bar',
        barMaxWidth: '50%',
        barGap: '0%',
        label: {
            show: true,
            position: 'top',
        },
        itemStyle: {
            color: chart_color
        }
    });
    if (series_name === "全体人群答对题目分布") {
        series_list.push(line_series);
    }
    return series_list
}