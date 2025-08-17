function updateValueFactor(value) {
  document.getElementById("value_factor").innerHTML = value;
}

// Country filter functions
function toggleCountryMenu() {
  var menu = document.getElementById('country-menu');
  menu.classList.toggle('hidden');
}

function selectAllCountries() {
  var checkboxes = document.querySelectorAll('.country-checkbox');
  checkboxes.forEach(function(checkbox) {
    checkbox.checked = true;
  });
  return false;
}

function clearAllCountries() {
  var checkboxes = document.querySelectorAll('.country-checkbox');
  checkboxes.forEach(function(checkbox) {
    checkbox.checked = false;
  });
  return false;
}

function updateCountries() {
  var checkboxes = document.querySelectorAll('.country-checkbox:checked');
  var countries = Array.from(checkboxes).map(function(checkbox) {
    return checkbox.value;
  });
  document.getElementById('countries-input').value = countries.join(',');
}

// Close country menu when clicking outside
document.addEventListener('click', function(event) {
  var menu = document.getElementById('country-menu');
  var button = document.getElementById('countries-button');
  if (menu && !menu.contains(event.target) && event.target !== button) {
    menu.classList.add('hidden');
  }
});
