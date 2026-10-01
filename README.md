[![Tests](https://github.com/earonesty/python-smx/actions/workflows/tests.yml/badge.svg)](https://github.com/earonesty/python-smx/actions/workflows/tests.yml)

### Simple python templates

    example:
      - key : %os.environ.get(USER)
      - roaming : %if(sys.platform=='win32',1,0)
      %indent(%include(file_name))
      - other : %eval(1 + 1)
      %indent(%python("
    import mod
    f = open('myfile.in')
    f.read()
    output(mod.process(f))
     ")

Allows simple macros to be expanded inline.  You can `from smx import Smx` to evaluate, or evaluate from the command line.   Options to import all env vars, or modules from the command line are available.  Macros can be nested... so `%expand(%include(...))` is a valid syntax.

Used for yml templates, config files, Kubernetes deployments, simple HTML pages, etc.

### Install
    pip install smx

### Use

```
   > smx file.in > file.out
   > smx --help
```

Or from python:

```
   from smx import Smx
   ctx = Smx()
   ctx.expand("%add(1,1)")
   ctx.expand_io(fin, fout)
   ctx.expand_file(filename, in_place=True)
```

### Defining macros

Use `%define(name,body,arg1,arg2,...)` to define a macro. The body is saved
without expansion, then expanded when you call the macro. Arguments are strings
available inside the body as `%arg1%`, `%arg2%`, etc.

```text
%define(host,"https://mysite.com/")
%define(link,%host()%val%,val)
%link(page)
```

The final line expands to `https://mysite.com/page`. The definitions produce no
output; `function define returned None` in debug logging is expected.
`%host()` and `%host%` both call the constant macro; bare `%host` is incomplete.
Adjacent expansions concatenate strings, so `%eval` is unnecessary here.
`%eval(%host() + val)` inserts an unquoted URL into a Python expression and
therefore raises a syntax error.

Calls to defined macros temporarily bind their arguments and restore the caller's variables
on return, including after an expansion error.

### Quoting and expansion

SMX arguments are template text, rather than Python expressions. Double quotes
can enclose an argument containing commas; the surrounding quotes are removed.
A leading apostrophe (`'`) suppresses expansion of that argument and has no
closing apostrophe. For example, `%strip('%host%)` returns the literal `%host%`.
The second argument of `define` is already saved without expansion.

The apostrophe in `%eval('math.factorial(int(val)))` in `test_defmacro` is this
SMX marker: it is removed before the expression reaches Python. `%eval` evaluates
a Python expression; `%python` can also execute Python statements.

### Including code and files

| Macro | Description |
| :---   | :- |
| indent(str) | each line of the indented string is indented at the level where the indent function was called. | 
| include(str) | include the specified file | 
| strip(str) | strip a string | 
| expand(str) | string is expanded using smx syntax | 
| python(str) | string is expanded using python syntax | 
| module(str) | string is interpreted as a module and imported | 

### Modules

| Macro | Description |
| :---   | :- |
| os.... | os functions are included by default, for example `%os.path.basename(...)` | 
| sys.... | sys functions are included by default EG: `%sys.platform%` can be used| 

### Misc

| Macro | Description |
| :---   | :- |
| for(name, range, loop) | loop code is expanded for each value in the range | 
| if(val, true-val, false-val) | if val is expanded to non-empty, true-val is executed | 
| add(a, b) | numbers are added | 
| sub(a, b) | numbers are subtracted | 

### Wsgi
 Smx includes an [wsgi module](wsgi.md).   The goal is to be able to easily serve template driven pages using smx syntax.

### Goals 

 - The syntax should be "macroy" not "pythony" ... that way you can tell, at a glance when there's macros going on... vs python going on.
 - Easy to add your own macros by deriving from Smx and adding new functions with the @smx.macro decorator.
 - Easy to import python modules and use them in basically any string context
 - JSON and YAML template friendly
 - Use "as is" in most configuration contexts
 - Templates run with Python access and should come from trusted authors.

### Caveats

 - Important to remember that all macros result in "strings", not other python types.
 - When context-oriented template programming gets complex, you probably shouldn't be using templates.

### Development

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r reqs.txt
./test.sh
```

### Background

SMX takes inspiration from the Server Macro Expansion syntax in the 1990s
Commerce Builder web server. This is a standalone Python implementation with a
small macro vocabulary; compatibility with legacy templates is partial.
See the [earlier SMX project](https://github.com/earonesty/smx) for historical context.
