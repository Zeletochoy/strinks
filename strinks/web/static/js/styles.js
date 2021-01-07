//function showGroupStyles(visible) {
//  $(this).find(".group-styles").style({display: visible ? "block" : "none"});
//}

//function groupMouseOver() { showGroupStyles(true); }
//function groupMouseOut() { showGroupStyles(false); }

function updateStyles() {
  const enabled = new Set();
  document.querySelectorAll(".style-checkbox").forEach(function (elt) {
    if (elt.checked) {
      enabled.add(elt.getAttribute("style-id"));
    }
  });
  console.log(enabled);
  const input = document.getElementById("styles-input");
  input.value = Array.from(enabled).join(",");
}
