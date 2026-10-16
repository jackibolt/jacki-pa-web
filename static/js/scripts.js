

/// HIGHLIGHT ACTIVE NAV ITEM
document.addEventListener('DOMContentLoaded', function () {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-links a');
    
    // Remove active class from all links
    navLinks.forEach(link => link.classList.remove('active'));
    
    // Add active class to the correct link based on current path
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        
        // Check exact match or if it's a meal plan related path
        if (currentPath === href) {
            link.classList.add('active');
        }
    });
});

/// VIEW PASSWORD TOGGLE
document.addEventListener('DOMContentLoaded', function () {
    const passwordInput = document.getElementById('password');
    const togglePassword = document.getElementById('togglePassword');
    const eyeOpen = document.getElementById('eyeOpen');
    const eyeClosed = document.getElementById('eyeClosed');

    if (togglePassword && passwordInput && eyeOpen && eyeClosed) {
        togglePassword.addEventListener('click', function () {
            const isPasswordVisible = passwordInput.type === 'text';

            passwordInput.type = isPasswordVisible ? 'password' : 'text';
            eyeOpen.style.display = isPasswordVisible ? 'inline' : 'none';
            eyeClosed.style.display = isPasswordVisible ? 'none' : 'inline';
        });
    }
});


/// MEAL FILTERING AND PAGINATION
const mealsPerPage = 15;
let currentPage = 1;

function showPage(page, filteredMeals) {
    const totalPages = Math.ceil(filteredMeals.length / mealsPerPage);
    currentPage = Math.max(1, Math.min(page, totalPages));

    // Hide all meals first
    document.querySelectorAll('.meal-box').forEach(meal => {
        meal.style.display = 'none';
    });

    // Show only the meals for the current page
    filteredMeals.forEach((meal, index) => {
        if (index >= (currentPage - 1) * mealsPerPage && index < currentPage * mealsPerPage) {
            meal.style.display = 'flex';
        }
    });

    renderPaginationControls(totalPages, filteredMeals);
}

function renderPaginationControls(totalPages, filteredMeals) {
    const container = document.getElementById('paginationControls');
    container.innerHTML = '';

    if (totalPages <= 1) return;

    for (let i = 1; i <= totalPages; i++) {
        const btn = document.createElement('button');
        btn.textContent = i;
        btn.className = 'page-btn' + (i === currentPage ? ' active' : '');
        btn.addEventListener('click', () => showPage(i, filteredMeals));
        container.appendChild(btn);
    }
}

function filterMeals() {
    const query = document.getElementById('mealSearch').value.toLowerCase();
    const selectedCuisine = document.getElementById('cuisineFilter').value;
    const selectedType = document.getElementById('mealTypeFilter').value;
    const mealBoxes = document.querySelectorAll('.meal-box');
    const selectedTag = document.getElementById('tagFilter').value; 
    const selectedCategory = document.getElementById('categoryFilter').value;

    const filteredMeals = [];

    mealBoxes.forEach(box => {
        const name = box.dataset.name;
        const cuisine = box.dataset.cuisine;
        const isSideDish = box.dataset.isSide === 'true';
        const tags = box.dataset.tags ? box.dataset.tags.split(',') : [];


        const matchesName = name.includes(query);
        const matchesCuisine = !selectedCuisine || cuisine === selectedCuisine;
        const matchesType =
            selectedType === '' ||
            (selectedType === 'main' && isSideDish === false) ||
            (selectedType === 'side' && isSideDish === true);

        const matchesTag = !selectedTag || tags.includes(selectedTag);
        
        const categories = box.dataset.categories ? box.dataset.categories.split(',') : [];
        const matchesCategory = !selectedCategory || categories.includes(selectedCategory.trim());

        if (matchesName && matchesCuisine && matchesType && matchesTag && matchesCategory) {
            filteredMeals.push(box);
        }
    });

    showPage(1, filteredMeals); // Show first page of filtered results
}

document.addEventListener('DOMContentLoaded', function () {
    const mealSearch = document.getElementById('mealSearch');
    const cuisineFilter = document.getElementById('cuisineFilter');
    const mealTypeFilter = document.getElementById('mealTypeFilter');
    const tagFilter = document.getElementById('tagFilter');
    const categoryFilter = document.getElementById('categoryFilter');

    if (mealSearch && cuisineFilter && mealTypeFilter && tagFilter && categoryFilter) {
        filterMeals(); // Load first page of all meals initially

        mealSearch.addEventListener('input', filterMeals);
        cuisineFilter.addEventListener('change', filterMeals);
        mealTypeFilter.addEventListener('change', filterMeals);
        tagFilter.addEventListener('change', filterMeals);
        categoryFilter.addEventListener('change', filterMeals);
    }
});




//// INGREDIENTS QUANTITY
document.addEventListener("DOMContentLoaded", () => {
    const wrapper = document.getElementById("ingredient-wrapper");
    if (!wrapper) return;

    const mealId = wrapper.dataset.mealId;
    const mealName = wrapper.dataset.mealName;
    const cuisineId = parseInt(wrapper.dataset.mealCuisineId);
    const categoryIds = JSON.parse(wrapper.dataset.mealCategoryIds);
    const cuisineName = wrapper.dataset.mealCuisineName;
    const categoryNames = JSON.parse(wrapper.dataset.mealCategoryNames);
    let ingredients = JSON.parse(wrapper.dataset.mealIngredients);

    document.querySelectorAll(".dot").forEach(dot => {
        dot.addEventListener("click", async (e) => {
        e.preventDefault();
        const clicked = e.target;
        const ingredientName = clicked.dataset.ingredientName;
        const newQuantity = parseInt(clicked.dataset.quantity);

        // Update quantity in the local ingredients array
        ingredients = ingredients.map(ing => {
            if (ing.name === ingredientName) {
            return { ...ing, quantity: newQuantity };
            }
            return ing;
        });

        try {
            const accessToken = wrapper.dataset.accessToken;
            const API_BASE_URL = wrapper.dataset.apiBaseUrl;
            console.log("mealId", mealId);
            const response = await fetch(`${API_BASE_URL}/meals/${mealId}`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${accessToken}`
                },
                body: JSON.stringify({
                    name: mealName,
                    cuisine_name: cuisineName,  // Name is used here
                    categories: categoryNames,  // Names are sent here
                    ingredients: ingredients.map(i => ({
                        ingredient_name: i.name,
                        quantity: i.quantity
                    }))
                    })
            });

            if (response.ok) {
            // Update dot visuals
            const parent = clicked.closest(".ingredient-dots");
            const allDots = parent.querySelectorAll(".dot");
            allDots.forEach(dot => {
                const dotQty = parseInt(dot.dataset.quantity);
                if (dotQty <= newQuantity) {
                dot.classList.add("filled");
                } else {
                dot.classList.remove("filled");
                }
            });
            } else {
            console.error("Failed to update quantity.");
            }
        } catch (err) {
            console.error("Error:", err);
        }
        });
    });
    });


//// UPDATE INGREDIENTS IN MEAL FORM
const form = document.querySelector('form');
if (form) {
    form.addEventListener('submit', function (e) {
        const ingredients = [];

        // Loop through each .ingredient-box
        document.querySelectorAll('#ingredient-wrapper .ingredient-box').forEach(box => {
            const nameEl = box.querySelector('.ingredient-name p:first-child');
            const filledDots = box.querySelectorAll('.dot.filled');

            const name = nameEl ? nameEl.textContent.trim() : null;
            const quantity = filledDots.length;  // Quantity = number of filled dots

            if (name && quantity > 0) {
                ingredients.push({
                    ingredient_name: name,
                    quantity: quantity
                });
            }
        });

        console.log("Ingredients to be submitted:", ingredients);
        // Inject into hidden input (must be present in the form)
        const hiddenInput = document.querySelector('#ingredients');
        if (hiddenInput) {
            hiddenInput.value = JSON.stringify(ingredients);
        } else {
            console.warn("⚠️ No hidden input with id='ingredients' found.");
        }
    });
}



//// INGREDIENTS REMOVE
document.addEventListener("DOMContentLoaded", () => {
    const wrapper = document.getElementById("ingredient-wrapper");
    if (!wrapper) return; // Not on an ingredient page
    let ingredients = JSON.parse(wrapper.dataset.mealIngredients);
    const mealId = wrapper.dataset.mealId;
    const mealName = wrapper.dataset.mealName;
    const cuisineName = wrapper.dataset.mealCuisineName;
    const categoryNames = JSON.parse(wrapper.dataset.mealCategoryNames);

    document.querySelectorAll(".btn-remove").forEach(button => {
        button.addEventListener("click", async (e) => {
        e.preventDefault();
        const clicked = e.target;
        const ingredientName = clicked.dataset.ingredientName;

        // Update the ingredients array
        ingredients = ingredients.filter(i => i.name !== ingredientName);

        try {
            const accessToken = wrapper.dataset.accessToken;
            const API_BASE_URL = wrapper.dataset.apiBaseUrl;

            const response = await fetch(`${API_BASE_URL}/meals/${mealId}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${accessToken}`
            },
            body: JSON.stringify({
                name: mealName,
                cuisine_name: cuisineName,
                categories: categoryNames,
                ingredients: ingredients.map(i => ({
                ingredient_name: i.name,
                quantity: i.quantity
                }))
            })
            });
            console.log("response", response);
            if (response.ok) {
            clicked.closest(".ingredient-box").remove();
            } else {
            console.error("Failed to update meal after removing ingredient.");
            }
        } catch (err) {
            console.error("Error updating meal:", err);
        }
        });
    });
});




////// INGREDIENTS SUGGESTIONS
document.addEventListener("DOMContentLoaded", async () => {
    const wrapper = document.getElementById("ingredient-wrapper");
    if (!wrapper) return;

    const API_BASE_URL = wrapper.dataset.apiBaseUrl;
    const accessToken = wrapper.dataset.accessToken;

    const mealId = wrapper.dataset.mealId;
    const mealName = wrapper.dataset.mealName;
    const cuisineName = wrapper.dataset.mealCuisineName;
    const categoryNames = JSON.parse(wrapper.dataset.mealCategoryNames);
    let ingredients = JSON.parse(wrapper.dataset.mealIngredients);

    const searchInput = document.getElementById("ingredient-search");
    const suggestionsBox = document.getElementById("ingredient-suggestions");
    const ingredientsList = document.querySelector(".ingredients-list");

    let allIngredients = [];

    // Fetch all ingredients once
    async function fetchAllIngredients() {
        try {
            const res = await fetch(`${API_BASE_URL}/ingredients`, {
                headers: {
                    Authorization: `Bearer ${accessToken}`,
                },
            });
            console.log(res)

            if (res.ok) {
                allIngredients = await res.json();
            } else {
                console.error("Failed to fetch ingredients.");
            }
        } catch (err) {
            console.error("Error fetching ingredients:", err);
        }
    }

    // Filter local list
    function filterIngredients(term) {
        return allIngredients
            .filter((i) => i.name.toLowerCase().includes(term.toLowerCase()))
            .slice(0, 10);
    }

    // Render suggestion dropdown
    function renderSuggestions(matches) {
        suggestionsBox.innerHTML = "";
        const searchTerm = searchInput.value.trim();

        if (matches.length === 0) {
            // Show "Add ingredient" option even when no matches found
            const addItem = document.createElement("div");
            addItem.classList.add("suggestion-item", "suggestion-add-ingredient");
            addItem.innerHTML = `
                <div style="font-weight: 500;">Add "${searchTerm}" as new ingredient</div>
                <div style="font-size: 11px; color: rgba(255,255,255,0.6); margin-top: 2px;">Can't find what you need? Create it</div>
            `;
            addItem.addEventListener("click", () => {
                document.getElementById("ingredientNameInput").value = searchTerm;
                openAddIngredientModal();
                suggestionsBox.style.display = "none";
                searchInput.value = "";
            });
            suggestionsBox.appendChild(addItem);
            suggestionsBox.style.display = "block";
            return;
        }

        matches.forEach((match) => {
            const item = document.createElement("div");
            item.classList.add("suggestion-item");
            item.textContent = match.name;
            item.addEventListener("click", () => {
                handleIngredientAdd(match.name);
                suggestionsBox.style.display = "none";
                searchInput.value = "";
            });
            suggestionsBox.appendChild(item);
        });

        // Add "Add ingredient" option at the bottom
        const addItem = document.createElement("div");
        addItem.classList.add("suggestion-item", "suggestion-add-ingredient");
        addItem.innerHTML = `
            <div style="font-weight: 500;">Add "${searchTerm}" as new ingredient</div>
            <div style="font-size: 11px; color: rgba(255,255,255,0.6); margin-top: 2px;">Can't find what you need? Create it</div>
        `;
        addItem.addEventListener("click", () => {
            document.getElementById("ingredientNameInput").value = searchTerm;
            openAddIngredientModal();
            suggestionsBox.style.display = "none";
            searchInput.value = "";
        });
        suggestionsBox.appendChild(addItem);

        suggestionsBox.style.display = "block";
    }

    // Listen for input
    searchInput.addEventListener("input", () => {
        const term = searchInput.value.trim();
        if (term.length === 0) {
            suggestionsBox.style.display = "none";
            return;
        }
        const matches = filterIngredients(term);
        renderSuggestions(matches);
    });

    // Hide dropdown on outside click
    document.addEventListener("click", (e) => {
        if (!e.target.closest(".ingredient-search-container")) {
            suggestionsBox.style.display = "none";
        }
    });

    // 👇 Function to add ingredient and update UI + backend
    async function handleIngredientAdd(ingredientName) {
        if (ingredients.some((i) => i.name.toLowerCase() === ingredientName.toLowerCase())) return;

        const newIngredient = { name: ingredientName, quantity: 1 };
        ingredients.push(newIngredient);

        try {
            const res = await fetch(`${API_BASE_URL}/meals/${mealId}`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${accessToken}`,
                },
                body: JSON.stringify({
                    name: mealName,
                    cuisine_name: cuisineName,
                    categories: categoryNames,
                    ingredients: ingredients.map((i) => ({
                        ingredient_name: i.name,
                        quantity: i.quantity,
                    })),
                }),
            });

            if (res.ok) {
                const box = document.createElement("div");
                box.classList.add("ingredient-box");
                box.innerHTML = `
                    <div class="ingredient-name">
                        <p>${newIngredient.name}</p>
                        <p class="ingredient-category"></p>
                    </div>
                    <div class="ingredient-dots">
                        ${[1, 2, 3]
                            .map(
                                (i) => `
                            <button class="dot ${i <= newIngredient.quantity ? "filled" : ""}" 
                                data-quantity="${i}" 
                                data-ingredient-name="${newIngredient.name}" 
                                title="Set quantity to ${i}"></button>
                        `
                            )
                            .join("")}
                    </div>
                    <button class="btn-remove" data-ingredient-name="${newIngredient.name}">✖</button>
                `;
                ingredientsList.appendChild(box);

                // Bind quantity dots for this ingredient
                box.querySelectorAll(".dot").forEach((dot) => {
                    dot.addEventListener("click", async (e) => {
                        e.preventDefault();
                        const clicked = e.target;
                        const ingName = clicked.dataset.ingredientName;
                        const newQty = parseInt(clicked.dataset.quantity);

                        ingredients = ingredients.map((ing) =>
                            ing.name === ingName ? { ...ing, quantity: newQty } : ing
                        );

                        const res = await fetch(`${API_BASE_URL}/meals/${mealId}`, {
                            method: "PUT",
                            headers: {
                                "Content-Type": "application/json",
                                Authorization: `Bearer ${accessToken}`,
                            },
                            body: JSON.stringify({
                                name: mealName,
                                cuisine_name: cuisineName,
                                categories: categoryNames,
                                ingredients: ingredients.map((i) => ({
                                    ingredient_name: i.name,
                                    quantity: i.quantity,
                                })),
                            }),
                        });

                        if (res.ok) {
                            const parent = clicked.closest(".ingredient-dots");
                            parent.querySelectorAll(".dot").forEach((d) => {
                                const dotQty = parseInt(d.dataset.quantity);
                                d.classList.toggle("filled", dotQty <= newQty);
                            });
                        } else {
                            console.error("Failed to update ingredient quantity.");
                        }
                    });
                });
            } else {
                console.error("Failed to add ingredient.");
            }
        } catch (err) {
            console.error("Error adding ingredient:", err);
        }
    }

    // Initial fetch of ingredients
    await fetchAllIngredients();
});


// Helper function to generate star SVG
function generateStarSVG(isFavorited) {
    if (isFavorited) {
        return '<svg width="20" height="20" viewBox="0 0 24 24" fill="#c8455a" style="display: inline-block; vertical-align: middle;"><polygon points="12,2 15,10 23,10 17,15 19,23 12,18 5,23 7,15 1,10 9,10"/></svg>';
    } else {
        return '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#999" stroke-width="1.5" style="display: inline-block; vertical-align: middle;"><polygon points="12,2 15,10 23,10 17,15 19,23 12,18 5,23 7,15 1,10 9,10"/></svg>';
    }
}

/// toggle star for favorites
function toggleStar(starElement, mealId, currentlyFavorite) {
    const newFavoriteStatus = !currentlyFavorite;

    fetch(`/meals/${mealId}/favorite`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ is_favorite: newFavoriteStatus })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            starElement.innerHTML = generateStarSVG(newFavoriteStatus);
            if (newFavoriteStatus) {
                starElement.classList.add('favorited');
            } else {
                starElement.classList.remove('favorited');
            }
            // Update the onclick function's second argument (currentlyFavorite)
            starElement.setAttribute('onclick', `toggleStar(this, ${mealId}, ${newFavoriteStatus})`);
        } else {
            // Revert on error
            const isFavorited = currentlyFavorite === true || currentlyFavorite === 'true';
            starElement.innerHTML = generateStarSVG(isFavorited);
            alert("Failed to update favorite status!");
        }
    })
    .catch(error => {
        console.error('Error updating favorite:', error);
        // Revert on error
        const isFavorited = currentlyFavorite === true || currentlyFavorite === 'true';
        starElement.innerHTML = generateStarSVG(isFavorited);
        alert("Error updating favorite!");
    });
}


/// set homepage ID
document.addEventListener("DOMContentLoaded", function() {
    if (window.location.pathname === '/') {
        document.body.setAttribute("id", "homepage");
    }
});



/// reset filters button
const resetFiltersBtn = document.getElementById('resetFiltersBtn');
if (resetFiltersBtn) {
  resetFiltersBtn.addEventListener('click', function () {
    // Clear inputs
    document.getElementById('mealSearch').value = '';
    document.getElementById('cuisineFilter').value = '';
    document.getElementById('mealTypeFilter').value = '';
    document.getElementById('tagFilter').value = '';

    // Show all meals
    const allMeals = document.querySelectorAll('.meal-box');
    allMeals.forEach(meal => meal.style.display = 'flex');
  });
}


/// PROFILE PAGE - MODAL AND FORM HANDLERS
// Number input adjuster
function adjustNum(delta) {
    const input = document.getElementById('cuisineNum');
    const val = Math.max(1, Math.min(10, parseInt(input.value) + delta));
    input.value = val;
}

// Toggle custom checkbox
function toggleCheck(el) {
    el.classList.toggle('checked');
}

// Sync custom checkbox with hidden form input
function syncHiddenCheckbox(name, el) {
    const hidden = document.querySelector(`input[name="${name}"]`);
    if (hidden) {
        hidden.value = el.classList.contains('checked') ? 'on' : '';
    }
}

// Toggle fill method
function toggleFill() {
    const toggle = document.getElementById('fillToggle');
    const labelR = document.getElementById('labelRandomize');
    const labelP = document.getElementById('labelRepeat');
    const hidden = document.getElementById('repeatHidden');
    toggle.classList.toggle('repeat');
    const isRepeat = toggle.classList.contains('repeat');
    labelR.classList.toggle('active', !isRepeat);
    labelP.classList.toggle('active', isRepeat);
    hidden.value = isRepeat ? 'on' : '';
}
