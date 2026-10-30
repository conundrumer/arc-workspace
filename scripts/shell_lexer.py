"""The reader of shell source for `delete_bash_hook`: `Lexer` splits
shell source into `Word`, `Redirect` and operator tokens, keeping each word's
executable children (substitutions), its quoting and heredoc bodies.
Source it cannot read raises `Unreadable`. `UNKNOWN` stands in a word's text
for a value the reader cannot know, and `DOLLAR` for a literal `$`."""

import re
from dataclasses import dataclass, field

UNKNOWN = "\x01"
DOLLAR = "\x02"


class Unreadable(ValueError):
    """Executable input whose boundaries or context cannot be read."""


@dataclass
class Word:
    text: str
    children: list[list['Token']] = field(default_factory=list)
    quoted: bool = False
    splits: bool = False
    span: tuple[int, int] | None = None


@dataclass
class Redirect:
    fd: int
    operator: str
    target: Word
    body: Word | None = None


type Token = Word | Redirect | str


class Lexer:
    """Retain executable children, quoting and input redirections.

    Offsets in failures refer to this reader's source, including a nested
    interpreter's source when that interpreter is read separately.
    """

    def __init__(self, source: str):
        self.source = source
        self.at = 0

    def fail(self, start: int, reason: str) -> Unreadable:
        return Unreadable(f"source[{start}:{self.at + 1}] {self.source[start:self.at + 1]!r}: {reason}")

    def tokens(self, closing: bool = False) -> list[Token]:
        tokens: list[Token] = []
        pending: list[Redirect] = []
        while self.at < len(self.source):
            start = self.at
            c = self.source[self.at]
            if c in ' \t\r':
                self.at += 1
                continue
            if c == '#':
                end = self.source.find('\n', self.at)
                self.at = len(self.source) if end < 0 else end
                continue
            if c == '\n':
                self.at += 1
                tokens.append('\n')
                for redir in pending:
                    lines: list[str] = []
                    while self.at < len(self.source):
                        end = self.source.find('\n', self.at)
                        end = len(self.source) if end < 0 else end + 1
                        line = self.source[self.at:end]
                        self.at = end
                        if redir.operator == '<<-':
                            line = line.lstrip('\t')
                        if line.rstrip('\n') == redir.target.text.replace(DOLLAR, '$'):
                            break
                        lines.append(line)
                    else:
                        raise self.fail(start, 'unterminated heredoc')
                    body = ''.join(lines)
                    redir.body = (Word(body.replace("$", DOLLAR)) if redir.target.quoted
                                  else Lexer(body).word(data=True))
                pending.clear()
                continue
            if self.source.startswith(('<(', '>('), self.at):
                tokens.append(self.word())
                continue
            redirection = re.match(r'(\d*)(<<-|<<<|<<|>>|<>|>&|<&|>|<)', self.source[self.at:])
            if redirection:
                self.at += redirection.end()
                fd, op = redirection.groups()
                while self.at < len(self.source) and self.source[self.at] in ' \t':
                    self.at += 1
                target = self.word(delimiter=op in {'<<', '<<-'})
                if not target.text:
                    raise self.fail(start, 'missing redirection operand')
                redir = Redirect(int(fd) if fd else (0 if op.startswith('<') else 1), op, target)
                tokens.append(redir)
                if op in {'<<', '<<-'}:
                    pending.append(redir)
                continue
            if c in ';&|()':
                self.at += 1
                if c == ')' and closing:
                    if pending:
                        raise self.fail(start, 'heredoc before substitution boundary')
                    return tokens
                op = c
                if c in ';&|' and self.at < len(self.source) and self.source[self.at] == c:
                    op += c
                    self.at += 1
                elif c == '|' and self.at < len(self.source) and self.source[self.at] == '&':
                    op += '&'
                    self.at += 1
                if op == '(':
                    tokens.extend(['(', *self.tokens(closing=True), ')'])
                else:
                    tokens.append(op)
                continue
            tokens.append(self.word())
        if pending or closing:
            raise self.fail(self.at, 'missing executable input boundary')
        return tokens

    def word(self, *, data: bool = False, delimiter: bool = False) -> Word:
        start = self.at
        out = Word('')
        quote = ''
        while self.at < len(self.source):
            c = self.source[self.at]
            if not data and not quote and (c in ' \t\r\n;&|()<>'):
                if not self.source.startswith(('<(', '>('), self.at):
                    break
            self.at += 1
            if c == '\\' and quote != "'":
                if self.at >= len(self.source):
                    raise self.fail(start, 'trailing escape')
                following = self.source[self.at]
                if (quote == '"' or data) and following not in '$`\\\n"':
                    out.text += '\\'
                    continue
                self.at += 1
                out.quoted = True
                if following != '\n':
                    out.text += DOLLAR if following == '$' else following
                continue
            if not data and c in "'\"":
                if not quote:
                    quote = c
                    out.quoted = True
                    continue
                if quote == c:
                    quote = ''
                    continue
            if quote == "'" or delimiter:
                out.text += DOLLAR if c == '$' else c
                continue
            if c == '`':
                out.children.append(self.backticks(start))
                out.text += UNKNOWN
                continue
            if not quote and not data and c in '<>' and self.at < len(self.source) and self.source[self.at] == '(':
                self.at += 1
                out.children.append(self.tokens(closing=True))
                out.text += UNKNOWN
                continue
            if c == '$' and self.at < len(self.source):
                out.splits |= not quote and not data
                if self.source.startswith('(', self.at) and not self.source.startswith('((', self.at):
                    self.at += 1
                    out.children.append(self.tokens(closing=True))
                    out.text += UNKNOWN
                    continue
                if self.source[self.at] in '{(':
                    self.expansion(out, start)
                    continue
                if self.source[self.at] in "'\"":
                    raise self.fail(start, 'unsupported shell quote expansion')
            out.text += c
        if quote:
            raise self.fail(start, 'unterminated quote')
        if not data and self.at == start:
            raise self.fail(start, 'unsupported word boundary')
        out.span = (start, self.at)
        return out

    def backticks(self, start: int) -> list[Token]:
        nested = ''
        while self.at < len(self.source):
            c = self.source[self.at]
            self.at += 1
            if c == '`':
                return Lexer(nested).tokens()
            if c == '\\' and self.at < len(self.source) and self.source[self.at] in '$`\\':
                c = self.source[self.at]
                self.at += 1
            nested += c
        raise self.fail(start, 'unterminated backticks')

    def expansion(self, out: Word, start: int) -> None:
        opening = self.source[self.at]
        closing = '}' if opening == '{' else ')'
        self.at += 1
        inner_start = self.at
        depth = 1
        while self.at < len(self.source):
            c = self.source[self.at]
            if c == '\\':
                self.at += 2
                continue
            if c == '`':
                self.at += 1
                out.children.append(self.backticks(start))
                continue
            if c in "'\"":
                raise self.fail(start, 'unsupported quote inside extended expansion')
            if self.source.startswith(('<(', '>('), self.at):
                self.at += 2
                out.children.append(self.tokens(closing=True))
                continue
            if self.source.startswith('$(', self.at) and not self.source.startswith('$((', self.at):
                self.at += 2
                out.children.append(self.tokens(closing=True))
                continue
            if self.source.startswith(('${', '$(('), self.at):
                self.at += 1
                self.expansion(out, start)
                continue
            if c == opening:
                depth += 1
            elif c == closing:
                depth -= 1
                if depth == 0:
                    inner = self.source[inner_start:self.at]
                    self.at += 1
                    out.text += ('${' + inner + '}' if opening == '{' and re.fullmatch(r'\w+', inner)
                                 else UNKNOWN)
                    return
            self.at += 1
        raise self.fail(start, 'unterminated parameter or arithmetic expansion')
