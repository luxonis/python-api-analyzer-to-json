import json
import os
import re
import sys
from inspect import Parameter, Signature
from pathlib import Path
from typing import List

from pydoctor.driver import get_system
from pydoctor.epydoc.markup import Field
from pydoctor.epydoc.markup._pyval_repr import colorize_pyval, colorize_inline_pyval
from pydoctor.epydoc.markup.epytext import parse_docstring
from pydoctor.model import Options, Documentable, DocumentableKind, Class, Function, Attribute

opts = Options.defaults()
opts.projectbasedirectory = os.getcwd()
opts.sourcepath = [Path(os.path.join(os.getcwd(), sys.argv[1]))]
system = get_system(opts)


def remove_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def serialize_annotation(annotation: str):
    # annotation == <code>{annotation_type}</code>
    return annotation.replace("<code>", "").replace("</code>", "")


def serialize_parameter(parameter: Parameter):
    data = {
        "name": parameter.name,
        "kind": str(parameter.kind),
    }

    if parameter.annotation is not Parameter.empty:
        data["type"] = colorize_inline_pyval(parameter.annotation).to_node().astext()
        data["type"] = remove_html_tags(data["type"])
    if parameter.default is not Parameter.empty:
        data["default"] = colorize_inline_pyval(parameter.default).to_node().astext()
        data["default"] = remove_html_tags(data["default"])

    return data


def serialize_attribute(obj, attr: Attribute):
    if (attr.annotation is not None):
        obj["type"] = colorize_inline_pyval(attr.annotation).to_node().astext()

    if (attr.value is not None):
        doc = colorize_pyval(
            attr.value,
            linelen=attr.system.options.pyvalreprlinelen,
            maxlines=attr.system.options.pyvalreprmaxlines
        )

        obj["value"] = doc.to_node().astext()


def serialize_function(obj, func: Function):
    obj["is_async"] = func.is_async
    obj["signature"] = {
        "parameters": list(map(serialize_parameter, func.signature.parameters.values()))
    }
    if func.signature.return_annotation is not Signature.empty:
        return_annotation = serialize_annotation(str(func.signature.return_annotation))
        pattern = r'(?:<a[^>]*>)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:</a>)?'
        match = re.search(pattern, return_annotation)
        if match:
            extracted_text = match.group("name")
            obj["signature"]["return_annotation"] = extracted_text
        else:
            obj["signature"]["return_annotation"] = "None"


def serialize_docstring_field(field: Field):
    obj = {
        "name": field.tag(),
        "body": field.body().to_node().astext(),
    }
    if field.arg() is not None:
        obj["arg"] = field.arg()
    return obj


def build_json(json_arr, documentables: List[Documentable]):
    for doc in documentables:
        obj = {
            "name": doc.fullName(),
            "short_name": doc.name,
            "kind": doc.kind.name,
            "is_visible": doc.isVisible,
            "is_private": doc.isPrivate,
            "children": [],
        }

        if (doc.parsed_docstring is None) and (doc.docstring is not None):
            # print(doc.docstring)
            doc.parsed_docstring = parse_docstring(doc.docstring, [])

        if doc.parsed_docstring is not None:
            obj["docstring"] = {
                "fields": list(map(serialize_docstring_field, doc.parsed_docstring.fields))
            }
            if doc.parsed_docstring.has_body:
                obj["docstring"]["summary"] = doc.parsed_docstring.get_summary().to_node().astext()
                obj["docstring"]["all"] = doc.parsed_docstring.to_node().astext()

        if doc.parent is not None:
            obj["parent"] = doc.parent.fullName()

        build_json(obj["children"], doc.contents.values())

        if doc.kind is DocumentableKind.CLASS:
            cls: Class = doc
            obj["bases"] = cls.bases
        elif doc.kind is DocumentableKind.FUNCTION or doc.kind is DocumentableKind.METHOD:
            serialize_function(obj, doc)
        elif doc.kind is DocumentableKind.ATTRIBUTE or doc.kind is DocumentableKind.CONSTANT or doc.kind is DocumentableKind.VARIABLE or doc.kind is DocumentableKind.TYPE_ALIAS or doc.kind is DocumentableKind.TYPE_VARIABLE or doc.kind is DocumentableKind.CLASS_VARIABLE:
            serialize_attribute(obj, doc)

        json_arr.append(obj)


json_ready = []
build_json(json_ready, system.rootobjects)

jsonified = json.dumps(json_ready)
with open("docs.json", "w") as f:
    f.write(jsonified)
