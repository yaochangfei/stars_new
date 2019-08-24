/**
 * Created by samuel.zhang on 2016/12/06.
 *
 * 文件下载工具类
 */


/**
 * 下载文件
 *
 * @param action：请求的path
 * @param method：请求方法，GET或POST
 * @param params_dict：请求的参数
 */
function download_file(action, method, params_dict) {
    if (params_dict === undefined) {
        params_dict = {}
    }
    set_xsrf(params_dict);

    //定义一个form表单
    var dowmload_form = $('<form style="display:none"></form>');
    dowmload_form.attr("action", action);
    dowmload_form.attr("method", method);
    for (var name in params_dict) {
        if (name) {
            var input = $('<input type="hidden" />');
            input.attr("name", name);
            input.attr("value", params_dict[name]);
            dowmload_form.append(input);
        }
    }
    //将表单放置在web中
    $("body").append(dowmload_form);
    //表单提交和移除
    dowmload_form.submit();
    dowmload_form.remove();
}