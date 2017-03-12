import json

from urllib.parse import urlparse


def lower_case_keys(dictionary):
    """
    Convert the keys of the dictionary to lower case,
    e.g. for working with a dictionary of headers.
    """
    return {k.lower(): v for k, v in dictionary.items()}


def prune_keys(dictionary):
    """
    Remove keys with no values.
    """
    for k, v in dictionary.items():
        if not v:
            del dictionary[k]
    return dictionary


def encode(dictionary, encoding='latin1'):
    """
    Convert to encoding.
    """
    d = {}
    for k, v in dictionary.items():
        if isinstance(k, bytes):
            key = k.decode(encoding)
        else:
            key = str(k)
        if isinstance(v, bytes):
            va = v.decode(encoding)
        else:
            va = str(v)
        d[key] = va
    return d


def header_remove(header, dictionary):
    """
    Remove a header.
    """
    if header:
        dictionary.pop(header, None)
    return dictionary


def header_add(header, value, dictionary):
    """
    Add a header.

    Lower cases the header name.
    """
    if header and value:
        dictionary[str(header.lower())] = value
    return dictionary


def urlizer(uri):
    """
    Turn a URL string into a dictionary for
    later editing, parsing, etc.
    """
    source_url = urlparse(uri)
    url_dict = {'scheme': source_url.scheme}
    # print source_url
    if ':' in source_url.netloc:
        url_dict['host'], url_dict['port'] = source_url.netloc.split(':')
    else:
        url_dict['host'] = source_url.netloc
        url_dict['port'] = '80'
    url_dict['path'] = source_url.path
    url_dict['params'] = source_url.params
    url_dict['query'] = source_url.query
    url_dict['fragment'] = source_url.fragment
    return url_dict


def deurlizer(uri_dict):
    """
    Take a dictionary, and return as a string.

    To Do: rewrite in a less crude literal way.
    """
    uri_string = uri_dict['scheme']
    uri_string += '://'
    uri_string += uri_dict['host']
    if 'port' in uri_dict:
        uri_string += ':'
        uri_string += str(uri_dict['port'])
    if 'path' in uri_dict:
        uri_string += uri_dict['path']
    if 'query' in uri_dict:
        uri_string += '?'
        uri_string += uri_dict['query']
    if 'params' in uri_dict:
        uri_string += uri_dict['params']
    if 'fragment' in uri_dict:
        uri_string += uri_dict['fragment']
    return uri_string


def json_dict(json_string):
    """
    JSON -> Dict
    Right now these are simple wrappers, but broken
    out as functions in case we want to do something
    cleverer.
    """
    return json.loads(json_string)


def dict_json(dictionary):
    """
    Dict -> JSON
    Right now these are simple wrappers, but broken
    out as functions in case we want to do something
    cleverer.
    """
    return json.dumps(dictionary)
