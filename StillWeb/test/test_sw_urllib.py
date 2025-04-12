# -*- coding: utf-8 -*-
# test_sw_urllib.py - test cases for sw_urllib.py
# Copyright (C) 2008  Darsey Litzenberger <dlitz@dlitz.net>

import unittest

RFC3986_BASE = "http://a/b/c/d;p?q"
RFC3986_normal_tests = [
    ("g:h",     "g:h"),
    ("g",       "http://a/b/c/g"),
    ("./g",     "http://a/b/c/g"),
    ("g/",      "http://a/b/c/g/"),
    ("/g",      "http://a/g"),
    ("//g",     "http://g"),
    ("?y",      "http://a/b/c/d;p?y"),
    ("g?y",     "http://a/b/c/g?y"),
    ("#s",      "http://a/b/c/d;p?q#s"),
    ("g#s",     "http://a/b/c/g#s"),
    ("g?y#s",   "http://a/b/c/g?y#s"),
    (";x",      "http://a/b/c/;x"),
    ("g;x",     "http://a/b/c/g;x"),
    ("g;x?y#s", "http://a/b/c/g;x?y#s"),
    ("",        "http://a/b/c/d;p?q"),
    (".",       "http://a/b/c/"),
    ("./",      "http://a/b/c/"),
    ("..",      "http://a/b/"),
    ("../",     "http://a/b/"),
    ("../g",    "http://a/b/g"),
    ("../..",   "http://a/"),
    ("../../",  "http://a/"),
    ("../../g", "http://a/g"),
]
RFC3986_abnormal_tests = [
    ("../../../g",      "http://a/g"),
    ("../../../../g",   "http://a/g"),
    ("/./g",            "http://a/g"),
    ("/../g",           "http://a/g"),
    ("g.",              "http://a/b/c/g."),
    (".g",              "http://a/b/c/.g"),
    ("g..",             "http://a/b/c/g.."),
    ("..g",             "http://a/b/c/..g"),
    ("./../g",          "http://a/b/g"),
    ("./g/.",           "http://a/b/c/g/"),
    ("g/./h",           "http://a/b/c/g/h"),
    ("g/../h",          "http://a/b/c/h"),
    ("g;x=1/./y",       "http://a/b/c/g;x=1/y"),
    ("g;x=1/../y",      "http://a/b/c/y"),
    ("g?y/./x",         "http://a/b/c/g?y/./x"),
    ("g?y/../x",        "http://a/b/c/g?y/../x"),
    ("g#s/./x",         "http://a/b/c/g#s/./x"),
    ("g#s/../x",        "http://a/b/c/g#s/../x"),
    ("http:g",          "http://a/b/c/g"),  # or "http:g"
]

class Test_rfc3986_urljoin(unittest.TestCase):
    pass

def _init_test_urljoin():
    for i in range(len(RFC3986_normal_tests)):
        def f(self, i=i):
            from StillWeb.sw_urllib import rfc3986_urljoin
            self.assertEqual(RFC3986_normal_tests[i][1], rfc3986_urljoin(RFC3986_BASE, RFC3986_normal_tests[i][0]))
        f.__doc__ = """RFC 3986 5.4.1. Normal Examples (%r)""" % (RFC3986_normal_tests[i][0],)
        setattr(Test_rfc3986_urljoin, "test_rfc3986_541_normal_%02d" % i, f)

    for i in range(len(RFC3986_abnormal_tests)):
        def f(self, i=i):
            from StillWeb.sw_urllib import rfc3986_urljoin
            self.assertEqual(RFC3986_abnormal_tests[i][1], rfc3986_urljoin(RFC3986_BASE, RFC3986_abnormal_tests[i][0]))
        f.__doc__ = """RFC 3986 5.4.2. Abormal Examples (%r)""" % (RFC3986_abnormal_tests[i][0],)
        setattr(Test_rfc3986_urljoin, "test_rfc3986_542_abnormal_%02d" % i, f)

_init_test_urljoin()

class OtherTests(unittest.TestCase):
    def test_remove_dot_segments(self):
        """remove_dot_segments"""
        from StillWeb.sw_urllib import remove_dot_segments

        # Relative URLs
        self.assertEqual("", remove_dot_segments("./"))
        self.assertEqual("", remove_dot_segments("../"))
        self.assertEqual("a", remove_dot_segments("a"))
        self.assertEqual("a/b/", remove_dot_segments("a/b/"))
        self.assertEqual("a/b/", remove_dot_segments("a/b/./"))
        self.assertEqual("a/b/", remove_dot_segments("a/b/."))
        self.assertEqual("a/b/c", remove_dot_segments("a/b/./c"))
        self.assertEqual("a/b/c/", remove_dot_segments("a/b/./c/"))
        self.assertEqual("a/c/", remove_dot_segments("a/b/../c/"))
        self.assertEqual("a/c/", remove_dot_segments("a/b//../c/"))
        self.assertEqual("a/", remove_dot_segments("a/b/../"))
        self.assertEqual("a/?a=b#foo", remove_dot_segments("a/b/../?a=b#foo"))

        # Relative URLs ending in "." or ".."
        # FIXME: Do we really want the trailing slash on the result?
        self.assertEqual("", remove_dot_segments("."))
        self.assertEqual("", remove_dot_segments(".."))
        self.assertEqual("a/", remove_dot_segments("a/b/.."))
        self.assertEqual("a/b/", remove_dot_segments("a/b/."))

        # Absolute URLs
        self.assertEqual("http://a", remove_dot_segments("http://a"))
        self.assertEqual("http://a/b/c", remove_dot_segments("http://a/b/c"))
        self.assertEqual("http://a/b/", remove_dot_segments("http://a/b/c/../"))
        self.assertEqual("http://a/c/", remove_dot_segments("http://a/../c/"))
        self.assertEqual("http://a/c/", remove_dot_segments("http://a/../c/./"))

        # Absolute URLs ending in "." or ".."
        # FIXME: Do we really want the trailing slash on the result?
        self.assertEqual("http://a/", remove_dot_segments("http://a/."))
        self.assertEqual("http://a/", remove_dot_segments("http://a/b/.."))
        self.assertEqual("http://a/b/", remove_dot_segments("http://a/b/."))

    def test_relative_url(self):
        """relative_url"""
        from StillWeb.sw_urllib import relative_url

        # Basic tests
        self.assertEqual("http://xyz",      relative_url("http://xyz",      "http://a/b/c/"))
        self.assertEqual("http://xyz/b/c/", relative_url("http://xyz/b/c/", "http://a/b/c/"))
        self.assertEqual("../",             relative_url("http://a/b/",     "http://a/b/c/"))
        self.assertEqual("../d",            relative_url("http://a/b/d",    "http://a/b/c/"))
        self.assertEqual("../d/",           relative_url("http://a/b/d/",   "http://a/b/c/"))
        self.assertEqual("../../e/f/gee.html",  relative_url("http://a/e/f/gee.html",   "http://a/b/c/dee.html"))
        self.assertEqual("../../e/f.html",      relative_url("http://a/e/f.html",       "http://a/b/c/dee.html"))

        # Test allow_empty
        self.assertEqual("", relative_url("http://a/b/c/", "http://a/b/c/", allow_empty=True))

        # Test allow_net
        self.assertEqual("//xyz/b/c/", relative_url("http://xyz/b/c/", "http://a/b/c/", allow_net=True))

        # Relative input URLs
        self.assertEqual("./", relative_url("./", "http://a/b/c/"))
        self.assertEqual("../", relative_url("../", "http://a/b/c/"))
        self.assertEqual("./", relative_url("foo/../", "http://a/b/c/"))

    def test_rebase_url(self):
        """rebase_url"""
        from StillWeb.sw_urllib import rebase_url

        # Simple rebasing
        self.assertEqual("http://a/new/b/c", rebase_url(url="http://a/b/c", src="http://a/", dest="http://a/new/"))
        self.assertEqual("http://a/new/b/c", rebase_url("http://a/old/b/c", "http://a/old/", "http://a/new/"))

        # When the URL can't be rebased
        self.assertEqual("http://xyz/foo", rebase_url("http://xyz/foo", "http://a/old/", "http://a/new/"))
        self.assertEqual("http://a/foo", rebase_url("/foo", "http://a/bar/", "http://xyz/new/"))
        self.assertRaises(ValueError, rebase_url, "/foo", "http://a/bar/", "http://xyz/new/", must_rebase=True)

if __name__ == '__main__':
    unittest.main()


# vim:set ts=4 sw=4 sts=4 expandtab:
