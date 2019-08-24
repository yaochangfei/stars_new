
> #### 初始化数据
> * python init_data.py

> #### 本地服务管理：
> * 启动：python __main__.py -port=8080

> #### 本地任务管理：
> * 启动：
>    + celery worker -A tasks -l INFO
>    + celery beat -A tasks -l INFO

> #### 调用任务的方式
> * function.delay(*args, *kwargs)

> #### 服务器服务管理：
> * 启动：python main.py server start 8080 4
> * 停止：python main.py server stop 8080 4
> * 重启：python main.py server restart 8080 4

> #### 服务器任务管理
> * 启动任务：python main.py tasks start
> * 停止任务：python main.py tasks stop

> #### 解决PyCurl安装错误
> * yum install python36-devel
> * yum install openssl openssl-devel
> * yum install libcurl-devel
> * export PYCURL_CURL_CONFIG=/usr/bin/curl-config
> * export PYCURL_SSL_LIBRARY=nss
> * easy_install pycurl
