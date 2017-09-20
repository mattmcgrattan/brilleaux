import json
import brilleaux_settings
import flask
import requests
from datetime import timedelta
from flask import make_response, request, current_app
from functools import update_wrapper
from flask_cache import Cache


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

    :rtype: string (Serialized JSON)
    """
    anno_list = {"@context": "http://iiif.io/api/presentation/2/context.json", "@type": "sc:AnnotationList",
                 "@id": request_uri,
                 'resources': []}

    if len(json_dict) > 0:
        for item in json_dict:
            # ignore target-less annotations.
            if 'resource' in item and 'on' in item:
                resource = item['resource']
                for res in resource:
                    # ignore resources that are not dicts with keys
                    # if isinstance(res, dict):
                    if 'value' in res.keys():
                        # IIIF Annotations use chars,
                        # not value.
                        res['chars'] = res['value']
                        del res['value']
                    if 'oa:hasPurpose' in res.keys():
                        # IIIF Annotations don't use Purpose
                        del res['oa:hasPurpose']
                        res['@type'] = 'oa:Tag'
                if isinstance(item['on'], dict):
                    item['on'] = target_extract(item['on'])  # o
                else:
                    # o_list = [target_extract(o) for o in item['on']]
                    # print('Item on:', item['on'])
                    # print('Type:', type(item['on']))
                    if isinstance(item['on'], list):
                        item['on'] = [target_extract(o) for o in item['on']][0]  # o_list[0]
                print(item)
                anno_list['resources'].append(item)
        return json.dumps(anno_list, indent=4)
    else:
        return None


def target_extract(json_dict):
    """
    Extract the target and turn into a simple 'on'
    :param json_dict:
    :return:
    """
    return '#'.join([json_dict['full'], json_dict['selector']['value']])


def got_body(json_data, request_uri):
    """
    Checks to see if a paged list is returned.

    If yes, grab the first page in the list,
    get the content.

    Turn the list of items into an annotation result.
    """
    content_dict = json_data
    if ('first' in content_dict and 'as:items' in content_dict['first']
            and '@list' in content_dict['first']['as:items']):
        anno_results = content_dict['first']['as:items']['@list']
        updated = repair_results(anno_results, request_uri)
        if updated:
            return updated
        else:
            return None
    else:
        return None


app = flask.Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'filesystem', 'CACHE_DIR': './'})


@app.route('/annotationlist/<path:anno_container>', methods=['GET'])
@crossdomain(origin='*')
@cache.cached(timeout=20)  # 20 second caching.
def brilleaux(anno_container):
    """
    Flask app.

    Expects an md5 hashed annotation container  as part of the path.

    Montague stores annotations in a container based on the md5 hash of
    the canvas uri.

    Requests the annotation list from Elucidate, using the IIIF context.

    Unpacks the annotation list, and reformats the JSON to be in the
    IIIF Presentation API annotation list format.

    Returns JSON-LD for an annotation list.

    The @id of the annotation list is set to the request_url.
    """
    if flask.request.method == 'GET':
        # e.g. anno_server = 'https://elucidate.dlcs-ida.org/annotation/w3c/'
        if brilleaux_settings.ELUCIDATE_URI:
            anno_server = brilleaux_settings.ELUCIDATE_URI
        else:
            anno_server = 'https://elucidate.dlcs-ida.org/annotation/w3c/'
        request_uri = ''.join([anno_server, anno_container])
        # make sure URL ends in a /
        if request_uri[-1] != '/':
            request_uri += "/"
            fl_req_uri = flask.request.url + "/"
        else:
            fl_req_uri = flask.request.url
        r = requests.get(request_uri, headers={
            'Accept': 'Application/ld+json; profile="http://iiif.io/api/presentation/2/context.json"'})
        print('Request URI')
        print(request_uri)
        print("Elucidate Status Code")
        print(r.status_code)
        if r.status_code == requests.codes.ok:
            if r.json():
                print(r.json())
                # noinspection PyBroadException
                try:
                    content = got_body(r.json(), fl_req_uri)
                except:
                    flask.abort(500)
                    content = None
                if content:
                    resp = flask.Response(content, headers={'Content-Type': 'application/ld+json;charset=UTF-8'})
                    return resp
                else:
                    flask.abort(500)
            else:
                flask.abort(404)
        else:
            flask.abort(r.status_code)
    else:
        flask.abort(405)


if __name__ == "__main__":
    app.run(threaded=True, debug=True, port=5000, host='0.0.0.0')
