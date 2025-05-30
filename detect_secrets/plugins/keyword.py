"""
This code was extracted in part from
https://github.com/PyCQA/bandit. Using similar heuristic logic,
we adapted it to fit our plugin infrastructure, to create an organized,
concerted effort in detecting all type of secrets in code.

Copyright (c) 2014 Hewlett-Packard Development Company, L.P.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
from __future__ import annotations

import re
from typing import Any
from typing import Dict
from typing import Generator
from typing import Optional
from typing import Pattern
from typing import Set

from ..core.potential_secret import PotentialSecret
from ..util.filetype import determine_file_type
from ..util.filetype import FileType
from .base import BasePlugin
from detect_secrets.util.code_snippet import CodeSnippet


# Note: All values here should be lowercase
DENYLIST = (
    'api[_\\.\\-]?key',
    'auth_?key',
    'service_?key',
    'account_?key',
    'db_?key',
    'database_?key',
    'priv_?key',
    'private_?key',
    'client_?key',
    'db_?pass',
    'database_?pass',
    'key_?pass',
    'password',
    'passwd',
    'token',
    '_pass\\b',
    'pwd',
    'secret',
    'contraseña',
    'contrasena',
    'recaptcha_.*key',
    'nessus_?key',
)
ALLOWLIST = (
    'publickeytoken',
    'tokenendpoint',
    'secretname',
    'keyvaultsecretname',
    'maxInvalidPasswordAttempts',
    'PasswordType',
    'forwardWindowsAuthToken',
    'saveBootstrapTokens',
    'AntiXsrfTokenKey',
    'savePWD',
    'userPWD',
    'example',
)
# Includes ], ', " as closing
CLOSING = r'[]\'"]{0,2}'
AFFIX_REGEX = r'\w*'
DENYLIST_REGEX = r'|'.join(DENYLIST)
# Support for suffix after keyword i.e. password_secure = "value"
DENYLIST_REGEX = r'({denylist}){suffix}'.format(
    denylist=DENYLIST_REGEX,
    suffix=AFFIX_REGEX,
)
# Support for prefix and suffix with keyword, needed for reverse comparisons
# i.e. if ("value" == my_password_secure) {}
DENYLIST_REGEX_WITH_PREFIX = r'{prefix}{denylist}'.format(
    prefix=AFFIX_REGEX,
    denylist=DENYLIST_REGEX,
)
# Non-greedy match
OPTIONAL_WHITESPACE = r'\s*'
OPTIONAL_NON_WHITESPACE = r'[^\s]{0,50}?'
QUOTE = r'[\'"`]'
# Secret regex details:
#   (?=[^\v\'"]*)   ->  this section match with every character except line breaks and quotes. This
#                       allows to find secrets that starts with symbols or alphanumeric characters.
#
#   (?=\w+)     ->  this section match only with words (letters, numbers or _ are allowed), and at
#                   least one character is required. This allows to reduce the false positives
#                   number.
#
#   [^\v\'"]*   ->  this section match with every character except line breaks and quotes. This
#                   allows to find secrets with symbols at the end.
#
#   [^\v,\'"`]  ->  this section match with the last secret character that can be everything except
#                   line breaks, comma, backticks or quotes. This allows to reduce the false
#                   positives number and to prevent errors in the code snippet highlighting.

# '$' sign is being used for variable rendering. That why it's not here.
SECRET = r'(?=[^\v\'\"]*)(?=[a-zA-Z0-9_!@#%^&])[^\v\'\"]*[^\v,\'\"`]'
SQUARE_BRACKETS = r'(\[[0-9]*\])'

FOLLOWED_BY_COLON_EQUAL_SIGNS_REGEX = re.compile(
    # e.g. my_password := "bar" or my_password := bar
    r'{denylist}({closing})?{whitespace}:=?{whitespace}({quote}?)({secret})(\3)'.format(
        denylist=DENYLIST_REGEX,
        closing=CLOSING,
        quote=QUOTE,
        whitespace=OPTIONAL_WHITESPACE,
        secret=SECRET,
    ),
    flags=re.IGNORECASE,
)
FOLLOWED_BY_COLON_REGEX = re.compile(
    # e.g. api_key: foo
    r'{denylist}({closing})?:{whitespace}({quote}?)({secret})(\3)'.format(
        denylist=DENYLIST_REGEX,
        closing=CLOSING,
        quote=QUOTE,
        whitespace=OPTIONAL_WHITESPACE,
        secret=SECRET,
    ),
    flags=re.IGNORECASE,
)

FOLLOWED_BY_COLON_QUOTES_REQUIRED_REGEX = re.compile(
    # e.g. api_key: "foo"
    r'{denylist}({closing})?:({whitespace})({quote})({secret})(\4)'.format(
        denylist=DENYLIST_REGEX,
        closing=CLOSING,
        quote=QUOTE,
        whitespace=OPTIONAL_WHITESPACE,
        secret=SECRET,
    ),
    flags=re.IGNORECASE,
)
FOLLOWED_BY_EQUAL_SIGNS_OPTIONAL_BRACKETS_OPTIONAL_AT_SIGN_QUOTES_REQUIRED_REGEX = re.compile(
    # e.g. my_password = "bar"
    # e.g. my_password = @"bar"
    # e.g. my_password[] = "bar";
    # e.g. char my_password[25] = "bar";
    r'{denylist}({square_brackets})?{optional_whitespace}[!=]{{1,2}}{optional_whitespace}(@)?(")({secret})(\5)'.format(
        denylist=DENYLIST_REGEX,
        square_brackets=SQUARE_BRACKETS,
        optional_whitespace=OPTIONAL_WHITESPACE,
        secret=SECRET,
    ),
    flags=re.IGNORECASE,
)
FOLLOWED_BY_OPTIONAL_ASSIGN_QUOTES_REQUIRED_REGEX = re.compile(
    # e.g. std::string secret("bar");
    # e.g. secret.assign("bar",17);
    r'{denylist}(.assign)?\((")({secret})(\3)'.format(
        denylist=DENYLIST_REGEX,
        secret=SECRET,
    ),
)
FOLLOWED_BY_EQUAL_SIGNS_REGEX = re.compile(
    # e.g. my_password = bar
    # e.g. my_password == "bar" or my_password != "bar" or my_password === "bar"
    # or my_password !== "bar"
    # e.g. my_password == 'bar' or my_password != 'bar' or my_password === 'bar'
    # or my_password !== 'bar'
    r'{denylist}({closing})?{whitespace}(={{1,3}}|!==?){whitespace}({quote}?)({secret})(\4)'.format(
        denylist=DENYLIST_REGEX,
        closing=CLOSING,
        quote=QUOTE,
        whitespace=OPTIONAL_WHITESPACE,
        secret=SECRET,
    ),
    flags=re.IGNORECASE,
)
FOLLOWED_BY_EQUAL_SIGNS_QUOTES_REQUIRED_REGEX = re.compile(
    # e.g. my_password = "bar"
    # e.g. my_password == "bar" or my_password != "bar" or my_password === "bar"
    # or my_password !== "bar"
    # e.g. my_password == 'bar' or my_password != 'bar' or my_password === 'bar'
    # or my_password !== 'bar'
    r'{denylist}({closing})?{whitespace}(={{1,3}}|!==?){whitespace}({quote})({secret})(\4)'.format(
        denylist=DENYLIST_REGEX,
        closing=CLOSING,
        quote=QUOTE,
        whitespace=OPTIONAL_WHITESPACE,
        secret=SECRET,
    ),
    flags=re.IGNORECASE,
)
PRECEDED_BY_EQUAL_COMPARISON_SIGNS_QUOTES_REQUIRED_REGEX = re.compile(
    # e.g. "bar" == my_password or "bar" != my_password or "bar" === my_password
    # or "bar" !== my_password
    # e.g. 'bar' == my_password or 'bar' != my_password or 'bar' === my_password
    # or 'bar' !== my_password
    r'({quote})({secret})(\1){whitespace}[!=]{{2,3}}{whitespace}{denylist}'.format(
        denylist=DENYLIST_REGEX_WITH_PREFIX,
        quote=QUOTE,
        whitespace=OPTIONAL_WHITESPACE,
        secret=SECRET,
    ),
)
FOLLOWED_BY_QUOTES_AND_SEMICOLON_REGEX = re.compile(
    # e.g. private_key "something";
    r'{denylist}{nonWhitespace}{whitespace}({quote})({secret})(\2);'.format(
        denylist=DENYLIST_REGEX,
        nonWhitespace=OPTIONAL_NON_WHITESPACE,
        quote=QUOTE,
        whitespace=OPTIONAL_WHITESPACE,
        secret=SECRET,
    ),
    flags=re.IGNORECASE,
)
FOLLOWED_BY_ARROW_FUNCTION_SIGN_QUOTES_REQUIRED_REGEX = re.compile(
    # e.g. my_password => "bar" or my_password => bar
    r'{denylist}({closing})?{whitespace}=>?{whitespace}({quote})({secret})(\3)'.format(
        denylist=DENYLIST_REGEX,
        closing=CLOSING,
        quote=QUOTE,
        whitespace=OPTIONAL_WHITESPACE,
        secret=SECRET,
    ),
    flags=re.IGNORECASE,
)
DATA_PUT_PASSWORD_REGEX = re.compile(
    # Matches patterns like data.put("password", "bar") or data.put('password', 'bar')
    r'data\.put\({whitespace}{quote}{denylist}{quote}{whitespace},{whitespace}{quote}({secret}){quote}{whitespace}\)'.format(
        denylist=DENYLIST_REGEX_WITH_PREFIX,
        quote=QUOTE,
        whitespace=OPTIONAL_WHITESPACE,
        secret=SECRET,
    ),
    re.IGNORECASE,
)
CONFIG_DENYLIST_REGEX_TO_GROUP = {
    FOLLOWED_BY_COLON_REGEX: 4,
    PRECEDED_BY_EQUAL_COMPARISON_SIGNS_QUOTES_REQUIRED_REGEX: 2,
    FOLLOWED_BY_EQUAL_SIGNS_REGEX: 5,
    FOLLOWED_BY_QUOTES_AND_SEMICOLON_REGEX: 3,
}
GOLANG_DENYLIST_REGEX_TO_GROUP = {
    FOLLOWED_BY_COLON_EQUAL_SIGNS_REGEX: 4,
    PRECEDED_BY_EQUAL_COMPARISON_SIGNS_QUOTES_REQUIRED_REGEX: 2,
    FOLLOWED_BY_EQUAL_SIGNS_REGEX: 5,
    FOLLOWED_BY_QUOTES_AND_SEMICOLON_REGEX: 3,
}
COMMON_C_DENYLIST_REGEX_TO_GROUP = {
    FOLLOWED_BY_EQUAL_SIGNS_OPTIONAL_BRACKETS_OPTIONAL_AT_SIGN_QUOTES_REQUIRED_REGEX: 6,
}
C_PLUS_PLUS_REGEX_TO_GROUP = {
    FOLLOWED_BY_OPTIONAL_ASSIGN_QUOTES_REQUIRED_REGEX: 4,
    FOLLOWED_BY_EQUAL_SIGNS_QUOTES_REQUIRED_REGEX: 5,
}
QUOTES_REQUIRED_DENYLIST_REGEX_TO_GROUP = {
    FOLLOWED_BY_COLON_QUOTES_REQUIRED_REGEX: 5,
    PRECEDED_BY_EQUAL_COMPARISON_SIGNS_QUOTES_REQUIRED_REGEX: 2,
    FOLLOWED_BY_EQUAL_SIGNS_QUOTES_REQUIRED_REGEX: 5,
    FOLLOWED_BY_QUOTES_AND_SEMICOLON_REGEX: 3,
    FOLLOWED_BY_ARROW_FUNCTION_SIGN_QUOTES_REQUIRED_REGEX: 4,
    DATA_PUT_PASSWORD_REGEX: 2,
}

TERRAFORM_DENYLIST_REGEX_TO_GROUP = {
    **QUOTES_REQUIRED_DENYLIST_REGEX_TO_GROUP,
    FOLLOWED_BY_EQUAL_SIGNS_REGEX: 5,
}

REGEX_BY_FILETYPE = {
    FileType.GO: GOLANG_DENYLIST_REGEX_TO_GROUP,
    FileType.OBJECTIVE_C: COMMON_C_DENYLIST_REGEX_TO_GROUP,
    FileType.C_SHARP: COMMON_C_DENYLIST_REGEX_TO_GROUP,
    FileType.C: COMMON_C_DENYLIST_REGEX_TO_GROUP,
    FileType.C_PLUS_PLUS: C_PLUS_PLUS_REGEX_TO_GROUP,
    FileType.CLS: QUOTES_REQUIRED_DENYLIST_REGEX_TO_GROUP,
    FileType.JAVA: QUOTES_REQUIRED_DENYLIST_REGEX_TO_GROUP,
    FileType.JAVASCRIPT: QUOTES_REQUIRED_DENYLIST_REGEX_TO_GROUP,
    FileType.PYTHON: QUOTES_REQUIRED_DENYLIST_REGEX_TO_GROUP,
    FileType.SWIFT: QUOTES_REQUIRED_DENYLIST_REGEX_TO_GROUP,
    FileType.TERRAFORM: TERRAFORM_DENYLIST_REGEX_TO_GROUP,
    FileType.JSON: QUOTES_REQUIRED_DENYLIST_REGEX_TO_GROUP,
    FileType.YAML: CONFIG_DENYLIST_REGEX_TO_GROUP,
    FileType.CONFIG: CONFIG_DENYLIST_REGEX_TO_GROUP,
    FileType.INI: CONFIG_DENYLIST_REGEX_TO_GROUP,
    FileType.PROPERTIES: CONFIG_DENYLIST_REGEX_TO_GROUP,
    FileType.TOML: CONFIG_DENYLIST_REGEX_TO_GROUP,
}


class KeywordDetector(BasePlugin):
    """
    Scans for secret-sounding variable names.

    This checks if denylisted keywords are present in the analyzed string.
    """
    secret_type = 'Secret Keyword'

    def __init__(self, keyword_exclude: Optional[str] = None) -> None:
        self.keyword_exclude = None
        if keyword_exclude:
            self.keyword_exclude = re.compile(
                keyword_exclude,
                re.IGNORECASE,
            )

    def analyze_string(
        self,
        string: str,
        denylist_regex_to_group: Optional[Dict[Pattern, int]] = None,
    ) -> Generator[str, None, None]:
        if any(allowed.lower() in string.lower() for allowed in ALLOWLIST):
            return

        if self.keyword_exclude and self.keyword_exclude.search(string):
            return

        if denylist_regex_to_group is None:
            attempts = [
                QUOTES_REQUIRED_DENYLIST_REGEX_TO_GROUP,
            ]
        else:
            attempts = [denylist_regex_to_group]

        has_results = False
        for denylist_regex_to_group in attempts:
            for denylist_regex, group_number in denylist_regex_to_group.items():
                match = denylist_regex.search(string)
                if match:
                    has_results = True
                    yield match.group(group_number)

            if has_results:
                break

    def analyze_line(
        self,
        filename: str,
        line: str,
        line_number: int = 0,
        context: CodeSnippet | None = None,
        raw_context: CodeSnippet | None = None,
        **kwargs: Any,
    ) -> Set[PotentialSecret]:
        filetype = determine_file_type(filename)
        denylist_regex_to_group = REGEX_BY_FILETYPE.get(filetype, QUOTES_REQUIRED_DENYLIST_REGEX_TO_GROUP)  # noqa: E501
        return super().analyze_line(
            filename=filename,
            line=line,
            line_number=line_number,
            context=context,
            raw_context=raw_context,
            denylist_regex_to_group=denylist_regex_to_group,
        )

    def json(self) -> Dict[str, Any]:
        return {
            'keyword_exclude': (
                self.keyword_exclude.pattern
                if self.keyword_exclude
                else ''
            ),
            **super().json(),
        }
