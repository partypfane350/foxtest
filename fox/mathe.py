# ehemals calc.py → jetzt Mathe-Modul
import ast, math, operator as op

_ALLOWED_OPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
    ast.FloorDiv: op.floordiv, ast.Mod: op.mod, ast.Pow: op.pow,
    ast.USub: op.neg, ast.UAdd: op.pos
}
_ALLOWED_FUNCS = {
    "abs": abs, "round": round,
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "ln": math.log, "log10": math.log10, "exp": math.exp,
    "ceil": math.ceil, "floor": math.floor
}
_ALLOWED_CONST = {"pi": math.pi, "e": math.e}

def _eval_ast(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int,float)): return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_ast(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_ast(node.left), _eval_ast(node.right))
    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_CONST: return _ALLOWED_CONST[node.id]
        raise ValueError(f"Unbekannte Konstante: {node.id}")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        fn = node.func.id
        if fn not in _ALLOWED_FUNCS: raise ValueError(f"Unerlaubte Funktion: {fn}")
        if node.keywords: raise ValueError("Keine Keyword-Argumente erlaubt")
        args = [_eval_ast(a) for a in node.args]
        return _ALLOWED_FUNCS[fn](*args)
    raise ValueError("Unerlaubter Ausdruck")

def normalize_expr(text: str) -> str:
    s = text.lower()
    for ph in ["was ist","wie viel ist","wie viel sind","rechne","berechne",
               "=","ist gleich","bitte","?"]:
        s = s.replace(ph, " ")
    s = s.replace(",", ".").replace("×","*").replace("x","*").replace("•","*")
    s = s.replace("÷","/").replace(":", "/").replace("^", "**")
    s = s.replace("% von", "/100*").replace("%of", "/100*").replace("%", "/100")
    return " ".join(s.split())

def safe_calc(expr: str) -> float:
    tree = ast.parse(expr, mode="eval")
    return _eval_ast(tree.body)

def try_auto_calc(user_text: str):
    t = user_text.lower()
    has_digit = any(ch.isdigit() for ch in t)
    has_op = any(sym in t for sym in "+-*/×x÷:^%")
    looks_math = (has_digit and has_op) or any(p in t for p in ["was ist","rechne","berechne"])
    if not looks_math: return None
    expr = normalize_expr(user_text)
    if not expr: return None
    try:
        return safe_calc(expr)
    except Exception:
        return None
