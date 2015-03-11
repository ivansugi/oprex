
# parsetab.py
# This file is automatically generated. Do not edit.
_tabversion = '3.2'

_lr_method = 'LALR'

_lr_signature = '\xcc\xeb\x1e\xe4\xa2\x08\xc1\xdc:\xda|\x1a\xdaD\xe17'
    
_lr_action_items = {'DEDENT':([9,10,21,22,25,29,30,33,36,40,41,42,43,45,46,],[-6,17,-18,-20,33,-19,-21,-7,-25,-22,-23,-26,-24,46,-27,]),'QUESTMARK':([11,20,28,],[18,27,35,]),'INDENT':([3,9,42,],[5,16,16,]),'WHITESPACE':([0,],[2,]),'VARNAME':([3,5,7,9,14,15,16,19,21,22,23,30,32,33,36,40,41,42,43,44,46,],[6,6,11,-6,20,24,-17,11,24,-20,24,-21,38,-7,-25,-22,-23,-26,-24,24,-27,]),'NEWLINE':([0,4,6,12,19,26,37,38,39,],[3,9,-8,-9,-10,-11,42,-8,43,]),'GLOBALMARK':([9,15,16,21,22,30,33,36,40,41,42,43,44,46,],[-6,23,-17,23,-20,-21,-7,-25,-22,-23,-26,-24,23,-27,]),'LITERAL':([32,],[39,]),'COLON':([24,38,],[31,31,]),'CHARCLASS':([31,],[37,]),'SLASH':([3,5,11,13,18,28,32,34,35,],[7,7,-12,19,-13,-14,7,-16,-15,]),'LPAREN':([7,19,],[14,14,]),'RPAREN':([20,27,],[28,34,]),'EQUALSIGN':([24,38,],[32,32,]),'$end':([0,1,2,3,8,9,17,33,],[-1,0,-2,-3,-4,-6,-5,-7,]),}

_lr_action = { }
for _k, _v in _lr_action_items.items():
   for _x,_y in zip(_v[0],_v[1]):
      if not _x in _lr_action:  _lr_action[_x] = { }
      _lr_action[_x][_k] = _y
del _lr_action_items

_lr_goto_items = {'definition':([15,21,44,],[21,21,21,]),'lookups':([3,5,32,],[4,4,4,]),'oprex':([0,],[1,]),'assignment':([15,21,23,32,44,],[22,22,30,40,22,]),'cells':([7,19,],[12,26,]),'cell':([7,19,],[13,13,]),'beginscope':([9,42,],[15,44,]),'charclass':([31,],[36,]),'definitions':([15,21,44,],[25,29,45,]),'expression':([3,5,32,],[8,10,41,]),}

_lr_goto = { }
for _k, _v in _lr_goto_items.items():
   for _x,_y in zip(_v[0],_v[1]):
       if not _x in _lr_goto: _lr_goto[_x] = { }
       _lr_goto[_x][_k] = _y
del _lr_goto_items
_lr_productions = [
  ("S' -> oprex","S'",1,None,None,None),
  ('oprex -> <empty>','oprex',0,'p_oprex','oprex.py',300),
  ('oprex -> WHITESPACE','oprex',1,'p_oprex','oprex.py',301),
  ('oprex -> NEWLINE','oprex',1,'p_oprex','oprex.py',302),
  ('oprex -> NEWLINE expression','oprex',2,'p_oprex','oprex.py',303),
  ('oprex -> NEWLINE INDENT expression DEDENT','oprex',4,'p_oprex','oprex.py',304),
  ('expression -> lookups NEWLINE','expression',2,'p_expression','oprex.py',322),
  ('expression -> lookups NEWLINE beginscope definitions DEDENT','expression',5,'p_expression','oprex.py',323),
  ('lookups -> VARNAME','lookups',1,'p_lookups','oprex.py',345),
  ('lookups -> SLASH cells','lookups',2,'p_lookups','oprex.py',346),
  ('cells -> cell SLASH','cells',2,'p_cells','oprex.py',357),
  ('cells -> cell SLASH cells','cells',3,'p_cells','oprex.py',358),
  ('cell -> VARNAME','cell',1,'p_cell','oprex.py',370),
  ('cell -> VARNAME QUESTMARK','cell',2,'p_cell','oprex.py',371),
  ('cell -> LPAREN VARNAME RPAREN','cell',3,'p_cell','oprex.py',372),
  ('cell -> LPAREN VARNAME RPAREN QUESTMARK','cell',4,'p_cell','oprex.py',373),
  ('cell -> LPAREN VARNAME QUESTMARK RPAREN','cell',4,'p_cell','oprex.py',374),
  ('beginscope -> INDENT','beginscope',1,'p_beginscope','oprex.py',405),
  ('definitions -> definition','definitions',1,'p_definitions','oprex.py',411),
  ('definitions -> definition definitions','definitions',2,'p_definitions','oprex.py',412),
  ('definition -> assignment','definition',1,'p_definition','oprex.py',422),
  ('definition -> GLOBALMARK assignment','definition',2,'p_definition','oprex.py',423),
  ('assignment -> VARNAME EQUALSIGN assignment','assignment',3,'p_assignment','oprex.py',457),
  ('assignment -> VARNAME EQUALSIGN expression','assignment',3,'p_assignment','oprex.py',458),
  ('assignment -> VARNAME EQUALSIGN LITERAL NEWLINE','assignment',4,'p_assignment','oprex.py',459),
  ('assignment -> VARNAME COLON charclass','assignment',3,'p_assignment','oprex.py',460),
  ('charclass -> CHARCLASS NEWLINE','charclass',2,'p_charclass','oprex.py',475),
  ('charclass -> CHARCLASS NEWLINE beginscope definitions DEDENT','charclass',5,'p_charclass','oprex.py',476),
]
