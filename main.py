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
import email.utils
import logging
import datetime


from xml.dom import minidom

#from datetime import datetime, timedelta

from google.appengine.api import urlfetch
from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.api import users


template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
								autoescape = True)


menu = ["home", "about", "lessons", "blog", "contact"]


def add_page(page):
    page.put()
    time.sleep(.1)
    get_pages(update = True)


def add_link(link):
    link.put()
    time.sleep(.1)
    get_links(update = True)

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

def get_links(update = False):
    mc_key = 'links'
    links = memcache.get(mc_key)
    if links is None or update:
        logging.error("DB QUERY")
        links = db.GqlQuery("SELECT * from Links ORDER BY position ASC")
        links = list(links)
        memcache.set(mc_key, links)
    return links

def parsePubDate(pubDate):
    print "PUBDATE", type(pubDate)
    d = email.utils.parsedate(pubDate)
    ts = time.mktime(d)
    return datetime.datetime.fromtimestamp(ts)

class Post(db.Model):
    pubDate = db.DateTimeProperty()
    title = db.StringProperty()
    content = db.TextProperty()
    author = db.StringProperty()

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

class Links(db.Model):
    position = db.IntegerProperty()
    name = db.StringProperty()
    url = db.StringProperty(required=True)
    created = db.DateTimeProperty(auto_now_add = True)
    last_modified = db.DateTimeProperty(auto_now = True)


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
            links = get_links(path)
            if path == "/blog":
                url = "http://cromptonmusic.blogspot.com/feeds/posts/default?alt=rss"
                result = urlfetch.fetch(url).content
                xml = minidom.parseString(result)
                items = xml.getElementsByTagName("item")
                posts = []
                for item in items:
                    pubDate = parsePubDate(item.getElementsByTagName("pubDate")[0].firstChild.nodeValue)
                    title = item.getElementsByTagName("title")[0].firstChild.nodeValue
                    content = item.getElementsByTagName("description")[0].firstChild.nodeValue
                    author = item.getElementsByTagName("author")[0].firstChild.nodeValue

                    author = author[author.find('(')+1:author.find(')')]

                    
                    post = Post(pubDate = pubDate, title = title, content = content, author = author)
                    print post.content
                    posts.append(post)

                self.render("blog.html", menu=menu, links=links, path=path, xml=xml, posts=posts)
            else:
                page = self.get_page(path)
            
                self.render("content.html", title=page.title, content=page.content, menu=menu, links=links, path=path)

class Edit_Links(MasterHandler):
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
 
        links = get_links(path)
        if user:
            if users.is_current_user_admin():
                greeting = ('Welcome, %s! (<a href="%s">sign out</a>)' %
                        (user.nickname(), users.create_logout_url('/')))
                self.render("edit_links.html", title=page.title, content=page.content, menu=menu, links=links, path=path, greeting=greeting)
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
        position = self.request.get('position')
        name = self.request.get('name')
        url = self.request.get('url')
        uInput = self.request.get('uInput')
        print "\n USER INPUT: ", uInput, "\n"
        if uInput == "Save":
            link = Links(name = name, url = url, path = path, position = int(position))
            add_link(link)
        elif uInput == "Delete":
            q = ("SELECT * FROM Links WHERE name='%s' AND url='%s'" %(name, url))
            result = db.GqlQuery(q).get()
            db.delete(result)
            time.sleep(.1)
            get_links(True)
        self.redirect(path)


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
 
        links = get_links(path)
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
EDIT_LINKS = EDIT_PAGE + '/links'
app = webapp2.WSGIApplication([
    (EDIT_LINKS, Edit_Links),
    (EDIT_PAGE, Edit),
    (PAGE_RE, Page)
], debug=True)


