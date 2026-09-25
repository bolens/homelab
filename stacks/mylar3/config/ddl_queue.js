// Queue UI owns one active-status request at a time. Native queue actions stay explicit.
var ImportTimer=null, ddlLoading=false, ddlStopped=false, ddlMutating=false, ddlActiveId=null, ddlFresh=false, ddlRemoveId=null, ddlTableLoading=false;
function ddlText(value) { return $('<span>').text(value == null ? '' : String(value)).html(); }
function ddlSchedule() { clearTimeout(ImportTimer); if (!ddlStopped && !document.hidden) ImportTimer=setTimeout(activecheck,5000); }
function ddlRowActionsEnabled() { $('#queue_table button').prop('disabled',ddlTableLoading || ddlMutating); }
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
    .fail(function(){$('#ddl_action_notice').text('The request could not be confirmed. Refresh and check the item before retrying.');})
    .always(function(){ddlMutating=false;ddlActionsEnabled();ddlRowActionsEnabled();activecheck();});
}
function ddlRowActions(full) {
    var actions=[], status=full[3];
    if (['Completed','Failed','Downloading','Incomplete'].indexOf(status)!==-1) actions.push(['restart','Restart']);
    else if (status==='Queued') actions.push(['restart','Start']);
    if (status==='Incomplete') actions.push(['resume','Resume']);
    actions.push(['remove','Remove']);
    var box=$('<div>').addClass('ddl_row_actions');
    $.each(actions,function(_,a){$('<button type="button">').attr({'data-ddl-mode':a[0],'data-ddl-id':String(full[5])}).text(a[1]).appendTo(box);});
    var prompt=$('<span>').addClass('ddl_remove_prompt').prop('hidden',ddlRemoveId!==String(full[5]));
    $('<span>').text('Remove entry?').appendTo(prompt);
    $('<button type="button" data-ddl-confirm="remove">').text('Remove').appendTo(prompt);
    $('<button type="button" data-ddl-confirm="cancel">').text('Cancel').appendTo(prompt);
    box.children().prop('hidden',ddlRemoveId===String(full[5]));
    box.attr('data-ddl-id',String(full[5])).append(prompt);
    return $('<div>').append(box).html();
}
$(document).ready(function(){
    $('#ddl_refresh, #ddl_active_actions button, #ddl_restart_queue, #ddl_clear_queue').button();
    $('#ddl_refresh').on('click',activecheck);
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
    });
    $('#queue_table').on('preDraw.dt',function(){
        ddlRemoveId=null;
        $(this).find('.ddl_remove_prompt').prop('hidden',true);
        $(this).find('[data-ddl-mode]').prop('hidden',false);
    });
    $('#ddl_restart_queue').on('click',function(){ajaxcallit('restart_queue');});
    $('#ddl_clear_queue').on('click',function(){ajaxcallit('clear_queue');});
    $('#ddl_sort').on('change',function(){if(this.value==='custom')return;var order=this.value.split(':');$('#queue_table').DataTable().order([Number(order[0]),order[1]]).draw();});
    $('#queue_table').on('order.dt',function(){var order=$(this).DataTable().order()[0],value=order[0]+':'+order[1];$('#ddl_sort').val($('#ddl_sort option').filter(function(){return this.value===value;}).length ? value : 'custom');});
    document.addEventListener('visibilitychange',function(){if(document.hidden)clearTimeout(ImportTimer);else activecheck();});
    $(window).on('beforeunload',function(){ddlStopped=true;clearTimeout(ImportTimer);});
});
