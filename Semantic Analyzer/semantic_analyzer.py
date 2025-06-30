import sys
import os
from collections import defaultdict, deque

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
            if idx != -1 and (first is None or idx < first): first = idx
        indent = first if first is not None else 0
        text = line[indent:]
        parts = text.split(':', 1)
        label = parts[0].lstrip('└─├─ ')
        value = None
        if len(parts) == 2:
            raw = parts[1].strip()
            value = raw[1:-1] if raw.startswith("'") and raw.endswith("'") else raw
        node = Node(label, value)
        while stack and stack[-1][0] >= indent: stack.pop()
        if stack: stack[-1][1].add_child(node)
        else: root = node
        stack.append((indent, node))
    return root

class SemanticError(Exception): pass

class SemanticAnalyzer:
    def __init__(self, tree: Node):
        self.tree = tree
        self.errors = []
        self.scopes = [{}]
        self.current_fn = None

    def error(self, msg, node=None):
        ctx = f" [at {node.typ} '{node.value}']" if node else ''
        self.errors.append(msg + ctx)

    def enter_scope(self):
        self.scopes.append({})

    def exit_scope(self):
        self.scopes.pop()

    def declare(self, name, kind, typ, mutable=False, node=None):
        sym = self.scopes[-1]
        if name in sym:
            self.error(f"Redeclaration of {kind} '{name}'", node)
        sym[name] = (kind, typ, mutable)

    def lookup(self, name, node=None):
        for scope in reversed(self.scopes):
            if name in scope: return scope[name]
        self.error(f"Use of undeclared identifier '{name}'", node)
        return None, None, False

    def check(self, node: Node):
        fn = getattr(self, f"check_{node.typ}", self.generic_check)
        return fn(node)

    def generic_check(self, node: Node):
        for c in node.children: self.check(c)

    def check_Program(self, node: Node):
        self.generic_check(node)
        # verify main
        main_entry = None
        for scope in self.scopes:
            if 'main' in scope and scope['main'][0]=='fn': main_entry = scope['main']
        if not main_entry or len(main_entry[1][0])!=0:
            self.error("Function 'main' with no parameters not defined")

    def check_LetDecl(self, node: Node):
        pat = next((c for c in node.children if c.typ=='Pattern'), None)
        if not pat: return self.error("Invalid LetDecl: missing pattern", node)
        # handle VarPattern or TuplePattern
        def get_vars(pat_node):
            if not pat_node.children: return []
            child = pat_node.children[0]
            if child.typ=='VarPattern': return [child]
            if child.typ=='TuplePattern': return [c for c in child.children if c.typ=='VarPattern']
            return []
        vars = get_vars(pat)
        if not vars: return self.error("Invalid LetDecl: no variable in pattern", pat)
        mutable = any(c.typ=='MutKw' for c in node.children)
        declared_type = None
        if any(c.typ=='Colon' for c in node.children):
            idx = next(i for i,c in enumerate(node.children) if c.typ=='Colon')
            tnode = node.children[idx+1]
            if tnode.children: declared_type = tnode.children[0].typ.lower()
        expr = next((c for c in node.children if c.typ=='Expr'), None)
        inferred = self.infer_type(expr)
        for var in vars:
            name = var.value
            if declared_type and inferred and declared_type!=(inferred.lower() if isinstance(inferred,str) else inferred):
                self.error(f"Type mismatch: declared '{declared_type}' vs initialized '{inferred}'", var)
            self.declare(name,'var',declared_type or inferred,mutable,var)

    def check_FunctionDecl(self, node: Node):
        name_node = next(c for c in node.children if c.typ=='Id')
        params_node = next(c for c in node.children if c.typ=='Params')
        # gather param types/names
        param_types=[]; param_names=[]
        for p in params_node.children:
            # p.typ == Param, child Type
            t = None
            if p.children and p.children[0].typ=='Type':
                t = p.children[0].children[0].typ.lower()
            param_types.append(t)
            # Param may wrap VarPattern or be direct 'Param' with no value
            # Try find VarPattern inside
            vp = next((c for c in p.children if c.typ=='VarPattern'), None)
            if vp: param_names.append(vp.value)
        # return type
        rnode = next((c for c in node.children if c.typ=='ReturnType'), None)
        ret_type = None
        if rnode and rnode.children:
            # assume single Type child
            ret_type = rnode.children[0].children[0].typ.lower()
        self.declare(name_node.value,'fn',(param_types,ret_type),False,name_node)
        # check body
        self.enter_scope()
        for nm, tp in zip(param_names,param_types):
            self.declare(nm,'var',tp,False)
        body = next(c for c in node.children if c.typ=='Body')
        self.check(body)
        self.exit_scope()

    def infer_type(self, expr: Node):
        if not expr or not expr.children: return None
        c = expr.children[0]
        if c.typ=='BoolLiteral': return 'bool'
        if c.typ=='Number': return 'i32'
        if c.typ=='TupleLiteral': return tuple(self.infer_type(x) for x in c.children)
        if c.typ=='ArrayLiteral':
            types=[self.infer_type(x) for x in c.children]
            if None in types: return None
            if all(t==types[0] for t in types): return f"[{types[0]};{len(types)}]"
            self.error("Heterogeneous array literal types",c); return None
        if c.typ=='Id': return self.lookup(c.value,c)[1]
        return None

    def report(self, input_path:str):
        if self.errors:
            for e in self.errors: print(f"Semantic error: {e}")
            sys.exit(1)
        print("Program was compiled successfully")
        with open('syntax_tree.txt','w',encoding='utf-8') as f: f.write(repr(self.tree))

if __name__=='__main__':
    script_dir=os.path.dirname(os.path.abspath(__file__))
    fn=sys.argv[1] if len(sys.argv)>1 else 'parse_tree.txt'
    inp=os.path.join(script_dir,fn)
    if not os.path.exists(inp): print(f"Parse tree file '{inp}' not found."); sys.exit(1)
    tree=parse_tree_from_file(inp)
    ana=SemanticAnalyzer(tree)
    ana.check(tree)
    ana.report(inp)
