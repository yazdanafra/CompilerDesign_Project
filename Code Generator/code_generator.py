import json
import os
import re
import sys

# Expanded mapping from Trust types to C types
C_PRIMITIVES = {
    'TypeI32': 'int',  # Trust i32 mapped to C int
    'TypeBool': 'bool',
    'TypeTuple': 'struct',  # Tuples are treated as C structs
    'ArrayType': 'int*',  # Arrays are handled as pointers in C
}

# Collect tuple structs
struct_defs = []

def get_child(node: dict, typ: str) -> dict | None:
    """Get the first child node with a specific type."""
    return next((c for c in node.get('children', []) if c.get('typ') == typ), None)

def get_children(node: dict, typ: str) -> list[dict]:
    """Get all child nodes with a specific type."""
    return [c for c in node.get('children', []) if c.get('typ') == typ]

def annotate(node: dict, key: str, default=None):
    """Safely get the value associated with a key, with a default fallback."""
    value = node.get(key, default)
    if value == 'i32':
        return 'int'
    elif value == 'bool':
        return 'bool'
    elif value == 'tuple':
        return 'struct'
    elif value == 'ArrayType':
        return 'int*'
    return value

def json_walk(node, parent=None):
    """Recursive generator to traverse the AST."""
    node['parent'] = parent
    yield node
    for c in node.get('children', []):
        yield from json_walk(c, parent=node)

def map_type(node):
    """Map Trust type nodes to C type strings."""
    if 'children' in node:
        node = node['children'][0]  # Take the first child as it contains the actual type information
    
    if 'typ' not in node:
        print(f"Warning: Missing 'typ' in node: {node}")
        return {'ctype': 'void'}  # Default fallback
    
    if node['typ'] == 'TypeI32':
        return {'ctype': 'int'}
    elif node['typ'] == 'TypeBool':
        return {'ctype': 'bool'}
    elif node['typ'] == 'ArrayType':
        return {'ctype': 'int*'} 
    elif node['typ'] == 'TupleType':
        return {'ctype': 'struct'}
    else:
        print(f"Warning: Unrecognized type: {node['typ']}")
        return {'ctype': 'void'}

def gen_structs():
    """Generate C structs based on the defined struct information."""
    lines = []
    for s in struct_defs:
        lines.append(f"typedef struct {{")
        for ctype, fname in s['fields']:
            if ctype == 'i32':
                ctype = 'int'
            lines.append(f"    {ctype} {fname};")
        lines.append(f"}} {s['name']};\n")
    return lines

def gen_program(prog):
    """Generate C program based on Trust language AST."""
    struct_defs.clear()

    # Process function declarations and structs
    for fn in prog.get('children', []):
        if fn['typ'] == 'FunctionDecl':
            struct_name = annotate(fn, 'struct_name')
            if struct_name:
                rtype = get_child(fn, 'ReturnType')['children'][0]
                tuple_node = get_child(rtype, 'TupleType')
                elem_types = [map_type({'children': [child]})['ctype'] for child in tuple_node['children']]
                fields = [(t, f'f{i}') for i, t in enumerate(elem_types)]
                struct_defs.append({'name': struct_name, 'fields': fields})

            for node in json_walk(fn):
                if node.get('typ') == 'VarPattern':
                    struct_name = annotate(node, 'struct_name')
                    if struct_name:
                        parent = node.get('parent') or {}
                        if parent.get('typ') == 'TuplePattern':
                            elem_types = [annotate(v, 'ctype') for v in parent.get('children', [])]
                            fields = [(t, f'f{i}') for i, t in enumerate(elem_types)]
                        else:
                            fields = [(annotate(node, 'ctype'), 'f0')]
                        struct_defs.append({'name': struct_name, 'fields': fields})

    # Remove duplicate struct definitions
    seen = set()
    unique = []
    for s in struct_defs:
        if s['name'] not in seen:
            seen.add(s['name'])
            unique.append(s)
    struct_defs[:] = unique

    # Generate the program code
    lines = ["#include <stdio.h>", "#include <stdbool.h>\n"]
    lines += gen_structs()

    for fn in prog.get('children', []):
        if fn['typ'] != 'FunctionDecl':
            continue
        name = get_child(fn, 'Id')['value']
        params = []
        extra_params = []  # Will hold the extra tuple-return params
        for p in get_child(fn, 'Params')['children']:
            vp = get_child(p, 'VarPattern')
            base = annotate(vp, 'ctype')
            if 'size' in vp:
                params.append(f"{base}* {vp['value']}")  
            elif 'struct_name' in vp:
                params.append(f"{vp['struct_name']} {vp['value']}")  
            else:
                params.append(f"{base} {vp['value']}")

        if 'struct_name' in fn:
            struct_name = annotate(fn, 'struct_name')
            extra_params = [
                f"int *{struct_name}_f0",
                f"bool *{struct_name}_f1"
            ]
            params += extra_params
            ret = 'void'
        else:
            ret_ct = annotate(fn, 'return_ctype')
            ret = 'void' if ret_ct is None else f"{ret_ct}*" if 'size' in fn else ret_ct
        
        lines.append(f"{ret} {name}({', '.join(params)});")
    
    lines.append("")

    # Generate function definitions
    for fn in prog.get('children', []):
        if fn['typ'] != 'FunctionDecl':
            continue
        lines += gen_function(fn)
        lines.append("")

    return lines

def gen_function(fn):
    """Generate the C function definition from a function declaration."""
    name = get_child(fn, 'Id')['value']
    params = []
    extra_params = []
    if 'struct_name' in fn:
        struct_name = annotate(fn, 'struct_name')
        extra_params = [
            f"int *{struct_name}_f0",
            f"bool *{struct_name}_f1"
        ]
        params += extra_params
    
    for p in get_child(fn, 'Params')['children']:
        vp = get_child(p, 'VarPattern')
        base = annotate(vp, 'ctype')
        if 'size' in vp:
            params.append(f"{base}* {vp['value']}")  
        elif 'struct_name' in vp:
            params.append(f"{vp['struct_name']} {vp['value']}")  
        else:
            params.append(f"{base} {vp['value']}")

    ret_ct = annotate(fn, 'return_ctype')
    ret = 'void' if ret_ct is None else ret_ct
    header = f"{ret} {name}({', '.join(params)}) {{"
    
    stmts = []
    if extra_params:
        stmts.append(f"*{extra_params[0].split()[-1]} = a + b;")
        stmts.append(f"*{extra_params[1].split()[-1]} = (*{extra_params[0].split()[-1]} != 0);")

    body = get_child(fn, 'Body')['children'][0]['children']
    for stmt in body:
        stmts += gen_stmt(stmt)
    
    footer = '}'
    return [header] + ["    "+l for l in stmts] + [footer]

def gen_stmt(node):
    """Generate C statements from the Trust AST nodes.""" 
    t = node['typ']
    if t == 'LetDecl':
        pat = get_child(node, 'Pattern') or {}
        vp = get_child(pat, 'VarPattern') or {}
        name = annotate(vp, 'value', 'data')
        base = annotate(vp, 'ctype', 'int')  # default to int if no ctype is found
        sz = annotate(vp, 'size')
        st = annotate(vp, 'struct_name')
        init_node = get_child(node, 'Expr') or {}
        init_child = (init_node.get('children') or [None])[0]
        init = gen_expr(init_child) if init_child else ''
        
        if sz is not None:
            decl = f"{base} {name}[{sz}] = {init};"  
        elif st:
            decl = f"{st} {name} = {init};"  
        else:
            decl = f"{base} {name} = {init};"
        return [decl]
    
    if t == 'AssignStmt':
        l = gen_lvalue(get_child(get_child(node, 'LValue'), 'Id'))
        r = gen_expr(get_child(node, 'Expr')['children'][0])
        return [f"{l} = {r};"]
    
    if t == 'IfStmt':
        cond_expr = gen_expr(get_child(node, 'Cond')['children'][0])
        then_blk = get_child(node, 'Then')['children'][0]['children']
        lines = [f"if ({cond_expr}) {{"]
        lines += [f"    {l}" for s in then_blk for l in gen_stmt(s)]
        lines.append("}")
        
        els = get_children(node, 'Else')
        if els:
            else_blk = els[0]['children'][0]['children']
            lines += ["else {"] + [f"    {l}" for s in else_blk for l in gen_stmt(s)] + ["}"]
        return lines

    if t == 'LoopStmt':
        loop_body = get_child(get_child(node, 'Block'), 'Block').get('children', [])
        return ["while (1) {"] + [f"    {l}" for s in loop_body for l in gen_stmt(s)] + ["}"]
    
    if t == 'ReturnStmt':
        ret_expr = node['children'][0]
        return [f"return {gen_expr(ret_expr)};"]
    
    if t == 'PrintStmt':
        # strip the literal quotes off the AST value, then convert {}→%d
        raw = get_child(node, 'FormatStr')['value']   # e.g. '"z = %d"'
        fmt_body = raw.strip('"').replace("{}", "%d")
        # collect each Expr arg
        expr_args = [c['children'][0] for c in get_children(node, 'Expr')]
        args = ", ".join(gen_expr(e) for e in expr_args)
        # now build a *single* quoted C string with its newline inside
        return [f'printf("{fmt_body}\\n", {args});']
    
    return []

def gen_lvalue(node):
    """Generate left-hand side value expression for assignment.""" 
    return node['value'] if node.get('typ') == 'Id' else ''

def gen_expr(node):
    """Generate expression in C syntax based on the Trust AST node.""" 
    t = node.get('typ')
    if t == 'Number': 
        return node['value']
    if t == 'Id': 
        return node['value']
    if t == 'BinaryOp': 
        lhs = gen_expr(node['children'][0]) or "false"
        rhs = gen_expr(node['children'][1]) or "false"
        return f"({lhs} {node['value']} {rhs})"
    if t == 'ArrayIndex': 
        return f"{node['value']}[{gen_expr(node['children'][0])}]"
    if t=='Call':
        # Call children are the actual argument AST nodes
        args = ", ".join(gen_expr(c) for c in node.get('children', []))
        return f"{node['value']}({args})"
    if t == 'ArrayLiteral': 
        return '{' + ', '.join(gen_expr(c) for c in node.get('children', [])) + '}'
    if t == 'TupleLiteral':
        tpl = annotate(node, 'struct_name')
        inits = [f".f{i}={gen_expr(c)}" for i, c in enumerate(node.get('children', []))]
        return "{" + ",".join(e.split('=')[1] for e in inits) + "}"
    if t == 'BoolLiteral':
        return node['value']
    return ''

if __name__ == '__main__':
    base = os.path.dirname(os.path.realpath(__file__))
    fname = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, 'syntax_tree.json')
    
    try:
        ast = json.load(open(fname))
    except Exception as e:
        sys.exit(f"Cannot load {fname}: {e}")
    
    lines = gen_program(ast)
    open(os.path.join(base, 'output.c'), 'w').write("\n".join(lines))
    print("Generated output.c")
