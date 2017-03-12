import flask
import requests
import json


def repair_results(json_dict):
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
            anno_list['resources'].append(res)
    return json.dumps(anno_list, indent=4)


def got_body(json_data):
    """
    Checks to see if a paged list is returned.

    If yes, grab the first page in the list,
    get the content.

    Turn the list of items into an annotation result.
    """
    content_dict = json_data
    anno_results = content_dict['first']['as:items']['@list']
    updated = repair_results(anno_results)
    return updated


app = flask.Flask(__name__)


@app.route('/annotationlist/<path:anno_container>', methods=['GET'])
def brilleaux(anno_container):
    if flask.request.method == 'GET':
        anno_server = 'https://annotation-dev.digtest.co.uk:443/annotation/w3c/'
        request_uri = ''.join([anno_server, anno_container])
        try:
            r = requests.get(request_uri, headers={
                'Accept': 'Application/ld+json; profile="http://iiif.io/api/presentation/2/context.json"'})
            if r.status_code == requests.codes.ok:
                try:
                    content = got_body(r.json())
                    resp = content
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
