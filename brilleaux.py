import json
import brilleaux_settings
import flask
from pyld import jsonld
import os
from flask_caching import Cache
from flask_cors import CORS
import logging
import sys
from typing import Optional
from async_elucidate import async_items_by_container


def remove_keys(d, keys):
    return {k: v for k, v in d.items() if k in (set(d.keys()) - set(keys))}


def to_rdfa(resource: dict, con_txt: dict, rdfa: bool = True) -> str:
    if "@type" in resource:
        if resource["@type"] == "dctypes:Dataset":
            # print(type(resource['value']))
            expanded = jsonld.expand(json.loads(resource["value"]))[0]
            expanded["@context"] = con_txt
            e = jsonld.expand(expanded)
            rows = []
            for f in e:
                for k, v in f.items():
                    i = jsonld.compact({k: [x for x in v]}, ctx=con_txt)
                    del (i["@context"])
                    if rdfa:
                        row = "".join(
                            [
                                '<p><strong><a href="',
                                str(k),
                                '">',
                                str([z for z, _ in i.items()][0]).split(":")[1].title(),
                                '</a></strong>: <span property="',
                                str(k),
                                '">',
                                str("; ".join([t["@value"] for t in v])),
                                "</span></p>",
                            ]
                        )
                        rows.append(row)
                    else:
                        row = "".join(
                            [
                                str([z for z, _ in i.items()][0]),
                                ": ",
                                str("; ".join([t["@value"] for t in v])),
                                ";<br>",
                            ]
                        )
                        rows.append(row)
            return "".join(rows)


def repair_results(json_dict: list, request_uri: str, cont: dict) -> Optional[str]:
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
    anno_list = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@type": "sc:AnnotationList",
        "@id": request_uri,
        "resources": [],
    }
    if json_dict:
        for item in json_dict:
            # ignore target-less annotations.
            if "body" in item:
                resource = item["body"]
                # convert motivations to Mirador format.
                if "motivation" in item:
                    if "@id" in item["motivation"]:
                        item["motivation"] = item["motivation"]["@id"]
                if "target" in item:
                    if isinstance(resource, list):
                        new = []
                        for res in resource:
                            if isinstance(res, dict):
                                res["@type"] = "oa:Tag"
                                if "source" in res.keys():
                                    res["chars"] = (
                                        '<a href="'
                                        + res["source"]
                                        + '">'
                                        + res["source"]
                                        + "</a>"
                                    )
                                if "value" in res.keys():
                                    if "@type" in res:
                                        if res["@type"] == "dctypes:Dataset":
                                            res = {
                                                "chars": to_rdfa(
                                                    res, con_txt=cont, rdfa=True
                                                ),
                                                "format": "application/html",
                                            }
                                        else:
                                            res["chars"] = res["value"]
                                    else:
                                        res["chars"] = res["value"]
                                new.append(remove_keys(d=res, keys=["value", "type", "generator",
                                                                    "source", "purpose"]))
                        if isinstance(item["target"], dict):
                            item["on"] = target_extract(item["target"])  # o
                        elif isinstance(item["target"], list):
                            item["on"] = [target_extract(o) for o in item["target"]][0]  # o_list[0]
                        else:
                            item["on"] = target_extract(item["target"])
                        item["body"] = new
                    else:
                        if "@type" in resource:
                            if resource["@type"] == "dctypes:Dataset":
                                item["resource"] = [
                                    {
                                        "chars": to_rdfa(
                                            resource, con_txt=cont, rdfa=True
                                        ),
                                        "format": "application/html",
                                    }
                                ]
                                item["on"] = target_extract(
                                    item["target"], fake_selector=True
                                )
                item = remove_keys(d=item, keys=["generator", "label", "target"])
                if "on" in item:
                    anno_list["resources"].append(item)
                else:
                    pass
        return json.dumps(anno_list, indent=4)
    else:
        return None


def target_extract(json_dict: dict, fake_selector: bool = False) -> Optional[str]:
    """
    Extract the target and turn into a simple 'on'
    :param fake_selector: if True, create a top left 50px box and associate with that.
    :param json_dict: annotation content as dictionary
    :return: string for the target URI
    """
    if "source" in json_dict:
        if "selector" in json_dict:
            return "#".join([json_dict["source"], json_dict["selector"]["value"]])
        else:
            if fake_selector:
                return "#".join([json_dict["source"], "xywh=0,0,50,50"])
            else:
                return json_dict["source"]
    else:
        if fake_selector:
            return "#".join([json_dict, "xywh=0,0,50,50"])
        else:
            return


def got_body(json_data: dict, request_uri: str, context: dict) -> Optional[str]:
    """
    Checks to see if a paged list is returned.

    If yes, grab the first page in the list,
    get the content.

    Turn the list of items into an annotation result.
    """
    content_dict = json_data
    if (
        "first" in content_dict
        and "as:items" in content_dict["first"]
        and "@list" in content_dict["first"]["as:items"]
    ):
        anno_results = content_dict["first"]["as:items"]["@list"]
        updated = repair_results(anno_results, request_uri, cont=context)
        if updated:
            return updated
        else:
            return None
    else:
        return None


def get_local_context(prefixes: tuple = ("dct", "dcterm", "sdo", "sorg")) -> dict:
    site_root = os.path.realpath(os.path.dirname(__file__))
    context = json.load(open(os.path.join(site_root, "context.json")))
    for prefix in prefixes:
        try:
            del context["@context"][prefix]
        except KeyError:
            pass
    return context


def get_iiif_context() -> dict:
    site_root = os.path.realpath(os.path.dirname(__file__))
    context = json.load(open(os.path.join(site_root, "iiif_context.json")))
    return context


app = flask.Flask(__name__)
app.config["context"] = get_local_context()
app.config["iiif_context"] = get_iiif_context()
CORS(app)
cache = Cache(
    app, config={"CACHE_TYPE": "filesystem", "CACHE_DIR": "./", "CACHE_THRESHOLD": 500}
)


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
        anno_server = brilleaux_settings.ELUCIDATE_URI
    else:
        anno_server = "https://elucidate.dlcs-ida.org/"
    if flask.request.method == "GET":
        request_uri = "".join([anno_server, "annotation/w3c/", anno_container])
        # make sure URL ends in a /
        if request_uri[-1] != "/":
            request_uri += "/"
        annotations = async_items_by_container(
            elucidate=anno_server,
            container=anno_container,
            header_dict={
                "Accept": "Application/ld+json; profile="
                + '"http://www.w3.org/ns/anno.jsonld"'
            },
        )
        content = repair_results(
            list(annotations), request_uri=request_uri, cont=app.config["context"]
        )
        if content:
            resp = flask.Response(
                content, headers={"Content-Type": "application/ld+json;charset=UTF-8"}
            )
            return resp
        else:
            flask.abort(404)
        # logging.debug("Request URI: %s", request_uri)
        # logging.debug("Elucidate Status Code: %s", r.status_code)
        # if r.status_code == requests.codes.ok:
        #     if r.json():
        #         content = None
        #         # noinspection PyBroadException
        #         try:
        #             content = got_body(
        #                 r.json(), fl_req_uri, context=app.config["context"]
        #             )
        #         except:
        #             logging.error("Could not parse the JSON")
        #             flask.abort(500)
        #         if content:
        #             resp = flask.Response(
        #                 content,
        #                 headers={"Content-Type": "application/ld+json;charset=UTF-8"},
        #             )
        #             return resp
        #         else:
        #             flask.abort(500)
    #         else:
    #             logging.error("No usable data returned from Elucidate")
    #             flask.abort(404)
    #     else:
    #         logging.error("Elucidate returned an error. Status code: %s", r.status_code)
    #         flask.abort(r.status_code)
    # else:
    #     logging.error("Brilleaux does not support this method.")
    #     flask.abort(405)


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.DEBUG,
        format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
    )
    app.run(threaded=True, debug=True, port=5000, host="0.0.0.0")
