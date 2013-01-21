#!/usr/bin/env ython
import logging
import json
import urllib

import fw.core
import fw.util
import fw.db

import date

user_messages = fw.db.DBDict('messages')

class Message(object):
	def __init__(self, sender, content):
		self.sender = sender
		self.content = content
		self.link = None
		self.id = fw.util.random_string()
		self.time = date.now()

def send(sender, to, content):
	msg = Message(sender, content)
	inbox = user_messages.get(to, [])
	inbox.insert(0, msg)
	user_messages[to] = inbox

def remove_mail(userid, id):
	inbox = user_messages.get(userid, [])
	inbox = [ msg for msg in inbox if msg.id != id ]
	user_messages[userid] = inbox

class Messages(fw.core.Widget):
	view = 'chat.fwml:messages'
	
	to = fw.core.Attr(default=None)
	
	def after_unserialize(self):
		self.messages = user_messages.get(self.session.userid, [])
	
	def get_view_attrs(self):
		return dict(messages=self.messages, to=self.to)
	
	def format_time(self, t):
		return date.format_time('%Y-%m-%d %H:%M:%S', t)

	@fw.core.action()
	def send(self, to, content):
		send(self.session.userid, to, content)
		self.to = None
	
	@fw.core.action()
	def remove(self, id):
		remove_mail(self.session.userid, id)
		self.updated = True
		self.messages = user_messages.get(self.session.userid, [])


fw.core.widget(name='messages', public=True)(Messages)