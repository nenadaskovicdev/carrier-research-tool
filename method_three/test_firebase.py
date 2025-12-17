# check_firebase_key.py
import json
import os

def check_service_account_file(filepath):
    """Check if the service account file is valid"""
    if not os.path.exists(filepath):
        print(f"❌ File does not exist: {filepath}")
        return False
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        print(f"✅ File exists and is valid JSON")
        
        # Check required fields
        required_fields = [
            "type", "project_id", "private_key_id", 
            "private_key", "client_email", "client_id",
            "auth_uri", "token_uri", "auth_provider_x509_cert_url",
            "client_x509_cert_url"
        ]
        
        print("\nChecking required fields:")
        all_valid = True
        for field in required_fields:
            if field in data:
                value = data[field]
                if field == "private_key":
                    print(f"  ✓ {field}: {'PRIVATE_KEY' if value.startswith('-----BEGIN') else 'INVALID_FORMAT'}")
                elif field == "client_email":
                    print(f"  ✓ {field}: {value}")
                else:
                    print(f"  ✓ {field}: Present")
            else:
                print(f"  ❌ {field}: MISSING")
                all_valid = False
        
        if all_valid:
            print("\n✅ All required fields are present!")
            print(f"\nService account email: {data['client_email']}")
            print(f"Project ID: {data['project_id']}")
            return True
        else:
            print("\n❌ Missing required fields!")
            return False
            
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False

# Check the file
filepath = "firebase_service_account.json"
print(f"Checking: {filepath}")
print("="*60)
check_service_account_file(filepath)