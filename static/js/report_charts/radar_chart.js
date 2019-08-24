function showRadarChart(result_data, series_name, chart_color) {

    var series_dict = get_series_dict(result_data, series_name, chart_color);
    var myChart = echarts.getInstanceByDom(document.getElementById('radar_chart'));
    if (myChart === undefined || myChart === null || myChart === "") {
        myChart = echarts.init(document.getElementById('radar_chart'));
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
        }
    } else {
        option = {
            //, "#a0d368", "#f7a35b", "#8085e9", "#f15c80"
            color: ["#7CB5EC"],
            title: {
                text: '全民科学素质总体水平',
                left: 'center',
                y: 20,
                textStyle: {
                    fontSize: 16,
                    fontWeight: 'normal',
                    color: '#373737'
                },
                show: false
            },
            legend: {
                data: [series_name],
                show: false
            },
            tooltip: {
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
            toolbox: {
                show: false,
                feature: {
                    saveAsImage: {}
                },
                right: 20
            },
            radar: {
                radius: '70%',
                center: ['50%', '55%'],
                axisLine: {
                    lineStyle: {
                        color: radar_line_color
                    }
                },
                splitLine: {
                    show: true,
                    lineStyle: {
                        color: radar_line_color
                    }
                },
                splitArea: {
                    show: true,
                    areaStyle: {
                        color: radar_split_area
                    }
                },
                indicator: [
                    {text: '总体状况', max: 100},
                    {text: '科学观念与方法', max: 100},
                    {text: '数学与信息', max: 100},
                    {text: '物质与能量', max: 100},
                    {text: '生命与健康', max: 100},
                    {text: '地球与环境', max: 100},
                    {text: '工程与技术', max: 100},
                    {text: '科技与社会', max: 100},
                    {text: '能力与发展', max: 100}
                ],
            },
            series: [series_dict]
        };
    }
    if(radar_title_color !== null){
        for(i =0;i < option.radar.indicator.length; i++){
            option.radar.indicator[i]['color'] = dimension_text_x_color
        }
    }
    var rgb_color_list = ["rgba(62, 130, 247, 0.17)", "rgba(149, 62, 247, 0.17)", "rgba(255, 127, 80, 0.17)", "rgba(135, 206, 250, 0.17)", "rgba(218, 112, 214, 0.17)"];
    var series_list = option.series;
    if (series_list) {
        for (var i = 0; i < series_list.length; i++) {
            series_list[i].data[0].areaStyle.color = rgb_color_list[i];
        }
    }
    myChart.clear();
    myChart.setOption(option, {'notMerge': true})
}

function get_xAxis(result_data) {
    var xAxis_list = [];
    if (result_data) {
        for (var key in result_data) {
            xAxis_list.push(key + '题')
        }
    }
    return xAxis_list
}

function get_series_dict(result_data, series_name, chart_color) {
    var value_list = [];
    var series_data_list = [];
    var total_sum = 0;
    var correct_sum = 0;
    if (result_data) {
        for (var i = 0; i < result_data.length; i++) {
            var data = result_data[i];
            total_sum += data.total;
            correct_sum += data.correct;
            if (data.total) {
                value_list.push((data.correct * 100 / data.total).toFixed(2))
            } else {
                value_list.push(0)
            }
        }
    }
    var total_percent = (correct_sum * 100 / total_sum).toFixed(2);
    value_list.unshift(total_percent);
    series_data_list.push({
        name: series_name,
        value: value_list,
        areaStyle: {
            'color': "rgba(62, 130, 247, 0.17)"
        },
        itemStyle: {color: chart_color},
        lineStyle: {
            color: chart_color,
            width: 1
        }
    });
    var series_dict = {
        type: 'radar',
        symbol: 'Circle',
        data: series_data_list
    };
    return series_dict

}
