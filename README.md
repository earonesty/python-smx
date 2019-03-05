Simple python macro expansion

    example:
      - key : value
      %indent(%include(file_name))
      - other : %iadd(%FROM_ENV%, 1)
      %indent(%python("
import mod
f = open('myfile.in')
f.read()
return(mod.process(f))
     ")
