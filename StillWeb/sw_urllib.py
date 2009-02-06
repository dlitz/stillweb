# -*- coding: utf-8 -*-
# sw_urllib.py - StillWeb URL library; supplements urllib.parse
# Copyright (C) 2008  Dwayne C. Litzenberger <dlitz@dlitz.net>

import urllib.parse

def remove_dot_segments(url):
    """Remove "." and ".." segments from an URL.

    This function works with both absolute and relative URLs.

    This function removes double slashes (empty path segments) from the path
    part of an URL.
    """

    (scheme, netloc, path, params, query, fragment) = urllib.parse.urlparse(url)

    # Strip leading and trailing slash(es) and split into path segments
    path_segments = path.strip("/").split("/")

    # Strip "." and "" segments and resolve ".." segments.
    i = len(path_segments)-1
    to_remove = 0
    while path_segments and i >= 0:
        seg = path_segments[i]
        if seg == "":   # double-slash or leading/trailing slash
            del path_segments[i]
        elif seg == ".":
            del path_segments[i]
        elif seg == "..":
            del path_segments[i]
            to_remove += 1
        elif to_remove:
            del path_segments[i]
            to_remove -= 1
        i -= 1

    # Restore leading slash, if present.
    if path.startswith("/"):
        path_segments.insert(0, '')

    # Restore trailing slash, if present.  (Also treat /. and /.. as trailing a slash.)
    if path.endswith("/") or path.endswith("/.") or path.endswith("/.."):
        path_segments.append('')

    # Reassemble the path
    path = "/".join(path_segments)

    # Return the reassembled URL
    return urllib.parse.urlunparse((scheme, netloc, path, params, query, fragment))


def rfc3986_urljoin(base, url, allow_fragments=True):
    """RFC 3986 compliant urljoin() function"""
    # Join the URLs using Python's URL joiner
    joined_url = urllib.parse.urljoin(base, url, allow_fragments)

    # Remove dot segments so we don't return stuff like http://a/../../c
    joined_url = remove_dot_segments(joined_url)

    # Return the result
    return joined_url


def relative_url(url, base_url, allow_empty=False, allow_net=False):
    """Return the relative representation of the given `url`, using `base_url`
    as a starting point.

    Unless `allow_empty` is set, zero-length relative URIs (which indicate the
    "current document") are never returned.

    Unless `allow_net` is set, network URIs (e.g. "//www.example.com/foo") are
    never returned.
    """

    # Make the target URL an absolute URL
    url = rfc3986_urljoin(base_url, url)

    # Parse the target URL
    (t_scheme, t_netloc, t_path, t_params, t_query, t_fragment) = urllib.parse.urlparse(url)

    # Parse the base URL
    (b_scheme, b_netloc, b_path, b_params, b_query, b_fragment) = urllib.parse.urlparse(base_url)

    for dummy in [0]:   # Run once
        # scheme
        if t_scheme != b_scheme:
            break
        if allow_net:
            t_scheme = ''

        # netloc
        if t_netloc != b_netloc:
            break
        t_scheme = ''
        t_netloc = ''

        # Path
        if t_path == b_path:
            # Take just the basename of the path
            p = t_path.split("/")
            if allow_empty:
                t_path = ''
            else:
                if not p or not p[-1]:
                    t_path = "./"
                else:
                    t_path = p[-1]

            # query
            if t_query != b_query:
                break
            t_query = ''

            # fragment
            if t_fragment != b_fragment:
                break
            t_fragment = ''
            break

        # Relative path calculation algorithm:
        # We have two paths, the target path (where we want to go) and the base
        # path (where we are coming from).  We need to:
        # 1. Find the deepest common parent between the two paths
        # 2. Determine how many instances of "../" we need to get from the base
        #    path to the common parent.
        # 3. Determine the relative path of the target with respect to the
        #    common parent, and append this to the "../" sequence.

        # Break down the path
        tp = t_path.split("/")   # target path
        bp = b_path.split("/")  # base path

        # Determine the tree depth of each of the paths
        tp_depth = len(tp)-1
        bp_depth = len(bp)-1

        # 1. Find the depth of the deepest common parent (DCP) path, noting
        # that the final path element is not a directory.
        n = min(len(tp), len(bp))
        dcp_depth = 0
        for i in range(1, n):
            if tp[i] != bp[i]:
                break
            dcp_depth = i

        # 2. Determine the number of "../"s needed to get from the base path to
        # the DCP path.
        go_up = bp_depth - dcp_depth - 1
        if go_up > 0:
            relpath = "../" * go_up
        else:
            relpath = ""

        # 3. Determine the relative path of the destination with respect to the
        # DCP path, and add it.
        relpath += "/".join(tp[dcp_depth+1:])

        if not relpath:
            relpath = "./"

        t_path = relpath

    return urllib.parse.urlunparse((t_scheme, t_netloc, t_path, t_params, t_query, t_fragment))

def rebase_url(url, src, dest, must_rebase=False):
    """Re-base an URL.

    If `url` is in `src`, then make it point to the same place under `dest`.

    This function raises ValueError if `url` cannot be rebased and `must_rebase` is true.
    """

    # Convert the target URL into an absolute URL (removing dot segments, e.g. "." and "..")
    t_url = rfc3986_urljoin(src, url)

    # Convert the target URL into a relative URL
    r_url = relative_url(t_url, src)

    # Parse the relative URL
    (r_scheme, r_netloc, r_path, r_params, r_query, r_fragment) = urllib.parse.urlparse(r_url)

    # Check if the relative URL is actually relative
    if r_scheme or r_netloc or r_path.startswith("../"):
        # We have an absolute URL.  Therefore the URL can't be rebased.
        if must_rebase:
            raise ValueError("Couldn't rebase URL")
        return t_url

    return rfc3986_urljoin(dest, r_url)

# vim:set ts=4 sw=4 sts=4 expandtab:
