// History review keeps native retry, mark and clear endpoints.
$(function() {
    $('#history_problems, #history_logs').button();
    var table=$('#history_table');
    function selectedCount() {
        var issues=Object.create(null);
        table.find('tbody input[type=checkbox]:checked').each(function(){issues[this.name]=true;});
        return Object.keys(issues).length;
    }
    function selection() {
        var count=selectedCount();
        $('#history_selected').text(count+' issues selected on this page');
        $('#history_apply, #history_bulk_action').prop('disabled',count===0);
    }
    $('#markissues').on('submit',function(event){event.preventDefault();});
    $('#history_select_page').on('click',function(){lastChecked=null;table.find('tbody input[type=checkbox]').prop('checked',true);selection();});
    $('#history_clear_selection').on('click',function(){lastChecked=null;table.find('tbody input[type=checkbox]').prop('checked',false);selection();});
    table.on('change click','input[type=checkbox]',selection);
    table.on('draw.dt',function(){
        lastChecked=null;
        var api=table.DataTable();
        api.rows({page:'current'}).every(function(){
            var row=$(this.node()),data=this.data(),cells=row.children('td');
            var labels=['Select','Date added','Comic','Issue','Status','Provider','Actions'];
            cells.each(function(i){$(this).attr('data-label',labels[i]);});
            cells.eq(0).find('input').attr('aria-label','Select '+data[1]+' issue '+data[2]);
            row.attr('data-history-status',data[3]);
            cells.eq(4).empty().append($('<span>').addClass('history_badge').text(data[3]));
            cells.eq(6).find('.history_activity').remove();
            var issue=String(data[4]);
            if (/^\d{1,20}$/.test(issue)) $('<a>').addClass('history_activity').attr('href','activity?issueid='+encodeURIComponent(issue)+'#wf_history').text('View activity').prependTo(cells.eq(6));
            cells.eq(6).find('#retry').text('Retry search').attr('title','Search again for this issue');
            if (!data[6]) cells.eq(5).text('Not recorded');
        });
        selection();
    });
    $('#history_apply').on('click',function(){
        var action=$('#history_bulk_action').val();
        var count=selectedCount();
        if (!count || !action) return;
        var question=action==='Retry' ? 'Retry searches for '+count+' selected issues?' : 'Clear history and reset status for '+count+' selected issues? This affects all history entries for each selected issue.';
        if (!window.confirm(question)) return;
        doAjaxCall('markissues',$('#history_bulk_action'),'table',true,'post');
    });
    // Confirm native retry links without intercepting ordinary navigation.
    table[0].addEventListener('click',function(event){
        var target=event.target.closest('a#retry');
        if(target && !window.confirm('Retry the search for this issue? Check current downloads and processing first.')) {
            event.preventDefault();event.stopImmediatePropagation();
        }
    },true);
    selection();
});
