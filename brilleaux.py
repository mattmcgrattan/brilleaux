import json
import brilleaux_settings
import flask
import os
from flask_caching import Cache
from flask_cors import CORS
import logging
import sys
from typing import Optional
from async_elucidate import async_items_by_container
from transformations import format_results, mirador_oa


def get_local_context(filename, remove_prefixes: Optional[tuple] = None) -> Optional[dict]:
    """
    Load a JSON-LD context, and optionally remove some unrequired prefixes.

    :param filename: json file
    :param remove_prefixes: tuple of prefixes to delete
    :return: dict object
    """
    site_root = os.path.realpath(os.path.dirname(__file__))
    context = json.load(open(os.path.join(site_root, filename)))
    if context:
        if remove_prefixes:  # delete optional list (tuple) of prefixes from the context.
            for prefix in remove_prefixes:
                try:
                    del context["@context"][prefix]
                except KeyError:
                    pass
        return context
    else:
        return


app = flask.Flask(__name__)
# app.config["context"] = get_local_context(
#     filename="context.json", remove_prefixes=("dct", "dcterm", "sdo", "sorg")
# )
# app.config["iiif_context"] = get_local_context(filename="iiif_context.json")
CORS(app)
cache = Cache(app, config={"CACHE_TYPE": "filesystem", "CACHE_DIR": "./", "CACHE_THRESHOLD": 500})


@app.route("/annotationlist/<path:anno_container>", methods=["GET"])
@cache.cached(timeout=120)  # Cache Flask request to save repeated hits to Elucidate.
def brilleaux(anno_container: str):
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
    if brilleaux_settings.ELUCIDATE_URI:
        anno_server = brilleaux_settings.ELUCIDATE_URI.replace("annotation/w3c/", "")
    else:
        anno_server = "https://elucidate.dlcs-ida.org/"
    if flask.request.method == "GET":
        request_uri = flask.request.url
        # make sure URL ends in a /
        if request_uri[-1] != "/":
            request_uri += "/"
        annotations = async_items_by_container(
            elucidate=anno_server,
            container=anno_container,
            header_dict={
                "Accept": "Application/ld+json; profile=" + '"http://www.w3.org/ns/anno.jsonld"'
            },
            flatten_ids=True,
            trans_function=mirador_oa,
        )
        content = format_results(list(annotations), request_uri=request_uri)
        if content:
            resp = flask.Response(
                json.dumps(content, sort_keys=True, indent=4),
                headers={"Content-Type": "application/ld+json;charset=UTF-8"},
            )
            return resp
        else:
            flask.abort(404)
    else:
        logging.error("Brilleaux does not support this method.")
        flask.abort(405)


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.DEBUG,
        format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
    )
    app.run(threaded=True, debug=True, port=5000, host="0.0.0.0")
