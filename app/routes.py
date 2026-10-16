from flask import (render_template, url_for, request, redirect, Blueprint,
                   flash, session, jsonify, g, current_app, make_response,
                   get_flashed_messages)
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask_jwt_extended.exceptions import NoAuthorizationError

from dotenv import load_dotenv
import json, requests, os, random, threading
import time, jwt, re, pprint

from datetime import datetime
from zoneinfo import ZoneInfo
from functools import wraps
from markupsafe import Markup
from flask_login import login_user, UserMixin

from app import User

from app.auth import login_required
from app.texts import hero_headlines

routes = Blueprint("routes", __name__)


# Load environment variables from the .env file
load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL")
print(f"API BASE: {API_BASE_URL}")


# ----- Helpers -----

def threaded_get(urls, headers=None):
    results = {}

    def fetch(key, url):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                results[key] = {'data': response.json(), 'status_code': response.status_code}
            else:
                results[key] = {'data': None, 'status_code': response.status_code}
        except Exception:
            results[key] = {'data': None, 'status_code': 500}  # Set status code to 500 for errors

    threads = []
    for key, url in urls.items():
        thread = threading.Thread(target=fetch, args=(key, url))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    return results



def get_api_session():
    s = requests.Session()
    s.headers.update({'Authorization': f"Bearer {g.access_token}"})
    return s


def random_subheader():
    return random.choice(hero_headlines)


def clear_and_flash(msg, category='message'):
    session.pop('_flashes', None)
    flash(msg, category)


# ----- Routes -----
## ROUTE FOR INDEX ✅
@routes.route('/')
def index():
    return redirect(url_for('routes.login'))

## ROUTE FOR LOGIN PAGE ✅ 
@routes.route('/login', methods=['GET', 'POST'])
def login():

    # If access_token is present, assume logged in
    if request.cookies.get('access_token'):
        return redirect(url_for('routes.home'))

    session.pop('_flashes', None)

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        remember_me = request.form.get('remember_me') == 'on'

        print(remember_me)

        base = API_BASE_URL.rstrip('/') if API_BASE_URL else ''
        login_url = f"{base}/auth/login"
        print(f'Calling API URL: {login_url}')
        try:
            response = requests.post(login_url, json={
                'email': email,
                'password': password,
                'remember_me': remember_me
            }, timeout=10)
        except Exception as e:
            print(f"Login request exception: {e}")
            clear_and_flash("⛔ Could not reach auth server. Try again later.", "error")
            return redirect(url_for('routes.login'))

        if response.status_code == 200:
            data = response.json()
            access_token = data['access_token']
            refresh_token = data['refresh_token']

            # ✅ Redirect response, not render
            resp = redirect(url_for('routes.home'))

            is_production = os.getenv('FLASK_ENV') == 'production'

            # ✅ Set cookies on response object
            response_obj = make_response(resp)

            # Cookie expiration (e.g., 1 hour access token, 1 year refresh token)
            access_token_age = 60 * 5  #1 hour
            refresh_token_age = 60 * 60 * 24 * 365  # 1 year

            if remember_me:
                response_obj.set_cookie('access_token', access_token, httponly=True, samesite='Lax',
                                        secure=is_production, max_age=access_token_age)
                response_obj.set_cookie('refresh_token', refresh_token, httponly=True, samesite='Lax',
                                        secure=is_production, max_age=refresh_token_age)
            else:
                # Session cookies (no max_age) – clears on browser close
                response_obj.set_cookie('access_token', access_token, httponly=True, samesite='Lax',
                                        secure=is_production)
                response_obj.set_cookie('refresh_token', refresh_token, httponly=True, samesite='Lax',
                                        secure=is_production)
                

            # clear_and_flash("✅ Login successful!")
            session['show_home_modal'] = True
            return response_obj


        # Flash only on 401 or 404
        if response.status_code in [401, 404]:
            clear_and_flash("⛔ Login failed. Check your email and password.", "error")

        return redirect(url_for('routes.login'))

    return render_template('login.html')



## ROUTE FOR FORGOT PASSWORD PAGE ✅
@routes.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        response = requests.post(f'{API_BASE_URL}/auth/forgot-password', json={'email': email})

        if response.status_code == 200:
            clear_and_flash("✅ Check your email for a reset link.")
        else:
            clear_and_flash("⛔ Couldn't send reset email.")
    return render_template('forgot_password.html', random_subhead=random_subheader())


## ROUTE FOR RESET PASSWORD PAGE ✅
@routes.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    token = request.args.get('token')

    if request.method == 'POST':
        new_password = request.form['password']
        response = requests.post(f'{API_BASE_URL}/auth/reset-password', json={
            'token': token,
            'password': new_password
        })

        if response.status_code == 200:
            clear_and_flash("✅ Password reset successfully.")
            return redirect(url_for('routes.login'))
        else:
            clear_and_flash("⛔ Reset failed. Try again.")
    
    return render_template('reset_password.html', token=token, random_subhead=random_subheader())


## ROUTE TO LOGOUT (API CALL) ✅ 
@routes.route('/logout', methods=['POST'])
@login_required
def logout():
    refresh_token = request.cookies.get('refresh_token')

    if not refresh_token:
        return jsonify({'error': 'Refresh token is missing'}), 400

    try:
        # Send the refresh token to your backend auth server
        backend_logout_response = requests.post(
            f'{API_BASE_URL}/auth/logout',
            cookies={'refresh_token': refresh_token}  # ← send it in cookie
        )

        if backend_logout_response.status_code == 200:
            resp = make_response(jsonify({'message': 'Logged out successfully'}))
            resp.delete_cookie('access_token')
            resp.delete_cookie('refresh_token')
            return resp
        else:
            print("Backend logout failed:", backend_logout_response.text)
            return jsonify({'error': 'Logout failed'}), 400

    except Exception as e:
        print(f"Logout exception: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred during logout.'}), 500


## ROUTE FOR HOME PAGE ✅ 
@routes.route('/home')
@login_required
def home():
    # ✅ Token has already been validated/refreshed, and user is set in `g`
    user = g.get("user") 
    
    access_token = g.get("access_token")
    # print(f"User from g: {g.get('user')}")
    
    session_requests = get_api_session()

    headers = {'Authorization': f'Bearer {access_token}'}
    user_profile = threaded_get({'user_profile': f'{API_BASE_URL}/user/profile'}, headers=headers).get('user_profile', {}).get('data', {})

    show_home_modal = session.pop('show_home_modal', False)

    # Next 7 days of everything; today's slice drives the schedule and agenda
    from datetime import timedelta
    today = _today()
    week_items, past_meals, google_reconnect = [], [], False
    try:
        sched_res = requests.get(f"{API_BASE_URL}/schedule",
                                 params={'start': today.isoformat(), 'end': (today + timedelta(days=5)).isoformat()},
                                 headers=headers, timeout=15)
        if sched_res.status_code == 200:
            week_items = sched_res.json().get('items', [])
            google_reconnect = bool(sched_res.json().get('google_reconnect'))
        # yesterday, for the meals strip only (overdue items get pulled onto a range's first day, so keep this separate)
        past_res = requests.get(f"{API_BASE_URL}/schedule",
                                params={'start': (today - timedelta(days=1)).isoformat(), 'end': (today - timedelta(days=1)).isoformat()},
                                headers=headers, timeout=15)
        past_meals = [i for i in past_res.json().get('items', []) if i['type'] == 'meal'] if past_res.status_code == 200 else []
    except requests.RequestException as e:
        past_meals = []
        print(f"Could not load the schedule: {e}")
    schedule_items = _mark_work([i for i in week_items if i['date'] == today.isoformat()])
    week_days = []
    meal_items = [i for i in week_items + past_meals if i['type'] == 'meal']
    for n in range(-1, 6):  # yesterday, today, then five days ahead
        day = today + timedelta(days=n)
        todays = [i for i in meal_items if i['date'] == day.isoformat()]
        sections = []  # one per meal type that has something planned, in order of the day
        for kind in ('Breakfast', 'Lunch', 'Snack', 'Dinner', 'Dessert', 'Meal'):
            dishes = [{'title': i['title'], 'label': i.get('label'), 'meal_id': i.get('meal_id')} for i in todays if i.get('meal_type', 'Meal') == kind]
            if dishes:
                sections.append({'type': kind, 'dishes': dishes})
        week_days.append({'label': 'Tonight' if n == 0 else day.strftime('%a'), 'date_text': day.strftime('%b %-d'),
                          'is_today': n == 0, 'is_past': n < 0, 'sections': sections})
    has_planned_meals = any(d['sections'] for d in week_days)

    timed, all_day, agenda = [], [], []
    for i in schedule_items:
        i['when'] = _fmt_time(i['start_time']) if i.get('start_time') else 'All day'
        if i['type'] in ('todo', 'reminder', 'prep'):
            agenda.append(i)
        (timed if i.get('start_time') else all_day).append(i)
    events_today = [i for i in schedule_items if i['type'] in ('event', 'gcal')]
    working_location = next((i['title'] for i in schedule_items if i['type'] == 'workloc'), None)
    hour = datetime.now(ZoneInfo(os.getenv("APP_TIMEZONE", "America/Chicago"))).hour
    greeting = 'Good morning' if hour < 12 else 'Good afternoon' if hour < 17 else 'Good evening'

    # Build user object for template with name from profile
    user_for_template = {
        **user,
        'name': user_profile.get('name', user.get('name'))
    }

    from app.weather import forecast
    return render_template('home.html', weather=forecast(), working_location=working_location, google_reconnect=google_reconnect,
        random_subhead=random_subheader(), user=user_for_template, show_home_modal=show_home_modal,
        help_modal='home',
        greeting=greeting, today_text=today.strftime('%A, %B %-d'),
        schedule_items=schedule_items, agenda=agenda, timed=timed, all_day=all_day,
        events_today=events_today, week_days=week_days, has_planned_meals=has_planned_meals,
        today=today.isoformat())


# --------------- #
### MEAL ROUTES ###

## ROUTE FOR SHOW ALL MEALS PAGE ✅
@routes.route('/meals')
@login_required
def meals():
    user = g.get("user")
    access_token = g.get("access_token")
    
    session_requests = get_api_session()
    headers = {'Authorization': f'Bearer {access_token}'}

    user_headers = {'Authorization': f"Bearer {g.access_token}"}

    user_prefs = requests.get(f"{API_BASE_URL}/user/profile" , headers=user_headers)
    if user_prefs.status_code == 200:
        user_profile = user_prefs.json()


    # Fetch meals
    meals_list = []
    try:
        response = session_requests.get(f'{API_BASE_URL}/meals', headers=headers)

        if response.status_code == 200:
            meals_data = response.json()
            meals_list = meals_data.get("meals", meals_data) if isinstance(meals_data, dict) else meals_data

        print("⚠️ Failed to fetch meals." if response.status_code != 200 else "✅ Meals fetched.")
    except Exception as e:
        print(f"Exception while fetching meals: {e}")

    # Fetch ingredients and categories
    ingredients = []
    ingredient_categories = []
    try:
        ingredients_response = requests.get(f'{API_BASE_URL}/ingredients', headers=headers)
        categories_response = requests.get(f'{API_BASE_URL}/ingredient_categories', headers=headers)
        
        if ingredients_response.status_code == 200:
            ingredients = ingredients_response.json()
        
        if categories_response.status_code == 200:
            ingredient_categories = categories_response.json()
            category_lookup = {cat["id"]: cat["name"] for cat in ingredient_categories}
            
            # Attach category_name to each ingredient
            for ing in ingredients:
                cat_id = ing.get("category_id")
                ing["category_name"] = category_lookup.get(cat_id, "—")

        print("✅ Ingredients and categories fetched.")
    except Exception as e:
        print(f"Exception while fetching ingredients: {e}")

    return render_template(
        'meals.html',
        meals=meals_list,
        ingredients=ingredients,
        ingredient_categories=ingredient_categories,
        random_subhead=random_subheader(),
        user=user
    )


## ROUTE TO TOGGLE FAVORITE STATUS ✅
@routes.route('/meals/<int:meal_id>/favorite', methods=['POST'])
@login_required
def toggle_favorite(meal_id):
    user = g.get("user")
    access_token = g.get("access_token")

    session_requests = get_api_session()
    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}

    is_favorite = request.json.get('is_favorite')
    print(f"Toggling is_favorite for meal {meal_id} to {is_favorite}")

    try:
        response = session_requests.put(f'{API_BASE_URL}/meals/{meal_id}', json={'is_favorite': is_favorite}, headers=headers)
        if response.status_code == 200:
            print('Meal favorite status updated successfully.')
            return jsonify({'success': True})
        else:
            print(f"Failed to update favorite status: {response.text}")
            return jsonify({'success': False, 'error': response.text}), 400
    except Exception as e:
        print(f"Exception toggling favorite: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


## ROUTE FOR VIEW MEAL DETAILS PAGE ✅
@routes.route('/meals/<int:meal_id>')
@login_required
def meal_detail(meal_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}
    
    user_headers = {'Authorization': f"Bearer {g.access_token}"}

    user_prefs = requests.get(f"{API_BASE_URL}/user/profile" , headers=user_headers)
    if user_prefs.status_code == 200:
        user_profile = user_prefs.json()

    # Fetch meal details
    response = requests.get(f'{API_BASE_URL}/meals/{meal_id}', headers=headers)
    if response.status_code == 200:
        meal = response.json()
        print(meal)
        if meal['tidbits'] is None:
            meal['tidbits'] = ""
        if meal['website_link'] is None:
            meal['website_link'] = ""

        urls = {
            'cuisines': f'{API_BASE_URL}/cuisines',
            'categories': f'{API_BASE_URL}/categories',
            'tags': f'{API_BASE_URL}/meals/tags',
            'ingredient_categories': f'{API_BASE_URL}/ingredient_categories'
        }

        results = threaded_get(urls, headers=headers)
        prep_resp = requests.get(f'{API_BASE_URL}/meals/{meal_id}/prep', headers=headers)
        prep_steps = prep_resp.json().get('steps', []) if prep_resp.status_code == 200 else []
        
        return render_template('meal.html', meal=meal, prep_steps=prep_steps, random_subhead=random_subheader(), api_base_url=API_BASE_URL,
                                cuisines=results['cuisines']['data'] if results['cuisines']['status_code'] == 200 else [],
                                categories=results['categories']['data'] if results['categories']['status_code'] == 200 else [],
                                tags=results['tags']['data'] if results['tags']['status_code'] == 200 else [],
                                ingredient_categories=results['ingredient_categories']['data'] if results['ingredient_categories']['status_code'] == 200 else [],
                                access_token=g.access_token, back_href=url_for('routes.meals'))
    
    print("⚠️ Failed to fetch meal details.")
    return redirect(url_for('routes.meals'))


## PREP STEPS (things to do ahead of a dish)
@routes.route('/meals/<int:meal_id>/prep', methods=['POST'])
@login_required
def add_prep_step(meal_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}
    try:
        days_before = int(request.form.get('days_before', 1))
    except ValueError:
        days_before = 1
    response = requests.post(f"{API_BASE_URL}/meals/{meal_id}/prep", headers=headers,
                             json={'text': request.form.get('text', ''), 'days_before': days_before})
    if response.status_code != 201:
        clear_and_flash((response.json() or {}).get('error', "Could not add the prep step."), "error")
    return redirect(url_for('routes.meal_detail', meal_id=meal_id))


@routes.route('/meals/<int:meal_id>/prep/<int:step_id>/delete', methods=['POST'])
@login_required
def delete_prep_step(meal_id, step_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.delete(f"{API_BASE_URL}/prep_steps/{step_id}", headers=headers)
    if response.status_code != 200:
        clear_and_flash("Could not remove the prep step.", "error")
    return redirect(url_for('routes.meal_detail', meal_id=meal_id))


@routes.route('/prep/done', methods=['POST'])
@login_required
def prep_done():
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.post(f"{API_BASE_URL}/prep_done", headers=headers,
                             json={'meal_plan_meal_id': request.form.get('meal_plan_meal_id'),
                                   'step_id': request.form.get('step_id')})
    if response.status_code != 200:
        clear_and_flash("Could not update the prep step.", "error")
    return _back_to('routes.schedule')


## ROUTE TO UPDATE A MEAL (API CALL) ✅
@routes.route('/meals/<int:meal_id>', methods=['POST'])
@login_required
def update_meal(meal_id):

    user_headers = {'Authorization': f"Bearer {g.access_token}"}

    user_prefs = requests.get(f"{API_BASE_URL}/user/profile" , headers=user_headers)
    if user_prefs.status_code == 200:
        user_profile = user_prefs.json()


    headers = {
        'Authorization': f"Bearer {g.access_token}",
        'Content-Type': 'application/json'
    }

    tags_raw = request.form.get('tags', '')
    tags = [tag.strip() for tag in tags_raw.split(',') if tag.strip()]

    categories_raw = request.form.get('category', '')
    print(f"categories raw: {categories_raw}")
    categories = [category.strip() for category in categories_raw.split(',') if category.strip()]
    if len(categories) == 0:
        categories = ['Dinner']
    # print(f"Category names: {categories}")


    already_default = request.form.get('is_default')
    if 'make_it_mine' in request.form:
        make_it_mine = request.form.get('make_it_mine')
    else:
        make_it_mine = None

    is_default = False if make_it_mine == 'true' or already_default == 'False' else True

    # category_names = request.form.getlist('category')
    # if len(category_names) == 0:
    #     category_names = ['Dinner']
    # print(f"Category names: {category_names}")

    # Base meal fields
    updated_data = {
        'name': request.form.get('name'),
        'emoji': request.form.get('emoji'),
        'cuisine': request.form.get('cuisine'),
        'tidbits': request.form.get('tidbits'),
        'website_link': request.form.get('website_link'),
        'is_side_dish': request.form.get('is_side_dish') == 'on',
        'categories': categories,
        'ingredients': [],
        'tags': [],
        'is_default': is_default
    }

    updated_data['tags'] = tags

    # Optional: Ingredients if passed from a hidden input
    ingredients_json = request.form.get('ingredients')
    if ingredients_json:
        try:
            updated_data['ingredients'] = json.loads(ingredients_json)
        except Exception as e:
            print(f"⚠️ Failed to parse ingredients: {str(e)}")

    print(f"UPDATED DATA: {updated_data}")

    response = requests.put(f'{API_BASE_URL}/meals/{meal_id}', json=updated_data, headers=headers)
    if response.status_code == 200:
        print("Meal updated successfully.")
        # clear_and_flash("✅ Meal updated successfully!")
        if make_it_mine == 'true':
            return redirect(url_for('routes.meal_detail', meal_id=meal_id))
        else:
            return redirect(url_for('routes.meals'))
    else:
        clear_and_flash("⚠️ Failed to update meal.")
        print("Failed to update meal:", response.json())

    return redirect(url_for('routes.meal_detail', meal_id=meal_id))


## ROUTE FOR NEW MEAL PAGE ✅
@routes.route('/meals/new', methods=['GET'])
@login_required
def new_meal():

    user_headers = {'Authorization': f"Bearer {g.access_token}"}

    user_prefs = requests.get(f"{API_BASE_URL}/user/profile" , headers=user_headers)
    if user_prefs.status_code == 200:
        user_profile = user_prefs.json()

    headers = {'Authorization': f"Bearer {g.access_token}"}

    urls = {
        'cuisines': f'{API_BASE_URL}/cuisines',
        'categories': f'{API_BASE_URL}/categories',
        'tags': f'{API_BASE_URL}/meals/tags'
    }

    results = threaded_get(urls, headers=headers)
    # print (f"RESULTS: {results['tags']}")

    return render_template(
        'meal.html', meal=None,
        cuisines=results['cuisines']['data'] if results['cuisines']['status_code'] == 200 else [],
        categories=results['categories']['data'] if results['categories']['status_code'] == 200 else [],
        mode='new', tags=results['tags']['data'] if results['tags']['status_code'] == 200 else [],
        random_subhead=random_subheader(), back_href=url_for('routes.meals'))


## ROUTE TO CREATE A MEAL (API CALL) ✅
@routes.route('/meals', methods=['POST'])
@login_required
def create_meal():

    # Get form data
    meal_name = request.form['name']
    emoji = request.form.get('emoji', '')
    cuisine_name = request.form.get('cuisine', '')
    is_side_dish = 'is_side_dish' in request.form
    category_names = request.form.getlist('category')
    tidbits = request.form['tidbits']
    website_link = request.form['website_link']
    ingredients = json.loads(request.form['ingredients'])
    tags_raw = request.form.get('tags', '')
    tags = [tag.strip() for tag in tags_raw.split(',') if tag.strip()]

    categories = category_names if len(category_names) != 0 else ['Dinner']

    # Create meal object
    meal_data = {
        'name': meal_name,
        'emoji': emoji if emoji else None,
        'cuisine': cuisine_name,
        'is_default': False,
        'is_side_dish': is_side_dish,
        'categories': categories,
        'tidbits': tidbits,
        'website_link': website_link,
        'ingredients': ingredients,
        'tags': tags
    }

    try:
        # 🔍 Print what you're sending
        print("Sending meal creation request with this data:")
        pprint.pprint(meal_data)

        # 📡 Make the request with timeout
        response = requests.post(
            f'{API_BASE_URL}/meals',
            json=meal_data,
            headers={'Authorization': f"Bearer {g.access_token}"},
            timeout=5
        )

        # 📥 Print the response you got back
        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.text}")

        if response.status_code == 201:
            response_json = response.json()
            meal_id = response_json.get("meal_id")
            # clear_and_flash("✅ Meal created successfully!")
            return redirect(url_for('routes.update_meal', meal_id=meal_id))
        else:
            clear_and_flash("⛔ Failed to create meal. Please try again.")
            return redirect(url_for('routes.new_meal'))

    except Exception as e:
        # 🧨 Print the error if something breaks
        print(f"Error during meal creation: {e}")
        # clear_and_flash(f"⛔ An error occurred: {e}")
        return redirect(url_for('routes.new_meal'))


## DELETE A MEAL (API CALL) ✅
@routes.route('/meals/<int:meal_id>/delete', methods=['POST'])
@login_required
def delete_meal(meal_id):
    if request.form.get('_method') != 'DELETE':
        return "Method Not Allowed", 405

    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.delete(f'{API_BASE_URL}/meals/{meal_id}', headers=headers)

    if response.status_code == 200:
        # clear_and_flash("✅ Meal deleted successfully!")
        pass
    else:
        clear_and_flash("⚠️ Failed to delete meal.")

    return redirect(url_for('routes.meals'))


## ROUTE TO BULK ADD MEALS PAGE ✅
@routes.route('/meals/bulk-add', methods=['GET', 'POST'])
@login_required
def bulk_add_meals():
    if request.method == 'POST':
        meal_entries = request.form.getlist('meals')  # we'll parse JSON on frontend
        try:
            success_count = 0
            fail_count = 0

            for meal_data_json in meal_entries:
                meal_data = json.loads(meal_data_json)
                print(f"Meal data JSON: {meal_data}")

                response = requests.post(
                    f'{API_BASE_URL}/meals',
                    json=meal_data,
                    headers={'Authorization': f"Bearer {g.access_token}"},
                    timeout=15
                )

                if response.status_code == 201:
                    success_count += 1
                else:
                    fail_count += 1

            print(f"✅ {success_count} meals created successfully. ⛔ {fail_count} failed.")
            return redirect(url_for('routes.meals'))  # or somewhere else

        except Exception as e:
            print(f"Bulk add error: {e}")
            # clear_and_flash(f"⛔ Error during bulk meal creation: {e}")
            return redirect(url_for('routes.bulk_add_meals'))

    else:
        headers = {'Authorization': f"Bearer {g.access_token}"}

        urls = {
            'cuisines': f'{API_BASE_URL}/cuisines',
            'categories': f'{API_BASE_URL}/categories'
        }

        results = threaded_get(urls, headers=headers)

        return render_template(
            'bulk_add_meals.html', back_href=url_for('routes.meals'), random_subhead=random_subheader(),
            cuisines=results['cuisines']['data'] if results['cuisines']['status_code'] == 200 else [],
            categories=results['categories']['data'] if results['categories']['status_code'] == 200 else []
        )


## ROUTE FOR EDIT TAGS PAGE ✅
@routes.route('/edit-tags', methods=['GET'])
@login_required
def edit_tags():
    
    headers = {'Authorization': f"Bearer {g.access_token}"}

    response = requests.get(f'{API_BASE_URL}/meals/tags', headers=headers)

    user_headers = {'Authorization': f"Bearer {g.access_token}"}
    user_prefs = requests.get(f"{API_BASE_URL}/user/profile" , headers=user_headers)
    if user_prefs.status_code == 200:
        user_profile = user_prefs.json()


    if response.status_code == 200:
        tags = response.json()
    else:
        tags = []

    return render_template('edit_tags.html', random_subheader=random_subheader(),
                           back_href=url_for('routes.meals'), tags=tags,
                           access_token=g.access_token, api_base_url=API_BASE_URL)


## ROUTE TO ADD NEW TAG (API CALL) ✅
@routes.route('/add-tag', methods=['POST'])
@login_required
def add_tag():
    name = request.form.get('name', '').strip()

    if not name:
        clear_and_flash('Tag name is required.', 'error')
        return redirect(url_for('routes.edit_tags'))

    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.post(
        f'{API_BASE_URL}/meals/tags',
        json={'name': name},
        headers=headers
    )

    if response.status_code == 201:
        clear_and_flash('Tag created.', 'success')
    else:
        try:
            error = response.json().get('error', 'Tag creation failed.')
        except:
            error = f'Tag creation failed. (Status: {response.status_code})'
        clear_and_flash(error, 'error')

    return redirect(url_for('routes.edit_tags'))


## ROUTE TO EDIT TAG (API CALL) ✅
@routes.route('/edit-tag', methods=['POST'])
@login_required
def edit_tag():
    original_name = request.form.get('original_name', '').strip()
    new_name = request.form.get('new_name', '').strip()

    if not original_name or not new_name:
        clear_and_flash('Tag name is required.', 'error')
        return redirect(url_for('routes.edit_tags'))

    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.put(
        f'{API_BASE_URL}/meals/tags/{original_name}',
        json={'name': new_name},
        headers=headers
    )

    if response.status_code == 200:
        clear_and_flash('Tag updated.', 'success')
    else:
        error = response.json().get('error', 'Update failed.')
        clear_and_flash(error, 'error')

    return redirect(url_for('routes.edit_tags'))


## ROUTE TO DELETE TAG (API CALL) ✅
@routes.route('/delete-tag', methods=['POST'])
@login_required
def delete_tag():
    name = request.form.get('name', '').strip()
    if not name:
        clear_and_flash('Tag name is required.', 'error')
        return redirect(url_for('routes.edit_tags'))

    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.delete(f'{API_BASE_URL}/meals/tags/{name}', headers=headers)

    if response.status_code == 200:
        clear_and_flash('Tag deleted.', 'success')
    else:
        error = response.json().get('error', 'Delete failed.')
        clear_and_flash(error, 'error')

    return redirect(url_for('routes.edit_tags'))


# -------------------- #
### MEAL PLAN ROUTES ###

## ROUTE FOR SHOW ALL MEAL PLANS PAGE ✅
@routes.route('/meal-plans')
@login_required
def meal_plans():
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.get(f'{API_BASE_URL}/meal_plans', headers=headers)

    if response.status_code == 200:
        data = response.json()
        meal_plans_list = data.get("meal_plans", [])
        finalized_plans, draft_plans = [], []

        for plan in meal_plans_list:
            if plan.get('finalized') is True:
                # Format creation date
                if 'created_at' in plan:
                    dt = datetime.strptime(plan['created_at'], "%a, %d %b %Y %H:%M:%S %Z")
                    plan['created_at'] = dt.strftime("%b %d, %Y")
                
                # Fetch full plan details to get meal checked status
                plan_id = plan.get('id')
                detailed_plan_res = requests.get(f'{API_BASE_URL}/meal_plan/{plan_id}', headers=headers)
                
                if detailed_plan_res.status_code == 200:
                    detailed_plan = detailed_plan_res.json()
                    meals = detailed_plan.get('meals', [])
                else:
                    meals = plan.get('meals', [])
                
                # Calculate meal completion stats
                total_meals = len(meals)
                cooked_meals = sum(1 for m in meals if m.get('is_checked'))
                percentage = int((cooked_meals / total_meals * 100)) if total_meals > 0 else 0
                
                plan['total_meals'] = total_meals
                plan['cooked_meals'] = cooked_meals
                plan['percentage'] = percentage
                
                finalized_plans.append(plan)
            else:
                if 'created_at' in plan:
                    dt = datetime.strptime(plan['created_at'], "%a, %d %b %Y %H:%M:%S %Z")
                    plan['created_at'] = dt.strftime("%b %d, %Y")
                draft_plans.append(plan)

        return render_template("meal_plans.html", meal_plans=finalized_plans, draft_plans=draft_plans, random_subhead=random_subheader())

    print("⚠️ Failed to fetch meal plans.")
    return render_template("meal_plans.html", meal_plans=[], draft_plans=[], random_subhead=random_subheader())


## ROUTE FOR VIEW A SINGLE MEAL PLAN PAGE ✅
@routes.route('/meal-plans/<int:meal_plan_id>', methods=['GET'])
@login_required
def view_meal_plan(meal_plan_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}

    # Get the meal plan
    response = requests.get(f'{API_BASE_URL}/meal_plan/{meal_plan_id}', headers=headers)
    print(f"Fetching meal plan from: {API_BASE_URL}/meal_plan/{meal_plan_id}")
    print(f"Response code: {response.status_code}")
    if response.status_code != 200:
        print("⚠️ Failed to fetch meal plan.")
        return redirect(url_for('routes.meal_plans'))
    meal_plan = response.json()
    print(meal_plan)

    # Format created date
    if 'meal_plan_created_at' in meal_plan:
        dt = datetime.strptime(meal_plan['meal_plan_created_at'], "%a, %d %b %Y %H:%M:%S %Z")
        meal_plan['meal_plan_created_at'] = dt.strftime("%b %d, %Y")

    # Get all meals
    all_meals_res = requests.get(f'{API_BASE_URL}/meals', headers=headers)
    print(f"Fetching all meals from: {API_BASE_URL}/meals")
    print(f"Response code: {all_meals_res.status_code}")
    if all_meals_res.status_code != 200:
        # clear_and_flash("⚠️ Failed to fetch full meal list.")
        return redirect(url_for('routes.meal_plans'))
    all_meals = all_meals_res.json()

    # Map all meals by ID
    meals_by_id = {meal['id']: meal for meal in all_meals}

    # Enrich each meal in the plan with full details
    enriched_meals = []
    for m in meal_plan.get('meals', []):
        meal_id = m['id']
        is_checked = m.get('is_checked', False)
        side_dish = m.get('side_dish')  # preserve it
        meal_plan_meal_id = m.get('meal_plan_meal_id')

        if meal_id in meals_by_id:
            enriched_meal = meals_by_id[meal_id]
            enriched_meal['is_checked'] = is_checked
            enriched_meal['side_dish'] = side_dish  # re-attach side dish
            enriched_meal['meal_plan_meal_id'] = meal_plan_meal_id
            enriched_meal['planned_date'] = m.get('planned_date')
            enriched_meals.append(enriched_meal)
        else:
            enriched_meals.append(m)

    meal_plan['meals'] = enriched_meals

    # Week board: seven days starting at ?week=, else the earliest planned day, else today
    from datetime import timedelta
    planned = sorted(m['planned_date'] for m in enriched_meals if m.get('planned_date'))
    try:
        week_start = datetime.strptime(request.args.get('week', ''), '%Y-%m-%d').date()
    except ValueError:
        week_start = datetime.strptime(planned[0], '%Y-%m-%d').date() if planned else _today()
    week_days = [{'iso': (week_start + timedelta(days=n)).isoformat(),
                  'label': (week_start + timedelta(days=n)).strftime('%a'),
                  'date_text': (week_start + timedelta(days=n)).strftime('%b %-d')} for n in range(7)]
    week_iso = {d['iso'] for d in week_days}
    tray_meals = [m for m in enriched_meals if not m.get('planned_date')]
    other_week_meals = sorted((m for m in enriched_meals if m.get('planned_date') and m['planned_date'] not in week_iso),
                              key=lambda m: m['planned_date'])
    for m in other_week_meals:
        m['planned_text'] = datetime.strptime(m['planned_date'], '%Y-%m-%d').strftime('%a %b %-d')

    return render_template('meal_plan.html', meal_plan=meal_plan, meals=all_meals, back_href=url_for('routes.meal_plans'),
                            api_base_url=API_BASE_URL, access_token=g.access_token, random_subhead=random_subheader(),
                            today=_today().isoformat(), week_days=week_days, tray_meals=tray_meals, other_week_meals=other_week_meals,
                            prev_week=(week_start - timedelta(days=7)).isoformat(),
                            next_week=(week_start + timedelta(days=7)).isoformat())


## ROUTE FOR TAGGING A MEAL PLAN (WHO IT IS FOR)
@routes.route('/meal-plans/<int:meal_plan_id>/label', methods=['POST'])
@login_required
def set_meal_plan_label(meal_plan_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.patch(f"{API_BASE_URL}/meal_plan/{meal_plan_id}/label",
                              json={'label': request.form.get('label', '')}, headers=headers)
    if response.status_code != 200:
        clear_and_flash(response.json().get('error', 'Could not save the tag.'), "error")
    return redirect(url_for('routes.view_meal_plan', meal_plan_id=meal_plan_id))


## ROUTE FOR GIVING A MEAL PLAN'S DINNERS DAYS
@routes.route('/meal-plans/<int:meal_plan_id>/dates', methods=['POST'])
@login_required
def set_meal_plan_dates(meal_plan_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}
    if request.is_json:  # drag-and-drop on the Week board
        body = request.get_json(silent=True) or {}
        payload = {'dates': {str(body.get('meal_plan_meal_id', '')): body.get('date') or None}}
        response = requests.patch(f"{API_BASE_URL}/meal_plan/{meal_plan_id}/dates", json=payload, headers=headers)
        return jsonify({'success': response.status_code == 200}), response.status_code
    if request.form.get('start_date'):
        payload = {'start_date': request.form['start_date']}
    else:
        payload = {'dates': {request.form.get('meal_plan_meal_id', ''): request.form.get('date') or None}}
    response = requests.patch(f"{API_BASE_URL}/meal_plan/{meal_plan_id}/dates", json=payload, headers=headers)
    if response.status_code != 200:
        clear_and_flash(response.json().get('error', 'Could not save the days.'), "error")
    return redirect(url_for('routes.view_meal_plan', meal_plan_id=meal_plan_id))


## ROUTE FOR REORDERING A MEAL PLAN (API CALL) ✅
@routes.route('/meal_plan/<int:meal_plan_id>/reorder', methods=['POST'])
@login_required
def reorder_meal_plan(meal_plan_id):
    try:
        data = request.get_json()
        ordered_ids = data.get("ordered_ids")
        ordered_ints = [int(i) for i in ordered_ids] if isinstance(ordered_ids, list) else []
            
        if not ordered_ids:
            return jsonify({"success": False, "error": "Missing ordered_ids"}), 400
    except Exception:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    # Send to API
    api_url = f"{API_BASE_URL}meal_plan/{meal_plan_id}/reorder_meals"
    headers = {'Authorization': f"Bearer {g.access_token}"}

    ordered_id_json = {"ordered_ids": ordered_ints}
    print(ordered_id_json)

    response = requests.patch(api_url, json=ordered_id_json, headers=headers)

    if response.ok:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": response.text}), response.status_code


## ROUTE FOR TOGGLING CHECKED STATE OF A MEAL ✅
@routes.route('/meal_plan/<int:meal_plan_id>/toggle_checked/<int:meal_id>', methods=['PATCH'])
@login_required
def toggle_checked_meal(meal_plan_id, meal_id):
    try:
        data = request.get_json()
        is_checked = data.get("is_checked", False)
    except Exception:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    # Send to API
    api_url = f"{API_BASE_URL}/meal_plan/{meal_plan_id}/toggle_checked/{meal_id}"
    headers = {'Authorization': f"Bearer {g.access_token}"}

    response = requests.patch(api_url, json={"is_checked": is_checked}, headers=headers)

    if response.ok:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": response.text}), response.status_code


## ROUTE FOR FETCHING GROCERIES FOR A MEAL PLAN ✅
@routes.route('/meal_plan/<int:meal_plan_id>/groceries', methods=['GET'])
@login_required
def get_meal_plan_groceries(meal_plan_id):
    """Fetch groceries for a specific meal plan from the API"""
    try:
        headers = {'Authorization': f"Bearer {g.access_token}"}
        
        # Call the API endpoint to get the grocery list
        api_url = f"{API_BASE_URL}/meal_plan/{meal_plan_id}/grocery_list"
        response = requests.get(api_url, headers=headers)
        
        if response.ok:
            groceries_data = response.json()
            
            # Extract the grocery_list from the API response
            # API returns: {"grocery_list": {category: {ingredient: {...}}}}
            grocery_dict = groceries_data.get('grocery_list', {})
            
            # Transform the nested dict into a flat array of grocery items
            # Structure: category -> ingredient_name -> {total_quantity, meal_details, average_quantity}
            flat_groceries = []
            for category, ingredients in grocery_dict.items():
                if isinstance(ingredients, dict):
                    for ingredient_name, ingredient_data in ingredients.items():
                        flat_groceries.append({
                            'name': ingredient_name,
                            'category': category,
                            'total_quantity': ingredient_data.get('total_quantity', 0),
                            'average_quantity': ingredient_data.get('average_quantity', 0),
                            'meal_details': ingredient_data.get('meal_details', []),
                            'checked': False
                        })
            
            return jsonify({"success": True, "groceries": flat_groceries})
        else:
            # Return empty groceries list if API call fails
            print(f"API error: {response.status_code} - {response.text}")
            return jsonify({"success": False, "groceries": []}), response.status_code
    except Exception as e:
        print(f"Error fetching groceries: {str(e)}")
        return jsonify({"success": False, "error": str(e), "groceries": []}), 500


## ROUTE FOR A NEW MEAL PLAN PAGE ✅
@routes.route('/meal-plan/new', methods=['GET', 'POST'])
@login_required
def new_meal_plan():

    session.pop('_flashes', None)

    headers = {'Authorization': f"Bearer {g.access_token}"}

    urls = {
        'user_profile': f'{API_BASE_URL}/user/profile',
        'categories': f'{API_BASE_URL}/categories',
        'meals': f'{API_BASE_URL}/meals',
        'tags': f'{API_BASE_URL}/meals/tags'
    }

    results = threaded_get(urls, headers=headers)

    user_profile = results['user_profile']['data']
    categories = results['categories']['data']
    meals = results['meals']['data']
    tags = results['tags']['data']

    print(tags)

    max_meals = 14

    if user_profile:
        return render_template('new_meal_plan.html', meals=meals, categories=categories, mode='new', max_meals=max_meals,
                                tags=tags, back_href=url_for('routes.meal_plans'), random_subhead=random_subheader())    

    print("⚠️ Failed to fetch meals or categories.")
    return redirect(url_for('routes.home'))


## ROUTE TO CREATE A NEW MEAL PLAN (API CALL) ✅
@routes.route('/meal-plan', methods=['POST'])
@login_required
def create_meal_plan():
    # Collect data from the form
    meal_plan_name = request.form['meal_plan_name']
    meals_quantity = int(request.form['meals_quantity'])  # Convert to int
    
    # Debug: log all form data
    print("=== FORM DATA ===")
    print(f"Form keys: {request.form.keys()}")
    for key in request.form.keys():
        print(f"{key}: {request.form[key]}")
    print("================")
    
    # Handle categories - can be JSON or form array
    if 'meal_categories_selected' in request.form and request.form['meal_categories_selected']:
        meal_categories = json.loads(request.form['meal_categories_selected'])
    else:
        meal_categories = request.form.getlist('meal_categories[]')
    
    # Handle meal IDs
    meal_ids_to_add = json.loads(request.form.get('meal_ids_to_add', '[]'))
    
    # Handle tags - can be JSON or form array
    if 'meal_tags_selected' in request.form and request.form['meal_tags_selected']:
        tags = json.loads(request.form['meal_tags_selected'])
    else:
        tags = request.form.getlist('meal_tags[]')
    
    # Ensure the data matches what the API expects
    meal_plan_data = {
        'meal_plan_name': meal_plan_name,
        'meals_quantity': meals_quantity,
        'meal_category': meal_categories,
        'meal_ids_to_add': meal_ids_to_add,
        'tags': tags
    }
    print(f"Meal Plan Data: {meal_plan_data}")

    headers = {'Authorization': f"Bearer {g.access_token}"}
    
    # Make the POST request to the API
    response = requests.post(f'{API_BASE_URL}/meal_plan', json=meal_plan_data, headers=headers)

    session['_flashes'] = []
    # Handle the response from the API
    if response.status_code == 201:
        print("✅ Meal plan created successfully!")
        new_id = response.json().get('meal_plan_id')
        label = request.form.get('label', '').strip()
        if label and new_id:
            requests.patch(f'{API_BASE_URL}/meal_plan/{new_id}/label', json={'label': label}, headers=headers)
        return redirect(url_for('routes.meal_plan_result', meal_plan_id=new_id))
    elif response.status_code == 302:
        print("⚠️ Redirected: Check if you're logged in or if data is correct.")
        return redirect(response.headers.get('Location'))  # Redirect based on the header if there's a Location header
    elif response.status_code == 403:
        clear_and_flash("⚠️ Free users can create up to 2 meal plans. Please delete an existing one to create a new one.")
        return redirect(url_for('routes.meal_plans'))
    elif response.status_code in (400, 404):
        print(response.text)
        try:
            error_message = response.json().get('error', response.text)
        except Exception as e:
            print("⚠️ JSON decoding failed:", e)
            error_message = response.text
        clear_and_flash(f"⚠️ {error_message}")
        return redirect(url_for('routes.new_meal_plan'))
    else:
        print(f"⚠️ Failed to create meal plan. Status Code: {response.status_code}, Error: {response.text}")
        return redirect(url_for('routes.meal_plans'))


## ROUTE FOR A GENERATED MEAL PLAN RESULT ✅
@routes.route('/meal-plan/<int:meal_plan_id>/edit')
@login_required
def meal_plan_result(meal_plan_id):

    headers = {'Authorization': f"Bearer {g.access_token}"}

    # Get the meal plan
    meal_plan_res = requests.get(f'{API_BASE_URL}/meal_plan/{meal_plan_id}', headers=headers)
    if meal_plan_res.status_code != 200:
        print("Failed to fetch meal plan.")
        return redirect(url_for('routes.meal_plans'))
    meal_plan = meal_plan_res.json()
    print(f"meal plan result: {meal_plan}")

    # Get all meals
    all_meals_res = requests.get(f'{API_BASE_URL}/meals', headers=headers)
    if all_meals_res.status_code != 200:
        print("Failed to fetch full meal list.")
        return redirect(url_for('routes.meal_plans'))
    all_meals = all_meals_res.json()

    # Convert list of all meals to a dict keyed by ID for fast lookup
    meals_by_id = {meal['id']: meal for meal in all_meals}

    help_text = 'none'
    for m in meal_plan.get('meals', []):
        if m.get('source') == 'filler_repeat':
            help_text = 'repeat'
            break
        elif m.get('source') == 'filler_random' or m.get('source') == 'filler_category':
            help_text = 'random'
            break

    # Enrich each meal in the plan with full details
    enriched_meals = []
    for m in meal_plan.get('meals', []):
        meal_id = m['id']
        if meal_id in meals_by_id:
            enriched_meal = meals_by_id[meal_id].copy()
            enriched_meal.update({
                'meal_plan_meal_id': m.get('meal_plan_meal_id'),
                'order': m.get('order'),
                'is_checked': m.get('is_checked'),
                'side_dish': m.get('side_dish'),
                'source': m.get('source')
            })
            enriched_meals.append(enriched_meal)
        else:
            enriched_meals.append(m)

    meal_plan['meals'] = enriched_meals
    print(f"meal plan result: {meal_plan}")


    return render_template('meal_plan_result.html', meal_plan=meal_plan, meals=all_meals, help_text=help_text,
                           back_href=url_for('routes.new_meal_plan'), random_subhead=random_subheader())


## ROUTE TO UPDATE A MEAL PLAN (API CALL) ✅
@routes.route('/meal-plan/<int:meal_plan_id>', methods=['POST'])
@login_required
def update_meal_plan(meal_plan_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}

    # Get values from form
    meal_ids_to_remove = json.loads(request.form['meal_ids_to_remove'])  # This will be a list of IDs
    meals_quantity = int(request.form['meals_quantity'])
    meal_category = request.form['meal_category']  # Assuming your API expects uppercase
    meal_plan_tags_raw = request.form['meal_tags']  # This will be a list of tags
    meal_ids_to_add = [int(x) for x in json.loads(request.form.get('meal_ids_to_add', '[]')) if x]

    tags = [tag.lower().strip() for tag in meal_plan_tags_raw.split(',') if tag.strip()]

    # Build the correct payload
    meal_plan_data = {
        'meal_ids_to_remove': meal_ids_to_remove,
        'meal_ids_to_add': meal_ids_to_add,
        'meals_quantity': meals_quantity,
        'meal_category': meal_category,
        'tags': tags
    }

    print(f"Updated Meal Plan Data: {meal_plan_data}")

    # PUT request to API
    response = requests.put(
        f'{API_BASE_URL}/meal_plan/{meal_plan_id}',
        json=meal_plan_data,
        headers=headers
    )

    if response.status_code == 200:
        print("✅ Meal plan updated successfully!")
        
        # Check if side dishes were cleared during re-edit
        response_data = response.json()
        if response_data.get('cleared_side_dishes'):
            clear_and_flash("✅ Meal plan updated! Your side dishes have been preserved. Go to 'Add Side Dishes' to adjust them for any newly replaced meals.")
        
        return redirect(url_for('routes.meal_plan_result', meal_plan_id=meal_plan_id))
    else:
        print(f"⚠️ Failed to update meal plan. Status Code: {response.status_code}, Error: {response.text}")
        clear_and_flash("Failed to update meal plan.")
        return redirect(url_for('routes.meal_plan_result', meal_plan_id=meal_plan_id))


## ROUTE FOR THE ADD SIDE DISHES PAGE ✅
@routes.route('/meal-plan/<int:meal_plan_id>/add-side-dishes', methods=['GET'])
@login_required
def add_side_dishes_page(meal_plan_id):

    user_headers = {'Authorization': f"Bearer {g.access_token}"}

    user_prefs = requests.get(f"{API_BASE_URL}/user/profile" , headers=user_headers)
    if user_prefs.status_code == 200:
        user_profile = user_prefs.json()

    headers = {'Authorization': f"Bearer {g.access_token}"}
    # Get the specific meal plan
    meal_plan_res = requests.get(f'{API_BASE_URL}/meal_plan/{meal_plan_id}', headers=headers)
    if meal_plan_res.status_code != 200:
        print("Failed to fetch meal plan.")
        return redirect(url_for('routes.meal_plans'))
    meal_plan = meal_plan_res.json()

    # Get all meals (including possible side dishes)
    all_meals_res = requests.get(f'{API_BASE_URL}/meals', headers=headers)
    if all_meals_res.status_code != 200:
        print("Failed to fetch full meal list.")
        return redirect(url_for('routes.meal_plans'))
    all_meals = all_meals_res.json()

    # Create a dict of meals by ID
    meals_by_id = {meal['id']: meal for meal in all_meals}

    # Enrich each meal in the plan with full details
    enriched_meals = []
    for m in meal_plan.get('meals', []):
        meal_id = m['id']
        if meal_id in meals_by_id:
            enriched_meal = meals_by_id[meal_id].copy()
            # Preserve side_dish data from the meal plan
            if m.get('side_dish'):
                enriched_meal['side_dish_id'] = m['side_dish'].get('id')
                enriched_meal['side_dish_name'] = m['side_dish'].get('name')
            else:
                enriched_meal['side_dish_id'] = None
                enriched_meal['side_dish_name'] = None
            enriched_meals.append(enriched_meal)
        else:
            enriched_meals.append(m)
    meal_plan['meals'] = enriched_meals

    # Filter out side dishes
    available_side_dishes = [meal for meal in all_meals if meal.get('is_side_dish')]

    return render_template(
        'add_side_dishes.html',
        meal_plan=meal_plan, back_href=url_for('routes.meal_plan_result', meal_plan_id=meal_plan_id),
        available_side_dishes=available_side_dishes, meal_plan_id=meal_plan_id,
        random_subhead=random_subheader(), access_token=g.access_token)


## ROUTE TO ASSIGN SIDE DISHES AND FINALIZE MEAL PLAN (API CALL) ✅
@routes.route('/meal-plan/<int:meal_plan_id>/add-side-dishes-and-finalize', methods=['POST'])
@login_required
def add_side_dishes_and_finalize(meal_plan_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}

    # STEP 1: Assign side dishes
    side_dishes = {}

    for key, value in request.form.items():
        if key.startswith("side_dish_") and value.strip():
            try:
                int_value = int(value)
                if int_value > 0:
                    meal_id = key.replace("side_dish_", "")
                    side_dishes[meal_id] = int_value
            except ValueError:
                continue

    payload = {'side_dishes': side_dishes}
    print(f"Sending side dish assignment payload: {payload}")

    response = requests.put(
        f'{API_BASE_URL}/meal_plan/{meal_plan_id}/add_side_dishes',
        json=payload,
        headers=headers
    )

    if response.status_code != 200:
        print(f"❌ Failed to assign side dishes: {response.status_code} - {response.text}")
        clear_and_flash("Failed to assign side dishes.")
        return redirect(url_for('routes.add_side_dishes_page', meal_plan_id=meal_plan_id))

    # Step 2: Finalize the meal plan (if not already finalized)
    finalize_response = requests.put(f'{API_BASE_URL}/meal_plan/{meal_plan_id}/finalize', headers=headers)

    if finalize_response.status_code == 200:
        print("✅ Meal plan finalized.")
        return redirect(url_for('routes.view_meal_plan', meal_plan_id=meal_plan_id, new='true'))
    else:
        # Check if plan is already finalized (which is ok for re-editing)
        error_data = finalize_response.json()
        if "already finalized" in error_data.get('error', '').lower():
            print("✅ Meal plan already finalized - side dishes updated.")
            return redirect(url_for('routes.view_meal_plan', meal_plan_id=meal_plan_id))
        else:
            print(f"❌ Failed to finalize meal plan: {finalize_response.status_code} - {finalize_response.text}")
            clear_and_flash("Failed to finalize meal plan.")
            return redirect(url_for('routes.add_side_dishes_page', meal_plan_id=meal_plan_id))


## ROUTE FOR DELETE MEAL PLAN (API CALL) ✅
@routes.route('/meal-plan/<int:meal_plan_id>/delete', methods=['POST'])
@login_required
def delete_meal_plan(meal_plan_id):
    if request.form.get('_method') != 'DELETE':
        return "Method Not Allowed", 405
    
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.delete(f'{API_BASE_URL}/meal_plan/{meal_plan_id}', headers=headers)

    if response.status_code == 200:
        print("✅ Meal plan deleted successfully!")
    else:
        print("⚠️ Failed to delete meal plan.")

    return redirect(url_for('routes.meal_plans'))


## ROUTE FOR DELETE MEAL PLAN (JSON API CALL) ✅
@routes.route('/meal_plan/<int:meal_plan_id>/delete', methods=['POST'])
@login_required
def delete_meal_plan_json(meal_plan_id):
    """Delete a meal plan via JSON API call from JavaScript"""
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.delete(f'{API_BASE_URL}/meal_plan/{meal_plan_id}', headers=headers)

    if response.status_code == 200:
        print("✅ Meal plan deleted successfully!")
        return jsonify({"success": True}), 200
    else:
        print("⚠️ Failed to delete meal plan.")
        return jsonify({"success": False, "error": "Failed to delete meal plan"}), response.status_code


# ------------------- #
## INGREDIENT ROUTES ##

## ROUTE FOR SHOW INGREDIENTS PAGE ✅
@routes.route('/ingredients', methods=['GET'])
@login_required
def ingredients():
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.get(f'{API_BASE_URL}/ingredients', headers=headers)

    categories_resp = requests.get(f'{API_BASE_URL}/ingredient_categories', headers=headers)
    categories = categories_resp.json() if categories_resp.status_code == 200 else []
    category_lookup = {cat["id"]: cat["name"] for cat in categories}

    if response.status_code == 200:
        ingredients = response.json()

        # Attach category_name to each ingredient
        for ing in ingredients:
            cat_id = ing.get("category_id")
            ing["category_name"] = category_lookup.get(cat_id, "—")

        return render_template(
            'ingredients.html',
            ingredients=ingredients,
            categories=categories,
            random_subhead=random_subheader()
        )

    print("⚠️ Failed to fetch ingredients.")
    return render_template(
        'ingredients.html',
        ingredients=[],
        categories=categories,
        random_subhead=random_subheader()
    )


## ROUTE TO GET INGREDIENTS AS JSON (for autocomplete)
@routes.route('/ingredients-list', methods=['GET'])
@login_required
def ingredients_list():
    """Returns ingredients as JSON for autocomplete with IDs for linking"""
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.get(f'{API_BASE_URL}/ingredients', headers=headers)

    if response.status_code == 200:
        ingredients = response.json()
        # Return ingredient names and IDs so we can link to actual ingredients
        return jsonify([{'name': ing.get('name', ''), 'id': ing.get('id')} for ing in ingredients])
    
    print("⚠️ Failed to fetch ingredients for autocomplete.")
    return jsonify([]), 400



## ROUTE TO ADD NEW INGREDIENT (API CALL) ✅
@routes.route('/ingredients/new', methods=['POST'])
@login_required
def new_ingredient():
    headers = {
        'Authorization': f"Bearer {g.access_token}",
        'Content-Type': 'application/json'
    }

    name = request.form.get('name')
    category_name = request.form.get('category_name')
    payload = {'name': name, 'category_name': category_name}
    response = requests.post(f'{API_BASE_URL}/ingredients', json=payload, headers=headers)

    if response.status_code == 201:
        print(f"✅ '{name}' added successfully!")
        return redirect(url_for('routes.ingredients'))  # Redirect to the ingredients section of the meals page
    else:
        print(f"⚠️ Failed to add ingredient: {response.json().get('message', 'Unknown error')}")

    return redirect(url_for('routes.ingredients'))


## ROUTE TO EDIT AN INGREDIENT (API CALL) ✅
@routes.route('/ingredients/<int:ingredient_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_ingredient(ingredient_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}

    name = request.form.get('name')
    category_name = request.form.get('category_name')
    update_payload = {'name': name, 'category_name': category_name}
    headers['Content-Type'] = 'application/json'
    put_resp = requests.put(f'{API_BASE_URL}/ingredients/{ingredient_id}', json=update_payload, headers=headers)

    if put_resp.status_code == 200:
        # clear_and_flash(f"✅ '{name}' updated successfully!")
        return redirect(url_for('routes.ingredients'))
    clear_and_flash(f"⚠️ Failed to update ingredient: {put_resp.json().get('message', 'Unknown error')}")

    return redirect(url_for('routes.ingredients'))


## ROUTE TO DELETE AN INGREDIENT (API CALL) ✅
@routes.route('/ingredients/<int:ingredient_id>/delete', methods=['POST'])
@login_required
def delete_ingredient(ingredient_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.delete(f'{API_BASE_URL}/ingredients/{ingredient_id}', headers=headers)

    if response.status_code == 204:
        print("🗑️ Ingredient deleted.")
    else:
        print("⚠️ Failed to delete ingredient.")
    return redirect(url_for('routes.meals'))


## ROUTE FOR PERSONAL GROCERY LIST ✅
@routes.route('/grocery_list', methods=['GET'])
@login_required
def grocery_list():
    """
    Display user's personal grocery list (all scratch items from active meal plans).
    Shows which meal plans contributed items to this list with proper item counts.
    """
    headers = {'Authorization': f"Bearer {g.access_token}"}
    
    # Fetch all meals first to create a lookup map for ingredients
    meals_response = requests.get(f'{API_BASE_URL}/meals', headers=headers)
    meals_by_id = {}
    if meals_response.status_code == 200:
        meals_json = meals_response.json()
        # Meals endpoint returns a list directly, not a dict
        meals_list = meals_json if isinstance(meals_json, list) else meals_json.get('meals', [])
        meals_by_id = {meal['id']: meal for meal in meals_list}
    
    # Fetch all meal plans
    meal_plans_response = requests.get(f'{API_BASE_URL}/meal_plans', headers=headers)
    user_meal_plans = []
    meal_plan_names = {}
    finalized_plans = {}  # {plan_id: plan_name}
    scratch_items_by_plan = {}  # Maps plan_id -> [scratch_item_ids]
    
    if meal_plans_response.status_code == 200:
        meal_plans_data = meal_plans_response.json()
        user_meal_plans = meal_plans_data.get("meal_plans", [])
        
        # Initialize scratch_items_by_plan for all plans
        for plan in user_meal_plans:
            plan_id = plan["id"]
            plan_name = plan.get("name", f"Plan {plan_id}")
            meal_plan_names[plan_id] = plan_name
            scratch_items_by_plan[plan_id] = []  # Initialize empty list for each plan
            
            if plan.get('finalized'):
                finalized_plans[plan_id] = plan_name
        
        # Fetch scratch items ONCE and use their plan_ids to populate scratch_items_by_plan
        try:
            scratch_response = requests.get(
                f'{API_BASE_URL}/scratch_items',
                headers=headers
            )
            if scratch_response.status_code == 200:
                scratch_data = scratch_response.json()
                
                # For each item, use its plan_ids to determine which plans it belongs to
                for category_name, items_dict in scratch_data.items():
                    if isinstance(items_dict, dict):
                        for ingredient_name, item_data in items_dict.items():
                            # Use plan_ids from the API response (these are authoritative)
                            plan_ids = item_data.get('plan_ids', [])
                            item_id = item_data.get('id')
                            
                            if item_id and plan_ids:
                                # Add this item to each plan it belongs to
                                for plan_id in plan_ids:
                                    if plan_id in scratch_items_by_plan:
                                        if item_id not in scratch_items_by_plan[plan_id]:
                                            scratch_items_by_plan[plan_id].append(item_id)
                                print(f"📦 Item '{ingredient_name}' (ID {item_id}) belongs to plans: {plan_ids}, added to scratch_items_by_plan")
        except Exception as e:
            import traceback
            print(f"⚠️ Failed to fetch scratch items: {e}")
            traceback.print_exc()
    
    
    # Fetch scratch items (user's personal grocery list - consolidated)
    scratch_response = requests.get(f'{API_BASE_URL}/scratch_items', headers=headers)
    
    # Fetch ingredients and categories for formatting
    ingred_response = requests.get(f'{API_BASE_URL}/ingredients', headers=headers)
    categories_resp = requests.get(f'{API_BASE_URL}/ingredient_categories', headers=headers)
    
    # Build a mapping of (plan_id, ingredient_name) -> [meal_names]
    # This will help us show which meals have each ingredient
    meal_details_map = {}
    
    for plan in user_meal_plans:
        if plan.get('finalized'):
            plan_id = plan["id"]
            try:
                # Fetch the full meal plan which includes meal IDs
                full_plan_response = requests.get(
                    f'{API_BASE_URL}/meal_plan/{plan_id}',
                    headers=headers
                )
                if full_plan_response.status_code == 200:
                    full_plan = full_plan_response.json()
                    plan_meals = full_plan.get('meals', [])
                    
                    # For each meal in the plan, look up its details from meals_by_id
                    for meal_info in plan_meals:
                        meal_id = meal_info.get('id')
                        meal_name = meal_info.get('name', f'Meal {meal_id}')
                        
                        # Get full meal details from our lookup map
                        if meal_id in meals_by_id:
                            full_meal = meals_by_id[meal_id]
                            meal_ingredients = full_meal.get('ingredients', [])
                            
                            # Map each ingredient to this meal
                            if meal_ingredients:
                                for ing in meal_ingredients:
                                    ing_name = ing.get('name', '')
                                    ing_qty = ing.get('quantity', 1)
                                    key = f"{plan_id}:{ing_name}"
                                    
                                    if key not in meal_details_map:
                                        meal_details_map[key] = []
                                    
                                    # Check if this meal is already in the list (same meal from same plan)
                                    meal_exists = any(m['meal_name'] == meal_name for m in meal_details_map[key])
                                    if not meal_exists:
                                        meal_details_map[key].append({
                                            'meal_name': meal_name,
                                            'quantity': ing_qty,
                                            'plan_id': plan_id  # Include plan_id so we can show correct plan name
                                        })
                        else:
                            print(f"⚠️ Meal {meal_id} ({meal_name}) not found in meals_by_id lookup")
            except Exception as e:
                print(f"⚠️ Failed to fetch meal details for plan {plan_id}: {e}")
    
    print(f"📊 Built meal_details_map with {len(meal_details_map)} entries")
    
    if scratch_response.status_code != 200:
        return render_template('grocery_list.html', grocery_list={}, 
                               meal_plan_ids=list(finalized_plans.keys()),
                               meal_plan_names=meal_plan_names,
                               scratch_items_by_plan=scratch_items_by_plan,
                               back_href=url_for('routes.meal_plans'),
                               random_subhead=random_subheader())
    
    # Build lookups
    categories = categories_resp.json() if categories_resp.status_code == 200 else []
    category_lookup = {cat["id"]: cat["name"] for cat in categories}
    
    ingredients = ingred_response.json() if ingred_response.status_code == 200 else []
    ingredient_lookup = {ing["id"]: ing for ing in ingredients if not ing.get("is_user_ingredient")}
    user_ingredient_lookup = {ing["id"]: ing for ing in ingredients if ing.get("is_user_ingredient")}
    
    # Format scratch items by category - matching template structure
    scratch_items = scratch_response.json()
    grocery_dict = {}
    
    print(f"🔍 Raw scratch_items response type: {type(scratch_items)}")
    print(f"🔍 Raw scratch_items response keys: {list(scratch_items.keys()) if isinstance(scratch_items, dict) else 'Not a dict'}")
    print(f"🔍 Full scratch_items response: {scratch_items}")
    
    # API returns: {category: {ingredient: {scratch_details: [...], total_quantity: ..., plan_ids: [...], meal_details: [...]}}}
    if isinstance(scratch_items, dict):
        for category_name, ingredients_dict in scratch_items.items():
            print(f"📂 Processing category: {category_name} with {len(ingredients_dict) if isinstance(ingredients_dict, dict) else '?'} items")
            if not isinstance(ingredients_dict, dict):
                continue
            
            grocery_dict[category_name] = {}
            
            for ingredient_name, ingredient_data in ingredients_dict.items():
                print(f"  📦 Processing ingredient: {ingredient_name}")
                if not isinstance(ingredient_data, dict):
                    continue
                
                # Get the scratch details and metadata from API (which now includes plan_ids and meal_details)
                scratch_details = ingredient_data.get("scratch_details", [])
                total_qty = ingredient_data.get("total_quantity", 0)
                plan_ids_for_item = ingredient_data.get("plan_ids", [])  # Use plan_ids from API directly
                meal_details = ingredient_data.get("meal_details", [])    # Use meal_details from API directly
                
                # Build the data structure the template expects
                grocery_dict[category_name][ingredient_name] = {
                    "id": scratch_details[0].get("id") if scratch_details else None,
                    "is_checked": scratch_details[0].get("is_checked", False) if scratch_details else False,
                    "quantity": scratch_details[0].get("quantity", 1) if scratch_details else 1,
                    "note": scratch_details[0].get("note", "") if scratch_details else "",
                    "average_quantity": total_qty,
                    "total_quantity": total_qty,
                    "meal_details": meal_details,  # From API response
                    "scratch_details": scratch_details,
                    "plan_ids": plan_ids_for_item  # From API response
                }
    
    total_items = sum(len(v) for v in grocery_dict.values())
    print(f"✅ Built grocery_dict with {len(grocery_dict)} categories, total items: {total_items}")
    print(f"📋 Finalized plans with items: {finalized_plans}")
    print(f"🗂️ Scratch items by plan (for deletion): {scratch_items_by_plan}")
    print(f"📊 Sample grocery_dict item structure: {list(grocery_dict.values())[0] if grocery_dict else 'Empty'}")
    
    # Filter out plans with 0 items - only show plans that actually have scratch items
    plan_ids_with_items = [plan_id for plan_id in finalized_plans.keys() if scratch_items_by_plan.get(plan_id, [])]
    print(f"📋 Plans to show in UI (filtered): {plan_ids_with_items}")
    
    return render_template('grocery_list.html', 
                           grocery_list=grocery_dict,
                           meal_plan_ids=plan_ids_with_items,
                           meal_plan_id=None,
                           meal_plan_name=None,
                           meal_plan_names=meal_plan_names,
                           scratch_items_by_plan=scratch_items_by_plan,
                           back_href=url_for('routes.meal_plans'),
                           random_subhead=random_subheader())


## ROUTE FOR SINGLE GROCERY LIST PAGE ✅
@routes.route('/meal_plan/<int:meal_plan_id>/grocery_list_view', methods=['GET'])
@login_required
def grocery_list_single_view(meal_plan_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}
    
    # Fetch both grocery list and meal plan details
    grocery_response = requests.get(f'{API_BASE_URL}/meal_plan/{meal_plan_id}/grocery_list', headers=headers)
    meal_plan_response = requests.get(f'{API_BASE_URL}/meal_plan/{meal_plan_id}', headers=headers)
    
    meal_plan_name = "Meal Plan"
    if meal_plan_response.status_code == 200:
        meal_plan_data = meal_plan_response.json()
        meal_plan_name = meal_plan_data.get('meal_plan_name', 'Meal Plan')

    if grocery_response.status_code == 200:
        grocery_data = grocery_response.json().get("grocery_list", {})
        return render_template('grocery_list.html', grocery_list=grocery_data,
            meal_plan_id=meal_plan_id, meal_plan_name=meal_plan_name,
            random_subhead=random_subheader(),
            back_href=url_for('routes.view_meal_plan', meal_plan_id=meal_plan_id)
        )

    print("⚠️ Failed to fetch grocery list.")
    return render_template(
        'grocery_list.html',
        grocery_list={}, meal_plan_id=meal_plan_id, meal_plan_name=meal_plan_name,
        back_href=url_for('routes.view_meal_plan', meal_plan_id=meal_plan_id),
        random_subhead=random_subheader()
    )


## ROUTE FOR COMBINED GROCERY LIST PAGE
@routes.route('/meal_plans/grocery_list_view', methods=['GET'])
@login_required
def grocery_list_view_combined():
    # Retrieve the meal_plan_ids from the query parameters
    meal_plan_ids = request.args.getlist('meal_plan_id', type=int)
    print(f"Meal Plan IDs: {meal_plan_ids}")

    if not meal_plan_ids:
        return "No meal plans selected.", 400

    # Send the request to the combined grocery list API with individual meal_plan_id parameters
    api_url = f'{API_BASE_URL}/meal_plans/grocery_list'
    params = []
    for meal_plan_id in meal_plan_ids:
        params.append(('meal_plan_id', meal_plan_id))  # Add each meal_plan_id as an individual param

    # Construct the full API endpoint with query parameters
    print(f"Full API URL: {api_url}?{'&'.join([f'{k}={v}' for k, v in params])}")

    # Send the request to the combined grocery list API
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.get(api_url, headers=headers, params=params)

    # Also fetch meal plan names for display
    meal_plan_names = {}
    for meal_plan_id in meal_plan_ids:
        plan_response = requests.get(f'{API_BASE_URL}/meal_plan/{meal_plan_id}', headers=headers)
        if plan_response.status_code == 200:
            meal_plan_data = plan_response.json()
            meal_plan_names[meal_plan_id] = meal_plan_data.get('meal_plan_name', f'Plan {meal_plan_id}')
        else:
            meal_plan_names[meal_plan_id] = f'Plan {meal_plan_id}'

    # print(response)

    if response.status_code == 200:
        grocery_data = response.json().get("grocery_list", {})
        return render_template('grocery_list.html', grocery_list=grocery_data,
                               meal_plan_ids=meal_plan_ids, meal_plan_names=meal_plan_names,
                               random_subhead=random_subheader(),
                               back_href=url_for('routes.meal_plans'))
    else:
        print("⚠️ Failed to fetch grocery list.")
        return render_template(
            'grocery_list.html',
            grocery_list={}, meal_plan_ids=meal_plan_ids, meal_plan_names=meal_plan_names,
            back_href=url_for('routes.meal_plans'),
            random_subhead=random_subheader()
        )


## ADD MEAL PLAN INGREDIENTS TO SCRATCH LIST
@routes.route('/meal_plan/<int:meal_plan_id>/add_to_scratch', methods=['POST'])
@login_required
def add_meal_plan_to_scratch(meal_plan_id):
    print(f"\n🔵 Flask add_to_scratch called: meal_plan_id={meal_plan_id}")
    headers = {'Authorization': f"Bearer {g.access_token}"}
    
    # Call the API endpoint
    api_url = f'{API_BASE_URL}/meal_plan/{meal_plan_id}/add_to_scratch'
    print(f"🔵 Calling API: POST {api_url}")
    response = requests.post(api_url, headers=headers)
    print(f"🔵 API response: status={response.status_code}, body={response.text[:200]}")
    
    if response.status_code in [200, 201]:
        data = response.json()
        result = {
            "success": True,
            "message": data.get("message"),
            "count": data.get("count", 0)
        }
        print(f"🔵 Returning to frontend: {result}")
        return jsonify(result), 200
    else:
        error_msg = response.json().get("error", "Failed to add items to scratch list")
        print(f"🔵 Error: {error_msg}")
        return jsonify({
            "success": False,
            "message": error_msg
        }), response.status_code


## CHECK IF MEAL PLAN INGREDIENTS ARE IN SCRATCH LIST
@routes.route('/meal_plan/<int:meal_plan_id>/check_scratch_status', methods=['GET'])
@login_required
def check_meal_plan_scratch_status(meal_plan_id):
    """Check if meal plan ingredients have already been added to scratch list"""
    headers = {'Authorization': f"Bearer {g.access_token}"}
    
    # Fetch meal plan's grocery list (ingredients)
    grocery_url = f'{API_BASE_URL}/meal_plan/{meal_plan_id}/grocery_list'
    grocery_response = requests.get(grocery_url, headers=headers)
    
    # Fetch user's scratch items
    scratch_url = f'{API_BASE_URL}/scratch_items'
    scratch_response = requests.get(scratch_url, headers=headers)
    
    if grocery_response.status_code != 200 or scratch_response.status_code != 200:
        return jsonify({
            "already_added": False,
            "count": 0
        }), 200
    
    # Extract ingredient IDs from meal plan
    grocery_data = grocery_response.json().get("grocery_list", {})
    meal_plan_ingredient_ids = set()
    
    # Collect all ingredient IDs from the meal plan
    for category_ingredients in grocery_data.values():
        if isinstance(category_ingredients, list):
            for item in category_ingredients:
                if "ingredient_id" in item:
                    meal_plan_ingredient_ids.add(item["ingredient_id"])
    
    # Extract ingredient IDs from scratch items
    scratch_items = scratch_response.json()
    scratch_ingredient_ids = set()
    
    if isinstance(scratch_items, list):
        for item in scratch_items:
            if "ingredient_id" in item and item["ingredient_id"]:
                scratch_ingredient_ids.add(item["ingredient_id"])
    
    # Count how many meal plan ingredients are in scratch list
    matching_count = len(meal_plan_ingredient_ids & scratch_ingredient_ids)
    total_count = len(meal_plan_ingredient_ids)
    
    # Consider it "already added" if at least 50% of ingredients are in scratch
    # (accounts for user possibly removing some items)
    already_added = matching_count > 0 and matching_count >= (total_count * 0.5)
    
    return jsonify({
        "already_added": already_added,
        "count": matching_count
    }), 200


@routes.route('/meal_plan/<int:meal_plan_id>/mark_added_to_grocery', methods=['POST'])
@login_required
def mark_meal_plan_added_to_grocery(meal_plan_id):
    """Mark a meal plan as added to grocery list by updating timestamp in API"""
    print(f"🔵 [DEBUG] mark_meal_plan_added_to_grocery called with meal_plan_id={meal_plan_id}")
    
    headers = {'Authorization': f"Bearer {g.access_token}"}
    
    # Call the API endpoint
    api_url = f'{API_BASE_URL}/meal_plan/{meal_plan_id}/mark_added_to_grocery'
    print(f"🔵 [DEBUG] Calling API at: {api_url}")
    
    try:
        response = requests.post(api_url, headers=headers)
        print(f"🔵 [DEBUG] API response status: {response.status_code}")
        print(f"🔵 [DEBUG] API response body: {response.text[:100] if response.text else 'empty'}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            return jsonify({
                "success": True,
                "message": data.get("message"),
                "added_at": data.get("added_at")
            }), 200
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("message", f"API error: {response.status_code}")
            except:
                error_msg = f"API error: {response.status_code} - {response.text}"
                
            return jsonify({
                "success": False,
                "message": error_msg
            }), response.status_code
    except Exception as e:
        print(f"🔵 [DEBUG] Exception: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        }), 500



## ROUTE TO ADD SCRATCH ITEM (API CALL) ✅
@routes.route("/scratch-list", methods=["POST"])
@login_required
def add_scratch_item():
    headers = {'Authorization': f"Bearer {g.access_token}"}

    data = request.get_json()

    new_data = {}
    if data.get('ingredient_id'):
        new_data['ingredient_id'] = data.get('ingredient_id')
        new_data['user_ingredient_id'] = None
        new_data['custom_name'] = None
    elif data.get('user_ingredient_id'):
        new_data['user_ingredient_id'] = data.get('user_ingredient_id')
        new_data['ingredient_id'] = None
        new_data['custom_name'] = None
    else:
        new_data['ingredient_id'] = None
        new_data['user_ingredient_id'] = None
        new_data['custom_name'] = data.get('custom_name')

    new_data['quantity'] = data.get('quantity')
    new_data['note'] = data.get('note')

    print(new_data)

    response = requests.post(f'{API_BASE_URL}/scratch_items', json=new_data, headers=headers)

    print("Response status from API:", response.status_code)
    print("API response body:", response.text)

    if response.status_code in [200, 201]:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False}), 400


## ROUTE TO UPDATE SCRATCH ITEM (API CALL) ✅
@routes.route("/scratch-list/<int:item_id>", methods=["PUT"])
@login_required
def update_scratch_item(item_id):
    print(f"📥 update_scratch_item called for item_id={item_id}")
    headers = {'Authorization': f"Bearer {g.access_token}"}

    # Get the updated data from JSON or form
    updated_data = {}

    # Try to get JSON data first
    if request.is_json:
        json_data = request.get_json()
        print(f"📋 JSON data received: {json_data}")
        if 'is_checked' in json_data:
            updated_data['is_checked'] = json_data.get('is_checked')
        if 'custom_name' in json_data:
            updated_data['custom_name'] = json_data.get('custom_name')
        if 'quantity' in json_data:
            updated_data['quantity'] = json_data.get('quantity')
    else:
        print("📋 No JSON data, checking form data")
        # Fall back to form data
        if request.form.get('name'):
            updated_data['custom_name'] = request.form.get('name')
        if request.form.get('quantity'):
            updated_data['quantity'] = request.form.get('quantity')

    print(f"🔄 Sending to API: {updated_data}")
    response = requests.patch(f'{API_BASE_URL}/scratch_items/{item_id}', json=updated_data, headers=headers)

    print(f"📤 API response status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Scratch item updated successfully.")
        return jsonify({"success": True})
    else:
        print(f"⚠️ Failed to update scratch item. Response: {response.text}")
        return jsonify({"success": False, "error": response.text}), 400


## ROUTE TO DELETE SCRATCH ITEM (API CALL) ✅
@routes.route("/scratch-list/<int:item_id>", methods=["POST", "DELETE"])
@login_required 
def delete_scratch_item(item_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}
    
    try:
        response = requests.delete(f'{API_BASE_URL}/scratch_items/{item_id}', headers=headers)
        print(f"🗑️ Delete response for item {item_id}: {response.status_code}")
        print(f"Response body: {response.text}")
    except Exception as e:
        print(f"❌ Exception deleting scratch item {item_id}: {str(e)}")
        if request.method == 'DELETE':
            return jsonify({
                'success': False, 
                'message': f'Error deleting item: {str(e)}'
            }), 500
        return redirect(url_for('routes.scratch_list'))

    # For AJAX requests (DELETE method), return JSON
    if request.method == 'DELETE':
        if response.status_code in [200, 204, 404]:  # 204/200: deleted, 404: already deleted
            print(f"✅ Successfully deleted scratch item {item_id}")
            return jsonify({
                'success': True, 
                'message': f'Deleted scratch item {item_id}',
                'status_code': response.status_code
            }), 200
        else:
            # API error - return the error details
            error_msg = "Failed to delete item from database"
            try:
                error_data = response.json()
                error_msg = error_data.get('error', error_msg)
            except:
                pass
            
            print(f"⚠️ Failed to delete scratch item {item_id}: HTTP {response.status_code}")
            print(f"Error message: {error_msg}")
            return jsonify({
                'success': False, 
                'message': error_msg,
                'status_code': response.status_code
            }), response.status_code
    
    # For form submissions (POST method), redirect to scratch list page
    if response.status_code == 200:
        print("✅ Item deleted via POST")
        flash('Item removed from grocery list', 'success')
    else:
        print("⚠️ Failed to delete item via POST")
        flash('Failed to remove item', 'error')
    return redirect(url_for('routes.scratch_list'))


## ROUTE TO BULK DELETE SCRATCH ITEMS (API CALL)
@routes.route('/scratch-list/clear', methods=['POST'])
@login_required
def clear_scratch_items():
    headers = {'Authorization': f"Bearer {g.access_token}"}

    scratch_response = requests.get(f'{API_BASE_URL}/scratch_items', headers=headers)
    scratch_list = scratch_response.json()

    ids_to_delete = []

    for items in scratch_list.values():
        for item_data in items.values():
            for detail in item_data['scratch_details']:
                ids_to_delete.append(detail['id'])

    for id in ids_to_delete:
        response = requests.delete(f'{API_BASE_URL}/scratch_items/{id}', headers=headers)

        print(f"Delete response: {response.status_code}")

        if response.status_code == 200:
            print("🗑️ Item deleted.")
        else:
            print("⚠️ Failed to delete item.")

    return redirect(url_for('routes.scratch_list'))



# ----------------- #
## SETTINGS ROUTES ##

## ROUTE FOR USER PROFILE PAGE, AND API CALL ✅
@routes.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():

    headers = {'Authorization': f"Bearer {g.access_token}"}
    api_url = f"{API_BASE_URL}/user/profile" 

    if request.method == 'POST':

        payload = {
            "name": request.form.get("name"),
            "email": request.form.get("email"),
            "start_date": request.form.get("start_date"),
            "end_date": request.form.get("end_date"),
            "cuisine_max_occurance": int(request.form.get("cuisine_max_occurance") or 0),
            "alphabetize_groceries": bool(request.form.get("alphabetize_groceries")),
            "show_default_ingredients": bool(request.form.get("show_default_ingredients")),
            "show_default_meals": bool(request.form.get("show_default_meals")),
            "repeat_extra_meals": bool(request.form.get("repeat_extra_meals"))

        }

        print(payload)

        response = requests.put(api_url, json=payload, headers=headers)
        if response.status_code == 200:
            clear_and_flash("Profile updated successfully!", "success")
            return redirect(url_for("routes.profile"))
        else:
            clear_and_flash("Failed to update profile.", "danger")

    # GET request
    profile_response = requests.get(api_url, headers=headers)
    print(f"RESPONSE STATUS: {profile_response.status_code}")

    if profile_response.status_code == 200:
        user_data = profile_response.json()
        # tags = tags_response.json()

    else:
        user_data = {}
        clear_and_flash("Failed to load user data.", "danger")

    return render_template("profile.html", user=user_data, random_subhead=random_subheader(), access_token=g.access_token,
                            api_base_url=API_BASE_URL)


# ----------------- #
## TO-DO ROUTES ##

def _today():
    """Today's date in the owner's timezone (Heroku runs in UTC)."""
    return datetime.now(ZoneInfo(os.getenv("APP_TIMEZONE", "America/Chicago"))).date()


def _mark_work(items):
    """Flag Google events that come from a work calendar (WORK_CALENDARS, default the ProviderTrust one)."""
    work = {c.strip().lower() for c in os.getenv('WORK_CALENDARS', 'jbolt@providertrust.com').split(',') if c.strip()}
    for i in items:
        if i.get('type') == 'gcal':
            i['is_work'] = (i.get('calendar_id') or '').lower() in work or (i.get('calendar') or '').lower() in work
    return items


def _back_to(default_endpoint):
    """Forms on the Today page post with next=home so we return there."""
    if request.form.get('next') == 'home':
        return redirect(url_for('routes.home'))
    return redirect(url_for(default_endpoint))


@routes.route('/todos', methods=['GET'])
@login_required
def todos():
    headers = {'Authorization': f"Bearer {g.access_token}"}
    open_resp = requests.get(f"{API_BASE_URL}/todos", params={'status': 'open'}, headers=headers)
    done_resp = requests.get(f"{API_BASE_URL}/todos", params={'status': 'done'}, headers=headers)
    if open_resp.status_code != 200 or done_resp.status_code != 200:
        clear_and_flash("Could not load your to-dos.", "error")
    open_todos = open_resp.json().get('todos', []) if open_resp.status_code == 200 else []
    done_todos = done_resp.json().get('todos', [])[:20] if done_resp.status_code == 200 else []
    return render_template('todos.html', open_todos=open_todos, done_todos=done_todos,
                           today=_today().isoformat(), random_subhead=random_subheader())


@routes.route('/todos/add', methods=['POST'])
@login_required
def add_todo():
    title = request.form.get('title', '').strip()
    if not title:
        clear_and_flash("Give the to-do a title.", "error")
        return _back_to('routes.todos')
    payload = {'title': title, 'due_date': request.form.get('due_date') or None}
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.post(f"{API_BASE_URL}/todos", json=payload, headers=headers)
    if response.status_code != 201:
        clear_and_flash(response.json().get('error', 'Could not add the to-do.'), "error")
    return _back_to('routes.todos')


@routes.route('/todos/<int:todo_id>/toggle', methods=['POST'])
@login_required
def toggle_todo(todo_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}
    done = request.form.get('done') == 'true'
    response = requests.patch(f"{API_BASE_URL}/todos/{todo_id}", json={'done': done}, headers=headers)
    if response.status_code != 200:
        clear_and_flash("Could not update the to-do.", "error")
    return _back_to('routes.todos')


@routes.route('/todos/<int:todo_id>/edit', methods=['POST'])
@login_required
def edit_todo(todo_id):
    title = request.form.get('title', '').strip()
    if not title:
        clear_and_flash("A to-do needs a title.", "error")
        return redirect(url_for('routes.todos'))
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.patch(f"{API_BASE_URL}/todos/{todo_id}", headers=headers,
                              json={'title': title, 'due_date': request.form.get('due_date') or None})
    if response.status_code != 200:
        clear_and_flash(response.json().get('error', 'Could not save the to-do.'), "error")
    return redirect(url_for('routes.todos'))


@routes.route('/todos/<int:todo_id>/delete', methods=['POST'])
@login_required
def delete_todo_item(todo_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.delete(f"{API_BASE_URL}/todos/{todo_id}", headers=headers)
    if response.status_code != 200:
        clear_and_flash("Could not delete the to-do.", "error")
    return redirect(url_for('routes.todos'))


# ----------------- #
## REMINDER ROUTES ##

def _describe_reminder(r, today):
    """Add display text and a group (overdue / soon / later) to a reminder from the API."""
    due = datetime.strptime(r['next_due'], '%Y-%m-%d').date()
    days = (due - today).days
    if days < 0:
        group, due_text = 'overdue', f"{-days} day{'s' if days != -1 else ''} overdue"
    elif days <= 30:
        group, due_text = 'soon', ('Today' if days == 0 else 'Tomorrow' if days == 1 else due.strftime('%a, %b %-d'))
    else:
        group, due_text = 'later', due.strftime('%a, %b %-d')
    if r.get('interval_value'):
        unit = r['interval_unit']
        repeat = f"Every {unit[:-1]}" if r['interval_value'] == 1 else f"Every {r['interval_value']} {unit}"
    else:
        repeat = "One time"
    return {**r, 'group': group, 'due_text': due_text, 'repeat_text': repeat}


@routes.route('/reminders', methods=['GET'])
@login_required
def reminders():
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.get(f"{API_BASE_URL}/reminders", headers=headers)
    items = []
    if response.status_code == 200:
        today = _today()
        items = [_describe_reminder(r, today) for r in response.json().get('reminders', [])]
    else:
        clear_and_flash("Could not load your reminders.", "error")
    groups = [
        {'title': 'Overdue', 'key': 'overdue', 'items': [r for r in items if r['group'] == 'overdue']},
        {'title': 'Due in the next 30 days', 'key': 'soon', 'items': [r for r in items if r['group'] == 'soon']},
        {'title': 'Later', 'key': 'later', 'items': [r for r in items if r['group'] == 'later']},
    ]
    return render_template('reminders.html', groups=groups, any_reminders=bool(items),
                           today=_today().isoformat(), random_subhead=random_subheader())


@routes.route('/reminders/add', methods=['POST'])
@login_required
def add_reminder():
    title = request.form.get('title', '').strip()
    next_due = request.form.get('next_due', '')
    unit = request.form.get('interval_unit', '')
    payload = {'title': title, 'next_due': next_due,
               'lead_days': int(request.form.get('lead_days') or 1)}
    if unit and unit != 'once':
        payload['interval_value'] = request.form.get('interval_value')
        payload['interval_unit'] = unit
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.post(f"{API_BASE_URL}/reminders", json=payload, headers=headers)
    if response.status_code != 201:
        clear_and_flash(response.json().get('error', 'Could not add the reminder.'), "error")
    return redirect(url_for('routes.reminders'))


@routes.route('/reminders/<int:reminder_id>/done', methods=['POST'])
@login_required
def reminder_done(reminder_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.post(f"{API_BASE_URL}/reminders/{reminder_id}/done",
                             json={'today': _today().isoformat()}, headers=headers)
    if response.status_code == 200:
        r = response.json()
        if r.get('active'):
            clear_and_flash(f"Done. Next time: {datetime.strptime(r['next_due'], '%Y-%m-%d').strftime('%b %-d, %Y')}.", "success")
        else:
            clear_and_flash("Done. That was a one-time reminder, so it's finished.", "success")
    else:
        clear_and_flash("Could not update the reminder.", "error")
    return _back_to('routes.reminders')


@routes.route('/reminders/<int:reminder_id>/edit', methods=['POST'])
@login_required
def edit_reminder(reminder_id):
    unit = request.form.get('interval_unit', '')
    repeats = bool(unit) and unit != 'once'
    payload = {'title': request.form.get('title', '').strip(),
               'next_due': request.form.get('next_due', ''),
               'lead_days': request.form.get('lead_days') or 1,
               'interval_value': request.form.get('interval_value') if repeats else None,
               'interval_unit': unit if repeats else None}
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.patch(f"{API_BASE_URL}/reminders/{reminder_id}", json=payload, headers=headers)
    if response.status_code != 200:
        clear_and_flash(response.json().get('error', 'Could not save the reminder.'), "error")
    return redirect(url_for('routes.reminders'))


@routes.route('/reminders/<int:reminder_id>/delete', methods=['POST'])
@login_required
def delete_reminder_item(reminder_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.delete(f"{API_BASE_URL}/reminders/{reminder_id}", headers=headers)
    if response.status_code != 200:
        clear_and_flash("Could not delete the reminder.", "error")
    return redirect(url_for('routes.reminders'))


# ----------------- #
## SCHEDULE ROUTES ##

def _fmt_time(hhmm):
    """'13:05' -> '1:05 PM'"""
    return datetime.strptime(hhmm, '%H:%M').strftime('%-I:%M %p')


@routes.route('/schedule', methods=['GET'])
@login_required
def schedule():
    from datetime import timedelta
    today = _today()
    try:
        start = datetime.strptime(request.args.get('start', ''), '%Y-%m-%d').date()
    except ValueError:
        start = today
    end = start + timedelta(days=6)

    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.get(f"{API_BASE_URL}/schedule",
                            params={'start': start.isoformat(), 'end': end.isoformat()}, headers=headers)
    items, google_reconnect = [], False
    if response.status_code == 200:
        items = _mark_work(response.json().get('items', []))
        google_reconnect = bool(response.json().get('google_reconnect'))
    else:
        clear_and_flash("Could not load your schedule.", "error")

    events_by_id = {}
    ev_resp = requests.get(f"{API_BASE_URL}/events", headers=headers)
    if ev_resp.status_code == 200:
        events_by_id = {e['id']: e for e in ev_resp.json().get('events', [])}

    days = []
    for n in range(7):
        day = start + timedelta(days=n)
        label = 'Today' if day == today else 'Tomorrow' if day == today + timedelta(days=1) else day.strftime('%A')
        day_items, working_location = [], None
        for i in (x for x in items if x['date'] == day.isoformat()):
            if i['type'] == 'workloc':  # shown as a pill on the day, not as an item
                working_location = working_location or i['title']
                continue
            if i['type'] == 'meal':  # meals live on the Meals pages and the Today strip, not here
                continue
            when = 'All day'
            if i.get('start_time'):
                when = _fmt_time(i['start_time']) + (' – ' + _fmt_time(i['end_time']) if i.get('end_time') else '')
            day_items.append({**i, 'when': when})
        days.append({'label': label, 'date_text': day.strftime('%b %-d'), 'is_today': day == today, 'items': day_items,
                     'working_location': working_location})

    return render_template('schedule.html', days=days, today=today.isoformat(), events_by_id=events_by_id, google_reconnect=google_reconnect,
                           prev_start=(start - timedelta(days=7)).isoformat(),
                           next_start=(start + timedelta(days=7)).isoformat(),
                           range_text=f"{start.strftime('%b %-d')} – {end.strftime('%b %-d')}",
                           show_today_link=(start != today), random_subhead=random_subheader())


@routes.route('/events/add', methods=['POST'])
@login_required
def add_event():
    payload = {
        'title': request.form.get('title', '').strip(),
        'event_date': request.form.get('event_date', ''),
        'start_time': request.form.get('start_time') or None,
        'end_time': request.form.get('end_time') or None,
    }
    unit = request.form.get('repeat_unit', '')
    if unit and unit != 'once':
        payload['repeat_value'] = request.form.get('repeat_value')
        payload['repeat_unit'] = unit
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.post(f"{API_BASE_URL}/events", json=payload, headers=headers)
    if response.status_code != 201:
        clear_and_flash(response.json().get('error', 'Could not add the event.'), "error")
    return redirect(url_for('routes.schedule'))


@routes.route('/events/<int:event_id>/edit', methods=['POST'])
@login_required
def edit_event_item(event_id):
    unit = request.form.get('repeat_unit', '')
    repeats = bool(unit) and unit != 'once'
    payload = {'title': request.form.get('title', '').strip(),
               'event_date': request.form.get('event_date', ''),
               'start_time': request.form.get('start_time') or None,
               'end_time': request.form.get('end_time') or None,
               'repeat_value': request.form.get('repeat_value') if repeats else None,
               'repeat_unit': unit if repeats else None}
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.patch(f"{API_BASE_URL}/events/{event_id}", json=payload, headers=headers)
    if response.status_code != 200:
        clear_and_flash(response.json().get('error', 'Could not save the event.'), "error")
    return redirect(url_for('routes.schedule'))


@routes.route('/events/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event_item(event_id):
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.delete(f"{API_BASE_URL}/events/{event_id}", headers=headers)
    if response.status_code != 200:
        clear_and_flash("Could not delete the event.", "error")
    return redirect(url_for('routes.schedule'))



# ----------------------- #
## GOOGLE CALENDAR (read-only) ##

def _google_callback_url():
    """The address Google sends the user back to. Must match what is registered in the Google Cloud console."""
    base = os.getenv('PUBLIC_BASE_URL', '').rstrip('/') or request.url_root.rstrip('/')
    if base.startswith('http://') and 'localhost' not in base and '127.0.0.1' not in base:
        base = 'https://' + base[len('http://'):]
    return f"{base}{url_for('routes.google_callback')}"


@routes.route('/google', methods=['GET'])
@login_required
def google_calendar():
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.get(f"{API_BASE_URL}/google/status", params={'refresh': request.args.get('refresh', '')},
                            headers=headers, timeout=20)
    info = response.json() if response.status_code == 200 else {}
    if response.status_code != 200:
        clear_and_flash("Could not reach the server.", "error")
    return render_template('google_calendar.html', info=info, callback_url=_google_callback_url(),
                           random_subhead=random_subheader())


@routes.route('/google/connect', methods=['GET'])
@login_required
def google_connect():
    state = os.urandom(16).hex()
    session['google_state'] = state
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.post(f"{API_BASE_URL}/google/auth_url", headers=headers,
                             json={'redirect_uri': _google_callback_url(), 'state': state}, timeout=15)
    if response.status_code != 200:
        clear_and_flash(response.json().get('error', 'Could not start the Google sign-in.'), "error")
        return redirect(url_for('routes.google_calendar'))
    return redirect(response.json()['url'])


@routes.route('/google/callback', methods=['GET'])
@login_required
def google_callback():
    expected = session.pop('google_state', None)
    if request.args.get('error'):
        clear_and_flash("Google Calendar was not connected.", "error")
    elif not expected or request.args.get('state') != expected or not request.args.get('code'):
        clear_and_flash("That Google sign-in could not be verified. Please try again.", "error")
    else:
        headers = {'Authorization': f"Bearer {g.access_token}"}
        response = requests.post(f"{API_BASE_URL}/google/connect", headers=headers, timeout=20,
                                 json={'code': request.args['code'], 'redirect_uri': _google_callback_url()})
        if response.status_code == 200:
            clear_and_flash("Google Calendar connected. Choose which calendars to show below.", "success")
        else:
            clear_and_flash(response.json().get('error', 'Could not connect Google Calendar.'), "error")
    return redirect(url_for('routes.google_calendar'))


@routes.route('/google/calendars', methods=['POST'])
@login_required
def google_choose_calendars():
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.put(f"{API_BASE_URL}/google/calendars", headers=headers,
                            json={'selected': request.form.getlist('calendar')}, timeout=15)
    if response.status_code == 200:
        clear_and_flash("Saved. Those calendars will show on Today and Schedule.", "success")
    else:
        clear_and_flash(response.json().get('error', 'Could not save your choice.'), "error")
    return redirect(url_for('routes.google_calendar'))


@routes.route('/google/disconnect', methods=['POST'])
@login_required
def google_disconnect():
    headers = {'Authorization': f"Bearer {g.access_token}"}
    response = requests.delete(f"{API_BASE_URL}/google", headers=headers, timeout=15)
    clear_and_flash("Google Calendar disconnected." if response.status_code == 200 else "Could not disconnect.",
                    "success" if response.status_code == 200 else "error")
    return redirect(url_for('routes.google_calendar'))
