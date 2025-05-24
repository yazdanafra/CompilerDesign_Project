# --- AST Node -------------------------------------------------------------
class ASTNode:
    def __init__(self, nodetype, token=None, children=None):
        self.nodetype = nodetype
        self.token    = token
        self.children = children or []
    def __repr__(self, level=0):
        indent = '  ' * level
        s = f"{indent}{self.nodetype}"
        if self.token and hasattr(self.token, 'lexeme'):
            s += f": {self.token.lexeme}"
        for c in self.children:
            if isinstance(c, ASTNode):
                s += "\n" + c.__repr__(level+1)
        return s