#!/usr/bin/env python
import logging

import fw.util
import fw.db

def create_or_get_session(widget):
	if '__sessid' in widget._data:
		fwsessid = widget._data['__sessid']
		del widget._data['__sessid']
	else:
		fwsessid = widget._req.cookies.get('fwsessid')
	if not fwsessid:
		fwsessid = fw.util.random_string()
		widget._set_cookie('fwsessid', fwsessid, weeks=2)
	widget._session = Session(fwsessid)
	widget.session = widget._session

sessions = fw.db.DBDict('sessions')

NO_DEFAULT = object()

class Session(object):
	def __init__(self, sessid):
		self.sessid = sessid
		self._storage = sessions.get(self.sessid, {})
		self._modified = False
	
	def put(self, key, val):
		self._storage[key] = val
		self._modified = True
	
	def get(self, key, default=None):
		return self._storage.get(key, default)
	
	def __getitem__(self, key):
		return self._storage[key]
	
	def __contains__(self, key):
		return key in self._storage

	def __setitem__(self, key, val):
		self._storage[key] = val
		self._modified = True

	def get_default(self, key, default):
		val = self.get(key)
		if not val:
			self.put(key, default)
			return default
		else:
			return val

	def get_or_random(self, key):
		val = self.get(key)
		if not val:
			default = fw.util.random_string()
			self.put(key, default)
			return default
		else:
			return val
	
	def _make_key(self, base):
		return 'sess_%s_%s' % (self.sessid, base)
	
	def _get_private(self):
		return self.get_or_random('private')
	
	def sign_url(self, name, params):
		sessid_param = '&__sessid=' + self.sessid
		return fw.util.sign_url(self._get_private(), name, params) + sessid_param
	
	def verify_url(self, name, params):
		return fw.util.verify_url(self._get_private(), name, params)
	
	def flush(self):
		if self._modified:
			sessions[self.sessid] = self._storage
			self._modified = False