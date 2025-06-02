#!/usr/bin/env python3
import os
import re
import sys
from collections import defaultdict, OrderedDict

SCRIPT_DIR        = os.path.dirname(os.path.realpath(__file__))
GRAMMAR_FILE      = os.path.join(SCRIPT_DIR, "Trust_Grammar.txt")
FIRSTFOLLOW_FILE  = os.path.join(SCRIPT_DIR, "first_follow.txt")
OUTPUT_FILE       = os.path.join(SCRIPT_DIR, "predict_table.md")

EPSILON = "ε"


def parse_grammar(grammar_path):
  
    productions = OrderedDict()
    nonterminals = []

    angle_re = re.compile(r"<([^>]+)>")
    token_re = re.compile(r'<[^>]+>|"[^"]+"|\S+')

    with open(grammar_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("//"):
                continue

            if "::=" not in line:
                continue

            lhs_part, rhs_part = line.split("::=", 1)
            m = angle_re.search(lhs_part)
            if not m:
                continue

            A = m.group(1).strip()
            if A not in productions:
                productions[A] = []
                nonterminals.append(A)

            for alt in rhs_part.split("|"):
                alt = alt.strip()
                if not alt:
                    continue

                symbols = []
                for tok in token_re.findall(alt):
                    if tok.startswith("<") and tok.endswith(">"):
                        symbols.append(tok[1:-1])       
                    elif tok.startswith('"') and tok.endswith('"'):
                        symbols.append(tok[1:-1])
                    else:
                        symbols.append(tok)

                if len(symbols) == 0:
                    symbols = [EPSILON]

                productions[A].append(symbols)

    return nonterminals, productions


def parse_first_follow(ff_path):
    FIRST  = {}
    FOLLOW = {}

    first_re  = re.compile(r"FIRST\(\s*([^\)]+)\s*\)\s*=\s*\{([^}]*)\}")
    follow_re = re.compile(r"FOLLOW\(\s*([^\)]+)\s*\)\s*=\s*\{([^}]*)\}")

    with open(ff_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            m1 = first_re.match(line)
            if m1:
                A = m1.group(1).strip()
                inside = m1.group(2).strip()
                items = { token.strip() for token in inside.split(",") if token.strip() }
                FIRST[A] = items
                continue

            m2 = follow_re.match(line)
            if m2:
                A = m2.group(1).strip()
                inside = m2.group(2).strip()
                items = { token.strip() for token in inside.split(",") if token.strip() }
                FOLLOW[A] = items
                continue

    return FIRST, FOLLOW


def compute_first_of_sequence(seq, FIRST):
    result = set()
    for sym in seq:
        if sym not in FIRST:
            result.add(sym)
            return result
        else:
            first_sym = FIRST[sym]
            result.update(first_sym - {EPSILON})
            if EPSILON in first_sym:
                continue
            else:
                return result
    result.add(EPSILON)
    return result


def build_predict_table(nonterminals, productions, FIRST, FOLLOW):
    all_terminals = set()
    for A in nonterminals:
        for x in FIRST.get(A, set()):
            if x != EPSILON and x not in nonterminals:
                all_terminals.add(x)
    if "EOF" in all_terminals:
        all_terminals.remove("EOF")
        all_terminals.add("$")

    TABLE = {
        A: { t: "error" for t in sorted(all_terminals) }
        for A in nonterminals
    }
    for A in nonterminals:
        for rhs in productions[A]:
            first_rhs = compute_first_of_sequence(rhs, FIRST)

            for a in (first_rhs - {EPSILON}):
                col = "$" if a == "EOF" else a
                TABLE[A][col] = f"{A} → {' '.join(rhs)}"
            if EPSILON in first_rhs:
                for b in FOLLOW.get(A, set()):
                    col = "$" if b == "EOF" else b
                    TABLE[A][col] = f"{A} → {EPSILON}"

    for A in nonterminals:
        for b in FOLLOW.get(A, set()):
            col = "$" if b == "EOF" else b
            if col in TABLE[A] and TABLE[A][col] == "error":
                TABLE[A][col] = "sync"

    return TABLE, sorted(all_terminals)


def print_markdown_table(nonterminals, terminals, TABLE, out_stream=sys.stdout):

    header = ["Nonterminal"] + terminals
    out_stream.write("| " + " | ".join(header) + " |\n")

    aligns = [" :–: " for _ in header]
    out_stream.write("|" + "|".join(aligns) + "|\n")

    for A in nonterminals:
        row = [A]
        for t in terminals:
            cell = TABLE[A].get(t, "error")
            row.append(cell)
        out_stream.write("| " + " | ".join(row) + " |\n")


def main():
    if not os.path.isfile(GRAMMAR_FILE):
        print(f"Error: could not find '{GRAMMAR_FILE}'", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(FIRSTFOLLOW_FILE):
        print(f"Error: could not find '{FIRSTFOLLOW_FILE}'", file=sys.stderr)
        sys.exit(1)

    nonterminals, productions = parse_grammar(GRAMMAR_FILE)
    FIRST, FOLLOW = parse_first_follow(FIRSTFOLLOW_FILE)

    TABLE, terminals = build_predict_table(nonterminals, productions, FIRST, FOLLOW)
    
    print_markdown_table(nonterminals, terminals, TABLE, out_stream=sys.stdout)

    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as fout:
            print_markdown_table(nonterminals, terminals, TABLE, out_stream=fout)
        print(f"\n→ Table also written to '{OUTPUT_FILE}'")
    except Exception as e:
        print(f"Warning: failed to write to '{OUTPUT_FILE}': {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
