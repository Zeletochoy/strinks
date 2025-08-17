function updateValueFactor(value) {
  document.getElementById("value_factor").innerHTML = value;
}

// Toggle more shops display
function toggleMoreShops(event, beerId) {
  event.preventDefault();
  var moreOfferings = document.getElementById('more-offerings-' + beerId);
  var link = event.currentTarget;
  var icon = link.querySelector('.more-shops-icon');

  if (moreOfferings.classList.contains('hidden')) {
    moreOfferings.classList.remove('hidden');
    icon.classList.remove('fa-chevron-down');
    icon.classList.add('fa-chevron-up');
  } else {
    moreOfferings.classList.add('hidden');
    icon.classList.remove('fa-chevron-up');
    icon.classList.add('fa-chevron-down');
  }
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
  var button = document.getElementById('countries-button');

  // Don't send countries parameter when all are selected (like styles)
  if (countries.length === allNodes.length) {
    document.getElementById('countries-input').value = '';
    button.textContent = 'Countries';
  } else {
    document.getElementById('countries-input').value = countries.join(',');
    // Update button text with count
    if (countries.length > 0) {
      button.textContent = `Countries (${countries.length})`;
    } else {
      button.textContent = 'Countries';
    }
  }
}

// Infinite scroll variables
let currentPage = 1;
let isLoading = false;
let hasMore = true;

function loadMoreBeers() {
  if (isLoading || !hasMore) return;

  isLoading = true;
  document.getElementById('loading-indicator').style.display = 'block';

  // Get current filter parameters
  const params = new URLSearchParams(window.location.search);
  params.set('page', currentPage);

  fetch('/api/beers?' + params.toString())
    .then(response => response.json())
    .then(data => {
      const beerGrid = document.getElementById('beer-grid');

      // Create temporary container to parse HTML
      const tempDiv = document.createElement('div');

      data.beers.forEach(beerHtml => {
        tempDiv.innerHTML = beerHtml;
        const beerCard = document.createElement('div');
        beerCard.className = 'mdl-cell mdl-cell--4-col beer-card';
        beerCard.innerHTML = tempDiv.firstElementChild.outerHTML;
        beerGrid.appendChild(beerCard);
      });

      // Upgrade MDL components in new cards
      if (typeof componentHandler !== 'undefined') {
        componentHandler.upgradeAllRegistered();
      }

      // Re-initialize cloudimage for new images
      if (window.ciResponsive) {
        window.ciResponsive.process();
      }

      hasMore = data.has_more;
      currentPage++;
      isLoading = false;

      document.getElementById('loading-indicator').style.display = 'none';

      if (!hasMore) {
        document.getElementById('end-of-results').style.display = 'block';
      }

      // Set up observer for the new last card
      setupIntersectionObserver();
    })
    .catch(error => {
      console.error('Error loading more beers:', error);
      isLoading = false;
      document.getElementById('loading-indicator').style.display = 'none';
    });
}

let observer = null;

function setupIntersectionObserver() {
  if (observer) {
    observer.disconnect();
  }

  const options = {
    root: null,
    rootMargin: '200px',
    threshold: 0.1
  };

  observer = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        loadMoreBeers();
      }
    });
  }, options);

  // Observe the last beer card
  const beerCards = document.querySelectorAll('.beer-card');
  if (beerCards.length > 0 && hasMore) {
    observer.observe(beerCards[beerCards.length - 1]);
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

  // Set up infinite scroll
  setupIntersectionObserver();

  // Back to top button
  const backToTopButton = document.getElementById('back-to-top');

  // Sticky filter bar
  const filterBar = document.querySelector('.filter-bar');

  window.addEventListener('scroll', function() {
    // Back to top button visibility
    if (window.pageYOffset > 300) {
      backToTopButton.style.display = 'block';
    } else {
      backToTopButton.style.display = 'none';
    }

    // Sticky filter bar
    if (window.pageYOffset > 100) {
      filterBar.classList.add('sticky');
    } else {
      filterBar.classList.remove('sticky');
    }
  });

  backToTopButton.addEventListener('click', function() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
});
