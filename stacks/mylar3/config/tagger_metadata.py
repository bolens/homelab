"""Explicit metadata overrides and loss-averse ComicInfo reconciliation.

Migration foundation only: this module neither invokes a tagger nor writes files.
"""

import copy
import re
import xml.etree.ElementTree as ET

MAX_XML = 262144


def parse(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_XML:
        raise ValueError('Invalid metadata size or type')
    try:
        text = raw.decode('utf-8-sig')
        if re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b', text, re.I):
            raise ValueError('DTD and entities are unsupported')
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        root = ET.fromstring(text, parser=parser)
    except (UnicodeError, ET.ParseError) as error:
        raise ValueError('Malformed ComicInfo') from error
    if root.tag != 'ComicInfo':
        raise ValueError('Expected ComicInfo root')
    return root


def overrides(*, volume=None, reading_order=None, age_rating=None):
    """Missing inputs preserve existing values. Volume is already resolved by Mylar."""
    result = {}
    if volume not in (None, '', 'None'):
        if isinstance(volume, bool) or not re.fullmatch(r'[1-9][0-9]{0,3}', str(volume)):
            raise ValueError('Invalid resolved volume')
        result['Volume'] = str(volume)
    if reading_order is not None:
        names, numbers = [], []
        for entry in reading_order:
            if not isinstance(entry, (tuple, list)) or len(entry) != 2:
                raise ValueError('Expected paired arc names and numbers')
            name, number = entry
            if not isinstance(name, str) or not name.strip() or ',' in name:
                raise ValueError('Ambiguous arc name')
            if isinstance(number, bool) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', str(number)):
                raise ValueError('Invalid arc order')
            names.append(name.strip())
            numbers.append(str(number))
        if names:
            result.update(StoryArc=','.join(names), StoryArcNumber=','.join(numbers))
    if age_rating not in (None, '', 'None'):
        if not isinstance(age_rating, str):
            raise ValueError('Invalid age rating')
        result['AgeRating'] = age_rating
    return result


def reconcile(original, tagged, *, updates=None, replace_fields=()):
    """Preserve old fields unless explicitly replaced, including unknown extensions.

    Tagged values may populate previously absent fields. An explicit replacement
    may remove an old field when the tagged document omits it. Callers must derive
    that allow-list from operator policy, never from arbitrary CLI output.
    """
    root = parse(tagged)
    old = parse(original) if original else None
    updates = dict(updates or {})
    allowed = set(replace_fields) | set(updates)
    arcs = {'StoryArc', 'StoryArcNumber'}
    if (set(updates) & arcs and not arcs <= set(updates)) or (allowed & arcs and not arcs <= allowed):
        raise ValueError('Arc names and numbers must be replaced together')
    if any(not isinstance(k, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', k) for k in allowed):
        raise ValueError('Invalid field name')
    if any(not isinstance(v, str) for v in updates.values()):
        raise ValueError('Expected explicit text updates')
    if old is not None:
        root.attrib.update(old.attrib)
        preserved = {node.tag for node in old if node.tag not in allowed}
        if preserved & arcs:
            preserved |= arcs
        for node in list(root):
            if node.tag in preserved:
                root.remove(node)
        root.extend(copy.deepcopy(node) for node in old if node.tag in preserved)
    for name, text in updates.items():
        for node in list(root):
            if node.tag == name:
                root.remove(node)
        ET.SubElement(root, name).text = text
    names, numbers = root.findall('StoryArc'), root.findall('StoryArcNumber')
    if len(names) > 1 or len(numbers) > 1 or (numbers and not names):
        raise ValueError('Ambiguous arc fields')
    if numbers:
        labels = (names[0].text or '').split(',')
        positions = (numbers[0].text or '').split(',')
        if len(labels) != len(positions) or any(not v.strip() for v in labels + positions):
            raise ValueError('Mismatched arc names and numbers')
    result = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    parse(result)
    return result
