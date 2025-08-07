import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import axios from 'axios';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Card } from './components/ui/card';
import { Badge } from './components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { Alert, AlertDescription } from './components/ui/alert';
import { Phone, MapPin, Car, User, LogOut, Navigation, Clock, Users, Package, CheckCircle, XCircle, AlertCircle, PhoneCall } from 'lucide-react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Fix Leaflet default markers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Custom icons
const taxiIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const passengerIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

function App() {
  const [user, setUser] = useState(null);
  const [currentLocation, setCurrentLocation] = useState(null);
  const [nearbyTaxis, setNearbyTaxis] = useState([]);
  const [activeTab, setActiveTab] = useState('login');
  const [authMode, setAuthMode] = useState('login'); // 'login', 'passenger', 'driver'
  const [rides, setRides] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [alert, setAlert] = useState({ show: false, type: '', message: '' });
  const [customerServiceInfo, setCustomerServiceInfo] = useState({ phone: '', message: '' });

  // Form states
  const [loginForm, setLoginForm] = useState({ phone: '', password: '' });
  const [passengerForm, setPassengerForm] = useState({ 
    name: '', 
    age: '',
    password: '' 
  });
  const [driverForm, setDriverForm] = useState({
    phone: '',
    name: '',
    car_registration_number: '',
    operating_number: '',
    taxi_office_name: '',
    taxi_office_phone: '',
    password: '',
    activation_code: ''
  });
  const [rideRequest, setRideRequest] = useState({
    pickup_address: '',
    destination_address: '',
    passenger_count: 1,
    has_luggage: false
  });

  // Get current location
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setCurrentLocation({
            lat: position.coords.latitude,
            lng: position.coords.longitude
          });
        },
        (error) => {
          console.error('Error getting location:', error);
          // Default to Riyadh coordinates
          setCurrentLocation({ lat: 24.7136, lng: 46.6753 });
        }
      );
    } else {
      setCurrentLocation({ lat: 24.7136, lng: 46.6753 });
    }
  }, []);

  // Setup axios interceptor for auth
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchUserProfile();
    }
  }, []);

  // Fetch customer service info
  useEffect(() => {
    fetchCustomerServiceInfo();
  }, []);

  // Fetch nearby taxis
  useEffect(() => {
    if (user && currentLocation) {
      fetchNearbyTaxis();
      const interval = setInterval(fetchNearbyTaxis, 30000); // Update every 30 seconds
      return () => clearInterval(interval);
    }
  }, [user, currentLocation]);

  const showAlert = (type, message) => {
    setAlert({ show: true, type, message });
    setTimeout(() => setAlert({ show: false, type: '', message: '' }), 5000);
  };

  const fetchUserProfile = async () => {
    try {
      const response = await axios.get(`${API}/me`);
      setUser(response.data);
    } catch (error) {
      localStorage.removeItem('token');
      delete axios.defaults.headers.common['Authorization'];
    }
  };

  const fetchCustomerServiceInfo = async () => {
    try {
      const response = await axios.get(`${API}/customer-service-info`);
      setCustomerServiceInfo(response.data);
    } catch (error) {
      console.error('Error fetching customer service info:', error);
    }
  };

  const fetchNearbyTaxis = async () => {
    if (!currentLocation) return;
    
    try {
      const response = await axios.get(`${API}/taxis/nearby`, {
        params: { lat: currentLocation.lat, lng: currentLocation.lng }
      });
      setNearbyTaxis(response.data);
    } catch (error) {
      console.error('Error fetching nearby taxis:', error);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    
    try {
      const response = await axios.post(`${API}/login`, loginForm);
      localStorage.setItem('token', response.data.access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
      setUser(response.data.user);
      setLoginForm({ phone: '', password: '' });
      showAlert('success', 'تم تسجيل الدخول بنجاح');
    } catch (error) {
      showAlert('error', 'خطأ في تسجيل الدخول. يرجى التحقق من رقم الهاتف وكلمة المرور.');
    }
    
    setIsLoading(false);
  };

  const handlePassengerRegister = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    
    try {
      const response = await axios.post(`${API}/register/passenger`, passengerForm);
      localStorage.setItem('token', response.data.access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
      setUser(response.data.user);
      setPassengerForm({ name: '', age: '', password: '' });
      showAlert('success', response.data.message);
    } catch (error) {
      const message = error.response?.data?.detail || 'خطأ في التسجيل.';
      showAlert('error', message);
    }
    
    setIsLoading(false);
  };

  const handleDriverRegister = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    
    try {
      const response = await axios.post(`${API}/register/driver`, driverForm);
      localStorage.setItem('token', response.data.access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
      setUser(response.data.user);
      setDriverForm({
        phone: '', name: '', car_registration_number: '', operating_number: '',
        taxi_office_name: '', taxi_office_phone: '', password: '', activation_code: ''
      });
      showAlert('success', response.data.message);
    } catch (error) {
      const message = error.response?.data?.detail || 'خطأ في التسجيل.';
      showAlert('error', message);
    }
    
    setIsLoading(false);
  };

  const handleLocationUpdate = async () => {
    if (!user || user.user_type !== 'driver' || !currentLocation || !user.is_activated) return;
    
    try {
      await axios.post(`${API}/driver/location`, {
        latitude: currentLocation.lat,
        longitude: currentLocation.lng
      });
    } catch (error) {
      console.error('Error updating location:', error);
      if (error.response?.status === 403) {
        showAlert('error', 'انتهت صلاحية التفعيل. يرجى تجديد الاشتراك.');
      }
    }
  };

  const handleRideRequest = async (e) => {
    e.preventDefault();
    if (!currentLocation) return;
    
    setIsLoading(true);
    try {
      await axios.post(`${API}/rides/request`, {
        pickup_latitude: currentLocation.lat,
        pickup_longitude: currentLocation.lng,
        pickup_address: rideRequest.pickup_address || 'الموقع الحالي',
        destination_address: rideRequest.destination_address,
        passenger_count: parseInt(rideRequest.passenger_count),
        has_luggage: rideRequest.has_luggage
      });
      
      showAlert('success', 'تم إرسال طلب التاكسي بنجاح!');
      setRideRequest({ pickup_address: '', destination_address: '', passenger_count: 1, has_luggage: false });
    } catch (error) {
      showAlert('error', 'خطأ في إرسال الطلب. يرجى المحاولة مرة أخرى.');
    }
    setIsLoading(false);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
    setUser(null);
    setNearbyTaxis([]);
  };

  const callCustomerService = () => {
    if (customerServiceInfo.phone) {
      window.open(`tel:${customerServiceInfo.phone}`, '_self');
    }
  };

  // Update location for drivers automatically
  useEffect(() => {
    if (user && user.user_type === 'driver' && currentLocation && user.is_activated) {
      handleLocationUpdate();
      const interval = setInterval(handleLocationUpdate, 60000); // Every minute
      return () => clearInterval(interval);
    }
  }, [user, currentLocation]);

  if (!user) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        {alert.show && (
          <Alert className={`fixed top-4 left-4 right-4 z-50 max-w-md mx-auto ${
            alert.type === 'success' ? 'border-green-500 bg-green-50' : 'border-red-500 bg-red-50'
          }`}>
            {alert.type === 'success' ? <CheckCircle className="w-4 h-4 text-green-600" /> : <XCircle className="w-4 h-4 text-red-600" />}
            <AlertDescription className={alert.type === 'success' ? 'text-green-800' : 'text-red-800'}>
              {alert.message}
            </AlertDescription>
          </Alert>
        )}

        <Card className="w-full max-w-md p-6 shadow-xl">
          <div className="text-center mb-6">
            <Car className="w-12 h-12 text-indigo-600 mx-auto mb-4" />
            <h1 className="text-2xl font-bold text-gray-900 mb-2">تطبيق التاكسي الذكي</h1>
            <p className="text-gray-600">اربط بين السائقين والركاب بسهولة</p>
          </div>

          <Tabs value={authMode} onValueChange={setAuthMode}>
            <TabsList className="grid w-full grid-cols-3 mb-6">
              <TabsTrigger value="login">تسجيل الدخول</TabsTrigger>
              <TabsTrigger value="passenger">راكب جديد</TabsTrigger>
              <TabsTrigger value="driver">سائق جديد</TabsTrigger>
            </TabsList>

            <TabsContent value="login">
              <form onSubmit={handleLogin} className="space-y-4">
                <div>
                  <Input
                    type="tel"
                    placeholder="رقم الهاتف"
                    value={loginForm.phone}
                    onChange={(e) => setLoginForm({...loginForm, phone: e.target.value})}
                    required
                    className="text-right"
                  />
                </div>
                <div>
                  <Input
                    type="password"
                    placeholder="كلمة المرور"
                    value={loginForm.password}
                    onChange={(e) => setLoginForm({...loginForm, password: e.target.value})}
                    required
                    className="text-right"
                  />
                </div>
                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? 'جارٍ تسجيل الدخول...' : 'تسجيل الدخول'}
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="passenger">
              <form onSubmit={handlePassengerRegister} className="space-y-4">
                <div>
                  <Input
                    type="text"
                    placeholder="الاسم الكامل"
                    value={passengerForm.name}
                    onChange={(e) => setPassengerForm({...passengerForm, name: e.target.value})}
                    required
                    className="text-right"
                  />
                </div>
                <div>
                  <Input
                    type="number"
                    placeholder="العمر (15 سنة أو أكثر)"
                    value={passengerForm.age}
                    onChange={(e) => setPassengerForm({...passengerForm, age: e.target.value})}
                    required
                    min="15"
                    max="100"
                    className="text-right"
                  />
                </div>
                <div>
                  <Input
                    type="password"
                    placeholder="كلمة المرور"
                    value={passengerForm.password}
                    onChange={(e) => setPassengerForm({...passengerForm, password: e.target.value})}
                    required
                    className="text-right"
                  />
                </div>
                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? 'جارٍ إنشاء الحساب...' : 'إنشاء حساب راكب'}
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="driver">
              <form onSubmit={handleDriverRegister} className="space-y-4">
                {/* Customer service contact */}
                <div className="bg-blue-50 p-3 rounded-lg border border-blue-200">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold text-blue-900 text-right">للحصول على كود التفعيل</h4>
                    <PhoneCall className="w-4 h-4 text-blue-600" />
                  </div>
                  <p className="text-sm text-blue-800 text-right mb-2">
                    {customerServiceInfo.message}
                  </p>
                  <Button 
                    type="button"
                    variant="outline" 
                    size="sm"
                    onClick={callCustomerService}
                    className="w-full text-right"
                  >
                    <Phone className="w-4 h-4 ml-2" />
                    اتصل بخدمة العملاء: {customerServiceInfo.phone}
                  </Button>
                </div>

                <div>
                  <Input
                    type="tel"
                    placeholder="رقم الهاتف (05xxxxxxxx)"
                    value={driverForm.phone}
                    onChange={(e) => setDriverForm({...driverForm, phone: e.target.value})}
                    required
                    pattern="^05\d{8}$"
                    maxLength={10}
                    className="text-right"
                  />
                </div>
                
                <div>
                  <Input
                    type="text"
                    placeholder="كود التفعيل (05xxxxx)"
                    value={driverForm.activation_code}
                    onChange={(e) => setDriverForm({...driverForm, activation_code: e.target.value})}
                    required
                    pattern="^05\d{5}$"
                    maxLength={7}
                    className="text-center text-lg font-mono"
                  />
                  <p className="text-xs text-gray-600 mt-1 text-right">
                    مثال: 0500001
                  </p>
                </div>

                <div>
                  <Input
                    type="text"
                    placeholder="الاسم الثلاثي (حسب الرخصة)"
                    value={driverForm.name}
                    onChange={(e) => setDriverForm({...driverForm, name: e.target.value})}
                    required
                    className="text-right"
                  />
                </div>
                <div>
                  <Input
                    type="text"
                    placeholder="رقم تسجيل السيارة"
                    value={driverForm.car_registration_number}
                    onChange={(e) => setDriverForm({...driverForm, car_registration_number: e.target.value})}
                    required
                    className="text-right"
                  />
                </div>
                <div>
                  <Input
                    type="text"
                    placeholder="رقم التشغيل"
                    value={driverForm.operating_number}
                    onChange={(e) => setDriverForm({...driverForm, operating_number: e.target.value})}
                    required
                    className="text-right"
                  />
                </div>
                <div>
                  <Input
                    type="text"
                    placeholder="اسم مكتب التاكسي"
                    value={driverForm.taxi_office_name}
                    onChange={(e) => setDriverForm({...driverForm, taxi_office_name: e.target.value})}
                    required
                    className="text-right"
                  />
                </div>
                <div>
                  <Input
                    type="tel"
                    placeholder="رقم هاتف المكتب"
                    value={driverForm.taxi_office_phone}
                    onChange={(e) => setDriverForm({...driverForm, taxi_office_phone: e.target.value})}
                    required
                    className="text-right"
                  />
                </div>
                <div>
                  <Input
                    type="password"
                    placeholder="كلمة المرور"
                    value={driverForm.password}
                    onChange={(e) => setDriverForm({...driverForm, password: e.target.value})}
                    required
                    className="text-right"
                  />
                </div>
                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? 'جارٍ إنشاء الحساب...' : 'إنشاء حساب سائق'}
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {alert.show && (
        <Alert className={`fixed top-4 left-4 right-4 z-50 max-w-md mx-auto ${
          alert.type === 'success' ? 'border-green-500 bg-green-50' : 'border-red-500 bg-red-50'
        }`}>
          {alert.type === 'success' ? <CheckCircle className="w-4 h-4 text-green-600" /> : <XCircle className="w-4 h-4 text-red-600" />}
          <AlertDescription className={alert.type === 'success' ? 'text-green-800' : 'text-red-800'}>
            {alert.message}
          </AlertDescription>
        </Alert>
      )}

      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-4 space-x-reverse">
              <Car className="w-8 h-8 text-indigo-600" />
              <h1 className="text-xl font-bold text-gray-900">تطبيق التاكسي الذكي</h1>
            </div>
            
            <div className="flex items-center space-x-4 space-x-reverse">
              <div className="flex items-center space-x-2 space-x-reverse">
                <User className="w-5 h-5 text-gray-600" />
                <span className="text-sm text-gray-700">{user.name}</span>
                <Badge variant={user.user_type === 'driver' ? 'default' : 'secondary'}>
                  {user.user_type === 'driver' ? 'سائق' : 'راكب'}
                </Badge>
                {user.user_type === 'driver' && (
                  <Badge variant={user.is_activated ? 'default' : 'destructive'} className="text-xs">
                    {user.is_activated ? 'مفعل' : 'غير مفعل'}
                  </Badge>
                )}
              </div>
              <Button variant="outline" size="sm" onClick={handleLogout}>
                <LogOut className="w-4 h-4 ml-2" />
                خروج
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Map Section */}
          <div className="lg:col-span-2">
            <Card className="p-4 h-96">
              <h2 className="text-lg font-semibold mb-4 text-right flex items-center">
                <MapPin className="w-5 h-5 ml-2" />
                الخريطة التفاعلية
              </h2>
              
              {currentLocation && (
                <MapContainer
                  center={[currentLocation.lat, currentLocation.lng]}
                  zoom={13}
                  style={{ height: '320px', width: '100%' }}
                  className="rounded-lg"
                >
                  <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  />
                  
                  {/* Current location marker */}
                  <Marker position={[currentLocation.lat, currentLocation.lng]} icon={passengerIcon}>
                    <Popup>موقعك الحالي</Popup>
                  </Marker>
                  
                  {/* Nearby taxis */}
                  {nearbyTaxis.map((taxi) => (
                    <Marker
                      key={taxi.id}
                      position={[taxi.latitude, taxi.longitude]}
                      icon={taxiIcon}
                    >
                      <Popup>
                        <div className="text-center">
                          <strong>{taxi.driver_name}</strong>
                          <br />
                          <span className="text-sm text-gray-600">سائق متاح</span>
                        </div>
                      </Popup>
                    </Marker>
                  ))}
                </MapContainer>
              )}
            </Card>
          </div>

          {/* Controls Section */}
          <div className="space-y-6">
            {user.user_type === 'passenger' ? (
              // Passenger Controls
              <Card className="p-4">
                <h3 className="text-lg font-semibold mb-4 text-right flex items-center">
                  <Navigation className="w-5 h-5 ml-2" />
                  طلب تاكسي
                </h3>
                
                <form onSubmit={handleRideRequest} className="space-y-4">
                  <div>
                    <Input
                      type="text"
                      placeholder="عنوان نقطة الانطلاق (اختياري)"
                      value={rideRequest.pickup_address}
                      onChange={(e) => setRideRequest({...rideRequest, pickup_address: e.target.value})}
                      className="text-right"
                    />
                  </div>
                  <div>
                    <Input
                      type="text"
                      placeholder="عنوان الوجهة"
                      value={rideRequest.destination_address}
                      onChange={(e) => setRideRequest({...rideRequest, destination_address: e.target.value})}
                      required
                      className="text-right"
                    />
                  </div>
                  <div className="flex space-x-2 space-x-reverse">
                    <div className="flex-1">
                      <label className="block text-sm font-medium mb-2 text-right">عدد الركاب</label>
                      <select
                        value={rideRequest.passenger_count}
                        onChange={(e) => setRideRequest({...rideRequest, passenger_count: e.target.value})}
                        className="w-full p-2 border border-gray-300 rounded-md text-right"
                      >
                        <option value="1">1</option>
                        <option value="2">2</option>
                        <option value="3">3</option>
                        <option value="4">4</option>
                      </select>
                    </div>
                    <div className="flex-1">
                      <label className="block text-sm font-medium mb-2 text-right">الأمتعة</label>
                      <select
                        value={rideRequest.has_luggage}
                        onChange={(e) => setRideRequest({...rideRequest, has_luggage: e.target.value === 'true'})}
                        className="w-full p-2 border border-gray-300 rounded-md text-right"
                      >
                        <option value="false">بدون أمتعة</option>
                        <option value="true">مع أمتعة</option>
                      </select>
                    </div>
                  </div>
                  <Button type="submit" className="w-full" disabled={isLoading}>
                    <Car className="w-4 h-4 ml-2" />
                    {isLoading ? 'جارٍ الطلب...' : 'طلب تاكسي'}
                  </Button>
                </form>
              </Card>
            ) : (
              // Driver Controls
              <Card className="p-4">
                <h3 className="text-lg font-semibold mb-4 text-right flex items-center">
                  <Car className="w-5 h-5 ml-2" />
                  لوحة السائق
                </h3>
                
                <div className="space-y-4">
                  <div className="text-center">
                    <Badge variant="default" className="text-sm">
                      متاح للعمل
                    </Badge>
                    <p className="text-sm text-gray-600 mt-2">
                      يتم تحديث موقعك تلقائياً كل دقيقة
                    </p>
                  </div>
                  
                  <div className="bg-gray-50 p-3 rounded-lg text-center">
                    <p className="text-sm text-gray-700 mb-2">انتظار طلبات الرحلات...</p>
                    <Clock className="w-6 h-6 text-gray-400 mx-auto" />
                  </div>
                </div>
              </Card>
            )}

            {/* Nearby Taxis/Stats */}
            <Card className="p-4">
              <h3 className="text-lg font-semibold mb-4 text-right">
                {user.user_type === 'passenger' ? 'التاكسيات القريبة' : 'معلومات السائق'}
              </h3>
              
              {user.user_type === 'passenger' ? (
                <div className="space-y-3">
                  {nearbyTaxis.length > 0 ? (
                    nearbyTaxis.slice(0, 3).map((taxi) => (
                      <div key={taxi.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                        <div className="flex items-center space-x-3 space-x-reverse">
                          <Car className="w-4 h-4 text-green-600" />
                          <span className="text-sm font-medium">{taxi.driver_name}</span>
                        </div>
                        <Badge variant="secondary" className="text-xs">متاح</Badge>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-4">
                      <Car className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                      <p className="text-sm text-gray-600">لا توجد تاكسيات متاحة في المنطقة</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-3 text-right">
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">رقم الهاتف</span>
                    <span className="font-semibold text-xs">{user.phone}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">رقم التسجيل</span>
                    <span className="font-semibold text-xs">{user.car_registration_number}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">رقم التشغيل</span>
                    <span className="font-semibold text-xs">{user.operating_number}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">مكتب التاكسي</span>
                    <span className="font-semibold text-xs">{user.taxi_office_name}</span>
                  </div>
                  {user.is_activated && user.activation_expires && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">صالح حتى</span>
                      <span className="font-semibold text-xs">
                        {new Date(user.activation_expires).toLocaleDateString('ar-SA')}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;