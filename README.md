[![Build Status](https://travis-ci.com/earonesty/python-smx.svg?branch=master)](https://travis-ci.com/earonesty/python-smx)
[![Coverage](https://codecov.io/gh/earonesty/python-smx/branch/master/graph/badge.svg)](https://codecov.io/gh/earonesty/python-smx)

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

Used for yml templates, config files, kubernates deployments, simple HTML pages, etc.

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
 - Unsafe by default, but trivial to use "Safe mode" allowing untrusted execution of a strict set of macro expansions

### Caveats

 - Important to remember that all macros result in "strings", not other python types.
 - When context-oriented template programming gets complex, you probably shouldn't be using templates.
