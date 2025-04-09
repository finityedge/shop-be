#!/usr/bin/env python3
"""
Django Unit Model Seeder Script
This script seeds Unit model data in a Django application.
"""
import argparse
import random
import sys
import os
import json
import django
from django.db import transaction
from django.contrib.auth import get_user_model

# Default configuration
DEFAULT_CONFIG = {
    "seeding": {
        "total_units": 50,
        "batch_size": 100
    },
    "unit_data": [
        {"name": "Pieces", "symbol": "pcs"},
        {"name": "Kilograms", "symbol": "kg"},
        {"name": "Grams", "symbol": "g"},
        {"name": "Liters", "symbol": "L"},
        {"name": "Milliliters", "symbol": "ml"},
        {"name": "Meters", "symbol": "m"},
        {"name": "Centimeters", "symbol": "cm"},
        {"name": "Box", "symbol": "box"},
        {"name": "Carton", "symbol": "ctn"},
        {"name": "Dozen", "symbol": "dz"},
        {"name": "Pack", "symbol": "pk"},
        {"name": "Pair", "symbol": "pr"},
        {"name": "Bottle", "symbol": "btl"},
        {"name": "Can", "symbol": "can"},
        {"name": "Sachet", "symbol": "sct"},
        {"name": "Roll", "symbol": "roll"},
        {"name": "Bundle", "symbol": "bdl"},
        {"name": "Tablet", "symbol": "tab"},
        {"name": "Capsule", "symbol": "cap"},
        {"name": "Sheet", "symbol": "sht"}
    ]
}

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Seed Unit model data into Django database")
    parser.add_argument("-c", "--config", help="Path to JSON configuration file")
    parser.add_argument("-n", "--number", type=int, help="Number of units to seed")
    parser.add_argument("-s", "--settings", default="settings", help="Django settings module path")
    parser.add_argument("--dry-run", action="store_true", help="Print data without saving")
    parser.add_argument("--clear", action="store_true", help="Clear existing Unit data before seeding")
    parser.add_argument("--user-id", type=int, help="User ID to set as created_by and modified_by")
    return parser.parse_args()

def load_config(config_path=None):
    """Load configuration from file or use defaults."""
    config = DEFAULT_CONFIG.copy()
    
    if config_path:
        try:
            with open(config_path, 'r') as f:
                custom_config = json.load(f)
                
            # Update config with custom values
            if "seeding" in custom_config:
                config["seeding"].update(custom_config["seeding"])
            if "unit_data" in custom_config:
                config["unit_data"] = custom_config["unit_data"]
                
            print(f"Configuration loaded from {config_path}")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error loading config file: {e}")
            sys.exit(1)
    
    return config

def apply_cli_overrides(config, args):
    """Override config with command line arguments."""
    if args.number:
        config["seeding"]["total_units"] = args.number
    return config

def setup_django(settings_module):
    """Set up Django environment."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    try:
        django.setup()
        print(f"Django setup complete with settings module: {settings_module}")
    except Exception as e:
        print(f"Failed to setup Django: {e}")
        sys.exit(1)

def get_user(user_id):
    """Get user for created_by and modified_by fields."""
    if not user_id:
        return None
    
    User = get_user_model()
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        print(f"Warning: User with ID {user_id} not found. Units will be created without user attribution.")
        return None

def generate_unit_data(config, total_units, user=None):
    """Generate unit data based on configuration."""
    from apps.inventory.models import Unit
    
    # Use defined units in config
    unit_templates = config["unit_data"]
    
    # If we have fewer templates than total_units, we'll need to create variations
    units_to_create = []
    
    if total_units <= len(unit_templates):
        # Use a random subset of the templates if we need fewer units than templates
        selected_templates = random.sample(unit_templates, total_units)
        
        for template in selected_templates:
            units_to_create.append(
                Unit(
                    name=template["name"],
                    symbol=template["symbol"],
                    created_by=user,
                    modified_by=user
                )
            )
    else:
        # Use all templates
        for template in unit_templates:
            units_to_create.append(
                Unit(
                    name=template["name"],
                    symbol=template["symbol"],
                    created_by=user,
                    modified_by=user
                )
            )
        
        # Generate additional variations
        remaining = total_units - len(unit_templates)
        for i in range(remaining):
            # Choose a random template and create a variation
            template = random.choice(unit_templates)
            variant_suffix = f" {random.choice(['Type', 'Variant', 'Class', 'Size'])} {i+1}"
            units_to_create.append(
                Unit(
                    name=f"{template['name']}{variant_suffix}",
                    symbol=f"{template['symbol']}{i+1}",
                    created_by=user,
                    modified_by=user
                )
            )
    
    return units_to_create

def clear_existing_data():
    """Clear existing Unit data."""
    from apps.inventory.models import Unit
    count = Unit.objects.count()
    Unit.objects.all().delete()
    print(f"Cleared {count} existing Unit records")

def save_units(units, batch_size, dry_run=False):
    """Save units to database in batches."""
    from apps.inventory.models import Unit
    
    if dry_run:
        print(f"DRY RUN: Would insert {len(units)} units with the following data:")
        for i, unit in enumerate(units[:5], 1):
            print(f"{i}. {unit.name} ({unit.symbol})")
        if len(units) > 5:
            print(f"... and {len(units) - 5} more units")
        return
    
    # Use bulk_create with batches
    total_created = 0
    for i in range(0, len(units), batch_size):
        batch = units[i:i+batch_size]
        with transaction.atomic():
            Unit.objects.bulk_create(batch)
            total_created += len(batch)
        print(f"Progress: Created {total_created}/{len(units)} units")
    
    print(f"Successfully created {total_created} units")

def main():
    """Main function to seed the database."""
    args = parse_arguments()
    
    # Setup Django environment
    setup_django(args.settings)
    
    # Load configuration
    config = load_config(args.config)
    config = apply_cli_overrides(config, args)
    
    # Import models here after Django is set up
    try:
        from apps.inventory.models import Unit
    except ImportError:
        print("Error: Could not import Unit model. Make sure your Django settings are correct.")
        sys.exit(1)
    
    # Extract specific configs
    total_units = config["seeding"]["total_units"]
    batch_size = config["seeding"]["batch_size"]
    
    print(f"Preparing to seed {total_units} units...")
    
    # Get user if specified
    user = get_user(args.user_id) if args.user_id else None
    
    # Clear existing data if requested
    if args.clear and not args.dry_run:
        clear_existing_data()
    
    # Generate unit data
    units = generate_unit_data(config, total_units, user)
    
    # Save to database
    if units:
        save_units(units, batch_size, args.dry_run)
    
    print("Seeding process completed")

if __name__ == "__main__":
    main()