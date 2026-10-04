"""Verified dotted comic release names; never infer catalog identity from a name."""
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import unicodedata


def policy(config):
    value = config.get('release_naming', {})
    if not isinstance(value, dict) or type(value.get('enabled', False)) is not bool:
        raise ValueError('release_naming.enabled must be boolean')
    size = value.get('batch_size', 1)
    if type(size) is not int or not 1 <= size <= 100:
        raise ValueError('Invalid release_naming.batch_size')
    if value.get('enabled', False):
        settings = config.get('mylar')
        paths = (config.get('writer_state'), settings.get('config_dir') if isinstance(settings, dict) else None)
        if any(not isinstance(p, str) or not Path(p).is_absolute() for p in paths):
            raise ValueError('Release naming requires Mylar and shared writer coordination')
    return dict(enabled=value.get('enabled', False), batch_size=size)


def dotted(value):
    if not isinstance(value, str) or not value.strip() or re.search(r'[\x00-\x1f\x7f]', value):
        raise ValueError('Invalid release label')
    value = unicodedata.normalize('NFC', value)
    value = re.sub(r'[\s_/:\\*?"<>|]+', '.', value)
    value = re.sub(r'(?<=\.)-+(?=\.)', '.', value)
    value = re.sub(r'\.+', '.', value).strip('.')
    if not value or value in ('.', '..'):
        raise ValueError('Empty release label')
    return value


def issue_number(value):
    value = str(value).strip()
    for fraction, decimal in (('½', '.5'), ('¼', '.25'), ('¾', '.75')):
        if value == fraction:
            value = '0'+decimal
        elif re.fullmatch(r'[+-]?\d+'+fraction, value):
            value = value[:-1]+decimal
    match = re.fullmatch(r'([+-]?\d+(?:\.\d+)?)[\s.]*([A-Za-z]+)?', value)
    if not match:
        raise ValueError('Unsupported release issue number')
    try:
        number = Decimal(match[1])
    except InvalidOperation as error:
        raise ValueError('Unsupported release issue number') from error
    absolute = format(abs(number), 'f')
    integer, dot, fraction = absolute.partition('.')
    result = ('-' if number < 0 else '')+integer.zfill(3)
    if dot and fraction.rstrip('0'):
        result += '.'+fraction.rstrip('0')
    if match[2]:
        result += '.'+match[2].upper()
    return result


def labels(source, group, issueid, year, kind=None, number=None):
    """Keep release blocks; remove only proven group/year/import-marker fields."""
    result = []
    stem = Path(source).stem
    markers = re.findall(r'\[__(\d+)__\]', stem)
    if markers and markers != [str(issueid)]:
        raise ValueError('Conflicting release filename identity')
    stem = re.sub(r'\[__\d+__\]', '', stem)
    for match in re.finditer(r'\(([^()]*)\)|\[([^\[\]]*)\]', stem):
        text = (match[1] if match[1] is not None else match[2]).strip()
        if re.fullmatch(r'(?:19|20)\d{2}', text):
            if text != year:
                raise ValueError('Publication or edition year needs review')
            continue
        if number is not None and re.fullmatch(r'#[\s]*[+-]?\d+(?:\.\d+)?(?:[\s.]*[A-Za-z]+)?', text):
            if issue_number(text[1:]) != issue_number(number):
                raise ValueError('Conflicting release filename number')
            continue
        if kind in ('TPB', 'HC', 'GN') and text.casefold() == kind.casefold():
            continue
        if group and dotted(text).casefold() == dotted(group).casefold():
            continue
        if group and text.casefold().endswith('-'+group.casefold()):
            text = text[:-len(group)-1].strip()
        if text:
            label = dotted(text)
            if label.casefold() not in {x.casefold() for x in result}:
                result.append(label)
    return result


def render(proposal):
    """Render only a publication already proven by the native naming resolver."""
    # Bracket blocks survive below; bare edition/variant text must not disappear.
    bare = re.sub(r'\([^()]*\)|\[[^\[\]]*\]', '', Path(proposal['source']).stem)
    words = re.findall(r'[^\W_]+', proposal['series'])
    prefix = r'^[\W_]*'+r'[\W_]*'.join(re.escape(word) for word in words)+r'(?!\w)'
    bare = re.sub(prefix, '', bare, count=1, flags=re.I)
    if proposal.get('group'):
        bare = re.sub(r'-'+re.escape(proposal['group'])+r'$', '', bare, flags=re.I)
    if re.search(r'\b(?:edition|deluxe|omnibus|hardcover|director[\W_]*s[\W_]*cut|variant|cover|reprint|printing|ashcan|preview|sketch|foil)\b', bare, re.I):
        raise ValueError('Unbracketed edition or variant label needs review')
    year = str(proposal['year'])
    if not re.fullmatch(r'(?:19|20)\d{2}', year):
        raise ValueError('A verified publication year is required')
    group = proposal.get('group')
    if group is not None and (not isinstance(group, str) or not group.strip()
                             or re.search(r'[()\[\]/\\]', group)):
        raise ValueError('Unverified release group')
    parts = [dotted(proposal['series'])]
    volume = proposal.get('volume')
    if volume is not None:
        if not re.fullmatch(r'[1-9]\d{0,2}', str(volume)):
            raise ValueError('Unverified series volume')
        parts.append('v'+str(volume))
    number = issue_number(proposal['number'])
    if proposal['type'] in ('TPB', 'HC', 'GN'):
        parts.extend(('v'+number, '('+proposal['type']+')'))
    else:
        parts.append(number)
    parts.append('('+year+')')
    parts.extend('('+label+')' for label in labels(proposal['source'], group, proposal['issueid'], year, proposal['type'], proposal['number']))
    name = '.'.join(parts)+(('-'+dotted(group)) if group else '')+'.cbz'
    if len(name.encode('utf-8')) > 255 or Path(name).name != name:
        raise ValueError('Release filename exceeds filesystem limits')
    return name
