import requests
import sys
import json
from datetime import datetime

class SmartTaxiAPITester:
    def __init__(self, base_url="https://f9cdeb8f-343e-42b3-a76f-8286081ec448.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.passenger_token = None
        self.driver_token = None
        self.passenger_user = None
        self.driver_user = None
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, token=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}" if endpoint else self.base_url
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=data)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                except:
                    print(f"   Response: {response.text[:200]}...")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")

            return success, response.json() if response.text and response.status_code < 500 else {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test API health check"""
        success, response = self.run_test(
            "API Health Check",
            "GET",
            "",
            200
        )
        return success

    def test_register_passenger(self):
        """Test passenger registration"""
        timestamp = datetime.now().strftime('%H%M%S')
        passenger_data = {
            "phone": f"966501234{timestamp}",
            "name": f"Test Passenger {timestamp}",
            "user_type": "passenger",
            "password": "TestPass123!"
        }
        
        success, response = self.run_test(
            "Register Passenger",
            "POST",
            "register",
            200,
            data=passenger_data
        )
        
        if success and 'access_token' in response:
            self.passenger_token = response['access_token']
            self.passenger_user = response['user']
            print(f"   Passenger registered: {self.passenger_user['name']} ({self.passenger_user['phone']})")
            return True
        return False

    def test_register_driver(self):
        """Test driver registration"""
        timestamp = datetime.now().strftime('%H%M%S')
        driver_data = {
            "phone": f"966507654{timestamp}",
            "name": f"Test Driver {timestamp}",
            "user_type": "driver",
            "password": "TestPass123!"
        }
        
        success, response = self.run_test(
            "Register Driver",
            "POST",
            "register",
            200,
            data=driver_data
        )
        
        if success and 'access_token' in response:
            self.driver_token = response['access_token']
            self.driver_user = response['user']
            print(f"   Driver registered: {self.driver_user['name']} ({self.driver_user['phone']})")
            return True
        return False

    def test_login_passenger(self):
        """Test passenger login"""
        if not self.passenger_user:
            print("❌ No passenger user to test login")
            return False
            
        login_data = {
            "phone": self.passenger_user['phone'],
            "password": "TestPass123!"
        }
        
        success, response = self.run_test(
            "Login Passenger",
            "POST",
            "login",
            200,
            data=login_data
        )
        
        if success and 'access_token' in response:
            print(f"   Login successful for passenger: {response['user']['name']}")
            return True
        return False

    def test_login_driver(self):
        """Test driver login"""
        if not self.driver_user:
            print("❌ No driver user to test login")
            return False
            
        login_data = {
            "phone": self.driver_user['phone'],
            "password": "TestPass123!"
        }
        
        success, response = self.run_test(
            "Login Driver",
            "POST",
            "login",
            200,
            data=login_data
        )
        
        if success and 'access_token' in response:
            print(f"   Login successful for driver: {response['user']['name']}")
            return True
        return False

    def test_get_passenger_profile(self):
        """Test getting passenger profile"""
        success, response = self.run_test(
            "Get Passenger Profile",
            "GET",
            "me",
            200,
            token=self.passenger_token
        )
        
        if success and response.get('user_type') == 'passenger':
            print(f"   Profile retrieved: {response['name']} ({response['user_type']})")
            return True
        return False

    def test_get_driver_profile(self):
        """Test getting driver profile"""
        success, response = self.run_test(
            "Get Driver Profile",
            "GET",
            "me",
            200,
            token=self.driver_token
        )
        
        if success and response.get('user_type') == 'driver':
            print(f"   Profile retrieved: {response['name']} ({response['user_type']})")
            return True
        return False

    def test_update_driver_location(self):
        """Test driver location update"""
        location_data = {
            "latitude": 24.7136,
            "longitude": 46.6753
        }
        
        success, response = self.run_test(
            "Update Driver Location",
            "POST",
            "driver/location",
            200,
            data=location_data,
            token=self.driver_token
        )
        
        if success:
            print(f"   Location updated successfully")
            return True
        return False

    def test_get_nearby_taxis(self):
        """Test getting nearby taxis"""
        params = {
            "lat": 24.7136,
            "lng": 46.6753
        }
        
        success, response = self.run_test(
            "Get Nearby Taxis",
            "GET",
            "taxis/nearby",
            200,
            data=params,
            token=self.passenger_token
        )
        
        if success:
            taxi_count = len(response) if isinstance(response, list) else 0
            print(f"   Found {taxi_count} nearby taxis")
            return True
        return False

    def test_request_ride(self):
        """Test ride request"""
        ride_data = {
            "pickup_latitude": 24.7136,
            "pickup_longitude": 46.6753,
            "pickup_address": "الموقع الحالي",
            "destination_address": "مطار الملك خالد الدولي"
        }
        
        success, response = self.run_test(
            "Request Ride",
            "POST",
            "rides/request",
            200,
            data=ride_data,
            token=self.passenger_token
        )
        
        if success and 'ride_id' in response:
            print(f"   Ride requested successfully: {response['ride_id']}")
            return True
        return False

    def test_unauthorized_access(self):
        """Test unauthorized access"""
        success, response = self.run_test(
            "Unauthorized Access Test",
            "GET",
            "me",
            401
        )
        return success

    def test_passenger_cannot_update_location(self):
        """Test that passengers cannot update driver location"""
        location_data = {
            "latitude": 24.7136,
            "longitude": 46.6753
        }
        
        success, response = self.run_test(
            "Passenger Cannot Update Location",
            "POST",
            "driver/location",
            403,
            data=location_data,
            token=self.passenger_token
        )
        return success

    def test_driver_cannot_request_ride(self):
        """Test that drivers cannot request rides"""
        ride_data = {
            "pickup_latitude": 24.7136,
            "pickup_longitude": 46.6753,
            "pickup_address": "الموقع الحالي",
            "destination_address": "مطار الملك خالد الدولي"
        }
        
        success, response = self.run_test(
            "Driver Cannot Request Ride",
            "POST",
            "rides/request",
            403,
            data=ride_data,
            token=self.driver_token
        )
        return success

def main():
    print("🚕 Smart Taxi API Testing Started")
    print("=" * 50)
    
    tester = SmartTaxiAPITester()
    
    # Test sequence
    tests = [
        ("API Health Check", tester.test_health_check),
        ("Register Passenger", tester.test_register_passenger),
        ("Register Driver", tester.test_register_driver),
        ("Login Passenger", tester.test_login_passenger),
        ("Login Driver", tester.test_login_driver),
        ("Get Passenger Profile", tester.test_get_passenger_profile),
        ("Get Driver Profile", tester.test_get_driver_profile),
        ("Update Driver Location", tester.test_update_driver_location),
        ("Get Nearby Taxis", tester.test_get_nearby_taxis),
        ("Request Ride", tester.test_request_ride),
        ("Unauthorized Access", tester.test_unauthorized_access),
        ("Passenger Cannot Update Location", tester.test_passenger_cannot_update_location),
        ("Driver Cannot Request Ride", tester.test_driver_cannot_request_ride),
    ]
    
    failed_tests = []
    
    for test_name, test_func in tests:
        try:
            if not test_func():
                failed_tests.append(test_name)
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            failed_tests.append(test_name)
    
    # Print results
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS")
    print("=" * 50)
    print(f"Tests run: {tester.tests_run}")
    print(f"Tests passed: {tester.tests_passed}")
    print(f"Tests failed: {len(failed_tests)}")
    print(f"Success rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if failed_tests:
        print(f"\n❌ Failed tests:")
        for test in failed_tests:
            print(f"   - {test}")
    else:
        print(f"\n✅ All tests passed!")
    
    return 0 if len(failed_tests) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())