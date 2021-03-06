from clang.cindex import Cursor, CursorKind, TokenGroup, AccessSpecifier
from ast.attributes.attribute import Attribute
from ast.attributes.annotation import Annotation
from utility.namespace import Namespace
from utility.code_generation import string_to_char_pack

from utility.logger import GlobalLogger
import pprint

def print_extent(extent):
    return '(l: {} c: {}, l: {}, c: {})'.format(extent.start.line, extent.start.column,
            extent.end.line, extent.end.column)

def text_in_cursor(cursor):
    txt = ''
    for t in cursor.get_tokens():
        if t.spelling:
            txt += ' ' + t.spelling
        else:
            txt += ' ' + t.displayname

    return txt


class Node(object):
    """Base class of all processed AST nodes

    An AST node has the original AST node (libclang.cindex.Cursor)
    info plus parsed attributes associated with it

    Node processing works by associating Node subclasses with different
    clang.cindex cursor kinds. Each Node subclass declares which members
    it recognises by mapping between the known cursor kinds and the corresponding Node
    subclasses. For example, a namespace may declare it only knows about classes and other
    namespaces as members, as follows:

        class Namespace(Node):

            @staticmethod
            def MEMBERS_MAPPING():
                return {
                    CursorKind.NAMESPACE: Namespace,
                    CursorKind.CLASS_DECL: Class
                }

    Node instances should be created through the Node.create_node() function,
    which takes care of creating the node and initializing its attributes and
    child nodes.
    """

    def __init__(self, cursor, parent = None, translation_unit = None, file = None):
        """ Initializes a node, given its libclang AST cursor and the parent node

            NEVER create nodes calling plain class constructor, use create_node()
            instead.
        """

        self.cursor = cursor
        self.parent = parent
        self.children = {}
        self.attributes = []
        self._skip_node = False

        if parent is not None:
            self.translation_unit = parent.translation_unit
        else:
            self.translation_unit = translation_unit

        if file is not None:
            self.file = file
        else:
            self.file = str(self.cursor.location.file)

        assert(self.translation_unit is not None)

    def skip(self):
        return self._skip_node

    def set_skip(self):
        self._skip_node = True

    def print_ast_node(self):
        """ Yields an string representation of the node, suitable for AST printing"""

        if self.cursor.kind == CursorKind.UNEXPOSED_DECL:
            short = '{}: (Unexposed decl) \'{}\''.format(self.file, text_in_cursor(self.cursor))
        else:
            short = "{}: ({}, Type kind: {}) {}".format(self.file, str(self.node_class_kind()), str(self.cursor.type.kind), self.fullname)

        if self.attributes:
            return short + '\n' + '\n =>'.join([a.description() for a in self.attributes])
        else:
            return short

    def get_children(self):
        for kind, values in self.children.iteritems():
            for name, value in values.iteritems():
                yield value

    @classmethod
    def create_child(nodeClass, **kwargs):
        """ Creates a child node of the given parent node, from the given
            libclang cursor

            If a mapping of the cursor kind is found (See Node class docstring above) an
            instance of the corresponding Node subclass is returned. Else None is returned.
        """

        if hasattr(nodeClass, 'MEMBERS_MAPPING'):
            cursor = kwargs['cursor']
            mapping = nodeClass.MEMBERS_MAPPING()

            if cursor.kind in mapping:
                class_ = mapping[cursor.kind]
                return class_.create_node(**kwargs)
        else:
            GlobalLogger.warning().step('{} has no {} mapping'.format(nodeClass.__name__, cursor.kind))
            return None

    @classmethod
    def create_node(nodeClass, **kwargs):
        """ Creates a node and initializes its children and attributes"""

        node = nodeClass(**kwargs)
        nodeInfo = '\r{}'.format(node.cursor.displayname or node.cursor.spelling)
        print (nodeInfo[:90] + '...') if len(nodeInfo) > 87 else nodeInfo,
        nodeClass.initialize_children(node)
        node.attributes = Attribute.get_node_attributes(node)
        node.process()

        if node.skip():
            return None
        else:
            return node

    def process(self):
        """ Processes node data after creation"""
        pass

    @classmethod
    def initialize_children(nodeClass, node):
        """ Fills the children dict of the node

            The children dictionary has one entry for each node kind
            recognised by this node class, so classes, functions, fields, etc
            are classified.
            Each kind entry is a dict 'node name' -> 'node', where the node name
            is the spelling of the AST node ('f', 'std::vector<int>', 'MyClass', etc)
        """

        node.children = {}
        if not hasattr(nodeClass, 'MEMBERS_MAPPING'):
            return

        mapping = nodeClass.MEMBERS_MAPPING()

        for childKind in [class_.node_class_kind() for class_ in set(mapping.values())]:
            node.children[childKind] = {}

        for c in node.cursor.get_children():
            if c.kind in mapping:
                child = nodeClass.create_child(cursor = c, parent = node)
                if child is not None and child.is_public and child.file == node.file:
                    node.children[child.node_class_kind()][child.displayname] = child

    @property
    def spelling(self):
        return self.cursor.spelling

    @property
    def displayname(self):
        return self.cursor.displayname

    @property
    def spelling_as_charpack(self):
        return string_to_char_pack(self.spelling)

    @property
    def displayname_as_charpack(self):
        return string_to_char_pack(self.displayname)

    @property
    def file_as_charpack(self):
        return string_to_char_pack(self.file)

    @property
    def name(self):
        if self.spelling:
            return self.spelling
        else:
            return ''

    @property
    def is_public(self):
        return self.cursor.access_specifier in [AccessSpecifier.PUBLIC, AccessSpecifier.NONE, AccessSpecifier.INVALID]

    @property
    def kind(self):
        return self.cursor.kind

    @property
    def kindstring(self):
        """ Returns the string representation of the kind of this node"""

        return type(self).__name__.lower()

    @classmethod
    def node_class_kind(nodeClass):
        """ Returns an string representation of the node kind implemented by the node class """

        return nodeClass.__name__.lower()

    @property
    def fullname(self):
        """ Returns the full qualified name of the entity pointed by the node """

        if self.parent is None or not self.name:
            return ''
        else:
            return Namespace.SCOPE_OPERATOR.join([self.parent.fullname, self.name])

    @property
    def fullname_as_charpack(self):
        return string_to_char_pack(self.fullname)

    def __str__(self):
        return self.print_ast_node()

    @property
    def attribute(self):
        """ Returns the attribute (if any) applied to this node

            Currently only one attribute per node is supported (See TranslationUnit.match_annotations()
            for the reasoning behind this limitation)
        """

        if self.attributes:
            return self.attributes[0]
        else:
            return None

    def reflection_enabled(self):
        """ Says whether the user requested reflection for this node

            Disabled by default, each Node subclass may implement a different criteria
        """

        return False
