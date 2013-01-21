#!/usr/bin/env python
import pickle

from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.ext.db import StringProperty, Model, FloatProperty, IntegerProperty

import fw.core

def one(q):
	f = q.fetch(2)
	if f:
		return f[0]
	else:
		return None

def find(model, *filters):
	q = model.all()
	for filter in filters:
		q = q.filter(*filter)
	return q

def find_one(model, *filters):
	return one(find(model, *filters))

def transaction(method):
	def wrapper(*args, **kwargs):
		return db.run_in_transaction(lambda: method(*args, **kwargs))
	wrapper.__name__ = method.__name__
	return wrapper

class ObjectProperty(db.Property):
	data_type = object
		
	def __init__(self, default=None):
		self.defaultval = default
		db.Property.__init__(self)
		
	def get_value_for_datastore(self, model_instance):
		return db.Blob(
			pickle.dumps(db.Property.get_value_for_datastore(self, model_instance), protocol=2)
		)

	def make_value_from_datastore(self, value):
		val = pickle.loads(value)
		if self.defaultval is not None and val is None:
			val = self.defaultval
		return val
	
	def validate(self, value):
		#if not isinstance(value, (basestring, dict, int, long, float, list, tuple, type(None))):
		#	raise db.BadValueError("%r" % type(value))
		return value

class MemCache(object):
	def __init__(self, name):
		self.ns = name
	
	def __getitem__(self, key):
		val = memcache.get(key, namespace=self.ns)
		if val == None:
			raise KeyError(key)
		return val
	
	def __setitem__(self, key, val):
		if isinstance(val, str) and len(val) > 10000:
			return
		memcache.set(key, val, namespace=self.ns)
	
	def __delitem__(self, key):
		memcache.delete(key, namespace=self.ns)
	
	def get(self, name, default=None):
		try:
			return self[name]
		except KeyError:
			return default


NO_DEFAULT = object()

dbdicts = {}

class DBDict(object):
	def __init__(self, name, default=NO_DEFAULT):
		full_name = str('dict_' + name)
		self.model = type(full_name, (DBDictModel,), {})
		self.default = default
		self.memcache = None #MemCache(full_name)
		dbdicts[name] = self
	
	def __getitem__(self, key):
		try:
			return (self.memcache or {})[key]
		except KeyError:
			entry = find_one(self.model, ('key_ =', key))
			if not entry:
				if self.default is NO_DEFAULT:
					raise KeyError(key)
				else:
					val = self.default()
					self.memcache[key] = val
					self[key] = val
					return val
			if self.memcache:
				self.memcache[key] = entry.val
			return entry.val
	
	def get(self, name, default=None):
		try:
			return self[name]
		except KeyError:
			return default
	
	def __setitem__(self, key, val):
		if self.memcache:
			self.memcache[key] = val
		entry = find_one(self.model, ('key_ =', key))
		if not entry:
			entry = self.model(key_=key)
		entry.val = val
		entry.put()
	
	def __delitem__(self, key):
		if self.memcache:
			del self.memcache[key]
		entry = find_one(self.model, ('key_ =', key))
		if entry:
			entry.delete()
		else:
			raise KeyError(key)
	
	def items(self):
		for entry in self.model.all():
			yield (entry.key_, entry.val)
	
	def entry(self, key):
		entry = find_one(self.model, ('key_ =', key))
		if not entry:
			entry = self.model(key_=key)
		class Entry(object):
			def set(s, val):
				self.memcache[key] = val
				entry.val = val
			def get(s):
				return entry.val
		return Entry()

class DBDictModel(db.Model):
	key_ = db.StringProperty()
	val = ObjectProperty()

class DBSet(object):
	def __init__(self, name):
		full_name = 'set_' + name
		self.model = type(full_name, (DBSetModel, ), {})
		self.memcache = MemCache(full_name)
	
	def add(self, val):
		entry = self.model(val=val)
		entry.put()
		id = entry.key().id()
		self.memcache[id] = val
		return id
	
	def __setitem__(self, id, val):
		entry = self.model.get_by_id(id)
		if not entry:
			raise KeyError(id)
		self.memcache[id] = val
		entry.val = val
		entry.put()
	
	def __getitem__(self, id):
		try:
			return self.memcache[id]
		except KeyError:
			entry = self.model.get_by_id(id)
			if not entry:
				raise KeyError(id)
			return entry.val

class DBSetModel(db.Model):
	val = ObjectProperty()
