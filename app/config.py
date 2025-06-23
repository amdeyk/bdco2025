# app/config.py
import os
import configparser
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class Config:
    """Configuration management with sensible defaults"""
    
    def __init__(self, config_file="config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        
        # Create default configuration
        self._set_defaults()
        
        # Load custom configuration if exists
        if os.path.exists(config_file):
            try:
                self.config.read(config_file)
                logger.info(f"Configuration loaded from {config_file}")
            except Exception as e:
                logger.error(f"Error loading configuration: {str(e)}")
        else:
            self._create_default_config()
    
    def _set_defaults(self):
        """Set default configuration values"""
        self.config['DEFAULT'] = {
            'AdminPassword': 'Magna_code@123',
            'SoftwareVersion': '2.0',
            'Debug': 'False',
            'SecretKey': 'generate_random_secret_key_here'
        }
        
        self.config['DATABASE'] = {
            'CSVPath': './data/guests.csv',
            'BackupDir': './data/backups'
        }
        
        self.config['PATHS'] = {
            'StaticDir': './static',
            'TemplatesDir': './templates',
            'LogsDir': './logs'
        }
        
        self.config['SECURITY'] = {
            'MaxLoginAttempts': '3',
            'SessionTimeout': '30'
        }
        
    
    def _create_default_config(self):
        """Create default configuration file"""
        try:
            # Ensure directory exists if config file has a path
            if os.path.dirname(self.config_file):
                os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
                
            # Write configuration
            with open(self.config_file, 'w') as f:
                self.config.write(f)
                
            logger.info(f"Created default configuration file: {self.config_file}")
        except Exception as e:
            logger.error(f"Error creating default configuration: {str(e)}")
    
    def get(self, section, key, fallback=None):
        """Get configuration value with fallback"""
        return self.config.get(section, key, fallback=fallback)
    
    def getboolean(self, section, key, fallback=None):
        """Get boolean configuration value with fallback"""
        return self.config.getboolean(section, key, fallback=fallback)
    
    def getint(self, section, key, fallback=None):
        """Get integer configuration value with fallback"""
        return self.config.getint(section, key, fallback=fallback)
    
    def set(self, section, key, value):
        """Set configuration value"""
        if section not in self.config:
            self.config[section] = {}
        
        self.config[section][key] = str(value)
        
        # Save changes
        try:
            with open(self.config_file, 'w') as f:
                self.config.write(f)
            logger.info(f"Updated configuration: {section}.{key}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            return False