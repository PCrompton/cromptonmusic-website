#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import webapp2
import os
import jinja2
import re
import time
import logging

from datetime import datetime, timedelta

from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.api import users


template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
								autoescape = True)

menu = """
    <li><a href='/'>Home</a></li>
    <li><a href='/about'>About</a></li>
    <li><a href='/lessons'>Lessons</a></li>
    <li><a href='/blog'>Blog</a></li>
    <li><a href='/contact'>Contact</a></li>
"""

menu = ["home", "about", "lessons", "contact"]

editMenu = """
    <li><a href='/edit'>Home</a></li>
    <li><a href='/about/edit'>About</a></li>
    <li><a href='/lessons/edit'>Lessons</a></li>
    <li><a href='/blog/edit'>Blog</a></li>
    <li><a href='/contact/edit'>Contact</a></li>
"""

links = """
    <li><a href='http://lyricora.org'>Lyricora</a></li>
    <li><a href='http://rositalee.com'>Rosita Lee Music Center</a></li>
    <li><a href='http://rising-stars-productions.com'>Rising Stars Productions</a></li>
    <li><a href='http://mmmusing.blogspot.com'>MMmusing</a></li>
"""


def add_page(page):
    page.put()
    time.sleep(.1)
    get_pages(update = True)


def get_pages(update = False):
    mc_key = 'pages'
    pages = memcache.get(mc_key)
    if pages is None or update:
        #print "DB QUERY"
        logging.error("DB QUERY")
        pages = db.GqlQuery("SELECT * from Pages ORDER BY created DESC")
        pages = list(pages)
        memcache.set(mc_key, pages)
    return pages


class Pages(db.Model):
    path = db.StringProperty()
    title = db.StringProperty()
    content = db.TextProperty(required = True)
    author = db.StringProperty()
    created = db.DateTimeProperty(auto_now_add = True)
    last_modified = db.DateTimeProperty(auto_now = True)

    @staticmethod
    def parent_key(path):
        return db.Key.from_path(path, 'pages')

    @classmethod
    def by_path(cls, path):
        pages = get_pages()
        for page in pages:
            if page.path == path:
                return page
        return None


class MasterHandler(webapp2.RequestHandler):

    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)
		
    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def get_title(self, path):
        #print "PATH: ", path
        if path == None or path == "/":
            title = "Home"
        else:
            a = 1
            title = path[1:].title()
        return title

    def validate_path(self, path):
        if path == None:
            path = "/"
        return path

    def get_page(self, path):
        path = self.validate_path(path)
        page = Pages.by_path(path)
        print "PAGE: ", page
        if page:
            return page
        else:
            title = self.get_title(path)
            content = title + " Content"
            page = Pages(title = title, content = content, path = path)
        return page


class Page(MasterHandler):
    def get(self, path):

        if ((len(path) > 1) \
            and path[1:] not in menu) \
            or (path[1:] == "home"):

            self.render("content.html", title="ERROR: 404", content=path+": page not found", menu=menu, links=links, path=path)
        else:
            page = self.get_page(path)
            self.render("content.html", title=page.title, content=page.content, menu=menu, links=links, path=path)


class Edit(MasterHandler):
    def get(self, path):
        user = users.get_current_user()
        page = self.get_page(path)
        #print "PATH: ", path;
        if path == None:
            path = "/"

        if ((len(path) > 1) \
            and path[1:] not in menu) \
            or (path[1:] == "home"):

            self.redirect(path)
 
        if user:
            if users.is_current_user_admin():
                greeting = ('Welcome, %s! (<a href="%s">sign out</a>)' %
                        (user.nickname(), users.create_logout_url('/')))
                self.render("edit.html", title=page.title, content=page.content, menu=menu, links=links, path=path, greeting=greeting)
            else:
                page.title = "Error: Forbidden!"
                greeting = ('You must have admin permissions to edit this page. (<a href="%s">sign out</a>)' %
                    (users.create_logout_url('/')))
                self.render("content.html", title="Error: Forbidden!", content=greeting, menu=menu, links=links, path=path)
        else:
            greeting = ('<a href="%s">Sign in or register</a>.' %
                        users.create_login_url('/'))

            self.render("content.html", title="Please login as admin", content=greeting, menu=menu, links=links, path=path)
        

    def post(self, path):
        path = self.validate_path(path)
        title = self.request.get('title')
        content = self.request.get('content')
        page = Pages(parent = Pages.parent_key(path), title = title, content = content, path = path)
        add_page(page)
        self.redirect(path)


PAGE_RE = r'(/(?:[a-zA-Z0-9_-]+/?)*)'
EDIT_PAGE = PAGE_RE + r'?' + r'/edit'
app = webapp2.WSGIApplication([
    (EDIT_PAGE, Edit),
    (PAGE_RE, Page)
], debug=True)
