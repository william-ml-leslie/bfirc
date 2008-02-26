import re

class ParseError(Exception):
	def __init__ ( self, value ):
		self.parameter = value
	def __str__ ( self ):
		return repr( self.parameter )

def parse_options (args, return_upper_case=False):
   params = {}
   param = []
   i = 0
   max = len(args)
   match_pattern = '[a-zA-Z0-9\[\]{}()<>*&^%$!,.\\/@\'#~:;`]'
   while i < max: 
      arg = args[i]

      if not arg: break

      if re.search('[a-zA-Z0-9]+=' + match_pattern + '+', arg):
         param = arg.split("=")
      elif re.search('[a-zA-Z0-9]+="' + match_pattern + '+"', arg):
         param = arg.split("=")
      elif re.search('[a-zA-Z0-9]+="', arg):
         param = arg.split("=")
         j = 0
         for j in range(i+1, max+1):
            if re.search('"', args[j]):
               break
         param[1] = param[1] + " " + " ".join(args[i+1:j+1])
         i += 1
         for k in range (i+1, j):
            max -= 1
            i += 1
      else:
         if len(args) > i:
            t = ":  \"" + args[i] + "\""
         else: t = ""

         raise ParseError('Error at line: ' + str( i ) + '' + t)
         return False

      param[1] = re.sub('"', '', param[1])

      if return_upper_case:
         params[ param[0].upper() ] = param[1]
      else:
         params[ param[0] ] = param[1] 
      i += 1 

   return params
