#!/usr/bin/env python
import fw.db
import fw.login
import fw.util

user_friends = fw.db.DBDict('login.social.friends')
user_profiles = fw.db.DBDict('login.social.profiles')

class User(object):
	def __init__(self, provider, userid):
		self.userid = userid
		self.provider = provider
		self._impl = None
	
	@property
	def impl(self):
		if not self._impl:
			try:
				self._impl = self.provider.get_user(self.userid)
			except AttributeError:
				self._impl = FakeUser()
		return self._impl
	
	@property
	def friends(self):
		try:
			return user_friends[self.userid]
		except KeyError:
			val = self.impl.get_friends()
			user_friends[self.userid] = val
			return val
	
	@property
	def name(self):
		return self.profile.name

	@property
	def profile(self):
		try:
			return user_profiles[self.userid]
		except KeyError:
			val = self.impl.get_profile()
			user_profiles[self.userid] = val
			return val

	def notify_friend(self, to, message):
		self.impl.notify_friend(to, message)

class Message(object):
	def __init__(self, text, link=None, image=None):
		self.link = link
		self.text = text
		self.image = image

class Profile(object):
	def __init__(self, name=None, city=None, gender=None, birth=None):
		self.name = name
		self.city = city
		self.gender = gender
		self.birth = birth

def get_user(id):
	provider_name, rest = id.split(':', 1)
	return User(fw.login.providers[provider_name], id)

class Friend(object):
	def __init__(self, owner, id, name, desc):
		self.owner = owner
		self.id = id
		self.name = name
		self.desc = desc
		self._is_using = None
	
	def __repr__(self):
		return 'Friend(%r, %r, %r)' % (self.id, self.name, self.desc)
	
	@property
	def is_using(self):
		if self._is_using is None:
			try:
				fw.login.users[self.id]
				self._is_using = True
			except KeyError:
				self._is_using = False
		return self._is_using

	def notify(self, message):
		get_user(self.owner).notify_friend(self.id, message)

class FakeUser(object):
	def get_profile(self):
		return Profile()
	
	def get_friends(self):
		return []
