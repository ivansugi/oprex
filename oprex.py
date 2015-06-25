# -*- coding: utf-8 -*-

import regex, argparse, codecs, unicodedata
from ply import lex, yacc
from collections import namedtuple, deque


def oprex(source_code):
    source_lines = sanitize(source_code)
    lexer = build_lexer(source_lines)
    result = parse(lexer=lexer)
    check_captures(lexer=lexer)
    return result


class OprexSyntaxError(Exception):
    def __init__(self, lineno, msg):
        msg = msg.replace('\t', ' ')
        if lineno:
            Exception.__init__(self, '\nLine %d: %s' % (lineno, msg))
        else:
            Exception.__init__(self, '\n' + msg)


def sanitize(source_code):
    # oprex requires the source code to have leading and trailing blank lines to make
    # "proper look of indentation" when it is a triple-quoted string
    source_lines = regex.split('\r?\n', source_code)
    if source_lines[0].split('--')[0].strip():
        raise OprexSyntaxError(1, 'First line must be blank, not: ' + source_lines[0])
    if source_lines[-1].split('--')[0].strip():
        numlines = len(source_lines)
        raise OprexSyntaxError(numlines, 'Last line must be blank, not: ' + source_lines[-1])
    return source_lines


states = (
    ('charclass', 'exclusive'),
)
LexToken = namedtuple('LexToken', 'type value lineno lexpos lexer')
ExtraToken = lambda t, type, value=None, lexpos=None: LexToken(type, value or t.value, t.lexer.lineno, lexpos or t.lexpos, t.lexer)
reserved = {
    '_' : 'UNDERSCORE',
}
tokens = [
    'ALTBEGIN',
    'ALTEND',
    'AMPERSAND',
    'OR',
    'CHAR',
    'COLON',
    'DEDENT',
    'DOT',
    'EQUALSIGN',
    'FLAGSET',
    'GLOBALMARK',
    'GT',
    'INDENT',
    'NUMBER',
    'LPAREN',
    'LT',
    'MINUS',
    'NEWLINE',
    'OF',
    'PLUS',
    'QUESTMARK',
    'RPAREN',
    'SLASH',
    'STRING',
    'VARNAME',
    'WHITESPACE',
] + reserved.values()

GLOBALMARK   = '*)'
t_AMPERSAND  = r'\&'
t_OR         = r'\|'
t_DOT        = r'\.'
t_EQUALSIGN  = r'\='
t_GT         = r'\>'
t_LPAREN     = r'\('
t_LT         = r'\<'
t_MINUS      = r'\-'
t_NUMBER     = r'\d+'
t_PLUS       = r'\+'
t_QUESTMARK  = r'\?'
t_RPAREN     = r'\)'
t_SLASH      = r'\/'
t_ignore = '' # oprex is whitespace-significant, no ignored characters


class Variable(namedtuple('Variable', 'name value lineno')):
    __slots__ = ()
    def is_builtin(self):
        return self.lineno == 0

class VariableDeclaration(namedtuple('VariableDeclaration', 'varname capture atomic')):   
    __slots__ = ()

class VariableLookup(namedtuple('VariableLookup', 'varname lineno optional')):
    __slots__ = ()

class Backreference(namedtuple('Backreference', 'varname lineno optional')):
    __slots__ = ()

class SubroutineCall(namedtuple('SubroutineCall', 'varname lineno optional')):
    __slots__ = ()

class Quantifier(namedtuple('Quantifier', 'base modifier')):
    __slots__ = ()

class Assignment(namedtuple('Assignment', 'declarations value lineno')):
    __slots__ = ()

class Scope(dict):
    ROOTSCOPE, BLOCKSCOPE, FLAGSCOPE = range(3)
    __slots__ = ('type')
    def __init__(self, type, parent_scope):
        self.type = type
        if parent_scope:
            self.update(parent_scope)


class Flagset(unicode):
    __slots__ = ('turn_ons', 'turn_offs')
    all_flags = {}
    scopeds = {
        'dotall'     : 's',
        'fullcase'   : 'f',
        'ignorecase' : 'i',
        'multiline'  : 'm',
        'verbose'    : 'x',
        'word'       : 'w',
    }
    globals = {
        'ascii'        : 'a',
        'bestmatch'    : 'b',
        'enhancematch' : 'e',
        'locale'       : 'L',
        'reverse'      : 'r',
        'unicode'      : 'u',
        'version0'     : 'V0',
        'version1'     : 'V1',
    }
    def __new__(cls, turn_ons, turn_offs):
        if turn_offs:
            flags = turn_ons + '-' + turn_offs
        else:
            flags = turn_ons
        flagset = unicode.__new__(cls, flags)
        flagset.turn_ons = turn_ons
        flagset.turn_offs = turn_offs
        return flagset
        
Flagset.all_flags.update(Flagset.scopeds)
Flagset.all_flags.update(Flagset.globals)


class Expression(unicode):
    __slots__ = ('grouped', 'quantifier')
    def __new__(cls, base_value, modifier=None): # modifier can be quantifier, scoped flags, capture, or atomic group
        value = base_value
        grouped = False
        quantifier = None
        if modifier:
            if modifier.startswith('(?'): # scoped flags/capture/atomic group -- in any case it should be missing the closing paren
                value = modifier + base_value + ')' # add the closing paren
                grouped = True
            else: # modifier is quantifier
                quantifier = modifier
                value += quantifier
        expr = unicode.__new__(cls, value)
        expr.grouped = grouped
        expr.quantifier = quantifier
        return expr


class CharClass(Expression):
    __slots__ = ('is_set_op',)
    escapes = {
        '['  : '\\[',
        ']'  : '\\]',
        '^'  : '\\^',
        '-'  : '\\-',
        '\\' : '\\\\',
    }
    def __new__(cls, value, is_set_op):
        charclass = Expression.__new__(cls, value)
        charclass.is_set_op = is_set_op
        return charclass

    class Item(namedtuple('CharClassItem', 'source type value')):
        __slots__ = ()

    @staticmethod
    def item_token(t, type, value):
        source = t.value
        if type not in ('include', 'op'): # testing those types requires parser context
            try:
                regex.compile('[' + value + ']')
            except regex.error as e:
                raise OprexSyntaxError(t.lineno, 
                    '%s compiles to %s which is rejected by the regex engine with error message: %s' % (source, value, e.message))
        t.type = 'CHAR'
        t.value = CharClass.Item(source, type, value)
        return t


Builtin   = lambda name, value: Variable(name, Expression(value), lineno=0)
BuiltinCC = lambda name, value: Variable(name, CharClass(value, is_set_op=False), lineno=0)
BUILTINS  = [
    BuiltinCC('alpha',     '[a-zA-Z]'),
    BuiltinCC('upper',     '[A-Z]'),
    BuiltinCC('lower',     '[a-z]'),
    BuiltinCC('alnum',     '[a-zA-Z0-9]'),
    BuiltinCC('digit',     r'\d'),
    BuiltinCC('backslash', r'\\'),
    BuiltinCC('whitechar', r'\s'),
    BuiltinCC('wordchar',  r'\w'),
    Builtin('.',           r'\b'),
    Builtin('_',           r'\B'),
    Builtin('SoS',         r'\A'),
    Builtin('EoS',         r'\Z'),
    Builtin('uany',        r'\X'),
]
FLAG_DEPENDENT_BUILTINS = dict(
    m = { # MULTILINE
        True  : [
            Builtin('SoL', '^'),
            Builtin('EoL', '$'),
        ],
        False : [
            Builtin('SoL', '(?m:^)'),
            Builtin('EoL', '(?m:$)'),
        ],
    },
    s = { # DOTALL
        True  : [
            Builtin('any', '.'),
        ],
        False : [
            Builtin('any', '(?s:.)'),
        ],
    },
    w = { # WORD
        True  : [
            BuiltinCC('linechar', r'[\r\n\x0B\x0C]'),
        ],
        False : [
            BuiltinCC('linechar', r'\n'),
        ],
    },
    x = { # VERBOSE
        True  : [
            BuiltinCC('space',  '[ ]'),
            BuiltinCC('tab',   r'[\t]'),
        ],
        False : [
            BuiltinCC('space',  ' '),
            BuiltinCC('tab',   r'\t'),
        ],
    },
)
DEFAULT_FLAGS = 'wm'
for flag in FLAG_DEPENDENT_BUILTINS:
    for var in FLAG_DEPENDENT_BUILTINS[flag][flag in DEFAULT_FLAGS]:
        BUILTINS.append(var)

def flags_redef_builtins(t, flags, scope):
    for flag in FLAG_DEPENDENT_BUILTINS:
        if flag in flags:
            for var in t.lexer.flag_dependent_builtins[flag][flag in flags.turn_ons]:
                scope[var.name] = var


def t_ALTBEGIN(t):
    r'''/\|'''
    return t


def t_ALTEND(t):
    r'''\|/'''
    return t


def t_COLON(t):
    r''':'''
    t.lexer.set_mode('charclass')
    return t


def t_charclass_DOT(t):
    r'''\.'''
    return t


def t_charclass_op(t):
    '''not:|not|and'''
    return CharClass.item_token(t, 'op', {
        'not:' : '^',
        'not'  : '--',
        'and'  : '&&',
    }[t.value])


def t_charclass_varname(t):
    r'''\w{2,}'''
    return CharClass.item_token(t, 'include', VariableLookup(t.value, t.lineno, optional=False))


def t_charclass_include(t):
    r'''\+\w+'''
    return CharClass.item_token(t, 'include', VariableLookup(t.value[1:], t.lineno, optional=False))


def t_charclass_prop(t):
    r'''/\w+(=\w+)?'''
    return CharClass.item_token(t, 'prop', '\p{%s}' % t.value[1:])


def t_charclass_name(t):
    r''':[\w-]+'''
    return CharClass.item_token(t, 'name', '\N{%s}' % t.value[1:].replace('_', ' '))


def t_charclass_escape(t):
    r'''(?x)\\
    ( [\\abfnrtv]    # Single-character escapes
    | N\{[^}]+\}     # Unicode character name
    | U[a-fA-F\d]{8} # 8-digit hex escapes
    | u[a-fA-F\d]{4} # 4-digit hex escapes
    | x[a-fA-F\d]{2} # 2-digit hex escapes 
    | [0-7]{1,3}     # Octal escapes
    )(?=[\s.])'''
    return CharClass.item_token(t, 'escape', t.value)


def t_charclass_bad_escape(t):
    r'''\\\S+'''
    raise OprexSyntaxError(t.lineno, 'Bad escape sequence: ' + t.value)


def t_charclass_literal(t):
    r'''\S'''
    return CharClass.item_token(t, 'literal', CharClass.escapes.get(t.value, t.value))


def t_FLAGSET(t):
    r'\([- \t\w]+\)'
    flags = t.value[1:-1] # exclude the surrounding ( )
    flags = flags.split(' ') # will contain empty strings in case of consecutive spaces, so...
    flags = filter(lambda flag: flag, flags) # ...exclude empty strings
    turn_ons = ''
    turn_offs = ''
    for flag in flags:
        try:
            if flag.startswith('-'):
                turn_offs += Flagset.all_flags[flag[1:]]
            else:
                turn_ons += Flagset.all_flags[flag]
        except KeyError:
            raise OprexSyntaxError(t.lineno, "Unknown flag '%s'. Supported flags are: %s" % (flag, ' '.join(sorted(Flagset.all_flags.keys()))))

    flags = Flagset(turn_ons, turn_offs)
    try:
        test = '(?%s)' % flags
        if 'V' in flags:
            regex.compile(test)
        else:
            regex.compile('(?V1)' + test)
    except Exception as e:
        raise OprexSyntaxError(t.lineno, '%s compiles to %s which is rejected by the regex engine with error message: %s' % 
            (t.value, test, str(e.message)))
    else:
        t.type = 'LPAREN'
        t.extra_tokens = [ExtraToken(t, 'FLAGSET', value=flags), ExtraToken(t, 'RPAREN')]
    return t


ESCAPE_SEQUENCE_RE = regex.compile(r'''\\
    ( [abfnrtv]   # Single-character escapes
    | N\{[^}]++\} # Unicode character name
    | U\d{8}      # 8-digit hex escapes
    | u\d{4}      # 4-digit hex escapes
    | x\d{2}      # 2-digit hex escapes
    | [0-7]{1,3}  # Octal escapes
    )''', regex.VERBOSE)

OVERESCAPED_RE = regex.compile(r'''\\\\
    ( \\\\          # Escaped backslash
    | ['"abfnrtv]   # Single-character escapes
    | N\\\{[^}]++\} # Unicode character name
    | U\d{8}        # 8-digit hex escapes
    | u\d{4}        # 4-digit hex escapes
    | x\d{2}        # 2-digit hex escapes
    | [0-7]{1,3}    # Octal escapes
    )''', regex.VERBOSE)

def restore_overescaped(match):
    match = match.group(1)
    if match.startswith('N'):
        charname = match[3:-2]
        unicodedata.lookup(charname) # raise KeyError if undefined character name
        return '\\N{' + charname + '}'
    else:
        return {
            'a'    : '\\x07',
            'b'    : '\\x08',
            'f'    : '\\x0C',
            'v'    : '\\x0B',
        }.get(match, '\\' + match)

def t_STRING(t):
    r'''("(\\.|[^"\\])*")|('(\\.|[^'\\])*')''' # single- or double-quoted string, with escape-quote support
    value = t.value[1:-1] # remove the surrounding quotes
    value = value.replace('\\"', '"').replace("\\'", "'") # apply escaped quotes
    value = regex.escape(value, special_only=True)
    try:
        t.value = OVERESCAPED_RE.sub(restore_overescaped, value)
    except KeyError as e:
        raise OprexSyntaxError(t.lineno, e.message)
    else:
        return t


def t_VARNAME(t):
    r'[A-Za-z_][A-Za-z0-9_]*'
    t.type = reserved.get(t.value, 'VARNAME')
    return t


# Rules that contain space/tab should be written in function form and be put 
# before the t_linemark rule to make PLY calls them first.
# Otherwise t_linemark will turn the spaces/tabs into WHITESPACE token.


def t_OF(t):
    r'[ \t]+of(?=[ \t:])(?![ \t]+(--|\n))' # without this, WHITESPACE VARNAME will be produced instead, requiring making "of" a reserved keyword
    t.type = 'WHITESPACE'
    t.extra_tokens = [ExtraToken(t, 'OF', lexpos=t.lexpos + t.value.index('of'))]
    return t


def t_ANY_linemark(t):
    r'(?m)(((^|[ \t]+)--.*)|[ \t\n])+(\*\)[ \t]*)*' # comments are also captured here
    lines = t.value.split('\n')
    indentation = lines[-1] # the whitespace characters after the last newline is indentation
    has_globalmark = GLOBALMARK in indentation
    num_newlines = len(lines) - 1
    t.lexer.lineno += num_newlines

    if num_newlines == 0:
        if GLOBALMARK in t.value: # globalmark must be put at the beginning of a line, i.e. requires newline
            raise OprexSyntaxError(t.lexer.lineno, 'Syntax error: ' + t.lexer.source_lines[t.lexer.lineno-1])
        else:
            t.type = 'WHITESPACE'
            return t

    # else, num_newlines > 0
    t.type = 'NEWLINE'
    if t.lexer.mode == 'charclass': # NEWLINE ends the charclass-mode state
        t.lexer.set_mode('INITIAL')
    if endpos(t) == len(t.lexer.lexdata) and not has_globalmark: # this is a just-before-the-end-of-input whitespace
        return t                                                 # no further processing needed

    t.extra_tokens = deque() # gonna produce these extra tokens:
    # - GLOBALMARK if has_globalmark
    # - INDENT if indentation depth is more than previous line's
    # - DEDENT (can be more than one) if indentation depth is less than previous line's

    def check_indentation_char():
        if indentation == GLOBALMARK:
            raise OprexSyntaxError(t.lexer.lineno, 'Syntax error: ' + indentation)

        indent_using_space = ' ' in indentation
        indent_using_tab = '\t' in indentation
        if indent_using_space and indent_using_tab:
            raise OprexSyntaxError(t.lexer.lineno, 'Cannot mix space and tab for indentation')

        indentchar = ' ' if indent_using_space else '\t'
        try: # all indentations must use the same character
            if indentchar != t.lexer.indentchar:
                raise OprexSyntaxError(t.lexer.lineno, 'Inconsistent indentation character')
        except AttributeError: # this is the first indent encountered, record whether it uses space or tab -- further indents must use the same character
            t.lexer.indentchar = indentchar

    def pull_out_globalmark():
        if indentation.count(GLOBALMARK) > 1:
            raise OprexSyntaxError(t.lexer.lineno, 'Syntax error: ' + indentation)
        if not indentation.startswith(GLOBALMARK):
            raise OprexSyntaxError(t.lexer.lineno, "The GLOBALMARK %s must be put at the line's beginning" % GLOBALMARK)

        t.extra_tokens.append(ExtraToken(t, 'GLOBALMARK', GLOBALMARK))
        return indentation.replace(GLOBALMARK, '  ' if t.lexer.indentchar == ' ' else '')

    if indentation:
        check_indentation_char()
        if has_globalmark:
            indentation = pull_out_globalmark()

    def produce_INDENT_DEDENT():
        indentlen = len(indentation)
        prev = t.lexer.indent_stack[-1]
        if indentlen == prev: # no change in indentation depth
            return

        # else, there's indentation depth change
        if indentlen > prev: # deeper indentation, start of a new scope
            t.extra_tokens.appendleft(ExtraToken(t, 'INDENT'))
            t.lexer.indent_stack.append(indentlen)
            return

        if indentlen < prev: # end of one or more scopes
            while indentlen < prev: # close all scopes having deeper indentation
                t.extra_tokens.appendleft(ExtraToken(t, 'DEDENT'))
                t.lexer.indent_stack.pop()
                prev = t.lexer.indent_stack[-1]
            if indentlen != prev: # the indentation tries to return to a nonexistent level
                raise OprexSyntaxError(t.lexer.lineno, 'Indentation error')

    if t.lexer.mode != 'alternation':
        produce_INDENT_DEDENT()

    return t


def t_INITIAL_charclass_error(t):
    raise OprexSyntaxError(t.lineno, 'Syntax error at or near: ' + t.value.split('\n')[0])


def endpos(t):
    return t.lexpos + len(t.value)
    

def p_oprex(t):
    '''oprex : 
             | WHITESPACE
             | NEWLINE
             | NEWLINE        main_expression
             | NEWLINE INDENT main_expression DEDENT'''
    if len(t) == 3:
        flags, expression = t[2]
    elif len(t) == 5:
        flags, expression = t[3]
    else:
        flags = expression = ''

    for flag in DEFAULT_FLAGS:
        if flag not in flags:
            flags = flag + flags
    if 'V' not in flags: # use V1 by default
        flags = 'V1' + flags # put at the front so it can be easily trimmed out of the result if unwanted

    t[0] = '(?%s)%s' % (flags, expression)


def p_main_expression(t):
    '''main_expression : global_flags expression
                       | global_flags
                       | expression'''
    last = len(t) - 1
    flag = t[1] if isinstance(t[1], Flagset) else ''
    expr = t[last] if isinstance(t[last], Expression) else ''
    t[0] = flag, expr


def p_global_flags(t):
    '''global_flags : LPAREN FLAGSET RPAREN NEWLINE'''
    flags = t[2]
    root_scope = t.lexer.scopes[0]
    if 'u' in flags.turn_ons: 
        root_scope.update(
            alpha    = Variable('alpha',    CharClass(r'\p{Alphabetic}',                 is_set_op=False), lineno=0),
            upper    = Variable('upper',    CharClass(r'\p{Uppercase}',                  is_set_op=False), lineno=0),
            lower    = Variable('lower',    CharClass(r'\p{Lowercase}',                  is_set_op=False), lineno=0),
            alnum    = Variable('alnum',    CharClass(r'\p{Alphanumeric}',               is_set_op=False), lineno=0),
            linechar = Variable('linechar', CharClass(r'[\r\n\x0B\x0C\x85\u2028\u2029]', is_set_op=False), lineno=0),
        )
        t.lexer.flag_dependent_builtins = FLAG_DEPENDENT_BUILTINS.copy()
        t.lexer.flag_dependent_builtins['w'] = t.lexer.flag_dependent_builtins['w'].copy()
        t.lexer.flag_dependent_builtins['w'][True] = [
            root_scope['linechar']
        ]
    flags_redef_builtins(t, flags, root_scope)
    t[0] = flags


def p_expression(t):
    '''expression : string_expr
                  | lookup_expr
                  | flagged_expr
                  | quantified_expr'''
    t[0] = t[1]


def p_string_expr(t):
    '''string_expr : str_b STRING str_b NEWLINE'''
    t[0] = Expression(t[1] + t[2] + t[3])


def p_str_b(t):
    '''str_b :
             | DOT
             | UNDERSCORE'''
    t[0] = {
        None : '',
        '.'  : '\\b',
        '_'  : '\\B',
    }[t[len(t)-1]]


def p_quantified_expr(t):
    '''quantified_expr : quantifier WHITESPACE expression
                       | quantifier COLON      charclass'''
    t[0] = quantify(t[3], quantifier=t[1])


def p_quantifier(t):
    '''quantifier : repeat_N_times
                  | repeat_range
                  | optionalize'''
    quant = t[1]
    base = {
        '{1}'   : '',
        '{,}'   : '*',
        '{0,}'  : '*',
        '{1,}'  : '+',
        '{,1}'  : '?',
        '{0,1}' : '?',
    }.get(quant.base, quant.base)
    modifier = quant.modifier if base else ''
    t[0] = base + modifier


def p_repeat_N_times(t):
    '''repeat_N_times : NUMBER of'''
    number = t[1]
    t[0] = Quantifier(base=('{%s}' % number), modifier='')


def p_repeat_range(t):
    '''repeat_range : numrange of
                    | numrange backtrack MINUS of
                    | NUMBER   backtrack PLUS  DOT DOT of
                    | NUMBER   backtrack PLUS  DOT DOT NUMBER of'''
    possessive = len(t) == 3 # the first form above
    greedy     = len(t) == 5 # the second form
    lazy       = not possessive and not greedy # third & fourth forms

    if lazy:
        min = t[1]
        max = t[6] if len(t) == 8 else ''
    else:
        min, max = t[1]

    if not min:
        min = '0'
    if max and int(max) <= int(min):
        raise OprexSyntaxError(t.lineno(0), 'Repeat max must be > min')

    t[0] = Quantifier(
        base='{%s,%s}' % ('' if min == '0' else min, max),
        modifier='+' if possessive else '?' if lazy else ''
    )


def p_backtrack(t):
    '''backtrack : WHITESPACE LT LT'''


def p_of(t):
    '''of : WHITESPACE OF'''


def p_numrange(t):
    '''numrange :        DOT DOT
                | NUMBER DOT DOT
                |        DOT DOT NUMBER
                | NUMBER DOT DOT NUMBER'''
    def number_or_empty(str):
        return str if str != '.' else ''
    min = number_or_empty(t[1])
    max = number_or_empty(t[len(t)-1])
    t[0] = min, max


def p_optionalize(t):
    '''optionalize : QUESTMARK of'''
    t[0] = Quantifier(base='?', modifier='+')


def quantify(expr, quantifier):
    if quantifier == '{0}' or expr == '':
        return Expression('')
    if quantifier == '{1}' or quantifier == '':
        return expr

    def merge_quantifiers():
        try:
            return {               # The purpose of this is so we can write x* as (x+)? e.g.
                 '? of +'  : '*' , #     digits?
                '?+ of ++' : '*+', #         digits = 1.. of digit
                '?? of +?' : '*?', # without making the regex output suboptimal
            }[quantifier + ' of ' + expr.quantifier]
        except KeyError: # not a "? of +" operation, try merge repeats e.g.
            n1 = int(expr.quantifier.strip('{').strip('}')) # colorhex = 3 of byte
            n2 = int(     quantifier.strip('{').strip('}')) #     byte = 2 of hex
            return '{%d}' % (n1 * n2)                       # --> optimize "hex{2}{3}" into "hex{6}"

    def strip_old_quantifier():
        return expr[:-len(expr.quantifier)]

    def put_in_group():
        unneeded = (
            expr.grouped # already
            or len(expr) == 1
            or isinstance(expr, CharClass)
            or ESCAPE_SEQUENCE_RE.fullmatch(expr)
        )
        if unneeded:
            return expr # unchanged
        else:
            return '(?:%s)' % expr

    try:
        return Expression(strip_old_quantifier(), modifier=merge_quantifiers())
    except:
        return Expression(put_in_group(), modifier=quantifier)


def p_alternation_expr(t):
    '''alternation_expr : ALTBEGIN NEWLINE alternatives ALTEND'''


def p_alternatives(t):
    '''alternatives : alternative
                    | alternative alternatives'''


def p_alternative(t):
    '''alternative : OR'''


def p_flagged_expr(t):
    '''flagged_expr : scoped_flags expression'''
    flags = t[1]
    t[0] = Expression(t[2], modifier='(?%s:' % flags)


def p_scoped_flags(t):
    '''scoped_flags : LPAREN FLAGSET RPAREN WHITESPACE'''
    flags = t[2]
    for flag_name, global_flag in Flagset.globals.iteritems():
        if global_flag in flags.turn_ons:
            raise OprexSyntaxError(t.lineno(2), "'%s' is a global flag and must be set using global flag syntax, not scoped." % flag_name)
    flags_redef_builtins(t, flags, begin_scope(t, Scope.FLAGSCOPE))
    t[0] = flags


def p_lookup_expr(t):
    '''lookup_expr : lookup             NEWLINE optional_block
                   | SLASH lookup_chain NEWLINE optional_block'''
    referenced_vars = set()
    current_scope = t.lexer.scopes[-1]
    def resolve_var(lookup):
        referenced_vars.add(lookup.varname)
        try:
            var = current_scope[lookup.varname]
        except KeyError:
            raise OprexSyntaxError(t.lineno(0), "'%s' is not defined" % lookup.varname)
        if lookup.optional:
            return quantify(var.value, quantifier=lookup.optional)
        else:
            return var.value

    def resolve(lookup):
        if isinstance(lookup, VariableLookup):
            return resolve_var(lookup)
        elif isinstance(lookup, Backreference): 
            t.lexer.backreferences.add(lookup)
            return '(?P=%s)%s' % (lookup.varname, lookup.optional)
        elif isinstance(lookup, SubroutineCall): 
            t.lexer.subroutine_calls.add(lookup)
            return '(?&%s)%s' % (lookup.varname, lookup.optional)

    if t[1] == '/': # chain of lookups
        t[0] = Expression(''.join(map(resolve, t[2])))
    else: # single lookup
        t[0] = resolve(t[1])
    end_scope(t, optional_block=t[len(t)-1], referenced_vars=referenced_vars)


def p_lookup_chain(t):
    '''lookup_chain : lookup SLASH
                    | lookup SLASH lookup_chain'''
    try:
        t[0] = t[3]
    except IndexError:
        t[0] = deque()
    t[0].appendleft(t[1])


def p_lookup(t):
    '''lookup : lookup_type
              | lookup_type QUESTMARK'''
    LookupClass, varname = t[1]
    has_questmark = len(t) == 3
    t[0] = LookupClass(varname, t.lineno(1), optional='?+' if has_questmark else '')


def p_lookup_type(t):
    '''lookup_type : variable_lookup
                   | backreference
                   | subroutine_call'''
    t[0] = t[1]


def p_variable_lookup(t):
    '''variable_lookup : VARNAME
                       | UNDERSCORE
                       | DOT'''
    t[0] = VariableLookup, t[1]


def p_backreference(t):
    '''backreference : EQUALSIGN VARNAME'''
    t[0] = Backreference, t[2]


def p_subroutine_call(t):
    '''subroutine_call : AMPERSAND VARNAME'''
    t[0] = SubroutineCall, t[2]


def p_charclass(t):
    '''charclass : charitems NEWLINE optional_block'''
    items = t[1]
    
    includes = []
    def track_inclusion(item):
        includes.append(item.value.varname)

    def check_op(index, item):
        is_first = index == 0
        is_last = index == len(items)-1
        prefix = is_first and not is_last
        infix = not (is_first or is_last)

        op_type, valid_placement = {
            'not:': ('unary', prefix),
            'not' : ('binary', infix),
            'and' : ('binary', infix),
        }[item.source]

        if not valid_placement:
            raise OprexSyntaxError(t.lineno(0), "Invalid use of %s '%s' operator" % (op_type, item.source))
        
        if op_type == 'binary': # binary ops require the previous item to be non-op
            prev_item = items[index-1]
            if prev_item.type == 'op':
                raise OprexSyntaxError(t.lineno(0),  "Bad set operation '%s %s'" % (prev_item.source, item.source))              

    has_range = False
    has_set_op = False
    for index, item in enumerate(items):
        if item.type == 'include':
            track_inclusion(item)
        elif item.type == 'op':
            check_op(index, item)
            has_set_op = True
        elif item.type == 'range':
            has_range = True

    current_scope = t.lexer.scopes[-1]
    def lookup(varname):
        try:
            var = current_scope[varname]
        except KeyError as e:
            raise OprexSyntaxError(t.lineno(0), "Cannot include '%s': not defined" % e.message)
        if not isinstance(var.value, CharClass):
            raise OprexSyntaxError(t.lineno(0), "Cannot include '%s': not a character class" % varname)
        else:
            return var.value

    def value_or_lookup(item):
        value = item.value
        if isinstance(value, VariableLookup):
            value = lookup(value.varname)
            if value.startswith('[') and not value.is_set_op: # remove nested [] unless it's set-operation
                value = value[1:-1]
            elif value == '-': # inside character class, dash needs to be escaped
                value = r'\-'
            elif len(value) == 2 and value[0] == '\\' and value[1] in '$.|?*+(){}': # remove unnecessary escape
                value = value[1]
        return value

    if len(items) == 1 and items[0].type == 'include': # simple aliasing
        t[0] = lookup(items[0].value.varname)
    else:
        result = ''.join(map(value_or_lookup, items))
        if result == '\\-': # no need to escape dash outside of character class
            result = '-'
        elif len(result) == 1:
            result = regex.escape(result, special_only=True)
        elif len(items) == 2 and result.startswith(r'^\p{'): # convert ^\p{something} to \P{something}
            result = result.replace(r'^\p{', r'\P{', 1)
        elif len(items) > 1 or has_range:
            result = '[' + result + ']'
        t[0] = CharClass(result, is_set_op=has_set_op)

    end_scope(t, optional_block=t[3], referenced_vars=includes)


def p_charitems(t):
    '''charitems : WHITESPACE charitem
                 | WHITESPACE charitem charitems'''
    try:
        t[0] = t[3]
    except IndexError:
        t[0] = deque()
    t[0].appendleft(t[2])


def p_charitem(t):
    '''charitem : ranged_char
                | single_char
                | period_char'''
    t[0] = t[1]

def p_ranged_char(t):
    '''ranged_char : CHAR DOT DOT CHAR'''
    L_source, L_type, L_value = t[1]
    R_source, R_type, R_value = t[4]
    source = '%s..%s' % (L_source, R_source)
    value = '%s-%s' % (L_value, R_value)

    for type in (L_type, R_type):
        if type in ('include', 'prop'):
            raise OprexSyntaxError(t.lineno(0), 'Invalid character range: ' + source)
    try:
        regex.compile('[%s]' % value)
    except regex.error as e:
        raise OprexSyntaxError(t.lineno(0), 
            '%s compiles to [%s] which is rejected by the regex engine with error message: %s' % (source, value, e.message))

    t[0] = CharClass.Item(source, 'range', value)


def p_period_char(t):
    '''period_char : DOT'''
    t[0] = CharClass.Item('.', 'literal', '.')


def p_single_char(t):
    '''single_char : CHAR'''
    t[0] = t[1]


def p_optional_block(t):
    '''optional_block : begin_block definitions end_block
                      |'''
    if len(t) > 1:
        t[0] = t[2]


def p_begin_block(t):
    '''begin_block : INDENT'''
    begin_scope(t, Scope.BLOCKSCOPE)


def begin_scope(t, type):
    current_scope = t.lexer.scopes[-1]
    new_scope = Scope(type=type, parent_scope=current_scope)
    t.lexer.scopes.append(new_scope)
    return new_scope


def p_end_block(t):
    '''end_block : DEDENT'''
    # we don't end_scope() immediately after seeing a DEDENT because the parent expression needs the variable(s) defined in its sub-block
    # instead the parent will do the end_scope() 


def end_scope(t, optional_block, referenced_vars):
    if optional_block:
        for var in optional_block:
            if var.name not in referenced_vars:
                raise OprexSyntaxError(var.lineno, "'%s' is defined but not used (by its parent expression)" % var.name)
        t.lexer.scopes.pop()

    while t.lexer.scopes[-1].type == Scope.FLAGSCOPE:
        t.lexer.scopes.pop()


def p_definitions(t):
    '''definitions : definition
                   | definition definitions'''
    try:
        t[0] = t[1] + t[2]
    except IndexError:
        t[0] = t[1]


def p_definition(t):
    '''definition : assignment
                  | GLOBALMARK assignment'''
    if t[1] == GLOBALMARK:
        assignment = t[2]
        scopes = t.lexer.scopes # global variable, define in all scopes
    else:
        assignment = t[1]
        scopes = t.lexer.scopes[-1:] # non-global, define in the deepest (current) scope only

    def make_var(declaration, base_value):
        varname = declaration.varname
        value = base_value
        if declaration.atomic:
            value = Expression(value, modifier='(?>')
        if declaration.capture:
            value = Expression(value, modifier='(?P<%s>' % varname)
            t.lexer.captures.add(varname)
        return Variable(varname, value, assignment.lineno)

    def define(declaration):
        var = make_var(declaration, assignment.value)
        try: # check the deepest scope for varname (every scope supersets its parent, so checking only the deepeset is sufficient)
            prev_def = scopes[-1][var.name]
        except KeyError: # not already defined, OK to define it
            for scope in scopes:
                scope[var.name] = var
        else: # already defined
            raise OprexSyntaxError(t.lineno(1),
                "'%s' is a built-in variable and cannot be redefined" % var.name
                if prev_def.is_builtin() else
                    "Names must be unique within a scope, '%s' is already defined (previous definition at line %d)"
                        % (var.name, prev_def.lineno))
        return var
    t[0] = map(define, assignment.declarations)


def p_assignment(t):
    '''assignment : declaration equals assignment
                  | declaration equals expression
                  | declaration COLON  charclass'''
    declaration = t[1]
    lineno = t.lineno(1)
    if isinstance(t[3], Assignment):
        assignment = t[3]
        assignment.declarations.append(declaration)
    else:
        value = t[3]
        assignment = Assignment([declaration], value, lineno)
    t[0] = assignment


def p_equals(t):
    '''equals :            EQUALSIGN
              | WHITESPACE EQUALSIGN
              |            EQUALSIGN WHITESPACE
              | WHITESPACE EQUALSIGN WHITESPACE'''


def p_declaration(t):
    '''declaration :        VARNAME
                   | DOT    VARNAME
                   |     LT VARNAME GT
                   | DOT LT VARNAME GT'''
    capture = t[len(t)-1] == '>'
    varname = t[len(t)-2] if capture else t[len(t)-1]
    atomic  = t[1] == '.'
    t[0] = VariableDeclaration(varname, capture, atomic)


def p_error(t):
    if t is None:
        raise OprexSyntaxError(None, 'Unexpected end of input')

    if t.type == 'INDENT':
        raise OprexSyntaxError(t.lineno, 'Unexpected INDENT')

    errline = t.lexer.source_lines[t.lineno - 1]
    pointer = ' ' * (find_column(t)-1) + '^'
    raise OprexSyntaxError(t.lineno, 'Unexpected %s\n%s\n%s' % (t.type, errline, pointer))


def find_column(t):
    last_newline = t.lexer.lexdata.rfind('\n', 0, t.lexpos)
    if last_newline < 0:
        last_newline = 0
    return t.lexpos - last_newline


lexer0 = lex.lex()
def build_lexer(source_lines):
    lexer = lexer0.clone()
    lexer.source_lines = source_lines
    lexer.input('\n'.join(source_lines)) # all newlines are now just \n, simplifying the lexer
    lexer.indent_stack = [0] # for keeping track of indentation depths
    lexer.captures = set()
    lexer.backreferences = set()
    lexer.subroutine_calls = set()
    lexer.flag_dependent_builtins = FLAG_DEPENDENT_BUILTINS
    lexer.scopes = [Scope(type=Scope.ROOTSCOPE, parent_scope=None)]

    root_scope = lexer.scopes[0]
    for var in BUILTINS:
        root_scope[var.name] = var

    return CustomLexer(lexer)


class CustomLexer:
    def __init__(self, real_lexer):
        real_lexer.mode = 'INITIAL'
        def set_mode(mode):
            real_lexer.mode = mode
            real_lexer.begin(mode)
        real_lexer.set_mode = set_mode
        self.__dict__ = real_lexer.__dict__
        self.real_lexer = real_lexer
        self.tokens = deque()

    def get_next_token(self):
        try:
            return self.tokens.popleft()
        except IndexError:
            lexer = self.real_lexer
            token = lexer.token()
            if token:
                self.tokens.append(token)
                if hasattr(token, 'extra_tokens'):
                    self.tokens.extend(token.extra_tokens)
            else:
                extra_dedent = LexToken('DEDENT', 'EOF', len(lexer.source_lines), len(lexer.lexdata), lexer)
                num_undedented = len(lexer.indent_stack) - 1
                self.tokens.extend([extra_dedent] * num_undedented)
                self.tokens.append(None)
            return self.get_next_token()

    def token(self):
        token = self.get_next_token()
        # print token
        return token


parser = yacc.yacc()
def parse(lexer):
    return unicode(parser.parse(lexer=lexer, tracking=True))


def check_captures(lexer):
    def check(type, lookups):
        for lookup in lookups:
            if lookup.varname not in lexer.captures:
                errmsg = "Invalid %s: '%s' is not defined/not a capture" % (type, lookup.varname)
                raise OprexSyntaxError(lookup.lineno, errmsg)
    check('subroutine call', lexer.subroutine_calls)
    check('backreference', lexer.backreferences)


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument('path/to/source/file')
    argparser.add_argument('--encoding', help='encoding of the source file')
    args = argparser.parse_args()

    source_file = getattr(args, 'path/to/source/file')
    default_encoding = 'utf-8'
    encoding = args.encoding or default_encoding

    with codecs.open(source_file, 'r') as f:
        source_code = f.read()

    print oprex(source_code)
