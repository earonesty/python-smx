=== Simple python macro expansion ===

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

=== Macros ===

indent(str) - each line of the indented string is indented at the level where the indent function was called.
include(str) - include  afile

