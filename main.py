import logging
import random
import time
import json
import urllib

import fw.core
import fw.util
import fw.login

import game
import gamemap
import gamedef
import date

fw.util.add_translations('lang.yaml')

class WorldMap(fw.core.Widget):
	view = 'main.fwml:map'
	
	x = fw.core.Attr(type=int, default=0)
	y = fw.core.Attr(type=int, default=0)
	use3d = fw.core.BoolAttr(default=True)
	
	def get_view_attrs(self):
		self.map_retriever = gamemap.MapRetriever()
		H = 10
		W = 20
		halfH = H/2
		halfW = W/2
		entries = reduce(lambda x,y: x+y, [
			[ (x-self.x+halfW, y-self.y+halfH, self.get_entry(x,y)) for x in xrange(self.x-halfW, self.x+halfW)
				if self.get_entry(x,y) ]
			for y in xrange(self.y-halfH, self.y+halfH)
		])
		return dict(entries=entries, use3d=self.use3d)
	
	def get_entry(self, x, y):
		return self.map_retriever.get(x, y)

	def next(self, x=0, y=0):
		return dict(x=self.x+int(x), y=self.y+int(y))
	
	def create_style(self, x, y):
		return 'position:absolute;left:%sem;top:%sem' % (x,y)

fw.core.widget(name='worldmap', public=True)(WorldMap)

@fw.core.api()
def get_map_field(x, y):
	map = gamemap.MapRetriever()
	
	sx = int(x) // gamemap.SECTOR_SIZE
	sy = int(y) // gamemap.SECTOR_SIZE
	
	return json.dumps([
		(sx*gamemap.SECTOR_SIZE + x, sy*gamemap.SECTOR_SIZE + y, val)
		for (x, y), val in map.get_sector(sx, sy).items()
		])

@fw.core.api()
def get_travelling_armies():
	pass

class ArmyCol(fw.core.Widget):
	view = 'main.fwml:armycol'
fw.core.widget(name='armycol')(ArmyCol)
	
class TopRow(fw.core.Widget):
	view = 'main.fwml:toprow'
	
	@fw.core.action()
	def logout(self):
		fw.login.Account(self).logout()
	
	def get_view_attrs(self):
		return dict(
			name=self.session.user.profile.name
		)
	
fw.core.widget(name='toprow')(TopRow)

class Prepare(fw.core.Widget):
	view = 'main.fwml:prepare'
	
	@fw.core.action()
	def do(self, cityname):
		gamemap.prepare(self.session.userid, cityname)
		self.session['registered'] = True
		self.top.redirect('game')
fw.core.widget(name='prepare', public=True, requires_login=True)(Prepare)

class Game(fw.core.Widget):
	view = 'main.fwml:game'
	
	city = fw.core.Attr(default=None)
	dialog = fw.core.Attr('dialogname', default=None)
	what = fw.core.Attr(default=None)
	profile = fw.core.Attr(default=None)
	
	def create_children(self):
		if self.dialog:
			widget = fw.core.widgets[self.dialog + '-dialog'](self)
			widget.init_with_data(dict(city=self.city))
			self.add_child('dialog', None, widget)
		fw.core.Widget.create_children(self)
	
	def after_unserialize(self):
		if not self.session.get('registered'):
			self.top.redirect('prepare')
	
	def get_view_attrs(self):
		what = self.what or ('city' if self.city else ('profile' if self.profile else 'map'))
		cities = gamemap.get_cities_of_user(self.session.userid)
		travelling_armies = gamemap.get_travelling_armies(self.session.userid)
		return dict(city=self.city,
					overlay_style='display:block' if self.dialog else '',
					cities=cities, armies=travelling_armies, time=date.now(),
					what=what)
	
	def get_dialog_content(self):
		if self.dialog:
			return self.get_child('dialog').render()
		else:
			return '<span fw_widget_path="dialog"></span>'

	def close_dialog(self):
		self.updated = True
		self.dialog = None

	def get_dialog_url(self, name, **args):
		return get_dialog_url(self, name, **args)
	
	@fw.core.action()
	def set_lang(self, lang):
		self.session['lang'] = lang
fw.core.widget(name='game', public=True, requires_login=True)(Game)

class AttackDialog(fw.core.Widget):
	view = 'main.fwml:attack-dialog'
	
	city = fw.core.Attr()
	
	def get_view_attrs(self):
		attack_url = self.attack.get_action_url({}, AttackDialog.args)
		return dict(units=gamedef.units, attack_url=attack_url, city=self.city)
	
	@fw.core.action()
	def attack(self, goal, mission, time, **units):
		units = dict( (name, int(num or 0)) for name, num in units.items() )
		game.City.Get(self.city).SendArmy(goal, units, mission, float(time) / 3600.)
		self.top.redirect('/city/' + self.city)
	
	args = gamedef.units.keys() + ['goal', 'mission', 'time']
	args = dict(zip(args, args))

fw.core.widget(name='attack-dialog', public=True)(AttackDialog)

class MiniUnits(fw.core.Widget):
	view = 'main.fwml:mini-units'
	
	e = fw.core.Attr()
	
	def get_view_attrs(self):
		return dict(units=self.e)
	
	def get_img(self, name, opt=None):
		if opt:
			name += '-' + opt
		return '/static/img/%s.png' % name
fw.core.widget(name='mini-units')(MiniUnits)

class UpkeepWidget(fw.core.Widget):
	view = 'main.fwml:upkeep'
	
	city = fw.core.Attr()
	dest = fw.core.Attr()
	units = fw.core.Attr()
	time = fw.core.Attr(type=float)
	
	def get_view_attrs(self):
		units = json.loads(self.units)
		dest = game.City.Get(self.dest)
		upkeep, walk_time = game.City.Get(self.city).CountArmyTravelCostAndTime(dest, units, self.time)
		return dict(upkeep=upkeep, walk_time=walk_time, time=self.time)
	
	def get_img(self, name):
		return '/static/img/%s.png' % name

fw.core.widget(name='upkeep', public=True)(UpkeepWidget)

def get_dialog_url(self, name, **args):
	return self.top.get_old_url(update=dict(dialogname=name))