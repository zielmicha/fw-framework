#!/usr/bin/env python
import logging
import json
import urllib

import fw.core
import fw.util

import game
import gamemap
import gamedef
import date

import main

class CityWidget(fw.core.Widget):
	id = fw.core.Attr()
	
	def after_unserialize(self):
		try:
			self.city = game.City.Get(self.id)
		except game.Error:
			self.city = None
	
	def get_view_attrs(self):
		state = self.city.GetState()
		def get_army(n):
			return [ (player, army[n], n)
					for player, army in self.city.foreign_armies.items()
					if (n in army) and any(army[n].values()) ]
		armies = get_army('attack') + get_army('defense')
		return dict(id=self.id, city=self.city, config=game.gamedef.config,
					state=state, armies=armies)
	
	def get_img(self, name, opt=None):
		if opt:
			name += '-' + opt
		return '/static/img/%s.png' % name
	
	def get_map_url(self, id):
		pos = map(int, id.split(','))
		return '/map/' + ','.join(map(str, pos))
	
	def get_dialog_url(self, name, **args):
		return main.get_dialog_url(self, name, **args)

fw.core.widget()(CityWidget)

class City(CityWidget):
	view = 'city.fwml:city'
	
	@fw.core.action()
	def train(self, name, amount):
		self.city.Train(name, int(amount))
		self.updated = True
	
	@fw.core.action()
	def build(self, name):
		self.city.Build(name)
		self.updated = True
	
	@fw.core.action()
	def set_title(self, title):
		gamemap.set_title(self.city, title)
	
	def get_battle_url(self):
		return '/battle?city=' + urllib.quote(self.id)

fw.core.widget(name='city', public=True, requires_login=True)(City)

class CityPreview(CityWidget):
	view = 'city.fwml:city-preview'
fw.core.widget(name='city-preview')(CityPreview)

class BattleLogDialog(fw.core.Widget):
	view = 'city.fwml:battlelog'
	
	city = fw.core.Attr()
	
	def get_view_attrs(self):
		def proc_val(key, argval):
			if key.startswith('battle'):
				(defender, attacker) = argval
				return dict(attacker=attacker[1], defender=defender[1],
					units=[ ('attacker',) + v for v in attacker[0] ] +
					[ ('defender',) + v for v in defender[0] ])
			elif key.startswith('army'):
				units, player, mission = argval
				return dict(units=units, player=player, mission=mission)
			else:
				return dict()
		log = sorted([
			(float(k.split('-')[1]), k.split('-')[0], proc_val(k, v))
			for k, v in gamemap.battle_logs.get(self.city,{}).items() ],
			key=lambda item: item[0], reverse=True)
		return dict(log=log)
	
	def format_time(self, t):
		return date.format_time('%Y-%m-%d %H:%M:%S', t)

fw.core.widget(name='battlelog-dialog', public=True)(BattleLogDialog)

class TimeCounter(fw.core.Widget):
	view = 'city.fwml:timecounter'
	
	time = fw.core.Attr(type=float)
	
	def get_view_attrs(self):
		return dict(seconds=int(self.time * 3600))

fw.core.widget(name='timecounter',)(TimeCounter)

class Increaser(fw.core.Widget):
	view = 'city.fwml:increaser'
	
	start = fw.core.Attr(type=float)
	step = fw.core.Attr(type=float)
	
	def get_view_attrs(self):
		return dict(start=self.start, step=self.step)

fw.core.widget(name='increaser',)(Increaser)

class Battle(fw.core.Widget):
	view = 'battle.fwml'
	
	city = fw.core.Attr()
	
	def after_unserialize(self):
		self.cityobj = game.City.Get(self.city)
	
	def get_view_attrs(self):
		state = self.cityobj.GetState()
		return dict(id=self.city, city=self.cityobj, config=game.gamedef.config,
					state=state)
	
	@fw.core.action()
	def build(self, name):
		self.cityobj.Build(name)
		self.updated = True

fw.core.widget(name='battle', public=True)(Battle)

@fw.core.api()
def get_battle_state(cityname):
	def full_units(units):
		' Return units, but with all possible unit types '
		return dict([ (kind, units.get(kind, 0)) for kind in gamedef.units.keys() ])
	
	log = gamemap.battle_logs.get(cityname, {})
	now = date.now()
	log = [ (float(k[len('battle-'):]), v) for k,v in log.items() if k.startswith('battle-') ]
	log.sort(reverse=True)
	entries = dict(attack={}, defense={})
	if log:
		entry_time, entry = log[0]
	else:
		entry_time = 0
	if (entry_time + gamedef.config.fight_round*1.2) > now:
		defense, attack = entry
		defenders = defense[1]
		attackers = attack[1]
		entries['defense'] = defense[0]
		entries['attack'] = attack[0]
	else:
		city = game.City.Get(cityname)
		defenders = city.garnison.copy()
		for k,v in city.friends_garnison.items(): defenders[k] = defenders.get(k,0) + v
		attackers = city.enemy_garnison
	return json.dumps((entries, full_units(attackers), full_units(defenders)))



