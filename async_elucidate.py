import asyncio
import hashlib
import logging
from typing import Optional
from urllib.parse import quote_plus

import aiohttp
import requests
from aiohttp import ClientSession, TCPConnector
from elucidate import (
    manifest_from_annotation,
    item_ids,
    read_anno,
    delete_anno,
    annotation_pages,
    transform_annotation,
)


async def fetch_all(urls: list, connector_limit: int = 5) -> asyncio.Future:
    """
    Launch async requests for all web pages in list of urls.

    :param urls: list of URLs to fetch
    :param connector_limit: integer for max parallel connections
    :return results from requests
    """
    tasks = []
    fetch.start_time = dict()  # dictionary of start times for each url
    async with ClientSession(connector=TCPConnector(limit=connector_limit)) as session:
        for url in urls:
            task = asyncio.ensure_future(fetch(url, session))
            tasks.append(task)  # create list of tasks
        results = await asyncio.gather(*tasks)  # gather task responses
        return results


async def fetch(url: str, session: aiohttp.client.ClientSession) -> dict:
    """
    Asynchronously fetch a url, using specified ClientSession.
    """
    async with session.get(url) as response:
        resp = await response.json()
        return resp


def async_items_by_topic(elucidate: str, topic: str, **kwargs) -> dict:
    """
    Asynchronously yield annotations from a query by topic to Elucidate.

    :param elucidate: Elucidate server, e.g. https://elucidate.example.com
    :param topic: URI from body source, e.g. 'https://topics.example.com/people/mary+jones'
    :return: annotation object
    """
    t = quote_plus(topic)
    sample_uri = elucidate + "/annotation/w3c/services/search/body?fields=source,id&value=" + t
    r = requests.get(sample_uri)
    if r.status_code == requests.codes.ok:
        loop = asyncio.get_event_loop()  # event loop
        future = asyncio.ensure_future(
            fetch_all([p for p in annotation_pages(r.json())])
        )  # tasks to do
        pages = loop.run_until_complete(future)  # loop until done
        for page in pages:
            for item in page["items"]:
                yield transform_annotation(
                    item=item,
                    flatten_at_ids=kwargs.get("flatten_ids"),
                    transform_function=kwargs.get("trans_function"),
                )


def async_items_by_target(elucidate: str, target_uri: str, **kwargs) -> dict:
    """
    Asynchronously yield annotations from a query by topic to Elucidate.

    :param elucidate: Elucidate server, e.g. https://elucidate.example.com
    :param target_uri: URI from target source and id, e.g. 'https://manifest.example.com/manifest/1'
    :return: annotation object
    """
    t = quote_plus(target_uri)
    sample_uri = elucidate + "/annotation/w3c/services/search/target?fields=source, id&value=" + t
    r = requests.get(sample_uri)
    if r.status_code == requests.codes.ok:
        loop = asyncio.get_event_loop()  # event loop
        future = asyncio.ensure_future(
            fetch_all([p for p in annotation_pages(r.json())])
        )  # tasks to do
        pages = loop.run_until_complete(future)  # loop until done
        for page in pages:
            for item in page["items"]:
                yield transform_annotation(
                    item=item,
                    flatten_at_ids=kwargs.get("flatten_ids"),
                    transform_function=kwargs.get("trans_function"),
                )


def async_items_by_container(
    elucidate: str,
    container: Optional[str] = None,
    target_uri: Optional[str] = None,
    header_dict: Optional[dict] = None,
    **kwargs
) -> Optional[dict]:
    """
    Asynchronously yield annotations from a query by container to Elucidate.

    Container can be hashed from target URI, or provided

    :param elucidate: Elucidate server, e.g. https://elucidate.example.com
    :param target_uri: URI from target source and id, e.g. 'https://manifest.example.com/manifest/1'
    :param container: container path
    :param header_dict: dict of headers
    :return: annotation object
    """
    if target_uri and not container:
        container = hashlib.md5(target_uri).hexdigest()
    if not container.endswith("/"):
        container += "/"
    if container:
        sample_uri = elucidate + "/annotation/w3c/" + container
        r = requests.get(sample_uri, headers=header_dict)
        if r.status_code == requests.codes.ok:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            future = asyncio.ensure_future(
                fetch_all([p for p in annotation_pages(r.json())])
            )  # tasks to do
            pages = loop.run_until_complete(future)  # loop until done
            for page in pages:
                for item in page["items"]:
                    yield transform_annotation(
                        item=item,
                        flatten_at_ids=kwargs.get("flatten_ids"),
                        transform_function=kwargs.get("trans_function"),
                    )
    else:
        return


def async_manifests_by_topic(elucidate: str, topic: Optional[str] = None) -> Optional[list]:
    """
    Asynchronously fetch the results from a topic query to Elucidate and yield manifest URIs

    N.B. assumption, if passed a string for target, rather than an object,
    that manifest and canvas URI patterns follow old API DLCS/Presley model.

    :param elucidate: URL for Elucidate server, e.g. https://elucidate.example.com
    :param topic:  URL for body source, e.g. https://topics.example.com/people/mary+jones
    :return: manifest URI
    """
    if topic:
        return [manifest_from_annotation(anno) for anno in async_items_by_topic(elucidate, topic)]


def iterative_delete_by_target_async_get(
    target: str, elucidate_base: str, dryrun: bool = True
) -> bool:
    """
    Delete all annotations in a container for a target uri. Works by querying for the
    annotations and then iteratively deleting them one at a time. Not a bulk delete operation
    using Elucidate's bulk APIs.

    N.B. Negative: could be slow, and involve many HTTP requests, Positive: doesn't really matter how big the
    result set is, it won't time out, as handling the annotations one at a time.

    Asynchronous query using the Elucidate search by target API to fetch the list of annotations to delete.

    DELETE is not asychronous, but sequential.

    :param dryrun: if True, will not actually delete, just logs and returns True (for success)
    :param target: target uri
    :param elucidate_base: base URI for Elucidate, e.g. https://elucidate.example.com
    :return: boolean success or fail, True if no errors on _any_ request.
    """
    statuses = []
    anno_items = async_items_by_target(elucidate=elucidate_base, target_uri=target)
    annotations = []
    for item in anno_items:
        annotations.extend([i for i in item_ids(item)])
    anno_uris = list(set(annotations))
    if anno_uris:
        for annotation in anno_uris:
            content, etag = read_anno(annotation)
            s = delete_anno(content["id"], etag, dry_run=dryrun)
            statuses.append(s)
            logging.info("Deleting %s status %s, dry run: %s", content["id"], s, dryrun)
    else:
        logging.warning("No annotations for %s", target)
        return True

    if statuses and all([x == 204 for x in statuses]):
        logging.info("Successfully deleted all annotations for target %s", target)
        return True
    else:
        logging.error("Could not delete all annotations for target %s", target)
        return False


def iiif_iterative_delete_by_manifest_async_get(
    manifest_uri: str, elucidate_uri: str, dry_run: bool = True
) -> bool:
    """
    Delete all annotations for every canvas in a IIIF manifest and for the manifest.

    Uses asynchronous code to parallel get the search results to build the annotation list.

    N.B. does NOT do an async DELETE. Delete is sequential.

    :param dry_run: if True, will not actually delete, just prints URIs
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
                            iterative_delete_by_target_async_get(
                                elucidate_base=elucidate_uri, target=canvas, dryrun=dry_run
                            )
                        )
                else:
                    logging.error("Could not find canvases in manifest %s", manifest_uri)
                    return False
            else:
                logging.error("Manifest %s contained no sequences", manifest_uri)
                return False
            statuses.append(
                iterative_delete_by_target_async_get(
                    elucidate_base=elucidate_uri, target=manifest["@id"], dryrun=dry_run
                )
            )
    else:
        logging.error("Could not GET manifest %s", manifest_uri)
        return False
    return all(statuses)
