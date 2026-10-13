// Enhance native controls without owning their actions or form state.
(function() {
    'use strict';
    var buttons='#btn_notifs a, #main #btn_menu a, #main a.button, #main .links a, #main td#options a, #main #pull_table td#status a, #main .ui-button, .ui-dialog .ui-button, #ajaxMsg input[type=button], .ui-dialog button, header input[type=submit], header button, #subhead_menu a, #main button, #main input[type=submit], #main input[type=button], #main input[type=reset], '+
        '#main .ddl_row_actions a, #main .import_actions a, #main .wf_jump a, #main .catalog_nav a, #main .history_maintenance_links a, #main .pp_links a, #main .pp_jump a, [data-mylar-component=button]';
    function enhance(scope) {
        var $=window.jQuery;
        if (!$ || !$.fn.button) return;
        $(scope).find(buttons).add($(scope).filter(buttons)).each(function() {
            var control=$(this);
            if (!$.trim(control.text()) && this.tagName==='A' && !control.hasClass('ui-button')) return;
            if (control.hasClass('mylar-pagination')) return;
            var navigation=this.tagName==='A' && this.getAttribute('href') && this.getAttribute('href')!=='#' && !this.onclick && this.getAttribute('role')!=='button';
            if (!control.hasClass('ui-button')) control.button();
            control.addClass('mylar-button');
            // Navigation keeps link semantics; command anchors retain button semantics.
            if (navigation) control.attr('role','link');
        });
    }
    function syncPagination() {
        var $=window.jQuery;
        if (!$) return;
        var pagination='#main .dataTables_paginate a, #main .dataTables_paginate button';
        $(pagination).addClass('mylar-pagination');
        $('#main .dataTables_wrapper').each(function() {
            var wrapper=$(this), table=wrapper.find('table')[0];
            if (!table || !$.fn.dataTable || !$.fn.dataTable.isDataTable(table)) return;
            var current=String($(table).DataTable().page()+1);
            wrapper.find('.mylar-pagination').each(function() {
                var control=$(this);
                if ($.trim(control.text())===current) control.attr('aria-current','page');
                else control.removeAttr('aria-current');
            });
        });
    }
    window.MylarComponents={enhance:enhance};
    document.addEventListener('DOMContentLoaded',function() {
        var $=window.jQuery;
        if (!$ || !$.fn.button) return;
        // Keep native icon choices, then enhance controls its ID list does not cover.
        if (typeof window.initActions==='function') window.initActions();
        syncPagination();
        enhance(document);
        $(document).on('draw.dt',function(e){syncPagination();enhance($(e.target).closest('.dataTables_wrapper')[0] || e.target);});
        var owner=document.body;
        if (!owner) return;
        new MutationObserver(function(records) {
            records.forEach(function(record) {
                if (record.type==='attributes') {
                    var control=$(record.target);
                    if (record.attributeName==='class') {
                        if (control.hasClass('ui-button') && !control.hasClass('mylar-button') && !control.hasClass('mylar-pagination')) enhance(record.target);
                    } else if (control.hasClass('mylar-button') && control.hasClass('ui-state-disabled')!==record.target.disabled) control.button('refresh');
                } else {
                    Array.prototype.forEach.call(record.addedNodes,function(node){if(node.nodeType===1) enhance(node);});
                }
            });
        }).observe(owner,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled','class']});
    });
})();
