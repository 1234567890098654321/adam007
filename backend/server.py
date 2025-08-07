from fastapi import FastAPI, APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, validator
from typing import List, Optional
import uuid
from datetime import datetime, timedelta
import bcrypt
import jwt
import json
import secrets
import string
import re

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
SECRET_KEY = "smart_taxi_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI()
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.driver_connections: dict = {}
        self.passenger_connections: dict = {}

    async def connect(self, websocket: WebSocket, user_id: str, user_type: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        if user_type == "driver":
            self.driver_connections[user_id] = websocket
        else:
            self.passenger_connections[user_id] = websocket

    def disconnect(self, websocket: WebSocket, user_id: str, user_type: str):
        self.active_connections.remove(websocket)
        if user_type == "driver" and user_id in self.driver_connections:
            del self.driver_connections[user_id]
        elif user_type == "passenger" and user_id in self.passenger_connections:
            del self.passenger_connections[user_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phone: str
    name: str
    user_type: str  # "driver" or "passenger"
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    
    # Passenger specific fields
    age: Optional[int] = None
    
    # Driver specific fields
    car_registration_number: Optional[str] = None
    operating_number: Optional[str] = None
    taxi_office_name: Optional[str] = None
    taxi_office_phone: Optional[str] = None
    activation_code: Optional[str] = None
    activation_expires: Optional[datetime] = None
    is_activated: bool = Field(default=False)

class PassengerCreate(BaseModel):
    name: str
    age: int
    password: str
    
    @validator('age')
    def validate_age(cls, v):
        if v < 15:
            raise ValueError('العمر يجب أن يكون 15 سنة أو أكثر')
        return v

class DriverCreate(BaseModel):
    phone: str  # رقم الهاتف الفعلي للسائق
    name: str  # الاسم الثلاثي
    car_registration_number: str
    operating_number: str
    taxi_office_name: str
    taxi_office_phone: str
    password: str
    activation_code: str  # كود التفعيل مطلوب عند التسجيل
    
    @validator('phone')
    def validate_phone(cls, v):
        # التحقق من صيغة رقم الهاتف السعودي
        if not re.match(r'^05\d{8}$', v):
            raise ValueError('رقم الهاتف يجب أن يبدأ بـ 05 ويتكون من 10 أرقام')
        return v
    
    @validator('activation_code')
    def validate_activation_code(cls, v):
        # التحقق من صيغة كود التفعيل: 05 + 5 أرقام من 00001 إلى 99999
        if not re.match(r'^05\d{5}$', v):
            raise ValueError('كود التفعيل يجب أن يبدأ بـ 05 ويتكون من 10 أرقام')
        
        # التحقق من أن الأرقام الـ5 الأخيرة في النطاق الصحيح
        last_five = v[2:]  # آخر 5 أرقام
        if not (1 <= int(last_five) <= 99999):
            raise ValueError('كود التفعيل غير صحيح')
        
        return v

class UserLogin(BaseModel):
    phone: str
    password: str

class UserResponse(BaseModel):
    id: str
    phone: str
    name: str
    user_type: str
    is_active: bool
    age: Optional[int] = None
    car_registration_number: Optional[str] = None
    operating_number: Optional[str] = None
    taxi_office_name: Optional[str] = None
    taxi_office_phone: Optional[str] = None
    is_activated: bool = False
    activation_expires: Optional[datetime] = None

class ActivationCode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    code: str
    driver_phone: Optional[str] = None  # رقم هاتف السائق الذي استخدم الكود
    is_used: bool = False
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TaxiLocation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    driver_id: str
    latitude: float
    longitude: float
    is_available: bool = True
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class RideRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    passenger_id: str
    pickup_latitude: float
    pickup_longitude: float
    pickup_address: str
    destination_latitude: Optional[float] = None
    destination_longitude: Optional[float] = None
    destination_address: Optional[str] = None
    passenger_count: int = 1
    has_luggage: bool = False
    status: str = "pending"  # pending, accepted, in_progress, completed, cancelled
    driver_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class RideRequestCreate(BaseModel):
    pickup_latitude: float
    pickup_longitude: float
    pickup_address: str
    destination_latitude: Optional[float] = None
    destination_longitude: Optional[float] = None
    destination_address: Optional[str] = None
    passenger_count: int = 1
    has_luggage: bool = False

# Helper Functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def generate_activation_code() -> str:
    """Generate activation code in format: 05XXXXX where XXXXX is 00001-99999"""
    # Get the highest used number
    import asyncio
    
    async def get_next_number():
        # Find the highest used code
        codes = await db.activation_codes.find().sort("code", -1).to_list(1)
        if not codes:
            return 1
        
        last_code = codes[0]["code"]
        if last_code.startswith("05"):
            last_number = int(last_code[2:])
            return min(last_number + 1, 99999)
        return 1
    
    # For sync context, we'll use a simple counter approach
    import random
    number = random.randint(1, 99999)
    return f"05{number:05d}"

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    user = await db.users.find_one({"id": user_id})
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    
    return User(**user)

# Routes
@api_router.get("/")
async def root():
    return {"message": "Smart Taxi API is running", "status": "success"}

@api_router.post("/register/passenger", response_model=dict)
async def register_passenger(passenger_data: PassengerCreate):
    # Generate a unique phone number for passengers
    phone = f"PASS{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.randbelow(1000):03d}"
    
    # Hash password
    hashed_password = hash_password(passenger_data.password)
    
    # Create user
    user = User(
        phone=phone,
        name=passenger_data.name,
        user_type="passenger",
        password_hash=hashed_password,
        age=passenger_data.age
    )
    
    await db.users.insert_one(user.dict())
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(**user.dict()),
        "message": f"تم تسجيل الراكب بنجاح. رقم هاتفك للدخول: {phone}"
    }

@api_router.post("/register/driver", response_model=dict)
async def register_driver(driver_data: DriverCreate):
    # Check if phone number already exists
    existing_phone = await db.users.find_one({"phone": driver_data.phone})
    if existing_phone:
        raise HTTPException(status_code=400, detail="رقم الهاتف مسجل من قبل")
    
    # Check if car registration or operating number already exists
    existing_car = await db.users.find_one({
        "$or": [
            {"car_registration_number": driver_data.car_registration_number},
            {"operating_number": driver_data.operating_number}
        ]
    })
    if existing_car:
        raise HTTPException(status_code=400, detail="رقم تسجيل السيارة أو رقم التشغيل مستخدم من قبل")
    
    # Verify activation code
    activation_code = await db.activation_codes.find_one({
        "code": driver_data.activation_code,
        "is_used": False
    })
    
    if not activation_code:
        raise HTTPException(status_code=404, detail="كود التفعيل غير صحيح أو مستخدم من قبل")
    
    # Check if code is expired
    if datetime.utcnow() > activation_code["expires_at"]:
        raise HTTPException(status_code=400, detail="كود التفعيل منتهي الصلاحية")
    
    # Hash password
    hashed_password = hash_password(driver_data.password)
    
    # Create user (activated by default since code is provided)
    user = User(
        phone=driver_data.phone,
        name=driver_data.name,
        user_type="driver",
        password_hash=hashed_password,
        car_registration_number=driver_data.car_registration_number,
        operating_number=driver_data.operating_number,
        taxi_office_name=driver_data.taxi_office_name,
        taxi_office_phone=driver_data.taxi_office_phone,
        activation_code=driver_data.activation_code,
        is_activated=True,
        activation_expires=datetime.utcnow() + timedelta(days=30)
    )
    
    await db.users.insert_one(user.dict())
    
    # Mark activation code as used
    await db.activation_codes.update_one(
        {"id": activation_code["id"]},
        {"$set": {"is_used": True, "driver_phone": driver_data.phone}}
    )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(**user.dict()),
        "message": "تم تسجيل السائق وتفعيل الحساب بنجاح!"
    }

@api_router.post("/login", response_model=dict)
async def login(user_data: UserLogin):
    user = await db.users.find_one({"phone": user_data.phone})
    if not user or not verify_password(user_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="رقم هاتف أو كلمة مرور خاطئة")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["id"]}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(**user)
    }

@api_router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(**current_user.dict())

@api_router.post("/admin/generate-codes/{count}")
async def generate_activation_codes(count: int):
    """Generate activation codes in format 05XXXXX (admin endpoint)"""
    if count > 100:
        raise HTTPException(status_code=400, detail="Cannot generate more than 100 codes at once")
    
    codes = []
    existing_codes = set()
    
    # Get existing codes to avoid duplicates
    existing = await db.activation_codes.find({}, {"code": 1}).to_list(100000)
    existing_codes = {doc["code"] for doc in existing}
    
    for i in range(count):
        # Generate codes sequentially starting from unused numbers
        code_found = False
        for num in range(1, 100000):
            code = f"05{num:05d}"
            if code not in existing_codes:
                existing_codes.add(code)
                
                activation_code = ActivationCode(
                    code=code,
                    expires_at=datetime.utcnow() + timedelta(days=30)
                )
                
                await db.activation_codes.insert_one(activation_code.dict())
                codes.append(code)
                code_found = True
                break
        
        if not code_found:
            break
    
    return {"codes": codes, "count": len(codes), "expires_in_days": 30}

@api_router.get("/customer-service-info")
async def get_customer_service_info():
    """Get customer service contact information"""
    return {
        "phone": "0506511358",
        "message": "للحصول على كود التفعيل، يرجى الاتصال بخدمة العملاء"
    }

@api_router.post("/driver/location")
async def update_driver_location(location_data: dict, current_user: User = Depends(get_current_user)):
    if current_user.user_type != "driver":
        raise HTTPException(status_code=403, detail="Only drivers can update location")
    
    if not current_user.is_activated:
        raise HTTPException(status_code=403, detail="يجب تفعيل حسابك أولاً لبدء العمل")
    
    # Check if activation is still valid
    if current_user.activation_expires and datetime.utcnow() > current_user.activation_expires:
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"is_activated": False}}
        )
        raise HTTPException(status_code=403, detail="انتهت صلاحية التفعيل. يرجى تجديد الاشتراك")
    
    location = TaxiLocation(
        driver_id=current_user.id,
        latitude=location_data["latitude"],
        longitude=location_data["longitude"]
    )
    
    await db.taxi_locations.update_one(
        {"driver_id": current_user.id},
        {"$set": location.dict()},
        upsert=True
    )
    
    # Broadcast location update to all passengers
    await manager.broadcast(json.dumps({
        "type": "driver_location_update",
        "driver_id": current_user.id,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "driver_name": current_user.name
    }))
    
    return {"message": "Location updated successfully"}

@api_router.get("/taxis/nearby")
async def get_nearby_taxis(lat: float, lng: float, current_user: User = Depends(get_current_user)):
    # Get all available activated taxis
    taxis = await db.taxi_locations.find({"is_available": True}).to_list(100)
    
    # Add driver info and filter activated drivers only
    taxi_list = []
    for taxi in taxis:
        driver = await db.users.find_one({
            "id": taxi["driver_id"],
            "is_activated": True,
            "user_type": "driver"
        })
        if driver and (not driver.get("activation_expires") or datetime.utcnow() < driver["activation_expires"]):
            taxi_list.append({
                "id": taxi["id"],
                "driver_id": taxi["driver_id"],
                "driver_name": driver["name"],
                "latitude": taxi["latitude"],
                "longitude": taxi["longitude"],
                "updated_at": taxi["updated_at"]
            })
    
    return taxi_list

@api_router.post("/rides/request", response_model=dict)
async def request_ride(ride_data: RideRequestCreate, current_user: User = Depends(get_current_user)):
    if current_user.user_type != "passenger":
        raise HTTPException(status_code=403, detail="Only passengers can request rides")
    
    ride = RideRequest(
        passenger_id=current_user.id,
        **ride_data.dict()
    )
    
    await db.ride_requests.insert_one(ride.dict())
    
    # Notify all activated drivers about new ride request
    await manager.broadcast(json.dumps({
        "type": "new_ride_request",
        "ride_id": ride.id,
        "passenger_name": current_user.name,
        "pickup_latitude": ride.pickup_latitude,
        "pickup_longitude": ride.pickup_longitude,
        "pickup_address": ride.pickup_address,
        "passenger_count": ride.passenger_count,
        "has_luggage": ride.has_luggage
    }))
    
    return {"ride_id": ride.id, "message": "تم إرسال طلب الرحلة بنجاح"}

@api_router.post("/rides/{ride_id}/accept")
async def accept_ride(ride_id: str, current_user: User = Depends(get_current_user)):
    if current_user.user_type != "driver":
        raise HTTPException(status_code=403, detail="Only drivers can accept rides")
    
    if not current_user.is_activated:
        raise HTTPException(status_code=403, detail="يجب تفعيل حسابك أولاً لقبول الرحلات")
    
    # Update ride status
    result = await db.ride_requests.update_one(
        {"id": ride_id, "status": "pending"},
        {"$set": {"status": "accepted", "driver_id": current_user.id}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="الرحلة غير موجودة أو تم قبولها من قبل")
    
    # Update driver availability
    await db.taxi_locations.update_one(
        {"driver_id": current_user.id},
        {"$set": {"is_available": False}}
    )
    
    # Notify passenger
    ride = await db.ride_requests.find_one({"id": ride_id})
    passenger_websocket = manager.passenger_connections.get(ride["passenger_id"])
    if passenger_websocket:
        await manager.send_personal_message(json.dumps({
            "type": "ride_accepted",
            "driver_name": current_user.name,
            "driver_phone": current_user.phone,
            "car_registration": current_user.car_registration_number
        }), passenger_websocket)
    
    return {"message": "تم قبول الرحلة بنجاح"}

@api_router.get("/rides/my-rides")
async def get_my_rides(current_user: User = Depends(get_current_user)):
    if current_user.user_type == "passenger":
        rides = await db.ride_requests.find({"passenger_id": current_user.id}).to_list(100)
    else:
        rides = await db.ride_requests.find({"driver_id": current_user.id}).to_list(100)
    
    return rides

@api_router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, user_type: str):
    await manager.connect(websocket, user_id, user_type)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"Message received: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id, user_type)

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()