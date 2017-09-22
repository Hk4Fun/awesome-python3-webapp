#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
url handlers, 实现MVC
该模块主要是url的处理函数，模板的渲染在app.py中
"""
__author__ = 'Hk4Fun'

import re, time, json, logging, hashlib, base64, asyncio

from aiohttp import web

from config import configs

from webframe import get, post

from models import User, Comment, Blog, next_id

from apis import APIResourceNotFoundError, APIValueError, APIError, APIPermissionError, Page


COOKIE_NAME = 'awesession'             # cookie名,用于设置cookie
_COOKIE_KEY = configs.session.secret   # cookie密钥,作为加密cookie的原始字符串的一部分
_RE_EMAIL = re.compile(r'^[\w\-]+\@[\w\-]+(\.[\w\-]+){1,4}$') # email的匹配正则表达式
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$') # 密码的匹配正则表达式

# 取得页码
def get_page_index(page_str):
    # 将传入的字符串转为页码信息, 实际只是对传入的字符串做了合法性检查（容错处理）
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p

# 通过用户信息计算cookie并加密
def user2cookie(user, max_age):
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age)) # expires(失效时间)是当前时间加上cookie最大存活时间的字符串
    # 利用用户id,加密后的密码,失效时间,加上cookie密钥,组合成待加密的原始字符串
    s = "%s-%s-%s-%s" % (user.id, user.passwd, expires, _COOKIE_KEY)
    # 将用户id，失效时间，加密字符串共同组成cookie
    return "-".join([user.id, expires, hashlib.sha1(s.encode("utf-8")).hexdigest()])

# 解密cookie
async def cookie2user(cookie_str):
    '''Parse cookie and load user if cookie is valid'''
    # cookie_str就是user2cookie函数的返回值，逆向还原user信息
    if not cookie_str:
        logging.info("invalid cookie!")
        return None
    try:
        # 解密是加密的逆向过程,因此,先通过'-'拆分cookie,得到用户id,失效时间,以及加密字符串
        L = cookie_str.split("-") # 返回一个str的list
        if len(L) != 3: # 由上可知,cookie由3部分组成,若拆分得到不是3部分,显然出错了
            logging.info("invalid cookie!")
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time(): # 时间是浮点表示的时间戳,一直在增大.因此失效时间小于当前时间,说明cookie已失效
            logging.info("invalid cookie : invalid expires!")
            return None
        user = await User.find(uid)  # 在拆分得到的id在数据库中查找用户信息
        if user is None:  # 没查到该uid的用户
            logging.info("invalid cookie : invalid uid!")
            return None
        # 利用用户id,加密后的密码,失效时间,加上cookie密钥,组合成待加密的原始字符串
        # 再对其进行加密,与从cookie分解得到的sha1进行比较.若相等,则该cookie合法
        s = "%s-%s-%s-%s" % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode("utf-8")).hexdigest():
            logging.info("invalid cookie : invalid sha1!")
            return None
        user.passwd = "*****"
        return user
    except Exception as e:
        logging.exception(e)
    return None

@get('/')
def index(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time()-3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time()-7200)
    ]
    return {
        '__template__': 'blogs.html',
        'blogs': blogs
    }

# API: 获取用户信息
@get('/api/users')
async def api_get_users(*, page="1"):
    page_index = get_page_index(page)
    num = await User.findNumber("count(id)")#获取用户数量
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = await User.findAll(orderBy="created_at desc")
    for u in users:
        u.passwd = "*****" # 将密码覆盖掉
    # 以dict形式返回,并且未指定__template__,将被app.py的response factory处理为json
    return dict(page=p, users=users)


# 返回注册页面
@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }

# 返回登陆页面
@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }

# 注册请求
@post('/api/users')
async def api_register_user(*, email, name, passwd):
    # 判断name是否存在，且是否只是'\n', '\r',  '\t',  ' '，这种特殊字符
    if not name or not name.strip():
        raise APIValueError('name')
    # 判断email是否存在，且是否符合规定的正则表达式
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    # 判断passwd是否存在，且是否符合规定的正则表达式
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')

    # 查一下库里是否有相同的email地址，如果有的话提示用户email已经被注册过
    users = await User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')

    # 利用当前时间与随机生成的uuid生成唯一的user id
    uid = next_id()
    # 构建shal_passwd，将uid与密码组合
    sha1_passwd = '%s:%s' % (uid, passwd)
    # 创建用户对象, 其中密码并不是用户输入的密码,而是经过复杂处理后的保密字符串
    # unicode对象在进行哈希运算之前必须先编码
    # sha1(secure hash algorithm),是一种不可逆的安全算法.这在一定程度上保证了安全性,因为用户密码只有用户一个人知道
    # hexdigest()函数将hash对象转换成16进制表示的字符串
    # Gravatar(Globally Recognized Avatar)是一项用于提供在全球范围内使用的头像服务。
    # 只要在Gravatar的服务器上上传了你自己的头像，便可以在其他任何支持Gravatar的博客、论坛等地方使用它。
    # 此处image就是一个根据用户email生成的头像
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),image='about:blank')
                # image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest()
    await user.save()# 保存这个用户到数据库用户表
    logging.info('save user OK')

    # 构建返回信息
    r = web.Response()
    # 添加cookie，user2cookie设置的是cookie的值
    # max_age是cookie的最大存活周期,单位是秒.当时间结束时,客户端将抛弃该cookie，之后需要重新登录
    # httponly=True用来防止XSS攻击，保护cookie
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    # 只把要返回的密码改成'******'，库里的密码依然是正确的，以保证真实的密码不会因返回而泄露
    user.passwd = '******'
    # 返回的是json数据，所以设置content-type为json的
    r.content_type = 'application/json'
    # 把user信息转换成json格式返回
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

# 登陆认证
@post('/api/authenticate')
async def authenticate(*, email, passwd):# 通过邮箱与密码验证登录
    # 如果email或passwd为空则报错
    if not email:
        raise APIValueError('email', 'Invalid email')
    if not passwd:
        raise APIValueError('passwd', 'Invalid  passwd')
    # 根据email在库里查找匹配的用户
    users = await User.findAll('email=?', [email])
    # 没找到用户，返回用户不存在
    if len(users) == 0:
        raise APIValueError('email', 'email not exist')
    # 取得用户记录.事实上,就只有一条用户记录,只不过返回的是list
    user = users[0]
    # 验证密码
    # 数据库中存储的并非原始的用户密码,而是加密的字符串
    # 我们对此时用户输入的密码做相同的加密操作,将结果与数据库中储存的密码比较,来验证密码的正确性
    # 以下步骤合成为一步就是:sha1 = hashlib.sha1((user.id+":"+passwd).encode("utf-8"))
    # 对照用户时对原始密码的操作(见api_register_user),操作完全一样
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    # 和库里的密码字段的值作比较，一样的话认证成功，不一样的话，认证失败
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', 'Invalid passwd')
    # 构建返回信息
    r = web.Response()
    # 用户登录之后,同样的设置一个cookie,以下的代码与注册用户部分的代码完全一样
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

# 用户登出
@get("/signout")
def signout(request):
    # 请求头部的referer,表示从哪里链接到当前页面,即上一个页面
    # 用户登出时,实际转到了/signout路径下,因此为了使登出毫无违和感,跳回上一个转过来的页面
    referer = request.headers.get("Referer")
    # 若无前一个网址,可能是用户新打开了一个标签页,则登录后转到首页
    r = web.HTTPFound(referer or '/')
    # 设置cookie的最大存活时间为0来删除cookie，这里的“-deleted-”只是提示，关键在与max_age=0
    r.set_cookie(COOKIE_NAME, "-deleted-", max_age=0, httponly=True)
    logging.info("user signed out.")
    return r

