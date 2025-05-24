from enum import Enum, auto
import os

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