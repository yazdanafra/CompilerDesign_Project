import os
import sys
from collections import namedtuple

# --- AST Node -------------------------------------------------------------
class ASTNode:
    def __init__(self, nodetype, token=None, children=None):
        self.nodetype = nodetype
        self.token    = token
        self.children = children or []

    def __repr__(self):
        return self._to_tree('', True)

    def _to_tree(self, prefix, is_last):
        # Leaf nodes show their lexeme
        if self.token and hasattr(self.token, 'lexeme') and not self.children:
            label = f"{self.nodetype}: '{self.token.lexeme}'"
        else:
            label = self.nodetype

        branch = '└── ' if is_last else '├── '
        line = prefix + branch + label

        new_prefix = prefix + ('    ' if is_last else '│   ')
        lines = [line]
        for idx, child in enumerate(self.children):
            if isinstance(child, ASTNode):
                last = (idx == len(self.children) - 1)
                lines.append(child._to_tree(new_prefix, last))
        return '\n'.join(lines)


# --- Token ---------------------------------------------------------------
Token = namedtuple('Token', ['type','lexeme','line','col'])

# --- Loader --------------------------------------------------------------
def load_tokens(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Could not find tokens file '{path}'")
    tokens = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            # Expect format: Token(TYPE, 'LEXEME', ..., line=N, col=M)
            if not line.startswith('Token('):
                continue
            try:
                # Extract type
                start = line.find('(') + 1
                comma = line.find(',', start)
                ttype = line[start:comma].strip()
                # Extract lexeme
                first_quote = line.find("'", comma)
                second_quote = line.find("'", first_quote + 1)
                lexeme = line[first_quote+1:second_quote]
                # Extract line number
                line_eq = line.find('line=', second_quote)
                comma2 = line.find(',', line_eq)
                line_no = int(line[line_eq+5:comma2])
                # Extract column number
                col_eq = line.find('col=', comma2)
                end_paren = line.find(')', col_eq)
                col_no = int(line[col_eq+4:end_paren])
                tokens.append(Token(ttype, lexeme, line_no, col_no))
            except Exception:
                # Skip lines that don't match expected format
                continue
    # Filter out whitespace and comments
    tokens = [t for t in tokens if t.type not in ('T_Whitespace','T_Comment')]
    last = tokens[-1] if tokens else Token('', '', 0, 0)
    # Append EOF token one column past last
    tokens.append(Token('T_EOF', '', last.line, last.col + 1))
    return tokens

# --- Parser --------------------------------------------------------------
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos    = 0
        self.errors = []

    def current(self): return self.tokens[self.pos]
    def peek(self): return self.tokens[self.pos+1] if self.pos+1<len(self.tokens) else Token('T_EOF','',0,0)

    def eat(self, typ):
        tok = self.current()
        if tok.type == typ:
            self.pos += 1
            return tok
        self.errors.append(f"Expected {typ} at {tok.line}:{tok.col}, got {tok.type}")
        return tok

    def is_assign_stmt(self):
        if self.current().type != 'T_Id': return False
        i = self.pos+1
        while i<len(self.tokens) and self.tokens[i].type=='T_LB':
            depth=1; i+=1
            while i<len(self.tokens) and depth>0:
                if self.tokens[i].type=='T_LB': depth+=1
                elif self.tokens[i].type=='T_RB': depth-=1
                i+=1
        return i<len(self.tokens) and self.tokens[i].type=='T_Assign'

    # --- Entry point ---
    def parse(self):
        root = ASTNode('Program')
        while self.current().type!='T_EOF':
            root.children.append(self.parse_top_level())
        return root

    def parse_top_level(self):
        if self.current().type=='T_Fn':
            node = self.parse_function_decl()
        else:
            node = self.parse_statement()
        # optional semicolon
        if self.current().type=='T_Semicolon': self.eat('T_Semicolon')
        return node

    # --- Statements & Declarations ---
    def parse_statement(self):
        t = self.current().type
        if t == 'T_Return':
            return self.parse_return_stmt()
        if t == 'T_Break':
            return self.parse_break_stmt()
        if t == 'T_Continue':
            return self.parse_continue_stmt()
        # # implicit declaration starting with type (no 'let')
        # if t in ('T_Bool','T_Int','T_LB','T_LP'):
        #     return self.parse_type_decl()
        # if t == 'T_Mut':
        #     return self.parse_let_decl()  # allow "mut x: T = ..."
        if self.is_assign_stmt():
            return self.parse_assign_stmt()
        if t == 'T_Let':
            return self.parse_let_decl()
        if t == 'T_If':
            return self.parse_if_stmt()
        if t == 'T_Loop':
            return self.parse_loop_stmt()
        if t == 'T_Print':
            return self.parse_print_stmt()
        return ASTNode('ExprStmt', children=[self.parse_expression()])


    def parse_return_stmt(self):
        node = ASTNode('ReturnStmt', token=self.eat('T_Return'))
        if self.current().type not in ('T_Semicolon','T_RC','T_EOF'):
            node.children.append(self.parse_expression())
        return node

    def parse_break_stmt(self):
        node = ASTNode('BreakStmt', token=self.eat('T_Break'))
        return node

    def parse_continue_stmt(self):
        node = ASTNode('ContinueStmt', token=self.eat('T_Continue'))
        return node

    def parse_let_decl(self):
        # must start with ‘let’
        if self.current().type != 'T_Let':
           tok = self.current()
           self.errors.append(f"Expected T_Let at {tok.line}:{tok.col}, got {tok.type}")
           # abort—and try to resynchronize
           return ASTNode('Error')
        node = ASTNode('LetDecl')
        # support both "let mut x" and "mut x"
        if self.current().type == 'T_Let':
            node.children.append(ASTNode('LetKw', self.eat('T_Let')))
        if self.current().type == 'T_Mut':
            node.children.append(ASTNode('MutKw', self.eat('T_Mut')))
        # pattern: identifier or tuple
        pat = self.parse_pattern()
        node.children.append(ASTNode('Pattern', children=[pat]))
        # optional type annotation
        if self.current().type == 'T_Colon':
            node.children.append(ASTNode('Colon', self.eat('T_Colon')))
            node.children.append(ASTNode('Type', self.parse_type()))
        # optional initializer
        if self.current().type == 'T_Assign':
            node.children.append(ASTNode('Assign', self.eat('T_Assign')))
            node.children.append(ASTNode('Expr', children=[self.parse_expression()]))
        return node

    def parse_assign_stmt(self):
        node=ASTNode('AssignStmt')
        node.children.append(self.parse_lvalue())
        node.children.append(ASTNode('Assign',self.eat('T_Assign')))
        node.children.append(ASTNode('Expr',children=[self.parse_expression()]))
        return node

    def parse_pattern(self):
        if self.current().type=='T_Id': return ASTNode('VarPattern',self.eat('T_Id'))
        self.eat('T_LP'); pats=[self.parse_pattern()]
        while self.current().type=='T_Comma': self.eat('T_Comma'); pats.append(self.parse_pattern())
        self.eat('T_RP'); return ASTNode('TuplePattern',children=pats)

    def parse_lvalue(self):
        node = ASTNode('LValue')
        base = ASTNode('Id', self.eat('T_Id'))
        while self.current().type == 'T_LB':
            self.eat('T_LB')
            idx = self.parse_expression()
            self.eat('T_RB')
            base = ASTNode('ArrayIndex', token=base.token, children=[base, idx])
        node.children.append(base)
        return node

    def parse_if_stmt(self):
        node = ASTNode('IfStmt')
        node.children.append(ASTNode('IfKw', self.eat('T_If')))
        # parse full boolean expression condition
        condition = self.parse_expression()
        node.children.append(ASTNode('Cond', children=[condition]))
        # then block
        node.children.append(ASTNode('Then', children=[self.parse_block()]))
        # optional else
        if self.current().type == 'T_Else':
            node.children.append(ASTNode('ElseKw', self.eat('T_Else')))
            if self.current().type == 'T_If':
                node.children.append(self.parse_if_stmt())
            else:
                node.children.append(ASTNode('Else', children=[self.parse_block()]))
        return node

    def parse_loop_stmt(self):
        node = ASTNode('LoopStmt')
        node.children.append(ASTNode('LoopKw', self.eat('T_Loop')))
        node.children.append(ASTNode('Block', children=[self.parse_block()]))
        return node

    def parse_print_stmt(self):
        node=ASTNode('PrintStmt'); node.children.append(ASTNode('PrintKw',self.eat('T_Print')))
        self.eat('T_LP'); node.children.append(ASTNode('FormatStr',self.eat('T_String')))
        args=[]
        while self.current().type=='T_Comma':
            self.eat('T_Comma')
            if self.current().type=='T_Id' and self.peek().type=='T_Assign':
                name=self.eat('T_Id'); self.eat('T_Assign'); val=self.parse_expression()
                args.append(ASTNode('NamedArg',token=name,children=[ASTNode('Value',children=[ASTNode('Expr',children=[val])])]))
            else:
                expr=self.parse_expression(); args.append(ASTNode('Expr',children=[expr]))
        node.children.extend(args); self.eat('T_RP'); return node

    def parse_block(self):
        self.eat('T_LC'); stmts=[]
        while self.current().type not in ('T_RC','T_EOF'):
            stmts.append(self.parse_statement())
            if self.current().type=='T_Semicolon': self.eat('T_Semicolon')
        self.eat('T_RC'); return ASTNode('Block',children=stmts)

    def parse_function_decl(self):
        node=ASTNode('FunctionDecl'); node.children.append(ASTNode('FnKw',self.eat('T_Fn')))
        node.children.append(ASTNode('Id',self.eat('T_Id')))
        self.eat('T_LP'); params=[]
        if self.current().type!='T_RP': params=self.parse_param_list()
        self.eat('T_RP'); node.children.append(ASTNode('Params',children=params))
        if self.current().type=='T_Arrow': node.children.append(ASTNode('Arrow',self.eat('T_Arrow'))); node.children.append(ASTNode('ReturnType',self.parse_type()))
        node.children.append(ASTNode('Body',children=[self.parse_block()])); return node

    def parse_param_list(self):
        params=[self.parse_param()]
        while self.current().type=='T_Comma': self.eat('T_Comma'); params.append(self.parse_param())
        return params

    def parse_param(self):
        name=self.eat('T_Id'); node=ASTNode('Param',token=name)
        if self.current().type=='T_Colon': self.eat('T_Colon'); node.children.append(ASTNode('Type',children=[self.parse_type()]))
        return node

    def parse_type(self):
        t=self.current().type
        if t=='T_Bool': return ASTNode('TypeBool',self.eat('T_Bool'))
        if t=='T_Int':  return ASTNode('TypeI32',self.eat('T_Int'))
        if t=='T_LB':
            self.eat('T_LB'); subtype=self.parse_type(); size=None
            if self.current().type=='T_Semicolon': self.eat('T_Semicolon'); size=ASTNode('Size',self.eat('T_Decimal'))
            self.eat('T_RB'); children=[subtype]+([size] if size else []); return ASTNode('ArrayType',children=children)
        if t=='T_LP':
            self.eat('T_LP'); types=[self.parse_type()]
            while self.current().type=='T_Comma': self.eat('T_Comma'); types.append(self.parse_type())
            self.eat('T_RP'); return ASTNode('TupleType',children=types)
        self.errors.append(f"Unexpected type {t} at {self.current().line}:{self.current().col}")
        return ASTNode('TypeError')

    PREC={
        'T_LOp_OR':1,'T_LOp_AND':2,'T_ROp_E':3,'T_ROp_NE':3,'T_ROp_L':4,'T_ROp_LE':4,'T_ROp_G':4,'T_ROp_GE':4,
        'T_AOp_Trust':5,'T_AOp_MN':5,'T_AOp_ML':6,'T_AOp_DV':6,'T_AOp_RM':6,
    }

    def parse_expression(self,min_prec=1):
        tok=self.current()
        if tok.type in('T_LOp_NOT','T_AOp_Trust','T_AOp_MN'):
            op=self.eat(tok.type); rhs=self.parse_expression(self.PREC.get(op.type,7)); lhs=ASTNode('UnaryOp',token=op,children=[rhs])
        else: lhs=self.parse_primary()
        while True:
            op_tok=self.current(); prec=self.PREC.get(op_tok.type,0)
            if prec<min_prec: break
            op=self.eat(op_tok.type); rhs=self.parse_expression(prec+1); lhs=ASTNode('BinaryOp',token=op,children=[lhs,rhs])
        return lhs

    def parse_primary(self):
        tok = self.current()
        # numeric literals
        if tok.type in ('T_Decimal', 'T_Hexadecimal'):
            return ASTNode('Number', self.eat(tok.type))
        # string literals
        if tok.type == 'T_String':
            return ASTNode('String', self.eat('T_String'))
        # boolean literals
        if tok.type in ('T_True', 'T_False'):
            return ASTNode('BoolLiteral', self.eat(tok.type))
        # identifiers: variable, function call, or array index
        if tok.type == 'T_Id':
            idt = self.eat('T_Id')
            # function call
            if self.current().type == 'T_LP':
                self.eat('T_LP')
                args = []
                if self.current().type != 'T_RP':
                    args = self.parse_expression_list()
                self.eat('T_RP')
                return ASTNode('Call', token=idt, children=args)
            # array indexing
            if self.current().type == 'T_LB':
                self.eat('T_LB')
                idx = self.parse_expression()
                self.eat('T_RB')
                return ASTNode('ArrayIndex', token=idt, children=[idx])
            # simple identifier
            return ASTNode('Id', token=idt)
        # tuple literal or grouped expression
        if tok.type == 'T_LP':
            # look ahead to see if tuple
            ahead = [t.type for t in self.tokens[self.pos+1:]]
            if 'T_Comma' in ahead[:ahead.index('T_RP')]:
                self.eat('T_LP')
                elems = self.parse_expression_list()
                self.eat('T_RP')
                return ASTNode('TupleLiteral', children=elems)
            # grouped expression
            self.eat('T_LP')
            expr = self.parse_expression()
            self.eat('T_RP')
            return expr
                # array literal or repetition [elem; count]
        if tok.type == 'T_LB':
            self.eat('T_LB')
            if self.current().type == 'T_RB':
                # empty array
                self.eat('T_RB')
                return ASTNode('ArrayLiteral', children=[])
            # parse first element
            first = self.parse_expression()
            # repetition syntax [expr; count]
            if self.current().type == 'T_Semicolon':
                self.eat('T_Semicolon')
                count = self.parse_expression()
                self.eat('T_RB')
                return ASTNode('ArrayRepeat', children=[first, count])
            # normal comma-separated literal
            elems = [first]
            while self.current().type == 'T_Comma':
                self.eat('T_Comma')
                elems.append(self.parse_expression())
            self.eat('T_RB')
            return ASTNode('ArrayLiteral', children=elems)
        # error recovery
        self.errors.append(f"Unexpected {tok.type} at {tok.line}:{tok.col}")
        self.pos += 1
        return ASTNode('Error')

    def parse_expression_list(self):
        es=[self.parse_expression()]
        while self.current().type=='T_Comma': self.eat('T_Comma'); es.append(self.parse_expression())
        return es

if __name__=='__main__':
    # Determine tokens file: use argument or fallback to tokens.txt next to script
    script_dir = os.path.dirname(os.path.realpath(__file__))
    tokens_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(script_dir, 'tokens.txt')
    try:
        tokens = load_tokens(tokens_file)
    except FileNotFoundError as e:
        print(e)
        print("Usage: python Parser.py [tokens_file]")
        sys.exit(1)
    p = Parser(tokens)
    tree = p.parse()
    output_file = sys.argv[2] if len(sys.argv) > 2 else os.path.join(script_dir, 'parser_output.txt')
    with open(output_file, 'w', encoding='utf-8') as out:
        if p.errors:
            out.write('Errors:\n')
            for e in p.errors:
                out.write(e + '\n')
            print(f"Found {len(p.errors)} errors. See '{output_file}'")
        else:
            out.write(tree.__repr__())
            print(f"Parse successful. AST written to '{output_file}'")

