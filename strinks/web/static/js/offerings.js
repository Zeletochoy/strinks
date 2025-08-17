function updateValueFactor(value) {
  document.getElementById("value_factor").innerHTML = value;
}

// Country filter functions
let toggleCountryMenuController = new AbortController();

function toggleCountryMenu() {
  const menu = document.getElementById('country-menu');
  const styleMenu = document.getElementById('style-menu');

  // Close style menu if it's open
  if (styleMenu && !styleMenu.classList.contains('hidden')) {
    styleMenu.classList.add('hidden');
    // Abort any existing style menu listeners
    if (typeof toggleStyleMenuController !== 'undefined') {
      toggleStyleMenuController.abort();
    }
  }

  if (menu.classList.toggle('hidden')) {
    toggleCountryMenuController.abort();
  } else {
    toggleCountryMenuController = new AbortController();
    document.addEventListener('click', (evt) => {
      // Check if click is outside the menu
      for (let targetElement = evt.target; targetElement; targetElement = targetElement.parentNode) {
        if (targetElement == menu) {
          return;
        }
      }
      // This is a click outside
      toggleCountryMenu();
    }, {signal: toggleCountryMenuController.signal});
  }
}

function selectAllCountries() {
  var nodes = document.querySelectorAll('#country-menu .treejs-node');
  nodes.forEach(function(node) {
    node.classList.add('treejs-node__checked');
  });
  updateCountries();
  event.preventDefault();
  event.stopPropagation();
  return false;
}

function clearAllCountries() {
  var nodes = document.querySelectorAll('#country-menu .treejs-node');
  nodes.forEach(function(node) {
    node.classList.remove('treejs-node__checked');
  });
  updateCountries();
  event.preventDefault();
  event.stopPropagation();
  return false;
}

function updateCountries() {
  var checkedNodes = document.querySelectorAll('#country-menu .treejs-node__checked');
  var allNodes = document.querySelectorAll('#country-menu .treejs-node');
  var countries = Array.from(checkedNodes).map(function(node) {
    return node.getAttribute('data-country');
  });

  // Don't send countries parameter when all are selected (like styles)
  if (countries.length === allNodes.length) {
    document.getElementById('countries-input').value = '';
  } else {
    document.getElementById('countries-input').value = countries.join(',');
  }
}

// Initialize MDL components when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  // Upgrade all MDL components
  if (typeof componentHandler !== 'undefined') {
    componentHandler.upgradeAllRegistered();
  }

  // Add click handlers for country checkboxes
  document.querySelectorAll('#country-menu .treejs-node').forEach(function(node) {
    node.addEventListener('click', function(e) {
      e.stopPropagation();
      this.classList.toggle('treejs-node__checked');
      updateCountries();
    });
  });

  // Initialize countries based on current checkboxes
  updateCountries();
});
