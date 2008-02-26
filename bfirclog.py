from bfircinit import COLOURS, _COLOURS, EVENTS, _VALID_COLS, make_events
import re
import random
import os
from curses import A_BOLD

class message:
	def __init__ (self):
		self.s = ""
		self.stamp = False
		self.frm = False
		self.attr = False
		self.e = False

def _mkncol( n ):
	l = len( _VALID_COLS ) 
	t = 0
	for i, c in enumerate( n ):
		 t += ( ord( c ) / ( i + 1 ) )
	random.seed( t )
	r = _COLOURS[ _VALID_COLS[ random.randint( 1, 6 ) ] ]
	if random.randint(0,1): r = r | A_BOLD
	
	if r == COLOURS["metalk"] | A_BOLD: return COLOURS["metalk"]

	return r

def format_string( src, string, event_type, events=None ):
	attribs = COLOURS["plain"]
	msg_from = None
	if not events: events = EVENTS

	for event in events:
		 if event_type == event[0]:
				if event[2].count("%s") == 2:
					string = event[2] % (src, string)
				elif event[2].count("%s") == 1:
					msg_from = event[2] % (src)
				attribs = event[3]
				break

	return (msg_from, attribs, string)

def escape_string( string ):
	escape = "[]()*"
	for e in escape:
		 if e in string:
				string = string.replace(e, str('\\'+e)  )
	return string

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

def read_log( f, n=0, pt=False, buf=None, events=None, bw=True ):
	out = []
	r = n
		
	if not bw: max = os.stat( f.name ).st_size -1

	for i in range( r ):
		c = ""
		string = ""
		maxed = False
		while c != "\n":
			c = f.read(1)
			if c != "\n" and bw: string = c + string
			if c != "\n" and not bw: string += c
			if bw and f.tell() > 2: f.seek( f.tell() -2)
			elif not bw and f.tell() < max: f.seek( f.tell() )
			else:
				maxed = True
				break
		msg = message()
		if not maxed:
			if len(string):
				event, segments = log_parse( string )
				if segments and not pt:
					msg.stamp = segments[0]
					msg.e = event
					if len(segments) == 3:
						src = segments[1]
						string = segments[2]
					else:
						src = segments[1]
						string = segments[2]

					msg.frm, msg.attr, msg.s = format_string( src, string, event, events )

					if event in [ 'privmsg', 'pubmsg', 'action' ]:

						if buf and msg.frm not in buf._ncols.keys():
							buf._ncols[ msg.frm ] = _mkncol( msg.frm )

						if buf: msg.attr = buf._ncols[ msg.frm ]

				else: msg.s = string
		elif not len( out ): return False
		else: return out
		out.append( msg )
	return out

def log_parse ( string ):
	event = get_event_from_prefix( string[0] )

	if not event:
		return False, False

	match = "(.+?)"
	substrings = event[2].count( "%s" )
	for i in range( substrings ):
		match = match + "%s(.*)"
	s = re.search( match, event[2] )
	
	match = ".(\[\d\d:\d\d:\d\d\] )"

	for g in s.groups():
		g = escape_string(g)
		match = match + g + "(.*)" 
		
	match = match.replace("", "")

	s = re.search( match, string )

	if s:	
		return event[0], s.groups()
	else:
		return False, False

def bfirclog_update ( colours ):
	global COLOURS
	global EVENTS
	COLOURS = colours
	EVENTS = make_events()
