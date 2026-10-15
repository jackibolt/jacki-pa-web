
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or "fallback-secret"
    DEBUG = False

    JWT_TOKEN_LOCATION = ['cookies']  # <-- Tell Flask-JWT where to look
    JWT_COOKIE_SECURE = False
    JWT_COOKIE_SAMESITE = 'Lax'

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    ENV = 'production'
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_SAMESITE = 'None'

