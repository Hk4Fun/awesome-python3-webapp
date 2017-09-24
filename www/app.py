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
from datetime import datetime
import orm
import logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(message)s",  # 日志格式
                    datefmt="[%Y-%m-%d %H:%M:%S]")  # 日期格式
from webframe import add_routes, add_static
# asyncio官方文档：https://docs.python.org/3/library/asyncio.html
import asyncio, os, json, time
# aiohttp是基于asyncio实现的HTTP框架，官方文档：http://aiohttp.readthedocs.io/en/stable/
from aiohttp import web
# Environment指jinja2模板的环境配置，FileSystemLoader是文件系统加载器，用来加载模板路径
from jinja2 import Environment, FileSystemLoader
from handlers import cookie2user, COOKIE_NAME

# # 定义处理http访问请求的方法
# def index(request):
#     # 该方法返回内容为body，加上content_type可以直接访问，否则浏览器会下载该网页
#     return web.Response(body=b'<h1>Awesome</h1>', content_type='text/html')
#
#
# async def init(loop):
#     # 往web对象中加入消息循环，生成一个支持异步IO的对象
#     app = web.Application(loop=loop)
#     # 将浏览器通过GET方式传过来的对根目录的请求转发给回调函数index处理，
#     app.router.add_route('GET', '/', index)
#     # 监听127.0.0.1地址的9000端口
#     srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
#     # 打印日志信息
#     logging.info('server started at http://127.0.0.1:9000...')
#     # 一定要把监听http请求的这个协程返回，这样就能持续监听http请求
#     return srv


#初始化jinja2模板，配置jinja2的环境
def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    #设置解析模板需要用到的环境变量
    options = dict(
        autoescape = kw.get('autoescape', True),#自动转义xml/html的特殊字符（就是在渲染模板时自动把变量中的<>&等字符转换为&lt;&gt;&amp;）
        block_start_string = kw.get('block_start_string', '{%'),#设置代码块起始字符串，还有下面那句是结束字符串
        block_end_string = kw.get('block_end_string', '%}'),#意思就是{%和%}中间是python代码，而不是html
        variable_start_string = kw.get('variable_start_string', '{{'),#这两句分别设置了变量的起始和结束字符串
        variable_end_string = kw.get('variable_end_string', '}}'),#就是说{{和}}中间是变量，看过templates目录下的test.html文件后就很好理解了
        auto_reload = kw.get('auto_reload', True)#当模板文件被修改后，下次请求加载该模板文件的时候会自动重新加载修改后的模板文件
    )
    path = kw.get('path', None)#从**kw中获取模板路径，默认为None
    if path is None:#如果path为None，则将当前文件所在目录下的templates目录设置为模板文件的目录
        #下面这句代码其实是三个步骤，先取当前文件也就是app.py的绝对路径，然后取这个绝对路径的目录部分，最后在这个目录后面加上templates子目录
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s' % path)
    # loader=FileSystemLoader(path)指的是到哪个目录下加载模板文件，同时把设置好的options传入，生成实例
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None) # 过滤器字典，其值为一个个函数，后面在模板展示的时候会用到
    if filters is not None:
        for name, f in filters.items():# 将过滤器加入模板环境中
            env.filters[name] = f
    app['__templating__'] = env#前面已经把jinja2的环境配置都赋值给env了，这里再把env存入app的dict中，这样app就知道要到哪儿去找模板，怎么解析模板。

# ------------------------------------------拦截器middlewares设置----------------------------------------
# 以下是一些middleware(中间件), 相当于装饰器，可以在url处理函数处理前后对url进行处理
# 每个middle factory接收2个参数,一个app实例,一个handler, 并返回一个新的handler


# 当有http请求的时候，先通过logging.info输出请求的信息，其中包括请求的方法和路径
async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: %s %s' % (request.method, request.path))
        return (await handler(request))# 日志记录完毕之后, 调用传入的handler继续处理请求
    return logger

# 打印post提交的数据
async def data_factory(app, handler):
    async def parse_data(request):
        # 打印的数据是针对post方法传来的数据,若http method非post,将跳过,直接调用handler处理请求
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):# 打印json数据
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):# 打印表单数据
                request.__data__ = await request.post()
                logging.info('request form: %s' % str(request.__data__))
        return (await handler(request))
    return parse_data

# 在处理请求之前,先将cookie解析出来,并将登录用户绑定到request对象上
# 这样后续的url处理函数就可以直接拿到登录用户
# 以后的每个请求,都是在这个middle之后处理的,都已经绑定了用户信息
async def auth_factory(app, handler):
    async def auth(request):
        logging.info("check user: %s %s" % (request.method, request.path))
        request.__user__ = None
        cookie_str = request.cookies.get(COOKIE_NAME) # 通过cookie名取得加密cookie字符串(handlers.py中有定义set_cookie)
        if cookie_str:
            user = await cookie2user(cookie_str) # 验证cookie,并得到用户信息
            if user:
                logging.info("set current user: %s" % user.email)
                request.__user__ = user # 将用户信息绑定到请求上
            # 请求的路径是管理页面,但用户非管理员,将会重定向到登录页面
        if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
            return web.HTTPFound('/signin')
        return (await handler(request))
    return auth

# 上面factory是在url处理函数之前先对请求进行了处理,以下则在url处理函数之后进行处理
# 其将request handler的返回值根据返回的类型转换为web.Response对象，吻合aiohttp框架的需求
# 注意jinja2模板的渲染在该函数进行
async def response_factory(app, handler):
    async def response(request):
        # 调用handler来处理url请求,并返回响应结果
        r = await handler(request)
        # 若响应结果为StreamResponse,直接返回
        # StreamResponse是aiohttp定义response的基类,即所有响应类型都继承自该类
        # StreamResponse主要为流式数据而设计
        if isinstance(r, web.StreamResponse):
            return r
        # 若响应结果为字节流,则将其作为应答的body部分,并设置响应类型为流型
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = "application/octet-stream"
            return resp
        # 若响应结果为字符串
        if isinstance(r, str):
            if r.startswith("redirect:"):# 判断响应结果是否为重定向，若是则返回重定向的地址
                return web.HTTPFound(r[9:])# 把r字符串之前的"redirect:"去掉
            # 响应结果不是重定向,则以utf-8对字符串进行编码,作为body并设置相应的响应类型
            resp = web.Response(body = r.encode("utf-8"))
            resp.content_type = "text/html;charset=utf-8"
            return resp
        # 若响应结果为字典,则尝试获取它的模板属性，其值为模板页
        if isinstance(r, dict):
            template = r.get("__template__")
            # 若不存在对应模板,则将字典调整为json格式返回,并设置响应类型为json
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode("utf-8"))
                resp.content_type = "application/json;charset=utf-8"
                return resp
            # 存在对应模板的,则将套用模板,用request handler的结果指定的模板页进行渲染
            else:
                # 增加__user__,前端页面将依次来决定是否显示用户信息，
                # __user__在用户登陆后被auth_factory绑定到request中
                r["__user__"] = request.__user__
                resp = web.Response(body=app["__templating__"].get_template(template).render(**r).encode("utf-8"))
                resp.content_type = "text/html;charset=utf-8"
                return resp
        # 若响应结果为整型的
        # 此时r为状态码,即404,500等
        if isinstance(r, int) and r >=100 and r<600:
            return web.Response
        # 若响应结果为元组,并且长度为2
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            # t为http状态码,m为错误描述
            # 判断t是否满足100~600的条件
            if isinstance(t, int) and t>= 100 and t < 600:
                # 返回状态码与错误描述
                return web.Response(t, str(m))
        # 如果都不是则默认以字符串形式返回响应结果,设置类型为普通文本
        resp = web.Response(body=str(r).encode("utf-8"))
        resp.content_type = "text/plain;charset=utf-8"
        return resp
    return response

# 这个时间过滤器的作用其实可以猜出来，返回日志创建的大概时间，用于显示在日志标题下面
# 这个在（渲染）模板中会用到，因为模板的时间输出为时间戳（数据库中定义的），需要进行时间格式的转换
# 在模板里用法如下：<p class="uk-article-meta">发表于{{ blog.created_at|datetime }}</p>
def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

async def init(loop):
    #创建数据库连接池
    await orm.create_pool(loop=loop, host='127.0.0.1', port=3306,
                          user='www-data', password='www-data', db='awesome')
    #设置中间件（拦截器）
    app = web.Application(loop=loop, middlewares=[
        logger_factory, response_factory, data_factory, auth_factory
    ])
    #初始化jinja2模板，并传入时间过滤器
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    #下面这两个函数在webframe模块中，分别把handlers中的url处理函数注册到app中以及添加静态文件路径
    add_routes(app, 'handlers')#handlers指的是handlers模块也就是handlers.py,这里不能加'.py'
    add_static(app)
    #异步监听访问请求
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

# 以下三步一步都不能少
loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
