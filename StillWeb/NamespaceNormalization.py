# -*- coding: utf-8 -*-
# NamespaceNormalization.py - DOM XML namespace normalization
# Copyright (C) 2008  Dwayne C. Litzenberger <dlitz@dlitz.net>

from xml.dom import XMLNS_NAMESPACE, EMPTY_NAMESPACE

from StillWeb.sw_util import getAttributeNodes

class NamespaceScope:
    def __init__(self, namespace_declarations=None):
        self._prefixes = {None: EMPTY_NAMESPACE}     # map prefix -> namespace
        self._namespaces = {EMPTY_NAMESPACE: None}   # map namespace -> most-recently-merged-prefix
        if namespace_declarations is not None:
            if hasattr(namespace_declarations, '_prefixes') and hasattr(namespace_declarations, '_namespaces'):
                self._prefixes.update(namespace_declarations._prefixes)
                self._namespaces.update(namespace_declarations._namespaces)
            else:
                self.update(namespace_declarations)

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self._prefixes)

    def copy(self):
        obj = self.__class__()
        obj._prefixes = self._prefixes.copy()
        obj._namespaces = self._namespaces.copy()
        return obj

    def update(self, namespace_declarations):
        # Merge the parent and new prefixes.  Return a list of prefixes that
        # were already present.
        duplicate_prefixes = []
        for (prefix, namespace) in namespace_declarations.items():
            if prefix in self and self[prefix] == namespace:
                duplicate_prefixes.append(prefix)
            self[prefix] = namespace
        return duplicate_prefixes

    def get(self, prefix, default=None):
        return self._prefixes.get(prefix, default)

    def __contains__(self, prefix):
        return self.has_prefix(prefix)

    def __getitem__(self, prefix):
        return self._prefixes[prefix]

    def __setitem__(self, prefix, namespace):
        assert prefix is None or isinstance(prefix, str)
        assert namespace == EMPTY_NAMESPACE or isinstance(namespace, str)
        self._prefixes[prefix] = namespace
        self._namespaces[namespace] = prefix

    def prefix_from_namespace(self, namespace):
        return self._namespaces[namespace]

    def has_prefix(self, prefix):
        return prefix in self._prefixes

    def has_namespace(self, namespaceURI):
        return namespaceURI in self._namespaces

    def items(self):
        return self._prefixes.copy().items()

def get_namespace_declarations(element):
    """Given a DOM Element (level 2), return the local namespace declarations
    on the element.

    This function returns a dictionary of prefix -> namespaceURI values.
    The non-prefix (default namespace) is represented by None.
    """

    assert element.nodeType == element.ELEMENT_NODE

    # Decode XML namespace declarations from xmlns and xmlns:* attributes
    declarations = {}
    for i in range(element.attributes.length):
        attrNode = element.attributes.item(i)
        if attrNode.namespaceURI != XMLNS_NAMESPACE:
            continue
        if (attrNode.localName, attrNode.prefix) == ('xmlns', None):
            # Default namespace (no prefix)
            (prefix, namespace) = (None, attrNode.nodeValue)
        elif attrNode.prefix == 'xmlns':
            # Prefix namespace
            (prefix, namespace) = (attrNode.localName, attrNode.nodeValue)
            if namespace == XMLNS_NAMESPACE or not namespace:
                # XML Namespaces 1.0 specifies strict requirements on the use of the XMLNS_NAMESPACE namespace,
                # and it does not allow 'undeclaring' prefixes.
                raise ValueError("Illegal namespace declaration %s=%r" % (attrNode.nodeName, attrNode.nodeValue))
        else:
            raise ValueError("Illegal use of namespace %s in attribute %s=%r" % (XMLNS_NAMESPACE, attrNode.nodeName, attrNode.nodeValue))
        assert prefix not in declarations    # This should never fail.
        declarations[prefix] = namespace
    return declarations

def replace_namespace_declarations(element, new_prefixes):
    """Given an element and a dictionary of prefix -> namespaceURI mappings,
    replace all namespace declarations on the element with the ones given.
    """

    assert element.nodeType == element.ELEMENT_NODE

    # Remove existing namespace declarations
    attrNodes_to_remove = []
    for i in range(element.attributes.length):
        attrNode = element.attributes.item(i)
        if attrNode.namespaceURI != XMLNS_NAMESPACE:
            continue
        attrNodes_to_remove.append(attrNode)
    for attrNode in attrNodes_to_remove:
        element.removeAttributeNode(attrNode)

    # Generate new xmlns attributes
    for (prefix, namespace) in new_prefixes.items():
        if prefix is None:
            element.setAttributeNS(XMLNS_NAMESPACE, 'xmlns', namespace or '')
        else:
            element.setAttributeNS(XMLNS_NAMESPACE, 'xmlns:' + prefix, namespace or '')

def change_attribute_prefix(attrNode, prefix):
    assert attrNode.NODE_TYPE == attrNode.ATTRIBUTE_NODE
    assert prefix is None or isinstance(prefix, str)

    if prefix is None:
        qualifiedName = attrNode.localName
    else:
        assert ":" not in prefix
        qualifiedName = "%s:%s" % (prefix, attrNode.localName)

    new_attrNode = attrNode.ownerDocument.createAttributeNS(attrNode.namespaceURI, qualifiedName)
    new_attrNode.value = attrNode.value
    attrNode.ownerElement.setAttributeNode(new_attrNode)
    return new_attrNode

def change_attribute_namespace(attrNode, namespaceURI):
    assert attrNode.NODE_TYPE == attrNode.ATTRIBUTE_NODE
    assert namespaceURI == EMPTY_NAMESPACE or isinstance(namespaceURI, str)

    new_attrNode = attrNode.ownerDocument.createAttributeNS(namespaceURI, attrNode.nodeName)
    new_attrNode.value = attrNode.value
    attrNode.ownerElement.setAttributeNode(new_attrNode)
    return new_attrNode

# See the algorithm at http://www.w3.org/TR/DOM-Level-3-Core/namespaces-algorithms.html
def normalize_namespaces(element, strip_dups=False, parent_prefixes=None):
    assert element.nodeType == element.ELEMENT_NODE

    if parent_prefixes is None:
        # Walk up the document tree to find the list of elements that might
        # declare namespaces.
        top_element = element.ownerDocument.documentElement
        ancestry = []
        e = element
        while not top_element.isSameNode(e):
            e = e.parentNode
            if e is None:
                raise ValueError("element %r not connected to document" % (element,))
            ancestry.append(e)

        # Walk down the tree to determine the current scope
        ancestry.reverse()
        parent_prefixes = NamespaceScope()
        for e in ancestry:
            parent_prefixes.update(get_namespace_declarations(e))

    # Build list of local namespace declarations
    new_prefixes = get_namespace_declarations(element)

    # Merge the parent and new prefixes
    current_prefixes = parent_prefixes.copy()
    if strip_dups:
        duplicate_prefixes = current_prefixes.update(new_prefixes)
        for prefix in duplicate_prefixes:
            del new_prefixes[prefix]
    else:
        current_prefixes.update(new_prefixes)

    # Fix the element's namespace declarations
    if element.prefix in current_prefixes and current_prefixes[element.prefix] == element.namespaceURI:
        # Elements prefix and namespaceURI are in-scope.  Do nothing
        pass
    elif element.namespaceURI == EMPTY_NAMESPACE and element.prefix is not None:
        # You can't have a non-empty prefix with an empty namespace with
        # XML Namespaces 1.0
        raise ValueError("Cannot undeclare non-default namespace prefix")
    else:
        # Create a local namespace declaration attribute for this
        # namespace.  Don't care if a conflicting prefix existed before.
        new_prefixes[element.prefix] = element.namespaceURI
        current_prefixes[element.prefix] = element.namespaceURI

    # Fix the attributes' namespace declarations
    for attrNode in list(getAttributeNodes(element)):
        # Skip xmlns attributes
        if attrNode.namespaceURI == XMLNS_NAMESPACE:
            continue

        # Skip attributes with no namespace URI
        if attrNode.namespaceURI == EMPTY_NAMESPACE:
            assert hasattr(attrNode, 'localName')   # Require at least DOM level 2 for now
            continue # Do nothing, because attributes don't have namespaces by default.

        # Skip attributes whose prefixes and namespace URIs match the current in-scope prefixes.
        if attrNode.prefix and attrNode.prefix in current_prefixes and current_prefixes[attrNode.prefix] == attrNode.namespaceURI:
            # Attribute and prefix are matched.  Do nothing.
            continue

        # If the attribute's namespace has a declared prefix in the current
        # scope, change the attribute's prefix to that prefix.  If there is
        # more than one such prefix, pick one that has the "most local" binding.
        if current_prefixes.has_namespace(attrNode.namespaceURI):
            prefix = current_prefix.prefix_from_namespace(attrNode.namespaceURI)
            change_attribute_prefix(attrNode, prefix)
            continue

        # The attribute's namespace has no associated prefix yet.  We need to
        # declare one.  If we can use the existing prefix (i.e. it's not
        # already defined), do so.
        if attrNode.prefix not in current_prefixes:
            new_prefixes[attrNode.prefix] = attrNode.namespaceURI
            current_prefixes[attrNode.prefix] = attrNode.namespaceURI
            continue

        # The attribute's namespace has no associated prefix, and the
        # attribute's current prefix is already taken.  Generate one.
        j = 1
        while True:
            generated_prefix = "NS%d" % (j,)
            if generated_prefix not in current_prefixes:
                break
            j += 1

        # Declare the new prefix
        new_prefixes[generated_prefix] = attrNode.namespaceURI
        current_prefixes[generated_prefix] = attrNode.namespaceURI

        # Change attribute's prefix
        change_attribute_prefix(attrNode, generated_prefix)

    # Update the namespace declarations on the element.
    replace_namespace_declarations(element, new_prefixes)

    # HACK - Remove xmlns='' attribute if it doesn't need to be there.
    if (new_prefixes.get(None, object()) == EMPTY_NAMESPACE and
            parent_prefixes.get(None, object()) == EMPTY_NAMESPACE and
            element.hasAttributeNS(XMLNS_NAMESPACE, 'xmlns') and
            not element.getAttributeNS(XMLNS_NAMESPACE, 'xmlns')):
        element.removeAttributeNS(XMLNS_NAMESPACE, 'xmlns')

    # Recurse over child elements
    for e in element.childNodes:
        if e.nodeType == element.ELEMENT_NODE:
            normalize_namespaces(e, strip_dups=strip_dups, parent_prefixes=current_prefixes)

def substitute_namespaces(element, element_dict, attribute_dict=None, deep=True):
    # NB: You probably need to call normalize_namespaces after using this.
    assert element.nodeType == element.ELEMENT_NODE

    # The default attribute_dict is the same as the element_dict, but with the
    # entry for EMPTY_NAMESPACE removed.
    if attribute_dict is None:
        attribute_dict = element_dict.copy()
        if EMPTY_NAMESPACE in attribute_dict:
            del attribute_dict[EMPTY_NAMESPACE]

    # Replace attribute namespaces
    for attrNode in list(getAttributeNodes(element)):
        if attrNode.namespaceURI in attribute_dict:
            attrNode = change_attribute_namespace(attrNode, attribute_dict[attrNode.namespaceURI])

    # Set element namespace
    if element.namespaceURI in element_dict:
        element.namespaceURI = element_dict[element.namespaceURI]

    # Iterate over child elements
    if deep:
        for node in element.childNodes:
            if node.nodeType != node.ELEMENT_NODE:
                continue
            substitute_namespaces(node, element_dict, attribute_dict, deep)

# vim:set ts=4 sw=4 sts=4 expandtab:
