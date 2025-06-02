| Nonterminal | ! | $ | ( | + | - | [ | bool | break | continue | fn | i32 | if | let | loop | println! | return | { |
| :–: | :–: | :–: | :–: | :–: | :–: | :–: | :–: | :–: | :–: | :–: | :–: | :–: | :–: | :–: | :–: | :–: | :–: |
| Program | Program → TopLevel * EOF | sync | Program → TopLevel * EOF | Program → TopLevel * EOF | Program → TopLevel * EOF | Program → TopLevel * EOF | Program → TopLevel * EOF | Program → TopLevel * EOF | Program → TopLevel * EOF | Program → TopLevel * EOF | Program → TopLevel * EOF | Program → TopLevel * EOF | Program → TopLevel * EOF | Program → TopLevel * EOF | Program → TopLevel * EOF | Program → TopLevel * EOF | error |
| TopLevel | sync | sync | sync | sync | sync | sync | sync | sync | sync | TopLevel → FunctionDecl | sync | sync | sync | sync | sync | sync | error |
| Statement | error | error | error | error | error | error | error | error | error | error | error | error | Statement → LetDecl | error | error | error | error |
| LetDecl | error | error | error | error | error | error | error | error | error | error | error | error | LetDecl → let mut ? Pattern (":" Type )? ("=" Expression )? | error | error | error | error |
| Pattern | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
| PatternList | error | error | PatternList → Pattern ("," Pattern )* | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
| AssignStmt | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
| LValue | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
| ReturnStmt | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | ReturnStmt → return Expression ? | error |
| BreakStmt | error | error | error | error | error | error | error | BreakStmt → break | error | error | error | error | error | error | error | error | error |
| ContinueStmt | error | error | error | error | error | error | error | error | ContinueStmt → continue | error | error | error | error | error | error | error | error |
| IfStmt | error | error | error | error | error | error | error | error | error | error | error | IfStmt → if Expression Block ("else" ("if" Expression Block | error | error | error | error | IfStmt → Block ))? |
| LoopStmt | error | error | error | error | error | error | error | error | error | error | error | error | error | LoopStmt → loop Block | error | error | error |
| Block | sync | sync | sync | sync | sync | sync | sync | sync | sync | sync | sync | sync | sync | sync | sync | sync | Block → { Statement * } |
| PrintStmt | error | error | error | error | error | error | error | error | error | error | error | error | error | error | PrintStmt → println! ( StringLiteral ("," (<Expression> | error | error |
| ExprStmt | ExprStmt → Expression | error | ExprStmt → Expression | ExprStmt → Expression | ExprStmt → Expression | ExprStmt → Expression | error | error | error | error | error | error | error | error | error | error | error |
| FunctionDecl | sync | sync | sync | sync | sync | sync | sync | sync | sync | FunctionDecl → fn Id ( ParamList ? ) ("->" Type )? Block | sync | sync | sync | sync | sync | sync | error |
| ParamList | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
| Param | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
| Type | error | error | error | error | error | error | Type → bool | error | error | error | error | error | error | error | error | error | error |
| TypeList | error | error | TypeList → Type ("," Type )* | error | error | TypeList → Type ("," Type )* | TypeList → Type ("," Type )* | error | error | error | TypeList → Type ("," Type )* | error | error | error | error | error | error |
| Expression | Expression → UnaryExpr (<BinaryOp> Expression )* | error | Expression → UnaryExpr (<BinaryOp> Expression )* | Expression → UnaryExpr (<BinaryOp> Expression )* | Expression → UnaryExpr (<BinaryOp> Expression )* | Expression → UnaryExpr (<BinaryOp> Expression )* | error | error | error | error | error | error | error | error | error | error | sync |
| UnaryExpr | error | error | error | UnaryExpr → + | UnaryExpr → - ) Expression | error | error | error | error | error | error | error | error | error | error | error | error |
| Primary | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
| Call | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
| ArgList | ArgList → Expression ("," Expression )* | error | ArgList → Expression ("," Expression )* | ArgList → Expression ("," Expression )* | ArgList → Expression ("," Expression )* | ArgList → Expression ("," Expression )* | error | error | error | error | error | error | error | error | error | error | error |
| TupleLiteral | error | error | TupleLiteral → ( Expression ("," Expression )* ) | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
| ArrayLiteral | ArrayLiteral → Expression ; Expression )? ] | error | ArrayLiteral → Expression ; Expression )? ] | ArrayLiteral → Expression ; Expression )? ] | ArrayLiteral → Expression ; Expression )? ] | ArrayLiteral → Expression ; Expression )? ] | error | error | error | error | error | error | error | error | error | error | error |
| Decimal | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
| Hexadecimal | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
| StringLiteral | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
| BoolLiteral | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
| Id | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
| SEMI | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error | error |
