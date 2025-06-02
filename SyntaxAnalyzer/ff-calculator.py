import os

EPSILON = 'ε'
ENDMARK = '$'

# --- (your original grammar definition) ---
grammar = {
    'Program':        [['TopLevel', 'Program'], ['EOF']],
    'TopLevel':       [['FunctionDecl'], ['Statement', 'SEMI?']],
    'Statement':      [['LetDecl'], ['TypeDecl'], ['AssignStmt'], ['ReturnStmt'],
                       ['BreakStmt'], ['ContinueStmt'], ['IfStmt'], ['LoopStmt'],
                       ['PrintStmt'], ['ExprStmt']],
    'LetDecl':        [['let', 'mut?', 'Pattern', '(:', 'Type', ')?', '(=', 'Expression', ')?']],
    'Pattern':        [['Id'], ['(', 'PatternList', ')']],
    'PatternList':    [['Pattern', ',', 'PatternList'], ['Pattern']],
    'TypeDecl':       [['Type', 'Id', '(=', 'Expression', ')?']],
    'AssignStmt':     [['LValue', '=', 'Expression']],
    'LValue':         [['Id', '[', 'Expression', ']', ']*']],
    'ReturnStmt':     [['return', 'Expression?']],
    'BreakStmt':      [['break']],
    'ContinueStmt':   [['continue']],
    'IfStmt':         [['if', 'Expression', 'Block', '(else', '(if', 'Expression', 'Block', '|', 'Block', ')?', ')?']],
    'LoopStmt':       [['loop', 'Block']],
    'Block':          [['{', 'Statement*', '}']],
    'PrintStmt':      [['println!', '(', 'StringLiteral', '(,', '(Expression', '|', 'Id=Expression', '))*', ')']],
    'ExprStmt':       [['Expression']],
    'FunctionDecl':   [['fn', 'Id', '(', 'ParamList?', ')', '(->', 'Type', ')?', 'Block']],
    'ParamList':      [['Param', ',ParamList'], ['Param']],
    'Param':          [['Id', '(:', 'Type', ')?']],
    'Type':           [['bool'], ['i32'], ['(', 'TypeList', ')'], ['[', 'Type', '(;', 'Decimal', ')?', ']']],
    'TypeList':       [['Type', ',TypeList'], ['Type']],
    'Expression':     [['UnaryExpr', '(BinaryOp', 'Expression', ')*']],
    'UnaryExpr':      [['!', 'Expression'], ['+', 'Expression'], ['-', 'Expression'], ['Primary']],
    'Primary':        [['Decimal'], ['Hexadecimal'], ['StringLiteral'], ['BoolLiteral'],
                       ['TupleLiteral'], ['ArrayLiteral'], ['Call'], ['Id'],
                       ['(', 'Expression', ')'], ['Id', '[', 'Expression', ']']],
    'Call':           [['Id', '(', 'ArgList?', ')']],
    'ArgList':        [['Expression', ',ArgList'], ['Expression']],
    'TupleLiteral':   [['(', 'Expression', ',Expression*', ')']],
    'ArrayLiteral':   [['[', '(Expression', '(,Expression)*', '|', 'Expression;Expression', ')?', ']']],
}

nonterminals = set(grammar.keys())
tokens = set()
for prods in grammar.values():
    for prod in prods:
        for sym in prod:
            if sym not in nonterminals:
                tokens.add(sym)
tokens = {t for t in tokens if t not in (EPSILON,)}  

first = {A: set() for A in nonterminals}
follow = {A: set() for A in nonterminals}
follow['Program'].add(ENDMARK)

def first_of_sequence(seq):
    result = set()
    for sym in seq:
        if sym in tokens:
            result.add(sym)
            return result
        result |= (first[sym] - {EPSILON})
        if EPSILON not in first[sym]:
            return result
    result.add(EPSILON)
    return result

# Compute FIRST sets
changed = True
while changed:
    changed = False
    for A, prods in grammar.items():
        for prod in prods:
            f_old = first[A].copy()
            fo = first_of_sequence(prod)
            first[A] |= fo
            if first[A] != f_old:
                changed = True

# Compute FOLLOW sets
changed = True
while changed:
    changed = False
    for A, prods in grammar.items():
        for prod in prods:
            for i, B in enumerate(prod):
                if B in nonterminals:
                    beta = prod[i+1:]
                    f_beta = first_of_sequence(beta) if beta else {EPSILON}
                    
                    # add FIRST(beta) \ {ε} to FOLLOW(B)
                    to_add = f_beta - {EPSILON}
                    if not to_add.issubset(follow[B]):
                        follow[B] |= to_add
                        changed = True
                    
                    # if ε in FIRST(beta), add FOLLOW(A) to FOLLOW(B)
                    if EPSILON in f_beta:
                        if not follow[A].issubset(follow[B]):
                            follow[B] |= follow[A]
                            changed = True

# ---------------------------------------------------------------------
# NEW: determine output file path in same folder as this script:
script_dir = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(script_dir, 'first_follow.txt')

# Open the file for writing
with open(output_path, 'w', encoding='utf-8') as f:
    # Print + write FIRST sets
    f.write("FIRST sets:\n")
    print("FIRST sets:")
    for A in sorted(nonterminals):
        line = f"  FIRST({A}) = {{ {', '.join(sorted(first[A]))} }}\n"
        print(line, end='')
        f.write(line)

    # Print + write FOLLOW sets
    f.write("\nFOLLOW sets:\n")
    print("\nFOLLOW sets:")
    for A in sorted(nonterminals):
        line = f"  FOLLOW({A}) = {{ {', '.join(sorted(follow[A]))} }}\n"
        print(line, end='')
        f.write(line)

print(f"\nResults also saved to: {output_path}")
