import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'greencycle-nexus-secret-kerala-2026')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///greencycle.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PORT = int(os.environ.get('PORT', 5001))
    TOKEN_EXPIRY_HOURS = int(os.environ.get('TOKEN_EXPIRY_HOURS', 48))
    
    # Operational configuration defaults (configurable via Admin)
    DEFAULT_DIESEL_PRICE = float(os.environ.get('DEFAULT_DIESEL_PRICE', 94.50))
    DEFAULT_PETROL_PRICE = float(os.environ.get('DEFAULT_PETROL_PRICE', 105.20))
    DEFAULT_ELECTRICITY_PRICE = float(os.environ.get('DEFAULT_ELECTRICITY_PRICE', 7.50))
    
    # CO2 reduction factors (kg CO2e avoided per kg recovered - labeled as estimates)
    CO2_FACTORS = {
        'PLASTIC': 1.5,
        'PAPER': 1.1,
        'CARDBOARD': 1.2,
        'GLASS': 0.3,
        'METAL': 2.8,
        'E-WASTE': 3.2,
        'ORGANIC': 0.5,
        'TEXTILE': 1.8,
        'DEFAULT': 0.8
    }
