#!/usr/bin/env python

"""Simple python macro expansion"""

__version__ = "0.8.2"

import os, sys, io

import six

import logging

log = logging.getLogger(__name__)

def macro(func):
    def wrap(*arg, **kw):
        return func(*arg, **kw)
    wrap.is_macro = True
    wrap.__name__ = func.__name__
    return wrap

class Smx:
    funcs = {}

    def __init__(self):

        self.__fi_lno = 1
        self.__fi_off = 0
        self.__fi_name = "<inline>"
        self.__locals = {}
        self.__globals = {
                "os" : os,
                "sys" : sys,
        }

        self.use_env = False

        for name, func in self.__class__.__dict__.items():
            if hasattr(func, "is_macro"):
                f = (lambda func, self: lambda *args: func(self, *args))(func, self)
                self.__globals[name] = f

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
        self.__globals[name] = eval(name)

    @macro
    def expand(self, dat):
        fi = io.StringIO(six.u(dat))
        fo = io.StringIO()
        self.expand_io(fi, fo)
        return str(fo.getvalue())

    def expand_file(self, file_name, output_stream=None, in_place=False):
        log.debug("expand file %s" % file_name)
        fi = io.open(file_name)

        self.__fi_name = file_name
        self.__fi_lno = 1
        
        if in_place:
            fo = NamedTemporaryFile(prefix=f, dir=os.path.dirname(f) or ".", delete=False)
        elif output_stream:
            fo = output_stream
        else:
            log.debug("using stdout")
            fo = sys.stdout

        self.expand_io(fi, fo)

        if in_place:
            fo.close()
            os.rename(fo.name, f) 

    def expand_io(self, fi, fo, term=[], in_c=None):
        c = in_c or fi.read(1)
        while c != '':
            if c == '\n':
                self.__fi_lno += 1
                self.__fi_off = 0
            elif c == ' ':
                self.__fi_off += 1

            if c in term:
                return c

            if c != '%':
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

                lno = self.__fi_lno
                off = self.__fi_off
                if c == '%':
                    self._exec(name, args, fi, fo, lno, off)
                elif c == '(':
                    anum = 1
                    arg, tc = self._exparg(name, anum, fi)
                    while arg is not None:
                        args.append(arg)
                        if tc != ',':
                            break
                        anum += 1
                        arg, tc = self._exparg(name, anum, fi)

                    self._exec(name, args, fi, fo, lno, off)
                else:
                    self._error(SyntaxError("unterminated macro"))

            c = fi.read(1)

    def _exec(self, name, args, fi, fo, lno, off):
        if self.use_env and not args:
            if name in os.environ:
                fo.write(six.u(os.environ[name]))
                return

        f = eval(name, self.__globals, self.__locals)

        if f is None:
            raise NameError("name '%s' is not defined" % (name))

        log.debug("exec %s %s", name, args)

        try:
            # these are available to the function, if needed

            self.__func_lno = lno
            self.__func_off = off

            res = f(*args)

            if res is not None:
                fo.write(six.u(res))
            else:
                log.debug("file %s, line %s, function %s returned None", self.__fi_name, lno, name)
        except Exception as e:
            log.exception("exception in file %s, line %s, function %s", self.__fi_name, lno, name)
            self._error(e, lno=lno)

    def _exparg(self, fname, argnum, fi):
        c = fi.read(1)

        while c.isspace():
            c = fi.read(1)

        fo = io.StringIO()
       
        if c in (',', ')'):
            return None, c

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

        return str(fo.getvalue()), term_char

    def _error(self, e, lno=None):
        if not lno:
            lno = self.__fi_lno
        err = "file %s, line %s: %s(%s)" % (self.__fi_name, lno, e.__class__.__name__, str(e))
        log.error(err)
        raise e


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Simple macro expansion')

    parser.add_argument('-d', '--debug', action='store_true', help='turn on debug logging')
    parser.add_argument('-i', '--inplace', action='store_true', help='modify files in-place')
    parser.add_argument('-e', '--env', action='store_true', help='export env vars as macro names')
    parser.add_argument('-r', '--restrict', action='append', help='restrict macros to explicit list')
    parser.add_argument('-m', '--module', action='append', help='import python module', default=[])
    parser.add_argument("inp", nargs="+", help='list of files', default=[])

    args = parser.parse_args()

    level = logging.ERROR
    if args.debug:
        level = logging.DEBUG

    logging.basicConfig(format='%(asctime)-15s %(levelname)s %(message)s', level=level)

    ctx = Smx()

    for m in args.module:
        ctx.module(m)

    if args.restrict:
        ctx.restrict(args.restrict)

    if args.env:
        ctx.use_env = True

    for f in args.inp:
        try:
            ctx.expand_file(f, in_place=args.inplace)
        except Exception as e:
            log.error(e)

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

    assert res == expected

def test_module():
    ctx = Smx()
    ret = ctx.expand("%os.path.basename(/foo/bar)")
    assert ret == "bar"

def test_err():
    ctx = Smx()
    try:
        ctx.expand("%add( 1 ,\n%add( 2 ,  ))") == "6"
        assert False
    except TypeError:
        pass

