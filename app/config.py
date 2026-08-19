import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv(override=True)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    DATABASE_URL = os.environ.get('DATABASE_URL')
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=90)
    SESSION_COOKIE_DOMAIN = os.environ.get('SESSION_COOKIE_DOMAIN')  # .tuc-tuc.co en producción
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB — rockola multi-archivo

    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TUYA_ACCESS_ID = os.environ.get('TUYA_ACCESS_ID')
    TUYA_ACCESS_SECRET = os.environ.get('TUYA_ACCESS_SECRET')
    ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development')

    @property
    def is_production(self):
        return self.ENVIRONMENT == 'production'
