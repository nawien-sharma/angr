#!/usr/bin/env python

import simuvex
from ..surveyor import Surveyor

import types
import collections
import logging
l = logging.getLogger("angr.surveyors.Explorer")

class Explorer(Surveyor):
	'''
	Explorer implements a symbolic exploration engine!

		found - paths where the target addresses have been found
		avoided - paths where the to-avoid addresses have been found
		deviating - paths that deviate from the restricted-to addresses
		looping - paths that were detected as looping
	'''

	path_lists = Surveyor.path_lists + [ 'found', 'avoided', 'deviating', 'looping']

	def __init__(self, project, start=None, starts=None, max_concurrency=None, max_active=None, pickle_paths=None, find=(), avoid=(), restrict=(), min_depth=0, max_depth=100, max_repeats=10, num_find=1, num_avoid=None, num_deviate=1, num_loop=None):
		'''
		Explores the path space until a block containing a specified address is
		found. Parameters (other than for Surveyor):

		@param find: a tuple containing the addresses to search for or a function
					 that, given a path, returns True or False
		@param avoid: a tuple containing the addresses to avoid or a function that,
					  given a path, returns True or False
		@param restrict: a tuple containing the addresses to restrict the
						 analysis to (i.e., avoid all others), or a function that,
						 given a path, returns True or False
		@param min_depth: the minimum number of SimRuns in the resulting path
		@param max_depth: the maximum number of SimRuns in the resulting path

		@param num_find: the minimum number of paths to find (default: 1)
		@param num_avoid: the minimum number of paths to avoid
						  (default: infinite)
		@param num_deviate: the minimum number of paths to deviate
							(default: infinite)
		@param num_loop: the minimum number of paths to loop
						 (default: infinite)
		'''
		Surveyor.__init__(self, project, start=start, starts=starts, max_concurrency=max_concurrency, max_active=max_active, pickle_paths=pickle_paths)

		# initialize the counter
		self._instruction_counter = collections.Counter()

		self._find = self._arg_to_set(find)
		self._avoid = self._arg_to_set(avoid)
		self._restrict = self._arg_to_set(restrict)
		self._max_repeats = max_repeats
		self._max_depth = max_depth
		self._min_depth = min_depth

		self.found = [ ]
		self.avoided = [ ]
		self.deviating = [ ]
		self.looping = [ ]

		self._num_find = num_find
		self._num_avoid = num_avoid
		self._num_deviate = num_deviate
		self._num_loop = num_loop

	@staticmethod
	def _arg_to_set(s):
		if type(s) in (int, long): return { s }
		elif type(s) in (types.FunctionType, types.MethodType): return s
		return set(s)

	def path_comparator(self, x, y):
		return self._instruction_counter[x.last_addr] - self._instruction_counter[y.last_addr]

	@property
	def done(self):
		if len(self.active) == 0:
			l.debug("Done because we have no active paths left!")
			return True

		if self._num_find is not None and len(self.found) >= self._num_find:
			l.debug("Done because we found the targets on %d path(s)!", len(self.found))
			return True

		if self._num_avoid is not None and len(self.avoided) >= self._num_avoid:
			l.debug("Done because we avoided on %d path(s)!", len(self.avoided))
			return True

		if self._num_deviate is not None and len(self.deviating) >= self._num_deviate:
			l.debug("Done because we deviated on %d path(s)!", len(self.deviating))
			return True

		if self._num_loop is not None and len(self.looping) >= self._num_loop:
			l.debug("Done because we looped on %d path(s)!", len(self.looping))
			return True

		return False

	def _match(self, criteria, path=None, imark_set=None):
		if type(criteria) is set:
			intersection = imark_set & criteria
			for i in intersection:
				l.debug("... matched 0x%x", i)
			return len(intersection) > 0
		else:
			return criteria(path)

	def filter_path(self, p):
		if len(p.addr_backtrace) < self._min_depth:
			return True

		if isinstance(p.last_run, simuvex.SimIRSB): imark_set = set(p.last_run.imark_addrs())
		else: imark_set = { p.last_run.addr, p.__class__.__name__ }

		for addr in imark_set:
			self._instruction_counter[addr] += 1

		l.debug("Checking 'avoid'...")
		if self._match(self._avoid, path=p, imark_set=imark_set):
			self.avoided.append(p)
			return False

		l.debug("Checking 'find'...")
		if self._match(self._find, path=p, imark_set=imark_set):
			self.found.append(p)
			return False

		l.debug("Checking 'restrict'...")
		if (type(self._restrict) is not set or len(self._restrict) > 0) and not self._match(self._restrict, path=p, imark_set=imark_set):
			l.debug("Path %s is not on the restricted addresses!", p)
			self.deviating.append(p)
			return False

		if p.detect_loops(self._max_repeats) >= self._max_repeats:
			# discard any paths that loop too much
			l.debug("Path %s appears to be looping!", p)
			self.looping.append(p)
			return False

		return True

	def __str__(self):
		return "<Explorer with paths: %s, %d found, %d avoided, %d deviating, %d looping>" % (Surveyor.__str__(self), len(self.found), len(self.avoided), len(self.deviating), len(self.looping))
