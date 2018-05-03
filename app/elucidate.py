import requests
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse, quote_plus, parse_qs
import asyncio
from aiohttp import ClientSession, TCPConnector


async def fetch_all(urls):
    """Launch requests for all web pages."""
    tasks = []
    fetch.start_time = dict()  # dictionary of start times for each url
    async with ClientSession(connector=TCPConnector(limit=5)) as session:
        for url in urls:
            task = asyncio.ensure_future(fetch(url, session))
            tasks.append(task)  # create list of tasks
        results = await asyncio.gather(*tasks)  # gather task responses
        return results


async def fetch(url, session):
    """Fetch a url, using specified ClientSession."""
    async with session.get(url) as response:
        resp = await response.json()
        return resp


def set_query_field(url, field, value, replace=False):
    # Parse out the different parts of the URL.
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
        components.fragment
    )
    return urlunparse(new_components)


def annotation_pages(result):
    if result['total'] > 0:
        last = urlparse(result['last'])
        last_page = parse_qs(last.query)['page'][0]
        for p in range(0, int(last_page) + 1):
            page = set_query_field(result['last'], field='page', value=p, replace=True)
            yield page
    else:
        return


def items_async(fetch_uri):
    r = requests.get(fetch_uri)
    if r.status_code == requests.codes.ok:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        future = asyncio.ensure_future(fetch_all([p for p in annotation_pages(r.json())]))  # tasks to do
        pages = loop.run_until_complete(future)  # loop until done
        for page in pages:
            for item in page['items']:
                yield item
