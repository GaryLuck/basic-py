import sys
import os
import re

class TinyBasicInterpreter:
    def __init__(self):
        self.program = {}  # Line number -> Code
        self.variables = {chr(i): 0 for i in range(ord('A'), ord('Z') + 1)}
        self.arrays = {}
        self.running = True

    def run_interactive(self):
        print("Tiny BASIC Interpreter Ready")
        while self.running:
            try:
                line = input("> ")
                self.process_input(line)
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\nBreak")
            except Exception as e:
                print(f"Error: {e}")

    def process_input(self, line):
        line = line.strip()
        if not line:
            return

        # Check if line starts with a number (Program line)
        match = re.match(r'^(\d+)\s*(.*)', line)
        if match:
            line_num = int(match.group(1))
            code = match.group(2).strip()
            if code:
                self.program[line_num] = code
            else:
                # If only line number is given, delete the line
                if line_num in self.program:
                    del self.program[line_num]
        else:
            # Direct command
            self.execute_statement(line)

    def execute_statement(self, stmt):
        stmt = stmt.strip()
        if not stmt:
            return

        parts = stmt.split(maxsplit=1)
        command = parts[0].upper()
        arg = parts[1] if len(parts) > 1 else ""

        if command == "PRINT":
            self.cmd_print(arg)
        elif command == "LET":
            self.cmd_let(arg)
        elif command == "GOTO":
            # GOTO is only valid inside a running program for jumping lines, 
            # but usually in direct mode it might not make sense unless we run.
            # But here `execute_statement` is used for both direct and program execution.
            # If direct command GOTO, it's ambiguous where to go in flow, 
            # but usually it effectively starts running from there or jumps if running.
            # For simplicity, we'll handle GOTO logic in the run_program loop specially or raise error if direct.
             raise RuntimeError("GOTO can only be used within a program or is handled by the runner")
        elif command == "IF":
             raise RuntimeError("IF can only be used within a program")
        elif command == "DIM":
            self.cmd_dim(arg)
        elif command == "END":
            # Stops execution
            pass 
        elif command == "RUN":
            self.cmd_run()
        elif command == "LIST":
            self.cmd_list()
        elif command == "NEW":
            self.cmd_new()
        elif command == "LOAD":
            self.cmd_load(arg)
        elif command == "SAVE":
            self.cmd_save(arg)
        elif command == "QUIT":
            self.running = False
        else:
            # Assignment without LET? Or unknown command. 
            # Requirement says "LET Assign a value". 
            # Some BASICs allow `A=10`. Requirement 7 says `LET`.
            print(f"Unknown command: {command}")

    def execute_program(self, start_line=None):
        if not self.program:
            return

        lines = sorted(self.program.keys())
        if start_line is None:
            pc_idx = 0
        else:
            try:
                pc_idx = lines.index(start_line)
            except ValueError:
                print(f"Line {start_line} not found.")
                return

        while 0 <= pc_idx < len(lines):
            line_num = lines[pc_idx]
            stmt = self.program[line_num]
            
            # Helper to check if we need to jump
            # We parse the command manually here because GOTO/IF need control over pc_idx
            parts = stmt.strip().split(maxsplit=1)
            command = parts[0].upper()
            arg = parts[1] if len(parts) > 1 else ""

            try:
                if command == "GOTO":
                    target_line = self.eval_expression(arg)
                    try:
                        pc_idx = lines.index(target_line)
                        continue
                    except ValueError:
                        print(f"Line {target_line} not found in program.")
                        break

                elif command == "IF":
                    # IF expression op expression THEN line
                    # Parsing strictly: IF <cond> THEN <target>
                    # Requirement says "Conditional jump".
                    # Let's look for THEN (standard) or just GOTO implied?
                    # "IF Conditional jump" usually implies "IF condition THEN line"
                    match = re.match(r'(.+?)\s+THEN\s+(.+)', arg, re.IGNORECASE)
                    if match:
                        condition_str = match.group(1)
                        target_str = match.group(2)
                        if self.eval_condition(condition_str):
                            # Target is a line number
                            target_line = self.eval_expression(target_str)
                            try:
                                pc_idx = lines.index(target_line)
                                continue
                            except ValueError:
                                print(f"Line {target_line} not found in program.")
                                break
                    else:
                        print(f"Syntax error in IF on line {line_num}")
                        break
                
                elif command == "END":
                    break
                
                else:
                    self.execute_statement(stmt)
            
            except Exception as e:
                print(f"Error on line {line_num}: {e}")
                break

            pc_idx += 1

    # --- commands ---

    def cmd_new(self):
        self.program.clear()
        self.variables = {chr(i): 0 for i in range(ord('A'), ord('Z') + 1)}
        self.arrays.clear()

    def cmd_list(self):
        for line_num in sorted(self.program.keys()):
            print(f"{line_num} {self.program[line_num]}")

    def cmd_run(self):
        self.execute_program()

    def cmd_save(self, filename):
        if not filename:
            print("Usage: SAVE filename")
            return
        try:
            with open(filename, 'w') as f:
                for line_num in sorted(self.program.keys()):
                    f.write(f"{line_num} {self.program[line_num]}\n")
            print(f"Saved to {filename}")
        except Exception as e:
            print(f"Error saving: {e}")

    def cmd_load(self, filename):
        if not filename:
            print("Usage: LOAD filename")
            return
        try:
            with open(filename, 'r') as f:
                self.program.clear()
                for line in f:
                    self.process_input(line)
            print(f"Loaded {filename}")
        except Exception as e:
            print(f"Error loading: {e}")

    def cmd_print(self, arg):
        # arg can be list of expressions separated by comma
        # But requirement says "Print the value of AN expression".
        # Let's support one expression first, or multiple if possible.
        # "PRINT Print the value of an expression" -> SINGULAR.
        # But commonly we might want multiple. Let's stick to one or string.
        # Actually standard BASIC print can take strings too.
        # Let's try to evaluate as expression first.
        # If it fails, maybe it's a string literal? Requirement only says "arithmetic expressions".
        # But usually PRINT "HELLO" is expected.
        val = self.eval_expression(arg)
        print(val)

    def cmd_let(self, arg):
        # LET A = expression
        if '=' not in arg:
            print("Syntax error: LET var = expression")
            return
        var_part, expr_part = arg.split('=', 1)
        var_name = var_part.strip().upper()
        
        val = self.eval_expression(expr_part)
        
        # Check if array or simple var
        # Variables keys are single letters.
        # Arrays are A-Z too but index access.
        
        # Regex to check for array assignment: A(expr)
        match_arr = re.match(r'^([A-Z])\((.+)\)$', var_name)
        if match_arr:
            # Array assignment
            name = match_arr.group(1)
            idx_expr = match_arr.group(2)
            idx = self.eval_expression(idx_expr)
            if name in self.arrays:
                if 0 <= idx < len(self.arrays[name]):
                    self.arrays[name][idx] = val
                else:
                    raise RuntimeError(f"Array index out of bounds: {name}({idx})")
            else:
                 raise RuntimeError(f"Array not defined: {name}")
        elif re.match(r'^[A-Z]$', var_name):
            # Simple variable
            self.variables[var_name] = val
        else:
             raise RuntimeError(f"Invalid variable name: {var_name}")

    def cmd_dim(self, arg):
        # DIM A(10)
        match = re.match(r'^([A-Z])\((.+)\)$', arg.strip().upper())
        if match:
            name = match.group(1)
            size_expr = match.group(2)
            size = self.eval_expression(size_expr)
            self.arrays[name] = [0] * (size + 1) # usually 0 to size
        else:
             raise RuntimeError("Syntax error: DIM A(size)")

    # --- Evaluator ---

    def eval_condition(self, condition_str):
        # Support >, <, >=, <=, =, <>
        # Split by operators
        ops = ['>=', '<=', '<>', '>', '<', '=']
        for op in ops:
            if op in condition_str:
                left, right = condition_str.split(op, 1)
                lval = self.eval_expression(left)
                rval = self.eval_expression(right)
                if op == '>=': return lval >= rval
                if op == '<=': return lval <= rval
                if op == '<>': return lval != rval
                if op == '>': return lval > rval
                if op == '<': return lval < rval
                if op == '=': return lval == rval
        raise RuntimeError("Invalid condition syntax")

    def eval_expression(self, expr_str):
        # A simple recursive descent parser or just shunting-yard or...
        # Since we have Python, we can transform the expression to be safe and use eval()
        # but "Variables are A-Z".
        # We also need to handle Array access in expression: A(idx).
        # We can substitute variables and array calls.
        
        # Replace arrays A(expr) -> self.get_array_val('A', expr)? 
        # But expr in access needs evaluation too.
        # eval() with a custom locals dictionary is easiest.
        
        # Let's build a safe evaluator using python's eval but restricted specific names.
        # However, "Integer arithmetic" means we must treat / as //.
        
        expr_str = expr_str.strip().upper()
        if not expr_str:
            return 0
            
        # Pre-process: replace / with // for integer division
        # This is a bit naive if encoded in strings but we supposedly only have vars and numbers.
        # Be careful not to replace inside variable names? Variables are single letters.
        expr_str = expr_str.replace('/', '//')

        # To handle arrays efficiently for eval:
        # We can pass a class/dict that handles getitem.
        
        class Context:
            def __init__(self, output, arrays):
                self.output = output
                self.arrays = arrays
            def __getitem__(self, key):
                if key in self.output:
                    return self.output[key]
                # Check directly in arrays if possible? 
                # eval will look up names. 'A' is 0. 'A(1)' attempts to call 'A'.
                # In Python, '0(1)' is error.
                # So if A is a variable (int) we can't treat it as function.
                # The requirements separate Variables A-Z and Arrays DIM A-Z.
                # Usually in BASIC, DIM A(10) shadowing A is allowed or A is array only?
                # "Variables are single letters A-Z... DIM Declare an array...".
                # Often in Tiny BASIC, a letter is either a scalar or an array.
                # Lets assume if DIM A(10) is called, A becomes an array (list).
                
                # Wait, my variables dict initializes all A-Z to 0. 
                # If DIM A(10) happens, I put it in self.arrays['A'].
                # I should probably unify storage.
                return 0

        # Let's unify storage?
        # Requirement: "Variables are single letters A-Z and are initialized to 0."
        # Requirement: "DIM Declare an array..."
        # If I have DIM A(10), does A still work as a variable? 
        # In many BASICs, A and A() are distinct.
        # But in Python eval, 'A' vs 'A(1)', 'A' must be callable to handle parens? No.
        # If 'A' is variable, it's an int. 'A(1)' fails.
        # So I have to parse/replace array syntax before eval OR use a custom dictionary where __getitem__ evaluates arrays?
        # Actually, simpler: Use regex to resolve array calls first? 
        # Recursion might be needed for nested A(B(1)).
        
        # Alternative: The Context dict has 'A' as a number. 
        # The expression string "A + B" -> uses numbers.
        # "A(1) + B" -> Python thinks A is function.
        # So I need to pass functions for array-defined variables in `locals`.
        
        # Let's prepare a locals dictionary each time.
        # For each letter A-Z:
        #   If it is in self.arrays, map it to a lambda or function wrapper?
        #   Else map it to the integer value.
        # BUT if A is an array, can I access A as a scalar? 
        # In C basics, no. In some basics, yes (first element?). 
        # Let's assume if it's an array, you must use ().
        
        local_vars = {}
        for char_code in range(ord('A'), ord('Z')+1):
            name = chr(char_code)
            if name in self.arrays:
                # It's an array. Create a wrapper function.
                # We need to bind the list.
                # Python loop variable closure issue (name), so default arg.
                def array_accessor(idx, n=name):
                    try: 
                       return self.arrays[n][int(idx)]
                    except IndexError:
                       raise RuntimeError(f"Index out of bounds for {n}")
                local_vars[name] = array_accessor
            else:
                local_vars[name] = self.variables[name]

        # Evaluate
        try:
            # We must only allow valid identifiers. 
            # Dangerous eval warnings apply, but this is a local script.
            result = eval(expr_str, {"__builtins__": None}, local_vars)
            return int(result)
        except Exception as e:
            raise RuntimeError(f"Expression error '{expr_str}': {e}")


if __name__ == "__main__":
    interpreter = TinyBasicInterpreter()
    if len(sys.argv) > 1:
        # Load file if argument provided
        interpreter.cmd_load(sys.argv[1])
        interpreter.cmd_run()
    else:
        interpreter.run_interactive()
