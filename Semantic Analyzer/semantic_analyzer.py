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
        self.in_format = False
    
    def _inside_print(self, node: Node) -> bool:
        # climb up until root; if we see a PrintStmt, we’re in formatting context
        while node:
            if node.typ == 'PrintStmt':
                return True
            node = node.parent
        return False


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
        # special‐case PrintStmt so that its own logic runs (and sets in_format)
        if node.typ == 'PrintStmt':
            return self.check_PrintStmt(node)

        # special checks for these node types
        if node.typ == 'BinaryOp':
            self.check_BinaryOp(node)
        elif node.typ == 'UnaryOp':
            self.check_UnaryOp(node)
        elif node.typ == 'ArrayIndex':
            self.check_ArrayIndex(node)
        elif node.typ == 'Call':
            self.check_Call(node)

        # then recurse
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
        self.check(node.children[0])


    def check_Expr(self, node: Node):
        # simply recurse into its child
        for c in node.children:
            self.check(c)



    def check_PrintStmt(self, node: Node):
        # mark that anything we infer/check under here is in 'format' mode
        saved = self.in_format
        self.in_format = True

        # format string itself needs no checks
        # but each Expr child *is* a formatting argument
        for c in node.children:
            if c.typ == 'Expr':
                # unwrap the Expr → real AST, then fully infer/check it
                expr = c.children[0]
                self.infer_type(expr)
                self.check(expr)
            elif c.typ == 'NamedArg':
                # named args still get checked
                val = next((ch for ch in c.children if ch.typ == 'Value'), None)
                if val:
                    expr = next((ch for ch in val.children if ch.typ == 'Expr'), None)
                    if expr:
                        self.infer_type(expr)
                        self.check(expr)

        # restore
        self.in_format = saved


    def check_Program(self, node: Node):
        # 1) process all top-level items (this will declare all functions/vars)
        for c in node.children:
            self.check(c)

        # 2) now enforce the special "main" rule without using lookup()
        global_scope = self.scopes[0]
        main_sym = global_scope.get('main')

        # main must exist, be a function, and take zero parameters
        if (not main_sym
            or main_sym['kind'] != 'fn'
            or (main_sym['type'][0] and len(main_sym['type'][0]) != 0)
        ):
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
        # **new**: descend into the Expr so ArrayIndex / other checks happen
        expr = next((c for c in node.children if c.typ=='Expr'), None)
        if expr:
            # expr.children[0] is the real value node (ArrayIndex, Number, etc.)
            self.check(expr.children[0])


    def check_AssignStmt(self, node: Node):
                # --- left side ---
        lval_node = node.children[0]       # the LValue node
        ltype     = self.infer_type(lval_node)
        # (only check mutability via lookup of the base identifier:)
        base = lval_node.children[0]
        entry = self.lookup(base.value, base) if base.value else None
        if entry and not entry['mutable']:
            self.error(f"Cannot assign to immutable variable '{base.value}'", base)

        # --- right side ---
        rhs_expr = node.children[2].children[0]  # unwrap the Expr→<value>

        # If this is a function call, pull its declared return type
        if rhs_expr.typ == 'Call' and rhs_expr.value:
            fn_entry = self.lookup(rhs_expr.value, rhs_expr)
            if fn_entry and fn_entry['kind']=='fn':
                ret = fn_entry['type'][1]
                if ltype and ret and ltype != ret:
                    self.error(
                        f"Assignment type mismatch: lhs is '{ltype}' but '{rhs_expr.value}' returns '{ret}'",
                        node
                    )
                    return

        # Otherwise, do the usual type‐check
        rtype = self.infer_type(node.children[2])
        if ltype and rtype and ltype != rtype:
            self.error(f"Type mismatch in assignment: '{ltype}' vs '{rtype}'", node)



    def check_IfStmt(self, node: Node):
        # node.children looks like [IfKw, Cond, Then, (ElseKw, Else)?]
        # pull out the condition expression
        cond_wrapper = next(c for c in node.children if c.typ == 'Cond')
        # Cond → Expr, so its first child is the actual Expr node
        cond_expr = cond_wrapper.children[0]

        # infer its type
        t = self.infer_type(cond_expr)
        if t != 'bool':
            self.error("If condition must be bool", cond_expr)

        # now continue checking inside the then/else blocks
        for c in node.children:
            if c.typ in ('Then','Else'):
                self.check(c)


    def body_always_returns(self, node_or_stmts):
        """
        Given either:
         - a list of ASTNode statements (e.g. the children of a Block), or
         - a single Block node whose children are statements,
        return True iff *every* control‐flow path through them ends in a return.
        """
        # Normalize to list of statements
        if isinstance(node_or_stmts, list):
            stmts = node_or_stmts
        elif hasattr(node_or_stmts, 'typ') and node_or_stmts.typ == 'Block':
            # A Block node wraps its statements directly as children
            stmts = node_or_stmts.children
        else:
            # Unexpected shape → no guaranteed return
            return False

        if not stmts:
            return False

        last = stmts[-1]

        # 1) Direct return
        if last.typ == 'ReturnStmt':
            return True

        # 2) IfStmt: both Then & Else must return
        if last.typ == 'IfStmt':
            then_node = next((c for c in last.children if c.typ == 'Then'), None)
            else_node = next((c for c in last.children if c.typ == 'Else'), None)
            if then_node and else_node:
                # Each of those wraps a Block
                return ( self.body_always_returns(then_node.children[0])
                     and self.body_always_returns(else_node.children[0]) )
            return False   # missing else means a fall‑through

        # 3) Nested Block
        if last.typ == 'Block':
            return self.body_always_returns(last)

        # 4) Anything else falls through
        return False
    

    def _stringify_type_node(self, type_wrapper: Node) -> str:
        """
        Given an ASTNode('Type', children=[…]), produce exactly
        the 'i32', 'bool', '[i32;3]', '(i32,bool)' strings
        that infer_type() would produce.
        """
        base = type_wrapper.children[0]

        # primitives
        if base.typ == 'TypeI32':
            return 'i32'
        if base.typ == 'TypeBool':
            return 'bool'

        # array [T;N]
        if base.typ == 'ArrayType':
            # The first child of ArrayType is itself a Type node
            subtype_type_node = Node('Type')
            subtype_type_node.children.append(base.children[0])
            subtype = self._stringify_type_node(subtype_type_node)

            size = base.children[1].value
            return f"[{subtype};{size}]"

        # tuple (T1,T2,…)
        if base.typ == 'TupleType':
            elems = []
            for elem_type in base.children:
                # wrap each element in a fake 'Type' node
                wrapper = Node('Type')
                wrapper.children.append(elem_type)
                elems.append(self._stringify_type_node(wrapper))
            return "(" + ",".join(elems) + ")"

        # fallback—shouldn’t happen
        return None

 


    def check_FunctionDecl(self, node: Node):
        # 1) Find the function’s name and signature
        name_node   = next(c for c in node.children if c.typ == 'Id')
        params_node = next(c for c in node.children if c.typ == 'Params')

        param_types = []
        param_names = []
        for p in params_node.children:
            # 1) name
            vp    = next((c for c in p.children if c.typ == 'VarPattern'), None)
            pname = vp.value if (vp and vp.value) else p.value

            # 2) type: stringify whatever Type is there (primitive, array, tuple)
            tnode = next((c for c in p.children if c.typ == 'Type'), None)
            if tnode:
                # _stringify_type_node expects a Node('Type', children=[…])
                ptype = self._stringify_type_node(tnode)
            else:
                ptype = None

            param_names.append(pname)
            param_types.append(ptype)


        # 2) Compute return type (None means “void”)
        ret = None
        rnode = next((c for c in node.children if c.typ == 'ReturnType'), None)
        if rnode and rnode.children:
            # rnode.children[0] is ASTNode('Type', …)
            ret = self._stringify_type_node(rnode.children[0])

        # 3) Declare the function in the enclosing scope
        self.declare(
            name_node.value,
            'fn',
            (param_types, ret),
            False,
            name_node
        )

        # 4) Enter the function’s own scope
        prev_fn = self.current_fn
        self.current_fn = (name_node.value, ret)
        self.enter_scope()

        # 5) Declare parameters as immutable variables
        for pname, ptype in zip(param_names, param_types):
            if pname:
                self.declare(pname, 'var', ptype, False)

        # 6) Type‐check every statement in the body block
        body_wrapper = next(c for c in node.children if c.typ == 'Body')
        block        = next(c for c in body_wrapper.children if c.typ == 'Block')
        for stmt in block.children:
            self.check(stmt)

        # 7) Pop back to the outer scope
        self.exit_scope()
        self.current_fn = prev_fn

        # 8) If non‐void, ensure every path returns
        if ret is not None:
            if not self.body_always_returns(block.children):
                self.error(
                    f"Function '{name_node.value}' may not return on all paths",
                    node
                )



    def check_ReturnStmt(self, node):
        if not self.current_fn:
            return self.error("Return outside function", node)
        _, ret = self.current_fn

        # New: void functions (ret is None) may not return a value
        if ret is None and node.children:
            return self.error("Return with a value in a void function", node)

        # Existing: typed functions must match
        rtype = self.infer_type(node.children[0]) if node.children else None
        if ret and rtype and ret != rtype:
            self.error(f"Return type '{rtype}' does not match '{ret}'", node)


    def check_Call(self, node: Node):
        if not node.value:
            self.error("Missing function name in call", node)
            return
        entry = self.lookup(node.value, node)
        if not entry or entry['kind'] != 'fn':
            return

        params, ret = entry['type']
        args = [self.infer_type(c) for c in node.children]

        # 1) arity check
        if len(args) != len(params):
            self.error(f"Call to '{node.value}' expects {len(params)} args, got {len(args)}", node)
            return

        # 2) first‐use inference on parameters
        for i, (a, p) in enumerate(zip(args, params)):
            if p is None and a is not None:
                # first call: fix parameter i’s type
                params[i] = a
            elif p is not None and a is not None and p != a:
                # now that p is fixed, mismatched argument triggers an error
                self.error(
                    f"Function '{node.value}' parameter {i} was inferred as '{p}', got '{a}'",
                    node
                )


    def check_BinaryOp(self, node: Node):
        op = node.value

        # 1) If we're anywhere inside a PrintStmt, suppress operand‑type errors
        if self._inside_print(node):
            if op in ('+','-','*','/','%'):       return 'i32'
            if op in ('&&','||'):                 return 'bool'
            if op in ('<','<=','>','>=','==','!='): return 'bool'
            return None

        # 2) Pull in each side’s type (this may recurse and first‑use infer)
        lt = self.infer_type(node.children[0])
        rt = self.infer_type(node.children[1])

        # 3) If either side is still unknown, defer the check until later
        if lt is None or rt is None:
            # still return a plausible result type
            if op in ('+','-','*','/','%'):       return 'i32'
            if op in ('&&','||'):                 return 'bool'
            if op in ('<','<=','>','>=','==','!='): return 'bool'
            return None

        # 4) Now both operand types are known—enforce the rules
        if op in ('+','-','*','/','%'):
            if lt != 'i32' or rt != 'i32':
                self.error("Arithmetic operators require i32 operands", node)
            return 'i32'

        if op in ('&&','||'):
            if lt != 'bool' or rt != 'bool':
                self.error("Logical operators require bool operands", node)
            return 'bool'

        if op in ('<','<=','>','>=','==','!='):
            if lt != 'i32' or rt != 'i32':
                self.error("Relational operators require i32 operands", node)
            return 'bool'

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
            # [element; count]
            elm_t = self.infer_type(expr.children[0])
            # now extract a literal integer from expr.children[1]:
            cnt_node = expr.children[1]
            lit = None
            if cnt_node.typ == 'Number':
                lit = int(cnt_node.value, 0)
            elif cnt_node.typ == 'UnaryOp' and cnt_node.children:
                # handle unary minus/plus around a Number
                child = cnt_node.children[0]
                if child.typ == 'Number':
                    val = int(child.value, 0)
                    lit = -val if cnt_node.value == '-' else val
            if elm_t is not None and lit is not None and lit > 0:
                return f"[{elm_t};{lit}]"
            # otherwise fall back to unknown-length
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
            # produce exactly "(T1,T2,…)" so it lines up with _stringify_type_node
            parts = [self.infer_type(c) for c in expr.children]
            return "(" + ",".join(parts) + ")"


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
