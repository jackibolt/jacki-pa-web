from functools import wraps
from flask import (request, redirect, g,
                   flash, url_for, make_response)
import requests, os, jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError


API_BASE_URL = os.getenv("API_BASE_URL")
SECRET_KEY = os.getenv("JWT_SECRET_KEY")  # must match the API's JWT_SECRET_KEY
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY must be set as an environment variable.")


from flask import g, request, redirect, url_for, flash, make_response
from functools import wraps
from jwt import ExpiredSignatureError, InvalidTokenError
import jwt
import os
import requests

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        print("🔐 Checking login status...")

        g.user = None
        g.new_access_token = None
        access_token = request.cookies.get('access_token')
        refresh_token = request.cookies.get('refresh_token')

        if not access_token and not refresh_token:
            print("⛔ No tokens found. Redirecting to login.")
            flash("⛔ You must be logged in to view this page.")
            return redirect(url_for('routes.login'))

        try:
            if access_token:
                user_data = jwt.decode(access_token, SECRET_KEY, algorithms=["HS256"])
                g.user = user_data
                g.access_token = access_token
                return view(*args, **kwargs)

        except ExpiredSignatureError:
            print("⚠️ Access token expired. Attempting refresh...")

        except InvalidTokenError:
            print("❌ Invalid access token. Attempting refresh if refresh token exists...")

        # Token was missing, expired, or invalid — try to refresh
        if refresh_token:
            refresh_response = requests.post(
                f"{API_BASE_URL}/auth/refresh",
                cookies={"refresh_token": refresh_token}
            )
            print("🔁 Refresh status:", refresh_response.status_code)

            if refresh_response.status_code == 200:
                new_access_token = refresh_response.json().get('access_token')
                if new_access_token:
                    print("✅ Token refreshed. Setting new access token.")
                    g.access_token = new_access_token
                    g.user = jwt.decode(new_access_token, SECRET_KEY, algorithms=["HS256"])

                    response = make_response(view(*args, **kwargs))
                    response.set_cookie(
                        'access_token', new_access_token,
                        httponly=True, samesite='Lax',
                        secure=(os.getenv('FLASK_ENV') == 'production'),
                        max_age=60 * 60  # 1 hour
                    )
                    return response

        # If we reach this point, either no refresh token or refresh failed
        print("⛔ Unable to verify login. Redirecting to login.")
        flash("⛔ Session expired or invalid. Please log in again.")
        return redirect(url_for('routes.login'))

    return wrapped_view
