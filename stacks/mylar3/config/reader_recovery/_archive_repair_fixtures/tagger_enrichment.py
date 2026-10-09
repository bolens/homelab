"""Reader-visible supplements derived from established metadata, never guesses."""
import re

if __package__:
    from .tagger_metadata import parse, SINGLETONS
else:
    from tagger_metadata import parse, SINGLETONS

FIELDS = {'Genre', 'LanguageISO', 'AgeRating', 'Manga', 'GTIN', 'SeriesGroup',
          'StoryArc', 'StoryArcNumber', 'Tags'}
RATINGS = {'Unknown', 'Rating Pending', 'Early Childhood', 'Everyone', 'G',
           'Everyone 10+', 'PG', 'Kids to Adults', 'Teen', 'MA15+', 'Mature 17+',
           'M', 'R18+', 'Adults Only 18+', 'X18+'}


def values(text):
    return list(dict.fromkeys(v.strip() for v in (text or '').split(',') if v.strip()))


def validate(policy):
    if not isinstance(policy, dict) or set(policy) - FIELDS:
        raise ValueError('Unsupported enrichment fields')
    for field, value in policy.items():
        if (not isinstance(value, str) or not value.strip() or len(value) > 65536
                or any(ord(c) < 32 for c in value)):
            raise ValueError('Invalid enrichment text')
        if field == 'LanguageISO' and not re.fullmatch(r'[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*', value):
            raise ValueError('Invalid language identifier')
        if field == 'AgeRating' and value not in RATINGS:
            raise ValueError('Invalid age rating')
        if field == 'Manga' and value not in {'Unknown', 'No', 'Yes', 'YesAndRightToLeft'}:
            raise ValueError('Invalid manga direction')
        if field == 'GTIN':
            digits = value.replace('-', '').replace(' ', '')
            valid = (len(digits) == 13 and re.fullmatch(r'(?:978|979)[0-9]{10}', digits) is not None
                     and sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(digits)) % 10 == 0)
            valid |= (len(digits) == 10 and re.fullmatch(r'[0-9]{9}[0-9X]', digits) is not None
                      and sum((10-i) * (10 if c == 'X' else int(c)) for i, c in enumerate(digits)) % 11 == 0)
            if not valid:
                raise ValueError('Expected a valid ISBN')
    if {'StoryArc', 'StoryArcNumber'} & set(policy):
        if not {'StoryArc', 'StoryArcNumber'} <= set(policy):
            raise ValueError('Expected paired arc names and positions')
        names = [v.strip() for v in policy['StoryArc'].split(',')]
        numbers = [v.strip() for v in policy['StoryArcNumber'].split(',')]
        if (len(names) != len(numbers) or not all(names)
                or not all(re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', n) for n in numbers)):
            raise ValueError('Expected paired arc names and positions')
    return policy


def supplements(raw, policy=None, *, metadata=None):
    """Fill absent/blank fields; extend Tags without replacing operator labels.

    Existing scalar and collection fields win. An existing arc never acquires a
    guessed position. Provider credits can supplement newly tagged archives.
    """
    policy = validate(policy or {})
    root = parse(raw) if raw else None
    current = {}
    if root is not None:
        for node in root:
            if isinstance(node.tag, str):
                if node.tag in SINGLETONS and node.tag in current:
                    raise ValueError('Duplicate metadata field')
                current[node.tag] = (node.text or '').strip()
    sources = dict(current)
    metadata = metadata or {}
    for key, field in [('characters', 'Characters'), ('teams', 'Teams'), ('locations', 'Locations')]:
        if metadata.get(key):
            sources[field] = ','.join(metadata[key])
    if metadata.get('publisher'):
        sources['Publisher'] = metadata['publisher']
    candidates = dict(policy)
    if sources.get('Publisher'):
        candidates.setdefault('SeriesGroup', 'Publisher: ' + sources['Publisher'])
    tags = values(current.get('Tags'))
    for field, prefix in [('Characters', 'Character'), ('Teams', 'Team'), ('Locations', 'Location')]:
        tags.extend(prefix + ': ' + v for v in values(sources.get(field)))
    tags.extend(values(policy.get('Tags')))
    tags = list(dict.fromkeys(tags))
    updates = {k: v for k, v in candidates.items() if k != 'Tags' and not current.get(k)}
    # Keep a supplied arc pair atomic and never pair old names with new positions.
    if current.get('StoryArc') or current.get('StoryArcNumber'):
        updates.pop('StoryArc', None)
        updates.pop('StoryArcNumber', None)
    if tags and tags != values(current.get('Tags')):
        updates['Tags'] = ', '.join(tags)
    return updates
