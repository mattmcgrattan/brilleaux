import json
import flask
from flask_cors import CORS
from functools import reduce
from elucidate import items_async
from urllib.parse import urlparse


def key_get(dictionary, keys, default=None):
    """
    Saves using loads of nested gets or try/except loops.

    :param dictionary: dict
    :param keys: keys to get
    :param default: return this if nothing else
    :return: value
    """
    return reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, keys, dictionary)


def transform_anno(anno, anno_id):
    """
        Takes a result returned from Elucidate in the drafts format for Annotation Studio:

    {
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "id": "https://elucidate-pmc.dlc.services/annotation/w3c/ \
        789b7dc83d1c2bfb5ab733ce205cdb40/220ced61-84a0-47a8-bebc-c73ec417dbe4",
        "type": "Annotation",
        "generator": "/capture-models/generic/linking-outer.json",
        "body": {
        "type": "TextualBody",
        "format": "text/json",
        "value": "{\"id\": \"6cedf19b-468f-46b1-bf8c-9e568c4b8a7a\", \"input\": \
        {\"https://annotation-studio.netlify.com/fields/linking/autocomplete\": \
        {\"label\": \"Audrey Turner (Painter)\", \
        \"url\": \"https://ra-exhibition-pmc.dlc.services//index/exhibitors/T#audrey+turner+%28painter%29\"}}, \
        \"selectors\": {\"https://annotation-studio.netlify.com/fields/linking/autocomplete\": \
        {\"type\": null, \"focused\": false, \"name\": null}}, \"template\": \
        \"/capture-models/generic/linking.json\", \"motivation\": {\"id\": \"http://www.w3.org/ns/oa#tagging\", \
        \"label\": \"oa:tagging\", \"instance\": \"tagging\"}, \"isPublishing\": false, \"isPreviewing\": true, \
        \"selector\": {\"type\": \"madoc:boxdraw\", \"x\": 1174, \"y\": 644, \"width\": 287, \"height\": 51, \
        \"name\": null}, \"fingerprint\": {\"scope\": \"/capture-models/generic/linking-outer.json\", \
        \"path\": [\"/capture-models/generic/linking.json\"], \"identity\": null, \"created\": \
        \"2018-04-30T18:18:03.702Z\", \"lifecycle\": \"DRAFT_LIFECYCLE_NEW\", \"source\": \"elucidate\", \
        \"creator\": \"you\"}}",
        "purpose": "editing"
        },
        "target": "https://presley-pmc.dlc.services/iiif/pmctest02/Vol201/canvas/c44",
        "motivation": "http://www.digirati.com/ns/crowds#drafting"
    }

    and return format required by the PMC/Galway viewer.

    {
            "@id": "https://mattmcgrattan.github.io/Vol208/c22/0",
            "@type": "oa:Annotation",
            "motivation": "oa:linking",
            "on": "https://presley-pmc.dlc.services/iiif/pmctest02/Vol208/canvas/c22#xywh=1110,780,295,51",
            "resource": {
                "@id": "https://chronicle250.com/index/exhibitors/A#andrew+j.+stone+%28painter%29",
                "label": "Andrew J. Stone (Painter)"
            }
        }

    Example manifest:  https://pmc-viewer.netlify.com/pmc-fixture.json

    Example annotation list: https://mattmcgrattan.github.io/Vol208/c2.json

    :param anno:
    :return:
    """
    try:
        values = json.loads(anno['body']['value'])
    except KeyError:
        return None
    else:
        label = key_get(values, keys=['input',
                                      'https://annotation-studio.netlify.com/fields/linking/autocomplete',
                                      'label'])
        url = key_get(values, keys=['input',
                                    'https://annotation-studio.netlify.com/fields/linking/autocomplete',
                                    'url'])
        x = key_get(values, keys=['selector', 'x'])
        y = key_get(values, keys=['selector', 'y'])
        w = key_get(values, keys=['selector', 'width'])
        h = key_get(values, keys=['selector', 'height'])
        xywh = ','.join([str(f) for f in [x, y, w, h]])
        on = anno['target'] + '#' + xywh
        result = {'@id': anno_id, '@type': 'oa:Annotation', 'motivation': 'oa:linking', 'on': on,
                  'resource': {'@id': url, 'label': label}}
        return result
    finally:
        pass


def transform_results(elucidate_iri, request_uri):
    """
    Package transformed results as an annotation list.
    """
    anno_list = {"@context": "http://iiif.io/api/presentation/2/context.json", "@type": "sc:AnnotationList",
                 "@id": request_uri,
                 'resources': [x for x in transform_annos(elucidate_iri, base=request_uri)]}
    return anno_list


def transform_annos(elucidate_uri, base):
    """
    Asynchronously grab annotations from Elucidate, and return in transformed format.

    :returns Annotations in PMC viewer format.
    """
    annotations = items_async(elucidate_uri)
    for count, annotation in enumerate(annotations):
        yield transform_anno(annotation, anno_id=''.join([base, str(count)]))


app = flask.Flask(__name__)
CORS(app)


@app.route('/annotationlist/<path:anno_container>', methods=['GET'])
def brilleaux(anno_container):
    """
    Flask app.

    Expects an md5 hashed annotation container  as part of the path.

    Montague stores annotations in a container based on the md5 hash of
    the canvas uri.

    Requests the annotation list from Elucidate, using the IIIF context.

    Unpacks the annotation list, and reformats the JSON to be in the
    annotation list format required by the PMC/Galway viewer.

    Returns JSON-LD for an annotation list.

    The @id of the annotation list is set to the request_url.
    """
    if flask.request.method == 'GET':
        anno_server = 'https://elucidate-pmc.dlc.services/annotation/w3c/'
        elucidate = ''.join([anno_server, anno_container])
        flask.Response(elucidate)
        # make sure URL ends in a /
        if elucidate[-1] != '/':
            elucidate += "/"
            fl_req_uri = flask.request.url + "/"
        else:
            fl_req_uri = flask.request.url
        annotationlist = transform_results(elucidate_iri=elucidate,
                                           request_uri=fl_req_uri)
        if annotationlist:
            resp = flask.Response(json.dumps(annotationlist, indent=2),
                                  headers={'Content-Type': 'application/ld+json;charset=UTF-8'})
            return resp
        else:
            flask.abort('404')


if __name__ == "__main__":
    app.run(threaded=True, debug=True, port=3000, host='0.0.0.0')
