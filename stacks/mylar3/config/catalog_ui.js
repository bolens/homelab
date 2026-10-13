// Native data loading, links, filters and actions retain ownership.
$(function() {
    var root=$('#catalog_review');
    function selection() {
        var count=$('#wanted_table tbody input:checked').length;
        $('#catalog_selected').text(count+(count===1 ? ' issue selected on this page' : ' issues selected on this page'));
        $('#catalog_apply').prop('disabled',count===0);
    }
    function decorate(table) {
        var library=table.id==='series_table';
        var headings=$(table).find('thead th').map(function(){return $(this).text().trim();}).get();
        $(table).find('tbody tr').each(function(){
            var row=$(this),cells=row.children('td');
            if(cells.length!==headings.length) return;
            cells.each(function(i){$(this).attr('data-label',headings[i] || 'Select');});
            var status=cells.eq(library ? 6 : 4);
            if(table.id==='series_table' || table.id==='wanted_table') {
                var text=status.text();
                status.empty().append($('<span>').addClass('catalog_badge').text(text));
                row.attr('data-catalog-status',text);
            }
            if(library) {
                var active=cells.eq(7),image=active.find('img');
                if(image.length) active.text(image.attr('alt'));
                if(row.hasClass('gradeU')) active.text('Removed from ComicVine');
            } else if(table.id==='wanted_table') {
                cells.eq(0).find('input').attr('aria-label','Select '+cells.eq(1).text()+' issue '+cells.eq(2).text());
            }
        });
        selection();
    }
    root.find('table').each(function(){
        var table=this;
        $(table).on('draw.dt',function(){decorate(table);});
        decorate(table);
    });
    $('#wanted_table').on('change click','input[type=checkbox]',selection);
    $('#markissues').on('submit',function(event){event.preventDefault();});
    $('#catalog_apply').on('click',function(){
        if($('#wanted_table tbody input:checked').length && $('#mark_issues').val()) mark_the_issues();
    });
});
