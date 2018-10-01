import hashlib
import requests
import json
import logging
from typing import Optional, Callable
from urllib.parse import (
    quote_plus,
    urlparse,
    urlunparse,
    urlencode,
    parse_qsl,
    parse_qs,
)


def remove_keys(d, keys):
    return {k: v for k, v in d.items() if k in (set(d.keys()) - set(keys))}


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

def transform_annotation(
    item: dict, flatten_at_ids: bool = True, transform_function: Callable = None
) -> Optional[dict]:
    if transform_function:
        if "body" and "target" in item:
            if flatten_at_ids:  # flatten dicts with @ids to simple key / value
                for k, v in item.items():
                    if "@id" in item[k]:
                        item[k] = item[k]["@id"]
            if isinstance(item["body"], list):
                item["body"] = [transform_function(body) for body in item["body"]]
            elif isinstance(item["body"], dict):
                item["body"] = transform_function(item["body"])
            if isinstance(item["target"], dict):
                    item["on"] = target_extract(item["target"])  # o
            elif isinstance(item["target"], list):
                item["on"] = [target_extract(o) for o in item["target"]][0]  # o_list[0]
            else:
                item["on"] = target_extract(item["target"])
            item = remove_keys(d=item, keys=["generator", "label", "target"])
            return item
        else:
            return
    else:
        return item


def set_query_field(url, field, value, replace=False):
    """
    Parse out the different parts of the URL.

    :param url:
    :param field:
    :param value:
    :param replace:
    :return:
    """
    components = urlparse(url)
    query_pairs = parse_qsl(urlparse(url).query)

    if replace:
        query_pairs = [(f, v) for (f, v) in query_pairs if f != field]
    query_pairs.append((field, value))

    new_query_str = urlencode(query_pairs)

    # Finally, construct the new URL
    new_components = (
        components.scheme,
        components.netloc,
        components.path,
        components.params,
        new_query_str,
        components.fragment,
    )
    return urlunparse(new_components)


def annotation_pages(result: json) -> str:
    """
    Generator for URLs for annotation pages from an Activity Streams paged result set

    :param result: Activity Streams paged result set
    :return: AS page
    """
    if result["total"] > 0:
        last = urlparse(result["last"])
        last_page = parse_qs(last.query)["page"][0]
        for p in range(0, int(last_page) + 1):
            page = set_query_field(result["last"], field="page", value=p, replace=True)
            yield page
    else:
        return


def items_by_topic(elucidate: str, topic: str) -> dict:
    """
    Yield annotations from query to Elucidate by body source.

    :param elucidate: URL for Elucidate server, e.g. https://elucidate.example.com
    :param topic:  URL for body source, e.g. https://topics.example.com/people/mary+jones
    :return: annotation object
    """
    t = quote_plus(topic)
    sample_uri = (
        elucidate + "/annotation/w3c/services/search/body?fields=id,source&value=" + t
    )
    r = requests.get(sample_uri)
    if r.status_code == requests.codes.ok:
        for page in annotation_pages(r.json()):
            items = requests.get(page).json()["items"]
            for item in items:
                yield item


def manifest_from_annotation(content: dict) -> Optional[str]:
    """
    Parse annotation and yield manifest URI

    N.B. assumption, if passed a string for target, rather than an object,
    that manifest and canvas URI patterns follow old API DLCS/Presley model.

    :param content: annotation object
    :return: manifest URI
    """
    if isinstance(content["target"], str):
        # hack that derives the manifest URI from the canvas URI
        # only works for specific URI pattern
        manifest = content["target"].split("canvas")[0] + "manifest"
    else:
        try:
            if isinstance(content["target"]["dcterms:isPartOf"], str):
                manifest = content["target"]["dcterms:isPartOf"]
            else:
                manifest = content["target"]["dcterms:isPartOf"]["id"]
        except TypeError:
            manifest = content["target"][0]["dcterms:isPartOf"]["id"]
        except KeyError:
            # annotations with no dcterms:isPartOf
            manifest = content["target"]["source"]
    return manifest


def manifests_by_topic(elucidate: str, topic: str) -> Optional[str]:
    """
    Parses results from an Elucidate topic search request, and yields manifest URIs.

    N.B. assumption, if passed a string for target, rather than an object,
    that manifest and canvas URI patterns follow old API DLCS/Presley model.

    :param elucidate: URL for Elucidate server, e.g. https://elucidate.example.com
    :param topic:  URL for body source, e.g. https://topics.example.com/people/mary+jones
    :return: manifest URI
    """
    if topic:
        for count, anno in enumerate(items_by_topic(elucidate, topic)):
            m = manifest_from_annotation(anno)
            if m:
                yield m


def bulk_update_topics(
    new_topic_id: str, old_topic_ids: str, elucidate_base: str, dry_run: bool = True
) -> int:
    """
    Use Elucidate's bulk update APIs to replace all instances of the old topic id(s) with the
    new topic id(s)

    :param new_topic_id: topic ids to use, string
    :param old_topic_ids: topic ids to replace, list
    :param elucidate_base: elucidate base URI, e.g. https://elucidate.example.com
    :param dry_run: if True, will simply log JSON and uri and then return a 200
    :return: http POST status code
    """
    bodies = []
    for old_topic_id in old_topic_ids:
        bodies.append(
            {
                "id": old_topic_id,
                "oa:isReplacedBy": new_topic_id,
                "source": {"id": old_topic_id, "oa:isReplacedBy": new_topic_id},
            }
        )
    post_data = json.dumps(
        {"@context": "http://www.w3.org/ns/anno.jsonld", "body": bodies}
    )
    post_uri = elucidate_base + "/annotation/w3c/services/batch/update"
    logging.debug("Posting %s to %s", post_data, post_uri)
    if not dry_run:
        resp = requests.post(
            url=post_uri,
            data=post_data,
            headers={
                "Content-type": 'application/ld+json; profile="http://www.w3.org/ns/anno.jsonld"'
            },
        )
        if resp.status_code != requests.codes.OK:
            logging.error("%s returned %s", post_uri, resp.content)
        return resp.status_code
    else:
        logging.debug("Dry run.")
        return 200


def bulk_delete_topic(topic_id: str, elucidate_base: str, dry_run: bool = True) -> int:
    """
    Use Elucidate's bulk apis to delete all instances of a topic URI.

    :param topic_id: topic id to delete
    :param elucidate_base: elucidate base URI, e.g. https://elucidate.example.com
    :param dry_run: if True, will simply log and then return a 200
    :return: http POST status code
    """
    post_uri = elucidate_base + "/annotation/w3c/services/batch/delete"
    post_data = json.dumps(
        {
            "@context": "http://www.w3.org/ns/anno.jsonld",
            "body": {"id": topic_id, "source": {"id": topic_id}},
        }
    )
    logging.debug("Posting %s to %s", post_data, post_uri)
    if not dry_run:
        resp = requests.post(
            url=post_uri,
            data=post_data,
            headers={
                "Content-type": 'application/ld+json; profile="http://www.w3.org/ns/anno.jsonld"'
            },
        )
        if resp.status_code != requests.codes.OK:
            logging.error("%s returned %s", post_uri, resp.content)
        return resp.status_code
    else:
        logging.debug("Dry run.")
        return 200


def gen_search_by_target_uri(
    target_uri: str, elucidate_base: str, model: str = "w3c", field=None
) -> Optional[str]:
    """
    Returns a search URI for searching Elucidate for a target using Elucidate's basic search API.
    N.B. does not GET this uri or return results.

    :param model: oa or w3c, defaults to w3c.
    :param elucidate_base: base URI for the annotation server, e.g. 'https://elucidate.example.com'
    :param target_uri: target URI to search for, e.g. canvas or manifest URI
    :param field: list of fields to search on, defaults to both source and id
    :return: uri
    """
    if field is None:
        field = ["source", "id"]
    if elucidate_base and target_uri:
        uri = "".join(
            [
                "/".join(
                    [
                        elucidate_base,
                        "annotation",
                        model,
                        "services/search/target?fields=",
                    ]
                ),
                ",".join(field),
                "&value=",
                target_uri,
            ]
        )
        return uri
    else:
        return None


def gen_search_by_container_uri(
    elucidate_base: str, target_uri: str, model: str = "w3c"
) -> Optional[str]:
    """
    Return the annotation container uri for a target. Assuming that the container URI
    is an md5 hash of the target URI (as per current DLCS general practice).
    N.B. does not GET this URI or return results.

    :param elucidate_base:  base URI for the annotation server, e.g. https://elucidate.example.com
    :param target_uri: target URI to search for, e.g. manifest or canvas URI
    :param model: oa or w3c
    :return: uri
    """
    if elucidate_base and target_uri:
        container = hashlib.md5(target_uri).hexdigest()
        uri = "/".join([elucidate_base, "annotation", model, container, ""])
        return uri
    else:
        return None


def get_items(uri: str) -> json:
    """
    Page through ActivityStreams paged results, yielding
    each page's items one at a time.

    :param uri: Request URI
    :return: page-of-items
    """
    while True:
        page_response = requests.get(uri)
        if page_response.status_code != 200:  # end of no results
            return
        j = page_response.json()
        if "first" in j:  # first page of result set
            if "as:items" in j["first"]:
                items = j["first"]["as:items"]["@list"]
            elif "items" in j["first"]:
                items = j["first"]["items"]
            else:
                items = None
        else:  # not first page of result set
            try:
                items = j["items"]
            except KeyError:
                items = None
        if items:
            for item in items:
                yield item
        try:  # try to get the next page (on first page)
            uri = j["first"]["next"]
        except KeyError:  # try to get the next page (on other page)
            uri = j.get("next")
        if uri is None:  # no next page, so end
            break


def item_ids(item: json) -> Optional[str]:
    """
    Yield identifier URI(s) for item from an Activity Streams item.


    :param item: Item from an activity streams page
    :return: uri
    """
    for i in ["@id", "id"]:
        if i in item:
            uri = item[i]
            yield uri


def read_anno(anno_uri: str) -> (Optional[str], Optional[str]):
    """
    Get an annotation from Elucidate, with content and ETag

    :param anno_uri: URI for annotation
    :return: annotation content, etag
    """
    r = requests.get(anno_uri)
    if r.status_code == requests.codes.ok:
        anno = r.json()
        etag = r.headers["ETag"].replace('W/"', "").replace('"', "")
        return anno, etag
    else:
        return None, None


def delete_anno(anno_uri: str, etag: str, dry_run: bool = True) -> int:
    """
    Delete an individual annotation, requires etag.

    :param anno_uri: URI for annotation
    :param etag: ETag
    :param dry_run: if True, log and return a 204
    :return: return http DELETE status code
    """
    header_dict = {
        "If-Match": etag,
        "Accept": 'application/ld+json; profile="http://www.w3.org/ns/anno.jsonld"',
        "Content-Type": 'application/ld+json; profile="http://www.w3.org/ns/anno.jsonld"',
    }
    if not dry_run:
        r = requests.delete(anno_uri, headers=header_dict)
        if r.status_code == 204:
            logging.info("Deleted %s", anno_uri)
        else:
            logging.error(
                "Failed to delete %s server returned %s", anno_uri, r.status_code
            )
        return r.status_code
    else:
        logging.debug("Dry run")
        return 204


def create_container(container_name: str, label: str, elucidate_uri: str) -> int:
    """
    Create an annotation container with a container name and label.

    Will default to Anno Dev server.

    :param container_name: name of the container
    :param label:  label for the container
    :param elucidate_uri:  uri for the annotation server, including full path.
    :return: status code
    """
    container_headers = {
        "Slug": container_name,
        "Content-Type": "application/ld+json",
        "Accept": 'application/ld+json;profile="http://www.w3.org/ns/anno.jsonld"',
    }
    container_dict = {
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "type": "AnnotationCollection",
        "label": label,
    }
    container_body = json.dumps(container_dict)
    container_uri = elucidate_uri + container_name + "/"
    c_get = requests.get(container_uri)
    if c_get.status_code == 200:
        logging.debug("Container already exists at: %s", container_uri)
        return c_get.status_code
    else:
        r = requests.post(elucidate_uri, headers=container_headers, data=container_body)
        if r.status_code in [200, 201]:
            logging.debug("Container created at: %s", container_uri)
        else:
            logging.error(
                "Could not create container at: %s reason: %s",
                container_uri,
                r.status_code,
            )
        return r.status_code


def uri_contract(uri):
    """
    Contract a URI to just the schema, netloc, and path

    for:

        https://example.org/foo#XYWH=0,0,200,200

    return:

        https://example.org/foo

    :param uri:
    :return:
    """
    if uri:
        parsed = urlparse(uri)
        contracted = urlunparse((parsed[0], parsed[1], parsed[2], None, None, None))
        return contracted
    else:
        return None


def identify_target(annotation_content: dict) -> Optional[str]:
    """
    Identify the base level target for an annotation, i.e.

    for:

        https://example.org/foo#XYWH=0,0,200,200

    return:

        https://example.org/foo

    :param annotation_content: annotation dict
    :return: uri
    """
    targets = []
    if "target" in annotation_content:
        if isinstance(annotation_content["target"], str):
            target = uri_contract(annotation_content["target"])
            return target
        elif isinstance(annotation_content["target"], dict):
            targets = list(
                set(
                    [
                        uri_contract(v)
                        for k, v in annotation_content["target"].items()
                        if k in ["id", "@id", "source"]
                    ]
                )
            )
            if targets:
                return targets[0]
        elif isinstance(annotation_content["target"], list):
            targets = []
            for t in annotation_content["target"]:
                targets.extend(
                    list(
                        set(
                            [
                                uri_contract(v)
                                for k, v in t.items()
                                if k in ["id", "@id", "source"]
                            ]
                        )
                    )
                )
        if targets:
            return targets[0]
        else:
            return None
    else:
        return None


def create_anno(
    elucidate_base: str,
    annotation: dict,
    target: str = None,
    container: str = None,
    model: str = "w3c",
) -> int:
    """
    POST an annotation to Elucidate, can be optionally passed a container, if container is None will use the
    MD5 hash of the manifest or canvas target as the container.

    If container_create is True, the POST will create the container if it does not already exist.

    :param elucidate_base: elucidate_base:  base URI for the annotation server, e.g. https://elucidate.example.com
    :param target: the target for the annotation (optional), will attempt to parse anno for target if not present
    :param annotation: Python dict for the annotation
    :param container: container name (optional), will use hash of target uri if not present
    :param model: oa or w3c
    :return: HTTP status code from Elucidate
    """
    if elucidate_base:
        if annotation:
            if (
                not container
            ):  # N.B. assumes all targets in the annotation have the same base URI
                if not target:
                    target = identify_target(annotation)
                    if not target:
                        logging.error(
                            "Could not identify a target to hash for the container"
                        )
                        return 400
                container = hashlib.md5(target).hexdigest()
            elucidate = "/".join([elucidate_base, "annotation", model, ""])
            container_status = create_container(
                container_name=container, elucidate_uri=elucidate, label=target
            )
            if container_status in [200, 201]:
                anno_headers = {
                    "Content-Type": "application/ld+json",
                    "Accept": 'application/ld+json;profile="http://www.w3.org/ns/anno.jsonld"',
                }
                post_uri = "/".join([elucidate_base, "annotation", model, container])
                anno_body = json.dumps(annotation, indent=4, sort_keys=True)
                r = requests.post(post_uri, headers=anno_headers, data=anno_body)
                if r.status_code in [200, 201]:
                    logging.debug("POST annotation at %s", post_uri)
                else:
                    logging.error("Could not POST annotation at %s", post_uri)
                return r.status_code
            else:
                logging.error("No annotation container found")
                return 404
        else:
            logging.error("No annotation body was provided")
            return 400
    else:
        logging.error("No Elucidate URI was provided")
        return 400


def bulk_delete_target(
    target_uri: str, elucidate_uri: str, dry_run: bool = True
) -> int:
    """
    Use Elucidate's bulk delete API to delete everything with a given target.

    :param target_uri: URI to delete
    :param elucidate_uri: URI of the Elucidate server, e.g. https://elucidate.example.com
    :param dry_run: if True, do not actually delete, just log request and return a 200
    :return: status code
    """
    header_dict = {
        "Accept": 'application/ld+json; profile="http://www.w3.org/ns/anno.jsonld"',
        "Content-Type": 'application/ld+json; profile="http://www.w3.org/ns/anno.jsonld"',
    }
    delete_dict = {
        "@context": "http://www.w3.org/ns/anno.jsonld",
        "target": {"id": target_uri, "source": {"id": target_uri}},
    }
    logging.debug(json.dumps(delete_dict, indent=4))
    uri = elucidate_uri + "/annotation/w3c/services/batch/delete"
    if not dry_run:
        r = requests.post(uri, data=json.dumps(delete_dict), headers=header_dict)
        logging.info("Bulk delete target: %s", target_uri)
        logging.info("Bulk delete status: %s", r.status_code)
        if r.status_code != requests.codes.ok:
            logging.warning(r.content)
        return r.status_code
    else:
        return 200


def iterative_delete_by_target(
    target: str,
    elucidate_base: str,
    search_method: str = "container",
    dryrun: bool = True,
) -> bool:
    """
    Delete all annotations in a container for a target uri. Works by querying for the
    annotations and then iteratively deleting them one at a time. Not a bulk delete operation
    using Elucidate's bulk APIs.

    N.B. Negative: could be slow, and involve many HTTP requests, Positive: doesn't really matter how big the
    result set is, it won't time out, as handling the annotations one at a time.

    Can query using the Elucidate search by target API or hash the target URI to get a container.

    :param dryrun: if True, will not actually delete, just logs and returns True (for success)
    :param search_method: 'container' (hash) or 'search' (Elucidate query)
    :param target: target uri
    :param elucidate_base: base URI for Elucidate, e.g. https://elucidate.example.com
    :return: boolean success or fail, True if no errors on _any_ request.
    """
    statuses = []
    if search_method == "container":
        uri = gen_search_by_container_uri(
            elucidate_base=elucidate_base, target_uri=target
        )
    elif search_method == "search":
        uri = gen_search_by_target_uri(target_uri=target, elucidate_base=elucidate_base)
    else:
        uri = None
    if uri:
        anno_items = get_items(uri)
        annotations = []
        for item in anno_items:
            annotations.extend([i for i in item_ids(item)])
        anno_uris = list(set(annotations))
        if anno_uris:
            for annotation in anno_uris:
                content, etag = read_anno(annotation)
                s = delete_anno(content["id"], etag, dry_run=dryrun)
                statuses.append(s)
                logging.info(
                    "Deleting %s status %s, dry run: %s", content["id"], s, dryrun
                )
        else:
            logging.warning("No annotations for %s", uri)
            return True
    else:
        logging.error("Could not generate an Elucidate query for %s", target)
        return False
    if statuses and all([x == 204 for x in statuses]):
        logging.info("Successfully deleted all annotations for target %s", target)
        return True
    else:
        logging.error("Could not delete all annotations for target %s", target)
        return False


def iiif_iterative_delete_by_manifest(
    manifest_uri: str, elucidate_uri: str, method: str = "search", dry_run: bool = True
) -> bool:
    """
    Delete all annotations for every canvas in a IIIF manifest and for the manifest

    :param dry_run: if True, will not actually delete, just prints URIs
    :param method: container (hash) or search (Elucidate query)
    :param manifest_uri: uri for IIIF manifest
    :param elucidate_uri: Elucidate base uri
    :return: boolean success or fail
    """
    statuses = []
    if manifest_uri:
        r = requests.get(manifest_uri)
        if r.status_code == requests.codes.ok:
            manifest = r.json()
            if "sequences" in manifest:
                if "canvases" in manifest["sequences"][0]:
                    canvases = manifest["sequences"][0]["canvases"]
                    canvas_ids = [c["@id"] for c in canvases]
                    for canvas in canvas_ids:
                        statuses.append(
                            iterative_delete_by_target(
                                elucidate_base=elucidate_uri,
                                target=canvas,
                                search_method=method,
                                dryrun=dry_run,
                            )
                        )
                else:
                    logging.error(
                        "Could not find canvases in manifest %s", manifest_uri
                    )
                    return False
            else:
                logging.error("Manifest %s contained no sequences", manifest_uri)
                return False
            statuses.append(
                iterative_delete_by_target(
                    elucidate_base=elucidate_uri,
                    target=manifest["@id"],
                    search_method=method,
                    dryrun=dry_run,
                )
            )
    else:
        logging.error("Could not GET manifest %s", manifest_uri)
        return False
    return all(statuses)


def iiif_bulk_delete_by_manifest(
    manifest_uri: str, elucidate_uri: str, dry_run: bool = True
) -> bool:
    """

    :param manifest_uri:
    :param elucidate_uri:
    :param dry_run:
    :return:
    """
    statuses = []
    if manifest_uri:
        r = requests.get(manifest_uri)
        if r.status_code == requests.codes.ok:
            manifest = r.json()
            if "sequences" in manifest:
                if "canvases" in manifest["sequences"][0]:
                    canvases = manifest["sequences"][0]["canvases"]
                    canvas_ids = [c["@id"] for c in canvases]
                    for canvas in canvas_ids:
                        statuses.append(
                            200
                            == bulk_delete_target(
                                target_uri=canvas,
                                elucidate_uri=elucidate_uri,
                                dry_run=dry_run,
                            )
                        )
                else:
                    logging.error("Manifest %s contained no canvases", manifest_uri)
                    return False
            else:
                logging.error("Manifest %s contained no sequences", manifest_uri)
                return False
            statuses.append(
                200
                == bulk_delete_target(
                    target_uri=manifest_uri,
                    elucidate_uri=elucidate_uri,
                    dry_run=dry_run,
                )
            )
    else:
        logging.error("Could not GET manifest %s", manifest_uri)
        return False
    return all(statuses)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
