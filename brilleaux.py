import json
import brilleaux_settings
import flask
import requests
from pyld import jsonld
import os
from flask_caching import Cache
from flask_cors import CORS
import logging
import sys
from typing import Optional


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


def repair_results(json_dict: dict, request_uri: str, cont: dict) -> Optional[str]:
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

    if len(json_dict) > 0:
        for item in json_dict:
            # ignore target-less annotations.
            if "resource" in item:
                resource = item["resource"]
                # convert motivations to Mirador format.
                if "motivation" in item:
                    # del(item['motivation'])
                    if "@id" in item["motivation"]:
                        item["motivation"] = item["motivation"]["@id"]
                if "as:generator" in item:
                    del (item["as:generator"])
                if "label" in item:
                    del (item["label"])
                if "on" in item:
                    if isinstance(resource, list):
                        for res in resource:
                            if isinstance(res, dict):

                                if "oa:hasPurpose" in res.keys():
                                    # IIIF Annotations don't use Purpose
                                    del res["oa:hasPurpose"]
                                    res["@type"] = "oa:Tag"
                                if "full" in res.keys():
                                    res["chars"] = (
                                        '<a href="'
                                        + res["full"]
                                        + '">'
                                        + res["full"]
                                        + "</a>"
                                    )
                                    del (res["full"])
                                    del (res["@type"])
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
                                    del res["value"]
                        if isinstance(item["on"], dict):
                            item["on"] = target_extract(item["on"])  # o
                        elif isinstance(item["on"], list):
                            item["on"] = [target_extract(o) for o in item["on"]][
                                0
                            ]  # o_list[0]
                        else:
                            item["on"] = target_extract(item["on"])
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
                                    item["on"], fake_selector=True
                                )
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
    :param fake_selector:
    :param json_dict:
    :return:
    """
    if "full" in json_dict:
        if "selector" in json_dict:
            return "#".join([json_dict["full"], json_dict["selector"]["value"]])
        else:
            if fake_selector:
                return "#".join([json_dict["full"], "xywh=0,0,50,50"])
            else:
                return json_dict["full"]
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


app = flask.Flask(__name__)
CORS(app)
cache = Cache(app, config={"CACHE_TYPE": "filesystem", "CACHE_DIR": "./"})


@app.route("/annotationlist/<path:anno_container>", methods=["GET"])
@cache.cached(timeout=120)  # 20 second caching.
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
    site_root = os.path.realpath(os.path.dirname(__file__))
    master_context = json.load(open(os.path.join(site_root, "context.json")))
    del (
        master_context["@context"]["dct"]
    )  # remove unwanted alternative dcterms 'dct' prefix
    del (
        master_context["@context"]["dcterm"]
    )  # unwanted alternative dcterms 'dcterm' prefix
    del (master_context["@context"]["sdo"])  # unwanted alternative schema.org prefix
    del (master_context["@context"]["sorg"]) # unwanted alternative schema.org prefix
    if flask.request.method == "GET":
        if brilleaux_settings.ELUCIDATE_URI:
            anno_server = brilleaux_settings.ELUCIDATE_URI
        else:
            anno_server = "https://elucidate.dlcs-ida.org/annotation/w3c/"
        request_uri = "".join([anno_server, anno_container])
        # make sure URL ends in a /
        if request_uri[-1] != "/":
            request_uri += "/"
            fl_req_uri = flask.request.url + "/"
        else:
            fl_req_uri = flask.request.url
        r = requests.get(
            request_uri,
            headers={
                "Accept": "Application/ld+json; profile="
                + '"http://iiif.io/api/presentation/2/context.json"'
            },
        )
        logging.debug("Request URI: %s", request_uri)
        logging.debug("Elucidate Status Code: %s", r.status_code)
        if r.status_code == requests.codes.ok:
            if r.json():
                content = None
                logging.debug("Elucidate response: %s", r.json())
                # noinspection PyBroadException
                try:
                    content = got_body(r.json(), fl_req_uri, context=master_context)
                except:
                    logging.error("Could not parse the JSON")
                    flask.abort(500)
                if content:
                    resp = flask.Response(
                        content,
                        headers={"Content-Type": "application/ld+json;charset=UTF-8"},
                    )
                    return resp
                else:
                    flask.abort(500)
            else:
                logging.error("No usable data returned from Elucidate")
                flask.abort(404)
        else:
            logging.error("Elucidate returned an error.")
            flask.abort(r.status_code)
    else:
        logging.error("Brilleaux does not support this method.")
        flask.abort(405)


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.ERROR,
        format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
    )
    app.run(threaded=True, debug=True, port=5000, host="0.0.0.0")
