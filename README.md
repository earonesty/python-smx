### Simple python macro expansion

    example:
      - key : value
      %indent(%include(file_name))
      - other : %iadd(%FROM_ENV%, 1)
      %indent(%python("
    import mod
    f = open('myfile.in')
    f.read()
    output(mod.process(f))
     ")

Allows simple macros to be expanded inline.  

### Including code and files ===

| Macro | Description |
| :---   | :- |
| indent(str) | each line of the indented string is indented at the level where the indent function was called. | 
| include(str) | include the specified file | 
| expand(str) | string is expanded using smx syntax | 
| python(str) | string is expanded using python syntax | 
| module(str) | string is interpreted as a module and imported | 

### Modules

| Macro | Description |
| :---   | :- |
| os.... | os functions are included by default | 
| sys.... | sys functions are included by default | 

### Misc

| Macro | Description |
| :---   | :- |
| add(a, b) | numbers are added | 
| sub(a, b) | numbers are subtracted | 



