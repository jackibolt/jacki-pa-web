# Dinnr — Frontend

Server-rendered Flask web application for [Dinnr](https://www.dinnr.dev), a meal planning app. Communicates with the Dinnr backend API to manage meals, generate meal plans, and produce grocery lists.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Pages & Routes](#pages--routes)
- [Authentication Flow](#authentication-flow)
- [Backend API Integration](#backend-api-integration)
- [Frontend Assets](#frontend-assets)
- [Deployment](#deployment)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Flask 3.1.0 |
| Templating | Jinja2 |
| Auth | Flask-Login, Flask-JWT-Extended, PyJWT |
| HTTP client | requests |
| Server | Gunicorn |
| CSS | Custom (CSS variables, Flexbox/Grid) |
| JS | Vanilla JavaScript, jQuery |
| Icons | Font Awesome 6.5 |
| Fonts | Google Fonts (Inter, Limelight, Open Sans) |

---

## Project Structure

```
click.cook.eat_flask/
├── app/
│   ├── __init__.py          # Flask app factory, JWT/Login config, template context
│   ├── routes.py            # All page routes and form handlers (~1,700 lines)
│   ├── auth.py              # login_required decorator, token refresh logic
│   ├── send_email.py        # Contact form email sending (SMTP)
│   ├── texts.py             # Rotating subheader tagline strings
│   └── s3_push_pull.py      # AWS S3 helpers (deprecated)
├── templates/
│   ├── layout.html              # Base template (header, footer, nav)
│   ├── home.html                # Dashboard — favorites and recent plans
│   ├── login.html               # Login form
│   ├── new_user.html            # Sign-up form
│   ├── forgot_password.html     # Password recovery request
 # Dinnr — Flask Frontend (dinnr_flask)

 This repo is the server-rendered Flask frontend used historically for Dinnr (meal planning). The README below is written to help a developer (or an LLM such as Claude) reproduce the app UI as a native Swift frontend: mapping pages to screens, describing client-side behaviors, authentication patterns, and how the Flask app interacts with the backend API.

 ---

 ## Goals for this README

 - Explain the UX surface (pages → Swift screens) and interactions that must be implemented in a mobile client.
 - Describe auth/session patterns and recommend a secure approach for Swift (Keychain + header-based tokens or cookie handling).
 - Provide a concise catalog of endpoints consumed by the frontend and the expected JSON shapes.
 - Document client-side behaviors implemented in `scripts.js` and Jinja templates that must be reproduced in Swift.
 - Note build and deployment details (Heroku) and repo cleanup items.

 ---

 ## Tech stack (frontend)

 - Flask 3.x + Jinja2 (server-rendered templates)
 - Styling: `static/css/styles.css` (+ `styles2.css`) with CSS variables
 - Client JS: `static/js/scripts.js` (vanilla JS + jQuery for UI behaviors)
 - Forms & multi-step flows implemented with HTML forms, modals, and client scripts

 ---

 ## Project structure (high level)

 - `app/` — Flask glue (routes, auth wrappers, helpers used to compose pages)
 - `templates/` — Jinja2 templates that correspond to pages and partials (use as UI spec)
 - `static/css/` — styles and variables (use tokens as design tokens for Swift)
 - `static/js/` — client-side behavior (filtering, pagination, inline edit flows)
 - `run.py`, `config.py`, `requirements.txt` — run & dependency metadata

 Note: Several templates were intentionally removed as part of cleanup (menu, new_ingredient, scratch_list). Use Git history if you need them restored.

 ---

 ## Mapping templates → Swift screens (recommended)

 - `layout.html` → App shell: navigation bar, persistent header, bottom nav (if used) and global styles
 - `home.html` → `DashboardView` (favorites, recent plans, quick actions)
 - `meals.html` → `MealsListView` (filters, search bar, pagination)
 - `meal.html` → `MealDetailView` (view/edit meal, ingredients list, tags)
 - `ingredients.html` → `IngredientsListView` (search, add/edit inline modal)
 - `meal_plan_result.html` → `MealPlanEditorView` (draggable reorder, add/remove meals)
 - `meal_plan.html` & `meal_plans.html` → `MealPlanDetailView` + `MealPlansListView`
 - `grocery_list.html` → `GroceryListView` (aggregated groceries for plan or multiple plans)
 - `profile.html` → `ProfileView` (preferences, password change)
 - `contact.html` → `ContactView` (contact form)
 - `_ingredient_modal.html` → `IngredientPicker` (modal / sheet component)
 - `_onboarding_modal.html` → `OnboardingFlow` (multi-step modal shown on first login)

 Use templates as a pixel/structure reference: copy markup structure, field names, and form payload keys into your Swift models and request bodies.

 ---

 ## Authentication & recommended mobile approach

 Server currently implements access + refresh JWT tokens and sets them as HTTP-only cookies when used via browser. For a native Swift client, prefer the header/token approach:

 1. Login (`POST /auth/login`) returns `access_token` and `refresh_token` JSON. Store tokens securely in the Keychain.
 2. Include `Authorization: Bearer <access_token>` for subsequent requests.
 3. On 401, call `POST /auth/refresh` with the `refresh_token` (in request body). Replace stored access token on success and retry the failed request.
 4. To logout call `POST /auth/logout` and remove tokens from Keychain.

 Notes:
 - Cookie-based flow is supported (server reads cookie `access_token`), but it requires properly handling HTTPCookieStorage and may be less portable across WebView and native flows.
 - Implement concurrency-safe refresh logic (single inflight refresh, queue other requests until completed).

 Swift helpers (conceptual):
 - Store `access_token` / `refresh_token` in Keychain.
 - Central `APIClient` that injects `Authorization` header and handles automatic refresh on 401.

 ---

 ## Key endpoints consumed by frontend (summary)

 The frontend relies on the backend API for most data. Implement these endpoints in your Swift client as the canonical data layer.

 Auth
 - POST `/auth/login` — body {email, password, remember_me} → returns tokens + user
 - POST `/auth/refresh` — body {refresh_token} or cookie → returns new access_token
 - POST `/auth/logout`

 Users
 - GET `/user/profile` — returns user and `preferences` + `subscription` object
 - PUT `/user/profile`

 Meals
 - GET `/meals?page=&per_page=&q=&cuisine=&category=&tag=` — list with filters and pagination
 - POST `/meals` — create meal, body includes `ingredients` array
 - GET/PUT/DELETE `/meals/<id>`

 Ingredients
 - GET `/ingredients` — list (user + default)
 - POST `/ingredients` — add custom ingredient
 - PUT `/ingredients/<id>`
 - DELETE `/ingredients/<id>`

 Meal plans
 - POST `/meal_plan` — generate plan (payload: length, tags, excluded meals)
 - GET `/meal_plans` — list
 - GET `/meal_plan/<id>` — full plan + aggregated grocery list
 - PUT `/meal_plan/<id>/finalize`
 - PATCH `/meal_plan/<id>/reorder_meals`

 Grocery
 - GET `/meal_plans/grocery_list` — combined grocery
 - GET/POST `/scratch-list`


 ---

 ## JSON resource shapes (examples)

 User profile (partial)
 ```json
 {
    "id": 1,
    "email": "user@example.com",
    "name": "Jane Doe",
    "preferences": { "alphabetize_groceries": false, "cuisine_max_occurance": 2 },
    "subscription": { "type": "premium", "status": "active" }
 }
 ```

 Meal (partial)
 ```json
 {
    "id": 42,
    "name": "Spaghetti Carbonara",
    "cuisine": "Italian",
    "categories": ["Dinner"],
    "tags": ["quick"],
    "ingredients": [ {"ingredient_id":5,"name":"Pasta","quantity":400,"unit":"g"} ]
 }
 ```

 MealPlan (partial)
 ```json
 { "id":77, "name":"Week A", "length":7, "meals": [ {"order":1, "meal":{...}} ], "grocery_list": [{"name":"Pasta","quantity":800}] }
 ```

 Error format
 ```json
 { "error": "Human readable message", "code": "optional" }
 ```

 ---

 ## Client behaviors to replicate (from `scripts.js` + templates)

 - Filtering/search on `meals.html` is performed client-side for smaller result sets; nonetheless the API supports server-side filtering — prefer server-side filtering in mobile clients for large datasets.
 - Pagination: pages of 15 items; implement server-driven pagination with `page` and `per_page` params and display `total` from response metadata.
 - Ingredient picker: `_ingredient_modal.html` is a modal listing ingredients with search and selection; implement as a sheet/modal with searchable list and multi-select support.
 - Inline edit/add ingredient: the web UI often uses inline forms; on mobile use dedicated edit views or sheets.
 - Onboarding modal: replicate the multi-step flow and track dismissal with `/close-onboarding`.
 - Prevent double-submit: disable submit buttons until response completes.

 ---

 ## UI tokens and styling

 Use CSS variables from `static/css/styles.css` as design tokens: translate hex values to Swift `Color` or `UIColor` constants.

 Example extracted tokens:
 - primaryOrange: `#ee4d20`
 - primaryGreen: `#4CAF50`
 - primaryBlack: `#131313`

 Typography and spacing can be derived from templates (class names and container sizes). Use `profile.html` and `contact.html` as the canonical layout references.

 ---

 ## Developer tasks & suggestions

 - Generate an OpenAPI spec from the Flask routes and models (I can help). Use OpenAPI Generator to produce typed Swift clients (`OpenAPIGenerator` -> `swift5` target).
 - Implement a single `APIClient` in Swift that handles auth, retries, and decoding.
 - Cache static lists (cuisines, categories, ingredient categories) and refresh periodically.
 - Add telemetry/error reporting for network errors and 401->refresh failures.

 ---

 ## Running & deployment notes

 - Development: `python run.py` after setting `.env` from `.env.example`.
 - Migrations are handled with Alembic in the backend repo — frontend doesn't run DB migrations.
 - Heroku: the app is deployed at `https://click-cook-eat-flask-frontend-7eafbe8f0f52.herokuapp.com/` (frontend). Heroku warns if `.python-version` is missing — add it to pin runtime.

 ---

 ## Next steps I can help with

 - Extract a machine-readable OpenAPI spec and run `openapi-generator` to create Swift models and an API client.
 - Scaffold a small Xcode project with `APIClient`, `Models` (User, Meal, MealPlan), and the `LoginView` + `MealsListView` to jump-start the rebuild.

 Would you like me to:
 1) generate an OpenAPI spec from the codebase, or
 2) scaffold a small Swift/Xcode starter with sample models and network client?
