var IPLIST, ADD_BUTTON;

function add_ip(ip) {
  ADD_BUTTON.trigger('click');
  var add_row_ip = IPLIST.find('tr.dynamic-ipaddress_set:last td.field-ip input');
  add_row_ip.val(ip);
}

function add_ip_range_button() {
  function dot2num(dot) {
      var d = dot.split('.');
      return ((((((+d[0])*256)+(+d[1]))*256)+(+d[2]))*256)+(+d[3]);
  }

  function num2dot(num) {
      var d = num%256;
      for (var i = 3; i > 0; i--) 
      { 
          num = Math.floor(num/256);
          d = num%256 + '.' + d;
      }
      return d;
  }

  function ip_generator(range) {
    if (!range) {
      return null;
    }

    var errmsg = 'Incorrect IP range';
    var ip = range.split('-');
    var ip0, ip1;

    if (ip.length != 2) {
      return errmsg;
    }

    if ( (ip[0].split('.').length != 4) || (ip[1].split('.').length != 4)) {
      return errmsg;
    }

    try {
      ip0 = dot2num(django.jQuery.trim(ip[0]));
      ip1 = dot2num(django.jQuery.trim(ip[1]));
    } catch(err) {
      return errmsg + ' ('+ err +')';
    }


    for (i=ip0; i <= ip1; i++) {
      add_ip(num2dot(i));
    }

    return null;
  }

  var button = django.jQuery('<a href="javascript:void(0)">Add IP address range</a>');

  button.click(function() {
    var range = prompt('Please enter IPv4 address range in following format:\n"<first IP> - <last IP>"\n(Example: 192.168.144.10 - 192.168.144.20)', null);
    var msg = ip_generator(range);

    if (msg) { // error
      alert(msg);
    }
  });

  return button;
}

django.jQuery(document).ready(function() {
  IPLIST = django.jQuery('#ipaddress_set-group');
  ADD_BUTTON = IPLIST.find('tr.add-row a');
  ADD_BUTTON.parent().append('&nbsp;&nbsp;&nbsp;');
  ADD_BUTTON.parent().append(add_ip_range_button());
});
