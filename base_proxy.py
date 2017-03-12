import flask
import requests
import elucidate

app = flask.Flask(__name__)

@app.route('/annotationlist/<path:anno_container>', methods=['GET'])
def brilleaux(anno_container):
    if flask.request.method == 'GET':
        anno_server = 'https://annotation-dev.digtest.co.uk:443/annotation/w3c/'
        request_uri = ''.join([anno_server, anno_container])
        try:
            r = requests.get(request_uri,headers={'Accept': 'Application/ld+json; profile="http://iiif.io/api/presentation/2/context.json"'})
            if r.status_code == requests.codes.ok:
                try:
                    content = elucidate.got_body(r.json())
                    resp = content
            else:
                resp = 'Nothing'
        except:
            # this should 500 and return something informative.
            print('I do not know what went wrong.')
            resp = 'Nothing'
            # e.g.
            # content = None
            # headers = dest_headers
            # status_code = "500"
            # reason = "Application error retrieving annotations."
    else:
        resp = 'Nothing'
    return resp
