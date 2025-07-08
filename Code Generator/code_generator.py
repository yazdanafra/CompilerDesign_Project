import json
import os
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


def translate_format(raw: str) -> str:
    """
    Given a Rust style format string literal (including the surrounding quotes),
    return a C format string with %d in place of any {...} placeholder,
    preserving escapes, and still as a quoted C string.
    """
    # strip leading & trailing quote
    inner = raw[1:-1]

    out = ""
    i = 0
    n = len(inner)
    while i < n:
        ch = inner[i]
        if ch == '{':
            # skip until matching '}', drop the contents
            while i < n and inner[i] != '}':
                i += 1
            # now inner[i] == '}', or i == n
            out += "%d"
            i += 1
        else:
            # normal char (including possible % or backslashes)
            out += ch
            i += 1

    # escape any literal "%" (Rust uses "{}" only, so % wouldn't appear normally,
    # but just in case): double up.
    out = out.replace("%", "%%")

    # return with C quotes
    return f"\"{out}\""


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
    struct_defs.clear()

    # 1) Collect all top‐level lets as C globals
    globals_code = []
    for node in prog['children']:
        if node['typ'] != 'LetDecl':
            continue

        # unwrap Pattern → VarPattern
        pat = get_child(node, 'Pattern')
        if not pat:
            continue
        vp = get_child(pat, 'VarPattern')
        if not vp:
            continue

        ctype = annotate(vp, 'ctype') or 'int'
        name  = vp['value']
        size  = vp.get('size')

        # initializer (if any)
        init_expr = None
        expr_wrap = get_child(node,'Expr')
        if expr_wrap and expr_wrap.get('children'):
            init_node = expr_wrap['children'][0]
            # unwrap unary plus/minus if necessary
            # gen_expr must handle Number, BinaryOp, UnaryOp, etc.
            init_expr = gen_expr(init_node)

        # default initializer if none
        if init_expr is None:
            init_expr = 'false' if ctype == 'bool' else '0'

        if size is not None:
            globals_code.append(f"{ctype} {name}[{size}] = {init_expr};")
        else:
            globals_code.append(f"{ctype} {name} = {init_expr};")



    # (a) named tuple returns
    for fn in prog.get('children', []):
        if fn['typ'] != 'FunctionDecl':
            continue
        struct_name = annotate(fn, 'struct_name')
        if struct_name:
            rtype      = get_child(fn, 'ReturnType')['children'][0]
            tuple_node = get_child(rtype, 'TupleType')
            fields     = [
                (map_type({'children': [c]})['ctype'], f'f{i}')
                for i, c in enumerate(tuple_node['children'])
            ]
            struct_defs.append({'name': struct_name, 'fields': fields})
        

    # (b) parameter‑tuple structs
    for fn in prog.get('children', []):
        if fn['typ'] != 'FunctionDecl':
            continue


        # look at each Param under Params
        for param in get_child(fn, 'Params')['children']:
            varpat = get_child(param, 'VarPattern')
            struct_name = annotate(varpat, 'struct_name')
            # only process tuple parameters
            if not struct_name:
                continue

            # the Param node has a child 'Type' or 'TypeAnnotation'
            type_node = get_child(param, 'Type') or get_child(param, 'TypeAnnotation')
            tup_node  = get_child(type_node, 'TupleType') if type_node else None
            if not tup_node:
                continue  # not a tuple parameter?

            # now build each field type from the tuple’s element types
            elem_cts = []
            for elem in tup_node['children']:
                if elem['typ'] == 'TypeI32':      elem_cts.append('int')
                elif elem['typ'] == 'TypeBool':   elem_cts.append('bool')
                elif elem['typ'] == 'ArrayType':  elem_cts.append('int*')
                else:                            elem_cts.append('void')

            fields = [(ctype, f"f{i}") for i, ctype in enumerate(elem_cts)]
            struct_defs.append({'name': struct_name, 'fields': fields})

    # (c) let‐binding tuple structs
    for fn in prog.get('children', []):
        if fn['typ'] != 'FunctionDecl':
            continue

        # iterate over all LetDecls in this function body
        body_stmts = get_child(fn, 'Body')['children'][0]['children']
        for stmt in body_stmts:
            if stmt['typ'] != 'LetDecl':
                continue

            # unwrap the Pattern wrapper
            pat_wrapper = get_child(stmt, 'Pattern')
            if not pat_wrapper:
                continue

            #
            # (c1) single‐binding with explicit tuple type:
            #      let t: (i32,bool) = …
            #
            # check for a single VarPattern carrying struct_name
            vp = get_child(pat_wrapper, 'VarPattern')
            struct_name = annotate(vp, 'struct_name') if vp else None

            # check if this same stmt has a Type → TupleType
            type_node = get_child(stmt, 'Type')
            tup_node  = get_child(type_node, 'TupleType') if type_node else None

            if struct_name and tup_node:
                # build C field types from the TupleType children
                elem_cts = []
                for elem in tup_node['children']:
                    if elem['typ'] == 'TypeI32':
                        elem_cts.append('int')
                    elif elem['typ'] == 'TypeBool':
                        elem_cts.append('bool')
                    elif elem['typ'] == 'ArrayType':
                        elem_cts.append('int*')
                    else:
                        elem_cts.append('void')

                fields = [(ctype, f"f{i}") for i, ctype in enumerate(elem_cts)]
                struct_defs.append({'name': struct_name, 'fields': fields})

                # we’ve generated this struct—skip to next LetDecl
                continue

            #
            # (c2) destructuring‐binding:
            #      let (a, b) = t
            #      pattern is TuplePattern of VarPatterns,
            #      but no Type annotation here
            #
            # look for a TuplePattern anywhere under the Pattern wrapper
            pat = None
            stack = [pat_wrapper]
            while stack:
                nd = stack.pop()
                if nd.get('typ') == 'TuplePattern':
                    pat = nd
                    break
                for ch in nd.get('children', []):
                    stack.append(ch)

            if not pat:
                # no TuplePattern, move on
                continue

            # each VarPattern child will carry the same struct_name
            # pick the first one to record the struct (fields were already
            # generated in c1, so we don’t append here—this pass just
            # ensures your code knows the struct_name exists)
            first_vp = next((c for c in pat['children'] if c['typ'] == 'VarPattern'), None)
            if not first_vp or 'struct_name' not in first_vp:
                continue

            # nothing more to do—the struct was already defined in c1
            # (if you ever want to recalc fields here, you could, but it's
            # redundant since we already appended above)
            # continue to next LetDecl
            continue


    # (d) global tuple‐let structs
    for node in prog['children']:
        if node['typ'] != 'LetDecl': 
            continue
        # explicit Type → TupleType?
        type_node = get_child(node,'Type')
        tup_node  = get_child(type_node,'TupleType') if type_node else None
        if not tup_node:
            continue
        pat = get_child(node,'Pattern')
        vp  = get_child(pat,'VarPattern') if pat else None
        struct_name = annotate(vp,'struct_name') if vp else None
        if not struct_name:
            continue
        # gather element ctypes
        fields = []
        for i, elem in enumerate(tup_node['children']):
            c = map_type({'children':[elem]})['ctype']
            fields.append((c,f"f{i}"))
        struct_defs.append({'name': struct_name, 'fields': fields})
    


    # dedupe
    unique, seen = [], set()
    for s in struct_defs:
        if s['name'] not in seen:
            seen.add(s['name'])
            unique.append(s)
    struct_defs[:] = unique

    # 2) Emit headers + typedefs first
    lines = [
    "#include <stdio.h>",
    "#include <stdbool.h>",
    ""
    ]
    lines += gen_structs()      # <<— BEFORE any globals that use them
    lines.append("")            # blank line

    # 3) Now emit your globals, which can safely reference tuple types
    lines += globals_code
    lines.append("")

    # forward‐declare prototypes
    for fn in prog.get('children', []):
        if fn['typ'] != 'FunctionDecl':
            continue

        name   = get_child(fn, 'Id')['value']
        params = []
        for p in get_child(fn, 'Params')['children']:
            vp = get_child(p, 'VarPattern')
            if 'size' in vp:
                params.append(f"{annotate(vp,'ctype')}* {vp['value']}")
            elif 'struct_name' in vp:
                params.append(f"{annotate(vp,'struct_name')} {vp['value']}")
            else:
                params.append(f"{annotate(vp,'ctype')} {vp['value']}")

        if 'struct_name' in fn:
            ret = annotate(fn, 'struct_name')
        else:
            ret = annotate(fn, 'return_ctype') or 'void'

        lines.append(f"{ret} {name}({', '.join(params)});")

    lines.append("")

    # definitions
    for fn in prog.get('children', []):
        if fn['typ'] == 'FunctionDecl':
            lines += gen_function(fn)
            lines.append("")

    return lines


def gen_function(fn):
    """Generate the C function definition from a function declaration."""
    name   = get_child(fn, 'Id')['value']
    params = []
    # build params (no tuple‐out pointers)
    for p in get_child(fn, 'Params')['children']:
        vp = get_child(p, 'VarPattern')
        if 'size' in vp:
            params.append(f"{annotate(vp,'ctype')}* {vp['value']}")
        elif 'struct_name' in vp:
            params.append(f"{annotate(vp,'struct_name')} {vp['value']}")
        else:
            params.append(f"{annotate(vp,'ctype')} {vp['value']}")

    # choose return type
    if 'struct_name' in fn:
        ret = annotate(fn, 'struct_name')
    else:
        ret = annotate(fn, 'return_ctype') or 'void'

    header = f"{ret} {name}({', '.join(params)}) {{"
    footer = "}"

    stmts = []

    # handle tuple‐return by value
    struct_name = annotate(fn, 'struct_name')
    if struct_name:
        # --- new code: build sum & flag locals ---
        body = get_child(fn, 'Body')['children'][0]['children']
        stmts = []
        for stmt in body:
            if stmt['typ'] == 'LetDecl':
                # your existing let‐stmt code will generate "int sum = a + b;"
                stmts += gen_stmt(stmt)
        # --- now the return ---
        # find the ReturnStmt as before
        ret_stmt = next(s for s in body if s['typ'] == 'ReturnStmt')
        child    = ret_stmt['children'][0]
        tpl      = child['children'][0] if child.get('typ') == 'Expr' else child
        vals     = [gen_expr(c) for c in tpl['children']]
        init     = "{" + ", ".join(vals) + "}"
        stmts.append(f"{struct_name} tmp = {init};")
        stmts.append("return tmp;")
        return [header] + ["    " + l for l in stmts] + [footer]
    

    # otherwise normal body
    body = get_child(fn, 'Body')['children'][0]['children']
    for stmt in body:
        stmts += gen_stmt(stmt)

    return [header] + ["    " + l for l in stmts] + [footer]


def gen_stmt(node):
    t = node['typ']
    
    if t == 'LetDecl':
        pat_wrap = get_child(node, 'Pattern')
        if not pat_wrap:
            return []

        # Unwrap initializer (if present)
        expr_wrap = get_child(node, 'Expr')
        init_node = None
        if expr_wrap and expr_wrap.get('children'):
            init_node = expr_wrap['children'][0]

        # A) Explicit tuple binding:  let t: (i32,bool) = (...);
        #    VarPattern will carry struct_name, and a Type→TupleType exists.
        vp0 = next((c for c in pat_wrap['children']
                if c['typ'] == 'VarPattern'), None)
        type_node = get_child(node, 'Type')
        tup_node  = get_child(type_node, 'TupleType') if type_node else None

        if vp0 and 'struct_name' in vp0 and tup_node:
            struct_name = vp0['struct_name']
            var_name    = vp0['value']
            init_code   = gen_expr(init_node) if init_node else "{}"
            return [f"{struct_name} {var_name} = {init_code};"]

        # B) Destructuring: let (a, b) = some_tuple;
        #    Pattern wrapper has a TuplePattern child.
        tpl_pat = next((c for c in pat_wrap['children']
                        if c['typ'] == 'TuplePattern'), None)
        if tpl_pat:
            # the first VarPattern carries the struct_name
            first_vp = tpl_pat['children'][0]
            if not first_vp or 'struct_name' not in first_vp:
                return []
            struct_name = first_vp['struct_name']

            # find the struct entry so we know each field’s C type
            entry = next((sd for sd in struct_defs if sd['name'] == struct_name), None)
            if not entry:
                return []

            # expression text (e.g. "myTupleVar" or a call)
            expr_code = gen_expr(init_node) if init_node else ""
            code = []
            for idx, vp in enumerate(tpl_pat['children']):
                field_name = vp['value']
                field_type = entry['fields'][idx][0]   # e.g. "int" or "bool"
                code.append(f"{field_type} {field_name} = {expr_code}.f{idx};")
            return code

        # C) Simple single‐var let:  let x = ...;  or arrays
        #    Find lone VarPattern
        vp = next((c for c in pat_wrap['children']
                if c['typ'] == 'VarPattern'), None)
        if not vp:
            return []

        base     = annotate(vp, 'ctype') or 'int'
        var_name = vp['value']
        size     = vp.get('size')    # for arrays, e.g. [i32; N]
        init_code = gen_expr(init_node) if init_node else ""

        if size is not None:
            # array declaration
            return [f"{base} {var_name}[{size}] = {init_code};"]
        else:
            # plain scalar
            return [f"{base} {var_name} = {init_code};"]


    # ---- 2) assignment ----
    if t == 'AssignStmt':
        l = gen_lvalue(get_child(get_child(node,'LValue'),'Id'))
        r = gen_expr(get_child(node,'Expr')['children'][0])
        return [f"{l} = {r};"]

    # ---- 3) if/else ----
    if t == 'IfStmt':
        # 1) Unwrap the condition
        cond_wrapper = get_child(node, 'Cond')
        if not cond_wrapper or not cond_wrapper.get('children'):
            # Missing Cond or empty children: default to false (or handle error)
            cond_code = "false"
        else:
            # The first child of Cond is often an Expr‐wrapper or direct expression
            inner = cond_wrapper['children'][0]
            # If that inner node is an Expr, unwrap one more level
            expr_node = inner['children'][0] if inner.get('typ') == 'Expr' else inner
            cond_code = gen_expr(expr_node)

        # 2) Unwrap the Then block
        then_wrapper = get_child(node, 'Then')
        then_blk = []
        if then_wrapper and then_wrapper.get('children'):
            # Then → [ Block ] → [ statements... ]
            block = then_wrapper['children'][0]
            then_blk = block.get('children', [])

        # 3) Emit the if line
        lines = [f"if ({cond_code}) {{"]
        for stmt in then_blk:
            for ln in gen_stmt(stmt):
                lines.append(f"    {ln}")
        lines.append("}")

        # 4) Optionally unwrap the Else block
        else_wrapper = get_child(node, 'Else')
        if else_wrapper and else_wrapper.get('children'):
            block = else_wrapper['children'][0]
            else_blk = block.get('children', [])
            lines.append("else {")
            for stmt in else_blk:
                for ln in gen_stmt(stmt):
                    lines.append(f"    {ln}")
            lines.append("}")

        return lines


    # ---- 4) while / break / return / print ----
    if t == 'LoopStmt':
        body = get_child(get_child(node,'Block'),'Block')['children']
        code = ["while (1) {"]
        for s in body:
            for ln in gen_stmt(s):
                code.append(f"    {ln}")
        code.append("}")
        return code
    if t == 'BreakStmt':
        return ["break;"]
    if t == 'ReturnStmt':
        if not node.get('children'):
            return ["return;"]
        child = node['children'][0]
        expr  = child['children'][0] if child['typ']=='Expr' else child
        return [f"return {gen_expr(expr)};"]
    if node['typ'] == 'PrintStmt':
        raw = get_child(node, 'FormatStr')['value']   # e.g. "\"No return, x = {x}\""
        inner = raw[1:-1]                             # strip the outer quotes

        out = ""
        i = 0
        n = len(inner)
        while i < n:
            if inner[i] == '{':
                # skip until the matching '}'
                while i < n and inner[i] != '}':
                    i += 1
                # consume the '}'
                if i < n and inner[i] == '}':
                    i += 1
                # emit a C %d placeholder
                out += "%d"
            else:
                out += inner[i]
                i += 1

        # add newline and re‑quote
        c_fmt = f"\"{out}\\n\""

        # collect all Expr arguments
        args = [gen_expr(wrap['children'][0])
                for wrap in get_children(node, 'Expr')]

        if args:
            return [f"printf({c_fmt}, {', '.join(args)});"]
        else:
            return [f"printf({c_fmt});"]


    # default: nothing
    return []




def gen_lvalue(node):
    """Generate left-hand side value expression for assignment.""" 
    return node['value'] if node.get('typ') == 'Id' else ''

def gen_expr(node):
    """Generate expression in C syntax based on the Trust AST node.""" 
    t = node.get('typ')
    if t == 'Number': 
        return node['value']
    if t == 'UnaryOp' and node['value'] in ('-','+'):
        return node['value'] + gen_expr(node['children'][0])
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
    with open(os.path.join(base, 'output.c'), 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    print("Generated output.c")
