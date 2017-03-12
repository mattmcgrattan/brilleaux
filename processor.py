"""
Module with base classes.

ToDo: look at replacing the urlparse elements in core.py with uritools?
"""

import codecs

import validators

import core  # simple functions like adding or removing headers, etc.


class Headers:
    """
    Class with methods for interacting with dictionaries of
    headers from an HTTP request.

    Inputs:
    header_dictionary: a dictionary of headers


    """

    def __init__(self, header_dictionary):
        """
        Rewrite the headers.

        Inputs:

        header_dictionary: dictionary of headers

        Output:

        A dictionary of headers.

        To Do: put in the appropriate Accept headers, if they don't exist
        or are missing?

        i.e. a request fixer-upper step.
        """
        self.header_dictionary = header_dictionary
        if not isinstance(self.header_dictionary, dict):
            raise TypeError("The headers must be in a dictionary")

    def lowercase(self):
        core.lower_case_keys(self.header_dictionary)

    def encode(self):
        core.encode(self.header_dictionary)

    def header_remove(self, header_name):
        """
        Remove a header.
        """
        core.header_remove(header_name, self.header_dictionary)

    def header_insert(self, header_name, header_value):
        """
        Insert a header.

        N.B. encodes as latin1 (i.e. ISO 8859-1)
        """
        core.header_add(codecs.encode(header_name,
                                      'latin1'),
                        codecs.encode(header_value, 'latin1'),
                        self.header_dictionary)


class RequestURI:
    """
    Update the request URI and the query, etc.

    Can be used to:

    redirect to a different host (as part of the proxy function)
    rewrite the request to change the api syntax etc.

    """

    def __init__(self, uri_string):
        """
        Receive URI as a string.
        Validate that it is a URI
        Convert to dict
        Update or replace one or more of:
            scheme
            host
            port
        Validate the result.
        Return as a string.

        Example:

        http: // 52.209.127.160/simpleAnnotationStore/annotation/search?uri \
        = http % 3A % 2F % 2Fdlcs.io % 2Fiiif-query % 2F4 % 2F % 3Fcanvas % \
        3Dn2 % 26manifest % 3Ds1 % 26sequence % 3Dn1 % 26s1 % 3DM-1011_R-127 \
        % 26n1 % 3D % 26n2 % 3D422 & APIKey = user_auth & media = image & \
        limit = 10000 & _ = 1474020896260

        """
        self.uri_string = uri_string
        if not validators.url(self.uri_string):
            raise ValueError('Not a valid URI')
        self.uri_dict = core.urlizer(self.uri_string)

    def host_update(self, new_host):
        """
        Check the host is a valid domain before updating.
        """
        if not validators.domain(new_host):
            raise ValueError('Not a valid domain')
        else:
            self.uri_dict['host'] = new_host
            if validators.url(core.deurlizer(self.uri_dict)):
                self.uri_string = core.deurlizer(self.uri_dict)
            else:
                raise ValueError('The resulting URI is not valid.')

    def scheme_update(self, new_scheme):
        """
        Update scheme.

        List of valid schemes from https://tools.ietf.org/html/rfc1808
        """
        schemes = ['file', 'ftp', 'gopher', 'hdl', 'http', 'https',
                   'imap', 'mailto', 'mms', 'news', 'nntp', 'prospero',
                   'rsync', 'rtsp', 'rtspu', 'sftp', 'shttp', 'sip', 'sips',
                   'snews', 'svn', 'svn+ssh', 'telnet', 'wais', 'ws', 'wss']
        if new_scheme not in schemes:
            raise ValueError('Not a valid URI scheme')
        else:
            self.uri_dict['scheme'] = new_scheme
            if validators.url(core.deurlizer(self.uri_dict)):
                self.uri_string = core.deurlizer(self.uri_dict)
            else:
                raise ValueError('The resulting URI is not valid.')

    def port_update(self, new_port):
        """
        Validate that if a port number is supplied
        that it is an integer.
        """
        if new_port:
            if not isinstance(new_port, int):
                raise TypeError('Port number must be an integer')
        if new_port == 80 or new_port is None:
            del self.uri_dict['port']
        else:
            self.uri_dict['port'] = new_port
        if validators.url(core.deurlizer(self.uri_dict)):
            self.uri_string = core.deurlizer(self.uri_dict)
        else:
            raise ValueError('The resulting URI is not valid.')

    def path_update(self, new_path):
        """
        Update the URI Path
        """
        self.uri_dict['path'] = new_path
        if validators.url(core.deurlizer(self.uri_dict)):
            self.uri_string = core.deurlizer(self.uri_dict)
        else:
            raise ValueError('The resulting URI is not valid.')

    def query_update(self, new_query):
        """
        Update the URI Query
        """
        self.uri_dict['query'] = new_query
        if validators.url(core.deurlizer(self.uri_dict)):
            self.uri_string = core.deurlizer(self.uri_dict)
        else:
            raise ValueError('The resulting URI is not valid.')
