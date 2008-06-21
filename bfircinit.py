import curses
import os
class decor:
	def set (self, pre=None, suf=None):
		if pre: self.prefix = pre
		if suf: self.suffix = suf

	def __init__ (self, pre="<", suf="> "):
		self.prefix = pre
		self.suffix = suf
	
		self.set(pre, suf)

IGNORE = []
IGNORE_TO = []
BUDDY_LIST = []
WATCH_LIST = []
AUTOJOIN_LIST = {}
WATCHWORDS = []
HIGHLIGHTS = {}

URL = ""
URL_LIST = []
URL_ACTION = ""
SHOW_URL_LIST = False
SHOW_EVENTS = True
CHANNEL_LIST = False
NICK_COLS = False
DO_RESIZE = False
SEARCH_MODE = False
TIMER_QUEUE = []
PING_TIME = 0.0
TIMEOUT = 107
ALIASES = {}
ESCAPE_SEQ = "|*|^|"
SCROLL_BY = 10
MAIN_WINDOW_NAME = "(server)"
SERVER_NAME = "Server"
QUIT_MESSAGE = "bfirc dans ta gueule."
current_buffer = MAIN_WINDOW_NAME
current_con = 0
AUTO_REJOIN = False
SCROLL_TOPIC = True
SCROLL_SEP = "   ***   "
AWAY = False
LOGGING = False
PROGRAM_DIR = os.path.expanduser("~") + "/.bfirc/"
LOGS_DIR = PROGRAM_DIR + "logs/"
LOG_ID = None
RC_PATH = os.path.expanduser("~") + "/.bfircrc"
if not os.access( RC_PATH, os.F_OK ):
	RC_PATH = ""

NICK = "bfirc-user"
REALNAME = NICK
SERVERS = []
PORT = 6667
PASS = ""

EXT_HOOKS = []
INPUT_HOOKS = []
_INPUT_HOOKS = []
OUTPUT_HOOKS = []
_OUTPUT_HOOKS = []
HOOKS = []

_COLOURS = {}
COLOURS = {}

PROGRAM_NAME = "bobfirc"
OPTION_LIST = [ "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z" ]							  
them_decor = decor("<", "> ")
them_act_decor = decor("* ", " ")

me_decor = decor("[", "] ")
me_act_decor = decor("* ", " ")

stamp_decor = decor("[", "] ")
system_decor = decor("[", "] ")
plain_decor = decor("", "")
topic_decor = decor("", "")

list_decor = decor("", "")
highlight_decor = decor("", "")

online_decor = decor("", "")
offline_decor = decor("", "")

_VALID_COLS = [ "BLACK", "RED", "GREEN", "YELLOW", "BLUE", "MAGENTA", "CYAN", "WHITE" ]

SYS_COLOURS = {
	"metalk" : "BLUE",
	"meact"  : "CYAN",
	"themtalk" : "RED",
	"themact" : "YELLOW",
	"system" : "GREEN",
	"systemwrap" : "GREEN",
	"error" : "RED",
	"stamp" : "BLACK",
	"plain" : "DEFAULT",
	"list" : "YELLOW",
	"highlight" : "GREEN",
	"online" : "GREEN",
	"offline" : "RED",
	"topic" : ( "CYAN", "BLUE" ),
	"info" : "YELLOW",
	"input" : "YELLOW",
	"search" : ( "WHITE", "RED" ),
	"select" : ( "WHITE", "BLUE" )
}

#stdscr = curses.initscr()
#curses.start_color()
#curses.use_default_colors()
#stdscr.timeout(TIMEOUT)




def make_colours( cols=None ):
	global COLOURS, _COLOURS
	for i in range( 63 ):
		if i > 7: j = i / 8
		else: j = -1
		curses.init_pair( i+1, i % 8, j )


	_COLOURS["BLACK"] = 0
	_COLOURS["RED"] = 1
	_COLOURS["GREEN"] = 2
	_COLOURS["YELLOW"] = 3
	_COLOURS["BLUE"] = 4
	_COLOURS["MAGENTA"] = 5
	_COLOURS["CYAN"] = 6
	_COLOURS["WHITE"] = 7
	_COLOURS["DEFAULT"] = -1
	if cols:
		SYS_COLOURS = cols
	for c in SYS_COLOURS:
		if c == "metalk":
			f = [ lambda x: x | curses.A_BOLD ]
		else:
			f = [ lambda x: x ]
		
		if type( SYS_COLOURS[ c ] ) is str:
			COLOURS[ c.lower() ] = f[0]( curses.color_pair( _COLOURS[ SYS_COLOURS[ c.lower() ].upper() ]+1 ) )
			continue

		COLOURS[ c.lower() ] = f[0]( curses.color_pair( _COLOURS[ SYS_COLOURS[ c.lower() ][ 0 ].upper() ] + 1 + ( _COLOURS[ SYS_COLOURS[ c ][ 1 ].upper() ] * 8 ) ) )

	for c in _COLOURS:
		_COLOURS[ c.upper() ] = curses.color_pair( _COLOURS[ c.upper() ] + 1 )
	
	return COLOURS

#COLOURS = make_colours( SYS_COLOURS )

def make_events ():
	events = [
		("error", "e",  "(@) %s: Error: %s", "error"),
		("system", "s", "(@) %s: %s", "system"),
		("systemwrap", "s", "(@) %s: %s", "system"),
		("time", "t", "(@) %s: %s\n", "system"),
		("topic", "T", "(^) %s changed topic to %s", "system"),
		("nick", "n", "(=) %s is now known as %s", "system"),
		("pubmsg", "@", them_decor.prefix + "%s" + them_decor.suffix, "themtalk"),
		("privmsg",	"@", them_decor.prefix + "%s" + them_decor.suffix, "themtalk"),
		("servernotice", "S", system_decor.prefix + SERVER_NAME + system_decor.suffix + "%s", "system"),
		("privnotice", "v", "Notice: " + them_decor.prefix + "%s" + them_decor.suffix, "themtalk"),
		("pubnotice", "P", system_decor.prefix + "%s" + system_decor.suffix, "themtalk"),
		("action", "^", them_act_decor.prefix + "%s" + them_act_decor.suffix, "themact"),
		("join", "j", "(-) %s has joined", "system"),
		("part", "p", ")-( %s has left", "system"),
		("kick", "k", "]-[ %s was kicked by %s", "system"),
		("quit", "q", ")o( %s has quit: %s", "system"),
		("me_say", "%", me_decor.prefix + "%s" + me_decor.suffix, "metalk"),
		("me_action", "~", me_act_decor.prefix + "%s" + me_act_decor.suffix, "meact"),
		("me_msg", "%", me_decor.prefix + "%s" + me_decor.suffix, "metalk"),
		("msg_to_me", "m", "PM <- %s: ", "themtalk"),
		("msg_from_me", "M", "PM -> %s: ", "metalk")
	]

	return events

EVENTS = make_events()
