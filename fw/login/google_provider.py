import logging

import fw.login
import fw.core

from google.appengine.api import users

class GoogleProvider(fw.login.LoginProvider):
	@classmethod
	def login(cls, top, redirect_url):
		url = fw.login.login_do.get_action_url(top, dict(provider='google', url=redirect_url))
		top.redirect(users.create_login_url(url))
	
	@classmethod
	def verify_login(cls, top):
		user = users.get_current_user()
		if not user:
			raise fw.login.LoginError
		return 'google:' + user.user_id()
	
	@classmethod
	def logout(cls, top):
		url = fw.login.logout_do.get_action_url(top)
		top.redirect(users.create_logout_url(url))

fw.login.providers['google'] = GoogleProvider
