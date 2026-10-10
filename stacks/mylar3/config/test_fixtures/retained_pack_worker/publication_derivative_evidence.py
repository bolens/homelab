"""Independent read-side validation of reviewed exact member-name relations."""
from pathlib import PurePosixPath
import stat

import publication_evidence as evidence


def exact(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise evidence.Unavailable('Exact derivative evidence schema required')


def inventory(value):
    exact(value, ('version', 'members', 'pages', 'payload', 'source_sha256', 'source_signature'))
    if not evidence.digest_value(value['source_sha256']):
        raise evidence.Unavailable('Exact inventory source digest required')
    stamp(value['source_signature'])
    result = {key: value[key] for key in ('version', 'members', 'pages', 'payload')}
    evidence.validate(result)
    return result


def absolute(value):
    if not isinstance(value, str) or not value or not PurePosixPath(value).is_absolute() or '..' in PurePosixPath(value).parts:
        raise evidence.Unavailable('Exact absolute historical path required')


def stamp(value, count=9):
    if not isinstance(value, list) or len(value) != count or any(type(n) is not int or n < 0 for n in value):
        raise evidence.Unavailable('Exact historical filesystem identity required')


def private_stamp(value):
    stamp(value)
    if not stat.S_ISREG(value[5]) or stat.S_IMODE(value[5]) != 0o600 or value[8] != 1:
        raise evidence.Unavailable('Private exclusive historical file identity required')


def file_fact(value, *, private=False):
    exact(value, ('path', 'signature', 'sha256'))
    absolute(value['path']);stamp(value['signature'])
    if not evidence.digest_value(value['sha256']):
        raise evidence.Unavailable('Exact historical file digest required')
    if private:private_stamp(value['signature'])


def observations(value):
    if not isinstance(value, list) or len(value) > 8:
        raise evidence.Unavailable('Bounded exact historical observations required')
    seen = set()
    for row in value:
        exact(row, ('owner', 'source_sha256', 'signature', 'catalog'))
        owner = evidence.exact_owner(row['owner']);key = evidence.canonical_digest(owner)
        if key in seen or not evidence.digest_value(row['source_sha256']):
            raise evidence.Unavailable('Distinct historical owner observation required')
        seen.add(key);stamp(row['signature']);evidence.catalog_fact(row['catalog'], owner)


def historical_facts(request, facts):
    stamp(facts['writer'], 4)
    source = facts['source']
    exact(source, ('path', 'inventory', 'decision', 'owner', 'observed'))
    if source['path'] != request['source'] or source['decision'] not in ('unknown', 'allowed'):
        raise evidence.Unavailable('Exact historical source admission required')
    evidence.exact_owner(source['owner']);observations(source['observed']);observations(facts['observed'])
    if ((source['decision']=='unknown' and source['observed'])
            or (source['decision']=='allowed' and request['owner'] not in [row['owner'] for row in source['observed']])):
        raise evidence.Unavailable('Historical admission decision and observations disagree')
    if (len(facts['observed']) != 1 or facts['observed'][0]['owner'] != request['owner']
            or facts['observed'][0]['catalog']['path'] != request['source']
            or facts['observed'][0]['source_sha256'] != request['source_sha256']):
        raise evidence.Unavailable('Exact selected historical owner required')
    inventory(source['inventory']);inventory(facts['derivative'])
    file_fact(facts['prepared'],private=True);file_fact(facts['review'],private=True)
    if (facts['review']['path'] != request['review']['path']
            or facts['review']['sha256'] != request['review']['sha256']
            or facts['prepared']['signature'] != facts['derivative']['source_signature']
            or facts['observed'][0]['signature'] != source['inventory']['source_signature']):
        raise evidence.Unavailable('Historical reviewed file binding changed')
    exact(request['backup'], ('manifest', 'manifest_sha256', 'restore', 'restore_sha256'))
    backup = facts['backup'];exact(backup, ('manifest', 'restore', 'files'))
    for key in ('manifest', 'restore'):
        file_fact(backup[key],private=True)
        if (backup[key]['path'] != request['backup'][key]
                or backup[key]['sha256'] != request['backup'][key + '_sha256']):
            raise evidence.Unavailable('Historical backup receipt binding changed')
    if not isinstance(backup['files'], list) or len(backup['files']) != 4:
        raise evidence.Unavailable('Complete historical backup roles required')
    roles, identities = set(), set()
    for row in backup['files']:
        exact(row, ('role', 'source', 'copies'))
        if (not isinstance(row['role'], str) or row['role'] not in ('source', 'catalog', 'workflow', 'marker')
                or row['role'] in roles or not isinstance(row['copies'], list) or len(row['copies']) != 2):
            raise evidence.Unavailable('Exact distinct historical backup roles required')
        roles.add(row['role']);file_fact(row['source'])
        for copy in row['copies']:
            file_fact(copy,private=True)
            if copy['sha256'] != row['source']['sha256']:
                raise evidence.Unavailable('Historical isolated restore digest changed')
        for copy in [row['source'], *row['copies']]:
            identity = tuple(copy['signature'][:2])
            if identity in identities:
                raise evidence.Unavailable('Historical backup aliases another file')
            identities.add(identity)
        if row['role'] == 'source' and (row['source']['path'] != request['source']
                or row['source']['sha256'] != request['source_sha256']
                or row['source']['signature'] != source['inventory']['source_signature']):
            raise evidence.Unavailable('Historical source backup binding changed')


def certificate(value):
    exact(value, ('version', 'kind', 'executable', 'readiness', 'request', 'facts', 'token'))
    if (type(value['version']) is not int or value['version'] != 1
            or value['kind'] != 'reviewed-nested-lineage' or value['executable'] is not False
            or value['readiness'] != 'explicit-adoption-required'
            or not evidence.digest_value(value['token'])
            or value['token'] != evidence.canonical_digest({key: item for key, item in value.items() if key != 'token'})):
        raise evidence.Unavailable('Immutable reviewed lineage certificate required')
    request = value['request']
    exact(request, ('version', 'source', 'prepared', 'source_sha256', 'prepared_sha256', 'owner',
                    'census', 'mapping', 'preservation', 'review', 'backup'))
    if type(request['version']) is not int or request['version'] != 1:
        raise evidence.Unavailable('Unsupported derivative request')
    for key in ('source', 'prepared'):
        absolute(request[key])
    if request['source'] == request['prepared'] or any(not evidence.digest_value(request[key]) for key in ('source_sha256', 'prepared_sha256')):
        raise evidence.Unavailable('Separate exact source and prepared archive required')
    evidence.exact_owner(request['owner']);evidence.census_value(request['census'])
    exact(request['review'], ('path', 'sha256'))
    absolute(request['review']['path'])
    if not evidence.digest_value(request['review']['sha256']):
        raise evidence.Unavailable('Reviewed evidence digest required')
    exact(request['preservation'], ('original', 'restore'))
    for row in request['preservation'].values():
        exact(row, ('path', 'signature'));absolute(row['path'])
        private_stamp(row['signature'])
    if (request['preservation']['original']['path'] == request['preservation']['restore']['path']
            or request['preservation']['original']['signature'][:2] == request['preservation']['restore']['signature'][:2]):
        raise evidence.Unavailable('Distinct preserved copies required')
    mapping = request['mapping']
    if not isinstance(mapping, list) or len(mapping) != 1:
        raise evidence.Unavailable('Only one reviewed nested metadata migration supported')
    exact(mapping[0], ('from', 'to'))
    before, after = mapping[0]['from'], mapping[0]['to']
    if (not isinstance(before, str) or '/' not in before or PurePosixPath(before).name.casefold() != 'comicinfo.xml'
            or after != str(PurePosixPath(before).with_name('SourceMetadata.xml'))):
        raise evidence.Unavailable('Unsupported metadata member migration')
    facts = value['facts']
    exact(facts, ('writer', 'source', 'observed', 'derivative', 'migration', 'prepared', 'review', 'backup'))
    historical_facts(request, facts)
    source = facts['source']
    if (not isinstance(source, dict) or source.get('owner') != request['owner']
            or source.get('path') != request['source']
            or source['inventory']['source_sha256'] != request['source_sha256']
            or facts['derivative']['source_sha256'] != request['prepared_sha256']):
        raise evidence.Unavailable('Historical derivative source facts changed')
    exact(facts['prepared'], ('path', 'signature', 'sha256'))
    if facts['prepared']['path'] != request['prepared'] or facts['prepared']['sha256'] != request['prepared_sha256']:
        raise evidence.Unavailable('Prepared derivative facts changed')
    old, new = inventory(source['inventory']), inventory(facts['derivative'])
    if old['payload'] == new['payload'] or old['pages'] != new['pages']:
        raise evidence.Unavailable('Changed page lineage or missing payload transition')
    old_rows = {row['name']: row for row in old['members']}
    new_rows = {row['name']: row for row in new['members']}
    if before not in old_rows or after in old_rows or before in new_rows or after not in new_rows:
        raise evidence.Unavailable('Incomplete metadata member bijection')
    promoted = 'ComicInfo.xml' not in old_rows
    expected_names = {after if name == before else name for name in old_rows}
    if promoted:
        expected_names.add('ComicInfo.xml')
    if expected_names != set(new_rows):
        raise evidence.Unavailable('Derivative adds or removes unrelated members')
    change = facts['migration']
    exact(change, ('mapping', 'root_sha256', 'member_order', 'derivative_order'))
    if not evidence.digest_value(change['root_sha256']) or change['mapping'] != mapping:
        raise evidence.Unavailable('Exact root metadata migration required')
    if promoted:
        root = new_rows['ComicInfo.xml']
        if root['directory'] or root['bytes'] > evidence.MAX_METADATA or root['sha256'] != change['root_sha256']:
            raise evidence.Unavailable('Exact promoted root metadata required')
    for name, row in old_rows.items():
        target = after if name == before else name
        if name == 'ComicInfo.xml':
            if new_rows[name]['sha256'] != change['root_sha256']:
                raise evidence.Unavailable('Root metadata migration digest changed')
        elif dict(row, name=target) != new_rows[target]:
            raise evidence.Unavailable('Derivative changed preserved member bytes')
    order, next_order = change['member_order'], change['derivative_order']
    for names, rows in ((order, old_rows), (next_order, new_rows)):
        if (not isinstance(names, list) or any(not isinstance(name, str) for name in names)
                or len(names) > evidence.MAX_MEMBERS or len(names) != len(set(names))
                or len(names) != len(rows) or {name.rstrip('/') for name in names} != set(rows)
                or any(name.endswith('/') and not rows[name.rstrip('/')]['directory'] for name in names)):
            raise evidence.Unavailable('Complete historical archive member order required')
    if [after if name == before else name for name in order] + (['ComicInfo.xml'] if promoted else []) != next_order:
        raise evidence.Unavailable('Derivative member order changed')
    return old, new


def attestation(value):
    exact(value, ('version', 'epoch', 'prior_revision', 'inventory', 'allowed', 'rejected',
                  'evidence', 'observed', 'intent', 'created', 'lineage'))
    if (type(value['version']) is not int or value['version'] != 2
            or any(not evidence.digest_value(value[key]) for key in ('epoch', 'intent'))
            or type(value['prior_revision']) is not int or value['prior_revision'] < 0
            or type(value['created']) is not int or value['created'] < 0):
        raise evidence.Unavailable('Unsupported derivative attestation')
    relation = value['lineage'];exact(relation, ('version', 'plan', 'parents'))
    parents = relation['parents']
    if (type(relation['version']) is not int or relation['version'] != 1
            or not isinstance(parents, list) or len(parents) > evidence.REGISTRY_LIMIT
            or any(not evidence.digest_value(key) for key in parents) or parents != sorted(set(parents))):
        raise evidence.Unavailable('Exact sorted derivative predecessors required')
    old, new = certificate(relation['plan'])
    evidence.validate(value['inventory'])
    request = relation['plan']['request']
    if (value['inventory'] != new or request['census']['epoch'] != value['epoch']
            or request['census']['revision'] != value['prior_revision']):
        raise evidence.Unavailable('Derivative inventory or census changed')
    owner_keys = []
    for key in ('allowed', 'rejected'):
        group = value[key]
        if not isinstance(group, list) or not (1 if key == 'allowed' else 0) <= len(group) <= 8:
            raise evidence.Unavailable('Explicit bounded derivative owners required')
        owner_keys.extend(evidence.canonical_digest(evidence.exact_owner(owner)) for owner in group)
    if len(owner_keys) > 8 or len(owner_keys) != len(set(owner_keys)) or request['owner'] not in value['allowed']:
        raise evidence.Unavailable('Contradictory derivative owners')
    if value['evidence'] != dict(sha256=relation['plan']['token'], description='Reviewed exact nested metadata migration'):
        raise evidence.Unavailable('Explicit reviewed derivative evidence required')
    if not isinstance(value['observed'], list) or len(value['observed']) != len(value['allowed']):
        raise evidence.Unavailable('Observed correct owners required')
    for owner, facts in zip(value['allowed'], value['observed']):
        exact(facts, ('owner', 'source_sha256', 'signature', 'catalog'))
        if (facts['owner'] != owner or not evidence.digest_value(facts['source_sha256'])
                or not isinstance(facts['signature'], list) or len(facts['signature']) != 9
                or any(type(number) is not int or number < 0 for number in facts['signature'])):
            raise evidence.Unavailable('Exact current-owner facts required')
        evidence.catalog_fact(facts['catalog'], owner)
    return evidence.canonical_digest(value)


def families(records):
    """Validate each immutable extension; never join preexisting payload families."""
    if len(records) > evidence.REGISTRY_LIMIT:
        raise evidence.Unavailable('Derivative family history exceeds bounds')
    index, groups = {}, {}
    for key, row in sorted(records.items(), key=lambda item: item[1]['prior_revision']):
        if evidence.attestation(row) != key:
            raise evidence.Unavailable('Derivative predecessor digest changed')
        payload = row['inventory']['payload']
        if row['version'] == 1:
            group = index.get(payload, payload)
            groups.setdefault(group, {})[key] = row;index[payload] = group
        else:
            old, new = certificate(row['lineage']['plan'])
            before, after = old['payload'], new['payload']
            group = index.get(before, before);prior = groups.setdefault(group, {})
            if row['lineage']['parents'] != sorted(prior) or after in index:
                raise evidence.Unavailable('Missing ancestors or forbidden payload-family join')
            if prior:
                for kind in ('allowed', 'rejected'):
                    inherited = {evidence.canonical_digest(owner) for value in prior.values() for owner in value[kind]}
                    if inherited != {evidence.canonical_digest(owner) for owner in row[kind]}:
                        raise evidence.Unavailable('Derivative failed to inherit every owner claim')
            elif row['allowed'] != [row['lineage']['plan']['request']['owner']] or row['rejected']:
                raise evidence.Unavailable('Unknown derivative fabricated correction claims')
            prior[key] = row;index[before] = group;index[after] = group
        allowed = {evidence.canonical_digest(owner) for value in groups[group].values() for owner in value['allowed']}
        rejected = {evidence.canonical_digest(owner) for value in groups[group].values() for owner in value['rejected']}
        if allowed & rejected:
            raise evidence.Unavailable('Conflicting derivative family owner claims')
    return index, groups


def matched(records, payload):
    index, groups = families(records)
    group = index.get(payload)
    return groups.get(group, {})
