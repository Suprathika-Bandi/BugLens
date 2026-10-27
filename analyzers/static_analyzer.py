import ast
import builtins
import re

PYTHON_BUILTINS = {
    "list", "dict", "str", "int", "float", "bool", "set", "tuple",
    "len", "id", "type", "max", "min", "sum", "range", "dir",
    "open", "input", "print", "format", "map", "filter", "all", "any",
}


def find_unused_variables(code):
    """Detect variables that are assigned but never loaded."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    assigned_variables = set()
    used_variables = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                assigned_variables.add(node.id)
            elif isinstance(node.ctx, ast.Load):
                used_variables.add(node.id)

    unused_variables = assigned_variables - used_variables
    # Ignore Python's conventional throwaway variable
    unused_variables.discard("_")

    return list(unused_variables)


def find_unused_imports(code):
    """Detect imported modules or symbols that are never used."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    imported_names = set()
    used_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name.split(".")[0]
                imported_names.add(name)

        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imported_names.add(name)

        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                used_names.add(node.id)

    unused_imports = imported_names - used_names
    return list(unused_imports)


def find_mutable_defaults(code):
    """Detect functions using mutable objects (list, dict, set) as default arguments."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    mutable_defaults = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    mutable_defaults.append({
                        "function": node.name,
                        "line": node.lineno,
                    })

    return mutable_defaults


def find_bare_except(code):
    """Detect except blocks with no exception type specified."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    bare_excepts = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                bare_excepts.append({
                    "line": node.lineno,
                })

    return bare_excepts


def find_broad_except(code):
    """Detect broad exception catching with silent pass."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    broad_excepts = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is not None:
                if isinstance(node.type, ast.Name) and node.type.id in ("BaseException", "Exception"):
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        broad_excepts.append({
                            "line": node.lineno,
                            "type": node.type.id,
                        })

    return broad_excepts


def find_undefined_variables(code):
    """Detect variables that are loaded before being defined in scope."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    builtin_names = set(dir(builtins))
    undefined_variables = set()

    class ScopeAnalyzer(ast.NodeVisitor):
        def __init__(self):
            self.defined = set()
            self.used = set()

        def visit_FunctionDef(self, node):
            self.defined.add(node.name)
            local_analyzer = ScopeAnalyzer()

            for arg in getattr(node.args, "posonlyargs", []):
                local_analyzer.defined.add(arg.arg)
            for arg in node.args.args:
                local_analyzer.defined.add(arg.arg)
            for arg in node.args.kwonlyargs:
                local_analyzer.defined.add(arg.arg)
            if node.args.vararg:
                local_analyzer.defined.add(node.args.vararg.arg)
            if node.args.kwarg:
                local_analyzer.defined.add(node.args.kwarg.arg)

            for statement in node.body:
                local_analyzer.visit(statement)

            for name in local_analyzer.used:
                if (
                    name not in local_analyzer.defined
                    and name not in self.defined
                    and name not in builtin_names
                ):
                    undefined_variables.add(name)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store):
                self.defined.add(node.id)
            elif isinstance(node.ctx, ast.Load):
                self.used.add(node.id)

    analyzer = ScopeAnalyzer()

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            analyzer.visit(node)
        else:
            analyzer.visit(node)

    for name in analyzer.used:
        if name not in analyzer.defined and name not in builtin_names:
            undefined_variables.add(name)

    return list(undefined_variables)


def find_dangerous_eval(code):
    """Detect dangerous calls to eval()."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    dangerous_calls = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "eval":
                dangerous_calls.append({
                    "line": node.lineno,
                })

    return dangerous_calls


def find_dangerous_exec(code):
    """Detect dangerous calls to exec()."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    dangerous_calls = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "exec":
                dangerous_calls.append({
                    "line": node.lineno,
                })

    return dangerous_calls


def find_division_by_zero(code):
    """Detect static division or modulo by literal zero."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    division_errors = []

    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
                if isinstance(node.right, ast.Constant) and node.right.value == 0:
                    division_errors.append({
                        "line": node.lineno,
                    })

    return division_errors


def find_unreachable_code(code):
    """Detect statements following unconditional return, raise, break, or continue."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    unreachable_lines = []

    for node in ast.walk(tree):
        statements = []

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            statements = node.body
        elif isinstance(node, (ast.For, ast.While)):
            statements = node.body
        elif isinstance(node, ast.If):
            statements = node.body

        for index, statement in enumerate(statements):
            if isinstance(
                statement,
                (ast.Return, ast.Raise, ast.Break, ast.Continue),
            ):
                for unreachable in statements[index + 1 :]:
                    unreachable_lines.append({
                        "line": unreachable.lineno,
                    })
                break

    return unreachable_lines


def find_none_comparison(code):
    """Detect comparisons to None using == or != instead of is or is not."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    none_comparisons = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            has_none = False
            for operator, comparator in zip(node.ops, node.comparators):
                if isinstance(operator, (ast.Eq, ast.NotEq)):
                    if (
                        isinstance(comparator, ast.Constant)
                        and comparator.value is None
                    ) or (
                        isinstance(node.left, ast.Constant)
                        and node.left.value is None
                    ):
                        has_none = True
                        break
            if has_none:
                none_comparisons.append({
                    "line": node.lineno,
                })

    return none_comparisons


def find_debug_prints(code):
    """Detect leftover print() debugging statements."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    debug_prints = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                debug_prints.append({
                    "line": node.lineno,
                })

    return debug_prints


def find_suspicious_conditions(code):
    """Detect constant conditions or self-comparisons."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    suspicious = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While)):
            test = node.test
            # Constant condition
            if isinstance(test, ast.Constant):
                suspicious.append({
                    "line": getattr(test, "lineno", node.lineno),
                    "condition": str(test.value),
                    "message": f"Conditional statement test is a static constant literal ({test.value}).",
                })
            # Self comparison: x == x, x != x
            elif isinstance(test, ast.Compare):
                if len(test.comparators) == 1 and isinstance(test.left, ast.Name) and isinstance(test.comparators[0], ast.Name):
                    if test.left.id == test.comparators[0].id:
                        suspicious.append({
                            "line": test.lineno,
                            "condition": f"{test.left.id} == {test.comparators[0].id}",
                            "message": f"Variable '{test.left.id}' is compared against itself.",
                        })

    return suspicious


def find_shadowed_builtins(code):
    """Detect variables that shadow Python built-in identifiers."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    shadowed = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id in PYTHON_BUILTINS:
                shadowed.append({
                    "variable": node.id,
                    "line": node.lineno,
                })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in node.args.args + getattr(node.args, "kwonlyargs", []):
                if arg.arg in PYTHON_BUILTINS:
                    shadowed.append({
                        "variable": arg.arg,
                        "line": arg.lineno,
                    })

    return shadowed
def find_out_of_range_list_indexes(code):
    """
    Detect out-of-range indexes into simple list literals.
    Works even when another part of the code has a syntax error.
    """
    findings = []
    lists = {}

    # Detect simple list assignments, such as nums = [10, 20, 30, 40]
    list_pattern = re.compile(
        r"^\s*([A-Za-z_]\w*)\s*=\s*\[([^\[\]]*)\]",
        re.MULTILINE,
    )

    for match in list_pattern.finditer(code):
        name = match.group(1)
        contents = match.group(2).strip()

        try:
            values = ast.literal_eval("[" + contents + "]")
            lists[name] = len(values)
        except (ValueError, SyntaxError):
            continue

    # Detect simple integer indexes, such as nums[5]
    index_pattern = re.compile(
        r"\b([A-Za-z_]\w*)\s*\[\s*(-?\d+)\s*\]"
    )

    for match in index_pattern.finditer(code):
        name = match.group(1)
        index = int(match.group(2))

        if name not in lists:
            continue

        length = lists[name]

        # Check positive and negative index boundaries.
        if index >= length or index < -length:
            line_number = code.count("\n", 0, match.start()) + 1

            if length:
                valid_indexes = f"0 to {length - 1}"
                negative_indexes = f"-{length} to -1"
            else:
                valid_indexes = "none"
                negative_indexes = "none"

            findings.append({
                "variable": name,
                "index": index,
                "length": length,
                "line": line_number,
                "message": (
                    f"List '{name}' has {length} elements, but index "
                    f"{index} is out of range. Valid indexes: "
                    f"{valid_indexes}; negative indexes: "
                    f"{negative_indexes}."
                ),
            })

    return findings