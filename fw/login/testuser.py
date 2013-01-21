#!/usr/bin/env python
import logging

import fw.db
import fw.login
import fw.login.social
import fw.core
import fw.util

users = fw.db.DBDict('login.testuser.users')

class TestUserProvider(fw.login.LoginProvider):
	@classmethod
	def login(cls, top, redirect_url):
		#url = fw.login.login_do.get_action_url(top, dict(provider='google', url=redirect_url))
		#top.redirect(users.create_login_url(url))
		top.redirect('/')
	
	@classmethod
	def verify_login(cls, top):
		ident = top._session['testuser.ident']
		try:
			users[ident]
		except KeyError:
			raise fw.login.LoginError
		return 'testuser:' + ident
	
	@classmethod
	def logout(cls, top):
		url = fw.login.logout_do.get_action_url(top)
		top.redirect(url)
	
	@classmethod
	def get_user(cls, id):
		proto, userid = id.split(':', 1)
		return TestUser(users[userid])

class TestUser(object):
	def __init__(self, name):
		self.name = name
	
	def get_profile(self):
		return fw.login.social.Profile(name='Tester ' + self.name)
	
	def get_friends(self):
		return []

@fw.widgets.Gate.add('login.testuser')
def login(top, path, args):
	ident = path.strip('/')
	top._session['testuser.ident'] = ident
	fw.login.login_do(top, 'testuser', '/')

def add(name):
	ident = fw.util.random_string()
	users[ident] = name

fw.login.providers['testuser'] = TestUserProvider
