"""Install finite cache admission without weakening native DDL generation CAS."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once, function_span
MARKER = '# homelab-cache-admission-v1'


def configuration(source):
    if MARKER in source:
        if source.count(MARKER) != 1: raise ValueError('Cache configuration marker changed')
        return source
    source = replace_once(source, "    'DDL_LOCATION': (str, 'DDL', None),", "    " + MARKER + "\n    'DDL_CACHE_MAX_GIB': (int, 'DDL', 20),\n    'DDL_CACHE_MIN_FREE_GIB': (int, 'DDL', 5),\n    'DDL_LOCATION': (str, 'DDL', None),")
    source = replace_once(source, '        for name, value in list(kwargs.items()):\n', "        from mylar import cache_admission\n        cache_admission.validate_update(kwargs)\n        for name, value in list(kwargs.items()):\n")
    ast.parse(source); return source


def getcomics(source):
    if MARKER in source: return source
    source = 'from mylar import cache_admission\n' + source
    body = function_span(source, 'downloadit')
    changed = replace_once(body, '        except requests.exceptions.Timeout as e:', '        '+MARKER+'\n        except cache_admission.Held:\n            mylar.DDL_LOCK = False\n            raise\n        except requests.exceptions.Timeout as e:')
    source = replace_once(source, body, changed)
    source = metadata_method(source, 'downloadit', 'id')
    source = replace_once(source, 'verified_transfer.receive(t, dst_path, resume, id)', 'verified_transfer.receive(t, dst_path, resume, id, original_generation=_original_ddl)')
    body = function_span(source, 'zip_zip')
    changed = replace_once(body, '        except Exception:', '        except cache_admission.Held:\n            raise\n        except Exception:')
    source = replace_once(source, body, changed)
    ast.parse(source); return source


def worker(source):
    if MARKER in source: return source
    if 'def _ddl_status_update(' not in source: raise ValueError('Native original generation CAS must be installed first')
    source = 'from mylar import cache_admission\n' + source
    old = "            except Exception:\n                mylar.DDL_LOCK = False\n                ddzstat = {'success': False, 'filename': None, '_queue_reason': 'Provider request failed'}"
    new = "            "+MARKER+"\n            except cache_admission.Held as exc:\n                mylar.DDL_LOCK = False\n                _ddl_cache_requeue(myDB, status_original, item, queue, str(exc))\n                continue\n"+old
    # The six existing status sites stay exact; this separate cache helper reuses
    # their original-generation CAS rather than creating another status upsert.
    source = replace_once(source, old, new)
    source += "\n\ndef _ddl_cache_requeue(database, original, item, queue, reason):\n    if _ddl_status_update(database, original, {'status': 'Queued'}) is None:\n        queue_control.clear_active(item['id'])\n        return False\n    queue_control.cache_held(item, queue, reason, refund=True)\n    return True\n"
    ast.parse(source); return source


def direct_provider(source, method, chunk_size, owner):
    if MARKER in source: return source
    source = 'from mylar import cache_admission, verified_transfer\n' + source
    body = function_span(source, method)
    old = "            with open(filepath, 'wb') as f:\n                for chunk in response.iter_content(chunk_size=" + str(chunk_size) + "):\n                    if chunk:\n                        f.write(chunk)\n                        f.flush()"
    new = "            " + MARKER + "\n            verified_transfer.receive(response, filepath, None, " + owner + ")"
    body2 = replace_once(body, old, new)
    body2 = replace_once(body2, '        except Exception as e:', '        except cache_admission.Held:\n            raise\n        except Exception as e:')
    source = replace_once(source, body, body2)
    source = provider_metadata(source, 'mediafire' if method == 'mediafire_dl' else 'pixeldrain')
    ast.parse(source); return source


def mega_provider(source):
    if MARKER in source: return source
    source = 'from mylar import cache_admission, verified_transfer\n' + source
    body = function_span(source, 'ddl_download')
    body2 = replace_once(body, '\n        except Exception as e:', '\n        '+MARKER+'\n        except cache_admission.Held:\n            raise\n        except Exception as e:')
    body2 = replace_once(body2, '                    filepath = og_filepath.replace(filepath)', "                    if filepath != og_filepath:\n                        if os.path.lexists(filepath):\n                            raise cache_admission.Held('Existing anchored Mega original is retained')\n                        os.link(og_filepath, filepath, follow_symlinks=False)\n                        os.unlink(og_filepath)\n                    verified_transfer.checked(filepath)")
    body2 = replace_once(body2, '                except Exception as e:', '                except cache_admission.Held:\n                    raise\n                except Exception as e:')
    old = "            checkdirectory = mylar.filechecker.validateAndCreateDirectory(\n                self.dl_location, True\n            )"
    new = "            with cache_admission.allocation(Path(self.dl_location).parent, 0, nodes=1):\n                checkdirectory = mylar.filechecker.validateAndCreateDirectory(\n                    self.dl_location, True\n                )"
    body2 = replace_once(body2, old, new)
    source = replace_once(source, body, body2)
    source = provider_metadata(source, 'mega')
    ast.parse(source); return source


def mega_library(source):
    if MARKER in source: return source
    body = function_span(source, '_download_file')
    begin = "        with tempfile.NamedTemporaryFile(mode='w+b',\n                                         prefix='megapy_',\n                                         delete=False) as temp_output_file:"
    replacement = "        "+MARKER+"\n        from mylar import cache_admission\n        if type(file_size) is not int or file_size < 0 or dest_path == '':\n            raise cache_admission.Held('Invalid Mega cache allocation')\n        with cache_admission.allocation(Path(dest_path), file_size, nodes=1) as reservation, cache_admission.temporary(reservation) as temp_output_file:"
    changed = replace_once(body, begin, replacement)
    changed = replace_once(changed, '                temp_output_file.write(chunk)', '                reservation.before_write(len(chunk))\n                temp_output_file.write(chunk)')
    changed = replace_once(changed, '            shutil.move(temp_output_file.name, output_path)', '            output_path = temp_output_file.promote(file_name, file_size)')
    source = replace_once(source, body, changed)
    ast.parse(source); return source


def metadata_method(source, name, owner, optional=False):
    body = function_span(source, name)
    lines = body.splitlines(keepends=True)
    if optional:
        if not lines[0].rstrip().endswith('):'): raise ValueError('Provider method signature changed')
        lines[0] = lines[0].rstrip()[:-2] + ', original_generation=None):\n'
        guard = "        _original_ddl = original_generation if original_generation is not None else verified_transfer.ddl_generation(db.DBConnection(), " + owner + ")\n        verified_transfer.ddl_metadata(db.DBConnection(), _original_ddl)\n"
    else:
        guard = "        _original_ddl = verified_transfer.ddl_generation(db.DBConnection(), " + owner + ")\n"
    lines.insert(1, guard); changed = ''.join(lines)
    tree = ast.parse(changed.lstrip())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'upsert']
    if len(calls) != 1: raise ValueError('Provider metadata site changed')
    call = calls[0]
    if not isinstance(call.args[0], ast.Constant) or call.args[0].value != 'ddl_info': raise ValueError('Provider metadata table changed')
    old = ast.get_source_segment(changed.lstrip(), call)
    values = ast.get_source_segment(changed.lstrip(), call.args[1])
    changed = replace_once(changed, old, 'verified_transfer.ddl_metadata(myDB, _original_ddl, '+values+')')
    return replace_once(source, body, changed)


def provider_metadata(source, kind):
    if kind == 'mega':
        source = metadata_method(source, 'ddl_download', 'id')
        source = metadata_method(source, 'testing', 'self.id', optional=True)
        source = replace_once(source, 'progress_hook=self.testing)', 'progress_hook=lambda data: self.testing(data, _original_ddl))')
        source = replace_once(source, 'filename, self.testing)', 'filename, lambda data: self.testing(data, _original_ddl))')
    elif kind == 'mediafire':
        source = metadata_method(source, 'ddl_download', 'id')
        source = metadata_method(source, 'mediafire_dl', 'id', optional=True)
        source = replace_once(source, 'self.mediafire_dl(url, id, fileinfo, issueid)', 'self.mediafire_dl(url, id, fileinfo, issueid, _original_ddl)')
        source = replace_once(source, 'verified_transfer.receive(response, filepath, None, id)', 'verified_transfer.receive(response, filepath, None, id, original_generation=_original_ddl)')
    else:
        source = metadata_method(source, 'ddl_download', 'id')
        source = metadata_method(source, 'pixel_ddl', 'self.id', optional=True)
        source = replace_once(source, 'self.pixel_ddl(file_id, file_info, issueid)', 'self.pixel_ddl(file_id, file_info, issueid, _original_ddl)')
        source = replace_once(source, 'verified_transfer.receive(response, filepath, None, self.id)', 'verified_transfer.receive(response, filepath, None, self.id, original_generation=_original_ddl)')
    ast.parse(source); return source


def main(directory):
    root = Path(directory)
    targets = {'config.py': configuration, 'getcomics.py': getcomics, 'queues/ddl.py': worker,
               'downloaders/mediafire.py': lambda s: direct_provider(s, 'mediafire_dl', 4096, 'id'),
               'downloaders/pixeldrain.py': lambda s: direct_provider(s, 'pixel_ddl', 1024, 'self.id'),
               'downloaders/mega.py': mega_provider}
    changed = {name: transform((root/name).read_text()) for name, transform in targets.items()}
    library = root.parent / 'lib/mega/mega.py'
    changed_library = mega_library(library.read_text())
    for name, source in changed.items():
        if (root/name).read_text() != source: (root/name).write_text(source)
    if library.read_text() != changed_library: library.write_text(changed_library)
    for name in ('cache_admission.py', 'verified_transfer.py', 'queue_control.py', 'pack_intake.py'):
        (root/name).write_bytes(Path(__file__).with_name(name).read_bytes())

if __name__ == '__main__': main(sys.argv[1])
