# -*- coding: utf-8 -*-
# TeXPlugin.py - TeX (texvc) plugin for StillWeb
# Copyright (C) 2008  Dwayne C. Litzenberger <dlitz@dlitz.net>

from StillWeb.Placeholders import ReplaceWithHTML, ReplaceWithNode, ReplaceWithNothing, PLACEHOLDERS_NAMESPACE
from StillWeb.sw_util import getChildText, TypicalPaths, ensure_path
from StillWeb.sw_urllib import rfc3986_urljoin

import os
import errno
import tempfile
import subprocess
import hashlib
import pickle
import urllib
import binascii
from xml.dom import minidom

class TexvcResultParseError(ValueError):
    pass

class TexvcCodeParseError(ValueError):
    pass

class TexvcRuntimeError(RuntimeError):
    pass

class TexvcError(Exception):
    def __init__(self, code, message, *extra_args):
        super().__init__(code, message, *extra_args)
        self.code = code
        self.message = message
        self.extra_args = extra_args


class Texvc(object):

    def __init__(self, program_dir, output_dir):
        self.program_dir = program_dir
        self.output_dir = output_dir
        self.temp_dir = None

    def create_temp_dir(self):
        assert self.temp_dir is None
        self.temp_dir = tempfile.mkdtemp(prefix="TeXPlugin-")

    def cleanup_temp_dir(self):
        if self.temp_dir is not None:
            # Recursively delete the contents of the temporary directory
            # (doesn't appear to be needed much)
            for (root_dir, dirs, files) in os.walk(self.temp_dir, topdown=False):
                for basename in files:
                    p = os.path.join(root_dir, basename)
                    print("TeXPlugin warning: deleting %r" % (p,))
                    os.unlink(p)
                for basename in dirs:
                    p = os.path.join(root_dir, basename)
                    print("TeXPlugin warning: deleting directory %r" % (p,))
                    os.rmdir(p)

            # Remove the temporary directory itself
            os.rmdir(self.temp_dir)

    def hash_code(self, latex_code):
        """Feed the given LaTeX code through texvc_tex and return a digest object"""
        texvc_tex_cmd = os.path.join(self.program_dir, "texvc_tex")
        if "\0" in latex_code:
            raise TexvcCodeParseError("NUL not allowed in TeX code")
        if not latex_code:
            raise TexvcCodeParseError("TeX code passed to hash_code must not be empty")
        args = [texvc_tex_cmd, latex_code.encode('UTF-8'), b'UTF-8']
        proc = subprocess.Popen(args, executable=texvc_tex_cmd, stdout=subprocess.PIPE)
        retval = proc.communicate()[0]
        if proc.returncode != 0:
            raise TexvcRuntimeError("texvc_tex failed with return code %r" % (proc.returncode,))
        if not retval:  # if we give texvc_tex garbage, it seems to output nothing
            raise TexvcCodeParseError("texvc_tex could not parse TeX code: %r" % (latex_code,))
        return hashlib.md5(retval)

    def run_texvc(self, latex_code):
        self.create_temp_dir()
        try:
            # Build argument list -- we use "ascii" encoding here, since we
            # really want raw binary directory names, but Python 3 (beta 3)
            # doesn't support that very well.
            texvc_cmd_path = os.path.join(self.program_dir, "texvc")
            args = [
                texvc_cmd_path.encode('ascii'),
                self.temp_dir.encode('ascii'),
                self.output_dir.encode('ascii'),
                latex_code.encode('UTF-8'),
                b"UTF-8"]

            # Invoke texvc, collect result, and check return code
            proc = subprocess.Popen(args, executable=texvc_cmd_path, stdout=subprocess.PIPE)
            raw_result = proc.communicate()[0].decode('UTF-8')
            if proc.returncode != 0:
                raise TexvcRuntimeError("%r failed with return code %r" % (texvc_cmd_path, proc.returncode,))

            # Parse texvc result and check for errors
            return self.parse_result(raw_result)

        finally:
            self.cleanup_temp_dir()

    @staticmethod
    def parse_result(input):
        """Parse output from texvc"""
        if not input:
            raise TexvcResultParseError("texvc parse error: empty output")
        rv = {'code': None, 'md5': None, 'html': None, 'html_strictness': None, 'mathml': None}
        code = rv['code'] = input[0]

        if code == "S":
            raise TexvcError(code, "syntax error")
        elif code == "E":
            raise TexvcError(code, "lexing error")
        elif code == "F":
            raise TexvcError(code, "unknown function %r" % (input[1:],), input[1:])
        elif code == '-':
            raise TexvcError(code, "error")
        elif code not in "+cmlCMLX":
            raise TexvcResultParseError("texvc parse error: unrecognized output: %r" % (input,))

        # Success
        assert code in "+cmlCMLX"
        rv['md5'] = input[1:33]

        if code in "lmc":
            rv['html'] = input[33:]
            rv['html_strictness'] = "lmc".index(code)
        elif code == "X":
            rv['mathml'] = input[33:]
        elif code in "LMC":
            (rv['html'], rv['mathml']) = input[33:].split("\0", 1)
            rv['html_strictness'] = "LMC".index(code)
        return rv



class TeXPlugin:
    def __init__(self, framework):
        self._framework = framework

        # Register the placeholder namespace
        ph_plugin = self._framework.plugins['StillWeb.Placeholders']
        ph_plugin.register_callback(self._handle_math_element, PLACEHOLDERS_NAMESPACE, 'math')
        ph_plugin.register_callback(self._handle_math_element, PLACEHOLDERS_NAMESPACE, 'm')

    def cleanup(self):
        if self._framework is not None:
            self._framework = None

    #
    # Namespace callback(s)
    #
    def _handle_math_element(self, page_generator, element):
        self.math_placeholder(getChildText(element), force_img=(element.getAttribute('force') == 'img'))

    #
    # Exported API (so other plugins can generate TeX code before passing it
    # to this function)
    #
    def math_placeholder(self, latex_code, force_img=False):
        # Strip whitespace
        latex_code = latex_code.strip()

        # If the code is empty, don't do anything.
        if not latex_code:
            raise ReplaceWithNothing()

        # Find the texvc executable
        texvc_program_dir = self._framework.plugins['vars'].vars['texvc_program_dir']

        # Find the output directory
        (output_dir_url, output_dir) = self._get_texvc_outdir()
        intermediate_dir = self._get_my_intermediate_dir()

        # Quietly make sure both directories exist
        ensure_path(output_dir)
        ensure_path(intermediate_dir)

        # Create a Texvc instance
        texvc = Texvc(texvc_program_dir, output_dir)

        # Two MD5 sums are calculated:
        #   1. The "original" checksum of the code actually found in the page
        #   2. The "canonical" checksum that texvc generates
        # These might be identical, or they might be different.  We cache them both.
        orig_md5 = hashlib.md5(latex_code.encode('UTF-8')).hexdigest()
        orig_md5_filename = os.path.join(intermediate_dir, "texvc-original-%s-sum" % (orig_md5,))

        # Try to read the canonical MD5 sum from the cache file.  Generate it if it's not cached.
        try:
            f = open(orig_md5_filename, "rt")
            canonical_md5 = binascii.b2a_hex(binascii.a2b_hex(f.read().strip().encode('ascii'))).decode('ascii')    # make sure it's hexadecimal
            assert len(canonical_md5) == 32     # 32 hexadecimal digits
            f.close()
        except EnvironmentError as exc:
            if exc.errno != errno.ENOENT:
                raise

            # Generate the MD5 sum of the *canonical* code (i.e. of texvc_tex's output)
            canonical_md5 = texvc.hash_code(latex_code).hexdigest()

            # Cache the generated MD5 sum for future reference
            f = open(orig_md5_filename, "wt", encoding="UTF-8")
            f.write(canonical_md5)
            f.close()

        # Check if we've already generated the output
        stamp_filename = os.path.join(intermediate_dir, "texvc-canonical-%s-stamp" % (canonical_md5,))
        result_filename = os.path.join(intermediate_dir, "texvc-canonical-%s-result" % (canonical_md5,))
        output_basename = "%s.png" % (canonical_md5,)
        output_filename = os.path.join(output_dir, output_basename)
        output_url = rfc3986_urljoin(output_dir_url, output_basename)
        if os.path.exists(stamp_filename) and os.path.exists(output_filename):
            print("skipping TeX %s" % (output_filename,))

            # Use the cached result
            result = pickle.load(open(result_filename, "rb"))

            # Check the hash result - this should never fail unless the cache file is corrupt
            if result['md5'] != canonical_md5:
                raise AssertionError("corrupt file: %r" % (result_filename,))

        else:
            print("generating TeX %s" % (output_filename,))

            # Parse texvc result and check for errors
            result = texvc.run_texvc(latex_code)

            # Check the hash result - our caching here breaks if we get this wrong.
            if result['md5'] != canonical_md5:
                raise AssertionError("texvc md5 sum mismatch (code=%r, my_md5=%r, texvc_md5=%r)" % (
                    latex_code, canonical_md5, result['md5']))

            # Check that the output file was created
            if not os.path.exists(output_filename):
                raise TexvcRuntimeError("texvc didn't create output file %r (canonical_md5=%r, code=%r)" % (output_filename, canonical_md5, latex_code))

            # Save the result for future use
            pickle.dump(result, open(result_filename, "wb"))

            # Write the canonical MD5 sum to the timestamp file (and update its timestamp)
            open(stamp_filename, "ab").close()
            os.utime(stamp_filename, None)     # should be unnecessary if we're writing to the file

        # If texvc gave us some HTML code (of moderate or conservative strictness), use that.
        if not force_img and result['html'] is not None and result['html_strictness'] > 0:
            raise ReplaceWithHTML(result['html'])

        # TODO - MathML support can go here if we want it.

        # Fall-back on the PNG image.
        imgElement = minidom.parseString("<img/>").documentElement
        imgElement.setAttribute('class', 'tex')
        imgElement.setAttribute('src', output_url)
        imgElement.setAttribute('alt', latex_code)
        raise ReplaceWithNode(imgElement)

    #
    # Internal functions
    #
    def _get_texvc_outdir(self):
        outdir_url = self._framework.plugins['vars'].vars['texvc_outdir_url']

        # Make sure there is a trailing slash after outdir_url
        (u_scheme, u_netloc, u_path, u_params, u_query, u_fragment) = urllib.parse.urlparse(outdir_url)
        u_path = u_path.rstrip("/") + "/"
        outdir_url = urllib.parse.urlunparse((u_scheme, u_netloc, u_path, u_params, u_query, u_fragment))

        # Figure out the absolute path to the directory
        out_tp = TypicalPaths(self._framework, outdir_url)
        outdir_path = out_tp.output_filename

        return (outdir_url, outdir_path)

    def _get_my_intermediate_dir(self):
        im_dir = os.path.join(self._framework.plugins['vars'].vars['intermediate_data_dir'], "StillWeb.TeXPlugin")
        return os.path.realpath(im_dir)

def create_plugin(framework):
    return TeXPlugin(framework)

# vim:set ts=4 sw=4 sts=4 expandtab:
