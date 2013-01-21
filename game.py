import logging
import math
import date
import pickle
import random

from fw.db import ObjectProperty
from fw import db
import fw.util

import gamedef
import gamemap

class ResProperty(ObjectProperty):
	def make_value_from_datastore(self, value):
		val = pickle.loads(value)
		if self.defaultval is not None and val is None:
			val = self.defaultval
		return gamedef.Res(val)
	
	def validate(self, value):
		if not isinstance(value, (tuple, type(None))):
			raise db.BadValueError("%r" % type(value))
		return value

TimeProperty = db.FloatProperty

event_types = {}
continoues_types = []

ATTACK_MISSIONS = ('attack', )

def register_continous(func):
	continoues_types.append(func)
	return func

def register_event(func):
	event_types[func.__name__] = func
	return func

class Error(Exception):
	pass

class NotEnoughResourcesError(Error):
	pass

class NotEnoughUnitsError(Error):
	pass

class City(db.Model):
	# PUBLIC INTERFACE

	@db.transaction
	def Build(self, ident):
		if ident not in self.buildings:
			self.buildings[ident] = 0
		level = self.buildings[ident] + 1
		buildingobj = gamedef.get_building_object(ident)
		self.add_queue_event(
			qname='_buildings',
			timedelta=buildingobj.get_time(level),
			func='building_built',
			args=(ident, buildingobj.get_costs(level))
		)
		self.put()
	
	@db.transaction
	def Train(self, ident, amount):
		self.add_units_to_queue(ident, amount)
		self.put()
	
	def SendArmy(self, dest, units, mission, time):
		id = fw.util.random_string()
		now = date.now()
		dest_city = City.Get(dest)
		cost, walk_time = self.CountArmyTravelCostAndTime(dest_city, units, time)
		leave_time = now + walk_time + time
		
		logging.info('leave-time time=%s walk=%s %s', time, walk_time, leave_time)
		if not self.decr_resources(cost):
			raise NotEnoughResourcesError()
		self.send_army(id, dest_city, units, mission, leave_time=now + walk_time + time)
		dest_city.send_army_from(id, arrive_time=now + walk_time,
								 walk_time=walk_time, leave_time=now + walk_time + time,
								 src=self, units=units, mission=mission)
		gamemap.add_travelling_army(id, self.owner, mission, units, self.location,
									dest, self.updated,
									self.updated + walk_time,
									leave_time)
		self.refresh()
	
	@classmethod
	def Get(self, location):
		city = self.get_city(location)
		#assert user._priviligated
		#if not user.userid == city.owner:
		#	raise Error('You are not owner of this city!')
		return city
	
	@classmethod
	def Create(self, user, location, title):
		City(location=location, owner=user, title=title).put()
	
	def GetState(self):
		def make_res_time(inc): # make it faster
			if inc == 0: return dict(time=-1, res=0)
			t = abs(1 / float(inc) * 3600)
			if t == 0: return dict(time=-1, res=0)
			got = 1
			while t < 1:
				t *= 10
				got *= 10
			return dict(time=t, res=got)
			
		return dict(
			garnison=self.garnison.copy(),
			buildings=self.buildings.copy(),
			location=self.location,
			building_progress=self.GetBuildingProgress(),
			unit_queues=self.GetUnitQueues(),
			queues_speed=self.queues_speed.copy(),
			resources=[
				dict(count=count,
					 income=inc,
					 name=nm,
					 time=make_res_time(inc),
					 buildings=[ (b_name, self.buildings.get(b_name, 0))
								for b_name in gamedef.config.resource_buildings[nm] ])
				for count, inc, nm in 
				zip(self.resources, self.resource_income, gamedef.config.resources)
			],
			travelling_to=list(self.GetTravellingTo()),
		)
	
	def CountArmyTravelCostAndTime(self, dest, units, time):
		dist = self.calc_dist_to(dest)
		walk_time = self.calc_walk_time(dist, units)
		cost = self.get_travel_cost(units, time, 'battle_upkeep').add(
				self.get_travel_cost(units, walk_time*2, 'travel_upkeep'))
		return cost, walk_time
	
	def calc_walk_time(self, dist, units):
		return dist * gamedef.config.walk_speed

	def get_travel_cost(self, units, time, field_name):
		cost = gamedef.empty_res()
		for typename, amount in units.items():
			type = gamedef.units[typename]
			single_cost = getattr(type, field_name)
			cost = cost.add(single_cost.mul(amount * time))
		return cost
	
	############################## GET * FUNCTONS ##############################

	def GetBuildingProgress(self):		
		return [
				(time - self.updated, args[0])
				for time, func, args, qname in self.events
				if qname == '_buildings'
			]
	
	def GetUnitQueues(self):
		def get_unit_queues():
			names = gamedef.config.unit_queues
			return zip(names, [
				(0, [])
					if (name not in self.unit_queues)
					else self.unit_queues[name]
				for name in names
			])
		return list(
			dict(name=qname, accum=accum, producing=[
					dict(name=ident, count=amount)
					for ident, amount, time, costs in queue
				], items=[
					dict(name=unit.ident, count=self.garnison.get(unit.ident, 0),
						 config=gamedef.units[unit.ident])
					for unit in gamedef.units_by_queue[qname]
				], isproducing=bool(queue),
				left=queue[0][2]-accum if queue else None,
				building=self.buildings[qname] if qname in self.buildings else 0
			)
			for qname, (accum, queue) in get_unit_queues()
		)
	
	def GetArmyState(self):
		names = gamedef.config.unit_queues
		def get_q_state(name):
			units = gamedef.units_by_queue[name]
			if name in gamedef.buildings:
				building = self.buildings.get(name, 0)
			else:
				buildings = None
			return (
				building,
				[ (unit.ident, self.garnison[unit.ident]) for unit in units ]
			)
		return map(get_q_state, names)
	
	def GetTravellingTo(self):
		for ev in self.events:
			time, kind, params, qname = ev
			rel_time = time - self.updated
			if kind == 'foreign_army_arrives':
				units, player, mission = params
				yield dict(time=rel_time, units=units, player=player, mission=mission)

	############################################################################
	
	@classmethod
	def get_city(self, location):
		city = db.find_one(City, ('location =', location))
		if not city:
			raise Error('City not found.')
		city.update()
		return city
	
	def update(self):
		self._exec_after_update = []
		self._update()
		for func in self._exec_after_update:
			func()
		del self._exec_after_update

	@db.transaction
	def _update(self):
		now = date.now()
		if not self.updated: self.updated = now
		self.events.sort()
		self.process_queues(now)
		self.process_events(now)
		self.put()
	
	def update_continous(self, amount):
		for method in continoues_types:
			method(self, amount)
	
	def process_queues(self, now):
		for ident, (func, args, time) in list(self.locked_queues.items()):
			if not self.run_event(func, args): 
				del self.locked_queues[ident] # unlock
				# now move all events in this queue forward in time
				forward = now - time
				def move_forward((mtime, func, args, qname)):
					if qname == ident: # move forward only events from locked queue
						return (mtime + forward, func, args, qname)
				self.events = map(move_forward, self.events)
			#else: do nothing, queue is still locked
	
	def lock_queue(self, name, func, args, time):
		self.locked_queues[name] = (func, args, time)
	
	def queue_is_locked(self, name):
		return name in self.locked_queues
	
	def process_events(self, now):
		while True: # run until all events are processed
			last_updated = self.updated
			to_delete = []
			old_events = self.events
			old_events.sort()
			self.events = []
			i = -1
			for i, (time, func, args, qname) in enumerate(old_events):
				if time > now:
					break # reached the end of events which happened aleardy
				if self.queue_is_locked(qname): continue # not enough resouces etc.
				self.updated = time
				self.update_continous(last_updated - time)
				last_updated = time
				if not self.run_event(func, args):
					to_delete.append(i)
				else:
					self.lock_queue(qname, func, args, time)
			
			self.update_continous(now - last_updated)
			
			old_events = [ val for i, val in enumerate(old_events) if i not in to_delete ]
			if not self.events:
				self.events = old_events
				break
			else:
				self.events += old_events
			
		self.updated = now
	
	def run_event(self, func, args):
		return event_types[func](self, *args)
	
	def add_event(self, time, func, args, tag=None):
		self.events.append([time, func, args, tag])
	
	def add_queue_event(self, qname, timedelta, func, args):
		timedelta /= self.get_queue_speed(qname)
		self.add_event(self.put_queue_ready(qname, timedelta), func, args, qname)
	
	def get_queue_ready(self, qname):
		now = date.now()
		if qname not in self.queues:
			self.queues[qname] = now
		last = self.queues[qname]
		if last < now:
			return now
		else:
			return last
	
	def put_queue_ready(self, qname, timedelta):
		time = self.get_queue_ready(qname) + timedelta
		self.queues[qname] = time
		return time
	
	def decr_resources(self, res):
		if not self.resources.is_enough(res):
			return False
		self.resources = self.resources.sub(res)
		return True
	
	def decr_garnison(self, units):
		for name, count in units.items():
			if self.garnison.get(name, 0) < count:
				raise NotEnoughUnitsError(name)
		
		for name, count in units.items():
			if count:
				self.garnison[name] -= count

	def incr_resources(self, res):
		self.resources = self.resources.add(res)
	
	def get_queue_speed(self, qname):
		return self.queues_speed.get(qname, 1)
	
	def refresh(self):
		self.resource_income = gamedef.config.default_income
		self.queues_speed = {}
		class Env:
			def incr_resource_income(this, res):
				self.resource_income = self.resource_income.add(res)
			def speed_queue(this, name, times):
				if name not in self.queues_speed:
					self.queues_speed[name] = 1
				self.queues_speed[name] *= times
		env = Env()
		for ident, level in self.buildings.items():
			buildingobj = gamedef.get_building_object(ident)
			buildingobj.run(env, level)
		
		for ident, n in self.garnison.items():
			self.decr_resource_income(gamedef.get_unit_object(ident).get_upkeep().mul(n))
	
	def add_units(self, ident, amount):
		if ident not in self.garnison:
			self.garnison[ident] = 0
		self.garnison[ident] += amount
		self.refresh()
	
	def decr_resource_income(self, res):
		self.resource_income = self.resource_income.sub(res)
	
	def get_unit_queue(self, name):
		if name not in self.unit_queues:
			self.unit_queues[name] = [0, []]
		return self.unit_queues[name]
	
	def get_garnison(self, name):
		if name not in self.garnison:
			self.garnison[name] = 0
		return self.garnison[name]
	
	def add_units_to_queue(self, ident, amount):
		unitobj = gamedef.get_unit_object(ident)
		q = unitobj.get_queue()
		qspeed = self.queues_speed[q] if q in self.queues_speed else 1
		self.get_unit_queue(q)[1].append(
			[ident, amount, unitobj.get_time() / qspeed, unitobj.get_costs()]
		)
	
	@db.transaction
	def send_army(self, id, dest, units, mission, leave_time):
		# todo: consume food.
		self.decr_garnison(units)
		self.add_event(leave_time, 'own_army_leaves_other_city', (dest.location, ))
		self.put()
	
	@register_event
	def own_army_leaves_other_city(self, other_city):
		def do():
			# update other city, so it will add event own_army_arrives to self
			City.Get(other_city)
		self._exec_after_update.append(do)
	
	def send_army_from(self, id, arrive_time, walk_time, leave_time, src, units, mission):
		self.add_event(arrive_time, 'foreign_army_arrives', (units, src.owner, mission))
		self.add_event(leave_time, 'foreign_army_leaves', (id, walk_time, units, src.owner, mission, src.location))
		self.put()
	
	def calc_dist_from(self, src):
		mypos = self.get_pos()
		its_pos = src.get_pos()
		diff = (mypos[0] - its_pos[0], mypos[1] - its_pos[1])
		return math.sqrt(diff[0] * diff[0] + diff[1] * diff[1])
	
	def calc_dist_to(self, dest):
		return self.calc_dist_from(dest)

	@register_event
	def foreign_army_arrives(self, units, player, mission):
		all_units = self.foreign_armies.get(player, {})
		if mission in ATTACK_MISSIONS:	
			self.incr_garsion(units, out=all_units.setdefault('attack', {}))
			self.incr_garsion(units, out=self.enemy_garnison)
		else:
			self.incr_garsion(units, out=all_units.setdefault('defense', {}))
			self.incr_garsion(units, out=self.friends_garnison)
		self.foreign_armies[player] = all_units
		
		# save log
		logkey = self.updated
		logval = (units, player, mission)
		
		def save_log():
			current_log = gamemap.battle_logs.get(self.location, {})
			current_log['army-%f' % logkey] = logval
			gamemap.battle_logs[self.location] = current_log
		
		self._exec_after_update.append(save_log)
	
	def incr_garsion(self, units, out):
		for name, num in units.items():
			out[name] = (out.get(name) or 0) + num
	
	@register_event
	def foreign_army_leaves(self, id, walk_time, units, player, mission, dest):
		decreased_units = self.decr_foreign_garnsion(player, mission, max=units)
		
		logging.info('foreign army leaves %s to %s (%d)', decreased_units, dest,
					 (date.now()-self.updated-walk_time)*-3600)
		
		
		def add_arriving_army():
			dest_city = City.Get(dest)
			
			@db.transaction
			def do():
				dest_city.add_event(self.updated+walk_time, 'own_army_arrives', (id, decreased_units))
				dest_city.put()
			do()
		
		self._exec_after_update.append(add_arriving_army)
	
	def decr_foreign_garnsion(self, player, mission, max):
		player_garnison = self.foreign_armies.get(player, {}).get(mission, {})
		everyone_garnsion = self.enemy_garnison if (mission in ATTACK_MISSIONS) else self.friends_garnison
		decreased = {}
		for name, count in max.items():
			count_in_garnsion = player_garnison.setdefault(name, 0)
			will_be_desreased = min(count, count_in_garnsion)
			player_garnison[name] = (player_garnison[name] or 0) - will_be_desreased
			everyone_garnsion[name] = (everyone_garnsion.get(name) or 0) - will_be_desreased
			decreased[name] = will_be_desreased
		return decreased
	
	@register_event
	def own_army_arrives(self, id, units):
		self.incr_garsion(units, out=self.garnison)
		def arrived():
			gamemap.remove_travelling_army(id, self.owner)
		self._exec_after_update.append(arrived)

	############################################################################
	############################ continous events ##############################
	############################################################################
	
	@register_continous
	def _add_resources(self, period):
		self.incr_resources(self.resource_income.mul(period))
	
	@register_continous
	def _produce_units(self, period):
		if not self.unit_queues: return
		for qident, q in self.unit_queues.items():
			(accumulated, requests) = q
			if not requests:
				q[0] = 0
				continue
			time_left = period + accumulated
			# TODO: maybe support for locking queues?
			for i, (ident, amount, time, costs) in enumerate(requests):
				costs = gamedef.Res(costs)
				may_be_done = time_left / time
				resources_enough_for = self.resources.div_max(costs)
				#logging.info('Units: [may_be_done, amount, resources_enough_for] = %r', [may_be_done, amount, resources_enough_for])
				#logging.info()
				will_be_done = int(min([may_be_done, amount, resources_enough_for]))
				if will_be_done == 0:
					break # don't waste time on producing 0 units
				time_needed = will_be_done * time
				res_needed = costs.mul(will_be_done)
				time_left -= time_needed
				self.decr_resources(res_needed)
				self.add_units(ident, will_be_done)
				if not isinstance(requests[i][1], int):
					requests[i][1] = int(requests[i][1])
				requests[i][1] -= will_be_done
				if requests[i][1]:
					break # these units are not yet produced
			requests[:] = filter(lambda (a, n, b, c): n != 0, requests)
			if requests:
				q[0] = time_left
			else: # there are no tasks, so queue is now wasting its time
				q[0] = 0
	
	@register_continous
	def _dissolve_units(self, period):
		not_enough = ( r < 0 for r in self.resources )
		if not any(not_enough): return
		for i, is_not_enough in enumerate(not_enough):
			if is_not_enough:
				units = gamedef.get_unit_with_biggest_upkeep(i)
				income = self.resource_income[i]
				for unit, cost in units:
					if income <= 0: break
					n = self.get_garnison[unit]
					need_destroy = -income / cost
					will_destroy = min(n, need_destroy)
					self.garnison[unit] -= will_destroy
					
	
	@register_continous
	def _fight(self, period):
		if not any(self.enemy_garnison.values()):
			return # no one attacking
		
		start_round_id = int(math.ceil(self.updated / gamedef.config.fight_round))
		end_round_id = int(math.floor((self.updated + period) / gamedef.config.fight_round))
		
		defense_garnison = dict(
			(key, self.garnison.get(key, 0) + self.friends_garnison.get(key, 0))
			for key in gamedef.units.keys() )
		attack_garnsion = dict( (key, self.enemy_garnison.get(key))
			for key in gamedef.units.keys() )
		
		self.last_fight_round = end_round_id
		full_rounds = end_round_id - start_round_id + 1
		
		if not full_rounds:
			return
		
		#logging.info('Rounds: %d', full_rounds)
		
		log = []
		
		for i in xrange(start_round_id, end_round_id + 1):
			#logging.info('Round: %d', i)
			defense_garnison, attack_garnsion, round_log = \
				self.fight_round(defense_garnison, attack_garnsion)
			if round_log[0][0] or round_log[1][0]:
				log.append((i * gamedef.config.fight_round, round_log))
			if not defense_garnison or not attack_garnsion:
				break
		
		# save state
		self.enemy_garnison = attack_garnsion
		self._balance_enemy_kills()
		self.friends_garnison = defense_garnison
		self._balance_defense_kills()
		
		self.refresh()
		
		# save log
		def save_log():
			current_log = gamemap.battle_logs.get(self.location, {})
			for key, val in log:
				current_log['battle-%.10f' % key] = val
			gamemap.battle_logs[self.location] = current_log
		
		self._exec_after_update.append(save_log)
	
	def fight_round(self, defense, attack):
		old_attack = attack.copy()
		old_defense = defense.copy()
		#logging.info('Defenders turn!')
		defender_log = self.fight_army(old_defense, attack), old_defense.copy()
		#logging.info('Attackers turn!')
		attacker_log = self.fight_army(old_attack, defense), old_attack.copy()
		return defense, attack, (defender_log, attacker_log)
		
	def fight_army(self, attackers, victims):
		log = []
		for name, amount in attackers.items():
			attacker_class = gamedef.units[name]
			amount = amount or 0
			#logging.info('%r %s are attacking!', amount, name)
			amount = math.ceil(amount)
			while amount:
				if not victims:
					return log
				victim = random.choice(victims.keys())
				victim_class = gamedef.units[victim]
				victim_amount = victims[victim]
				if not victim_amount:
					del victims[victim]
					continue
				may_destroy_hp = attacker_class.attack * amount
				may_kill = min(float(may_destroy_hp) / victim_class.hp, amount) # todo: attack range
				will_be_killed = min(may_kill, victim_amount)
				used_attack_hp = will_be_killed * victim_class.hp
				left_attack_hp = may_destroy_hp - used_attack_hp
				attackers_that_not_attacked = int(left_attack_hp // attacker_class.attack)
				
				#logging.info('%d %s attacked and killed %d %s and damaged %d%% (out of %d)',
				#			 amount - attackers_that_not_attacked, name,
				#			 int(will_be_killed), victim, (will_be_killed % 1) * 100,
				#			 math.ceil(victims[victim]))
				
				# LOG: name, victim, attackedNumber, willBeKilled, allVictims
				log.append((name, victim, amount - attackers_that_not_attacked,
							will_be_killed, victims[victim]))
				
				victims[victim] -= will_be_killed
				if not victims[victim]:
					del victims[victim]
				
				amount = attackers_that_not_attacked
			#attackers[name] = amount
		return log
	
	def _balance_enemy_kills(self):
		self._balance(self.enemy_garnison, 'attack')
	
	def _balance_defense_kills(self):
		self.garnison = self._balance(self.friends_garnison, 'defense', self.garnison)
		
		for k, v in self.garnison.items():
			self.friends_garnison.setdefault(k, 0)
			self.friends_garnison[k] -= v
	
	def _balance(self, curr, type, additional=None):
		foreign_armies = self.foreign_armies.items()
		if additional is not None:
			ADDITIONAL = Ellipsis
			foreign_armies.append((ADDITIONAL, {type: additional}))
		for unittype in gamedef.units.keys():
			prev_count = sum( army.setdefault(type, {}).get(unittype, 0) for nm, army in foreign_armies )
			curr_count = curr.get(unittype) or 0
			lost_count = float(prev_count - curr_count)
			if prev_count == 0:
				#assert not curr_count, 'balancing (%s, %s):%s curr_count=%s, prev_count=%s' % (curr, type, unittype, curr_count, prev_count)
				lost_count = 0
				prev_count = 1
				continue
			for name, army in foreign_armies:
				lost_in_this_army = lost_count / prev_count * army[type].setdefault(unittype, 0)
				army[type][unittype] -= lost_in_this_army
		
		for name, army in foreign_armies:
			if not any( n>0 for n in army[type].values()) and name in self.foreign_armies:
				if type in self.foreign_armies[name]:
					del self.foreign_armies[name][type]
		
		if additional is not None:
			return additional
	
	############################################################################
	############################### events #####################################
	############################################################################
	
	@register_event
	def building_built(self, ident, costs):
		if not self.decr_resources(costs):
			return True
		self.buildings[ident] += 1
		self.refresh()
	
	############################################################################
	
	def get_pos(self):
		return map(int, self.location.split(','))
	
	buildings = ObjectProperty({})
	location = db.StringProperty()
	title = db.StringProperty()
	resources = ResProperty(gamedef.config.default_resources)
	resource_income = ResProperty(gamedef.config.default_income)
	updated = TimeProperty()
	
	events = ObjectProperty([])
	locked_queues = ObjectProperty({})
	queues = ObjectProperty({})
	queues_speed = ObjectProperty({})
	
	garnison = ObjectProperty({})
	unit_queues = ObjectProperty({})
	
	foreign_armies = ObjectProperty({})
	enemy_garnison = ObjectProperty({})
	friends_garnison = ObjectProperty({})
	
	last_fight_round = db.IntegerProperty()
	
	owner = db.StringProperty()
