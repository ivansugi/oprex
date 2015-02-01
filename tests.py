# -*- coding: utf-8 -*-

import unittest, regex
from oprex import oprex, OprexSyntaxError

class TestErrorHandling(unittest.TestCase):
    def given(self, oprex_source, expect_error):
        try:
            oprex(oprex_source)
        except Exception as err:
            got_error = err.message
        else:
            got_error = ''

        if got_error != expect_error:
            msg = 'For input: %s\n----------------------------- Got Error: -----------------------------\n%s\n\n-------------------------- Expected Error: ---------------------------\n%s'
            raise AssertionError(msg % (
                oprex_source or '(empty string)', 
                got_error or '(no error)', 
                expect_error or '(no error)',
            ))


    def test_white_guards(self):
        self.given('one-liner input',
        expect_error='''Line 1: First line must be blank, not: one-liner input''')

        self.given('''something in the first line
        ''',
        expect_error='Line 1: First line must be blank, not: something in the first line')

        self.given('''
        something in the last line''',
        expect_error='Line 2: Last line must be blank, not:         something in the last line')


    def test_unknown_symbol(self):
        self.given('''
            `@#$%^&;{}[]\\
        ''',
        expect_error='Line 2: Unsupported syntax: `@#$%^&;{}[]\\')


    def test_unexpected_token(self):
        self.given('''
            /to/be/?
        ''',
        expect_error='''Line 2: Unexpected QUESTION
            /to/be/?
                   ^''')


    def test_mixed_indentation(self):
        self.given('''
            \tthis_line_mixes_tab_and_spaces_for_indentation
        ''',
        expect_error='Line 2: Cannot mix space and tab for indentation')

        self.given('''
            /tabs/vs/spaces/
\t\ttabs = 'this line is tabs-indented'
                spaces = 'this line is spaces-indented'
        ''',
        expect_error='Line 3: Cannot mix space and tab for indentation')


    def test_undefined_variable(self):
        self.given('''
            bigfoot
        ''',
        expect_error="Line 2: Variable 'bigfoot' is not defined")

        self.given('''
            /horses/and/unicorns/
                horses = 'Thoroughbreds'
                and = ' and '
        ''',
        expect_error="Line 2: Variable 'unicorns' is not defined")

        self.given('''
            /unicorns/and/horses/
                horses = 'Thoroughbreds'
                and = ' and '
        ''',
        expect_error="Line 2: Variable 'unicorns' is not defined")


    def test_illegal_variable_name(self):
        self.given('''
            101dalmatians
        ''',
        expect_error='Line 2: Illegal variable name (must start with a letter): 101dalmatians')

        self.given('''
            _this_
        ''',
        expect_error='Line 2: Illegal variable name (must start with a letter): _this_')

        self.given('''
            etc_
        ''',
        expect_error='Line 2: Illegal variable name (must not end with underscore): etc_')


    def test_duplicate_variable(self):
        self.given('''
            dejavu
                dejavu = 'Déjà vu'
                dejavu = 'Déjà vu'
        ''',
        expect_error="Line 4: Variable 'dejavu' already defined (names must be unique within a scope)")


    def test_unclosed_literal(self):
        self.given('''
            mcd
                mcd = 'McDonald's
        ''',
        expect_error='''Line 3: Missing closing quote: 'McDonald's''')

        self.given('''
            quotes_mismatch
                quotes_mismatch = "'
        ''',
        expect_error="""Line 3: Missing closing quote: "'""")


class TestOutput(unittest.TestCase):
    def given(self, oprex_source, expect_regex):
        regex_source = oprex(oprex_source)
        if regex_source != expect_regex:
            msg = 'For input: %s\n---------------------------- Got Output: -----------------------------\n%s\n\n------------------------- Expected Output: ---------------------------\n%s'
            raise AssertionError(msg % (
                oprex_source or '(empty string)', 
                regex_source or '(empty string)', 
                expect_regex or '(empty string)',
            ))


    def test_empties(self):
        self.given('',
        expect_regex='')

        self.given('''
        ''',
        expect_regex='')

        self.given('''

        ''',
        expect_regex='')
        self.given('''


        ''',
        expect_regex='')


class TestMatches(unittest.TestCase):
    def given(self, oprex_source, expect_full_match, no_match=[], partial_match={}):
        regex_source = oprex(oprex_source)
        for text in expect_full_match:
            match = regex.match(regex_source, text)
            partial = match and match.group(0) != text
            if not match or partial:
                raise AssertionError('%s\nis expected to fully match: %s\n%s\nThe regex is: %s' % (
                    oprex_source or '(empty string)', 
                    text or '(empty string)', 
                    'It does match, but only partially. The match is: ' + (match.group(0) or '(empty string)') if partial else "But it doesn't match at all.",
                    regex_source or '(empty string)',
                ))

        for text in no_match:
            match = regex.match(regex_source, text)
            if match:
                raise AssertionError('%s\nis expected NOT to match: %s\n%s\nThe regex is: %s' % (
                    oprex_source or '(empty string)', 
                    text or '(empty string)', 
                    'But it does match. The match is: ' + (match.group(0) or '(empty string)'),
                    regex_source or '(empty string)',
                ))


        for text, partmatch in partial_match.iteritems():
            match = regex.match(regex_source, text)
            partial = match and match.group(0) != text and match.group(0) == partmatch
            if not match or not partial:
                raise AssertionError('%s\nis expected to partially match: %s\n%s\nThe regex is: %s' % (
                    oprex_source or '(empty string)', 
                    text or '(empty string)', 
                    "But it doesn't match at all." if not match else 'The expected partial match is: %s\nBut the resulting match is: %s' % (
                        partmatch or '(empty string)', 
                        match.group(0) or '(empty string)'
                    ),
                    regex_source or '(empty string)',
                ))


    def test_simple_optional(self):
        self.given('''
            /a?/ether/
                ether = /e/ther/
                    e = 'e'
                    ther = 'ther'
                a = 'a'
            ''',
            expect_full_match=['ether', 'aether'],
        )

        self.given('''
            /air/man?/ship?/
                air = 'air'
                man = 'man'
                ship = 'ship'
            ''',
            expect_full_match=['air', 'airman', 'airship', 'airmanship'],
            no_match=['manship'],
            partial_match={'airma' : 'air'},
        )

        self.given('''
            /ultra?/nagog/
                ultra = "ultra"
                nagog = 'nagog'
            ''',
            expect_full_match=['ultranagog', 'nagog'],
            no_match=['ultrnagog'],
        )

        self.given('''
            /cat?/fish?/
                cat  = 'cat'
                fish = 'fish'
            ''',
            expect_full_match=['catfish', 'cat', 'fish', ''],
            partial_match={
                'catfishing' : 'catfish', 
                'cafis' : '',
            }
        )

        self.given('''
            /very?/very?/nice/
                very = 'very '
                nice = "nice"
            ''',
            expect_full_match=['nice', 'very nice', 'very very nice'],
        )


    def test_escaping(self):
        self.given('''
            orly
                orly = "O RLY?"
            ''',
            expect_full_match=['O RLY?'],
            no_match=['O RLY', 'O RL'],
        )


if __name__ == '__main__':
    unittest.main()
