jQuery.extend( jQuery.fn.dataTableExt.oSort, {
    "sort-tag-pre": function ( a ) {
        return a.match(/ data-sort="(.*?)">/)[1].toLowerCase();
    },
 
    "sort-tag-asc": function ( a, b ) {
        return ((a < b) ? -1 : ((a > b) ? 1 : 0));
    },
 
    "sort-tag-desc": function ( a, b ) {
        return ((a < b) ? 1 : ((a > b) ? -1 : 0));
    }
} );
