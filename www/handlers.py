#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
url handlers, 实现MVC
该模块主要是url的处理函数，模板的渲染在app.py中
"""
__author__ = 'Hk4Fun'

import re, time, json, logging, hashlib, base64, asyncio

from webframe import get, post

from models import User, Comment, Blog, next_id

from apis import APIResourceNotFoundError, APIValueError, APIError, APIPermissionError, Page


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

@get('/greeting')
async def handler_url_greeting(*,name,request):
    body='<h1>Awesome: /greeting %s</h1>'%name
    return body

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
