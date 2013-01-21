#!/usr/bin/env python
import logging

import fw.core

import game

class CityWidget(fw.core.Widget):
	id = fw.core.Attr()
	
	def after_unserialize(self):
		try:
			self.city = game.City.Get(self.id)
		except game.Error:
			self.city = None
	
	def get_view_attrs(self):
		return dict(city=self.city)


fw.core.widget()(CityWidget)

class City(CityWidget):
	view = 'dev.fwml:city'
	
	@fw.core.action()
	def create_city(self):
		game.City.Create(None, self.id)
	
	@fw.core.action()
	def build(self, name):
		self.city.Build(name)
	
	@fw.core.action()
	def train_units(self, name, amount):
		self.city.Train(name, int(amount))
	
	@fw.core.action()
	def gift(self, name, num):
		self.city.incr_resources(game.gamedef.res(**{name: int(num)}))
		self.city.put()

fw.core.widget(name='dev.city', public=True)(City)