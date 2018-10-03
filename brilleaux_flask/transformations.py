from typing import Optional, Callable, Union
from jinja2 import Template
import uuid


def remove_keys(d, keys):
    return {k: v for k, v in d.items() if k in (set(d.keys()) - set(keys))}


def target_extract(
    targets: Union[dict, list], target_format: str = "simple", fake_selector: Optional[str] = None
) -> Optional[Union[list, str, dict]]:
    """
    Extract the target and turn into a simple 'on'
    :param fake_selector: e.g. "xywh=0,0,50,50" to use for selectorless annotations
    :param targets: annotation content as dictionary
    :param target_format: "simple" or "specificresource"
        simple "on" versus on selector with oa:FragmentSelector.
    :return: string for the target URI
    """
    if targets:
        if isinstance(targets, dict):
            targets = [targets]  # cast to a single item list.
        if target_format == "simple":
            if "source" in targets[0]:
                if "selector" in targets[0]:  # i.e. not a whole canvas or whole manifest annotation
                    return "#".join([targets[0]["source"], targets[0]["selector"]["value"]])
                else:  # i.e. whole canvas or whole manifest annotation
                    if fake_selector:
                        return "#".join([targets[0]["source"], fake_selector])
                    else:
                        return targets[0]["source"]
            else:
                return targets[0]
        elif target_format == "specificresource":
            on = []
            for t in targets:
                selector_val = None
                if "source" in t:
                    on_dict = {"@type": "oa:SpecificResource", "full": t["source"]}
                    if "selector" in t:  # i.e. not a whole canvas or whole manifest annotation
                        selector_val = t["selector"]["value"]
                    else:
                        if fake_selector:  # i.e. whole canvas or whole manifest annotation
                            selector_val = (
                                fake_selector
                            )  # use whatever the default fake selector is
                    if selector_val:
                        x, y, w, h = [int(a) for a in selector_val.split("=")[1].split(",")]
                        path = "".join(
                            [
                                "M",
                                str(x),
                                ",",
                                str(y),
                                "h",
                                str(0.5 * w),
                                "v0",
                                "h",
                                str(0.5 * w),
                                "v",
                                str(0.5 * h),
                                "v",
                                str(0.5 * h),
                                "h",
                                str(-0.5 * w),
                                "h",
                                str(-0.5 * w),
                                "v",
                                str(-0.5 * h) + "z",
                            ]
                        )
                        with open("svg_template.html", "r") as template_file:
                            template = Template(template_file.read())
                            on_dict["selector"] = {
                                "@type": "oa:Choice",
                                "default": {"@type": "oa:FragmentSelector", "value": selector_val},
                                "item": {
                                    "@type": "oa:SvgSelector",
                                    "value": Template.render(
                                        template, path_value=path, uuid_val=str(uuid.uuid4())
                                    ),
                                },
                            }
                    on.append(on_dict)
            return on
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
            item["motivation"] = "oa:tagging"
            if isinstance(item["body"], list):
                item["body"] = [transform_function(body) for body in item["body"]]
            elif isinstance(item["body"], dict):
                item["body"] = transform_function(item["body"])
            item["on"] = target_extract(
                targets=item["target"],
                target_format="specificresource",
                fake_selector="xywh=0,0,75,75",
            )
            item["@id"] = item["id"]
            item["@type"] = "oa:Annotation"
            item["resource"] = item["body"]
            item = remove_keys(
                d=item, keys=["generator", "label", "target", "creator", "type", "id", "body"]
            )
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
    Takes a list of annotations and returns as a standard Presentation API 1
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
