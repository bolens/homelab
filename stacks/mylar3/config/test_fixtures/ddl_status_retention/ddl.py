from mylar import ddl_schedule as queue_schedule
# homelab-ddl-scheduling-v1
from mylar import workflow
# homelab-workflow-v1
from mylar import queue_control, verified_transfer
import requests
"""DDL queue worker functions."""

import datetime
import os
import re
import time

import mylar
from .. import logger, helpers
from mylar import db, getcomics
from mylar.downloaders import mediafire, mega, pixeldrain


def ddl_downloader(queue):
    myDB = db.DBConnection()
    # homelab-queue-control-v1
    link_type_failure = {}
    queue_control.recover(queue)
    while True:
        if mylar.DDL_LOCK is True:
            time.sleep(5)

        elif mylar.DDL_LOCK is False and queue.qsize() >= 1:
            item = queue_schedule.take(queue)
            if item is None:
                time.sleep(1)
                continue

            if item == 'exit':
                logger.info('Cleaning up workers for shutdown')
                break

            if not workflow.ddl_begin(queue_control.begin, item, queue):
                continue

            queue_schedule.started(item)

            if item['id'] not in mylar.DDL_QUEUED:
                mylar.DDL_QUEUED.append(item['id'])

            try:
                link_type_failure[item['id']].append(item['link_type_failure'])
            except Exception:
                pass

            logger.info('Now loading request from DDL queue: %s' % item['series'])

            ctrlval = {'id':      item['id']}
            val = {'status':       'Downloading',
                   'updated_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
            myDB.upsert('ddl_info', val, ctrlval)

            # homelab-ddl-result-ownership-v1
            ddzstat = {'success': False, 'filename': None,
                       '_queue_reason': 'Unsupported download provider'}
            try:
                if item['site'] == 'DDL(GetComics)':
                    try:
                        remote_filesize = item['remote_filesize']
                    except Exception:
                        try:
                            remote_filesize = helpers.human2bytes(re.sub('/s', '', item['size'][:-1]).strip())
                        except Exception:
                            remote_filesize = 0

                    if any([item['link_type'] == 'GC-Main', item['link_type'] in ('GC-Mirror', 'GC_Mirror')]):
                        ddz = getcomics.GC()
                        ddzstat = ddz.downloadit(item['id'], item['link'], item['mainlink'], item['resume'], item['issueid'], remote_filesize)
                    elif item['link_type'] == 'GC-Mega':
                        meganz = mega.MegaNZ()
                        ddzstat = meganz.ddl_download(item['link'], None, item['id'], item['issueid'], item['link_type'])
                    elif item['link_type'] == 'GC-Media':
                        mediaf = mediafire.MediaFire()
                        ddzstat = mediaf.ddl_download(item['link'], item['id'], item['issueid'])
                    elif item['link_type'] == 'GC-Pixel':
                        pdrain = pixeldrain.PixelDrain()
                        ddzstat = pdrain.ddl_download(item['link'], item['id'], item['issueid'])

                elif item['site'] == 'DDL(External)':
                    meganz = mega.MegaNZ()
                    ddzstat = meganz.ddl_download(item['link'], item['filename'], item['id'], item['issueid'], item['link_type'])

            except Exception:
                mylar.DDL_LOCK = False
                ddzstat = {'success': False, 'filename': None, '_queue_reason': 'Provider request failed'}
            ddzstat = verified_transfer.validate_result(ddzstat, item)

            queue_control.finish(item, ddzstat)
            workflow.ddl_finished(item, ddzstat)

            if ddzstat['success'] is True:
                tdnow = datetime.datetime.now()
                nval = {'status':  'Completed',
                        'updated_date': tdnow.strftime('%Y-%m-%d %H:%M')}
                myDB.upsert('ddl_info', nval, ctrlval)

            if all([ddzstat['success'] is True, mylar.CONFIG.POST_PROCESSING is True]):
                try:
                    if ddzstat['filename'] is None:
                        logger.info('%s successfully downloaded - now initiating post-processing for %s.' % (os.path.basename(ddzstat['path']), ddzstat['path']))
                        mylar.PP_QUEUE.put({'nzb_name':     os.path.basename(ddzstat['path']),
                                            'nzb_folder':   ddzstat['path'],
                                            'failed':       False,
                                            'issueid':      None,
                                            'comicid':      item['comicid'],
                                            'apicall':      True,
                                            'ddl':          True,
                                            'download_info': {'provider': 'DDL', 'id': item['id']}})
                    else:
                        logger.info('%s successfully downloaded - now initiating post-processing for %s' % (ddzstat['filename'], ddzstat['path']))
                        mylar.PP_QUEUE.put({'nzb_name':     ddzstat['filename'],
                                            'nzb_folder':   ddzstat['path'],
                                            'failed':       False,
                                            'issueid':      item['issueid'],
                                            'comicid':      item['comicid'],
                                            'apicall':      True,
                                            'ddl':          True,
                                            'download_info': {'provider': 'DDL', 'id': item['id']}})
                except Exception as e:
                    logger.error('process error: %s [%s]' %(e, ddzstat))

                mylar.DDL_QUEUED.remove(item['id'])
                try:
                    link_type_failure.pop(item['id'], None)
                except KeyError:
                    pass

                try:
                    pck_cnt = 0
                    if item['comicinfo'][0]['pack'] is True:
                        logger.fdebug('[PACK DETECTION] Attempting to remove issueids from the pack dont-queue list')
                        for x,y in dict(mylar.PACK_ISSUEIDS_DONT_QUEUE).items():
                            if y == item['id']:
                                pck_cnt +=1
                                del mylar.PACK_ISSUEIDS_DONT_QUEUE[x]
                        logger.fdebug('Successfully removed %s issueids from pack queue list as download is completed.' % pck_cnt)
                except Exception:
                    pass

                ddl_cleanup(item['id'])

            elif all([ddzstat['success'] is True, mylar.CONFIG.POST_PROCESSING is False]):
                path = ddzstat['path']
                if ddzstat['filename'] is not None:
                    path = os.path.join(path, ddzstat['filename'])
                logger.info('File successfully downloaded. Post Processing is not enabled - item retained here: %s' % (path,))
                ddl_cleanup(item['id'])
            else:
                if item['site'] == 'DDL(GetComics)':
                    try:
                        ddzstat['links_exhausted']
                    except KeyError:
                        logger.info('[Status: %s] Failed to download item from %s : %s ' % (ddzstat['success'], item['link_type'], ddzstat))
                        try:
                            link_type_failure[item['id']].append(item['link_type'])
                        except KeyError:
                            link_type_failure[item['id']] = [item['link_type']]
                        logger.fdebug('[%s] link_type_failure: %s' % (item['id'], link_type_failure))
                        ggc = getcomics.GC(comicid=item['comicid'], issueid=item['issueid'], oneoff=item['oneoff'])
                        # homelab-ddl-fix-v1
                        # homelab-worker-recovery-v1
                        try:
                            retry = ggc.parse_downloadresults(item['id'], item['mainlink'], item['comicinfo'], item['packinfo'], link_type_failure[item['id']])
                        except (requests.RequestException, OSError):
                            attempts = item.get('_mirror_network_retries', 0) + 1
                            logger.warn('DDL mirror lookup failed; retry attempt %s of 3', attempts)
                            if attempts <= 3:
                                item['_mirror_network_retries'] = attempts
                                myDB.upsert('ddl_info', {'status': 'Queued'}, ctrlval)
                                queue.put(item)
                                time.sleep(5)
                            else:
                                # homelab-ddl-lookup-terminal-v1
                                queue_control.stop_retry(item, lookup_failed=True)
                                myDB.upsert('ddl_info', {'status': 'Failed'}, ctrlval)
                                helpers.reverse_the_pack_snatch(item['id'], item['comicid'])
                                link_type_failure.pop(item['id'], None)
                                if item['id'] in mylar.DDL_QUEUED:
                                    mylar.DDL_QUEUED.remove(item['id'])
                            continue
                        if isinstance(retry, dict) and 'links_exhausted' in retry:
                            # homelab-ddl-terminal-v1
                            queue_control.stop_retry(item, retry)
                            myDB.upsert('ddl_info', {'status': 'Failed'}, ctrlval)
                            helpers.reverse_the_pack_snatch(item['id'], item['comicid'])
                            link_type_failure.pop(item['id'], None)
                            if item['id'] in mylar.DDL_QUEUED:
                                mylar.DDL_QUEUED.remove(item['id'])
                            ddl_cleanup(item['id'])
                    else:
                        logger.info('[REDO] Exhausted all available links [%s] for issueid %s and was not able to download anything' % (link_type_failure[item['id']], item['issueid']))
                        queue_control.stop_retry(item, ddzstat)
                        nval = {'status':  'Failed',
                                'updated_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
                        myDB.upsert('ddl_info', nval, ctrlval)
                        helpers.reverse_the_pack_snatch(item['id'], item['comicid'])
                        link_type_failure.pop(item['id'], None)
                        ddl_cleanup(item['id'])
                else:
                    logger.info('[Status: %s] Failed to download item from %s : %s ' % (ddzstat['success'], item['site'], ddzstat))
                    myDB.action('DELETE FROM ddl_info where id=?', [item['id']])
                    mylar.search.FailedMark(item['issueid'], item['comicid'], item['id'], ddzstat['filename'], item['site'])
        else:
            time.sleep(5)


def ddl_cleanup(record_id):
    if getattr(mylar.CONFIG, 'KEEP_HTML_CACHE', False):
        logger.fdebug('[HTML-cleanup] KEEP_HTML_CACHE enabled; skipping removal for %s.', record_id)
        return

    tlnk = 'getcomics-%s.html' % record_id
    cache_path = os.path.join(mylar.CONFIG.CACHE_DIR, 'html_cache', tlnk)
    try:
        os.remove(cache_path)
    except FileNotFoundError:
        logger.fdebug('[HTML-cleanup] %s not found in html_cache. Nothing to remove.', tlnk)
    except Exception as e:
        logger.fdebug('[HTML-cleanup] Unable to remove %s from html_cache: %s. '
                      'Manual removal required or set `cleanup_cache=True` in the config.ini to '
                      'clean cache items on every startup. If this was a Retry - ignore this.',
                      tlnk, e)
