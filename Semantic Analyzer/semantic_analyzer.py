import sys
import os

class Node:
    def __init__(self, typ, value=None):
        self.typ = typ
        self.value = value
        self.children = []
        self.parent = None

    def add_child(self, node):
        node.parent = self
        self.children.append(node)

    def __repr__(self):
        return f"Node({self.typ}, {self.value}, children={len(self.children)})"

def parse_tree_from_file(path: str) -> Node:
    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\n') for line in f if line.strip()]
    root = None
    stack = []
    for line in lines:
        first = None
        for ch in ('├', '└'):
            idx = line.find(ch)
            if idx != -1 and (first is None or idx < first):
                first = idx
        indent = first or 0
        text = line[indent:]
        parts = text.split(':', 1)
        label = parts[0].lstrip('└─├─ ')
        value = None
        if len(parts) == 2:
            raw = parts[1].strip()
            value = raw[1:-1] if raw.startswith("'") and raw.endswith("'") else raw
        node = Node(label, value)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack:
            stack[-1][1].add_child(node)
        else:
            root = node
        stack.append((indent, node))
    return root

class SemanticAnalyzer:
    def __init__(self, tree: Node):
        self.tree = tree
        self.errors = []
        self.scopes = [{}]        # global scope
        self.current_fn = None    # (name, return_type)

    def error(self, msg, node=None):
        ctx = f" [at {node.typ} '{node.value}']" if node and node.value is not None else ''
        self.errors.append(msg + ctx)

    def enter_scope(self):
        self.scopes.append({})

    def exit_scope(self):
        self.scopes.pop()

    def declare(self, name, kind, typ, mutable=False, node=None):
        if not name:
            return
        sym = self.scopes[-1]
        if name in sym:
            self.error(f"Redeclaration of {kind} '{name}'", node)
        sym[name] = {'kind': kind, 'type': typ, 'mutable': mutable}

    def lookup(self, name, node=None):
        if not name:
            self.error(f"Use of undeclared identifier '{name}'", node)
            return None
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        self.error(f"Use of undeclared identifier '{name}'", node)
        return None

    def check(self, node: Node):
        method = getattr(self, f"check_{node.typ}", self.generic_check)
        return method(node)

    def generic_check(self, node: Node):
        # dispatch early to any node‐specific checks:
        if node.typ == 'BinaryOp':
            self.check_BinaryOp(node)
        elif node.typ == 'UnaryOp':
            self.check_UnaryOp(node)
        elif node.typ == 'ArrayIndex':
            self.check_ArrayIndex(node)
        # then recurse:
        for c in node.children:
            self.check(c)

    def check_ArrayIndex(self, node: Node):
        """
        node.value is the array name (string),
        node.children[0] is the index expression (Number, UnaryOp, Id, etc.)
        """
        # 1) must be an i32
        idx_expr = node.children[0]
        idx_type = self.infer_type(idx_expr)
        if idx_type != 'i32':
            self.error("Array index must be of type i32", node)

        # 2) if the index is a literal, enforce > 0
        #    handle bare Number or UnaryOp(Number)
        lit = None
        if idx_expr.typ == 'Number':
            lit = int(idx_expr.value, 0)
        elif idx_expr.typ == 'UnaryOp' and idx_expr.children:
            child = idx_expr.children[0]
            if child.typ == 'Number':
                val = int(child.value, 0)
                # note: node.value.lexeme is the operator string, here '-' for negative
                if idx_expr.value == '-':
                    lit = -val
                else:
                    lit = val
        if lit is not None and lit <= 0:
            self.error("Array index must be > 0", node)


    def check_ExprStmt(self, node: Node):
        # type-check standalone expression statements
        expr = node.children[0]
        self.infer_type(expr)

    def check_Expr(self, node: Node):
        # unwrap and type-check any Expr node
        self.infer_type(node)

    def check_PrintStmt(self, node: Node):
        # check both positional and named args
        for c in node.children:
            if c.typ == 'Expr':
                self.infer_type(c)
            elif c.typ == 'NamedArg':
                val = next((ch for ch in c.children if ch.typ == 'Value'), None)
                if val:
                    expr = next((ch for ch in val.children if ch.typ == 'Expr'), None)
                    if expr:
                        self.infer_type(expr)

    def check_Program(self, node: Node):
        for c in node.children:
            self.check(c)
        main = self.lookup('main')
        if not main or main['kind'] != 'fn' or main['type'][0]:
            self.error("Function 'main' with no parameters not defined")

    def check_LetDecl(self, node: Node):
        # 1) find the pattern
        pat = next((c for c in node.children if c.typ == 'Pattern'), None)
        if not pat or not pat.children:
            return self.error("Invalid LetDecl: missing pattern", node)
        first = pat.children[0]
        if first.typ == 'VarPattern' and first.value:
            vars = [first]
        elif first.typ == 'TuplePattern':
            vars = [c for c in first.children if c.typ == 'VarPattern' and c.value]
        else:
            vars = []
        if not vars:
            return self.error("Invalid LetDecl: no variable in pattern", pat)

        # 2) extract declared type (if present), but only if Type->child exists
        declared = None
        if any(c.typ == 'Colon' for c in node.children):
            idx = next(i for i, c in enumerate(node.children) if c.typ == 'Colon')
            type_node = node.children[idx+1]    # ASTNode('Type', …)
            if type_node.children:
                base = type_node.children[0]    # e.g. ASTNode('TypeI32', token=…)
                # 2a) simple builtins:
                # instead of `if base.token and ...: declared = base.token.lexeme` do:
                if base.value is not None:
                    declared = base.value
                # 2b) array annotations [T;N]:
                elif base.typ == 'ArrayType' and len(base.children) >= 2:
                    # subtype at children[0].children[0].token.lexeme
                    sub = base.children[0]
                    size = base.children[1]
                    if sub.children and sub.children[0].token and size.token:
                        tlex = sub.children[0].token.lexeme
                        nlex = size.token.lexeme
                        declared = f"[{tlex};{nlex}]"

        # 3) infer initializer’s type
        expr = next((c for c in node.children if c.typ == 'Expr'), None)
        inferred = self.infer_type(expr) if expr else None

        # 4) mutability / initialization
        has_init   = expr is not None
        mutable_kw = any(c.typ == 'MutKw' for c in node.children)
        mutable    = mutable_kw or not has_init

        # 5) declare each var, checking declared vs inferred
        for var in vars:
            name = var.value
            if name == '_':
                if has_init:
                    self.error("Cannot assign to wildcard '_'", var)
                continue
            if declared and inferred and declared != inferred:
                self.error(f"Type mismatch: declared '{declared}' vs initialized '{inferred}'", var)
            self.declare(name, 'var', declared or inferred, mutable, var)


    def check_AssignStmt(self, node: Node):
        lval_node = node.children[0]       # the LValue node
        ltype = self.infer_type(lval_node)
        # (only check mutability via lookup of the base identifier:)
        base = lval_node.children[0]
        entry = self.lookup(base.value, base) if base.value else None
        if entry and not entry['mutable']:
            self.error(f"Cannot assign to immutable variable '{base.value}'", base)

        rtype = self.infer_type(node.children[2])
        if ltype and rtype and ltype != rtype:
            self.error(f"Type mismatch in assignment: '{ltype}' vs '{rtype}'", node)
        


    def check_FunctionDecl(self, node: Node):
        name_node   = next(c for c in node.children if c.typ == 'Id')
        params_node = next(c for c in node.children if c.typ == 'Params')

        param_types = []
        param_names = []
        for p in params_node.children:
            # name
            vp = next((c for c in p.children if c.typ=='VarPattern'), None)
            pname = vp.value if vp and vp.value else p.value

            # declared type (if any)
            ptype = None
            tnode = next((c for c in p.children if c.typ=='Type'), None)
            if tnode and tnode.children:
                base = tnode.children[0]
                # now just read base.value
                if base.value is not None:
                    ptype = base.value

            param_names.append(pname)
            param_types.append(ptype)

        # return type, same idea
        ret = None
        rnode = next((c for c in node.children if c.typ=='ReturnType'), None)
        if rnode and rnode.children:
            tnode = rnode.children[0]
            if tnode.children:
                base = tnode.children[0]
                if base.value is not None:
                    ret = base.value

        # declare fn with real i32/bool strings
        self.declare(
            name_node.value,
            'fn',
            (param_types, ret),
            False,
            name_node,
        )

        # now push scope, declare parameters
        prev = self.current_fn
        self.current_fn = (name_node.value, ret)
        self.enter_scope()
        for nm, tp in zip(param_names, param_types):
            if nm:
                self.declare(nm, 'var', tp, False)
        body = next(c for c in node.children if c.typ=='Body')
        self.check(body)
        self.exit_scope()
        self.current_fn = prev


    def check_ReturnStmt(self, node: Node):
        if not self.current_fn:
            return self.error("Return outside function", node)
        _, ret = self.current_fn
        rtype = self.infer_type(node.children[0]) if node.children else None
        if ret and rtype and ret != rtype:
            self.error(f"Return type '{rtype}' does not match '{ret}'", node)

    def check_Call(self, node: Node):
        if not node.value:
            self.error("Missing function name in call", node)
            return
        entry = self.lookup(node.value,node)
        if not entry or entry['kind']!='fn':
            return
        params,_ = entry['type']
        args = [self.infer_type(c) for c in node.children]
        if len(args)!=len(params):
            self.error(f"Call to '{node.value}' expects {len(params)} args, got {len(args)}", node)
        for i,(a,p) in enumerate(zip(args,params)):
            if p and a and p!=a:
                self.error(f"Argument {i} type '{a}' mismatches '{p}'", node)

    def check_BinaryOp(self, node: Node):
        op = node.value           # e.g. '+', '&&', '!=', '<='

        # 1) arithmetic: +, -, *, /, %
        if op in ('+','-','*','/','%'):
            lt = self.infer_type(node.children[0])
            rt = self.infer_type(node.children[1])
            if lt!='i32' or rt!='i32':
                self.error("Arithmetic operators require i32 operands", node)
            return 'i32'

        # 2) logical: &&, ||
        if op in ('&&','||'):
            lt = self.infer_type(node.children[0])
            rt = self.infer_type(node.children[1])
            if lt!='bool' or rt!='bool':
                self.error("Logical operators require bool operands", node)
            return 'bool'

        # 3) relational: <, <=, >, >=, ==, !=
        if op in ('<','<=','>','>=','==','!='):
            lt = self.infer_type(node.children[0])
            rt = self.infer_type(node.children[1])
            if lt!='i32' or rt!='i32':
                self.error("Relational operators require i32 operands", node)
            return 'bool'

        # 4) anything else we don’t check here
        return None




    def check_UnaryOp(self, node: Node):
        # operator now comes through directly as a string in node.value
        op = node.value

        # first, figure out the operand’s type
        t = self.infer_type(node.children[0])

        # unary plus/minus must apply to an i32
        if op in ('+', '-'):
            if t != 'i32':
                self.error("Unary + or - requires i32 operand", node)
            return 'i32'

        # logical not must apply to a bool
        if op == '!':
            if t != 'bool':
                self.error("Logical not requires bool operand", node)
            return 'bool'

        # (Trust has no other prefix ops) — fall back to passing the operand type through
        return t




    def infer_type(self, expr: Node):
        # 1) direct dispatch on the node kind
        if expr.typ == 'Expr':
            # unwrap the single child
            return self.infer_type(expr.children[0])
        
        if expr.typ == 'LValue':
        # LValue → either Id or ArrayIndex
            return self.infer_type(expr.children[0])

        if expr.typ == 'Number':
            return 'i32'
        if expr.typ == 'BoolLiteral':
            return 'bool'

        if expr.typ == 'String':
            # Trust’s println! can take strings without further checks
            return 'str'

        if expr.typ == 'Id':
            entry = self.lookup(expr.value, expr)
            return entry['type'] if entry else None

        if expr.typ == 'UnaryOp':
            return self.check_UnaryOp(expr)

        if expr.typ == 'BinaryOp':
            return self.check_BinaryOp(expr)

        if expr.typ == 'Call':
            entry = self.lookup(expr.value, expr)
            return entry['type'][1] if entry else None

        if expr.typ == 'ArrayLiteral':
            # [e,e,e]
            elms = [self.infer_type(c) for c in expr.children]
            if None in elms:
                return None
            if not all(t == elms[0] for t in elms):
                self.error("Heterogeneous array literal types", expr)
                return None
            return f"[{elms[0]};{len(elms)}]"

        if expr.typ == 'ArrayRepeat':
            # [e; n]
            elm = self.infer_type(expr.children[0])
            cnt = self.infer_type(expr.children[1])
            if elm and cnt == 'i32':
                return f"[{elm};?]"
            return None

        if expr.typ == 'ArrayIndex':
            # arr[idx]
            arr_sym = self.lookup(expr.value, expr)
            if not arr_sym: return None
            arr_t = arr_sym['type']
            # expects "[T;N]"
            if isinstance(arr_t, str) and arr_t.startswith('['):
                return arr_t[arr_t.index('[')+1 : arr_t.index(';')]
            return None

        if expr.typ == 'TupleLiteral':
            return tuple(self.infer_type(c) for c in expr.children)

        # anything else—pattern nodes, type nodes, print‐stmt wrappers, etc.—
        # is not a real expression to type‐check:
        return None


def report_errors(errors, tree):
    if errors:
        for e in errors:
            print(f"Semantic error: {e}")
        sys.exit(1)
    print("Program was compiled successfully")
    with open('syntax_tree.txt', 'w', encoding='utf-8') as f:
        f.write(repr(tree))

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fn = sys.argv[1] if len(sys.argv)>1 else 'parse_tree.txt'
    inp = os.path.join(script_dir, fn)
    if not os.path.exists(inp):
        print(f"Parse tree file '{inp}' not found."); sys.exit(1)
    tree = parse_tree_from_file(inp)
    analyzer = SemanticAnalyzer(tree)
    analyzer.check(tree)
    report_errors(analyzer.errors, tree)
