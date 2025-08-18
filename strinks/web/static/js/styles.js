let styleTree = null;
let toggleStyleMenuController = new AbortController();

// Make styleTree globally accessible
window.styleTree = null;

function toggleStyleMenu() {
  const menu = document.getElementById("style-menu");
  const countryMenu = document.getElementById("country-menu");

  // Close country menu if it's open
  if (countryMenu && !countryMenu.classList.contains("hidden")) {
    countryMenu.classList.add("hidden");
    // Abort any existing country menu listeners
    if (typeof toggleCountryMenuController !== 'undefined') {
      toggleCountryMenuController.abort();
    }
  }

  console.log(menu);
  if (menu.classList.toggle("hidden")) {
    toggleStyleMenuController.abort();
  } else {
    toggleStyleMenuController = new AbortController();
    document.addEventListener("click", (evt) => {
      let targetElement = evt.target; // clicked element
      for (let targetElement = evt.target; targetElement; targetElement = targetElement.parentNode) {
        if (targetElement == menu) {
          return;
        }
      }
      // This is a click outside.
      toggleStyleMenu();
    }, {signal: toggleStyleMenuController.signal});
  }
}

function updateStyles() {
  const input = document.getElementById("styles-input");
  // Use 'this' if called from Tree callbacks, otherwise use global styleTree
  const tree = this && this.values ? this : styleTree;
  if (!tree) return;
  const values = tree.values;
  const button = document.getElementById("styles-button");

  if (values.length === Object.keys(tree.leafNodesById).length) {
    // Everything included by default, reduce URL params
    input.value = "";
    button.textContent = "Styles";
  } else {
    input.value = values.join(",");
    // Update button text with count
    if (values.length > 0) {
      button.textContent = `Styles (${values.length})`;
    } else {
      button.textContent = "Styles";
    }
  }
}

function initStyleTree(containerId, groupedStyles, selectedStyles) {
  const data = [];
  for (let groupId = 0; groupId < groupedStyles.length; groupId++) {
    const group = groupedStyles[groupId];
    const groupData = {
      id: "group" + groupId,
      text: group[0],
      children: [],
    };
    for (let i = 0; i < group[1].length; i++) {
      const style = group[1][i];
      groupData.children.push({
        id: style[1],
        text: style[0],
      });
    }
    data.push(groupData);
  }
  styleTree = new Tree(containerId, {
    data,
    closeDepth: 1,
    loaded: function() {
      this.values = selectedStyles;
      updateStyles.call(this);
    },
    onChange: function() {
      updateStyles.call(this);
    }
  });
  // Also set the global reference
  window.styleTree = styleTree;
}

function selectAllStyles() {
  if (styleTree) {
    styleTree.values = Object.keys(styleTree.leafNodesById);
    updateStyles();
  }
  return false;
}

function clearAllStyles() {
  if (styleTree) {
    styleTree.values = [];
    updateStyles();
  }
  return false;
}
