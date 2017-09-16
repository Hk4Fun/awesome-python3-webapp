#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
async web application
异步web初级框架
"""
__author__ = 'Hk4Fun'

# logging输出的信息可以帮助我们理解程序执行的流程，对后期除错也非常有帮助
# logging.basicConfig配置需要输出的信息等级，INFO指的是普通信息，INFO以及INFO以上的比如说WARNING警告信息也会被输出
# 日志级别大小关系为：CRITICAL > ERROR > WARNING > INFO > DEBUG > NOTSET
# logging.basicConfig函数各参数:
# filename: 指定输出的日志文件名，即可以保存日志到文件
# filemode: 和file函数意义相同，指定日志文件的打开模式，'w'或'a'
# format: 指定输出的格式和内容，format可以输出很多有用信息：
#  %(levelno)s: 打印日志级别的数值
#  %(levelname)s: 打印日志级别名称
#  %(pathname)s: 打印当前执行程序的路径，其实就是sys.argv[0]
#  %(filename)s: 打印当前执行程序名
#  %(funcName)s: 打印日志的当前函数
#  %(lineno)d: 打印日志的当前行号
#  %(asctime)s: 打印日志的时间
#  %(thread)d: 打印线程ID
#  %(threadName)s: 打印线程名称
#  %(process)d: 打印进程ID
#  %(message)s: 打印日志信息
# datefmt: 指定时间格式，同time.strftime()
# level: 设置日志级别，默认为logging.WARNING
# stream: 指定将日志的输出流，可以指定输出到sys.stderr,sys.stdout或者文件，默认输出到sys.stderr，当stream和filename同时指定时，stream被忽略
import logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(message)s",  # 日志格式
                    datefmt="[%Y-%m-%d %H:%M:%S]")  # 日期格式
# asyncio官方文档：https://docs.python.org/3/library/asyncio.html
import asyncio, os, json, time
# aiohttp是基于asyncio实现的HTTP框架，官方文档：http://aiohttp.readthedocs.io/en/stable/
from aiohttp import web
from datetime import datetime

# 定义处理http访问请求的方法
def index(request):
    # 该方法返回内容为body，加上content_type可以直接访问，否则浏览器会下载该网页
    return web.Response(body=b'<h1>Awesome</h1>', content_type='text/html')


async def init(loop):
    # 往web对象中加入消息循环，生成一个支持异步IO的对象
    app = web.Application(loop=loop)
    # 将浏览器通过GET方式传过来的对根目录的请求转发给回调函数index处理，
    app.router.add_route('GET', '/', index)
    # 监听127.0.0.1地址的9000端口
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    # 打印日志信息
    logging.info('server started at http://127.0.0.1:9000...')
    # 一定要把监听http请求的这个协程返回，这样就能持续监听http请求
    return srv

# 以下三步一步都不能少
loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
