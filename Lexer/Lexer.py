from enum import Enum, auto
import os
import sys

class TokenType(Enum):
    # Keywords
    T_Bool = auto()
    T_Break = auto()
    T_Continue = auto()
    T_Else = auto()
    T_False = auto()
    T_Fn = auto()
    T_Int = auto()
    T_If = auto()
    T_Let = auto()
    T_Loop = auto()
    T_Mut = auto()
    T_Print = auto()   # println!
    T_Return = auto()
    T_True = auto()

    # Arithmetic Operators
    T_AOp_Trust = auto()  # +
    T_AOp_MN = auto()     # -
    T_AOp_ML = auto()     # *
    T_AOp_DV = auto()     # /
    T_AOp_RM = auto()     # %

    # Relational Operators
    T_ROp_L = auto()      # <
    T_ROp_G = auto()      # >
    T_ROp_LE = auto()     # <=
    T_ROp_GE = auto()     # >=
    T_ROp_NE = auto()     # !=
    T_ROp_E = auto()      # ==

    # Logical Operators
    T_LOp_AND = auto()    # &&
    T_LOp_OR = auto()     # ||
    T_LOp_NOT = auto()    # !

    # Assignment and type/operator symbols
    T_Assign = auto()     # =
    T_Colon = auto()      # :
    T_Arrow = auto()      # ->

    # Delimiters
    T_LP = auto()         # (
    T_RP = auto()         # )
    T_LC = auto()         # {  (Left Curly)
    T_RC = auto()         # }  (Right Curly)
    T_LB = auto()         # [
    T_RB = auto()         # ]
    T_Semicolon = auto()  # ;
    T_Comma = auto()      # ,

    # Literals & identifiers
    T_Id = auto()
    T_Decimal = auto()
    T_Hexadecimal = auto()
    T_String = auto()
    T_Comment = auto()
    T_Whitespace = auto()

    # End-of-file
    T_EOF = auto()

class Token:
    def __init__(self, type_: TokenType, lexeme: str, literal=None, line: int = 0, column: int = 0):
        self.type = type_
        self.lexeme = lexeme
        self.literal = literal
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type.name}, '{self.lexeme}', {self.literal}, line={self.line}, col={self.column})"

class LexerError(Exception):
    pass

class SymbolTable:
    """
    A simple symbol table to record identifiers with their positions.
    """
    def __init__(self):
        self.symbols = {}

    def add(self, name: str, position: tuple):
        if name not in self.symbols:
            self.symbols[name] = {'name': name, 'positions': []}
        self.symbols[name]['positions'].append(position)

class Lexer:
    KEYWORDS = {
        'bool': TokenType.T_Bool,
        'break': TokenType.T_Break,
        'continue': TokenType.T_Continue,
        'else': TokenType.T_Else,
        'false': TokenType.T_False,
        'fn': TokenType.T_Fn,
        'i32': TokenType.T_Int,
        'if': TokenType.T_If,
        'let': TokenType.T_Let,
        'loop': TokenType.T_Loop,
        'mut': TokenType.T_Mut,
        'println': TokenType.T_Print,
        'return': TokenType.T_Return,
        'true': TokenType.T_True,
    }

    TWO_CHAR_TOKENS = {
        '->': TokenType.T_Arrow,
        '==': TokenType.T_ROp_E,
        '!=': TokenType.T_ROp_NE,
        '<=': TokenType.T_ROp_LE,
        '>=': TokenType.T_ROp_GE,
        '&&': TokenType.T_LOp_AND,
        '||': TokenType.T_LOp_OR,
    }

    SINGLE_CHAR_TOKENS = {
        '+': TokenType.T_AOp_Trust,
        '-': TokenType.T_AOp_MN,
        '*': TokenType.T_AOp_ML,
        '/': TokenType.T_AOp_DV,
        '%': TokenType.T_AOp_RM,
        '<': TokenType.T_ROp_L,
        '>': TokenType.T_ROp_G,
        '=': TokenType.T_Assign,
        '!': TokenType.T_LOp_NOT,
        ':': TokenType.T_Colon,
        ';': TokenType.T_Semicolon,
        ',': TokenType.T_Comma,
        '(': TokenType.T_LP,
        ')': TokenType.T_RP,
        '{': TokenType.T_LC,
        '}': TokenType.T_RC,
        '[': TokenType.T_LB,
        ']': TokenType.T_RB,
    }

    def __init__(self, text: str, symbol_table: SymbolTable = None):
        self.text = text
        self.pos = 0
        self.current_char = self.text[self.pos] if self.text else None
        self.line = 1
        self.column = 1
        self.symbol_table = symbol_table

    def advance(self):
        if self.current_char == '\n':
            self.line += 1
            self.column = 0
        self.pos += 1
        self.current_char = self.text[self.pos] if self.pos < len(self.text) else None
        self.column += 1

    def peek(self):
        peek_pos = self.pos + 1
        return self.text[peek_pos] if peek_pos < len(self.text) else None

    def tokenize(self):
        tokens = []
        while self.current_char is not None:
            if self.current_char.isspace():
                tokens.append(self.collect_whitespace())
            elif self.current_char == '/' and self.peek() == '/':
                tokens.append(self.collect_comment())
            elif self.current_char.isalpha() or self.current_char == '_':
                tokens.append(self.collect_identifier())
            elif self.current_char.isdigit():
                tokens.append(self.collect_number())
            elif self.current_char == '"':
                tokens.append(self.collect_string())
            else:
                two = self.current_char + (self.peek() or '')
                if two in self.TWO_CHAR_TOKENS:
                    tt = self.TWO_CHAR_TOKENS[two]
                    start_line, start_col = self.line, self.column
                    self.advance(); self.advance()
                    tokens.append(Token(tt, two, None, start_line, start_col))
                elif self.current_char in self.SINGLE_CHAR_TOKENS:
                    tt = self.SINGLE_CHAR_TOKENS[self.current_char]
                    lex = self.current_char
                    start_line, start_col = self.line, self.column
                    self.advance()
                    tokens.append(Token(tt, lex, None, start_line, start_col))
                else:
                    raise LexerError(f"Unknown character '{self.current_char}' at line {self.line}, column {self.column}")
        tokens.append(Token(TokenType.T_EOF, '', None, self.line, self.column))
        return tokens

    def collect_whitespace(self):
        start_line, start_col = self.line, self.column
        lexeme = ''
        while self.current_char is not None and self.current_char.isspace():
            lexeme += self.current_char
            self.advance()
        return Token(TokenType.T_Whitespace, lexeme, None, start_line, start_col)

    def collect_comment(self):
        start_line, start_col = self.line, self.column
        lexeme = ''
        lexeme += self.current_char; self.advance()
        lexeme += self.current_char; self.advance()
        while self.current_char is not None and self.current_char != '\n':
            lexeme += self.current_char; self.advance()
        if self.current_char == '\n':
            lexeme += self.current_char; self.advance()
        return Token(TokenType.T_Comment, lexeme, None, start_line, start_col)

    def collect_number(self):
        start_line, start_col = self.line, self.column
        lexeme = ''
        if self.current_char == '0' and self.peek() in ('x', 'X'):
            lexeme += self.current_char; self.advance()
            lexeme += self.current_char; self.advance()
            while self.current_char is not None and (self.current_char.isdigit() or self.current_char.lower() in 'abcdef'):
                lexeme += self.current_char; self.advance()
            value = int(lexeme, 16)
            return Token(TokenType.T_Hexadecimal, lexeme, value, start_line, start_col)
        while self.current_char is not None and self.current_char.isdigit():
            lexeme += self.current_char; self.advance()
        value = int(lexeme)
        return Token(TokenType.T_Decimal, lexeme, value, start_line, start_col)

    def collect_string(self):
        start_line, start_col = self.line, self.column
        lexeme = ''
        lexeme += self.current_char; self.advance()
        while self.current_char is not None and self.current_char != '"':
            if self.current_char == '\\':
                lexeme += self.current_char; self.advance()
                if self.current_char is not None:
                    lexeme += self.current_char; self.advance()
            else:
                lexeme += self.current_char; self.advance()
        if self.current_char == '"':
            lexeme += self.current_char; self.advance()
        else:
            raise LexerError(f"Unterminated string literal at line {start_line}, column {start_col}")
        return Token(TokenType.T_String, lexeme, None, start_line, start_col)

    def collect_identifier(self):
        start_line, start_col = self.line, self.column
        lexeme = ''
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == '_'):
            lexeme += self.current_char; self.advance()
        if lexeme == 'println' and self.current_char == '!':
            lexeme += self.current_char; self.advance()
            tok_type = TokenType.T_Print
        elif lexeme in self.KEYWORDS:
            tok_type = self.KEYWORDS[lexeme]
        else:
            tok_type = TokenType.T_Id
            if self.symbol_table is not None:
                self.symbol_table.add(lexeme, (start_line, start_col))
        return Token(tok_type, lexeme, None, start_line, start_col)

if __name__ == "__main__":
    # 1. Grab filenames from command line (or defaults)
    if len(sys.argv) >= 2:
        input_name = sys.argv[1]
    else:
        input_name = "input10.txt"

    if len(sys.argv) >= 3:
        output_name = sys.argv[2]
    else:
        output_name = "tokens.txt"

    # 2. Compute the base directory where this script lives
    script_dir = os.path.dirname(os.path.realpath(__file__))

    # 3. Build the input path: must be inside the same folder as the script
    input_path = os.path.join(script_dir, input_name)
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Could not find '{input_name}' in {script_dir}")

    # 4. Build the output path: point it to ../Syntax Analyzer/
    syntax_dir = os.path.abspath(os.path.join(script_dir, os.pardir, "SyntaxAnalyzer"))
    # ensure that directory exists
    os.makedirs(syntax_dir, exist_ok=True)
    output_path = os.path.join(syntax_dir, output_name)

    # 5. Read the source
    with open(input_path, 'r', encoding='utf-8') as f:
        source = f.read()

    # 6. Lex, write tokens...
    symtab = SymbolTable()
    lexer = Lexer(source, symbol_table=symtab)
    tokens = lexer.tokenize()

    with open(output_path, 'w', encoding='utf-8') as out:
        for tok in tokens:
            out.write(repr(tok) + '\n')
        out.write("\nSymbol Table:\n")
        for name, info in symtab.symbols.items():
            out.write(f"{name}: {info['positions']}\n")

    print(f"Lexing complete. {len(tokens)} tokens written to '{output_path}'.")
    print("Symbol Table entries:", len(symtab.symbols))
