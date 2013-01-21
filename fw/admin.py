#!/usr/bin/env python

import logging
import cgi
import pprint

import fw.core
import fw.util
import fw.db

_ = fw.core.widget(name='admin.dbdict', public=True, admin=True)
class AdminDBDict(fw.core.Widget):
	view = 'fw/admin.fwml'
	
	ident = fw.core.Attr(default='')
	
	@fw.core.action()
	def set_collection(self, name):
		self.ident = name
	
	@fw.core.action()
	def delete(self, key):
		self.updated = True
		del fw.db.dbdicts[self.ident][key]
	
	@fw.core.action()
	def add(self, key, val):
		obj = eval(val)
		fw.db.dbdicts[self.ident][key] = obj
	
	def get_view_attrs(self):
		dicts = fw.db.dbdicts.keys()
		if self.ident:
			dbdict = fw.db.dbdicts[self.ident]
			return dict(name=self.ident, dicts=dicts, items=
						[ (k, self.proc_val(k, v)) for k, v in dbdict.items() ])
		else:
			return dict(name=None, items=[], dicts=dicts)
	
	def proc_val(self, k, v):
		if isinstance(v, str) and ('JFIF' in v[:16] or v.startswith('\x89PNG')):
			blob = self.get_val.get_blob_url(args=dict(key=k))
			return '<img src="%s" height=20%%>' % (blob, )
		else:
			return cgi.escape(pprint.pformat(v))
	
	@fw.core.blob()
	def get_val(self, key):
		return fw.db.dbdicts[self.ident][key]
_(AdminDBDict)
