import os
import re
import sys
from collections import namedtuple

# --- AST Node -------------------------------------------------------------
class ASTNode:
    def __init__(self, nodetype, token=None, children=None):
        self.nodetype = nodetype
        self.token    = token
        self.children = children or []
    def __repr__(self, level=0):
        indent = '  ' * level
        s = f"{indent}{self.nodetype}"
        if self.token and hasattr(self.token, 'lexeme'):
            s += f": {self.token.lexeme}"
        for c in self.children:
            if isinstance(c, ASTNode):
                s += "\n" + c.__repr__(level+1)
        return s

# --- Token ---------------------------------------------------------------
Token = namedtuple('Token', ['type','lexeme','line','col'])

# --- Loader --------------------------------------------------------------
def load_tokens(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Could not find tokens file '{path}'")
    tokens = []
    line_col_re = re.compile(r"line=(\d+), col=(\d+)\)")
    token_re    = re.compile(r"Token\((?P<type>[^,]+),\s*'(?P<lex>.*?)',.*line=\d+,\s*col=\d+\)")
    with open(path, encoding='utf-8') as f:
        for line in f:
            m1 = line_col_re.search(line)
            m2 = token_re.search(line)
            if m1 and m2:
                ttype   = m2.group('type')
                lexeme  = m2.group('lex')
                line_no = int(m1.group(1))
                col_no  = int(m1.group(2))
                tokens.append(Token(ttype, lexeme, line_no, col_no))
    tokens = [t for t in tokens if t.type not in ('T_Whitespace','T_Comment')]
    last   = tokens[-1] if tokens else Token('','',0,0)
    tokens.append(Token('T_EOF','', last.line, last.col+1))
    return tokens