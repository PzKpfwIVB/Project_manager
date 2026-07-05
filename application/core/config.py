import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
SECRET_KEY = os.getenv('SECRET_KEY')
FILE_STORAGE = os.getenv('FILE_STORAGE')
DUMMY_FILES = os.getenv('DUMMY_FILES')
