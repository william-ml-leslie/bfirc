#    bfirc - 0.1.0	Pure Python ncurses IRC client with pretty colours
#    Copyright (C) 2007-2008  Robert Farrell
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os
import birclib
import parseopt
import re
import curses
from parseopt import ParseError
from bfircinit import *
from bfircinit import _COLOURS, _INPUT_HOOKS, _OUTPUT_HOOKS
from bfirclog import * 
from bfirclog import _mkncol
from birclib import Event
from birclib import nm_to_n
import time
import signal
import random
import traceback
import locale

#from dump import DEBUG

locale.setlocale( locale.LC_ALL, '' )
# HAI WELCOME TO MY INTERNET PROGRAM!!


#birclib.DEBUG = True

irc = birclib.IRC()
connections = {}
buffers = {}
_sbuffers = []
whois_buffer = {}


COMMAND_LIST = [ "quit", "server", "server",
    "url", "urls", "whois", "addtopic",
	 "addtopic", "topic", "allnames", 
	"watch", "watch", "names", "ignore",
	"ignoreto", "ignoreto", "join",
	"part", "part", "open", "msg", "say",
	"set", "away", "kick", "alias" ]

COMMAND_LIST.sort()            # hack hack hack

if not LOGS_DIR[-1] == "/": LOGS_DIR += "/"
if not PROGRAM_DIR[-1] == "/": PROGRAM_DIR += "/"

class IntEvent:
	def __init__ ( self, event_type, args ):
		self.event_type = event_type
		self.args = args
	
	def eventtype ( self ):
		return self.event_type

class OutEvent:
	def __init__ ( self, source, target, event_type, arguments ):
		self.event_type = event_type
		self.source = source
		self.target = target
		self.arguments = arguments
	
	def eventtype ( self ):
		return self.event_type

class BOF:
	pass

class EndSearch:
	pass

class CancelSearch:
	pass

class StartPasteMode:
	pass

class EndPasteMode:
	pass

class Paste:
	def __init__ (self):
		self.on = False
		self._on = False
		self._timeout = 0.01
		self._time = 0.0
		self._count = 0
		self._max = 5

	def inc (self):
		t = time.time()

		if t - self._time <= self._timeout:
			if not self._on:
				self._count += 1 

		elif self._on:
			self._on = False
			raise EndPasteMode

		else:
			self._count = 0

		self._time = t

		if self._count == self._max and not self._on:
			self._count = 0
			self._on = True
			raise StartPasteMode	

class whois_struct:
	def __init__ (self):
		self.user = []
		self.channels = []
		self.server = []


class irc_window:
	def __init__ (self, type="main", target=None):

		self.max_h, self.max_w = stdscr.getmaxyx()

		self.win_type = type


		self.contents = []
		self.seek = None
		self.nicklist = []
		self._ncols = {}
		self.topic = ""
		self.topic_raw = ""
		self.dirty = False
	
		self.logging = False
		self.log_file = ""

		self.scrolling = 0
	

		self.has_unread = False
		self.has_unread_events = False
		self.has_unread_messages = False
		self.has_unread_to_me = False


		if not type == "input":	self.resize()



		if type == "list":
			self.visible = False
			self.window.leaveok(True)

		elif type == "status":
			self.lag = 0.00

		elif type == "away":
			self.marks = []
			self.selected = -1
	
	def in_chan ( self, s ):
		s = s.lower()
		m = False
		for n in self.nicklist:
			if s == n.lower():
				m = True
				break

		return m or ( s == self.get_id().lower() )

	def init(foo):
		pass
	def redraw (self, no_refresh=False):
		#self.window.redrawwin()
		#self.window.touchwin()
		self.window.noutrefresh()
		if not no_refresh:
			self.window.refresh()
		input_win.refresh()

	def resize (self, no_create=False):
		global SCROLL_BY

		self.max_h, self.max_w = stdscr.getmaxyx()
		type = self.win_type
		if type == "main":
			self.h = self.max_h - 3
			self.w = self.max_w
			self.y = 1
			self.x = 0
			#SCROLL_BY = self.h
		elif type == "away":
			self.h = (self.max_h - 3) / 2
			self.w = self.max_w
			self.y = 1
			self.x = 0
		elif type == "sep":
			self.h = 1
			self.w = self.max_w
			self.y = away_win.h + 1
			self.x = 0
		elif type == "context":
			self.h = self.max_h - 3 - away_win.h - sep_win.h
			self.w = self.max_w
			self.y = sep_win.y + 1
			self.x = 0
		elif type == "info":
			self.h = 1
			self.w = input_win.x
			self.y = self.max_h - 1
			self.x = 0
		elif type == "status":
			self.h = 1
			self.w = self.max_w
			self.y = self.max_h - 2
			self.x = 0
		elif type == "list":
			self.h = 5
			self.w = 18
			self.y = 1
			self.x = self.max_w - self.w - 1
		elif type == "topic":
			self.h = 1
			self.w = self.max_w
			self.y = 0
			self.x = 0

		if not no_create:
			self.window = curses.newwin(self.h, self.w, self.y, self.x)
			self.window.idlok(1)
			self.window.scrollok(True)

	def scroll_history (self, scroll_by):
		if not self.win_type == "input" or not self.contents: return False
		
		self.window.erase()

		l = len(self.contents)

		if self.i + scroll_by >= l:
			self.i = l
			return False
		elif self.i + scroll_by < 0: scroll_by = 0
		else: self.i += scroll_by

		return self.contents[self.i]

	def write_time (self):
		self.write(PROGRAM_NAME, time.strftime("%c"), "time")

	def addstr( self, s, a, wrap=False ):
		global URL
		sel = False
		if self == away_win and s.count( "\n" ) > 1:
			s = s.replace( "\n", " " )

		if a in [ COLOURS["plain"], COLOURS["plain"] | curses.A_BOLD ]: 
			rx = re.search( "((ftp|http):\/\/[a-zA-Z0-9\/\\\:\?\%\.\&\;=#\-\_\!\+\~]*)", s )
			if not rx:
				rx = re.search( "(www\.[a-zA-Z0-9\/\\\:\?\%\.\&\;=#\-\_\!\+\~]*)", s )
			if rx:
				URL = rx.groups()[0]
				if URL not in URL_LIST and URL + "/" not in URL_LIST and "http://" + URL not in URL_LIST:
					if len( URL_LIST ) >= 10: URL_LIST.pop( 0 )
					URL_LIST.append( URL )
		if a in [ COLOURS["select"], COLOURS["select"] | curses.A_BOLD, COLOURS["systemwrap"], COLOURS["systemwrap"] | curses.A_BOLD ]:
				sel = True

		if not wrap:
			self.window.addstr( s, a )
			return

		mx = self.window.getmaxyx()[1] - 2

		if not " " in s:
			x = self.window.getyx()[1]
			if x + len( s ) > mx:
				self.window.addstr( '\n' )
			self.window.addstr( s, a )
			return

		s = s.split(" ")
		l = len( s )
		
		for j, i in enumerate( s ):
			y, x = self.window.getyx()

			if x + len( i ) > mx:
				if sel:
					# Fill the line out if it's a selected item in a list (as per away mode)
					self.window.addstr( " " * (mx - x-1 ), a )
				if self == away_win:
					# Only show first line if it's for the away messages list
					break
				else:
					if len ( i ) < mx: tb = "\t"
					else: tb = ""
					self.window.addstr( '\n' + tb )

			if j != l - 1 or l == 1:
				spc = ' '
			else:
				spc = ''

			#if j < l -1: spc = " "
			#else: spc = ""
			self.window.addstr(i + spc, a )
		
		
	def echo (self, string, attribs=None, event_type=None, no_refresh=False, y=None, x=None, wrap=False):

		if not attribs: attribs = COLOURS["plain"]

		

		if y is not None and x is not None:
			self.window.move(y, x)
		if "\020r" in string:
			string = string.replace("\020r", "\r")
		if "\020n" in string:
			string = string.replace("\020n", "\n")
		if "\r" in string:
			string = string.replace("\r", "")
		
		self._echo_bold( string, attribs, wrap )

		if not self in buffers.values() or self.get_id() == current_buffer and not no_refresh and not AWAY:
			self.window.noutrefresh()
			if list_win.visible:
				list_win.window.redrawwin()
				list_win.window.noutrefresh()

		if self in buffers.values() and self.get_id() != current_buffer:
			if event_type in ["privmsg", "pubmsg", "action"]:
				self.has_unread = True
				self.has_unread_messages = True
			elif event_type in ["join", "part", "quit"] and SHOW_EVENTS:
				self.has_unread = True
				self.has_unread_events = True
			elif event_type in ["system", "systemwrap", "error"]:
				self.has_unread = True
				self.has_unread_events = True
			update_status()
		if not no_refresh and not AWAY:
			input_win.noutrefresh()
			curses.doupdate()

	def _echo_bold ( self, string, attribs, wrap=False ):

		bold_toggle = False

		if "" in string:
			for s in string.split(""):
				if bold_toggle: bold_attribs = attribs | curses.A_BOLD
				else: bold_attribs = attribs

				bold_toggle = not bold_toggle

				self.addstr(s, bold_attribs, wrap)
		else:
			self.addstr(string, attribs, wrap)


	def stop_logging (self):
		if self.logging:
			self.logging = False
			try:
				self.log_file.close()
			except: return False


	def write (self, src, string, event_type=None, log_only=False):
		msg_from, attribs, string = format_string( src, string, event_type )

		if event_type in [ 'privmsg', 'pubmsg', 'action' ]:
			if src not in self._ncols.keys():
				self._ncols[ src ] = mkncol( src )
			attribs = self._ncols[ src ]


		highlight_msg = False

		if msg_from and is_highlighted( string )[ 0 ]:
			highlight_msg = True	
			#string = "%s" % string
			if self.get_id() != current_buffer:
				self.has_unread = True
				self.has_unread_to_me = True

		stamp = stamp_decor.prefix + time.strftime("%H:%M:%S") + stamp_decor.suffix
		
		if LOGGING:
			pfx = get_log_prefix( event_type )
			if msg_from:
				o = str( (pfx or "") + stamp + msg_from + string + "\n").replace("", "")
				log_write( self, o )
			else:
				o = str( (pfx or "") + stamp + string + "\n").replace('', '')
				log_write( self, o )

		if event_type in ( "msg_to_me", "msg_from_me" ):#== "msg_to_me":
			priv_msg = "PM"

			if LOGGING:
				pfx = get_log_prefix( "privmsg" )
				if event_type == "msg_to_me":
					_src = src
				elif event_type == "msg_from_me":
					_src = NICK
				m = format_string( _src, string, "privmsg" )[ 0 ]
				o = str( (pfx or "") + stamp + m + string + "\n").replace("", "")
				log_write( src.lower(), o )
		else:
			priv_msg = None

		if not log_only:
			if len(self.contents) and not self.scrolling:
				self.echo("\n", no_refresh=True)

			self.insert_line( msg_from, attribs, string, stamp )
			if not self.scrolling:
				out_str = self.compile_escape_string( msg_from, attribs, string, stamp)
				self.echo_escape_string( out_str, no_refresh=True, event_type=event_type )
	

			if msg_from and AWAY:
				topic_win.window.erase()
				if birclib.is_channel( self.get_id() ):
					pfx = '' + self.get_id() + ': '
				else:
					pfx = ''

				tws = ( pfx + msg_from + string)[:topic_win.w-1]
				tws += ( topic_win.w - 1 - len( tws ) ) * " "
				topic_win.echo( tws, COLOURS["topic"] )
	
			pm = src.lower() in buffers.keys() and not birclib.is_channel( self.get_id() ) 

			if AWAY and (highlight_msg or event_type == "msg_to_me" or priv_msg or pm):
				away_win.echo("\n", no_refresh=True)
				away_win.marks.append( ( self.get_id(), len(self.contents ) ) )
				away_frm = ( priv_msg or self.get_id() ) + ": " + msg_from + ": "
				contents_str = self.compile_escape_string( away_frm, attribs, string, stamp )
				away_win.insert_line( away_frm, attribs, string, stamp )#contents_str )
				away_win.echo_escape_string( contents_str )
				update_sepwin( len( away_win.marks ) )

		update_status()

		if not AWAY and self.get_id() == current_buffer:
			self.window.noutrefresh()
			input_win.refresh()

		if ( event_type == "me_say" or event_type == "me_msg" ) and self.scrolling:
			self.scroll_to(0)

	


	def clear (self):
		self.window.erase()
		self.refresh()

	def refresh (self):
		self.window.refresh()

	def get_id (self):
		return buffers.keys()[ buffers.values().index(self) ]

	def search (self, s):
		global SEARCH_MODE

		SEARCH_MODE = True

		info_win.window.erase()
		info_win.echo("    Search:", COLOURS["system"])
		curses.curs_set(0)
		search_win.erase()
		search_win.window.touchwin()
		#search_win.window.redrawwin()
		search_win.refresh()
		try:
			while True:
				try: c = stdscr.getkey()
				except: c = None	
				if c:
					result = process_input(search_win, c, search_win.s)#, True)

					if type(result) == str:
						search_win.s = result
					elif (type(result) == bool and not result) and ( search_win.s or len(search_win.temp_buffer) ):
						break

		except CancelSearch:
			SEARCH_MODE = False
			buffer_switch()
			return

		search_win.s = "".join(search_win.temp_buffer) + search_win.s
		search_win.temp_buffer = []
		search_win.contents.append(search_win.s)
		search_win.i = len(search_win.contents)
		s = search_win.s
		search_win.s = ""

		sch = False
		sch = self.scroll( 0, v=True, m=s )
		if sch is None:
			ask_question("Finished searching for " + s + ". Press any key.")
			self.scroll_to(0)
			return

		while True:
			try:
				self.scroll( self.h*2, v=True )
				self.scroll_to( sch, hl=s )
				if sch:
					c = ask_question( "r: search again, x: stop search.", ["r", "x"] )
				if c == "x":
					raise EndSearch
				elif c == "r":
					sch = False

				while sch is False:
					sch = self.scroll( 1, v=True, m=s )
					if sch is None:
						raise BOF

			except BOF:
				SEARCH_MODE = False

				ask_question("Finished searching for " + s + ". Press any key.")
				self.scroll_to(0)
				break

			except CancelSearch:
				SEARCH_MODE = False

				ask_question("Search canceled. Press any key.")
				self.scroll_to(0)
				break

			except EndSearch:
				SEARCH_MODE = False

				self.scroll_to(0)
				break

		

	def echo_search ( self, s, spns, attr=None ):
		if attr is None: attr = COLOURS["plain"]
		j = 0
		for i in range( len( spns ) ):
			o = s[ j : spns[i][0] ]
			j = spns[i][1]
			self.echo( o, attr, no_refresh=True, wrap=True )
			o = s[ spns[i][0] : spns[i][1] ]
			self.echo( o, COLOURS["search"], no_refresh=True, wrap=True )
		o = s[ j : ]
		if len( o ):
			self.echo( o, attr, no_refresh=True, wrap=True )

	def open_log (self, fs=False):
		if LOG_ID:
			path = LOGS_DIR + LOG_ID + "/" + self.get_id()
		else:
			path = LOGS_DIR + NICK + "/" + self.get_id()
		if os.access( path, os.F_OK ):
			f = open( path )
			if not self.seek or fs:
				f.seek( os.stat( path ).st_size -1 ) 
			else:
				f.seek( self.seek )
			return f
		else: return False

	def echo_escape_string( self, s, ln=None, v=False, m=False, event_type=None, no_refresh=False ):
		spns = []
		output = s.split(ESCAPE_SEQ)
		i = 0
		l = len( output )
		
		limit = self.h

		while i < l:
			try:
				output_attr = int(output[i])
			except ValueError:
				output_attr = COLOURS["plain"]
		
			try:
				output_string = output[i+1]
			except IndexError:
				output_string = output[i]
				
			i += 2 

			if not v:
				wrap = ( i == l )#output_attr == COLOURS["plain"] )
				if wrap: output_string = output_string.rstrip(" ")
				if ln:
					output_attr = COLOURS["select"]
				if ln and i == l:
					tmpy, tmpx = self.window.getyx()
				self.echo(output_string, output_attr, no_refresh=True, event_type=event_type, wrap=wrap) 
				if ln and i == l:
					tmpx = self.window.getyx()[1]
					pd = " " * ( self.w - tmpx - 2 )
					self.echo(pd, output_attr, no_refresh=True, event_type=event_type, wrap=wrap) 
			elif m:
				s = re.search( m, output_string )
				if not s:
					self.echo(output_string, output_attr, no_refresh=True, wrap=False) 
				else:
					rx = re.compile( m )
					spns = []
					while s:
						spns.append( s.span() )
						s = rx.search( output_string, s.end() )
					self.echo_search( output_string, spns, output_attr )
		if not no_refresh:
			self.window.noutrefresh()
			input_win.refresh()

		if spns: return spns
		else: return False


	def compile_escape_string( self, msg_from, attribs, string, stamp ):
		if stamp:
			if msg_from:
				ih, string = is_highlighted( string )
				if ih:
					p = COLOURS["highlight"]
				else:
					p = COLOURS["plain"]

				o = str(COLOURS["stamp"]) + \
					ESCAPE_SEQ + \
					stamp + \
					ESCAPE_SEQ + \
					str(attribs) + \
					ESCAPE_SEQ + \
					msg_from + \
					ESCAPE_SEQ + \
					str( p ) + \
					ESCAPE_SEQ + \
					string 
			else:
				o = str(COLOURS["stamp"]) + \
					ESCAPE_SEQ + \
					stamp + \
					ESCAPE_SEQ + \
					str(attribs) + \
					ESCAPE_SEQ + \
					string 
		else:
			if string:
				o = "0" + ESCAPE_SEQ + string 
			else:
				o = str( COLOURS["plain"] ) + ESCAPE_SEQ + " " 
		return o

	def insert_line( self, msg_from, attribs, string, stamp, n=0 ):
		ln = self.compile_escape_string( msg_from, attribs, string, stamp )
		self.contents.insert( n, ln )

	def add_line( self, msg_from, attribs, string, stamp ):
		ln = self.compile_escape_string( msg_from, attribs, string, stamp )
		self.contents.append( ln )

	def scroll (self, scroll_by=0, v=False, m=None):
		l = len(self.contents) + 1
	
		if self.scrolling + self.h + scroll_by >= l:
			if AWAY: return
			f = self.open_log()
			if f:
				results = read_log( f, scroll_by, buf=self )
				if not results: return None
				for r in results:
					if r.stamp: r.stamp = "" + r.stamp + ""
					self.add_line( r.frm, r.attr, r.s, r.stamp ) 
					self.scrolling = self.scrolling + 1
				ix = self.scrolling
				self.seek = f.tell()
				f.close()
			else:
				ix = l
		else:
			ix = self.scrolling + scroll_by

		return self.scroll_to( ix, v=v, m=m )


	def scroll_to( self, ix, jmp=False, hl=False, v=False, m=None, abs=False ):
		no_stop = not ( ix <= 0 )
		os = 0
		if abs and type( m ) is int: m = ix
		l = len( self.contents )
		spns = None
		if l < self.h:
			f = 0
			t = l -1
		elif ix > l:
			f = l - self.h
			t = l
		elif ix <= 0:
			no_stop = True
			f = 0
			t = self.h
		else:
			f = ix
			if ix + self.h > l: t = l -1
			else:
				t = ix + self.h
		
		self.scrolling = f

		if not hl:
			limit = self.h
		else:
			f -= self.h / 2
			if f < 0: f = 0
			limit = self.h + (self.h / 2)

		ln = None
		can_stop = True

		if type( m ) is int:
			f = l - ix -1
			t = l

			f = l - ix - 1
			t = l

#			if t - f > self.h:
#				val = t - f - self.h
#				t -= val
#				ix -= val
#			else:
#				f = self.h - ( t - f ) 
			if t - f > self.h:
				while t - f > self.h:
					ix -= 1
					t -= 1
			else:
				while t - f < self.h and f > 0:
					f -= 1
				

			can_stop = False
			no_stop = False
			limit = self.h
			jmp = False
			abs = True

			ln = ix

		new_range = self.contents[ f : t ]

		match = False
		if v and m and type( m ) is not int:
			for i, s in enumerate( new_range ):
				if re.search( m, s ):
					match = True
					break
			if match: return f + i
			else: return False

		new_range.reverse()

		first_line = True


		spns = []
		self.window.erase()
		ll = False

		for j, output in enumerate(new_range):
					
			self.echo("\n", no_refresh=True)
			if hl:
				tmp = self.echo_escape_string( output, v=True, m=hl, no_refresh=True )
				if tmp:
					spns += tmp
			elif ln == j:
				self.echo_escape_string( output, ln=True, no_refresh=True )
				can_stop = True
			else:
				self.echo_escape_string( output, no_refresh=True )
								
			tmpy, tmpx = self.window.getyx()
			if tmpy >= limit and (not jmp or abs) and not no_stop and can_stop:
				break
				
			first_line = False


		if not v or spns:
			if not AWAY and self.get_id() == current_buffer:
				self.window.noutrefresh()
				input_win.noutrefresh()
				curses.doupdate()
			elif AWAY:
				context_win.window.refresh()
		if spns: return True
		else: return False
		

class InputWindow ( irc_window ):
	def __init__ ( self ):
		irc_window.__init__( self, "input" )
		self.autocomp = False
		self.temp_buffer = []
		self.cpos = 0
		self.pcpos = 0
		self.ts = ""
		self.mch = ""
		self.cs = ""
		self.i = 0
		self.ix = 0
		self.s = ""
		self.byte_buf = ""
		self.esc = None
		self.cache = []
		self.cache_lmt = 100
		self.cache_m = []
		self.pview = False	
		self.resize()
		self.mvrel = 0

		self.window = curses.newpad( 1, 512 )

	def resize( self, no_create=True ):
		self.max_h, self.max_w = stdscr.getmaxyx()
		self.y = self.max_h - 1
		self.x = 15
		self.h = 1
		self.w = self.max_w - self.x
	
	def mk_pview ( self ):
		if PASTE.on or self.cpos:
			return

		tmpx = self.window.getyx()[ 1 ]
		if not tmpx:
			self.window.clrtoeol()
			self.refresh()
			return

		ix = len( self.s ) - self._fw()
		if tmpx == ix:
			ix = 0

		s = self.s[ ix : ]
		s_len = len( s )
		m = False
		for c in buffers[ current_buffer ].nicklist + self.cache:
			if c[ : s_len ] == s:
				m = True
				self.echo_bg( c[ s_len : ] )
				break
	
		if self.pview and not m:
			self.pview = False
			self.window.clrtoeol()
			self.refresh()
		elif m:
			self.pview = True

	def cache_add ( self, args, l=10 ):
		for i, a in enumerate( args ):

			if buffers[ current_buffer ].in_chan( a ):
				continue

			in_c = ( a in self.cache )

			if len( a ) >= l and not in_c:
					self.cache.insert( 0, a )

					c_len = len( self.cache )

					if c_len >= self.cache_lmt:
						try:
							del cache[ c_len - 1 ]
						except:
							raise_error("bobf fucked up again. Tell him I said: " + str( c_len ) + " and also: " + str( len( self.cache ) ) + " and also: " + str( self.cache_lmt ) )

			if in_c:
				self.cache.insert( 0, self.cache.pop( self.cache.index( a ) ) )


				

	def auto_complete ( self ):
		if not len( self.s ): return None
		if self.window.getyx()[ 1 ] == 0: return None

		if not self.ts and not self.s[ -self.cpos -1 ].isalnum() and self.s[ -self.cpos -1 ] not in "[]{}^_|/":
			return None

		self.autocomp = False

		if not self.ts:
			s = self.s.split(" ")
			self.ts = s[-1]
		else:
			for i in range( len( self.mch ) ): 
				self.bs( v=True )
			self.refresh()

		rx = escape_string( self.ts.lower() )

		c_len = None

		if rx[0] == "/":
			c_list = COMMAND_LIST[ self.ix : ]
			rx = rx[ 1 : ]
			x = -1
		else:
			c_list = buffers[ current_buffer ].nicklist[ : ]
			c_len = len( c_list ) - 1
			c_list += self.cache[ : ]
			c_list = c_list[ self.ix : ]
			x = 0

		m = False
		

		for i, n in enumerate ( c_list ):
			if re.search( "^" + rx, n.lower() ):
				self.ix = self.ix + i + 1#len( self.ts ) + self.ix + i 
				m = True
				break
		
		if not m:
			self.mch = ""
			self.ts = ""
			self.ix = 0
			self.autocomp = True
			return None


		self.mch = ""
		for c in n[ len( self.ts ) + x : ]:
			self.mch += c
			process_input( self, c )

		if self.ix - 1 <= c_len and len( self.s ) == len( n ):
			process_input( self, ":" )
			process_input( self, " " )
			self.mch += ": "

		self.autocomp = True
	
	def clear ( self ):
		self.erase()
		self.refresh()

	def erase ( self ):
		self.cpos = 0
		self.s = ""
		self.pcpos = 0
		self.window.erase()

	def refresh ( self ):
		self.window.refresh( 0, self.pcpos, self.y, self.x, self.y + self.h, self.x + self.w-1 )

	def noutrefresh ( self ):
		self.window.noutrefresh( 0, self.pcpos, self.y, self.x, self.y + self.h, self.x + self.w -1 )

	def cleartobol (self):
		if not self.s: return

		s = self.s[ len( self.s ) - self.cpos : ]
		self.erase()
		self.s = s
		self.addstr( s, refresh=False )
		self.mvc( len ( s ) )
		
	def feed_input ( self, key="", left=True, refresh=True ):
		if len( self.s ) == 1: return

		os = self.w / 2
		string = self.s
		if left:
			self.pcpos += os
			self.refresh()
			return

		if not left:
			self.pcpos -= os
			self.refresh()

	def insstr ( self, s, attr=None, y=None, x=None, refresh=True ):
		if attr is None: attr = COLOURS["input"]

		tmpy, tmpx = self.window.getyx()
		if y is not None or x is not None:
			if not x: x = tmpx
			if not y: y = tmpy
			self.window.insstr( y, x, s, attr )
		else:
			self.window.insstr( s, attr )

		if refresh: self.refresh()


	def addstr ( self, s, attr=None, refresh=True ):
		if attr is None: attr = COLOURS["input"]

		self.window.addstr( s, attr )
		if refresh:
			self.refresh()
		
	def echo (self, string, attribs=None, event_type=None, no_refresh=False, wrap=False):
		if attribs is None:
			attribs = COLOURS["input"]

		attribs = attribs | curses.A_BOLD

		tmpx = self.window.getyx()[ 1 ]
		tmpmx = self.window.getmaxyx()[ 1 ]
		
		if tmpx > tmpmx - 50:
			curses.flash()
			return

		y = 0
		x = 0

		if self.cpos:
			y = 0
			x = len( self.s ) - self.cpos
			self.s = self.s[ 0 : len( self.s ) - self.cpos ] + string + self.s[ len( self.s ) - self.cpos : ]
			self.insstr( string, attribs, y, x )
			self.window.move( y, x + 1 )

		else:
			tmpx = self.window.getyx()[1]
			if tmpx >= self.w + self.pcpos - 1:
				self.feed_input( string )
			self.addstr( string, attribs )
			self.s += string
			

		self.refresh()


	def echo_bg ( self, s, attribs=None, no_refresh=False ):
		if attribs is None:
			attribs = COLOURS["input"]

		if self.cpos:
			return 

		tmpy, tmpx = self.window.getyx()
		self.addstr( s, attr=attribs, refresh=not no_refresh )
		self.window.move( tmpy, tmpx )
		if not no_refresh:
			self.refresh()
		
		
	def delete ( self, v=False ):
		if not len( self.s ): return

		if self.mvc( -1 ):
			self.bs( v=v )

	def _fw ( self, bw=True ):
		y, x = self.window.getyx()

		i = 0
		l = len( self.s )

		if bw:
			d = -1
			os = self.cpos
		else:
			d = 1
			os = x

		while i < l:
			ix = ( d * i ) + ( d * os ) 
			if d * ix < l and not self.s[ ix ].isalnum() and i > 0:
				break
			i += 1

		if not i: return x

		return i


	def delw ( self ):
		if not len( self.s ): return

		for j in range( self._fw( bw=False ) ): self.delete( v=True )
		self.refresh()
		
	def bs ( self, v=False ):
		tmpy, tmpx = self.window.getyx()
		if tmpx <= self.pcpos: self.feed_input( left=False )
		

		if tmpx >= 1 and self.cpos:
			self.s = self.s[ 0 : len( self.s ) - self.cpos - 1] + self.s[ len( self.s ) - self.cpos : ]
		if tmpx >= 1 and not self.cpos:
			self.s = self.s[:-1]

		if tmpx >= 1:
			self.window.delch( tmpy, tmpx - 1 )
			if not v: self.refresh()

		self.mk_pview()

		
	def bsw ( self ):
		tmpy, tmpx = self.window.getyx()
		if not tmpx > 0: return

		for j in range( self._fw() ): self.bs( v=True )
		self.refresh()


	def mvw ( self, bw=True ):
		if bw: ix = 1
		else: ix = -1

		for i in range( self._fw( bw ) ):
			self.mvc( ix )
		return

	def mvc ( self, lb, v=False ):
		if lb < 0 and self.cpos == 0:
			return None
		if lb > 0 and self.cpos == len( self.s ):
			return None
		
		if self.pview:
			self.pview = False
			self.window.clrtoeol()
			self.refresh()

		self.cpos += lb	
		tmpy, tmpx = self.window.getyx()
		tmpx = len( self.s ) - self.cpos
		self.window.move( tmpy, tmpx )

		left = ( tmpx > self.pcpos )
		if tmpx < self.pcpos: left = False
		elif tmpx > self.pcpos + self.w: left = True
		else:
			if not v: self.refresh()
			return True

		while not ( self.pcpos <= tmpx <= self.pcpos + self.w ):
			self.feed_input( left=left )

		if not v: self.refresh()
		return True



class MessageWindow( irc_window ):
	def __init__ ( self ):
		irc_window.__init__( self, "input" )
		
		self.y = self.max_h - 1
		self.x = 15
		self.h = 1
		self.w = self.max_w - self.x
	
		self.window = curses.newwin( self.h, self.w, self.y, self.x )
	
	def echo( self, s, attr=None ):
		if attr is None: attr = COLOURS["system"]
		self.window.erase()
		s = s.center( self.w - self.x )
		self._echo_bold( s, attr )
		self.window.redrawwin()
		self.window.refresh()
	
	
# Event handlers:

def _on_connect (connection, event):
	global TIMER_QUEUE

	connection.notified = False
	if connection.attempts:
		system_write( 'Connection re-established after [' + str( connection.attempts ) + '] attempts.' )
	connection.attempts = 0

	ping_server( connection )

	if PASS:
		irc_process_command(connection, "whois", ["nickserv"])

	if len(AUTOJOIN_LIST):
		connection.need_autojoin = True
	
	if not connection.live:
		connection.live = True
	
	TIMER_QUEUE = queue_clear( TIMER_QUEUE, irc_process_command, connection, "server", None )
	

def _on_privmsg (connection, event):
	global NICK
	src = birclib.nm_to_n(event.source())
	s = event.arguments()[0]

	ignored = is_ignored( src, s )

	if event.target().lower() == NICK.lower() and not ignored:
		if not src.lower() in buffers.keys():
			buffers[current_buffer].write( src, s, "msg_to_me" )
		else:
			if src.lower() != current_buffer: buffers[src.lower()].has_unread_to_me = True
			buffers[src.lower()].write(src, s, event.eventtype())
	elif event.target().lower() in buffers.keys():
		buffers[event.target().lower()].write(src, s, event.eventtype(), log_only=ignored)

def _on_pubmsg (connection, event):
	_on_privmsg(connection, event)


def _on_action (connection, event):
	_on_privmsg (connection, event)


def _on_privnotice(connection, event):
	s = event.arguments()[0] 
	if event.source():
		src = birclib.nm_to_n( event.source() )
		buffer = current_buffer
		event_type = event.eventtype()
	else:
		src = s
		s = ""
		buffer = MAIN_WINDOW_NAME
		event_type = "servernotice"

	ignored = is_ignored( src )
	buffers[buffer].write(src, s, event_type, log_only=ignored)
	if ignored: return
	if not current_buffer == buffer:
		buffers[buffer].has_unread = True
		buffers[buffer].has_unread_to_me = True


def _on_pubnotice(connection, event):
	s = event.arguments()[0] 
	if event.source():
		src = birclib.nm_to_n( event.source() )
		buffer = current_buffer
		event_type = event.eventtype()
	else:
		src = s
		s = ""
		buffer = MAIN_WINDOW_NAME
		event_type = "servernotice"

	buffers[buffer].write(src, s, event_type, is_ignored( src ) )
	s = event.arguments()[0] 


def _on_join (connection, event):
	global NICK

	src = birclib.nm_to_n(event.source())
	targ = event.target().lower()

	if src.lower() == NICK.lower():
		buffers[targ] = irc_window("main")
		buffers[targ].has_unread = True
		buffers[targ].has_unread_events = True
		max_y = stdscr.getmaxyx()[0]
		buffers[targ].scroll(max_y)
		buffers[targ].scroll_to(0)

	if targ in WATCH_LIST:
		notice( [targ + ":", src, "has joined."], src, COLOURS["online"] )
	elif src.lower() in BUDDY_LIST:
		notice( ["Buddy joined:", src.lower(), targ], src.lower(), COLOURS["online"])

	if not is_ignored( src ) and src.lower() != NICK.lower():
		buffers[targ].write( mk_full_nick( event.source() ), "", event.eventtype())

	if src[0] in ["@", "+"]: src = src[1:]

	if src.lower() != NICK.lower():
		buffers[targ].nicklist.append(src)
		buffers[targ]._ncols[ src ] = mkncol( src )
		

	buffers[targ].nicklist.sort( key=str.lower )
	


def _on_part (connection, event):
	targ = event.target().lower()
	src = birclib.nm_to_n(event.source())

	if targ in WATCH_LIST:
		notice( [targ + ":", src, "has left."], src, COLOURS["offline"] )
	elif src.lower() in BUDDY_LIST:
		notice( ["Buddy left:", src.lower(), targ], src.lower(), COLOURS["offline"])

	if not is_ignored( src ):
		buffers[targ].write( mk_full_nick( event.source() ), "", event.eventtype())


	buffers[targ].nicklist.pop( buffers[targ].nicklist.index(src) )


	if birclib.nm_to_n(event.source()) == NICK:
		buffers[targ].has_unread = False
		if targ == current_buffer: buffer_switch("next")
		del buffers[targ]

def _on_kick (connection, event):
	chan = event.target()
	targ = event.arguments()[0]
	src = birclib.nm_to_n(event.source())

	if targ.lower() in WATCH_LIST:
		notice( [targ + ":", chan, "was kicked."], chan, COLOURS["offline"] )
	elif targ.lower() in BUDDY_LIST:
		notice( ["Buddy was kicked:", src.lower(), targ], src.lower(), COLOURS["offline"])

	chan = chan.lower()

	if not is_ignored( src ):
		buffers[chan].write( targ, src, event.eventtype())

	buffers[chan].nicklist.pop( buffers[chan].nicklist.index(targ) )

	if birclib.nm_to_n(targ).lower() == NICK.lower():
		buffers[chan].has_unread = False
		system_write("You were kicked from " + chan + " by " + src + "")

		if chan == current_buffer: buffer_switch(MAIN_WINDOW_NAME)
		else: buffer_switch()
		del buffers[chan]

		if AUTO_REJOIN:
			irc_process_command(connection, "join", [chan])	
	  

def _on_quit (connection, event):
	src = birclib.nm_to_n(event.source())
	
	notified = False

	if src.lower() in BUDDY_LIST:
		notice( ["Buddy quit:", src.lower()], src.lower(), COLOURS["offline"])
		notified = True

	for buffer in buffers.keys():
		if src in buffers[buffer].nicklist:
			buffers[buffer].nicklist.pop ( buffers[buffer].nicklist.index(src) )
			if buffer in WATCH_LIST and not notified:
				notice( [buffer + ":", src, "has quit."], src, COLOURS["offline"] )
				notified = True
			#if not src in IGNORE:
			if not is_ignored( src ):
				buffers[buffer].write( mk_full_nick( event.source() ), event.arguments()[0], event.eventtype())


def _on_namreply (connection, event):
	nam_list = event.arguments()[2].split(" ")[:-1]
	for i in range(0, len(nam_list)):
		if nam_list[i][0] in ["@", "+"]: nam_list[i] = nam_list[i][1:]

	buffers[ event.arguments()[1].lower() ].nicklist += nam_list
 

def _on_endofnames (connection, event):
	buffer = event.arguments()[0]

	if event.arguments()[0] in buffers.keys():
		buffers[ buffer ].nicklist.sort( key=str.lower )
		buffers[buffer].write_time()
		#irc_process_command( connection, "names", [buffer] + buffers[buffer].nicklist )
		show_list( "Users in channel " + buffer + ":", buffers[buffer].nicklist, "User list truncated. Use /allnames to see a full list.", buffer )

def _on_forwardtochannel (connection, event):
	buffers[MAIN_WINDOW_NAME].write("Channel " + event.arguments()[0] + " forwarded to " + event.arguments()[1], "",  "servernotice")
	buffer_switch()
	
def _on_currenttopic (connection, event):
	irc_topic_change( buffers[ event.arguments()[0].lower() ], event.arguments()[1] )

def _on_topic (connection, event):
	irc_topic_change( buffers[ event.target().lower() ], event.arguments()[0], birclib.nm_to_n(event.source()) )

def _on_topicinfo( con, evt ):
	d = time.strftime( "%x", time.localtime( int( evt.arguments()[ 2 ] ) ) )
	t = time.strftime( "%X", time.localtime( int( evt.arguments()[ 2 ] ) ) )

	o = "\n\tTopic set by: " + evt.arguments()[ 1 ] + " at " + t + " on the " + d + "\n"
	ch = evt.arguments()[0].lower()

	if ch in buffers.keys():
		buffers[ ch ].echo( "\n" + ch + " topic:\n\t[ " + buffers[ ch ].topic_raw + " ]\n", COLOURS["system"], wrap=True )
		buffers[ ch ].echo( o, COLOURS["system"] )

def _on_nick (connection, event):
	global NICK
	global current_buffer
	
	src = birclib.nm_to_n(event.source() )
	targ = event.target()

	if src.lower() == NICK.lower():
		NICK = targ

		for buffer in buffers:
			buffers[buffer].stop_logging()

	need_refresh = False

	for key in buffers.keys():
		if src in buffers[key].nicklist:
			buffers[key].nicklist[ buffers[key].nicklist.index(src) ] = targ
			buffers[key].nicklist.sort()
			buffers[key].write(src, targ, "nick")

		if src == key:
			need_refresh = True
			buffers[targ] = buffers.pop(key)
			buffers[targ].write(src, targ, "nick")

	if src == current_buffer:
		current_buffer = targ
	if need_refresh: update_info()

def _on_nicknameinuse (connection, event):
	global NICK
	new_nick = NICK + str( int( random.random()*100 ) )

	raise_error( "Nickname " + NICK + " in use, using " + new_nick + "" )
	NICK = new_nick
	irc_process_command( connection, "nick", [new_nick] )
	
def _on_whois (connection, event):
	compile_whois(event.arguments(), event.eventtype(), connection)

def _on_ping (connection, event):
	connection.ping( event.arguments()[0] )

def _on_pong (connection, event):
	global TIMER_QUEUE
	connection.lag = time.time() - PING_TIME
	TIMER_QUEUE = queue_unique( TIMER_QUEUE, 2, ping_server, connection )
	update_status( connection.lag )
	
def _on_ctcp (connection, event):
	args = event.arguments()
	src = birclib.nm_to_n( event.source() )
	
	if args[0] == "VERSION":
		irc_process_command( connection, "_version", [src] )
	
	elif args[0] == "PING":
		irc_process_command( connection, "_pong", [ src, event.arguments()[ 1 ] ] )
	
	
def _on_ctcpreply (connection, event):
	args = event.arguments()

	if args[0] == "PING":
		secs = time.time() - float( event.arguments()[ 1 ] )
		secs = "%.02f" % secs
		system_write( "Ping reply from " + birclib.nm_to_n( event.source() ) + " took " + secs + " seconds." )
	
def _on_nickerror (connection, event):
	global NICK
	raise_error( "Erroneus nickname: " + event.arguments()[ 0 ] + ". Using bfirc-user." )
	NICK = "bfirc-user"
	irc_process_command( connection, "nick", [NICK] )

def _on_nosuchnick (connection, event):
	raise_error(event.arguments()[1] + ': ' + event.arguments()[0] + '', current_buffer )

def _on_cannotsendtochan( connection, event ):
	raise_error( event.arguments()[ 1 ] + ': ' + event.arguments()[ 0 ] + '', current_buffer )

def _on_mode( connection, event ):
	targ = event.target().lower()
	if not targ in buffers.keys():
		targ = None
	if len( event.arguments() ) == 2:
		suf = ' to ' + event.arguments()[ 1 ] + ''
	else:
		suf = ''

	system_write( '' + birclib.nm_to_n( event.source() ) + ' sets mode [' + event.arguments()[0] + ']' + suf, targ )

def _on_umode( connection, event ):
	targ = ' to ' + event.target() + ''
	src = birclib.nm_to_n( event.source() )
	if targ == src:
		targ = ''

	if event.target().lower() == NICK.lower() and event.arguments()[0] == '+e' and connection.need_autojoin:
		connection.need_autojoin = False
		irc_process_command(connection, "join", AUTOJOIN_LIST)
	system_write( '' + src + ' sets umode [' + event.arguments()[0] + ']' + targ, MAIN_WINDOW_NAME )
	
def debug_event (connection, event):
	system_write("\nEvent Type: " + str(event.eventtype()) + "\nSource: " + str(event.source()) + "\nTarget: " + str(event.target()) + "\nArguments: " + str(event.arguments()) )

# Internal IRC-related functions:


def is_highlighted ( s ):
	h = False
	for m in WATCH_WORDS + [ NICK ]:
		if re.search("^"+m+"\W|\W"+m+"\W|\W"+m+"$|^"+m+"$", s):
			s = s.replace( m, '' + m + '' )
			h = True
			#break
	return h, s

def is_ignored ( src, msg=None ):
	ignored = False

	if src.lower() in IGNORE: ignored = True
	
	if msg is None:
		return ignored

	for ignoreto in IGNORE_TO:
		if re.search("^" + ignoreto + "\W" , msg): ignored = True

	return ignored

def mk_full_nick ( s ):
	n = birclib.nm_to_n ( s )
	i = " [ " + s.split( "!", 1 )[1] + " ]"
	return n + i

def compile_whois (args, type, connection):
	user = args[0].lower()
	if not user in whois_buffer.keys(): whois_buffer[ user ] = whois_struct()

	if type == "whoisuser":
		whois_buffer[ user ].user = args
		
	elif type == "whoischannels":
		whois_buffer[ user ].channels = args[1:]

	elif type == "whoisserver":
		whois_buffer[ user ].server = args[1:]

	elif type == "endofwhois":
		f = buffers[current_buffer].echo
		w = whois_buffer.pop(user)
		a = COLOURS["system"]
		if not len( w.user ):
			return	
		if w.user[0] == "NickServ":
			if w.user[1] == "NickServ" and w.user[2] == "services." and w.user[4] == "Nickname Services":
				system_write( "Sending password. NickServ authenticated as:" )
				irc_process_command(connection, "id", [PASS])
#				if connection.need_autojoin:
#					irc_process_command(connection, "join", AUTOJOIN_LIST)
#					connection.need_autojoin = False
			else:
				system_write( "NickServ could not be authenticated. Not sending password." )
				return False
		f("\n	Whois     :" + w.user[0] + " [" + w.user[1] + "@" + w.user[2] + "]", a, no_refresh=True)
		f("\n	IRC Name  :" + w.user[4], a, no_refresh=True)
		if w.channels:
			f("\n	Channels  :" + ":".join(w.channels[0].split(" ")), a, no_refresh=True)
		if w.server:
			if len(w.server) == 2: server = w.server[1]
		f("\n	Server    :" + w.server[0] + " [" + (server or "") + "]", a, no_refresh=True)

		f("\nEnd of Whois", a)


def irc_process_command (connection, command, args):
	global NICK
	global REALNAME
	global PORT
	global SERVER
	global PING_TIME
	global SHOW_URL_LIST

	if command in ALIASES:
		command = ALIASES[ command ]

	buf = current_buffer
	command = command.lower()
	if type(args) == str: args = args.split( " " )

	override = False
	for h in _INPUT_HOOKS:
		if h[ 0 ] == "_" + command:
			try:
				connection, buf, command, args = h[ 1 ]( connection, current_buffer, command, args )
				override = True
			except:
				raise_error( "Error in hook handler for " + command + ":\n" + traceback.format_exc(0) )


	v_cmds = [ "server", "url", "urls", "quit", "buddy", "close", "open", "set", "_stack", "loadrc", "connect", "alias" ]

	if not command in v_cmds and not connection.connected:
		if connection.live:
			connection.live = False
			discon( connection )
		elif command != "_pingserver":
			system_write('Not connected to server.', current_buffer)
		return
	else:
		if command == "quit" and not connection.connected:
			command = "_quit"

	try:
		if command == "server":
			SERVER = args[0]
			if len(args) >= 2: PORT = args[1]
			connection.connect(SERVER, PORT, NICK, ircname=REALNAME)

		elif command == "connect":
			if not len( args ):
				return

			s = args[ 0 ]
			tmp = s.split('.')
			if len( tmp ) >= 2:
				n = tmp[ -2 ]
			else:
				n = s

			add_conn( n, s )
			
		elif command == "loadrc":
			if args: path = args[ 0 ]
			else: path = None
			
			load_rc( path=path, ft=False )

		elif command == "umode":
			if not len( args ):
				system_write( "umode: Must specify mode(s)." )
				return

			connection.mode( NICK, args[ 0 ] )

		elif command == "quote":
			if not len( args ):
				system_write( "quote: Must specify argument(s)." )
				return

			connection.send_raw( " ".join( args ) )

		elif command == "raw":
			if not len( args ):
				system_write( "raw: Must specify argument(s)." )
				return

			connection.send_raw( " ".join( args ) )

	
		elif command == "pass":
			if not len( args ):
				system_write( "pass: Must specify argument." )
				return

			connection.pass_( args[ 0 ] )

		elif command == "ping":
			if not len( args ):
				system_write( "Ping: Must specify a user." )
				return

			connection.ctcp( "PING", args[ 0 ], str( time.time() ) )

		elif command == "_pong":
			connection.ctcp_reply( args[ 0 ], "PING " + args[ 1 ] )
		
		elif command == "_st":
			buffers[buf].scroll_to( int( args[0] ) )

		elif command == 'alias':
			if len( args ) != 2:
				system_write( 'Usage: /alias <alias> <command>' )
				return
	
			ALIASES[ args[ 0 ] ] = args[ 1 ]

		elif command == "url":
			if not URL_ACTION:
				raise_error("No URL action specified in rc file.")
				return
			if not URL:
				raise_error("No URL in cache.")

			if not "%s" in URL_ACTION:
				cmd = URL_ACTION + " " + URL
			else:
				cmd = URL_ACTION % URL
				
			r = os.system( cmd )
			if not r:
				system_write("System command: " + cmd + " successful.")
			else:
				system_write("System command " + cmd + " returned: Error " + str( r ) + "")

		elif command == "urls":
			if not URL_LIST:
				raise_error("No URLs in stack.")
				return
			list_win.contents = []
			for url in URL_LIST:
				list_win.contents.append( url )

			list_win.contents = make_option_list( list_win.contents )
			for i, t in enumerate( list_win.contents ):
				list_win.contents[ i ] = t.replace("http://www.", "")
				list_win.contents[ i ] = t.replace("http://", "")

			show_list_win ( list_win, no_anim=True )	
			SHOW_URL_LIST = True

		elif command == "_stack":
			system_write( str( TIMER_QUEUE ) )

		elif command == "_pingserver":
			connection.ping( connection.server + " 2132109321 20139031 9021" )
			PING_TIME = time.time()

		elif command == "_version":
			system_write( "" + args[0] + " requested CTCP VERSION" )
			connection.ctcp_reply( args[0], 'VERSION ' + PROGRAM_NAME  + ' by Bob Farrell 2007-2008.' )

		elif command == "whois":
			if not args: return
			connection.whois(args)

		elif command == "addtopic":
			irc_add_topic( connection, buf, " ".join(args) )

		elif command == "nick":
			connection.nick(args[0])
				
		elif command == "topic":
			if not args and birclib.is_channel(buf):
				buffers[buf].echo( "\n" + buf + " topic:\n\t[ " + buffers[buf].topic_raw + " ]\n", COLOURS["system"], wrap=True )
			elif birclib.is_channel( buf ):
				connection.topic( buf, " ".join( args ) )
		  
		elif command == "allnames":
			if not len( args ): args = [buf]
			if birclib.is_channel(args[0]):
				show_list( "Users in channel " + args[0] + ":", buffers[args[0]].nicklist, extend=True)

		elif command == "watch":
			if not args: args = [buf]
			for arg in args:
				irc_watch_channel(arg)

		elif command == "buddy":
			irc_add_buddy( args[0] )

		elif command == "names":
			if not len( args ):
				args = [buf]
				buffer = current_buffer
			elif not args[0].lower() in buffers.keys():
				return
			else:
				buffer = current_buffer

			if birclib.is_channel(args[0]):
				show_list( "Users in channel " + args[0] + ":", buffers[args[0]].nicklist, "User list truncated. Use /allnames to see a full list.", buffer )

		elif command == "ignore":
			if not args:
				show_list("Ignored users:", IGNORE)
			else:
				irc_ignore( args[0] )

		elif command == "ignoreto":
			if not args:
				show_list("Completely ignored users:", IGNORE_TO)
			else:
				irc_ignoreto( args[0] )

		elif command == "kick":
			l = len( args )

			if not l:
				system_write("Must specify a user to kick.")
				return
			elif l == 1:
				connection.kick( current_buffer, args[0] )
			elif l == 2:
				connection.kick( args[ 0 ], args[ 1 ] )
			elif l >= 3:
				connection.kick( args[ 0 ], args[ 1 ], " ".join( args[ 2 : ] ) )

		elif command == "quit":
			if not args: args = [QUIT_MESSAGE]
			connection.quit( " ".join(args) )
			connection.disconnect()
			exit_program()

		elif command == "_quit":
			exit_program() 

		elif command == "join":
			for chan in args:
				chan = chan.lower()
				# if chan not in buffers.keys():

				# ^^ This was messing up the reconnect crap
				# it's not necessarily a permanent fix but I don't think there's anything
				# wrong with sending the server a JOIN request for an already joined channel;
				# it shouldn't break anything.

				connection.join(chan)

		elif command == "part":
			if not args: args = buf
			else: args = args[0].lower()
			if args in buffers.keys() and birclib.is_channel(args):
				buffers[args].stop_logging()
				connection.part(args)

		elif command == "close":
			if not args: args = buf
			else:
				args = args[0].lower()

			if birclib.is_channel(args):
				irc_process_command(connection, "part", args)
			elif args in buffers.keys() and args != MAIN_WINDOW_NAME:
				if args == buf: buffer_switch("next")
				buffers[args].stop_logging()
				del buffers[args]

		elif command == "open":
			user = args[0].lower()
			if len(args) > 1:
				msg = " ".join(args[1:])
			else: msg = None

			if not birclib.nm_to_n(user) in buffers.keys():
				buffer = user.lower()
				buffers[buffer] = irc_window("main")
				buffers[ buffer ]._ncols[ buffer ] = mkncol( buffer )
				max_y = stdscr.getmaxyx()[0]
				#for i in range(50):
				buffers[buffer].scroll(50)
				buffers[buffer].scroll_to(0)
				buffers[buffer].write_time()
			buffer_switch( user )

			if msg:
				connection.privmsg(birclib.nm_to_n(user), msg)
				buffers[user.lower()].write(NICK, msg, "me_msg")
		
		elif command == "msg":
			user = args[0]
			msg = " ".join( args[1:] )
			connection.privmsg( birclib.nm_to_n(user), msg )
			buffer = user.lower()
			if not buffer in buffers.keys():
				buffers[buf].write( user, msg, "msg_from_me" )
			else:
				buffers[buffer].write( user, msg, "me_msg" )

		elif command == "say":
			text = " ".join(args)
			connection.privmsg(buf, text)
			buffers[buf].write(NICK, text, "me_say") 
			input_win.cache_add( args )

		elif command == "me":
			connection.action(buf, " ".join(args))
			text = " ".join(args)
			buffers[buf].write(NICK, text, "me_action")

		elif command in  ["id", "identify"]:
			connection.privmsg("nickserv", "identify " + args[0])

		elif command == "set":
			set_option(args[0:])

		elif command == "away":
			set_away()

		else:
			if command and not override:
				system_write("Unrecognised command: " + command + "")
	except birclib.ServerConnectionError:
		discon( connection )

def irc_add_topic ( conn, buffer, s ):
	conn.topic( buffer, s + buffers[buffer].topic_raw )
		
def irc_topic_change (buffer, topic, src=None):
	buffer.topic_raw = topic

	if len(topic) < buffer.w:
		topic = topic.center( buffer.w )

	buffer.topic = topic
	buffer.scrolling = 0

	if buffers.values()[buffers.values().index(buffer)] == buffers[current_buffer]:
		topic_win.window.erase()
		topic_win.echo( topic[:buffer.w-1], COLOURS["topic"] )

	if src:
		buffer.write(src, buffer.topic_raw, "topic")

def irc_ignore (user):
	if not user.lower() in IGNORE:
		IGNORE.append( user.lower() )


def irc_ignoreto (user):
	if not user.lower() in IGNORE_TO:
		IGNORE_TO.append( user.lower() )
	irc_ignore(user)

def irc_add_buddy (user):
	if not user.lower() in BUDDY_LIST:
		BUDDY_LIST.append( user.lower() )


def irc_watch_channel (chan):
	if birclib.is_channel(chan):
		if not chan.lower() in WATCH_LIST:
			WATCH_LIST.append( chan.lower() )


def ping_server (connection):
	irc_process_command( connection, "_pingserver", [] )

# Internal "other" functions:
	
def add_con( n, s ):
	connections[ n ] = irc.server()
	connections[ n ].connect( s, PORT, NICK, ircname=REALNAME )

def mkncol( s ):
	if not NICK_COLS: return COLOURS["themtalk"]

	return _mkncol( s )

def get_log_prefix( event ):
	for i in range( len( EVENTS ) ):
		if event == EVENTS[i][0]:
			return EVENTS[i][1]
	return False

def get_event_from_prefix( prefix ):
	for i in range( len( EVENTS ) ):
		if prefix == EVENTS[i][1]:
			return EVENTS[i]
	return False

def clear_unread ():
	for key in buffers.keys():
		buffers[key].has_unread = buffers[key].has_unread_to_me = buffers[key].has_unread_messages = buffers[key].has_unread_events = False
	buffer_switch()

def utf8 (string):
	string = unicode(string.encode("utf8"), "utf8")
	return string

def set_away ():
	global AWAY
	AWAY = not AWAY

	if AWAY:
		#curses.curs_set(0)
		away_win.selected = -1
		away_win.contents = []
		away_win.marks = []
		context_win.contents = []
		context_win.window.erase()
		away_win.window.redrawwin()
		away_win.window.noutrefresh()
	#	context_win.window.redrawwin()
		context_win.window.noutrefresh()
		sep_win.window.hline( 0, 0, curses.ACS_HLINE, sep_win.w )
		sep_win.window.redrawwin()
		sep_win.window.noutrefresh()
		away_win.window.refresh()

		input_win.window.erase()
		input_win.noutrefresh()
		info_win.window.erase()
		info_win.window.noutrefresh()
		topic_win.window.erase()
		topic_win.window.noutrefresh()
		status_win.window.erase()
		status_win.window.hline(curses.ACS_HLINE, status_win.w)
		status_win.window.noutrefresh()
		input_win._echo_bold("Away mode is on, press b to return.", COLOURS["system"])
		curses.curs_set(0)


	else:
		curses.curs_set(1)
		away_win.window.erase()
		input_win.window.erase()
		input_win.noutrefresh()
		away_win.window.noutrefresh()
		input_win.s = ""
		buffer_switch(current_buffer)
	
	
def set_option (args):
	global SCROLL_TOPIC
  
	option = args[0].upper()
	
	params = parseopt.parse_options(args[1:], True)
	if not params:
		t = args[0].split("=")
		option = t[0].upper()
		params = t[1]

	if re.search("DECOR", option):
		pre = suf = None

		if option == "ME_DECOR":
			me_decor.set(pre, suf)
		if option == "ME_ACTION_DECOR":
			me_action_decor.set(pre, suf)
		if option == "THEM_DECOR":
			them_decor.set(pre, suf)
		if option == "THEM_ACTION_DECOR":
			them_action_decor.set(pre, suf)

	if option == "SCROLL_TOPIC":
		SCROLL_TOPIC = yes_no( params )
	

def show_list ( title, items, extend="List truncated.", buffer=None ):
	if not buffer: buffer = current_buffer

	if type(extend) == str:
		truncate_message = extend
		extend = False
	elif type(extend) == bool and not extend:
		truncate_message = "List truncated."

	s = ""
	length = 0
	buffers[buffer].echo("\n" + title + "\n	", COLOURS["system"])
	for i in items:
		if len(i) > length: length = len(i)
	
	lines = 0
	
	for i in items:
		tmpy, tmpx = buffers[buffer].window.getyx()
		if lines + 4 >= buffers[buffer].h:
			if extend:
				buffers[buffer].echo("\nPress \"c\" to continue or \"x\" to cancel.\n	")
				c = wait_for_key(["c", "x"])
				if c == "c":
					lines = 0
				elif c == "x":
					buffers[buffer].echo("\nCanceled.")
					break
		 
			else:
				buffers[buffer].echo("\n" + truncate_message)
				break
		if tmpx + length + 7 >= buffers[buffer].w:
			buffers [buffer].echo("\n	", no_refresh=True)
			lines += 1
		
		buffers[buffer].echo( system_decor.prefix, COLOURS["system"], no_refresh=True)
		buffers[buffer].echo( i.center(length), curses.A_BOLD | COLOURS["system"], no_refresh=True)
		buffers[buffer].echo( system_decor.suffix, COLOURS["system"] , no_refresh=True)

	buffers[buffer].echo("\n")


def raise_error (s, buffer=MAIN_WINDOW_NAME):
	buffers[buffer].write ( PROGRAM_NAME, s, "error" )

def system_write (s, buffer=None):
	if buffer is None:
		buffer = MAIN_WINDOW_NAME

	buffers[buffer].write(PROGRAM_NAME, s, "systemwrap")

def debug_echo (s, buffer=MAIN_WINDOW_NAME):
	if type( s ) is not str:
		s = str( s )
	buffers[buffer].echo( "\nDEBUG: " + s, _COLOURS["RED"] )

def ask_question (q, k=None):
	curses.curs_set( 0 )
	message_win.echo(q) 
	r = wait_for_key(k)
	input_win.refresh()
	curses.curs_set( 1 )
	update_info()
	return r

def ask_yes_no (q):
	if ask_question (q + " (y/n)", ["y", "Y", "n", "N"]) in ["y", "Y"]:
		return True
	else:
		return False

def load_rc (path=None, ft=True):
	global NICK
	global PORT
	global LOGS_DIR
	global NICK_COLS
	global COLOURS
	global EVENTS
	global SYS_COLOURS
	global INPUT_HOOKS
	global HOOKS
	global _INPUT_HOOKS
	global OUTPUT_HOOKS
	global _OUTPUT_HOOKS
	global SERVER, PORT, NICK, REALNAME, PASS, LOG_ID, \
			SCROLL_TOPIC, AUTO_REJOIN, URL_ACTION, \
			AUTOJOIN_LIST, BUDDY_LIST, IGNORE, \
			IGNORE_TO, QUIT_MESSAGE, WATCH_LIST, \
			WATCHWORDS, NICK_COLS, LOGGING, LOGS_DIR, \
			SYS_COLOURS, INPUT_HOOKS, OUTPUT_HOOKS, \
			SHOW_EVENTS

	
	if not path:
		path = RC_PATH
	
	if not path:
		raise_error("Cannot find rc file, please create ~/.bfircrc or specify as an argument on the command line.")

	try:
		f = open(path, "r")
	except IOError:
		raise_error("IOError: Couldn't load rc file: " + path + "")
		return

	f.close()
	
	tmp = NICK


	try:
		execfile( path, globals() )
	except:
		raise_error( "Error in rc file " + path + ":\n" + traceback.format_exc(0) )
	
	INPUT_HOOKS = map( lambda x: ("_" + x[0], x[1]), INPUT_HOOKS )
	_INPUT_HOOKS = INPUT_HOOKS[ : ]

	_OUTPUT_HOOKS = OUTPUT_HOOKS[ : ]

	SYS_COLOURS["systemwrap"] = SYS_COLOURS["system"]
	COLOURS = make_colours( SYS_COLOURS )
	EVENTS = make_events()

	buffer_switch()

	bfirclog_update( COLOURS )

	if not ft:
		NICK = tmp

	PORT = int(PORT)

	if NICK_COLS: NICK_COLS = True
	else: NICK_COLS = False


	if not LOGS_DIR[-1] == "/": LOGS_DIR += "/"
	if "~" == LOGS_DIR[0]:
		LOGS_DIR = os.path.expanduser("~") + LOGS_DIR[ 1 : ]

	system_write( "Loaded RC file: " + path )

def yes_no ( string ):
	if "YES" in string.upper():
		return True
	if "NO" in string.upper():
		return False

def exit_program ():
	for key in buffers.keys():
		buffers[key].stop_logging()
	curses.endwin()
	print "Bye!"
	sys.exit(0)

def update_info (buffer=None):
	s = current_buffer

	if not birclib.is_channel(s) and s != MAIN_WINDOW_NAME: s = birclib.nm_to_n(s)

	s = "[" + s[0:9] + "]"
	info_win.window.erase()
	info_win.echo(s, COLOURS["info"], no_refresh=True)

	tmpy, tmpx = info_win.window.getyx()
	info_win.window.attrset(COLOURS["metalk"])
	info_win.window.hline(tmpy, tmpx, curses.ACS_HLINE, info_win.w - tmpx - 0)
 
	info_win.window.redrawwin()
	info_win.window.noutrefresh()

	status_win.window.erase()

	s = ""

def update_sepwin ( c=None, s=None ):
	sep_win.window.erase()

	if s is None and c is None:
		sep_win.window.hline( 0, 0, curses.ACS_HLINE, sep_win.w )
		sep_win.window.refresh()
		return
	
	if s and c is None:
		sep_win.window.hline( 0, 0, curses.ACS_HLINE, sep_win.w )
		sep_win.window.refresh()
		return

	if s is None and c:
		o = "" + str( c ) + " Message"
		if c > 1: o += "s"
	
	elif s and c:
		o = "Message " + str( s ) + "/" + str( c ) + "" 

	sep_win.echo( "[", COLOURS["info"] )
	sep_win.echo( o, COLOURS["system"] )
	sep_win.echo( "]", COLOURS["info"] )
	l = len( o ) - o.count( '' ) + 2
	sep_win.window.hline( 0, l, curses.ACS_HLINE, sep_win.w - l )
	sep_win.window.refresh()

def update_status (lag=None, no_refresh=False, msg=None):
	s = None

	status_win.window.erase()
	_skeys = dsorted( buffers.keys() )
	for key in _skeys:
		if buffers[key].has_unread:
			
			if buffers[key].has_unread_events:
				attr = curses.A_BOLD | COLOURS["meact"]

			if buffers[key].has_unread_messages:
				attr = curses.A_BOLD | COLOURS["metalk"]

			if buffers[key].has_unread_to_me:
				attr = curses.A_BOLD | COLOURS["themtalk"]

			s = key 
			tmpy, tmpx = status_win.window.getyx()
			if not tmpx + len(s) + 2 >= status_win.w:
				status_win.echo("|", curses.A_BOLD | COLOURS["info"], no_refresh=True)
				status_win.echo(s, attr, no_refresh=True)
	if s: status_win.echo("|", curses.A_BOLD | COLOURS["info"], no_refresh=True)

	tmpy, tmpx = status_win.window.getyx()
	for i in range(0, status_win.w - tmpx):
		status_win.window.insch(tmpy, 0, " ")
	status_win.window.hline( tmpy, 0, curses.ACS_HLINE, status_win.w - tmpx )

	if not msg and connections[0].connected:
		if lag:
			status_win.lag = lag
		else:
			lag = status_win.lag
		
		if lag <= float(TIMEOUT) / 1000.0:
			lt = "<"
		else: lt = " "

		if lag < 1.0:
			attribs = _COLOURS["GREEN"]
		elif lag < 2.0:
			attribs = _COLOURS["YELLOW"]
		else:
			attribs = _COLOURS["RED"] | curses.A_BOLD
		
		status_win.echo( "[", COLOURS["info"], no_refresh=True, y=tmpy, x=0 )
		status_win.echo( "Lag: " + lt + "%.02fs" % lag, attribs, no_refresh=True )
		status_win.echo( "]", COLOURS["info"], no_refresh=True )

	else:
		attribs = COLOURS["error"]
		status_win.echo( "[", COLOURS["info"], no_refresh=True, y=tmpy, x=0 )
		status_win.echo( "Disconnected!", attribs, no_refresh=True )
		status_win.echo( "]", COLOURS["info"], no_refresh=True )

	status_win.window.noutrefresh()

	if not no_refresh:
		input_win.refresh()
	else: input_win.refresh()

def buffer_switch (buffer=None):
	global current_buffer
	if AWAY: return

	_skeys = dsorted( buffers.keys() )	

	if buffer in ["next", "prev"]:
		d = 1
		if buffer == "next":
			pass
		elif buffer == "prev":
			_skeys.reverse() # this is not the most efficient way to do this

		m = False
		for key in _skeys:
			if buffers[key].has_unread:
				m = key
				break

		if not m:
			ci = _skeys.index( current_buffer )
			l = len( _skeys ) -1

			ci += d
			if ci < 0: ci = l
			if ci > l: ci = 0

			new_buffer = _skeys[ ci ]
		else:
			new_buffer = m
	elif buffer:
		new_buffer = buffer

	else: new_buffer = current_buffer


	current_buffer = new_buffer

	if buffer:
		buffers[current_buffer].has_unread = False
		buffers[current_buffer].has_unread_events = False
		buffers[current_buffer].has_unread_messages = False
		buffers[current_buffer].has_unread_to_me = False


	update_info(buffer)
	update_status(no_refresh=True)

  
	if buffer:
		buffers[current_buffer].window.redrawwin()
		buffers[current_buffer].window.noutrefresh()

	if buffers[current_buffer].dirty:
		buffers[current_buffer].dirty = False
		buffers[current_buffer].scroll_to(0)
	input_win.noutrefresh()
	curses.doupdate()
	irc_topic_change( buffers[current_buffer], buffers[current_buffer].topic_raw )


def show_context ( up ):
	if up:
		if away_win.selected < 0: return
		away_win.selected -= 1
	else:
		away_win.selected += 1

	away_win.scroll_to( away_win.selected, m=0, abs=True )
	context_win.contents = buffers[ away_win.marks[ away_win.selected ][0]  ].contents
	update_sepwin( len( away_win.marks ), away_win.selected + 1 )

	context_win.scroll_to(
		len( buffers[ away_win.marks[ away_win.selected ][0] ].contents ) - away_win.marks[ away_win.selected ][1],
		abs=True )

def process_input (window, key, string="", refresh=True):
	global CHANNEL_LIST
	global PASTE
	global SHOW_URL_LIST
	global URL
	attribs = COLOURS["input"]
	if refresh:
		try:
			PASTE.inc()
		except StartPasteMode:
			PASTE.on = True
		except EndPasteMode:
			PASTE.on = False
	
	if window.byte_buf:
		key = key

	if SHOW_URL_LIST:
		if key in OPTION_LIST[ 0:len(list_win.contents) ]:
			URL = URL_LIST[ OPTION_LIST.index( key ) ] 
			irc_process_command( None, "url", None )
			hide_list_win(list_win)
			SHOW_URL_LIST = False
		if key == chr( 27 ):
			hide_list_win( list_win )
			SHOW_URL_LIST = False
		return

	if CHANNEL_LIST:
		if key in OPTION_LIST[ 0:len(list_win.contents) ]:
			buffer_switch( dsorted( buffers.keys() )[OPTION_LIST.index(key)] )
			hide_list_win(list_win)
		if key == chr( 6 ):
			hide_list_win( list_win )
		return

	if AWAY:
		if key == "b":
			set_away()

		elif key in ["KEY_UP", "k"]:
			if away_win.selected == 0 or not len( away_win.marks ):
				return
			show_context( True )

		elif key in ["KEY_DOWN", "j"]:
			if away_win.selected == len( away_win.marks ) - 1:
				return
			show_context( False )

		elif key == "KEY_PPAGE":
			if not len( context_win.contents ):
				return

			context_win.scroll( 1 )

		elif key == "KEY_NPAGE":
			if not len( context_win.contents ):
				return

			context_win.scroll( -1 )
		elif key == chr( 12 ):
			away_win.redraw()
			context_win.redraw()
			sep_win.redraw()
			away_win.scroll_to( away_win.scrolling )
		return True 
	
	
	if window == input_win and key != chr(9) and window.autocomp:
		window.autocomp = False
		window.ix = 0 
		window.ts = ""
		window.cache_m = window.cache[ : ]

	if window.esc:
#		if key == "[":
#			window.esc = "^"
#			return

		if key == chr(27):
			window.esc = None
			return

		window.esc += key
		
		if not len( window.esc ) >= 3:
			window.esc = None
			return

		if window.esc == "^Od":
			tmpx = window.window.getyx()[1]
			window.esc = None
			window.mvw()#lb=window._fw() )
			return

		elif window.esc == "^Oc":
			tmpx = window.window.getyx()[1]
			window.esc = None
			window.mvw( bw=False )#lb=-window._fw( bw=False ) )
			return

		elif window.esc == "^[3^":
			window.esc = None
			window.delw()
			return
	
		elif window.esc[ -1 ] == "^":
			window.esc = None
			return
		
		#if window.esc[0] != "^":# and window.esc != 3:
		#	return

		return


#		elif key == "^":
#			window.esc = None
#			return
		
	
	if len(key) == 1 and ord(key[0]) in [ 32, 33, 34, 39, 40, 41, 44, 45, 46, 59, 58 ]:
		space_event( window, current_buffer )

	if len(key) == 1 and ord(key[0]) >= 32 and ord(key[0]) < 127:
		window.echo(key, attribs, no_refresh=not refresh)	
		window.mk_pview()
		return
	
	elif key == chr( 27 ):
		window.esc = "^"
		return
	
	elif key == "KEY_DC":		
		window.delete()

	elif len(key) == 1 and ord( key[0] ) > 127:
		if not window.byte_buf:
			window.byte_buf = key
		else:
			string += window.byte_buf + key
			window.echo(window.byte_buf + key, attribs, no_refresh=not refresh)	
			window.byte_buf = ""
		return 
	

	elif key == "KEY_BACKSPACE" or key == chr(127):
		return window.bs()
	
	elif key == chr( 8 ):
		return window.bsw()

	elif key == "KEY_ENTER" or key == chr(10):
		if PASTE.on:
			window.s += "\020r\020n"
			return
		return False

	elif key == "KEY_PPAGE":
		buffers[current_buffer].scroll(SCROLL_BY)

	elif key == "KEY_NPAGE":
		buffers[current_buffer].scroll(-SCROLL_BY)
	
	elif key in ["KEY_DOWN", "KEY_UP"]:
		if key == "KEY_DOWN": scroll = 1
		elif key == "KEY_UP": scroll = -1

		history = window.scroll_history(scroll)
		window.window.erase()
		window.s = ""
		string = ""
		if history:
			for c in history:
				string = process_input(window, c, string, refresh=False)
		window.refresh()
		return string
	
	elif key in ["KEY_LEFT", "KEY_RIGHT"]:
		if key == "KEY_LEFT":
			return window.mvc( 1 )

		elif key == "KEY_RIGHT": 
			return window.mvc( -1 )

	elif key == chr(18):			#C-r
		buffers[current_buffer].search( window.s )

	elif key == chr(1) or key == "KEY_HOME":		  #C-a
		window.mvc( len( window.s ) - window.cpos )

	elif key == "KEY_END":
		window.mvc( - window.cpos )

	elif key == chr(24):	  #C-x
		conn_switch()

	elif key == chr(5):		  #C-e
		irc_process_command( None, "urls", None )

	elif key == chr(14):		  #C-n
		buffer_switch("next")
	
	elif key == chr(16):		  #C-p
		buffer_switch("prev")

	elif key == chr(6):			#C-f
		if not list_win.visible:
			list_win.contents = make_channel_list()
			list_win.contents = make_option_list( list_win.contents )
			show_list_win(list_win, dsorted( buffers.keys() ).index(current_buffer), no_anim=True)
			CHANNEL_LIST = True
		
	
	elif key == chr(23):		  #C-w
		clear_unread()	

	elif key == chr(21):		  #C-u
		window.cleartobol()
		return ""
	
	elif key == chr(12):		#C-l
		buffer_switch()
		buffers[current_buffer].scroll_to( buffers[current_buffer].scrolling )

	elif key == chr(9):			#Tab
		if PASTE.on:
			string += "\t"
			return string

		if window.s == "/topic " or window.s == "/topic":
			if window.s == "/topic": process_input( window, " " )
			for c in buffers[current_buffer].topic_raw:
				process_input( window, c )
			return

		window.auto_complete()

def space_event( win, buf ):
	attr = None
	s = win.s[ len( win.s ) - win._fw() : ].lstrip()
	st = s
	for h in _INPUT_HOOKS:
		if h[ 0 ] == "_word":
			try:
				s, attr = h[ 1 ]( s, buf )
			except:
				raise_error( "Error in hook handler for word" + traceback.format_exc(0) )

	if st == s and attr is None:
		return
	
	if st != s or attr is not None:
		for i in range( len( st ) ):
			win.bs( v=True )
	
	win.echo( s, attr )

	return s, attr



def make_channel_list ( p=False ):
	channel_list = []
	_skeys = dsorted( buffers.keys() )
	for i in range( 0, len( _skeys ) ):
		s = _skeys[i]
		if buffers[ _skeys[i] ].has_unread and not p:
			s = "%s" % s
		channel_list.append(s)
	return channel_list
	
def make_option_list (option_list):
	for i in range( 0, len(option_list) ):
		option_list[i] = "%s %s" % (OPTION_LIST[i], option_list[i])
	return option_list

def update_list_win (win, mark=None, mark_attr=None):
	if type(mark) == int:
		mark = [mark]

	attr = mark_attr | curses.A_BOLD
	l = len(win.contents)
	r = win.w - 2

	for i in range(0, l):
		if i in mark:
			win.window.addstr( win.y + i + 1, win.x + 1, win.contents[i][:r], attr)
	win.window.refresh()
		  

def notice (notice_list, mark=None, mark_attr=None):
	global TIMER_QUEUE
	if type(notice_list) == str:
		notice_list = [notice_list]

	list_win.contents = notice_list
	if mark in list_win.contents:
		mark = list_win.contents.index(mark)

	if not list_win.visible:
		show_list_win (list_win, mark, mark_attr)
		TIMER_QUEUE = queue_now ( TIMER_QUEUE, 3, hide_list_win, list_win )
	else:
		TIMER_QUEUE = queue_job ( TIMER_QUEUE, 0, notice, notice_list, mark, mark_attr ) 


def show_list_win (win, mark=None, mark_attr=None, no_anim=False):
	global CHANNEL_LIST
	if not AWAY: buffer = buffers[current_buffer]
	else: buffer = away_win

	w = 18
	max = buffers[ MAIN_WINDOW_NAME ].w - 5
	for i, c in enumerate( win.contents ):
		lc = len( c )
		if lc + 5 > w and lc < max:
			w = lc + 5
		elif lc > max:
			win.contents[ i ] = c[ : max ]
			
	win.x = win.max_w - w - 1
	
	win.w = w
	win.visible = True
	curses.curs_set(0)
	if type(mark) == int:
		mark = [mark]
	if not mark_attr:
		mark_attr = COLOURS["highlight"] 

	l = len(win.contents)
	if l+2 >= win.max_h - 2: l = win.max_h - 2

	win.window.erase()
	win.window.resize( l+2, win.w )

	win.echo("\n", no_refresh=True)

	r = win.w - 2
	for i in range(0, l):
		attr = COLOURS["list"]
		if mark:
			if i in mark:
				attr = mark_attr | curses.A_BOLD
		win.echo(" " +win.contents[i][:r], attr, no_refresh=True)
		if not i == l: win.echo("\n", no_refresh=True)
	
	win.window.border()

	if buffer.h >= 25: l = buffer.h - 25
	if not no_anim:
		for j in range(buffer.h - l -2 - len(win.contents), 4, -1):
			win.window.mvwin(j-3, win.x-1)
			buffer.window.touchwin()
			buffer.window.noutrefresh()
			win.window.refresh()
			time.sleep(0.01)
	else:
		win.window.mvwin(1, buffers[ MAIN_WINDOW_NAME ].w - win.w -2 )
		buffer.window.touchwin()
		buffer.window.noutrefresh()
		win.window.refresh()

def hide_list_win (win):	
	global CHANNEL_LIST
	if not AWAY: buffer = buffers[current_buffer]
	else: buffer = away_win
	
	CHANNEL_LIST = False

	win.visible = False
	win.window.erase()
	buffer.window.touchwin()
	buffer.window.noutrefresh()
	input_win.refresh()
	curses.curs_set(1)

def scroll_topic ():
	if not SCROLL_TOPIC or AWAY: return

	topic = buffers[current_buffer].topic

	if len( topic ) <= topic_win.w: return

	topic += SCROLL_SEP
	topic_out = topic

	if len(topic) - topic_win.scrolling < topic_win.w:
		topic_out = topic[ topic_win.scrolling : len(topic) ]
		topic_out = topic_out + topic[ : topic_win.w - len(topic_out) -1 ]
	else:
		topic_out = topic[ topic_win.scrolling : topic_win.scrolling + topic_win.w -1 ]

	topic_win.window.erase()
	topic_win.echo( topic_out, COLOURS["topic"] ) 

	topic_win.scrolling += 1

	if topic_win.scrolling >= len(topic):
		topic_win.scrolling = 0


def discon ( connection ):
	global TIMER_QUEUE

	if not connection.notified:
		for buffer in buffers:
			system_write('Disconnected from server!', buffer)

		connection.notified = True

	update_status( msg="Disconnected!" )
	
	buffers[ MAIN_WINDOW_NAME ].scroll_to( 0 )
	connection.attempts += 1

	buffers[ MAIN_WINDOW_NAME ].echo( '\n\tReconnecting in 30 seconds... [' + str( connection.attempts ) + '] attempts.', COLOURS["system"] )

	#if current_buffer != MAIN_WINDOW_NAME: system_write('Reconnecting in 30 secs...', current_buffer)
	TIMER_QUEUE = queue_job( TIMER_QUEUE, 30, irc_process_command, connection, "server", SERVER )

def sigint (signum, frame):
	if SEARCH_MODE:
		raise CancelSearch
		return

	if ask_yes_no("Quit " + PROGRAM_NAME + "?"):
		exit_program()

def do_resize ():
	global DO_RESIZE
	DO_RESIZE = False

	curses.ungetch("")
	curses.endwin()
	curses.initscr()
#	stdscr.refresh()
	
	for key in buffers.keys():
		buffers[key].window.erase()
		buffers[key].resize(no_create=True)
		buffers[key].window.resize( buffers[key].h, buffers[key].w )
		if key is not current_buffer or AWAY: buffers[key].dirty = True
		#buffers[key].window.touchwin()
		#buffers[key].window.redrawwin()
		buffers[key].window.noutrefresh()
	
	for win in [away_win, sep_win, context_win]:
		win.window.erase()
		win.resize(no_create=True)
		win.window.resize( win.h, win.w )

	input_win.resize( no_create=True )
	search_win.resize( no_create=True )

	for win in [status_win, topic_win, info_win, list_win]:
		win.resize(no_create=True)
		win.window.resize( win.h, win.w )
		win.window.mvwin( win.y, win.x )
		win.window.noutrefresh()

	for x in [status_win.window, topic_win.window, list_win.window, info_win.window ]:
		x.redrawwin()
		x.touchwin()
		x.refresh()
	
	if not AWAY:
		buffers[current_buffer].scroll_to(0)
		buffers[current_buffer].window.refresh()
	else:
		pass
		#away_win.redraw()
		#context_win.redraw()
		#sep_win.redraw()

	
	update_info()
	update_status()
	input_win.refresh()

def sigwinch (signum, frame):
	global DO_RESIZE

	DO_RESIZE = True
 
def dsorted( d ):
	r = sorted( d )
	if MAIN_WINDOW_NAME in r:
		r.insert( 0, r.pop( r.index( MAIN_WINDOW_NAME ) ) )
	return r

def conn_switch ():
	pass

def wait_for_key (keys):
	if keys == None: keys = []

	curses.ungetch("*")
		
	c = ""
	while c not in keys:
		c = stdscr.getch()

		if c and not keys and c is not ord("*") and c > 0:
			return None

		if 48 <= c < 127: c = chr(c)
		else:
			if c == 9: return False

	return c

def log_write ( buf, string ):
	if not LOGGING: return

	if buf == away_win: return
	
	
	if LOG_ID:
		subdir = LOG_ID
	else:
		subdir = NICK
	p = LOGS_DIR + subdir + "/"

	if type( buf ) is str:
		p += buf
	else:
		p += buf.get_id()
		buf.log_path = p

	if type( buf ) is not str and not buf.logging:
		buf.logging = True

	if not os.access(LOGS_DIR + subdir + "/", os.F_OK):
		os.makedirs(LOGS_DIR + subdir + "/")

	try:
		f = open(p, mode="a")
	except IOError: return False		

	try:
		f.write(string)
		f.close()
	except IOError: return False

def check_time( t ):
	global TIMER_QUEUE
	global PING_TIME

	if time.time() - PING_TIME > 20.0:		
		TIMER_QUEUE = queue_unique( TIMER_QUEUE, 2, ping_server, connections[0] )
		PING_TIME = time.time()

	if time.strftime("%d") != time.strftime("%d", t):
		for buffer in buffers:
			buffers[buffer].write_time()
			t = time.localtime()
	return t

def queue_now ( queue, when, job, *args ):
	if not queue:
		queue = []
	queue.append( [time.time() + when, job, args] )
	return queue

def queue_job ( queue, when, job, *args ):
	if not queue:
		queue = []

	l = len(queue)
	t = time.time()

	for i in range (0, l):	 
		if queue[i][0] > t and job == queue[i][1]:
			t = queue[i][0]

	if t:
		queue.append ( [when + t, job, args] )
	else:
		queue = queue_now( queue, when, job, args )

	return queue
		
def queue_clear (queue, job, *args):
	if not queue:
		return queue

	l = len(queue)
	if not l: return queue
	i = 0
	while i < l:
		if queue[i][1] == job and len( queue[i][2] ) == len( args ):
			match = True
			for j in range( len( args ) ):
				if args[j] != queue[i][2][j] and args[j] != None:
					match = False
			if match:
				queue.pop(i)
				l -= 1
		i += 1
	return queue

def queue_unique( queue, when, job, *args ):
	global TIMER_QUEUE
	TIMER_QUEUE = queue_clear( queue, job, *args )
	TIMER_QUEUE = queue_job( queue, when, job, *args )
	return TIMER_QUEUE

def process_queue (queue):
	if not queue: return False

	l = len(queue)
	if not l: return False
		
	current_time = time.time()

	for i in range(0, l):
		if queue[i][0] <= current_time:
			queue[i][1]( *queue[i][2] )
			queue.pop(i)
			break

	return queue

def oe2e ( e ):
	t = Event( e.event_type, e.source, e.target, e.arguments )
	return t

def e2oe ( e ):
	t = OutEvent( e.source(), e.target(), e.eventtype(), e.arguments() )
	return t

def __handle_event ( c, e ):
	et = e.eventtype()
	
	m = False
	for out_h in _OUTPUT_HOOKS:
		if et == out_h[ 0 ]:
			try:
				tmp = e2oe( e )
				c, e = out_h[ 1 ]( c, tmp, *out_h[ 2 : ] )
				e = oe2e( e )
				m = True
			except:
				raise_error( "Error in hook handler for " + tmp.event_type + ":\n" + traceback.format_exc(0) )
				
	
	if et in EXT_HOOKS and c and e:
		EXT_HOOKS[ et ]( c, e )
	### Development only:
#	elif et != "all_raw_messages" and not m:
#		debug_event( c, e )
	###


def set_handlers():
	global EXT_HOOKS
	EXT_HOOKS = {
		"welcome" : _on_connect,
		"nick" : _on_nick,
		"nicknameinuse" : _on_nicknameinuse,
		"470" : _on_forwardtochannel,
		"topic" : _on_topic,
		"currenttopic" : _on_currenttopic,
		"topicinfo" : _on_topicinfo,
		"namreply" : _on_namreply,
		"endofnames" : _on_endofnames,
		"privmsg" : _on_privmsg,
		"pubmsg" : _on_pubmsg,
		"privnotice" : _on_privnotice,
		"pubnotice" : _on_pubnotice,
		"action" : _on_action,
		"part" : _on_part,
		"join" : _on_join,
		"quit" : _on_quit,
		"kick" : _on_kick,
		"whoisuser" : _on_whois,
		"endofwhois" : _on_whois,
		"whoisserver" : _on_whois,
		"whoisoperator" : _on_whois,
		"whowasuser" : _on_whois,
		"whoischannels" : _on_whois,
		"pong" : _on_pong,
		"ping" : _on_ping,
		"ctcp" : _on_ctcp,
		"ctcpreply" : _on_ctcpreply,
		"erroneusnickname" : _on_nickerror,
		"nosuchnick" : _on_nosuchnick,
		"cannotsendtochan" : _on_cannotsendtochan,
		"mode" : _on_mode,
		"umode" : _on_umode
	}

	irc.add_global_handler("all_events", __handle_event)
	"""
	irc.add_global_handler("welcome", __handle_event)
	irc.add_global_handler("nick", __handle_event)
	irc.add_global_handler("nicknameinuse", __handle_event)
	irc.add_global_handler("470", __handle_event)
	irc.add_global_handler("topic", __handle_event)
	irc.add_global_handler("currenttopic", __handle_event)
	irc.add_global_handler("namreply", __handle_event)
	irc.add_global_handler("endofnames", __handle_event)
	irc.add_global_handler("privmsg", __handle_event)
	irc.add_global_handler("pubmsg", __handle_event)
	irc.add_global_handler("privnotice", __handle_event)
	irc.add_global_handler("pubnotice", __handle_event)
	irc.add_global_handler("action", __handle_event)
	irc.add_global_handler("part", __handle_event)
	irc.add_global_handler("join", __handle_event)
	irc.add_global_handler("quit", __handle_event)
	irc.add_global_handler("kick", __handle_event)
	irc.add_global_handler("whoisuser", __handle_event)
	irc.add_global_handler("endofwhois", __handle_event)
	irc.add_global_handler("whoisserver", __handle_event)
	irc.add_global_handler("whoisoperator", __handle_event)
	irc.add_global_handler("whowasuser", __handle_event)
	irc.add_global_handler("whoischannels", __handle_event)
	irc.add_global_handler("pong", __handle_event)
	irc.add_global_handler("ping", __handle_event)
	irc.add_global_handler("ctcp", __handle_event)
	irc.add_global_handler("ctcpreply", __handle_event)
	irc.add_global_handler("erroneusnickname", __handle_event)
	"""

def main (scr):
	global TIMER_QUEUE
	global PING_TIME
	global DO_RESIZE
	global RC_PATH
	
	try:
		path = sys.argv[1]
		RC_PATH = path
	except:
		path = None

	rc_file = load_rc(path)

	buffers[MAIN_WINDOW_NAME].scroll( buffers[MAIN_WINDOW_NAME].h )
	buffers[MAIN_WINDOW_NAME].scroll_to( 0 )
	
	buffers[MAIN_WINDOW_NAME].write_time()
	irc_topic_change( buffers[MAIN_WINDOW_NAME], " " + PROGRAM_NAME + ": " + SERVER )

	set_handlers()

	if SERVER:
		try:
			connections[0].connect(SERVER, PORT, NICK, ircname=REALNAME)
		except birclib.ServerConnectionError, x:
			print x
			sys.exit(1)
			
	buffer_switch()
	t = time.localtime()
	PING_TIME = time.time()

	while True:
		if not AWAY:
			input_win.clear()

		while True:
			if DO_RESIZE:
				do_resize()

			TIMER_QUEUE = process_queue(TIMER_QUEUE)

			t = check_time( t )
			irc.process_once()

			scroll_topic()

			try: c = scr.getkey()
			except: c = None	

			#irc.process_once()
			
			if c:
				result = process_input(input_win, c, input_win.s)

				if (type(result) == bool and not result) and ( input_win.s or len(input_win.temp_buffer) ):
					break
		lnb = input_win.s.count("\020r\020n")

		if lnb == 1 and input_win.s[ : -4 ] == "\020r\020n":
			input_win.s = input_win.s.replace("\020r\020n", "")
			lnb = 0

		lines = [ input_win.s ]
		if lnb >= 1:
			r = ask_question( "l: insert line breaks, m: separate messages, x: cancel.", ["l", "m", "x"] )
			if r == "l": pass
			elif r == "m": lines = input_win.s.split("\020r\020n")
			elif r == "x": continue

		for line in lines:
			input_win.contents.append(line)
			input_win.i = len(input_win.contents)

			if re.search("^/", line):
				command = "/".join( line.split("/")[1:] )
				args = command.split(" ")[1:]
				command = command.split(" ")[0]
				irc_process_command(connections[0], command, args)
			elif len(line): irc_process_command(connections[0], "say", line.split(" "))


connections[0] = irc.server()
connections[0].live = True
connections[0].attempts = 0
connections[0].need_autojoin = False

y, x = stdscr.getmaxyx()

signal.signal(signal.SIGWINCH, sigwinch)
signal.signal(signal.SIGINT, sigint)

PASTE = Paste()


buffers[MAIN_WINDOW_NAME] = irc_window("main")

input_win = InputWindow()
search_win = InputWindow()

message_win = MessageWindow()

status_win = irc_window("status")
info_win = irc_window("info")

away_win = irc_window("away")
sep_win = irc_window("sep")
context_win = irc_window("context")

list_win = irc_window("list")
topic_win = irc_window("topic")

COLOURS["topic"] = COLOURS["topic"] | curses.A_BOLD
topic_win.window.erase()
list_win.window.erase()


try: curses.wrapper(main)
except:
	raise

