#!/usr/bin/env python

import os, sys, io
import six
import logging

__version__ = "0.9.5"

from tempfile import NamedTemporaryFile

log = logging.getLogger(__name__)

def macro(*args, **kws):
    if not kws:
        func = args[0]
        def wrap(*arg, **kw):
            return func(*arg, **kw)
        wrap.is_macro = True
        wrap.quoted = False
        wrap.__name__ = args[0].__name__
        return wrap
    else:
        def outer(func):
            def wrap(*arg, **kw):
                return func(*arg, **kw)
            wrap.is_macro = True
            wrap.quoted = kws.get("quote")
            wrap.__name__ = kws.get("name") or func.__name__
            return wrap
        return outer

class Smx:
    funcs = {}

    def __init__(self, init={}, environ={}):

        self.environ = environ
        self.__fi_lno = 1
        self.__fi_off = 0
        self.__fi_name = "<inline>"
        self.__locals = {}
        self.__globals = {
                "os" : os,
                "sys" : sys,
                "version" : __version__,
        }
        self.__stack = []
        if isinstance(init, Smx):
            init = init.__locals
        self.__locals.update(init)

        for name, func in self.__class__.__dict__.items():
            if hasattr(func, "is_macro"):
                f = (lambda func, self: lambda *args: func(self, *args))(func, self)
                f.quoted = func.quoted
                self.__globals[func.__name__] = f
                if func.__name__ in ["expand","module"]:
                    globals()[func.__name__] = f

    @macro
    def python(self, data):
        try:
            return str(eval(data, self.__globals, self.__locals))
        except SyntaxError:
            self.__output = None
            exec(data, self.__globals, self.__locals)
            return self.__output

    @macro
    def output(self, data):
        self.__output = str(data)

    @macro
    def strip(self, data, chars=None):
        return data.strip(chars)

    @macro
    def include(self, f):
        return open(f).read()

    @macro
    def indent(self, data, n=None):
        if n is None:
            n = self.__func_off
        else:
            n = int(n)

        data = data.lstrip()
        res = ""
        first = True
        for line in io.StringIO(six.u(data)):
            if not first:
                line = " " * n + line
            res += line
            first = False

        return str(res.rstrip())

    @macro
    def eval(self, code):
        return eval(code, self.__globals, self.__locals)

    @macro(name="if",quote=[2,3])
    def _if(self, cond, do1, do2):
        ret = ""
        if cond and eval(cond):
            ret += self.expand(str(do1))
        else:
            ret += self.expand(str(do2))
        return ret

    @macro(name="for",quote=[3])
    def _for(self, name, loop, do):
        ret = ""
        locs = {}
        self.push_local(locs)
        for x in eval(loop):
            locs[name]=x
            ret += self.expand(str(do))
        return ret

    @macro(quote=[2])
    def define(self, name, body, *args):
        j_names = ','.join(args)
        defs = ""
        for arg in args:
            defs += "    self._Smx__locals['" + arg + "']=" + arg + "\n"
        code = """def _tmp(self, """ + j_names + """):
    self.push_local({})
""" + defs + """
    self.__res = self.expand('''""" + body + """''')
    self.pop_local()
    return self.__res
"""
        locs = {}
        exec(code, globals(), locs)
        self.__globals[name] = lambda *args: locs["_tmp"](self, *args)

    def pop_local(self):
        if self.__stack:
            self.__locals = self.__stack.pop()

    def push_local(self, x):
        self.__stack.append(x)
        self.__locals = x 

    @macro
    def set(self, key, val):
        self.__locals[key] = val

    @macro
    def get(self, key):
        return self.__locals.get(key,self.__globals.get(key,""))

    @macro
    def add(self, a, b):
        try:
            return str(int(a)+int(b))
        except ValueError:
            return str(float(a)+float(b))

    @macro
    def sub(self, a, b):
        try:
            return str(int(a)-int(b))
        except ValueError:
            return str(float(a)-float(b))

    @macro
    def module(self, name):
        self.__globals[name] = new_module = __import__(name)

    @macro
    def expand(self, dat):
        fi = io.StringIO(six.u(dat))
        fo = io.StringIO()
        log.debug("expand '%s", dat)
        self.expand_io(fi, fo)
        return str(fo.getvalue())

    def expand_file(self, file_name, output_stream=None, in_place=False):
        log.debug("expand file %s" % file_name)
        fi = io.open(file_name)

        self.__fi_name = file_name
        self.__fi_lno = 1

        if in_place:
            fo = NamedTemporaryFile(prefix=file_name, dir=os.path.dirname(file_name) or ".", delete=False, mode="w")
        elif output_stream:
            fo = output_stream
        else:
            log.debug("using stdout")
            fo = sys.stdout

        self.expand_io(fi, fo)

        if in_place:
            fo.close()
            os.rename(fo.name, file_name) 

    def expand_io(self, fi, fo, term=[], in_c=None):
        c = in_c or fi.read(1)
        par = 0
        tmp = u''
        while c != '':
            if c == '\n':
                self.__fi_lno += 1
                self.__fi_off = 0
            elif c == ' ':
                self.__fi_off += 1
            elif c == '(':
                par += 1

            if c in term and not par:
                return c

            if c == ')':
                par -= 1

            if c == ' ':
                tmp += c
            else:
                fo.write(tmp)
                tmp = u''

            if c != '%':
                if c != ' ':
                    fo.write(c)
                c = fi.read(1)
                continue

            if (c=='%'):
                c = fi.read(1)
                if (c == '%'):
                    fo.write(c)
                    c = fi.read(1)
                    continue

                name = ""
                while (c.isalnum() or c == "."):
                    name += c
                    c = fi.read(1)

                args = []

                f = self.__locals.get(name) or self.__globals.get(name)
                quoted = f and getattr(f, "quoted", None)

                lno = self.__fi_lno
                off = self.__fi_off
                if c == '%':
                    self._exec(name, args, fi, fo, lno, off)
                elif c == '(':
                    anum = 1
                    noexp = quoted and anum in quoted
                    arg, tc = self._exparg(name, anum, fi, no_expand=noexp)
                    while arg is not None:
                        args.append(arg)
                        if tc != ',':
                            break
                        anum += 1
                        noexp = quoted and anum in quoted
                        arg, tc = self._exparg(name, anum, fi, no_expand=noexp)

                    self._exec(name, args, fi, fo, lno, off)
                else:
                    self._error(SyntaxError("unterminated macro"))

            c = fi.read(1)

    def _exec(self, name, args, fi, fo, lno, off):
        if not args:
            if name in self.environ:
                fo.write(six.u(self.environ[name]))
                return

        if name in self.__locals:
            f = self.__locals[name]
        elif name in self.__globals:
            f = self.__globals[name]
        elif "." in name:
            f = eval(name, self.__globals, self.__locals)
        else:
            f = None

        if f is None:
            self._error(NameError("name '%s' is not defined" % (name)), lno=lno)

        log.debug("exec %s %s", name, args)

        try:
            # these are available to the function, if needed

            self.__func_lno = lno
            self.__func_off = off

            if isinstance(f, dict):
                if len(args) == 1:
                    res = f[args[0]]
                else:
                    f[args[0]] = args[1]
                    res = None
            elif not args and not callable(f):
                res = str(f)
            else:
                res = f(*args)

            if res is not None:
                fo.write(six.u(str(res)))
            else:
                log.debug("file %s, line %s, function %s returned None", self.__fi_name, lno, name)
        except Exception as e:
            log.debug("exception in file %s, line %s, function %s", self.__fi_name, lno, name)
            self._error(e, lno=lno)

    def scan_io(self, fi, fo, term, in_c = None):
        c = in_c or fi.read(1)
        res = u""
        par = 0
        while c != '':
            # todo, properly generate a parse tree
            if c == '\n':
                self.__fi_lno += 1
                self.__fi_off = 0
            elif c == ' ':
                self.__fi_off += 1
            elif c == '(':
                par += 1

            if par:
                if c in ')':
                    par -= 1
            elif c in term:
                break

            res += c
            c = fi.read(1)
        return c, res

    def _exparg(self, fname, argnum, fi, no_expand=False):
        c = fi.read(1)

        while c.isspace():
            c = fi.read(1)

        fo = io.StringIO()
      
        if c == "'":
            no_expand = True
            c = fi.read(1)

        if c in (')'):
            return None, c

        if c in (','):
            return "", c

        if no_expand:
            if c == '"':
                term_char, res = self.scan_io(fi, fo, term=['"'])
            else:
                term_char, res = self.scan_io(fi, fo, term=[',',')'], in_c=c)
        else:
            if c == '"':
                term_char = self.expand_io(fi, fo, term=['"'])
            else:
                term_char = self.expand_io(fi, fo, term=[',',')'], in_c=c)

        if term_char == '"':
            c = fi.read(1)
            while c.isspace():
                c = fi.read(1)
            term_char = c

        if term_char not in [',', ')']:
            self._error(SyntaxError("parsing argument %s in '%s'" % (argnum, fname)))

        if no_expand:
            return res, term_char

        return str(fo.getvalue()), term_char

    def _error(self, e, lno=None):
        if not lno:
            lno = self.__fi_lno
        err = "file %s, line %s: %s(%s)" % (self.__fi_name, lno, e.__class__.__name__, str(e))
        log.error(err)
        e.line_number = lno
        e.file_name = self.__fi_name
        raise e


def main(test_argv=None):
    import argparse

    parser = argparse.ArgumentParser(description='Simple macro expansion')

    parser.add_argument('-v', '--version', action='store_true', help='show version')
    parser.add_argument('-d', '--debug', action='store_true', help='turn on debug logging')
    parser.add_argument('-c', '--command', help='run a single statement')
    parser.add_argument('-i', '--inplace', action='store_true', help='modify files in-place')
    parser.add_argument('-e', '--env', action='store_true', help='export env vars as macro names')
    parser.add_argument('-r', '--restrict', action='append', help='restrict macros to explicit list')
    parser.add_argument('-m', '--module', action='append', help='import python module', default=[])
    parser.add_argument("inp", nargs="*", help='list of files', default=[])

    args = parser.parse_args(test_argv)

    if args.version:
        print(__version__)

    level = logging.ERROR
    if args.debug:
        level = logging.DEBUG

    logging.basicConfig(format='%(asctime)s %(lineno)d %(levelname)s %(message)s', level=level)

    ctx = Smx()

    for m in args.module:
        ctx.module(m)

    if args.restrict:
        ctx.restrict(args.restrict)

    if args.env:
        ctx.environ = os.environ

    if args.command:
        print(ctx.expand(args.command))

    for f in args.inp:
        try:
            ctx.expand_file(f, in_place=args.inplace)
        except Exception as e:
            log.exception(e)

if __name__ == "__main__":
    main()

def test_simple():
    ctx = Smx()
    assert ctx.expand("%add(1,1)") == "2"

def test_nested():
    ctx = Smx()
    assert ctx.expand("%add(1,%add(2,3))") == "6"

def test_python():
    ctx = Smx()
    res = ctx.expand("""%python("
import os

def func(x, y):
   return x + y

output(func(4,5))
")""")
    
    assert res == "9"

def test_spaces():
    ctx = Smx()
    assert ctx.expand("%add( 1 ,\n%add( 2 , 3 ))") == "6"

    assert ctx.expand("%expand(  1  )") == "1"

def test_indent():
    ctx = Smx()
    res = ctx.expand("""
    <<-here
    %indent(
stuff
indented
    )
""")

    expected = """
    <<-here
    stuff
    indented
"""

    log.debug("%s %s", res, expected)
    assert res == expected

def test_basename():
    ctx = Smx()
    ret = ctx.expand("%os.path.basename(/foo/bar)")
    assert ret == "bar"

def test_eval():
    ctx = Smx()
    ret = ctx.expand("%eval(2 ** 32)")
    assert ret == "4294967296"

def test_err():
    ctx = Smx()
    try:
        ctx.expand("%add( 1 ,\n%add( 2 ,  ))") == "6"
        assert False
    except TypeError:
        pass

def test_for():
    ctx = Smx()
    res = ctx.expand("%for(x,range(9),%x%)")
    assert res == "012345678"


def test_define():
    ctx = Smx()
    
    ctx.expand("""
    %python(
        def factorial(val):
            import math
            return(math.factorial(int(val)))
        )
    """)
    
    res = ctx.expand("%factorial(3)")
    assert res == "6"

def test_defmacro():
    ctx = Smx()
    
    ctx.expand("""
    %define(factorial,%strip(
            %module(math)
            %eval('math.factorial(int(val)))
        ),val)
    """)
    
    res = ctx.expand("%factorial(3)")
    print("res == ", res)
    assert res == "6"


def test_set_get():
    ctx = Smx()
    ctx.expand("%python(x = 4)")
    res = ctx.expand("%x%")
    assert res == "4"
    ctx.expand("%set(x,5)")
    res = ctx.expand("%x%")
    assert res == "5"
    res = ctx.expand("%get(x)")
    print("res == 5 ? ", res)
    assert res == "5"
    res = ctx.expand("%get(nada)")
    assert res == ""

def test_if():
    ctx = Smx()
    res = ctx.expand("%if(,T,F)")
    assert res == "F"
    res = ctx.expand("%if(False,T,F)")
    assert res == "F"
    res = ctx.expand("%if(True,T,F)")
    assert res == "T"
    res = ctx.expand("%if(sys.platform == 'nada',T,F)")
    assert res == "F"

def test_escape():
    ctx = Smx()
    res = ctx.expand("%%")
    assert res == "%"
    res = ctx.expand("%%%add(1,1)")
    assert res == "%2"

def test_os():
    ctx = Smx()
    ret = ctx.expand("%os.path.basename(/foo/bar)")
    assert ret == "bar"

def test_version():
    ctx = Smx()
    ret = ctx.expand("%version%")
    assert ret == str(__version__)

def test_module():
    ctx = Smx()
    res = ctx.expand("%module(platform)%platform.system%")
    assert res

def test_error_lineno():
    ctx = Smx()
    try:
        res = ctx.expand("1\n2%sys.platform%\n3\n4\n5%xxfooxx%")
        assert False
    except NameError as e:
        assert e.line_number == 5
        assert "xxfooxx" in str(e)

def test_file():
    with NamedTemporaryFile(delete=False) as f:
        f.write(six.b("%for(i,range(3),%i%)"))

    # to stream
    out = io.StringIO()
    Smx().expand_file(f.name, out)
    print(out.getvalue())
    assert str(out.getvalue()) == "012"

    # inplace
    Smx().expand_file(f.name, in_place=True)
    res = str(open(f.name).read())
    assert res == "012"

    os.unlink(f.name)
