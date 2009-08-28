#!/usr/bin/env python

import os
import pager
import logging
import wsgiref.handlers

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

iso_codes_to_language_name = {}
iso_codes = open(os.path.join(os.path.dirname(__file__) + '/templates', 'iso_codes.txt'), 'r')
language_select_form_element = ""

for line in iso_codes:
	row = line.split('|')
	iso_codes_to_language_name[row[0]] = row[3]

iso_codes.close()

#
# Model
#

class Localization(db.Model):	
	user_id = db.StringProperty(required=True)
	created = db.DateTimeProperty(required=True, auto_now_add=True)
	modified = db.DateTimeProperty(required=True, auto_now=True)
	name = db.StringProperty(required=True)
	searchable_name = db.StringProperty(required=True)
	bundle_id = db.StringProperty(required=True)
	bundle_version = db.StringProperty(required=True)
	iso_language_code = db.StringProperty(required=True)
	application_link = db.LinkProperty(required=True)
	localization_link = db.LinkProperty(required=True)
	user_link = db.LinkProperty()

	def language(self):
		return iso_codes_to_language_name[self.iso_language_code]
	
	def user_html(self):
		user = users.User(self.user_id)
		if self.user_link:
			return '<a href="%s">%s</a>' % (self.user_link, user.nickname())
		else:
			return user.nickname()
	
	def localization_link(self):
		return "/%d" % self.key().id()

#
# Util
#

def is_development_server():
	return os.environ['SERVER_SOFTWARE'].startswith('Dev')

def user_id_for_user(user):
	if is_development_server():
		return user.email()
	else:
		return user.user_id() # inconsistent on dev server

def stop_processing(*a, **kw):
	pass

def require_user(f):	
	def g(*a, **kw):
		handler = a[0]

		if is_development_server():
			user = users.User("test@example.com")
		else:
			user = users.get_current_user()

		if user == None:
			#handler.error(401)
			handler.redirect(users.create_login_url(handler.request.url))	    
			return stop_processing
		new_args = (handler, user) + a[1:]
		return f(*new_args, **kw)
	return g

def require_localization(f):	
	def g(*a, **kw):
		handler = a[0]
		localization_id = a[1]

		try:
			localization = Localization.get_by_id(int(localization_id))
		except db.BadKeyError:
			localization = None

		if localization == None:
			handler.error(404)
			return stop_processing 
		
		new_args = (handler, localization) + a[2:]
		return f(*new_args, **kw)
	return g

def render(file, template_values={}):
	path = os.path.join(os.path.dirname(__file__) + '/templates', file)
	if (os.path.exists(path)):
		return template.render(path, template_values)
	else:
		return False

#
# Handlers
#

class LocalizationsHandler(webapp.RequestHandler):
	def get(self):
		bookmark = self.request.get('bookmark', None)
		format = self.request.get('format', None)
		q = self.request.get('q', "").lower()

		if q:
			pager_query = pager.PagerQuery(Localization).filter('searchable_name >=', q).filter('searchable_name <', q + u"\ufffd").order('searchable_name').order('modified')
		else:
			pager_query = pager.PagerQuery(Localization).order('modified')

		prev, results, next = pager_query.fetch(20, bookmark)
		
		if format == 'rss':
			self.response.out.write(render("feed.rss", { 'q' : q, 'prev' : prev, 'results' : results, 'next' : next }))
		else:
			self.response.out.write(render("index.html", { 'q' : q, 'prev' : prev, 'results' : results, 'next' : next }))

	@require_user
	def post(self, user):
		name = self.request.get('name', None)
		bundle_id = self.request.get('bundle_id', None)
		bundle_version = self.request.get('bundle_version', None)
		iso_language_code = self.request.get('iso_language_code', None)
		application_link = self.request.get('application_link', None)
		localization_link = self.request.get('localization_link', None)
		user_link = self.request.get('user_link', None)
		
		localization = Localization(user_id=user_id_for_user(user), name=name, searchable_name=name.lower(), bundle_id=bundle_id, bundle_version=bundle_version, iso_language_code=iso_language_code, application_link=application_link, localization_link=localization_link, user_link=user_link)
		localization.put()
		
		self.redirect(localization.localization_link())

class LocalizationHandler(webapp.RequestHandler):
	@require_localization
	def get(self, localization):
		self.response.out.write(render("view.html", { 'localization' : localization }))

	@require_user
	def post(self, user):
		pass

	@require_localization
	@require_user
	def put(self, user, localization):
		pass

	@require_localization
	@require_user
	def delete(self, user, localization):
		pass

class LocalizationNewHandler(webapp.RequestHandler):
	@require_user
	def get(self, user):
		self.response.out.write(render("new.html", { }))

class LocalizationEditHandler(webapp.RequestHandler):
	@require_localization
	@require_user
	def get(self, user, localization):
		self.response.out.write(render("edit.html", { }))

class AboutHandler(webapp.RequestHandler):
	def get(self):
		self.response.out.write(render("about.html", { }))

def main():
	application = webapp.WSGIApplication([
		('/about/?', AboutHandler),
		('/', LocalizationsHandler),
		('/new/?', LocalizationNewHandler),
		('/(.+)/?', LocalizationHandler),
		('/(.+)/edit/?', LocalizationEditHandler),
	], debug=True)
	wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
	main()
