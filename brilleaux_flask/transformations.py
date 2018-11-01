from typing import Optional, Callable


def remove_keys(d, keys):
    return {k: v for k, v in d.items() if k in (set(d.keys()) - set(keys))}


def target_extract(json_dict: dict, fake_selector: bool = False) -> Optional[str]:
    """
    Extract the target and turn into a simple 'on'.

    Optionally, fake a selector (e.g. for whole canvas annotations)

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
    """
    Transform an annotation given an arbitrary
    function that is passed in. Assumes W3C to OA as the basic model.

    :param item: annotation
    :param flatten_at_ids: if True replace @id dict with simple "@id" : "foo"
    :param transform_function: function to pass the annotation through
    :return:
    """
    if transform_function:
        if "body" and "target" in item:
            if flatten_at_ids:  # flatten dicts with @ids to simple key / value
                for k, v in item.items():
                    if "@id" in item[k]:
                        item[k] = item[k]["@id"]
            item["motivation"] = "oa:tagging"  # force motivation to tagging
            if isinstance(item["body"], list):  # transform each anno body (in list of bodies)
                item["body"] = [transform_function(body) for body in item["body"]]
            elif isinstance(item["body"], dict):  # transform single anno (if not a list)
                item["body"] = transform_function(item["body"])
            if isinstance(item["target"], dict):  # replace the target with a simple 'on'
                item["on"] = target_extract(item["target"])  # o
            elif isinstance(item["target"], list):
                item["on"] = [target_extract(o) for o in item["target"]][0]  # o_list[0]
            else:
                item["on"] = target_extract(item["target"])
            item["@id"] = item["id"]
            item["@type"] = "oa:Annotation"
            item["resource"] = item["body"]
            item = remove_keys(
                d=item, keys=["generator", "label", "target", "creator", "type", "id", "body"]
            )  # remove unused keys
            return item
        else:
            return
    else:
        return item


def mirador_oa(w3c_body: dict) -> dict:
    """
    Transform a single W3C Web Annotation Body (e.g. as produced by Montague) and returns
    formatted for Mirador.

    :param w3c_body: annotation body
    :return: transformed annotation body
    """
    new_body = {}
    if "source" in w3c_body.keys():
        new_body["chars"] = '<a href="' + w3c_body["source"] + '">' + w3c_body["source"] + "</a>"
        new_body["format"] = "application/html"
    if "value" in w3c_body.keys():
        new_body["@type"] = "oa:Tag"
        new_body["chars"] = w3c_body["value"]
    new_body = remove_keys(new_body, ["value", "type", "generator", "source", "purpose"])
    return new_body


def format_results(annotation_list: list, request_uri: str) -> Optional[dict]:
    """
    Takes a list of annotations and returns as a standard Presentation API
    Annotation List.

    :param annotation_list: list of annotations
    :param request_uri: the URI to use for the @id
    :return dict or None
    """
    if annotation_list:
        anno_list = {
            "@context": "http://iiif.io/api/presentation/2/context.json",
            "@type": "sc:AnnotationList",
            "@id": request_uri,
            "resources": annotation_list,
        }
        return anno_list
    else:
        return None
