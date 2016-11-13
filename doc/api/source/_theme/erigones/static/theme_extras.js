// dano
window.onhashchange = function(e) {
  document.getElementById(window.location.hash.substring(1)).scrollIntoView();
};
