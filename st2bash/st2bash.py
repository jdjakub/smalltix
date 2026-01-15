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
from typing import List, Optional, Tuple

# ----------------------------------------------------------------------
# Tokens
# ----------------------------------------------------------------------

@dataclass
class Token:
    type: str
    value: str

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
            tokens.append(Token('CARET', '^'))
            i += 1
            continue
        
        # Assignment
        if source[i:i+2] == ':=':
            tokens.append(Token('ASSIGN', ':='))
            i += 2
            continue
        
        # Dot (statement separator)
        if source[i] == '.':
            tokens.append(Token('DOT', '.'))
            i += 1
            continue
        
        # Semicolon (cascade)
        if source[i] == ';':
            tokens.append(Token('SEMI', ';'))
            i += 1
            continue
        
        # Parentheses
        if source[i] == '(':
            tokens.append(Token('LPAREN', '('))
            i += 1
            continue
        if source[i] == ')':
            tokens.append(Token('RPAREN', ')'))
            i += 1
            continue
        
        # Block brackets (not fully supported yet)
        if source[i] == '[':
            tokens.append(Token('LBRACKET', '['))
            i += 1
            continue
        if source[i] == ']':
            tokens.append(Token('RBRACKET', ']'))
            i += 1
            continue
        
        # Vertical bar (for temporaries)
        if source[i] == '|':
            tokens.append(Token('BAR', '|'))
            i += 1
            continue
        
        # Numbers (integer or float)
        if source[i].isdigit() or (source[i] == '-' and i + 1 < len(source) and source[i+1].isdigit()):
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
                tokens.append(Token('FLOAT', source[i:j]))
            else:
                tokens.append(Token('INT', source[i:j]))
            i = j
            continue
        
        # String literals
        if source[i] == "'":
            j = i + 1
            while j < len(source):
                if source[j] == "'":
                    if j + 1 < len(source) and source[j+1] == "'":
                        j += 2  # escaped quote
                    else:
                        break
                else:
                    j += 1
            tokens.append(Token('STRING', source[i+1:j]))
            i = j + 1
            continue
        
        # Symbol literals (#symbol or #'symbol with spaces')
        if source[i] == '#':
            if i + 1 < len(source) and source[i+1] == "'":
                # #'symbol with spaces'
                j = i + 2
                while j < len(source) and source[j] != "'":
                    j += 1
                tokens.append(Token('SYMBOL', source[i+2:j]))
                i = j + 1
            else:
                # #symbol
                j = i + 1
                while j < len(source) and (source[j].isalnum() or source[j] in '_:'):
                    j += 1
                tokens.append(Token('SYMBOL', source[i+1:j]))
                i = j
            continue
        
        # Identifiers and keywords
        if source[i].isalpha() or source[i] == '_':
            j = i
            while j < len(source) and (source[j].isalnum() or source[j] == '_'):
                j += 1
            name = source[i:j]
            # Check if it's a keyword (ends with :)
            if j < len(source) and source[j] == ':':
                tokens.append(Token('KEYWORD', name + ':'))
                i = j + 1
            else:
                tokens.append(Token('NAME', name))
                i = j
            continue
        
        # Binary selectors (operators)
        binary_chars = '+-*/\\<>=@%|&?,~'
        if source[i] in binary_chars:
            j = i
            while j < len(source) and source[j] in binary_chars:
                j += 1
            tokens.append(Token('BINARY', source[i:j]))
            i = j
            continue
        
        raise SyntaxError(f"Unexpected character: {source[i]!r} at position {i}")
    
    tokens.append(Token('EOF', ''))
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
    body: List[ASTNode]

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
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
    
    def current(self) -> Token:
        return self.tokens[self.pos]
    
    def peek(self, offset: int = 0) -> Token:
        pos = self.pos + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return Token('EOF', '')
    
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
        """Parse a block: [ :param | statements ]"""
        self.expect('LBRACKET')
        
        params = []
        # Parse block parameters :param1 :param2 |
        while self.current().type == 'KEYWORD' and self.current().value.startswith(':'):
            # Block params look like :name but tokenizer sees them differently
            # Actually in Smalltalk block params are : followed by name
            pass
        
        # For now, blocks are not fully supported
        # Just consume until ]
        depth = 1
        while depth > 0:
            tok = self.advance()
            if tok.type == 'LBRACKET':
                depth += 1
            elif tok.type == 'RBRACKET':
                depth -= 1
            elif tok.type == 'EOF':
                raise SyntaxError("Unclosed block")
        
        return BlockNode([], [])

# ----------------------------------------------------------------------
# Code Generator
# ----------------------------------------------------------------------

class CodeGenerator:
    def __init__(self):
        self.tmp_counter = 0
        self.lines = []
        self.temps = set()  # track declared temporaries
        self.params = set()  # track method parameters
        self.inst_vars = set()  # will be populated by context
    
    def new_tmp(self) -> str:
        self.tmp_counter += 1
        return f"tmp{self.tmp_counter}"
    
    def generate_method(self, node: MethodNode, original_source: str) -> str:
        """Generate complete Bash method script"""
        self.lines = []
        self.temps = set(node.temps)
        self.params = set(node.params)
        
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
        
        return '\n'.join(self.lines)
    
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
            return "[ \"block not supported\" ]"
        
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
            self.lines.append(f"echo ${result}")
        
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
        args_str = ' '.join(f"${v}" if not v.startswith(('int/', 'float/', 'true', 'false', 'nil')) else v 
                           for v in arg_vars)
        recv_ref = f"${recv_var}" if not recv_var.startswith(('int/', 'float/', 'true', 'false', 'nil')) else recv_var
        
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
            recv_ref = f"${recv_var}"
            args_str = ' '.join(f"${v}" if not v.startswith(('int/', 'float/', 'true', 'false', 'nil')) else v
                               for v in arg_vars)
            
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
                if value_var.startswith(('int/', 'float/', 'true', 'false', 'nil')):
                    self.lines.append(f"echo {value_var} > $self/{name}")
                else:
                    self.lines.append(f"echo ${value_var} > $self/{name}")
                return value_var
        
        elif isinstance(node, SendNode):
            return self.generate_send(node)
        
        elif isinstance(node, CascadeNode):
            return self.generate_cascade(node)
        
        elif isinstance(node, BlockNode):
            raise NotImplementedError("Blocks not yet supported")
        
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
            else:
                # Instance variable
                self.lines.append(f"{target_var}=$(cat $self/{name})")
        
        elif isinstance(node, SendNode):
            recv_var = self.generate_expr(node.receiver)
            
            arg_vars = []
            for arg in node.args:
                arg_vars.append(self.generate_expr(arg))
            
            selector = node.selector.replace(':', '-')
            args_str = ' '.join(f"${v}" if not v.startswith(('int/', 'float/', 'true', 'false', 'nil')) else v 
                               for v in arg_vars)
            recv_ref = f"${recv_var}" if not recv_var.startswith(('int/', 'float/', 'true', 'false', 'nil')) else recv_var
            
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
                recv_ref = f"${recv_var}"
                args_str = ' '.join(f"${v}" if not v.startswith(('int/', 'float/', 'true', 'false', 'nil')) else v
                                   for v in arg_vars)
                
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
        args_str = ' '.join(f"${v}" if not v.startswith(('int/', 'float/', 'true', 'false', 'nil')) else v 
                           for v in arg_vars)
        recv_ref = f"${recv_var}" if not recv_var.startswith(('int/', 'float/', 'true', 'false', 'nil')) else recv_var
        
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
            args_str = ' '.join(f"${v}" if not v.startswith(('int/', 'float/', 'true', 'false', 'nil')) else v
                               for v in arg_vars)
            recv_ref = f"${recv_var}"
            
            if args_str:
                self.lines.append(f"{tmp}=$(./send {recv_ref} {selector} {args_str})")
            else:
                self.lines.append(f"{tmp}=$(./send {recv_ref} {selector})")
            
            last_result = tmp
        
        return last_result

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def transpile(source: str) -> str:
    """Transpile Smalltalk method source to Bash script"""
    tokens = tokenize(source)
    parser = Parser(tokens)
    ast = parser.parse_method()
    gen = CodeGenerator()
    return gen.generate_method(ast, source)

def main():
    if len(sys.argv) < 2:
        print("Usage: smalltix_transpiler.py <source_file> [output_file]", file=sys.stderr)
        print("       smalltix_transpiler.py -e '<smalltalk source>'", file=sys.stderr)
        sys.exit(1)
    
    if sys.argv[1] == '-e':
        if len(sys.argv) < 3:
            print("Error: -e requires source argument", file=sys.stderr)
            sys.exit(1)
        source = sys.argv[2]
    else:
        with open(sys.argv[1], 'r') as f:
            source = f.read()
    
    try:
        result = transpile(source)
        
        if len(sys.argv) > 2 and sys.argv[1] != '-e':
            with open(sys.argv[2], 'w') as f:
                f.write(result)
                f.write('\n')
        elif len(sys.argv) > 3 and sys.argv[1] == '-e':
            with open(sys.argv[3], 'w') as f:
                f.write(result)
                f.write('\n')
        else:
            print(result)
    
    except (SyntaxError, NotImplementedError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
