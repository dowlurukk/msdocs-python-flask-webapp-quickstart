#!/usr/bin/env python3
"""
Azure App Service compatibility fix for typing_extensions conflicts
This script ensures the correct typing_extensions version is used
"""
import sys
import os
import subprocess
import importlib.util

def fix_typing_extensions():
    """Fix typing_extensions import conflicts in Azure App Service"""
    try:
        # First, try to install the correct version to the site-packages
        print("Installing correct typing_extensions version...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "--force-reinstall", "--target", "/tmp/8de1e6c548f3a4e/antenv/lib/python3.12/site-packages",
            "typing_extensions==4.15.0"
        ])
        
        # Remove any cached imports
        if 'typing_extensions' in sys.modules:
            del sys.modules['typing_extensions']
        
        # Force the correct path to be first in sys.path
        site_packages = "/tmp/8de1e6c548f3a4e/antenv/lib/python3.12/site-packages"
        if site_packages not in sys.path:
            sys.path.insert(0, site_packages)
        
        # Test the import
        import typing_extensions
        if hasattr(typing_extensions, 'Sentinel'):
            print("✅ typing_extensions.Sentinel is available")
            return True
        else:
            print("❌ typing_extensions.Sentinel is not available")
            return False
            
    except Exception as e:
        print(f"❌ Error fixing typing_extensions: {e}")
        return False

def install_requirements():
    """Install requirements with compatibility fixes"""
    try:
        # Install critical packages first
        critical_packages = [
            "typing_extensions==4.15.0",
            "pydantic==2.12.4", 
            "pydantic-core==2.41.5"
        ]
        
        for package in critical_packages:
            print(f"Installing {package}...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", 
                "--force-reinstall", package
            ])
        
        # Install remaining requirements
        print("Installing remaining requirements...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        
        return True
    except Exception as e:
        print(f"❌ Error installing requirements: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Starting Azure App Service compatibility fix...")
    
    # Fix typing_extensions
    if not fix_typing_extensions():
        print("❌ Failed to fix typing_extensions")
        sys.exit(1)
    
    # Install requirements
    if not install_requirements():
        print("❌ Failed to install requirements")
        sys.exit(1)
    
    print("✅ All dependencies installed successfully!")
    
    # Start the application
    os.system("gunicorn --bind=0.0.0.0 --timeout 600 app:app")