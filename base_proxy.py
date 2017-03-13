import json

import flask
import requests
from datetime import timedelta
from flask import make_response, request, current_app
from functools import update_wrapper


def crossdomain(origin=None, methods=None, headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True):
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, str):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, str):
        origin = ', '.join(origin)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator



def repair_results(json_dict, request_uri):
    """
    Takes a result returned from Digirati
    Annotation Server, which does NOT
    display properly using the SimpleAnnotation
    endpoint in Mirador, and makes:

    value = chars

    and turns all oa:hasPurpose into:

    oa:Tag
    """
    anno_list = {"@context": "http://iiif.io/api/presentation/2/context.json", "@type": "sc:AnnotationList",
                 "@id": request_uri,
                 'resources': []}
    for item in json_dict:
        resource = item['resource']
        for res in resource:
            if 'value' in res.keys():
                res['chars'] = res['value']
                del res['value']
            if 'oa:hasPurpose' in res.keys():
                del res['oa:hasPurpose']
                res['@type'] = 'oa:Tag'
        anno_list['resources'].append(item)
    return json.dumps(anno_list, indent=4)


def got_body(json_data, request_uri):
    """
    Checks to see if a paged list is returned.

    If yes, grab the first page in the list,
    get the content.

    Turn the list of items into an annotation result.
    """
    content_dict = json_data
    anno_results = content_dict['first']['as:items']['@list']
    updated = repair_results(anno_results, request_uri)
    return updated  # json.dumps(anno_results[0], indent=2)


app = flask.Flask(__name__)


@app.route('/annotationlist/<path:anno_container>', methods=['GET'])
@crossdomain(origin='*')
def brilleaux(anno_container):
    if flask.request.method == 'GET':
        anno_server = 'https://elucidate.dlcs-ida.org/annotation/w3c/'
        request_uri = ''.join([anno_server, anno_container])
        try:
            r = requests.get(request_uri, headers={
                'Accept': 'Application/ld+json; profile="http://iiif.io/api/presentation/2/context.json"'})
            if r.status_code == requests.codes.ok:
                try:
                    content = got_body(r.json(), flask.request.url)
                    resp = flask.Response(content, headers={'Content-Type': 'application/ld+json;charset=UTF-8'})
                    # resp = json.dumps(r.json(), indent=4, sort_keys=True)
                except:
                    resp = 'Nothing'
            else:
                resp = 'Nothing'
        except:
            # this should 500 and return something informative.
            print('I do not know what went wrong.')
            resp = 'Nothing'
    else:
        resp = 'Nothing'
    return resp
