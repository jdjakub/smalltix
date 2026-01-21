#!/usr/bin/env python3
"""
Smalltalk to Smalltix Bash transpiler

Transpiles Smalltalk method syntax into Bash scripts for the Smalltix system,
where objects are directories, references are file paths, and methods are
executable files.

Author: Claude Opus 4.5 (Anthropic)
"""

import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple, Set

# ----------------------------------------------------------------------
# Tokens
# ----------------------------------------------------------------------

@dataclass
class Token:
    type: str
    value: str
    pos: int = 0  # position in source

def tokenize(source: str) -> List[Token]:
    tokens = []
    i = 0
    
    while i < len(source):
        # Skip whitespace
        if source[i].isspace():
            i += 1
            continue
        
        # Skip comments (Smalltalk uses "double quotes")
        if source[i] == '"':
            i += 1
            while i < len(source) and source[i] != '"':
                i += 1
            i += 1  # skip closing "
            continue
        
        # Return arrow
        if source[i] == '^':
            tokens.append(Token('CARET', '^', i))
            i += 1
            continue
        
        # Assignment
        if source[i:i+2] == ':=':
            tokens.append(Token('ASSIGN', ':=', i))
            i += 2
            continue
        
        # Dot (statement separator)
        if source[i] == '.':
            tokens.append(Token('DOT', '.', i))
            i += 1
            continue
        
        # Semicolon (cascade)
        if source[i] == ';':
            tokens.append(Token('SEMI', ';', i))
            i += 1
            continue
        
        # Parentheses
        if source[i] == '(':
            tokens.append(Token('LPAREN', '(', i))
            i += 1
            continue
        if source[i] == ')':
            tokens.append(Token('RPAREN', ')'))
            i += 1
            continue
        
        # Block brackets
        if source[i] == '[':
            tokens.append(Token('LBRACKET', '[', i))
            i += 1
            continue
        if source[i] == ']':
            tokens.append(Token('RBRACKET', ']', i))
            i += 1
            continue
        
        # Vertical bar (for temporaries)
        if source[i] == '|':
            tokens.append(Token('BAR', '|', i))
            i += 1
            continue
        
        # Numbers (integer or float)
        if source[i].isdigit() or (source[i] == '-' and i + 1 < len(source) and source[i+1].isdigit()):
            start = i
            j = i
            if source[j] == '-':
                j += 1
            while j < len(source) and source[j].isdigit():
                j += 1
            # Only treat as float if dot is followed by digit (not statement separator)
            if j < len(source) and source[j] == '.' and j + 1 < len(source) and source[j+1].isdigit():
                j += 1
                while j < len(source) and source[j].isdigit():
                    j += 1
                tokens.append(Token('FLOAT', source[i:j], start))
            else:
                tokens.append(Token('INT', source[i:j], start))
            i = j
            continue
        
        # String literals
        if source[i] == "'":
            start = i
            j = i + 1
            while j < len(source):
                if source[j] == "'":
                    if j + 1 < len(source) and source[j+1] == "'":
                        j += 2  # escaped quote
                    else:
                        break
                else:
                    j += 1
            tokens.append(Token('STRING', source[i+1:j], start))
            i = j + 1
            continue
        
        # Symbol literals (#symbol or #'symbol with spaces')
        if source[i] == '#':
            start = i
            if i + 1 < len(source) and source[i+1] == "'":
                # #'symbol with spaces'
                j = i + 2
                while j < len(source) and source[j] != "'":
                    j += 1
                tokens.append(Token('SYMBOL', source[i+2:j], start))
                i = j + 1
            else:
                # #symbol
                j = i + 1
                while j < len(source) and (source[j].isalnum() or source[j] in '_:'):
                    j += 1
                tokens.append(Token('SYMBOL', source[i+1:j], start))
                i = j
            continue
        
        # Identifiers and keywords
        if source[i].isalpha() or source[i] == '_':
            start = i
            j = i
            while j < len(source) and (source[j].isalnum() or source[j] == '_'):
                j += 1
            name = source[i:j]
            # Check if it's a keyword (ends with :)
            if j < len(source) and source[j] == ':':
                tokens.append(Token('KEYWORD', name + ':', start))
                i = j + 1
            else:
                tokens.append(Token('NAME', name, start))
                i = j
            continue
        
        # Block parameter (colon followed by name)
        if source[i] == ':' and i + 1 < len(source) and source[i+1].isalpha():
            start = i
            j = i + 1
            while j < len(source) and (source[j].isalnum() or source[j] == '_'):
                j += 1
            tokens.append(Token('BLOCKPARAM', source[i+1:j], start))
            i = j
            continue
        
        # Binary selectors (operators)
        binary_chars = '+-*/\\<>=@%|&?,~'
        if source[i] in binary_chars:
            start = i
            j = i
            while j < len(source) and source[j] in binary_chars:
                j += 1
            tokens.append(Token('BINARY', source[i:j], start))
            i = j
            continue
        
        raise SyntaxError(f"Unexpected character: {source[i]!r} at position {i}")
    
    tokens.append(Token('EOF', '', len(source)))
    return tokens

# ----------------------------------------------------------------------
# AST Nodes
# ----------------------------------------------------------------------

@dataclass
class ASTNode:
    pass

@dataclass
class LiteralNode(ASTNode):
    type: str  # 'int', 'float', 'string', 'symbol'
    value: str

@dataclass
class VariableNode(ASTNode):
    name: str

@dataclass
class AssignNode(ASTNode):
    name: str
    value: ASTNode

@dataclass
class SendNode(ASTNode):
    receiver: ASTNode
    selector: str
    args: List[ASTNode]

@dataclass
class CascadeNode(ASTNode):
    receiver: ASTNode
    messages: List[Tuple[str, List[ASTNode]]]  # list of (selector, args)

@dataclass
class ReturnNode(ASTNode):
    value: ASTNode

@dataclass
class BlockNode(ASTNode):
    params: List[str]
    temps: List[str]
    body: List[ASTNode]
    body_start: int = 0  # position of first body token in source
    body_end: int = 0    # position of ']' in source

@dataclass
class MethodNode(ASTNode):
    selector: str
    params: List[str]
    temps: List[str]
    body: List[ASTNode]

# ----------------------------------------------------------------------
# Parser
# ----------------------------------------------------------------------

class Parser:
    def __init__(self, tokens: List[Token], source: str = ''):
        self.tokens = tokens
        self.pos = 0
        self.source = source
    
    def current(self) -> Token:
        return self.tokens[self.pos]
    
    def peek(self, offset: int = 0) -> Token:
        pos = self.pos + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return Token('EOF', '', 0)
    
    def advance(self) -> Token:
        tok = self.current()
        self.pos += 1
        return tok
    
    def expect(self, type: str) -> Token:
        tok = self.current()
        if tok.type != type:
            raise SyntaxError(f"Expected {type}, got {tok.type} ({tok.value!r})")
        return self.advance()
    
    def parse_method(self) -> MethodNode:
        """Parse a complete method: pattern, temps, statements
        
        The message pattern (selector and parameters) is required, even though
        the selector may duplicate the filename. This is necessary because
        parameter names are defined in the message pattern.
        """
        selector, params = self.parse_message_pattern()
        temps = self.parse_temporaries()
        body = self.parse_statements()
        return MethodNode(selector, params, temps, body)
    
    def parse_message_pattern(self) -> Tuple[str, List[str]]:
        """Parse method signature: unary, binary, or keyword"""
        tok = self.current()
        
        if tok.type == 'NAME':
            # Unary
            self.advance()
            return (tok.value, [])
        
        elif tok.type == 'BINARY':
            # Binary
            sel = self.advance().value
            param = self.expect('NAME').value
            return (sel, [param])
        
        elif tok.type == 'KEYWORD':
            # Keyword
            selector = ''
            params = []
            while self.current().type == 'KEYWORD':
                selector += self.advance().value
                params.append(self.expect('NAME').value)
            return (selector, params)
        
        else:
            raise SyntaxError(f"Expected message pattern, got {tok.type}")
    
    def parse_temporaries(self) -> List[str]:
        """Parse | temp1 temp2 | declarations"""
        temps = []
        if self.current().type == 'BAR':
            self.advance()
            while self.current().type == 'NAME':
                temps.append(self.advance().value)
            self.expect('BAR')
        return temps
    
    def parse_statements(self) -> List[ASTNode]:
        """Parse a sequence of statements separated by dots"""
        stmts = []
        while self.current().type not in ('EOF', 'RBRACKET'):
            stmt = self.parse_statement()
            if stmt:
                stmts.append(stmt)
            if self.current().type == 'DOT':
                self.advance()
            else:
                break
        return stmts
    
    def parse_statement(self) -> Optional[ASTNode]:
        """Parse a single statement (return or expression)"""
        if self.current().type == 'CARET':
            self.advance()
            return ReturnNode(self.parse_expression())
        else:
            return self.parse_expression()
    
    def parse_expression(self) -> ASTNode:
        """Parse expression, possibly with assignment"""
        # Check for assignment: name := expr
        if self.current().type == 'NAME' and self.peek(1).type == 'ASSIGN':
            name = self.advance().value
            self.advance()  # skip :=
            value = self.parse_expression()
            return AssignNode(name, value)
        
        return self.parse_cascade()
    
    def parse_cascade(self) -> ASTNode:
        """Parse cascaded messages: recv msg1; msg2; msg3"""
        expr = self.parse_keyword_send()
        
        if self.current().type == 'SEMI':
            # We have a cascade - need to extract receiver and first message
            if not isinstance(expr, SendNode):
                raise SyntaxError("Cascade requires a message send")
            
            messages = [(expr.selector, expr.args)]
            receiver = expr.receiver
            
            while self.current().type == 'SEMI':
                self.advance()
                sel, args = self.parse_cascade_message()
                messages.append((sel, args))
            
            return CascadeNode(receiver, messages)
        
        return expr
    
    def parse_cascade_message(self) -> Tuple[str, List[ASTNode]]:
        """Parse a single message in a cascade (no receiver)"""
        tok = self.current()
        
        if tok.type == 'NAME':
            # Unary
            self.advance()
            return (tok.value, [])
        
        elif tok.type == 'BINARY':
            # Binary
            sel = self.advance().value
            arg = self.parse_unary_send()
            return (sel, [arg])
        
        elif tok.type == 'KEYWORD':
            # Keyword
            selector = ''
            args = []
            while self.current().type == 'KEYWORD':
                selector += self.advance().value
                args.append(self.parse_binary_send())
            return (selector, args)
        
        else:
            raise SyntaxError(f"Expected message in cascade, got {tok.type}")
    
    def parse_keyword_send(self) -> ASTNode:
        """Parse keyword message: recv key1: arg1 key2: arg2"""
        receiver = self.parse_binary_send()
        
        if self.current().type == 'KEYWORD':
            selector = ''
            args = []
            while self.current().type == 'KEYWORD':
                selector += self.advance().value
                args.append(self.parse_binary_send())
            return SendNode(receiver, selector, args)
        
        return receiver
    
    def parse_binary_send(self) -> ASTNode:
        """Parse binary message: recv + arg"""
        receiver = self.parse_unary_send()
        
        while self.current().type == 'BINARY':
            selector = self.advance().value
            arg = self.parse_unary_send()
            receiver = SendNode(receiver, selector, [arg])
        
        return receiver
    
    def parse_unary_send(self) -> ASTNode:
        """Parse unary message: recv msg"""
        receiver = self.parse_primary()
        
        while self.current().type == 'NAME' and self.peek(1).type != 'ASSIGN':
            # Make sure it's not a keyword by checking next isn't ':'
            selector = self.advance().value
            receiver = SendNode(receiver, selector, [])
        
        return receiver
    
    def parse_primary(self) -> ASTNode:
        """Parse primary: literal, variable, block, or (expr)"""
        tok = self.current()
        
        if tok.type == 'INT':
            self.advance()
            return LiteralNode('int', tok.value)
        
        elif tok.type == 'FLOAT':
            self.advance()
            return LiteralNode('float', tok.value)
        
        elif tok.type == 'STRING':
            self.advance()
            return LiteralNode('string', tok.value)
        
        elif tok.type == 'SYMBOL':
            self.advance()
            return LiteralNode('symbol', tok.value)
        
        elif tok.type == 'NAME':
            self.advance()
            return VariableNode(tok.value)
        
        elif tok.type == 'LPAREN':
            self.advance()
            expr = self.parse_expression()
            self.expect('RPAREN')
            return expr
        
        elif tok.type == 'LBRACKET':
            return self.parse_block()
        
        else:
            raise SyntaxError(f"Unexpected token in primary: {tok.type} ({tok.value!r})")
    
    def parse_block(self) -> BlockNode:
        """Parse a block: [ :param1 :param2 | | temps | statements ]"""
        start_tok = self.current()
        source_start = start_tok.pos
        self.expect('LBRACKET')
        
        # Parse block parameters :param1 :param2 ... |
        params = []
        while self.current().type == 'BLOCKPARAM':
            params.append(self.advance().value)
        
        # If we had params, expect a | to end them
        if params:
            self.expect('BAR')
        
        # Parse temporaries (optional)
        temps = []
        if self.current().type == 'BAR':
            self.advance()
            while self.current().type == 'NAME':
                temps.append(self.advance().value)
            self.expect('BAR')
        
        # Record where body starts (after params and temps)
        body_start = self.current().pos
        
        # Parse statements until ]
        body = []
        while self.current().type != 'RBRACKET':
            stmt = self.parse_statement()
            if stmt:
                body.append(stmt)
            if self.current().type == 'DOT':
                self.advance()
        
        end_tok = self.current()
        body_end = end_tok.pos  # position of ], not including it
        source_end = end_tok.pos + 1  # include the ]
        self.expect('RBRACKET')
        
        return BlockNode(params, temps, body, body_start, body_end)

# ----------------------------------------------------------------------
# Code Generator
# ----------------------------------------------------------------------

class CodeGenerator:
    def __init__(self, source: str = ''):
        self.source = source
        self.tmp_counter = 0
        self.lines = []
        self.temps = set()  # track declared temporaries
        self.params = set()  # track method parameters
        self.inst_vars = set()  # will be populated by context
        self.block_counter = 0
        self.extracted_blocks = []  # list of (name, source, bash) tuples
        self.method_selector = ''  # current method's selector (mangled)
        self.block_path_stack = []  # for nested blocks: stack of block name suffixes
    
    def new_tmp(self) -> str:
        self.tmp_counter += 1
        return f"tmp{self.tmp_counter}"
    
    def new_block_name(self) -> str:
        self.block_counter += 1
        if self.block_path_stack:
            return f"~block{self.block_counter}"
        else:
            return f"~block{self.block_counter}"
    
    def current_block_path(self) -> str:
        """Return the full block path suffix for nested blocks"""
        return ''.join(self.block_path_stack)
    
    def needs_dollar_prefix(self, var_name: str) -> bool:
        """Check if a variable reference needs $ prefix in Bash.
        
        Returns False for literals (int/, float/), special values (true, false, nil),
        and global class references (capitalized names).
        """
        if var_name.startswith(('int/', 'float/')):
            return False
        if var_name in ('true', 'false', 'nil'):
            return False
        if var_name and var_name[0].isupper():
            return False
        return True
    
    def var_ref(self, var_name: str) -> str:
        """Return the Bash reference for a variable (with or without $)."""
        if self.needs_dollar_prefix(var_name):
            return f"${var_name}"
        return var_name
    
    def generate_method(self, node: MethodNode, original_source: str) -> Tuple[str, List[Tuple[str, str]]]:
        """Generate complete Bash method script.
        
        Returns: (main_script, [(block_name, block_script), ...])
        """
        self.lines = []
        self.temps = set(node.temps)
        self.params = set(node.params)
        self.method_selector = node.selector.replace(':', '-')
        self.block_counter = 0
        self.extracted_blocks = []
        self.block_path_stack = []
        
        # Include original source verbatim as comments
        for line in original_source.rstrip().split('\n'):
            self.lines.append(f"# {line}")
        self.lines.append("#")
        
        # self=$1
        self.lines.append("self=$1")
        
        # Parameters: param1=$2, param2=$3, etc.
        for i, param in enumerate(node.params, start=2):
            self.lines.append(f"{param}=${i}")
        
        # Generate body - handle final return specially for optimization
        for i, stmt in enumerate(node.body):
            is_last = (i == len(node.body) - 1)
            self.generate_statement(stmt, is_final=is_last)
        
        main_script = '\n'.join(self.lines)
        return (main_script, self.extracted_blocks)
    
    def reconstruct_source(self, node: MethodNode) -> List[str]:
        """Reconstruct original Smalltalk source for comment header"""
        lines = []
        
        # Temporaries
        if node.temps:
            lines.append("| " + " ".join(node.temps) + " |")
        
        # Body statements
        for stmt in node.body:
            lines.append(self.node_to_source(stmt))
        
        return lines
    
    def node_to_source(self, node: ASTNode) -> str:
        """Convert AST node back to Smalltalk source"""
        if isinstance(node, LiteralNode):
            if node.type == 'int':
                return node.value
            elif node.type == 'float':
                return node.value
            elif node.type == 'string':
                return f"'{node.value}'"
            elif node.type == 'symbol':
                return f"#{node.value}"
        
        elif isinstance(node, VariableNode):
            return node.name
        
        elif isinstance(node, AssignNode):
            return f"{node.name} := {self.node_to_source(node.value)}"
        
        elif isinstance(node, SendNode):
            recv = self.node_to_source(node.receiver)
            # Add parens if receiver is complex
            if isinstance(node.receiver, (SendNode, AssignNode)):
                if self.is_keyword_or_binary(node.receiver):
                    recv = f"({recv})"
            
            if not node.args:
                # Unary
                return f"{recv} {node.selector}"
            elif len(node.args) == 1 and not node.selector.endswith(':'):
                # Binary
                return f"{recv} {node.selector} {self.node_to_source(node.args[0])}"
            else:
                # Keyword
                parts = node.selector.split(':')[:-1]  # remove trailing empty
                result = recv
                for part, arg in zip(parts, node.args):
                    result += f" {part}: {self.node_to_source(arg)}"
                return result
        
        elif isinstance(node, CascadeNode):
            recv = self.node_to_source(node.receiver)
            parts = [recv]
            for i, (sel, args) in enumerate(node.messages):
                if i > 0:
                    parts.append(";")
                if not args:
                    parts.append(sel)
                elif len(args) == 1 and not sel.endswith(':'):
                    parts.append(f"{sel} {self.node_to_source(args[0])}")
                else:
                    kw_parts = sel.split(':')[:-1]
                    for kp, arg in zip(kw_parts, args):
                        parts.append(f"{kp}: {self.node_to_source(arg)}")
            return " ".join(parts)
        
        elif isinstance(node, ReturnNode):
            return f"^ {self.node_to_source(node.value)}"
        
        elif isinstance(node, BlockNode):
            parts = ["["]
            if node.params:
                for p in node.params:
                    parts.append(f":{p}")
                parts.append("|")
            if node.temps:
                parts.append("|")
                parts.extend(node.temps)
                parts.append("|")
            for stmt in node.body:
                parts.append(self.node_to_source(stmt))
                parts.append(".")
            # Remove trailing dot
            if parts[-1] == ".":
                parts.pop()
            parts.append("]")
            return " ".join(parts)
        
        return "???"
    
    def is_keyword_or_binary(self, node: ASTNode) -> bool:
        if isinstance(node, SendNode):
            return len(node.args) > 0
        return False
    
    def generate_statement(self, node: ASTNode, is_final: bool = False) -> str:
        """Generate code for a statement, return the variable holding result"""
        if isinstance(node, ReturnNode):
            if is_final:
                # Optimization: final return doesn't need tmp+echo
                self.generate_expr_final(node.value)
                return None
            else:
                result = self.generate_expr(node.value)
                self.lines.append(f"echo ${result}")
                return result
        else:
            if is_final:
                # Final expression in a block - output directly
                self.generate_expr_final(node)
                return None
            else:
                return self.generate_expr(node)
    
    def generate_expr_final(self, node: ASTNode) -> None:
        """Generate expression as final statement - output directly without capturing"""
        if isinstance(node, LiteralNode):
            if node.type == 'int':
                self.lines.append(f"echo int/{node.value}")
            elif node.type == 'float':
                self.lines.append(f"echo float/{node.value}")
            else:
                raise NotImplementedError(f"{node.type} literals not yet supported")
        
        elif isinstance(node, VariableNode):
            name = node.name
            if name == 'self':
                self.lines.append("echo $self")
            elif name in ('true', 'false', 'nil'):
                self.lines.append(f"echo {name}")
            elif name in self.temps or name in self.params:
                self.lines.append(f"echo ${name}")
            else:
                # Instance variable
                self.lines.append(f"cat $self/{name}")
        
        elif isinstance(node, SendNode):
            self.generate_send_final(node)
        
        elif isinstance(node, CascadeNode):
            self.generate_cascade_final(node)
        
        elif isinstance(node, AssignNode):
            # Assignment as final expression - do assignment, then output value
            result = self.generate_expr(node)
            self.lines.append(f"echo {self.var_ref(result)}")
        
        elif isinstance(node, BlockNode):
            # Block as final expression - generate block, then output it
            result = self.generate_block(node)
            self.lines.append(f"echo {self.var_ref(result)}")
        
        else:
            raise NotImplementedError(f"Unknown node type: {type(node)}")
    
    def generate_send_final(self, node: SendNode) -> None:
        """Generate a message send as final statement - no capture"""
        recv_var = self.generate_expr(node.receiver)
        
        # Generate arguments
        arg_vars = []
        for arg in node.args:
            arg_vars.append(self.generate_expr(arg))
        
        # Build selector (replace : with -)
        selector = node.selector.replace(':', '-')
        
        # Build send command - no capture
        args_str = ' '.join(self.var_ref(v) for v in arg_vars)
        recv_ref = self.var_ref(recv_var)
        
        if args_str:
            self.lines.append(f"./send {recv_ref} {selector} {args_str}")
        else:
            self.lines.append(f"./send {recv_ref} {selector}")
    
    def generate_cascade_final(self, node: CascadeNode) -> None:
        """Generate cascaded messages as final statement"""
        recv_var = self.generate_expr(node.receiver)
        
        for i, (selector, args) in enumerate(node.messages):
            is_last_msg = (i == len(node.messages) - 1)
            
            arg_vars = []
            for arg in args:
                arg_vars.append(self.generate_expr(arg))
            
            selector = selector.replace(':', '-')
            recv_ref = self.var_ref(recv_var)
            args_str = ' '.join(self.var_ref(v) for v in arg_vars)
            
            if is_last_msg:
                # Final message - no capture
                if args_str:
                    self.lines.append(f"./send {recv_ref} {selector} {args_str}")
                else:
                    self.lines.append(f"./send {recv_ref} {selector}")
            else:
                # Non-final message in cascade - capture (though result is discarded)
                tmp = self.new_tmp()
                if args_str:
                    self.lines.append(f"{tmp}=$(./send {recv_ref} {selector} {args_str})")
                else:
                    self.lines.append(f"{tmp}=$(./send {recv_ref} {selector})")
    
    def generate_expr(self, node: ASTNode) -> str:
        """Generate code for expression, return variable name holding result"""
        
        if isinstance(node, LiteralNode):
            if node.type == 'int':
                return f"int/{node.value}"
            elif node.type == 'float':
                return f"float/{node.value}"
            elif node.type == 'string':
                raise NotImplementedError("String literals not yet supported")
            elif node.type == 'symbol':
                raise NotImplementedError("Symbol literals not yet supported")
        
        elif isinstance(node, VariableNode):
            name = node.name
            if name == 'self':
                return 'self'
            elif name == 'true':
                return 'true'
            elif name == 'false':
                return 'false'
            elif name == 'nil':
                return 'nil'
            elif name in self.temps or name in self.params:
                return name
            elif name[0].isupper():
                # Capitalized names are global class references
                return name
            else:
                # Instance variable - read from file
                tmp = self.new_tmp()
                self.lines.append(f"{tmp}=$(cat $self/{name})")
                return tmp
        
        elif isinstance(node, AssignNode):
            name = node.name
            if name in self.temps or name in self.params:
                # Local variable assignment - generate directly into this name
                self.generate_expr_into(node.value, name)
                return name
            else:
                # Instance variable assignment
                value_var = self.generate_expr(node.value)
                self.lines.append(f"echo {self.var_ref(value_var)} > $self/{name}")
                return value_var
        
        elif isinstance(node, SendNode):
            return self.generate_send(node)
        
        elif isinstance(node, CascadeNode):
            return self.generate_cascade(node)
        
        elif isinstance(node, BlockNode):
            return self.generate_block(node)
        
        else:
            raise NotImplementedError(f"Unknown node type: {type(node)}")
    
    def generate_expr_into(self, node: ASTNode, target_var: str) -> None:
        """Generate expression, storing result directly into target_var"""
        
        if isinstance(node, LiteralNode):
            if node.type == 'int':
                self.lines.append(f"{target_var}=int/{node.value}")
            elif node.type == 'float':
                self.lines.append(f"{target_var}=float/{node.value}")
            else:
                raise NotImplementedError(f"{node.type} literals not yet supported")
        
        elif isinstance(node, VariableNode):
            name = node.name
            if name == 'self':
                self.lines.append(f"{target_var}=$self")
            elif name in ('true', 'false', 'nil'):
                self.lines.append(f"{target_var}={name}")
            elif name in self.temps or name in self.params:
                self.lines.append(f"{target_var}=${name}")
            elif name[0].isupper():
                # Capitalized names are global class references
                self.lines.append(f"{target_var}={name}")
            else:
                # Instance variable
                self.lines.append(f"{target_var}=$(cat $self/{name})")
        
        elif isinstance(node, SendNode):
            recv_var = self.generate_expr(node.receiver)
            
            arg_vars = []
            for arg in node.args:
                arg_vars.append(self.generate_expr(arg))
            
            selector = node.selector.replace(':', '-')
            args_str = ' '.join(self.var_ref(v) for v in arg_vars)
            recv_ref = self.var_ref(recv_var)
            
            if args_str:
                self.lines.append(f"{target_var}=$(./send {recv_ref} {selector} {args_str})")
            else:
                self.lines.append(f"{target_var}=$(./send {recv_ref} {selector})")
        
        elif isinstance(node, CascadeNode):
            # For cascade, generate all messages, last one goes into target
            recv_var = self.generate_expr(node.receiver)
            
            for i, (selector, args) in enumerate(node.messages):
                is_last_msg = (i == len(node.messages) - 1)
                
                arg_vars = []
                for arg in args:
                    arg_vars.append(self.generate_expr(arg))
                
                selector = selector.replace(':', '-')
                recv_ref = self.var_ref(recv_var)
                args_str = ' '.join(self.var_ref(v) for v in arg_vars)
                
                if is_last_msg:
                    if args_str:
                        self.lines.append(f"{target_var}=$(./send {recv_ref} {selector} {args_str})")
                    else:
                        self.lines.append(f"{target_var}=$(./send {recv_ref} {selector})")
                else:
                    tmp = self.new_tmp()
                    if args_str:
                        self.lines.append(f"{tmp}=$(./send {recv_ref} {selector} {args_str})")
                    else:
                        self.lines.append(f"{tmp}=$(./send {recv_ref} {selector})")
        
        elif isinstance(node, AssignNode):
            # Nested assignment - do inner assignment, then copy to target
            result = self.generate_expr(node)
            self.lines.append(f"{target_var}=${result}")
        
        elif isinstance(node, BlockNode):
            # Block - generate it and assign to target
            result = self.generate_block(node)
            self.lines.append(f"{target_var}=${result}")
        
        else:
            raise NotImplementedError(f"Unknown node type: {type(node)}")
    
    def generate_send(self, node: SendNode) -> str:
        """Generate a message send"""
        recv_var = self.generate_expr(node.receiver)
        
        # Generate arguments
        arg_vars = []
        for arg in node.args:
            arg_vars.append(self.generate_expr(arg))
        
        # Build selector (replace : with -)
        selector = node.selector.replace(':', '-')
        
        # Build send command
        tmp = self.new_tmp()
        args_str = ' '.join(self.var_ref(v) for v in arg_vars)
        recv_ref = self.var_ref(recv_var)
        
        if args_str:
            self.lines.append(f"{tmp}=$(./send {recv_ref} {selector} {args_str})")
        else:
            self.lines.append(f"{tmp}=$(./send {recv_ref} {selector})")
        
        return tmp
    
    def generate_cascade(self, node: CascadeNode) -> str:
        """Generate cascaded messages"""
        recv_var = self.generate_expr(node.receiver)
        
        last_result = None
        for selector, args in node.messages:
            arg_vars = []
            for arg in args:
                arg_vars.append(self.generate_expr(arg))
            
            selector = selector.replace(':', '-')
            tmp = self.new_tmp()
            args_str = ' '.join(self.var_ref(v) for v in arg_vars)
            recv_ref = self.var_ref(recv_var)
            
            if args_str:
                self.lines.append(f"{tmp}=$(./send {recv_ref} {selector} {args_str})")
            else:
                self.lines.append(f"{tmp}=$(./send {recv_ref} {selector})")
            
            last_result = tmp
        
        return last_result
    
    def generate_block(self, node: BlockNode) -> str:
        """Generate a block closure.
        
        This extracts the block body into a separate method and generates
        code to create a BlockClosure object capturing the current bindings.
        """
        # Generate unique block name
        self.block_counter += 1
        block_suffix = self.current_block_path() + f"~block{self.block_counter}"
        block_method_name = f"{self.method_selector}{block_suffix}"
        
        # Determine captured variables: self + outer temps + outer params (excluding self)
        # (everything currently in scope that isn't the block's own params/temps)
        captured = ['self']
        for t in self.temps:
            if t != 'self' and t not in captured:
                captured.append(t)
        for p in self.params:
            if p != 'self' and p not in captured:
                captured.append(p)
        
        # Build the block method source comment
        # _method: captured1 and: captured2 ... and: blockParam1 ...
        block_source_lines = []
        sig_parts = []
        all_block_params = captured + node.params
        for i, name in enumerate(all_block_params):
            if i == 0:
                sig_parts.append(f"_method: {name}")
            else:
                sig_parts.append(f"and: {name}")
        sig_line = ' '.join(sig_parts) if sig_parts else "_method"
        block_source_lines.append(sig_line)
        
        # Extract verbatim block body source from original
        block_body_source = self.source[node.body_start:node.body_end].strip()
        for line in block_body_source.split('\n'):
            block_source_lines.append(line)
        
        # Generate the block method's bash code
        block_lines = []
        for line in block_source_lines:
            block_lines.append(f"# {line}")
        block_lines.append("#")
        
        # Parameters: captured vars then block params
        param_index = 1
        for name in captured:
            block_lines.append(f"{name}=${param_index}")
            param_index += 1
        for name in node.params:
            block_lines.append(f"{name}=${param_index}")
            param_index += 1
        
        # Generate block body with a new generator context
        # Save current state
        old_lines = self.lines
        old_temps = self.temps
        old_params = self.params
        old_tmp_counter = self.tmp_counter
        
        # Set up for block body generation
        self.lines = []
        self.temps = set(node.temps)
        self.params = set(captured) | set(node.params)
        self.tmp_counter = 0
        
        # Push onto block path stack for nested blocks
        self.block_path_stack.append(f"~block{self.block_counter}")
        
        # Generate body statements - last one is final (implicit return)
        for i, stmt in enumerate(node.body):
            is_last = (i == len(node.body) - 1)
            self.generate_statement(stmt, is_final=is_last)
        
        # Pop block path stack
        self.block_path_stack.pop()
        
        # Collect generated body lines
        body_lines = self.lines
        
        # Restore state
        self.lines = old_lines
        self.temps = old_temps
        self.params = old_params
        self.tmp_counter = old_tmp_counter
        
        # Combine block method
        block_script = '\n'.join(block_lines + body_lines)
        
        # Store extracted block
        self.extracted_blocks.append((block_method_name, block_script))
        
        # Generate code in main method to create the BlockClosure
        # 1. Create bindings array with captured values
        num_captured = len(captured)
        if num_captured == 1:
            bindings_var = self.new_tmp()
            self.lines.append(f"{bindings_var}=$(./send Array with- $self)")
        elif num_captured == 2:
            bindings_var = self.new_tmp()
            cap_refs = ' '.join(f"${name}" for name in captured)
            self.lines.append(f"{bindings_var}=$(./send Array with-with- {cap_refs})")
        elif num_captured == 3:
            bindings_var = self.new_tmp()
            cap_refs = ' '.join(f"${name}" for name in captured)
            self.lines.append(f"{bindings_var}=$(./send Array with-with-with- {cap_refs})")
        elif num_captured == 4:
            bindings_var = self.new_tmp()
            cap_refs = ' '.join(f"${name}" for name in captured)
            self.lines.append(f"{bindings_var}=$(./send Array with-with-with-with- {cap_refs})")
        else:
            # For more captures, we'd need a different approach
            # For now, build incrementally
            bindings_var = self.new_tmp()
            self.lines.append(f"{bindings_var}=$(./send Array new- int/{num_captured})")
            for i, name in enumerate(captured, start=1):
                self.lines.append(f"_=$(./send ${bindings_var} at-put- int/{i} ${name})")
        
        # 2. Create BlockClosure
        # Use directory of current script (blocks are sibling files)
        self.lines.append("blockDir=${0%/*}")
        block_var = self.new_tmp()
        self.lines.append(f"{block_var}=$(./send BlockClosure fromCode-with- $blockDir/{block_method_name} ${bindings_var})")
        
        return block_var

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def transpile(source: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Transpile Smalltalk method source to Bash script.
    
    Returns: (main_script, [(block_name, block_script), ...])
    """
    tokens = tokenize(source)
    parser = Parser(tokens, source)
    ast = parser.parse_method()
    gen = CodeGenerator(source)
    return gen.generate_method(ast, source)

def main():
    if len(sys.argv) < 2:
        print("Usage: smalltix_transpiler.py <source_file> [output_dir]", file=sys.stderr)
        print("       smalltix_transpiler.py -e '<smalltalk source>'", file=sys.stderr)
        sys.exit(1)
    
    if sys.argv[1] == '-e':
        if len(sys.argv) < 3:
            print("Error: -e requires source argument", file=sys.stderr)
            sys.exit(1)
        source = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else None
    else:
        with open(sys.argv[1], 'r') as f:
            source = f.read()
        output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        main_script, blocks = transpile(source)
        
        if output_dir:
            import os
            os.makedirs(output_dir, exist_ok=True)
            
            # Extract method name from source (first line)
            first_line = source.strip().split('\n')[0]
            method_name = first_line.split()[0] if first_line else 'method'
            method_name = method_name.replace(':', '-')
            
            # Write main method
            main_path = os.path.join(output_dir, method_name)
            with open(main_path, 'w') as f:
                f.write(main_script)
                f.write('\n')
            print(f"Written: {main_path}")
            
            # Write block methods
            for block_name, block_script in blocks:
                block_path = os.path.join(output_dir, block_name)
                with open(block_path, 'w') as f:
                    f.write(block_script)
                    f.write('\n')
                print(f"Written: {block_path}")
        else:
            # Print to stdout
            print("=== Main Method ===")
            print(main_script)
            for block_name, block_script in blocks:
                print(f"\n=== Block: {block_name} ===")
                print(block_script)
    
    except (SyntaxError, NotImplementedError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
