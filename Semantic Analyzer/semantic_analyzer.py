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
        for c in node.children:
            self.check(c)

    # New: type‑check any Expr node
    def check_Expr(self, node: Node):
        # Force resolution of any Id inside
        self.infer_type(node)

    # New: ensure every expression in a println! is checked
    def check_PrintStmt(self, node: Node):
        # unnamed positional args
        for c in node.children:
            if c.typ == 'Expr':
                self.infer_type(c)
            elif c.typ == 'NamedArg':
                # NamedArg → Value → Expr
                val = next((ch for ch in c.children if ch.typ=='Value'), None)
                if val:
                    expr = next((ch for ch in val.children if ch.typ=='Expr'), None)
                    if expr:
                        self.infer_type(expr)

    def check_Program(self, node: Node):
        for c in node.children:
            self.check(c)
        main = self.lookup('main')
        if not main or main['kind'] != 'fn' or main['type'][0]:
            self.error("Function 'main' with no parameters not defined")

    def check_LetDecl(self, node: Node):
        pat = next((c for c in node.children if c.typ == 'Pattern'), None)
        if not pat or not pat.children:
            return self.error("Invalid LetDecl: missing pattern", node)
        first = pat.children[0]
        vars = []
        if first.typ == 'VarPattern' and first.value:
            vars = [first]
        elif first.typ == 'TuplePattern':
            vars = [c for c in first.children if c.typ == 'VarPattern' and c.value]
        if not vars:
            return self.error("Invalid LetDecl: no variable in pattern", pat)

        declared = None
        if any(c.typ == 'Colon' for c in node.children):
            idx = next(i for i,c in enumerate(node.children) if c.typ=='Colon')
            tnode = node.children[idx+1]
            if tnode.children:
                declared = tnode.children[0].typ.lower()

        expr = next((c for c in node.children if c.typ=='Expr'), None)
        inferred = self.infer_type(expr) if expr else None

        has_init = expr is not None
        mutable_kw = any(c.typ=='MutKw' for c in node.children)
        mutable = mutable_kw or not has_init

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
        base = node.children[0].children[0]
        entry = self.lookup(base.value, base) if base.value else None
        if entry and not entry['mutable']:
            self.error(f"Cannot assign to immutable variable '{base.value}'", base)
        ltype = entry['type'] if entry else None
        rtype = self.infer_type(node.children[2])
        if ltype and rtype and ltype != rtype:
            self.error(f"Type mismatch in assignment: '{ltype}' vs '{rtype}'", node)

    def check_FunctionDecl(self, node: Node):
        name_node = next(c for c in node.children if c.typ=='Id')
        params_node = next(c for c in node.children if c.typ=='Params')

        param_types = []
        param_names = []
        for p in params_node.children:
            # 1) pick up the declared name
            pname = p.value
            # if there is a VarPattern or Id child, use its .value instead
            if p.children:
                vp = next((c for c in p.children if c.typ in ('VarPattern','Id')), None)
                if vp and vp.value:
                    pname = vp.value

            # 2) pick up the type (if any)
            ptype = None
            if p.children and p.children[0].typ=='Type':
                ptype = p.children[0].children[0].typ.lower()

            param_names.append(pname)
            param_types.append(ptype)

        # return-type
        rnode = next((c for c in node.children if c.typ=='ReturnType'), None)
        ret = None
        if rnode and rnode.children:
            ret = rnode.children[0].children[0].typ.lower()

        # declare the function symbol
        self.declare(name_node.value,'fn',(param_types,ret),False,name_node)

        # check body
        prev = self.current_fn
        self.current_fn = (name_node.value,ret)
        self.enter_scope()
        for nm, tp in zip(param_names,param_types):
            if nm:
                self.declare(nm,'var',tp,False)
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
        # skip calls with no name
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
        lt = self.infer_type(node.children[0])
        rt = self.infer_type(node.children[1])
        op = node.value.lexeme if node.value else None
        if op in ('&&','||'):
            if lt!='bool' or rt!='bool':
                self.error("Logical operators require bool",node)
            return 'bool'
        if op in ('+','-','*','/','%'):
            if lt!='i32' or rt!='i32':
                self.error("Arithmetic requires i32",node)
            return 'i32'
        return None

    def check_UnaryOp(self, node: Node):
        t = self.infer_type(node.children[0])
        op = node.value.lexeme if node.value else None
        if op=='!' and t!='bool':
            self.error("Logical not requires bool",node)
        if op in ('+','-') and t!='i32':
            self.error("Unary + or - requires i32",node)
        return t

    def infer_type(self, expr: Node):
        if not expr or not expr.children:
            return None
        c = expr.children[0]
        if c.typ=='BoolLiteral':       return 'bool'
        if c.typ=='Number':            return 'i32'
        if c.typ=='TupleLiteral':      return tuple(self.infer_type(x) for x in c.children)
        if c.typ=='ArrayLiteral':
            types = [self.infer_type(x) for x in c.children]
            if None in types: return None
            if all(t==types[0] for t in types):
                return f"[{types[0]};{len(types)}]"
            self.error("Heterogeneous array literal types",c)
            return None
        if c.typ=='Id':
            entry = self.lookup(c.value,c)
            return entry['type'] if entry else None
        if c.typ=='BinaryOp': return self.check_BinaryOp(c)
        if c.typ=='UnaryOp':  return self.check_UnaryOp(c)
        if c.typ=='Call':
            # always lookup the function name
            if not c.value:
                self.error("Missing function name in call", c)
                return None
            entry = self.lookup(c.value, c)
            return entry['type'][1] if entry else None
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
