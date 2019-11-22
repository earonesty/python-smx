## SmxWsgi module

Simplest way to use the SmxWsgi module:

```
SMX_INIT=/path/to/my/config.file SMX_ROOT=/path/to/my/html/ gunicorn -w 4 smx:wsgi
```

* This will serve up files named "index.smx" as directory listings.
* The following macros are availale:
* All cgi env vars are availalbe in %environ() 
* %form(x) returns form input data, or query string
* %jq(x) contains the json posted dict
* %redirect(url) will redirect
* %redirect(url, 301) will redirect301
* %error(500, msg, body) will throw an error

All smx macros and python are otherwise available.

* .smx pages are always parsed
* .html pages can optionally contain embedded smx, trigger with %expand% at the top of the page. 

