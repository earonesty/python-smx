To use SmxWsgi:

SMX_INIT=/path/to/my/config.file SMX_ROOT=/path/to/my/html/ gunicorn -w 4 smx:SmxWsgi

* This will serve up files named "index.smx" as directory listings.
* The following macros are availale:
* All cgi env vars are availalbe in %environ() 
* %form(x) returns form input data, or query string
* %jq% contains the json posted dict



