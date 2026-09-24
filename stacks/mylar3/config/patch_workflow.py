"""Checked native integration for workflow controls and durable observations."""
import ast
from pathlib import Path
import sys
from patch_queue_control import replace_once

MARKER='# homelab-workflow-v1'


def search(source):
    if MARKER in source:return source
    source='from mylar import workflow\n'+MARKER+'\n'+source
    for name,deco in [('search_init','observe_search'),('search_the_matrix','observe_provider'),('searcher','dispatch')]:
        source=replace_once(source,'def '+name+'(', '@workflow.'+deco+'\ndef '+name+'(')
    source=replace_once(source,'    prov_order = preferred\n', '    prov_order = workflow.provider_order(preferred, nzbprovider)\n    totalproviders = len(prov_order)\n')
    source=replace_once(source,"                #if it's not manually initiated, make sure it's not already downloaded/snatched.\n                if not manual:",
                        "                # Reserved handoffs bypass only the status check, not automatic dispatch validation.\n                if not manual and not workflow.in_handoff(issueid):")
    source=replace_once(source,'send_to_nzbget = ss.sender(nzbpath)', 'send_to_nzbget = workflow.sender(lambda: ss.sender(nzbpath), IssueID)')
    source=replace_once(source,'sendtosab = ss.sender()', 'sendtosab = workflow.sender(lambda: ss.sender(), IssueID)')
    ast.parse(source);return source


def search_queue(source):
    if MARKER in source:return source
    source='from mylar import workflow\n'+MARKER+'\n'+source
    source=replace_once(source,'    while True:\n','    while True:\n        workflow.tick(queue)\n')
    source=replace_once(source,'            gumbo_line = True', '            if workflow.safe_queue_item(item, queue):\n                continue\n\n            gumbo_line = True')
    ast.parse(source);return source


def ddl(source):
    if MARKER in source:return source
    source='from mylar import workflow\n'+MARKER+'\n'+source
    source=replace_once(source,'queue_control.begin(item, queue)', 'workflow.ddl_begin(queue_control.begin, item, queue)')
    source=replace_once(source,'            queue_control.finish(item, ddzstat)', '            queue_control.finish(item, ddzstat)\n            workflow.ddl_finished(item, ddzstat)')
    ast.parse(source);return source


def nzb_queue(source):
    if MARKER in source:return source
    source='from mylar import workflow_nzb\n'+MARKER+'\n'+source
    source=replace_once(source,'qu_retrieve = mylar.RETURN_THE_NZBQUEUE.get(True)',
                        'qu_retrieve = workflow_nzb.take(mylar.RETURN_THE_NZBQUEUE)')
    source=replace_once(source,'item = queue.get(True)', 'item = workflow_nzb.take(queue)')
    source=replace_once(source,'def cdh_monitor(queue, item, nzstat, readd=False):',
                        '@workflow_nzb.complete\ndef cdh_monitor(queue, item, nzstat, readd=False):')
    ast.parse(source);return source


def processing(source):
    if MARKER in source:return source
    source='from mylar import workflow\n'+MARKER+'\n'+source
    source=replace_once(source,"                if failchk[0]['mode'] == 'retry':",
                        "                if failchk[0]['mode'] == 'retry':\n                    workflow.release_failed(failchk[0]['issueid'])")
    ast.parse(source);return source


def server(source):
    if MARKER in source:return source
    source='from mylar import workflow, workflow_web\n'+MARKER+'\n'+source
    source=replace_once(source,'    def ddl_requeue(self, mode, id=None, issueid=None):','    @workflow.guard_requeue\n    def ddl_requeue(self, mode, id=None, issueid=None):')
    source=replace_once(source,'    def queueManage(self):','''    def activity(self):
        workflow_web.require_login()
        cherrypy.response.headers['Cache-Control'] = 'no-store'
        return serve_template(templatename='workflow.html', title='Activity')
    activity.exposed = True
    activity._cp_config = {'tools.sessions.on': True}

    def workflowStatus(self, issueid='', stage='', before=0):
        workflow_web.require_login()
        cherrypy.response.headers['Content-Type'] = 'application/json'
        cherrypy.response.headers['Cache-Control'] = 'no-store'
        try:
            return json.dumps(workflow_web.snapshot(issueid, stage, int(before or 0)))
        except (ValueError, TypeError):
            raise cherrypy.HTTPError(400, 'Invalid activity filter')
        except Exception:
            raise cherrypy.HTTPError(503, 'Workflow state is unavailable')
    workflowStatus.exposed = True
    workflowStatus._cp_config = {'tools.sessions.on': True}

    def workflowAction(self, csrf='', action='', **values):
        workflow_web.protect(csrf)
        cherrypy.response.headers['Content-Type'] = 'application/json'
        cherrypy.response.headers['Cache-Control'] = 'no-store'
        try:
            if any(not isinstance(v, str) or len(v)>2000 for v in values.values()):
                raise ValueError('Invalid action size')
            result = workflow_web.action(action, values)
        except (ValueError, TypeError, KeyError) as error:
            cherrypy.response.status = 409
            return json.dumps({'ok': False, 'error': str(error)[:160]})
        except Exception:
            cherrypy.response.status = 503
            return json.dumps({'ok': False, 'error': 'Workflow state is unavailable; refresh before retrying'})
        return json.dumps({'ok': True, 'result': result})
    workflowAction.exposed = True
    workflowAction._cp_config = {'tools.sessions.on': True}

    def queueManage(self):''')
    ast.parse(source);return source


def api(source):
    if MARKER in source:return source
    source='from mylar import workflow\n'+source
    source=replace_once(source,'    def _forceProcess(self, **kwargs):','    @workflow.force_process\n    def _forceProcess(self, **kwargs):')
    source=replace_once(source,"            mylar.PP_QUEUE.put({'nzb_name':    self.nzb_name,", "            workflow.processing_put(mylar.PP_QUEUE, {'nzb_name':    self.nzb_name,")
    source=replace_once(source,"                                'download_info': None})", "                                'download_info': None}, kwargs.get('workflow_command'))")
    source=replace_once(source,"'reportImportProblems',", "'reportImportProblems', 'workflowCommands', 'workflowAcknowledge',")
    source=replace_once(source,'    def _getHealth(self, **kwargs):','''    # homelab-workflow-v1
    def _workflowCommands(self, **kwargs):
        if not mylar.CONFIG.API_ENABLED or self.apikey != mylar.CONFIG.API_KEY:
            self.data = self._failureResponse('Primary API key required')
            return
        from mylar import workflow_web
        self.data = self._successResponse(workflow_web.commands())

    def _workflowAcknowledge(self, **kwargs):
        if not mylar.CONFIG.API_ENABLED or self.apikey != mylar.CONFIG.API_KEY:
            self.data = self._failureResponse('Primary API key required')
            return
        from mylar import workflow_web
        try:
            result = workflow_web.acknowledge(kwargs.get('command_id'), kwargs.get('phase'), kwargs.get('reason', ''))
        except (ValueError, TypeError, KeyError):
            self.data = self._failureResponse('Invalid workflow acknowledgement')
        else:
            self.data = self._successResponse(result)

    def _getHealth(self, **kwargs):''')
    source=replace_once(source,"            result = import_problems.report(kwargs.get('report'))", "            if kwargs.get('guidance') is not None:\n                from mylar import workflow_web\n                workflow_web.report_guidance(kwargs['guidance'])\n            result = import_problems.report(kwargs.get('report'))")
    ast.parse(source);return source


def template(name,source):
    if name=='base.html':
        if 'href="activity"' not in source:
            source=replace_once(source,'<a href="postProcessing">Post-processing</a>', '<a href="activity">Activity</a><a href="postProcessing">Post-processing</a>')
        if 'tt.value != "workflow"' not in source:
            source=replace_once(source,'tt.value != "post_processing"', 'tt.value != "workflow" && tt.value != "post_processing"')
    elif 'href="activity"' not in source:
        source=replace_once(source,'<div id="subhead_menu">','<div id="subhead_menu">\n<a id="menu_link_edit" href="activity">Activity</a>')
    return source


def main(directory):
    root=Path(directory);templates=root.parent/'data/interfaces/default'
    for name,patch in [('search.py',search),('queues/search.py',search_queue),('queues/ddl.py',ddl),('queues/nzb.py',nzb_queue),('process.py',processing),('webserve.py',server),('api.py',api)]:
        p=root/name;p.write_text(patch(p.read_text()))
    for name in ('base.html','manage.html','queue_management.html','import_problems.html','post_processing.html'):
        p=templates/name;p.write_text(template(name,p.read_text()))
    for name in ('workflow_store.py','workflow.py','workflow_web.py','workflow_nzb.py'):
        (root/name).write_text(Path(__file__).with_name(name).read_text())
    (templates/'workflow.html').write_text(Path(__file__).with_name('workflow.html').read_text())
    print('Workflow native boundaries, authenticated actions and navigation verified')


if __name__=='__main__':main(sys.argv[1])
