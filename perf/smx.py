from smx import Smx

ctx = Smx()

def testcmd(f, out):
    with open(f) as fin:
        ctx.expand_io(fin, out)

# each test is name: {command: func, files: named files}

tests = {
    "simple" : {
        "command" : lambda out: testcmd('test', out),
        "files" : {
            "index": """
<html>
<body>
%body%
</body>
</html>
            """,
            "test": """
%define(body,
    %python("
rows = [
            {'name': 'bob', 'age': 24},
            {'name': 'joe', 'age': 24},
]
    ")

    %for(r,%rows%,
        <tr><td>%r(name)<td>%r(age)</tr>
    )
)
%expand(%include(index))
            """,
        },
    }
}
