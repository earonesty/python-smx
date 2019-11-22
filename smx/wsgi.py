import io
import os
import json
import traceback
import logging
from urllib.parse import parse_qs
from .smx import Smx
from .memoize import memoize

log = logging.getLogger(__name__)


def parse_query_string(content):
    info = parse_qs(content)
    for k in info:
        if len(info[k]) == 1 and type(info[k]) is list:
            info[k] = info[k][0]        # type:ignore
    return info


class Writer:
    def write(self, s) -> None:
        pass


class HttpError(Exception):
    def __init__(self, code: int, msg: str, body: str = None):
        self.code = int(code)
        self.msg = msg
        self.body = body


class RedirectError(HttpError):
    def __init__(self, path: str, code=302):
        self.path = path
        if code == 301:
            msg = "Moved Permanently"
        else:
            msg = "Moved Temporarily"
        super().__init__(code, msg, "")


CHUNK = 1024*1024


def throw(err):
    raise err


class SmxWsgi:
    def __init__(self, root=None, init=None):
        if not root:
            root = os.environ.get("SMX_ROOT")
        if not init:
            init = os.environ.get("SMX_INIT")

        self.__detect = {".html", ".htm"}
        self.__expand = {".htx", ".smx"}

        self.root = root
        self.ctx = Smx()
        if init:
            fp = os.path.join(self.root, init)
            with open(fp) as f:
                self.ctx.expand_io(f, Writer())

        self._init  = False

    @memoize
    def is_script(self, path):
        _, ext = os.path.splitext(path)

        if ext in self.__detect:
            with open(path) as f:
                x = f.read(32)
                return "%expand%" in x
        return ext in self.__expand

    def static_resp(self, start_response, path):
        content_type = "text/plain"
        content_length = None

        headers = []
        headers.append(('Content-Type', content_type))
        if content_length is not None:
            headers.append(('Content-Length', str(content_length)))

        with open(path, 'rb') as f:
            x = f.read(CHUNK)
            start_response('200 OK', headers)
            while x:
                log.debug("YIELD")
                yield x
                x = f.read(CHUNK)

    @memoize
    def find_index(self, dir):
        for f in ["index.smx", "index.html", "index.htm"]:
            p = os.path.join(dir, f)
            if os.path.exists(p):
                return p
        return p

    def __call__(self, env, start_response):

        if not self._init:
            os.chdir(self.root)
            self._init = True

        try:
            url = env.get('SCRIPT_NAME')
            if not url:
                url = env.get('PATH_INFO', '/')

            log.debug('%s', url)

            url.replace("..", ".")

            if url == "/":
                full_path = self.root
            else:
                full_path = os.path.join(self.root, url.lstrip("/"))

            if os.path.isdir(full_path):
                full_path = self.find_index(full_path)

            try:
                if not self.is_script(full_path):
                    log.debug("STATIC %s", url)
                    yield from self.static_resp(start_response, full_path)
                    return

                log.debug("SCRIPT %s", url)

                content = b"{}"
                length = env.get("CONTENT_LENGTH", 0)
                content_type = env.get('CONTENT_TYPE', "")
                info = {}
                jq = {}
                if length:
                    content = env['wsgi.input'].read(int(length))
                if content_type.startswith('application/x-www-form-urlencoded'):
                    info = parse_query_string(content)
                elif content_type.startswith('application/json'):
                    if content:
                        try:
                            jq = json.loads(content)
                        except Exception:
                            raise HttpError(400, "Invalid JSON " + str(content, "utf-8"))
                    else:
                        jq = {}
                # elif ... handle more stuff

                query = env.get('QUERY_STRING')

                if query:
                    params = parse_query_string(query)
                else:
                    params = {}

                info.update(params)

                # todo:
                #   we process the first MAX_MEM_SIZE bytes for status codes & errors
                #   if the file is larger than that
                #   we STREAM the results

                ctx = Smx(self.ctx, environ=env)

                headers = {}

                ctx.set("form", lambda k: info.get(k))
                ctx.set("jq", jq)
                ctx.set("header", headers)
                ctx.set("error", lambda k, m=None, b=None: throw(HttpError(k, m, b)))
                ctx.set("redirect", lambda k: throw(RedirectError(k)))

                fo = io.StringIO()
                with open(full_path) as fi:
                    ctx.expand_io(fi, fo)

                response = fo.getvalue().encode("utf8")
                headers.update({'Content-Type': content_type,
                                "Content-Length": str(len(response))})
                start_response('200 OK', [(k, v) for k, v in headers.items()])
                yield bytes(fo.getvalue(), "utf8")
            except ConnectionAbortedError as e:
                log.error("GET %s : ERROR : %s", url, e)
            except HttpError:
                raise
            except FileNotFoundError as e:
                raise HttpError(404, type(e).__name__ + " : " + str(e))
            except Exception as e:
                raise HttpError(500, type(e).__name__ + " : " + str(e), traceback.format_exc())
        except HttpError as e:
            try:
                response = e.body

                if response is None:
                    response = "<h1>%s %s</h1><p>An error was encountered processing your request</p>" % (e.code, e.msg or "Error")

                headers = [('Content-Type', 'text/html'), ("Content-Length", str(len(response)))]
                if isinstance(e, RedirectError):
                    headers.append(('Location', e.path))
                    response = ""
                else:
                    log.error("GET %s : ERROR : %s", url, e)

                start_response(str(e.code) + ' ' + e.msg, headers)
                yield bytes(response, "utf-8")
            except ConnectionAbortedError as e:
                log.error("GET %s : ERROR : %s", url, e)
        except Exception:
            log.exception("Internal Error")
            start_response("500 Internal Error", [])
            yield bytes(traceback.format_exc(), "utf8")


if __name__ == "__main__":
    main()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Start dev server')
    parser.add_argument('--debug', "-d", help='set logging level debug', action="store_true")
    parser.add_argument('--root', "-r", required=True, action="store", help='document root')
    parser.add_argument('--init', "-i", default=None, action="store", help='context init')
    parser.add_argument('--port', "-p", type=int, default=8123, help='listen port')
    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(format='%(asctime)s %(levelname)-5.5s [%(name)s:%(lineno)s][%(threadName)s] %(message)s')
        log.setLevel(logging.DEBUG)

    from wsgiref.simple_server import make_server
    httpd = make_server('', args.port, SmxWsgi(args.root, args.init))
    print("Serving on port %s..." % args.port)
    httpd.serve_forever()


def app_fixture(test_env=False, with_init=None):
    # doing this because pytest fixtures seem hard to add optional params to

    import tempfile, shutil, wsgiref, wsgiref.util
    root = os.path.join(tempfile.gettempdir(), "smx-tests." + os.urandom(32).hex())
    os.mkdir(root)
    if with_init:
        init = os.path.join(root, os.urandom(16).hex()) 
        with open(init, "w") as f:
            f.write(with_init)
        os.environ["SMX_INIT"] = init

    if test_env:
        os.environ["SMX_ROOT"] = root
        app = SmxWsgi()
    else:
        app = SmxWsgi(root)

    def req(url, post=b'', type=""):
        temp = io.BytesIO(post)
        qs = ""
        split = url.split('?')
        if len(split) == 2:
            url, qs = split
        environ = {
                'PATH_INFO': url,
                'QUERY_STRING': qs,
                'REQUEST_METHOD': 'POST' if post else 'GET',
                'CONTENT_LENGTH': len(post),
                'CONTENT_TYPE': type,
                'wsgi.input': temp,
                }

        class resp:
            code = None
            head = None
            data = None

        resp = resp()

        def start_resp(code, head):
            resp.code = int(code.split(" ")[0])
            resp.head = dict(head)

        wsgiref.util.setup_testing_defaults(environ)
        out = b''
        log.debug(environ)
        for ret in app(environ, start_resp):
            assert resp.code
            out += ret
        resp.data = out
        return resp

    def create(path, data=b''):
        if type(data) is str:
            data = bytes(data, "utf8")
        fp = os.path.join(root, path.lstrip("/"))
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "wb") as f:
            f.write(data)

    app.req = req
    app.create = create
    app.__del__ = lambda: shutil.rmtree(root)

    return app

def test_basic():
    app = app_fixture()
    app.create("hi.smx", "%add(1,1)")
    res = app.req("/hi.smx")
    assert res.data == b'2'

def test_redirect():
    app = app_fixture()
    app.create("hi.smx", "%redirect(/yo)")
    res = app.req("/hi.smx")
    assert res.data == b''
    assert res.code == 302
    assert res.head.get("Location") == "/yo"

def test_error():
    app = app_fixture()
    app.create("hi.smx", "%notavar%")
    res = app.req("/hi.smx")
    assert b'Traceback' in res.data
    assert res.code == 500

def test_qs():
    app = app_fixture(test_env=True)
    app.create("hi.smx", "%add(%form(x),1)")
    res = app.req("/hi.smx?x=4")
    assert b'5' == res.data
    assert res.code == 200

def test_static():
    app = app_fixture(test_env=True)
    app.create("hi.txt", "%add(1,1)")
    res = app.req("/hi.txt")
    assert b'%add(1,1)' == res.data
    assert res.code == 200


def test_init():
    app = app_fixture(with_init='%set(foo, 44)')
    app.create("hi.smx", "%add(2,%foo%)")
    res = app.req("/hi.smx")
    assert b'46' == res.data
    assert res.code == 200

def test_index():
    app = app_fixture(test_env=True)
    app.create("index.smx", "%add(1,1)")
    res = app.req("/")
    assert b'2' == res.data
    assert res.code == 200

def test_post_jq():
    app = app_fixture(test_env=True)
    app.create("index.smx", "%add(%jq(x),1)")
    res = app.req("/", post=b'{"x":4}', type="application/json")
    assert b'5' == res.data
    assert res.code == 200

def test_post_badjq():
    app = app_fixture(test_env=True)
    app.create("index.smx", "%add(%jq(x),1)")
    res = app.req("/", post=b'"x":4}', type="application/json")
    assert res.code == 400

def test_404():
    app = app_fixture(test_env=True)
    res = app.req("/")
    assert res.code == 404

def test_500():
    app = app_fixture(test_env=True)
    app.create("index.smx", "%addsdfsfd%")
    res = app.req("/")
    assert res.code == 500

def test_include():
    app = app_fixture(test_env=True)
    app.create("other", "xxx")
    app.create("index.smx", "yyy%include(other)")
    res = app.req("/")
    assert res.data == b'yyyxxx'


def test_main():
    import threading

    app = app_fixture(test_env=True)
    app.create("index.smx", "%add(44,44)")

    import sys
    sys.argv = ["smx", "-r", app.root, '-p' '8001']

    t = threading.Thread(target=main, daemon=True)
    import requests
    t.start()
    import time
    t = time.monotonic() + 1
    while time.monotonic() < t:
        try:
            assert requests.get("http://127.0.0.1:8001").text == "88"
        except requests.ConnectionError:
            continue


