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


@get('/')
async def index(request):
    users = await User.findAll()
    return {
        '__template__': 'test.html',
        'users': users
    }

@get('/greeting')
async def handler_url_greeting(*,name,request):
    body='<h1>Awesome: /greeting %s</h1>'%name
    return body

