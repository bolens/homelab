// Queue UI owns one active-status request at a time. Native queue actions stay explicit.
var ImportTimer=null, ddlLoading=false, ddlStopped=false, ddlMutating=false, ddlActiveId=null, ddlFresh=false, ddlRemoveId=null, ddlTableLoading=false;
var ddlCsrf=null, ddlTableFailed=false;
var ddlPreferenceRequest=null, ddlPreferenceTimer=null, ddlPreferenceSequence=0, ddlPreferenceAttempts=0;
var ddlPreferencesLoading=false, ddlPreferencesLoaded=false, ddlPreferencesPaused=false, ddlPreferenceBlocked=false;
function ddlPreferenceReadFailed(xhr) {
    var status=xhr && xhr.status;
    if (status===401 || status===403) {
        ddlPreferenceBlocked=true;
        $('#ddl_schedule_note').text('Sign in through Manage, then refresh status to load queue preferences.');
        return;
    }
    if (status>=400 && status<500 && status!==408 && status!==429) ddlPreferenceBlocked=true;
    if (ddlPreferenceBlocked || ddlPreferenceAttempts>=4) {
        $('#ddl_schedule_note').text('Queue preferences could not be loaded. Refresh status to retry.');
        return;
    }
    $('#ddl_schedule_note').text('Queue preferences are temporarily unavailable. Retrying automatically…');
    if (!ddlStopped && !ddlPreferencesPaused && !document.hidden) {
        clearTimeout(ddlPreferenceTimer);
        ddlPreferenceTimer=setTimeout(function(){ddlPreferenceTimer=null;ddlLoadPreferences(false);},Math.min(8000,2000*Math.pow(2,ddlPreferenceAttempts-1)));
    }
}
function ddlLoadPreferences(resetRetries) {
    if (ddlCsrf || ddlPreferencesLoading || ddlStopped || ddlPreferencesPaused || document.hidden) return;
    if (resetRetries) {ddlPreferenceAttempts=0;ddlPreferenceBlocked=false;clearTimeout(ddlPreferenceTimer);ddlPreferenceTimer=null;}
    if (ddlPreferenceBlocked || ddlPreferenceAttempts>=4) return;
    var sequence=++ddlPreferenceSequence;
    ddlPreferencesLoading=true;ddlPreferenceAttempts++;
    $('#ddl_schedule_note').text('Loading queue preferences…');
    ddlPreferenceRequest=$.ajax({url:'workflowStatus',dataType:'json',timeout:10000,cache:true}).done(function(data){
        if (sequence!==ddlPreferenceSequence || ddlStopped || ddlPreferencesPaused) return;
        var policy=data && data.policy;
        if (!data || data.error || typeof data.csrf!=='string' || !data.csrf || !policy || ['mixed','singles','packs','alternate'].indexOf(policy.ddl_kind)===-1 || ['fifo','newest','release_oldest','release_newest'].indexOf(policy.ddl_order)===-1 || typeof policy.ddl_paused!=='boolean') {ddlPreferenceReadFailed();return;}
        ddlCsrf=data.csrf;
        if (!ddlPreferencesLoaded) {
            $('#ddl_kind').val(policy.ddl_kind);$('#ddl_order').val(policy.ddl_order);$('#ddl_paused').prop('checked',policy.ddl_paused);
            $('#ddl_schedule_note').text('Applies to the next eligible download. Active transfers keep running; provider cooldowns still apply.');
        } else $('#ddl_schedule_note').text('Connection restored. Your current choices were kept; save to apply them.');
        ddlPreferencesLoaded=true;
        $('#ddl_schedule :input').prop('disabled',ddlMutating);$('#ddl_save_schedule').button('refresh');
    }).fail(function(xhr){if(sequence===ddlPreferenceSequence && !ddlStopped && !ddlPreferencesPaused)ddlPreferenceReadFailed(xhr);})
    .always(function(){if(sequence===ddlPreferenceSequence){ddlPreferencesLoading=false;ddlPreferenceRequest=null;}});
}
function ddlPausePreferences() {
    ddlPreferencesPaused=true;ddlPreferenceSequence++;
    clearTimeout(ddlPreferenceTimer);ddlPreferenceTimer=null;
    var request=ddlPreferenceRequest;
    if (ddlPreferencesLoading) ddlPreferenceAttempts=Math.max(0,ddlPreferenceAttempts-1);
    ddlPreferencesLoading=false;ddlPreferenceRequest=null;
    if (request) request.abort();
}
function ddlResumePreferences() {ddlPreferencesPaused=false;ddlLoadPreferences(false);}
function ddlSchedulingAction(action,values) {
    if (!ddlCsrf || ddlMutating) return;
    ddlMutating=true;ddlRowActionsEnabled();$('#ddl_schedule :input').prop('disabled',true);$('#ddl_save_schedule').button('refresh');
    $.ajax({url:'workflowAction',type:'POST',data:$.extend({csrf:ddlCsrf,action:action},values),dataType:'json',timeout:15000})
    .done(function(data){$('#ddl_schedule_note').text(data && data.ok ? (action==='ddl_next' ? 'This queued item will run next when its provider is available.' : 'Preferences saved. The active download is unchanged.') : 'Change was not confirmed. Reload before retrying.');})
    .fail(function(){$('#ddl_schedule_note').text('Change was not confirmed. Refresh status to reconnect before deciding whether to save again.');ddlCsrf=null;})
    .always(function(){ddlMutating=false;ddlRowActionsEnabled();$('#ddl_schedule :input').prop('disabled',!ddlCsrf);$('#ddl_save_schedule').button('refresh');activecheck();});
}
function ddlText(value) { return $('<span>').text(value == null ? '' : String(value)).html(); }
function ddlAge(seconds) {
    if (seconds == null || !isFinite(Number(seconds))) return 'Unknown';
    seconds=Math.max(0,Math.floor(Number(seconds)));
    if (seconds<60) return seconds+'s ago';
    if (seconds<3600) return Math.floor(seconds/60)+'m ago';
    if (seconds<86400) return Math.floor(seconds/3600)+'h ago';
    return Math.floor(seconds/86400)+'d ago';
}
function ddlReviewLink(full) {
    if (full[3]==='Completed') return {label:'Review import',href:'postProcessing#pp_work'};
    if (full[3]==='NZB handoff') return {label:'Review handoff',href:'activity#wf_handoff'};
    if (full[3]==='Failed') return {label:'Review problems',href:'importProblems'};
    return null;
}
function ddlDecorateRows() {
    var table=$('#queue_table').DataTable();
    var labels=['Series','Size','Provider','Progress','Download status','Updated','Actions','Received','Speed','Last progress','Download / import status'];
    table.rows({page:'current'}).every(function(){
        var full=this.data(),index=this.index(),status=full[3];
        $(this.node()).attr('data-ddl-state',status);
        $.each(labels,function(column,label){$(table.cell(index,column).node()).attr('data-label',label);});
        var state=$('<span>').addClass('ddl_status_badge').text(status==='Completed' ? 'Downloaded' : status);
        $(table.cell(index,4).node()).empty().append(state);
        var age=(full[9] || {}).last_progress_seconds;
        $(table.cell(index,9).node()).text(ddlAge(age)).attr('title',age==null ? 'No progress observation recorded' : age+' seconds since progress');
    });
}
function ddlSchedule() { clearTimeout(ImportTimer); if (!ddlStopped && !document.hidden) ImportTimer=setTimeout(activecheck,5000); }
function ddlRowActionsEnabled() { $('#queue_table button').prop('disabled',ddlTableLoading || ddlMutating || ddlTableFailed); }
function ddlActionsEnabled() { $('#ddl_active_actions button').prop('disabled',!ddlFresh || ddlMutating || ddlActiveId==null); }
function ddlFailed() {
    ddlFresh=false;ddlActionsEnabled();
    $('#ddl_notice').attr('data-stale','true').text('Status could not be refreshed. The last snapshot is retained. Refresh to retry or sign in through Manage.');
}
function activecheck() {
    if (ddlLoading || ddlStopped || ddlMutating) return;
    clearTimeout(ImportTimer);ddlLoading=true;$('#ddl_refresh').prop('disabled',true);
    $.ajax({url:'check_ActiveDDL',dataType:'json',timeout:10000,cache:true})
    .done(function(obj) {
        if (!obj || typeof obj.status!=='string' || obj.error) {ddlFailed();return;}
        ddlFresh=true;ddlActiveId=obj.a_id == null ? null : String(obj.a_id);
        var downloading=obj.status.indexOf('Downloading')===0;
        var hasItem=ddlActiveId!==null;
        $('#ddl_notice').attr('data-stale','false').text('Status is current. Updates every five seconds.');
        $('#ddl_state').text(downloading ? 'Downloading' : hasItem ? 'Needs attention' : 'Idle');
        $('#ddl_idle').prop('hidden',downloading).text(hasItem ? obj.status.replace(/<br\s*\/?\s*>|<\/br>/gi,' ') : 'No active DDL download. Queued items and previous downloads appear below.');
        $('#ddl_transfer').prop('hidden',!downloading);
        $('#ddl_series').text(obj.a_series || 'Current download');$('#ddl_filename').text(obj.a_filename || 'Filename not available yet');
        $('#ddl_size').text(obj.a_size || 'Unknown');$('#ddl_checked').text(new Date().toLocaleTimeString());
        var raw=String(obj.percent), known=downloading && obj.status.indexOf('unknown')===-1 && /^\d+(\.\d+)?%$/.test(raw);
        if (known) {var percent=Math.max(0,Math.min(100,parseFloat(raw)));$('#ddl_progress').attr('value',percent);$('#ddl_percent').text(percent+'%');}
        else {$('#ddl_progress').removeAttr('value');$('#ddl_percent').text('Size unknown');}
        $('#ddl_active_actions').prop('hidden',!hasItem).find('[data-ddl-mode=resume]').prop('hidden',!downloading);
        ddlActionsEnabled();
        // homelab-queue-progress-v1: preserve table page and scroll position.
        // Keep the focused inline confirmation intact while active status continues.
        if ($('#queue_table').length && ddlRemoveId===null && !ddlTableLoading) {$('#queue_table').DataTable().ajax.reload(null, false);}
    }).fail(ddlFailed).always(function(){ddlLoading=false;$('#ddl_refresh').prop('disabled',false);ddlSchedule();});
}
function ajaxcallit(mode,id,confirmed) {
    if (ddlMutating) return;
    if (mode==='remove' && !confirmed) return;
    if ((mode==='clear_queue' || mode==='abort') && !window.confirm(mode==='clear_queue' ? 'Remove all queued entries? Active and completed downloads stay in place.' : 'Abort this download?')) return;
    ddlMutating=true;clearTimeout(ImportTimer);ddlActionsEnabled();ddlRowActionsEnabled();
    $('#ddl_action_notice').text('Sending request…');
    $.ajax({url:'ddl_requeue',data:{mode:mode,id:id},dataType:'json',timeout:15000})
    .done(function(data){$('#ddl_action_notice').text(data && data.status===true && !data.error ? data.message || 'Request accepted.' : 'The request was not confirmed. Refresh and check the item before retrying.');})
    .fail(function(xhr){$('#ddl_action_notice').text(xhr && xhr.status===409 ? 'This entry is held or changed. Review its NZB handoff in Activity, then refresh before removing it.' : 'The request could not be confirmed. Refresh and check the item before retrying.');})
    .always(function(){ddlMutating=false;ddlActionsEnabled();ddlRowActionsEnabled();activecheck();});
}
function ddlRowActions(full) {
    var actions=[], status=full[3];
    if (['Completed','Failed','Downloading','Incomplete'].indexOf(status)!==-1) actions.push(['restart','Restart']);
    else if (status==='Queued') actions.push(['next','Download next']);
    if (status==='Incomplete') actions.push(['resume','Resume']);
    actions.push(['remove','Remove']);
    var box=$('<div>').addClass('ddl_row_actions');
    var review=ddlReviewLink(full);
    if (review) $('<a>').addClass('ddl_review_link').attr('href',review.href).text(review.label).appendTo(box);
    $.each(actions,function(_,a){$('<button type="button">').attr({'data-ddl-mode':a[0],'data-ddl-id':String(full[5])}).text(a[1]).appendTo(box);});
    var prompt=$('<span>').addClass('ddl_remove_prompt').prop('hidden',ddlRemoveId!==String(full[5]));
    $('<span>').text(status==='NZB handoff' ? 'Remove DDL entry? Pending NZB searches are cancelled. Accepted NZB downloads continue. Uncertain handoffs require Activity review.' : 'Remove entry?').appendTo(prompt);
    $('<button type="button" data-ddl-confirm="remove">').text('Remove').appendTo(prompt);
    $('<button type="button" data-ddl-confirm="cancel">').text('Cancel').appendTo(prompt);
    box.children('[data-ddl-mode]').prop('hidden',ddlRemoveId===String(full[5]));
    box.attr('data-ddl-id',String(full[5])).append(prompt);
    return $('<div>').append(box).html();
}
$(document).ready(function(){
    $('#ddl_refresh, #ddl_active_actions button, #ddl_restart_queue, #ddl_clear_queue').button();
    $('#ddl_save_schedule').button();
    ddlLoadPreferences(false);
    $('#ddl_schedule').on('submit',function(event){event.preventDefault();ddlSchedulingAction('policy',{values:JSON.stringify({ddl_kind:$('#ddl_kind').val(),ddl_order:$('#ddl_order').val(),ddl_paused:$('#ddl_paused').prop('checked')})});});
    $('#ddl_refresh').on('click',function(){ddlLoadPreferences(true);activecheck();});
    $('#ddl_active_actions').on('click','button',function(){if(ddlFresh && ddlActiveId!==null)ajaxcallit($(this).attr('data-ddl-mode'),ddlActiveId);});
    function closeRemove(box) {
        ddlRemoveId=null;
        box.children('[data-ddl-mode]').prop('hidden',false);
        box.find('.ddl_remove_prompt').prop('hidden',true);
        box.find('[data-ddl-mode=remove]').focus();
    }
    $('#queue_table').on('click','button[data-ddl-mode]',function(){
        if (ddlMutating || ddlTableLoading) return;
        var button=$(this),mode=button.attr('data-ddl-mode'),id=button.attr('data-ddl-id');
        if (mode==='next') {ddlSchedulingAction('ddl_next',{ddl_id:id});return;}
        if (mode!=='remove') {ajaxcallit(mode,id);return;}
        $('#queue_table .ddl_remove_prompt:visible').each(function(){closeRemove($(this).parent());});
        ddlRemoveId=id;
        var box=button.closest('.ddl_row_actions');
        box.children('[data-ddl-mode]').prop('hidden',true);
        box.find('.ddl_remove_prompt').prop('hidden',false).find('[data-ddl-confirm=cancel]').focus();
    });
    $('#queue_table').on('click','button[data-ddl-confirm]',function(){
        var box=$(this).closest('.ddl_row_actions'),id=box.attr('data-ddl-id'),remove=$(this).attr('data-ddl-confirm')==='remove';
        closeRemove(box);
        if (remove) ajaxcallit('remove',id,true);
    }).on('keydown','.ddl_remove_prompt',function(event){
        if(event.key==='Escape'){event.preventDefault();closeRemove($(this).parent());}
    });
    $('#queue_table').on('processing.dt',function(event,settings,processing){
        ddlTableLoading=processing;ddlRowActionsEnabled();
        $(this).attr('aria-busy',processing ? 'true' : 'false');
        $('#queue_table_processing').attr('aria-hidden','true');
        $('#ddl_table_refresh').text(processing ? 'Updating queue…' : '');
    });
    $('#queue_table').on('init.dt',function(){
        $(this).DataTable().columns([7,8,9]).visible($('#ddl_show_details').prop('checked'),false);
        $(this).DataTable().columns.adjust();
        ddlDecorateRows();
    }).on('draw.dt',ddlDecorateRows);
    $('#ddl_show_details').on('change',function(){
        var table=$('#queue_table').DataTable();
        table.columns([7,8,9]).visible(this.checked,false);table.columns.adjust();ddlDecorateRows();
    });
    $('#queue_table').on('preDraw.dt',function(){
        ddlRemoveId=null;
        $(this).find('.ddl_remove_prompt').prop('hidden',true);
        $(this).find('[data-ddl-mode]').prop('hidden',false);
    });
    $('#ddl_restart_queue').on('click',function(){ajaxcallit('restart_queue');});
    $('#ddl_clear_queue').on('click',function(){ajaxcallit('clear_queue');});
    $('#ddl_sort').on('change',function(){if(this.value==='custom')return;var order=this.value.split(':');$('#queue_table').DataTable().order([Number(order[0]),order[1]]).draw();});
    $('#queue_table').on('order.dt',function(){
        var order=$(this).DataTable().order()[0],value=order[0]+':'+order[1];
        $('#ddl_sort').val($('#ddl_sort option').filter(function(){return this.value===value;}).length ? value : 'custom');
        $('#ddl_sort_note').text(value==='11:asc' ? 'Estimated from saved preferences and Download next. Active first, eligible downloads before cooldowns, then history. Updates automatically.' : 'Changes the table view only.');
    });
    document.addEventListener('visibilitychange',function(){if(document.hidden){clearTimeout(ImportTimer);ddlPausePreferences();}else{ddlResumePreferences();activecheck();}});
    $(window).on('beforeunload pagehide',function(){ddlStopped=true;clearTimeout(ImportTimer);ddlPausePreferences();});
    $(window).on('pageshow',function(event){if(event.originalEvent && event.originalEvent.persisted){ddlStopped=false;ddlResumePreferences();activecheck();}});
});
