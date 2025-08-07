from fastapi import FastAPI, APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timedelta
import bcrypt
import jwt
import json

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

class UserCreate(BaseModel):
    phone: str
    name: str
    user_type: str
    password: str

class UserLogin(BaseModel):
    phone: str
    password: str

class UserResponse(BaseModel):
    id: str
    phone: str
    name: str
    user_type: str
    is_active: bool

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
@api_router.post("/register", response_model=dict)
async def register(user_data: UserCreate):
    # Check if user already exists
    existing_user = await db.users.find_one({"phone": user_data.phone})
    if existing_user:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    
    # Hash password
    hashed_password = hash_password(user_data.password)
    
    # Create user
    user = User(
        phone=user_data.phone,
        name=user_data.name,
        user_type=user_data.user_type,
        password_hash=hashed_password
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
        "user": UserResponse(**user.dict())
    }

@api_router.post("/login", response_model=dict)
async def login(user_data: UserLogin):
    user = await db.users.find_one({"phone": user_data.phone})
    if not user or not verify_password(user_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid phone number or password")
    
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

@api_router.post("/driver/location")
async def update_driver_location(location_data: dict, current_user: User = Depends(get_current_user)):
    if current_user.user_type != "driver":
        raise HTTPException(status_code=403, detail="Only drivers can update location")
    
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
    # Get all available taxis (simplified - in production you'd use geospatial queries)
    taxis = await db.taxi_locations.find({"is_available": True}).to_list(100)
    
    # Add driver info
    taxi_list = []
    for taxi in taxis:
        driver = await db.users.find_one({"id": taxi["driver_id"]})
        if driver:
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
    
    # Notify all drivers about new ride request
    await manager.broadcast(json.dumps({
        "type": "new_ride_request",
        "ride_id": ride.id,
        "passenger_name": current_user.name,
        "pickup_latitude": ride.pickup_latitude,
        "pickup_longitude": ride.pickup_longitude,
        "pickup_address": ride.pickup_address
    }))
    
    return {"ride_id": ride.id, "message": "Ride request created successfully"}

@api_router.post("/rides/{ride_id}/accept")
async def accept_ride(ride_id: str, current_user: User = Depends(get_current_user)):
    if current_user.user_type != "driver":
        raise HTTPException(status_code=403, detail="Only drivers can accept rides")
    
    # Update ride status
    result = await db.ride_requests.update_one(
        {"id": ride_id, "status": "pending"},
        {"$set": {"status": "accepted", "driver_id": current_user.id}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Ride not found or already accepted")
    
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
            "driver_phone": current_user.phone
        }), passenger_websocket)
    
    return {"message": "Ride accepted successfully"}

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