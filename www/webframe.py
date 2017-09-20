#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基于aiohttp的web框架，进一步简化Web开发
aiohttp相对比较底层，想要使用框架时编写更少的代码，就只能在aiohttp框架上封装一个更高级的框架
Web框架的设计是完全从使用者出发，目的是让框架使用者编写尽可能少的代码
"""
__author__ = 'Hk4Fun'

import asyncio
# 用来修改文件模块路径
import os
# 用来获取函数的参数信息
import inspect
import logging
# 用来还原被装饰函数的属性，如__name__
import functools
# 用来解析url的查询参数
from urllib import parse
from aiohttp import web
# 引用自己的模块，检测api调用错误，这里可以先忽略它
from apis import APIError


# 这是个装饰器，在handlers模块中被引用，其作用是给http请求添加请求方法和请求路径这两个属性
# 这是个三层嵌套的decorator（装饰器），目的是可以在decorator本身传入参数
# 这个装饰器将一个函数映射为一个URL处理函数
def get(path):
    def decorator(func):  # 传入参数是函数
        # python内置的functools.wraps装饰器作用是把装饰后的函数的__name__属性变为原始的属性，即func的属性
        # 因为当不使用该装饰器时函数的__name__为wrapper，而不是func
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'  # 给原始函数添加请求方法 “GET”
        wrapper.__route__ = path  # 给原始函数添加请求路径 path
        return wrapper
    return decorator
# 这样，一个函数通过@get(path)的装饰就附带了URL信息

# 同get(path)
def post(path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator


# 关于inspect.Parameter 的  kind 类型有5种：
# POSITIONAL_ONLY		只是位置参数
# POSITIONAL_OR_KEYWORD	可以是位置参数也可以是关键字参数
# VAR_POSITIONAL		相当于 *args
# KEYWORD_ONLY			相当于 *,key
# VAR_KEYWORD			相当于 **kw
# 具体可参考：http://blog.csdn.net/weixin_35955795/article/details/53053762
# 函数的参数fn本身就是个函数，下面五个函数是针对fn函数的参数做一些处理判断


# 这个函数将得到fn函数中的没有默认值的KEYWORD_ONLY的元组
def get_required_kw_args(fn):
    args = [] # 定义一个空的list，用来储存符合条件的fn的参数名
    params = inspect.signature(fn).parameters # 返回一个关于函数参数的键值字典（映射mapping）
    for name, param in params.items():
        # 参数类型为KEYWORD_ONLY且没有指定默认值，inspect.Parameter.empty表示参数的默认值为空
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name) # 只是将参数名添加进去
    return tuple(args)

#和上一个函数基本一样，唯一的区别就是不需要满足没有默认值这个条件，也就是说这个函数把fn的所有的KEYWORD_ONLY参数名都提取出来
def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

#判断fn有没有KEYWORD_ONLY
def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

#判断fn有没有**kw（变长关键字参数）
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True


# 判断是否存在一个参数叫做request，并且该参数要在其他普通的位置参数之后，
# 即fn(POSITIONAL_ONLY, request, VAR_POSITIONAL, KEYWORD_ONLY, VAR_KEYWORD)
# 当然，这里request可以为VAR_POSITIONAL, KEYWORD_ONLY, VAR_KEYWORD中的一种
def has_request_arg(fn):
    sig = inspect.signature(fn) # 这边之所以拆成两行，是因为后面raise语句要用到sig
    params = sig.parameters
    found = False # 默认没有找到
    for name, param in params.items():
        if name == 'request':
            found = True
            continue # 为什么不是break？因为还得接着往下检查其他参数，确保request为最后一个位置参数
                     # 或者是VAR_POSITIONAL, KEYWORD_ONLY, VAR_KEYWORD中的一种
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL
                      and param.kind != inspect.Parameter.KEYWORD_ONLY
                      and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s'
                             % (fn.__name__, str(sig)))
    return found


# RequestHandler目的就是从URL函数中分析其需要接收的参数
# 进而从request中获取必要的参数构造成字典以**kw传给该URL函数并调用

class RequestHandler(object):
    # 初始化自身的属性，从fn中获取必要的参数信息
    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

    # 定义了__call__方法后这个类的实例就相当于一个函数可以直接调用了
    # 为什么要这么做呢？因为后面app.router.add_route()中需要传入一个回调函数
    # 而这个回调函数我们本来可以直接把handlers里的函数传进来
    # 但为了方便开发（构造框架），我们对该函数进行了一系列的封装处理
    # 这样也使得框架使用者尽管往handlers里添加实现业务逻辑的函数（handler）就行了，不必修改其他的模块，实现了透明化

    # __call__方法的代码逻辑:
    # 1.定义kw对象，用于保存参数
    # 2.判断request对象是否存在符合条件的参数，如果存在则根据是POST还是GET方法将参数内容保存到kw
    # 3.如果kw为空(说明request没有传递参数)，则将match_info列表里面的资源映射表（在装饰器参数里的url路径有表示）赋值给kw；
    #   如果不为空则把命名关键字参数的内容给kw
    # 4.完善_has_request_arg和_required_kw_args属性

    # app.router.add_route()调用回调函数时会往该函数传递request参数
    async def __call__(self, request):
        kw = None
        # 如果fn有（**kw）或者（KEYWORD_ONLY）
        # 这说明fn需要传参，这些参数的值来自于request提交的数据
        # 这里不考虑POSITIONAL_OR_KEYWORD和VAR_POSITIONAL，
        # 因为用不到VAR_POSITIONAL，而且要求handlers中的url函数参数除了match_info和request其他的参数必须为KEYWORD_ONLY
        if self._has_var_kw_arg or self._has_named_kw_args:
            # POST/GET方法下解析request提交的数据类型并提取
            # method为post的处理
            if request.method == 'POST':
                # POST提交请求的类型通过content_type获取，可参考：http://www.cnblogs.com/aaronjs/p/4165049.html
                if not request.content_type:# 判断是否存在Content-Type，不存在则无法根据数据类型获取解析提交的数据
                    return web.HTTPBadRequest('Missing Content-Type!')
                ct = request.content_type.lower() #统一小写，方便检测
                if ct.startswith('application/json'): # 这里用的是startswith而不是直接比较，因为后面可能还会有charset=utf-8，但我们并不关心
                    params = await request.json()  # 如果是json数据格式就用json()来读取json信息
                    if not isinstance(params, dict):# 序列化后应该为dict，否则说明提交的json数据格式本身是有错误的
                        return web.HTTPBadRequest('JSON body must be object!')
                    kw = params  # 正确的话把request的参数信息给kw（已经序列化成一个字典了）
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'): # 传统的浏览器提交表单格式
                    params = await request.post()  # 浏览器表单信息用post方法来读取
                    kw = dict(**params)  # 将表单信息转换成字典给kw
                else:#提交的数据类型既不是json对象，又不是浏览器表单，那就只能返回不支持该消息主体类型，其实就是不支持xml
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
            # method为get的处理
            if request.method == 'GET':  # get方法比较简单，直接在url后面加上查询参数来请求服务器上的资源
                # request.query_string表示url中的查询字符串
                # 比如我百度ReedSun，得到网址为https://www.baidu.com/s?ie=UTF-8&wd=ReedSun
                # 其中‘ie=UTF-8&wd=ReedSun’就是查询字符串
                qs = request.query_string
                if qs: # 如果存在查询字符串
                    kw = dict()
                    # parse.parse_qs(qs, keep_blank_values=False, strict_parsing=False)函数的作用是解析一个给定的字符串
                    # keep_blank_values默认为False，指示是否忽略空白值，True不忽略，False忽略
                    # strict_parsing如果是True，遇到错误是会抛出ValueError错误，如果是False会忽略错误
                    # 这个函数将返回一个字典，其中key是等号之前的字符串，value是等号之后的字符串但会是列表
                    # 比如上面的例子就会返回{'ie': ['UTF-8'], 'wd': ['ReedSun']}
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        # 经过以上处理参数仍为空说明没有从Request中获取到数据或者fn没有符合的参数类型
        # 则将match_info列表里面的资源映射表（在装饰器参数里的url路径有表示）赋值给kw
        if kw is None:
            # Resource may have variable path also. For instance, a resource
            # with the path '/a/{name}/c' would match all incoming requests
            # with paths such as '/a/b/c', '/a/1/c', and '/a/etc/c'.
            # A variable part is specified in the form {identifier}, where the
            # identifier can be used later in a request handler to access the
            # matched value for that part. This is done by looking up the
            # identifier in the Request.match_info mapping:
            kw = dict(**request.match_info)
        # kw不为空时，则进一步处理kw
        else:
            # 当fn没有**kw且有KEYWORD_ONLY时，kw中只留下KEYWORD_ONLY的参数，其他的都删除，否则传参过多
            if (not self._has_var_kw_arg) and self._has_named_kw_args:
                copy = dict()
                for name in self._named_kw_args:# 遍历fn中每一个KEYWORD_ONLY参数
                    if name in kw:#如果该参数在kw中也有则复制到copy中
                        copy[name] = kw[name]
                kw = copy#将筛选出来的KEYWORD_ONLY参数覆盖掉原来的kw，这样kw中只留下KEYWORD_ONLY参数
            # 再将match_info中的数据放入kw，同时检查是否与kw中的数据命名重复，这里优先选择match_info
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in kw args (choose match_info\'s): %s' % k)
                kw[k] = v
        # 别漏了request，如果有request这个参数，则把request加入
        # 注意，这里说明fn不需要request时我们是可以不传的
        # 而如果没有这个框架则url函数必须要有request参数
        # 因为app.router.add_route()会强行传递request给它，再次看出框架的屏蔽性与透明化
        if self._has_request_arg:
            kw['request'] = request
        # 没有默认值的KEYWORD_ONLY参数必须要有值传给它，否则会报错
        if self._required_kw_args:
            for name in self._required_kw_args:
                if name not in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw)) # 打印出最终传递给fn的参数
        try:
            return (await self._func(**kw))
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)


# 向app中添加静态文件路径
def add_static(app):
    # os.path.abspath(__file__), 返回当前脚本的绝对路径(包括文件名)
    # os.path.dirname(), 去掉文件名,返回目录路径
    # os.path.join(), 将分离的各部分组合成一个路径名
    # 因此以下操作就是将本文件同目录下的static目录加入到app的路由管理器中
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/',path)
    logging.info('add static %s => %s' % ('/static/', path))

# 注册URL处理函数
def add_route(app, fn):
    # 获取'__method__'和'__route__'属性，如果为空则抛出异常
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    # 判断fn是不是协程(即@asyncio.coroutine修饰的)并且判断是不是一个生成器(generator function)
    if not asyncio.iscoroutine(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)# 都不是的话，转换为协程
    logging.info('add route : method = %s, path = %s, fn = %s (%s)' % (
        method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    # 注册为相应的url处理方法(回调函数)，回调函数为RequestHandler的自省函数 '__call__'
    app.router.add_route(method, path, RequestHandler(app, fn))


def add_routes(app, module_name):
    # 自动搜索传入的module_name的module的url处理函数
    # 检查传入的module_name是否有'.'
    # Python rfind() 返回字符串最后一个'.'出现的索引位置（从右边开始寻找），如果没有匹配项则返回-1
    n = module_name.rfind('.')
    # 没有'.',说明模块在当前目录下，直接导入
    if n == (-1):
        # __import__的作用类似import，import是为当前模块导入另一个模块，而__import__则是返回一个对象
        # __import__(name, globals=None, locals=None, fromlist=(), level=0)
        # name -- 模块名
        # globals, locals -- determine how to interpret the name in package context
        # fromlist -- name表示的模块的子模块或对象名列表
        # level -- 绝对导入还是相对导入,默认值为0, 即使用绝对导入,正数值表示相对导入时,导入目录的父目录的层数
        mod = __import__(module_name, globals(), locals())
        logging.info('globals = %s', globals()['__name__'])
    else:
        name = module_name[n+1:] # 取得子模块名
        # 以下语句表示, 先用__import__表达式导入模块以及子模块
        # 再通过getattr()方法取得子模块, 如handlers.handler
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):# 遍历mod的方法和属性
        if attr.startswith('_'):# 如果是以'_'开头的，一律pass，我们定义的处理方法不是以'_'开头的
            continue
        fn = getattr(mod, attr)# 获取到非'_'开头的属性或方法
        if callable(fn):# 能调用的说明是方法
            # 检测'__method__'和'__route__'属性
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:# 如果都有，说明是我们定义的url处理方法，注册到app的route中
                add_route(app, fn)
