jQuery.extend( jQuery.fn.dataTableExt.oSort, {
    "icon-tag-pre": function ( a ) {
        return a.match(/<i class="icon-(.*?)">/)[1].toLowerCase();
    },
 
    "icon-tag-asc": function ( a, b ) {
        return ((a < b) ? -1 : ((a > b) ? 1 : 0));
    },
 
    "icon-tag-desc": function ( a, b ) {
        return ((a < b) ? 1 : ((a > b) ? -1 : 0));
    }
} );
