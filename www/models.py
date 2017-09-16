#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
定义三张表：User、Blog、Comment
"""

___author__ = 'Hk4Fun'

import asyncio
import orm
import time
import uuid  # 用来生成唯一标识符
from orm import Model, StringField, BooleanField, FloatField, TextField


# 用当前时间戳与随机生成的uuid合成作为id
def next_id():
    # uuid4()以随机数的方式生成uuid,hex属性将uuid转为32位的16进制数，共50位
    return "%015d%s000" % (int(time.time() * 1000), uuid.uuid4().hex)


# ORM映射,将User映射到数据库users表
class User(Model):
    # __table__的值将在创建类时被映射为表名
    __table__ = "users"

    # 定义各属性的域,以及是否主键,将在创建类时被映射为数据库表的列
    # 此处default用于存储每个用于独有的id,next_id将在insert的时候被调用
    id = StringField(primary_key=True, default=next_id, ddl="varchar(50)")  # 唯一标识符，作为主键
    email = StringField(ddl="varchar(50)")  # 邮箱
    passwd = StringField(ddl="varchar(50)")  # 密码
    admin = BooleanField()  # 管理员身份，值为1表示该用户为管理员，值为0表示该用户不是管理员
    name = StringField(ddl="varchar(50)")  # 名字
    image = StringField(ddl="varchar(500)")  # 应该是头像吧
    created_at = FloatField(default=time.time)  # 此处default用于存储创建的时间,在insert的时候被调用


class Blog(Model):
    __table__ = "blogs"

    id = StringField(primary_key=True, default=next_id, ddl="varchar(50)")
    user_id = StringField(ddl="varchar(50)")  # 作者id
    user_name = StringField(ddl="varchar(50)")  # 作者名
    user_image = StringField(ddl="varchar(500)")  # 作者上传的图片
    name = StringField(ddl="varchar(50)")  # 文章名
    summary = StringField(ddl="varchar(200)")  # 文章概要
    content = TextField()  # 文章正文
    created_at = FloatField(default=time.time)  # 创建时间


class Comment(Model):
    __table__ = "comments"

    id = StringField(primary_key=True, default=next_id, ddl="varchar(50)")
    blog_id = StringField(ddl="varchar(50)")  # 博客id
    user_id = StringField(ddl="varchar(50)")  # 评论者id
    user_name = StringField(ddl="varchar(50)")  # 评论者名字
    user_image = StringField(ddl="varchar(500)")  # 评论者上传的图片
    content = TextField()  # 评论内容
    created_at = FloatField(default=time.time)


# if __name__ == "__main__":
#     # 测试
#     async def check(loop):
#         await orm.create_pool(loop=loop, host='localhost', port=3306, user='root', password='123a456s789q',
#                               db='awesome')
#         user = User(name='hk4fun', email='hk4fun@example.com', passwd='1234567890', image='about:blank')
#         await user.save()
#         await orm.destroy_pool()
#
#
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(check(loop))
#     loop.close()
