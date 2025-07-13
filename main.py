from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, PyMongoError
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from bson import ObjectId
from pathlib import Path
import os
from dotenv import load_dotenv
import logging
import resend
import json
import uuid
import hashlib
import shutil
import base64

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB connection
MONGODB_CONNECTION_STRING = os.getenv("MONGODB_CONNECTION_STRING")

DATABASE_NAME = "MECHGENZ"
COLLECTION_NAME = "contact_submissions"
GALLERY_COLLECTION_NAME = "website_images"
ADMIN_COLLECTION_NAME = "admin_users"

# Resend configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "re_G4hUh9oq_Dcaj4qoYtfWWv5saNvgG7ZEW")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "mechgenz4@gmail.com")
COMPANY_EMAIL = os.getenv("COMPANY_EMAIL", "info@mechgenz.com")
VERIFIED_DOMAIN = os.getenv("VERIFIED_DOMAIN", None)

# Email notification list - both admin Gmail and company Outlook
NOTIFICATION_EMAILS = [ADMIN_EMAIL, COMPANY_EMAIL]

# Initialize Resend
resend.api_key = RESEND_API_KEY

# File upload configuration
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
IMAGES_DIR = Path("images")
IMAGES_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx", ".txt"}

# Global MongoDB client
mongodb_client = None
database = None
collection = None
gallery_collection = None
admin_collection = None
is_db_connected = False

def hash_password(password: str) -> str:
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return hash_password(password) == hashed

def initialize_gallery_data():
    """Initialize gallery collection with default website images"""
    global gallery_collection
    
    try:
        if gallery_collection is None:
            return False
            
        # Check if gallery data already exists
        existing_count = gallery_collection.count_documents({})
        if existing_count > 0:
            logger.info(f"Gallery collection already has {existing_count} images")
            return True
            
        logger.info("Initializing gallery collection with default images...")
        
        # Default gallery images configuration (11 images with 9 categories)
        default_images = [
            {
                "id": "hero_main_banner",
                "name": "Main Hero Banner",
                "description": "Primary hero banner displayed on the homepage",
                "current_url": "https://images.pexels.com/photos/1108101/pexels-photo-1108101.jpeg",
                "default_url": "https://images.pexels.com/photos/1108101/pexels-photo-1108101.jpeg",
                "locations": ["Homepage Hero", "Main Banner"],
                "recommended_size": "1920x1080",
                "category": "hero",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "id": "about_company_image",
                "name": "About Company Image",
                "description": "Image representing our company and values",
                "current_url": "https://images.pexels.com/photos/3184291/pexels-photo-3184291.jpeg",
                "default_url": "https://images.pexels.com/photos/3184291/pexels-photo-3184291.jpeg",
                "locations": ["About Page", "Company Section"],
                "recommended_size": "800x600",
                "category": "about",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "id": "services_trading",
                "name": "Trading Services",
                "description": "Image showcasing our trading and contracting services",
                "current_url": "https://images.pexels.com/photos/906494/pexels-photo-906494.jpeg",
                "default_url": "https://images.pexels.com/photos/906494/pexels-photo-906494.jpeg",
                "locations": ["Services Page", "Trading Section"],
                "recommended_size": "600x400",
                "category": "services",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "id": "services_contracting",
                "name": "Contracting Services",
                "description": "Image representing our contracting and construction services",
                "current_url": "https://images.pexels.com/photos/1216589/pexels-photo-1216589.jpeg",
                "default_url": "https://images.pexels.com/photos/1216589/pexels-photo-1216589.jpeg",
                "locations": ["Services Page", "Contracting Section"],
                "recommended_size": "600x400",
                "category": "services",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "id": "portfolio_project_1",
                "name": "Featured Project 1",
                "description": "Showcase of our premium project work",
                "current_url": "https://images.pexels.com/photos/323780/pexels-photo-323780.jpeg",
                "default_url": "https://images.pexels.com/photos/323780/pexels-photo-323780.jpeg",
                "locations": ["Portfolio Page", "Featured Projects"],
                "recommended_size": "800x600",
                "category": "portfolio",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "id": "portfolio_project_2",
                "name": "Featured Project 2",
                "description": "Another example of our quality work",
                "current_url": "https://images.pexels.com/photos/2219024/pexels-photo-2219024.jpeg",
                "default_url": "https://images.pexels.com/photos/2219024/pexels-photo-2219024.jpeg",
                "locations": ["Portfolio Page", "Featured Projects"],
                "recommended_size": "800x600",
                "category": "portfolio",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "id": "contact_office_image",
                "name": "Office Location",
                "description": "Image of our office location in Doha",
                "current_url": "https://images.pexels.com/photos/380769/pexels-photo-380769.jpeg",
                "default_url": "https://images.pexels.com/photos/380769/pexels-photo-380769.jpeg",
                "locations": ["Contact Page", "Office Section"],
                "recommended_size": "600x400",
                "category": "contact",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "id": "team_leadership",
                "name": "Leadership Team",
                "description": "Photo representing our leadership and management team",
                "current_url": "https://images.pexels.com/photos/3184338/pexels-photo-3184338.jpeg",
                "default_url": "https://images.pexels.com/photos/3184338/pexels-photo-3184338.jpeg",
                "locations": ["About Page", "Team Section"],
                "recommended_size": "800x600",
                "category": "team",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "id": "logo_main",
                "name": "MECHGENZ Logo",
                "description": "Main company logo for branding",
                "current_url": "https://images.pexels.com/photos/3184465/pexels-photo-3184465.jpeg",
                "default_url": "https://images.pexels.com/photos/3184465/pexels-photo-3184465.jpeg",
                "locations": ["Header", "Footer", "All Pages"],
                "recommended_size": "300x100",
                "category": "branding",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "id": "testimonials_background",
                "name": "Testimonials Background",
                "description": "Background image for customer testimonials section",
                "current_url": "https://images.pexels.com/photos/3184339/pexels-photo-3184339.jpeg",
                "default_url": "https://images.pexels.com/photos/3184339/pexels-photo-3184339.jpeg",
                "locations": ["Homepage", "Testimonials Section"],
                "recommended_size": "1200x800",
                "category": "testimonials",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "id": "trading_machinery",
                "name": "Trading Machinery",
                "description": "Heavy machinery and equipment trading showcase",
                "current_url": "https://images.pexels.com/photos/1108099/pexels-photo-1108099.jpeg",
                "default_url": "https://images.pexels.com/photos/1108099/pexels-photo-1108099.jpeg",
                "locations": ["Trading Page", "Machinery Section"],
                "recommended_size": "800x600",
                "category": "trading",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        # Insert all default images
        result = gallery_collection.insert_many(default_images)
        logger.info(f"✅ Successfully initialized gallery with {len(result.inserted_ids)} images")
        
        # Create indexes for better performance
        gallery_collection.create_index("id", unique=True)
        gallery_collection.create_index("category")
        gallery_collection.create_index("updated_at")
        
        logger.info("✅ Gallery database indexes created")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error initializing gallery data: {e}")
        return False

def initialize_default_admin():
    """Initialize default admin if none exists"""
    global admin_collection
    
    try:
        if admin_collection is None:
            return False
            
        # Check if any admin exists
        existing_admin = admin_collection.find_one({})
        if existing_admin:
            logger.info("Admin user already exists")
            # Update existing admin with correct credentials if needed
            if existing_admin.get("email") != "mechgenz4@gmail.com" or not verify_password("mechgenz4", existing_admin.get("password", "")):
                logger.info("Updating admin credentials to match requirements...")
                admin_collection.update_one(
                    {"_id": existing_admin["_id"]},
                    {
                        "$set": {
                            "name": "Mechgenz",
                            "email": "mechgenz4@gmail.com",
                            "password": hash_password("mechgenz4"),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                logger.info("✅ Admin credentials updated")
            return True
            
        logger.info("Creating default admin user...")
        
        # Create default admin with the requested credentials
        default_admin = {
            "name": "Mechgenz",
            "email": "mechgenz4@gmail.com",
            "password": hash_password("mechgenz4"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = admin_collection.insert_one(default_admin)
        logger.info(f"✅ Default admin created with ID: {result.inserted_id}")
        logger.info("Default login: mechgenz4@gmail.com / mechgenz4")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating default admin: {e}")
        return False

def connect_to_mongodb():
    """Initialize MongoDB connection"""
    global mongodb_client, database, collection, gallery_collection, admin_collection, is_db_connected
    
    try:
        if not MONGODB_CONNECTION_STRING:
            logger.error("MongoDB connection string not found in environment variables")
            logger.info("Please create a .env file in the backend directory with MONGODB_CONNECTION_STRING")
            return False
        
        logger.info("Attempting to connect to MongoDB...")
        mongodb_client = MongoClient(MONGODB_CONNECTION_STRING)
        
        # Test the connection
        mongodb_client.admin.command('ping')
        logger.info("Successfully connected to MongoDB Atlas")
        
        # Get database and collections
        database = mongodb_client[DATABASE_NAME]
        collection = database[COLLECTION_NAME]
        gallery_collection = database[GALLERY_COLLECTION_NAME]
        admin_collection = database[ADMIN_COLLECTION_NAME]
        is_db_connected = True
        
        logger.info(f"Database: {DATABASE_NAME}, Collections: {COLLECTION_NAME}, {GALLERY_COLLECTION_NAME}, {ADMIN_COLLECTION_NAME}")
        
        # Initialize gallery data if empty
        initialize_gallery_data()
        
        # Initialize default admin if none exists
        initialize_default_admin()
        
        return True
        
    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        is_db_connected = False
        return False
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {e}")
        is_db_connected = False
        return False

def close_mongodb_connection():
    """Close MongoDB connection"""
    global mongodb_client, is_db_connected
    if mongodb_client:
        mongodb_client.close()
        is_db_connected = False
        logger.info("MongoDB connection closed")

def format_file_size(bytes_size):
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    logger.info("Starting up MECHGENZ Contact Form API...")
    logger.info(f"📧 Email configuration:")
    logger.info(f"   Admin Email: {ADMIN_EMAIL}")
    logger.info(f"   Company Email: {COMPANY_EMAIL}")
    logger.info(f"   Notification Recipients: {', '.join(NOTIFICATION_EMAILS)}")
    
    success = connect_to_mongodb()
    if not success:
        logger.warning("Failed to initialize MongoDB connection - API will run but form submissions will fail")
        logger.info("To fix this:")
        logger.info("1. Create a .env file in the backend directory")
        logger.info("2. Add your MongoDB connection string: MONGODB_CONNECTION_STRING=your_connection_string")
        logger.info("3. Restart the server")
    else:
        logger.info("✅ Gallery management system ready")
        logger.info("✅ Admin system ready")
        logger.info("✅ Dual email notification system ready")
        logger.info("✅ File upload system ready")
    
    yield
    
    # Shutdown
    close_mongodb_connection()

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="MECHGENZ Contact Form API",
    description="Backend API for handling contact form submissions with file uploads and gallery management",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files for image and upload serving
app.mount("/images", StaticFiles(directory="images"), name="images")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Get CORS origins from environment variable
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "Content-Range", "Access-Control-Expose-Headers"]
)

# Add a middleware to include proper headers for admin panels
@app.middleware("http")
async def add_cors_and_pagination_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Add CORS headers
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count, Content-Range"
    
    return response

# Health check endpoint
@app.get("/")
async def root():
    """Root endpoint for health check"""
    return {
        "message": "MECHGENZ Contact Form API is running",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database_connected": is_db_connected,
        "email_config": {
            "admin_email": ADMIN_EMAIL,
            "company_email": COMPANY_EMAIL,
            "notification_recipients": NOTIFICATION_EMAILS
        }
    }

@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    try:
        # Test MongoDB connection
        if mongodb_client and is_db_connected:
            mongodb_client.admin.command('ping')
            db_status = "connected"
        else:
            db_status = "disconnected"
        
        return {
            "status": "healthy",
            "database": db_status,
            "timestamp": datetime.utcnow().isoformat(),
            "mongodb_configured": MONGODB_CONNECTION_STRING is not None,
            "resend_configured": RESEND_API_KEY is not None,
            "email_setup": {
                "admin_email": ADMIN_EMAIL,
                "company_email": COMPANY_EMAIL,
                "dual_notifications": True
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# ============================================================================
# ADMIN PROFILE ENDPOINTS
# ============================================================================

@app.get("/api/admin/profile")
async def get_admin_profile():
    """Get admin profile information"""
    try:
        if not is_db_connected or admin_collection is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        
        # Get the first (and should be only) admin user
        admin = admin_collection.find_one({})
        if not admin:
            raise HTTPException(
                status_code=404,
                detail="Admin profile not found"
            )
        
        # Remove sensitive data
        admin_data = {
            "name": admin.get("name", ""),
            "email": admin.get("email", ""),
            "created_at": admin.get("created_at", "").isoformat() if admin.get("created_at") else "",
            "updated_at": admin.get("updated_at", "").isoformat() if admin.get("updated_at") else ""
        }
        
        return {
            "success": True,
            "admin": admin_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching admin profile: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch admin profile"
        )

@app.put("/api/admin/profile")
async def update_admin_profile(request: Request):
    """Update admin profile information"""
    try:
        if not is_db_connected or admin_collection is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        
        # Get request data
        data = await request.json()
        name = data.get("name", "").strip()
        email = data.get("email", "").strip()
        current_password = data.get("currentPassword", "")
        new_password = data.get("password", "")
        
        # Validate required fields
        if not name:
            raise HTTPException(
                status_code=400,
                detail="Name is required"
            )
        
        if not email:
            raise HTTPException(
                status_code=400,
                detail="Email is required"
            )
        
        # Get current admin
        admin = admin_collection.find_one({})
        if not admin:
            raise HTTPException(
                status_code=404,
                detail="Admin profile not found"
            )
        
        # Prepare update data
        update_data = {
            "name": name,
            "email": email,
            "updated_at": datetime.utcnow()
        }
        
        # If password change is requested, verify current password and update
        if new_password:
            if not current_password:
                raise HTTPException(
                    status_code=400,
                    detail="Current password is required to change password"
                )
            
            # Verify current password
            if not verify_password(current_password, admin.get("password", "")):
                raise HTTPException(
                    status_code=400,
                    detail="Current password is incorrect"
                )
            
            # Add new password to update data
            update_data["password"] = hash_password(new_password)
        
        # Update admin profile
        result = admin_collection.update_one(
            {"_id": admin["_id"]},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to update admin profile"
            )
        
        # Return updated admin data (without password)
        updated_admin = {
            "name": update_data["name"],
            "email": update_data["email"],
            "updated_at": update_data["updated_at"].isoformat()
        }
        
        logger.info(f"Admin profile updated successfully")
        
        return {
            "success": True,
            "message": "Profile updated successfully",
            "admin": updated_admin
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating admin profile: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update admin profile"
        )

@app.post("/api/admin/login")
async def admin_login(request: Request):
    """Admin login endpoint"""
    try:
        if not is_db_connected or admin_collection is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        
        data = await request.json()
        email = data.get("email", "").strip()
        password = data.get("password", "")
        
        if not email or not password:
            raise HTTPException(
                status_code=400,
                detail="Email and password are required"
            )
        
        # Find admin by email
        admin = admin_collection.find_one({"email": email})
        if not admin:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )
        
        # Verify password
        if not verify_password(password, admin.get("password", "")):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )
        
        # Return success (in a real app, you'd return a JWT token)
        return {
            "success": True,
            "message": "Login successful",
            "admin": {
                "name": admin.get("name", ""),
                "email": admin.get("email", "")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during admin login: {e}")
        raise HTTPException(
            status_code=500,
            detail="Login failed"
        )

# ============================================================================
# FILE UPLOAD AND SERVING ENDPOINTS
# ============================================================================

@app.get("/api/submissions/{submission_id}/file/{filename}")
async def download_file(submission_id: str, filename: str):
    """Download a file attached to a submission"""
    try:
        if not is_db_connected or collection is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        
        # Verify submission exists and contains this file
        submission = collection.find_one({"_id": ObjectId(submission_id)})
        if not submission:
            raise HTTPException(
                status_code=404,
                detail="Submission not found"
            )
        
        # Check if file exists in submission
        uploaded_files = submission.get("uploaded_files", [])
        file_info = None
        for file_data in uploaded_files:
            if file_data.get("saved_name") == filename:
                file_info = file_data
                break
        
        if not file_info:
            raise HTTPException(
                status_code=404,
                detail="File not found in submission"
            )
        
        # Check if physical file exists
        file_path = UPLOAD_DIR / filename
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Physical file not found"
            )
        
        # Return file
        return FileResponse(
            path=file_path,
            filename=file_info.get("original_name", filename),
            media_type=file_info.get("content_type", "application/octet-stream")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to download file"
        )

# ============================================================================
# CONTACT FORM ENDPOINTS WITH FILE UPLOAD SUPPORT
# ============================================================================

async def send_notification_email(form_data, uploaded_files=None):
    """Send notification email to both admin and company when a new contact form is submitted"""
    try:
        # Create attachments list if files were uploaded
        attachments = []
        attachment_html = ""
        
        if uploaded_files and len(uploaded_files) > 0:
            attachment_html = f"""
            <div style="background-color: #e8f5e8; padding: 20px; border-left: 4px solid #4caf50; margin: 20px 0; border-radius: 5px;">
                <h3 style="color: #2e7d32; margin-top: 0; display: flex; align-items: center;">
                    <span style="font-size: 20px; margin-right: 8px;">📎</span>
                    Attachments ({len(uploaded_files)})
                </h3>
                <p style="color: #2e7d32; margin-bottom: 15px;">The following files have been attached to this inquiry:</p>
                <div style="background-color: white; padding: 15px; border-radius: 5px; border: 1px solid #c8e6c9;">
            """
            
            for file_info in uploaded_files:
                file_path = UPLOAD_DIR / file_info["saved_name"]
                if file_path.exists():
                    file_size = file_info["file_size"]
                    
                    # Only attach files smaller than 5MB to avoid email size limits
                    if file_size < 5 * 1024 * 1024:  # 5MB limit
                        try:
                            # Read file content for attachment
                            with open(file_path, "rb") as f:
                                file_content = f.read()
                            
                            # Encode file content as base64 for Resend
                            file_content_b64 = base64.b64encode(file_content).decode('utf-8')
                            
                            # Add to Resend attachments
                            attachments.append({
                                "filename": file_info["original_name"],
                                "content": file_content_b64,
                                "content_type": file_info.get("content_type", "application/octet-stream")
                            })
                            
                            # Add to HTML display
                            attachment_html += f"""
                            <div style="display: flex; align-items: center; margin-bottom: 10px; padding: 8px; background-color: #f8f9fa; border-radius: 4px;">
                                <span style="font-size: 16px; margin-right: 10px;">📄</span>
                                <div>
                                    <strong style="color: #2e7d32;">{file_info["original_name"]}</strong>
                                    <br><small style="color: #666;">({format_file_size(file_info["file_size"])}) - Attached</small>
                                </div>
                            </div>
                            """
                        except Exception as file_error:
                            logger.error(f"Error reading file {file_info['saved_name']}: {file_error}")
                            # Add to HTML display as link instead
                            attachment_html += f"""
                            <div style="display: flex; align-items: center; margin-bottom: 10px; padding: 8px; background-color: #fff3cd; border-radius: 4px;">
                                <span style="font-size: 16px; margin-right: 10px;">📄</span>
                                <div>
                                    <strong style="color: #856404;">{file_info["original_name"]}</strong>
                                    <br><small style="color: #666;">({format_file_size(file_info["file_size"])}) - Available in admin panel</small>
                                </div>
                            </div>
                            """
                    else:
                        # File too large - show as link only
                        attachment_html += f"""
                        <div style="display: flex; align-items: center; margin-bottom: 10px; padding: 8px; background-color: #fff3cd; border-radius: 4px;">
                            <span style="font-size: 16px; margin-right: 10px;">📄</span>
                            <div>
                                <strong style="color: #856404;">{file_info["original_name"]}</strong>
                                <br><small style="color: #666;">({format_file_size(file_info["file_size"])}) - Too large for email, available in admin panel</small>
                            </div>
                        </div>
                        """
            
            attachment_html += """
                </div>
            </div>
            """
        
        # Create email content for notification (matching the design from the image)
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>New Contact Form Submission - MECHGENZ</title>
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 0;
                    background-color: #f4f4f4;
                }}
                .email-container {{
                    background-color: #ffffff;
                    margin: 0;
                    padding: 0;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #ff5722 0%, #ff7043 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .logo {{
                    font-size: 28px;
                    font-weight: bold;
                    letter-spacing: 2px;
                    margin-bottom: 5px;
                }}
                .tagline {{
                    font-size: 12px;
                    letter-spacing: 3px;
                    opacity: 0.9;
                }}
                .alert {{
                    background-color: #fff3e0;
                    color: #ff5722;
                    padding: 20px;
                    margin: 0;
                    text-align: center;
                    font-weight: bold;
                    border-left: 4px solid #ff5722;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .alert-icon {{
                    font-size: 20px;
                    margin-right: 10px;
                }}
                .content {{
                    padding: 30px;
                }}
                .info-text {{
                    color: #666;
                    margin-bottom: 20px;
                    font-size: 14px;
                }}
                .contact-section {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                .contact-title {{
                    color: #ff5722;
                    font-size: 18px;
                    font-weight: bold;
                    margin-bottom: 15px;
                    display: flex;
                    align-items: center;
                }}
                .contact-title-icon {{
                    margin-right: 8px;
                    font-size: 20px;
                }}
                .contact-row {{
                    display: flex;
                    margin-bottom: 12px;
                    align-items: flex-start;
                }}
                .contact-label {{
                    font-weight: bold;
                    color: #333;
                    min-width: 80px;
                    margin-right: 10px;
                }}
                .contact-value {{
                    color: #666;
                    flex: 1;
                }}
                .message-section {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                .message-title {{
                    color: #ff5722;
                    font-size: 18px;
                    font-weight: bold;
                    margin-bottom: 15px;
                    display: flex;
                    align-items: center;
                }}
                .message-title-icon {{
                    margin-right: 8px;
                    font-size: 20px;
                }}
                .message-content {{
                    background-color: white;
                    padding: 15px;
                    border-radius: 5px;
                    border-left: 4px solid #ff5722;
                    white-space: pre-wrap;
                    color: #333;
                }}
                .action-buttons {{
                    text-align: center;
                    margin: 30px 0;
                }}
                .btn {{
                    display: inline-block;
                    padding: 12px 24px;
                    margin: 8px;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: bold;
                    color: white;
                    font-size: 14px;
                }}
                .btn-primary {{
                    background-color: #ff5722;
                }}
                .btn-secondary {{
                    background-color: #2196f3;
                }}
                .footer {{
                    background-color: #37474f;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    font-size: 12px;
                    line-height: 1.4;
                }}
                .footer p {{
                    margin: 5px 0;
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <div class="logo">MECHGENZ</div>
                    <div class="tagline">TRADING CONTRACTING AND SERVICES</div>
                </div>
                
                <div class="alert">
                    <span class="alert-icon">🔔</span>
                    New Contact Form Submission
                </div>
                
                <div class="content">
                    <p class="info-text">You have received a new inquiry through the website contact form.</p>
                    
                    <div class="contact-section">
                        <div class="contact-title">
                            <span class="contact-title-icon">📋</span>
                            Contact Information
                        </div>
                        
                        <div class="contact-row">
                            <div class="contact-label">Name:</div>
                            <div class="contact-value">{form_data.get('name', 'Not provided')}</div>
                        </div>
                        
                        <div class="contact-row">
                            <div class="contact-label">Email:</div>
                            <div class="contact-value">{form_data.get('email', 'Not provided')}</div>
                        </div>
                        
                        <div class="contact-row">
                            <div class="contact-label">Phone:</div>
                            <div class="contact-value">{form_data.get('phone', 'Not provided')}</div>
                        </div>
                        
                        <div class="contact-row">
                            <div class="contact-label">Submitted:</div>
                            <div class="contact-value">{datetime.utcnow().strftime('%B %d, %Y at %I:%M %p')} UTC</div>
                        </div>
                    </div>
                    
                    <div class="message-section">
                        <div class="message-title">
                            <span class="message-title-icon">💬</span>
                            Message
                        </div>
                        <div class="message-content">{form_data.get('message', 'Not provided')}</div>
                    </div>
                    
                    {attachment_html}
                    
                    <div class="action-buttons">
                        <a href="http://localhost:5173/admin/user-inquiries" class="btn btn-primary">
                            🖥️ View in Admin Panel
                        </a>
                        <a href="mailto:{form_data.get('email', '')}?subject=Re: Your inquiry to MECHGENZ" class="btn btn-secondary">
                            ↩️ Reply Directly
                        </a>
                    </div>
                </div>
                
                <div class="footer">
                    <p>This is an automated notification from your MECHGENZ website contact form.</p>
                    <p>© 2024 MECHGENZ W.L.L. All Rights Reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Send notification email to BOTH admin Gmail and company Outlook
        params = {
            "from": "MECHGENZ Website <info@mechgenz.com>",
            "to": NOTIFICATION_EMAILS,
            "subject": f"🔔 New Contact Form Submission from {form_data.get('name', 'Unknown')}",
            "html": html_content,
            "reply_to": form_data.get('email', COMPANY_EMAIL)
        }
        
        # Add attachments if any (and not too large)
        if attachments:
            params["attachments"] = attachments
        
        logger.info(f"📧 Sending notification email to: {', '.join(NOTIFICATION_EMAILS)}")
        if attachments:
            logger.info(f"📎 Including {len(attachments)} attachments (files under 5MB)")
        elif uploaded_files:
            logger.info(f"📎 {len(uploaded_files)} files uploaded but not attached (too large or error)")
        
        email_response = resend.Emails.send(params)
        logger.info(f"✅ Dual notification email sent successfully!")
        logger.info(f"   - Admin Gmail: {ADMIN_EMAIL}")
        logger.info(f"   - Company Outlook: {COMPANY_EMAIL}")
        logger.info(f"   - Resend ID: {email_response.get('id', 'Unknown')}")
        
        return {
            "success": True,
            "sent_to": NOTIFICATION_EMAILS,
            "resend_id": email_response.get('id'),
            "attachments_included": len(attachments) if attachments else 0
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to send dual notification email: {e}")
        return {
            "success": False,
            "error": str(e),
            "attempted_recipients": NOTIFICATION_EMAILS
        }

@app.post("/api/send-reply")
async def send_reply_email(request: Request):
    """Send email reply directly to user from admin"""
    try:
        logger.info("Received email reply request")
        
        # Get the JSON data from request
        email_data = await request.json()
        logger.info(f"Email data received: {email_data}")
        
        # Validate required fields
        required_fields = ['to_email', 'to_name', 'reply_message']
        for field in required_fields:
            if not email_data.get(field):
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required field: {field}"
                )
        
        to_email = email_data['to_email']
        to_name = email_data['to_name']
        reply_message = email_data['reply_message']
        original_message = email_data.get('original_message', '')
        
        # Create professional reply email content for the user
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Reply from MECHGENZ</title>
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f4f4f4;
                }}
                .email-container {{
                    background-color: #ffffff;
                    border-radius: 10px;
                    padding: 30px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    text-align: center;
                    border-bottom: 3px solid #ff5722;
                    padding-bottom: 20px;
                    margin-bottom: 30px;
                }}
                .logo {{
                    font-size: 28px;
                    font-weight: bold;
                    color: #ff5722;
                    letter-spacing: 2px;
                }}
                .tagline {{
                    font-size: 12px;
                    color: #666;
                    letter-spacing: 3px;
                    margin-top: 5px;
                }}
                .greeting {{
                    font-size: 18px;
                    color: #333;
                    margin-bottom: 20px;
                }}
                .reply-content {{
                    background-color: #f9f9f9;
                    padding: 20px;
                    border-left: 4px solid #ff5722;
                    margin: 20px 0;
                    border-radius: 5px;
                }}
                .original-message {{
                    background-color: #f0f0f0;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 20px 0;
                    border-left: 3px solid #ccc;
                }}
                .original-message h4 {{
                    color: #666;
                    margin-top: 0;
                    font-size: 14px;
                }}
                .contact-info {{
                    margin: 20px 0;
                    padding: 15px;
                    background-color: #f8f8f8;
                    border-radius: 5px;
                }}
                .contact-info h4 {{
                    color: #ff5722;
                    margin-top: 0;
                }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    text-align: center;
                    color: #666;
                    font-size: 14px;
                }}
                .signature {{
                    margin-top: 30px;
                    padding: 20px;
                    background-color: #ff5722;
                    color: white;
                    border-radius: 5px;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <div class="logo">MECHGENZ</div>
                    <div class="tagline">TRADING CONTRACTING AND SERVICES</div>
                </div>
                
                <div class="greeting">Dear {to_name},</div>
                
                <p>Thank you for contacting MECHGENZ Trading Contracting & Services. We appreciate your inquiry and are pleased to respond to your message.</p>
                
                <div class="reply-content">
                    <h3 style="color: #ff5722; margin-top: 0;">Our Response:</h3>
                    <p style="margin-bottom: 0; white-space: pre-line;">{reply_message}</p>
                </div>
                
                {f'''
                <div class="original-message">
                    <h4>Your Original Message:</h4>
                    <p style="margin-bottom: 0; font-style: italic; white-space: pre-line;">{original_message}</p>
                </div>
                ''' if original_message else ''}
                
                <p>If you have any further questions or need additional information, please don't hesitate to contact us. We look forward to the opportunity to work with you.</p>
                
                <div class="contact-info">
                    <h4>Contact Information</h4>
                    <p><strong>Office:</strong> Buzwair Complex, 4th Floor, Rawdat Al Khail St, Doha Qatar<br>
                    <strong>P.O. Box:</strong> 22911</p>
                    <p><strong>Phone:</strong> +974 30401080</p>
                    <p><strong>Email:</strong> info@mechgenz.com | mishal.basheer@mechgenz.com</p>
                    <p><strong>Website:</strong> www.mechgenz.com</p>
                    <p><strong>Managing Director:</strong> Mishal Basheer</p>
                </div>
                
                <div class="signature">
                    <p style="margin: 0;"><strong>Best Regards,<br>
                    MECHGENZ Team<br>
                    Trading Contracting and Services</strong></p>
                </div>
                
                <div class="footer">
                    <p>© 2024 MECHGENZ W.L.L. All Rights Reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Create plain text version
        text_content = f"""
        Dear {to_name},

        Thank you for contacting MECHGENZ Trading Contracting & Services. We appreciate your inquiry and are pleased to respond to your message.

        Our Response:
        {reply_message}

        {f"Your Original Message:\\n{original_message}\\n" if original_message else ""}

        If you have any further questions or need additional information, please don't hesitate to contact us. We look forward to the opportunity to work with you.

        Contact Information:
        Office: Buzwair Complex, 4th Floor, Rawdat Al Khail St, Doha Qatar
        P.O. Box: 22911
        Phone: +974 30401080
        Email: info@mechgenz.com | mishal.basheer@mechgenz.com
        Website: www.mechgenz.com
        Managing Director: Mishal Basheer

        Best Regards,
        MECHGENZ Team
        Trading Contracting and Services

        © 2024 MECHGENZ W.L.L. All Rights Reserved.
        """
        
        # Send email directly to the user using Resend
        logger.info(f"Sending reply email directly to user {to_name} ({to_email}) using Resend API")
        
        params = {
            "from": "MECHGENZ <info@mechgenz.com>",
            "to": [to_email],
            "subject": f"Reply from MECHGENZ - Your Inquiry",
            "html": html_content,
            "text": text_content,
            "reply_to": COMPANY_EMAIL
        }
        
        email_response = resend.Emails.send(params)
        logger.info(f"Resend API response: {email_response}")
        
        if email_response and email_response.get('id'):
            logger.info(f"Reply email sent successfully to {to_email}. Resend ID: {email_response['id']}")
            return {
                "success": True,
                "message": f"Reply sent successfully to {to_name} ({to_email})",
                "email_id": email_response['id'],
                "customer_email": to_email,
                "customer_name": to_name,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            logger.error(f"Failed to send reply email. Resend response: {email_response}")
            raise HTTPException(
                status_code=500,
                detail="Failed to send reply email. Please try again."
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending reply email: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send reply email: {str(e)}"
        )

@app.post("/api/contact")
async def submit_contact_form(
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    message: str = Form(...),
    files: List[UploadFile] = File(None)
):
    """Handle contact form submissions with optional file uploads"""
    try:
        logger.info("📝 Received contact form submission")
        
        # Check if database connection is available
        if not is_db_connected or collection is None:
            logger.error("Database connection not available")
            raise HTTPException(
                status_code=503, 
                detail="Database connection not available. Please check MongoDB configuration."
            )
        
        # Validate required fields
        if not name.strip():
            raise HTTPException(status_code=400, detail="Name is required")
        if not email.strip():
            raise HTTPException(status_code=400, detail="Email is required")
        if not message.strip():
            raise HTTPException(status_code=400, detail="Message is required")
        
        # Prepare form data
        form_data = {
            "name": name.strip(),
            "email": email.strip(),
            "phone": phone.strip() if phone else "",
            "message": message.strip()
        }
        
        logger.info(f"Form data: {form_data}")
        
        # Handle file uploads
        uploaded_files = []
        if files and len(files) > 0:
            logger.info(f"Processing {len(files)} uploaded files")
            
            for file in files:
                if file.filename and file.filename.strip():
                    # Validate file
                    file_extension = Path(file.filename).suffix.lower()
                    if file_extension not in ALLOWED_EXTENSIONS:
                        raise HTTPException(
                            status_code=400,
                            detail=f"File type '{file_extension}' not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
                        )
                    
                    # Read file content
                    file_content = await file.read()
                    file_size = len(file_content)
                    
                    if file_size > MAX_FILE_SIZE:
                        raise HTTPException(
                            status_code=400,
                            detail=f"File '{file.filename}' is too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
                        )
                    
                    if file_size == 0:
                        continue  # Skip empty files
                    
                    # Generate unique filename
                    unique_id = uuid.uuid4().hex[:8]
                    safe_filename = f"{unique_id}_{file.filename}"
                    file_path = UPLOAD_DIR / safe_filename
                    
                    # Save file to disk
                    with open(file_path, "wb") as buffer:
                        buffer.write(file_content)
                    
                    # Store file information
                    file_info = {
                        "original_name": file.filename,
                        "saved_name": safe_filename,
                        "file_size": file_size,
                        "content_type": file.content_type or "application/octet-stream"
                    }
                    uploaded_files.append(file_info)
                    
                    logger.info(f"✅ Saved file: {file.filename} -> {safe_filename} ({format_file_size(file_size)})")
        
        # Prepare submission data for database
        submission_data = {
            **form_data,
            "uploaded_files": uploaded_files,
            "submitted_at": datetime.utcnow(),
            "status": "new"
        }
        
        logger.info(f"Submission data to be stored: {submission_data}")
        
        # Store in MongoDB
        try:
            result = collection.insert_one(submission_data)
            logger.info(f"✅ Successfully stored submission with ID: {result.inserted_id}")
        except PyMongoError as e:
            logger.error(f"MongoDB error: {e}")
            # Clean up uploaded files if database save failed
            for file_info in uploaded_files:
                file_path = UPLOAD_DIR / file_info["saved_name"]
                if file_path.exists():
                    file_path.unlink()
            raise HTTPException(
                status_code=500,
                detail="Database error occurred while storing submission"
            )
        
        # Send dual notification email (to both admin and company) with attachments
        try:
            email_result = await send_notification_email(form_data, uploaded_files)
            if email_result.get("success"):
                logger.info(f"✅ Dual notification emails sent successfully to: {', '.join(email_result.get('sent_to', []))}")
                if email_result.get("attachments_included", 0) > 0:
                    logger.info(f"📎 {email_result['attachments_included']} attachments included in notification")
            else:
                logger.warning(f"⚠️ Email notification failed: {email_result.get('error')}")
        except Exception as e:
            logger.error(f"Failed to send notification email: {e}")
            # Don't fail the entire request if email fails
        
        return {
            "success": True,
            "message": "Contact form submitted successfully",
            "submission_id": str(result.inserted_id),
            "timestamp": datetime.utcnow().isoformat(),
            "files_uploaded": len(uploaded_files),
            "notifications_sent_to": NOTIFICATION_EMAILS
        }
        
    except HTTPException:
        raise
    except PyMongoError as e:
        logger.error(f"MongoDB error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while processing submission"
        )
    except Exception as e:
        logger.error(f"Unexpected error in submit_contact_form: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing your submission"
        )

@app.get("/api/submissions")
async def get_submissions(
    limit: Optional[int] = 50,
    skip: Optional[int] = 0,
    status: Optional[str] = None
):
    """Retrieve contact form submissions (for admin use)"""
    try:
        if not is_db_connected or collection is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        
        # Build query filter
        query_filter = {}
        if status:
            query_filter["status"] = status
        
        # Get submissions with pagination
        cursor = collection.find(query_filter).sort("submitted_at", -1).skip(skip).limit(limit)
        submissions = []
        
        for doc in cursor:
            # Convert ObjectId to string for JSON serialization
            doc["_id"] = str(doc["_id"])
            # Convert datetime to ISO string
            if "submitted_at" in doc:
                doc["submitted_at"] = doc["submitted_at"].isoformat()
            submissions.append(doc)
        
        # Get total count
        total_count = collection.count_documents(query_filter)
        
        return {
            "success": True,
            "submissions": submissions,
            "total_count": total_count,
            "returned_count": len(submissions),
            "skip": skip,
            "limit": limit
        }
        
    except HTTPException:
        raise
    except PyMongoError as e:
        logger.error(f"MongoDB error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while retrieving submissions"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred"
        )

@app.put("/api/submissions/{submission_id}/status")
async def update_submission_status(submission_id: str, request: Request):
    """Update the status of a specific submission"""
    try:
        if not is_db_connected or collection is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        
        # Get the new status from request body
        data = await request.json()
        new_status = data.get("status")
        
        if not new_status:
            raise HTTPException(
                status_code=400,
                detail="Status field is required"
            )
        
        # Update the submission
        result = collection.update_one(
            {"_id": ObjectId(submission_id)},
            {
                "$set": {
                    "status": new_status,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=404,
                detail="Submission not found"
            )
        
        return {
            "success": True,
            "message": "Submission status updated successfully",
            "submission_id": submission_id,
            "new_status": new_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating submission status: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while updating submission status"
        )

@app.delete("/api/submissions/{submission_id}")
async def delete_submission(submission_id: str):
    """Delete a specific submission and its associated files"""
    try:
        if not is_db_connected or collection is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        
        # Get submission first to check for files
        submission = collection.find_one({"_id": ObjectId(submission_id)})
        if not submission:
            raise HTTPException(
                status_code=404,
                detail="Submission not found"
            )
        
        # Delete associated files
        uploaded_files = submission.get("uploaded_files", [])
        for file_info in uploaded_files:
            file_path = UPLOAD_DIR / file_info["saved_name"]
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted file: {file_info['saved_name']}")
        
        # Delete submission from database
        result = collection.delete_one({"_id": ObjectId(submission_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete submission"
            )
        
        logger.info(f"Deleted submission {submission_id} and {len(uploaded_files)} associated files")
        
        return {
            "success": True,
            "message": "Submission deleted successfully",
            "submission_id": submission_id,
            "files_deleted": len(uploaded_files)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting submission: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while deleting submission"
        )

# ============================================================================
# GALLERY MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/website-images")
async def get_website_images():
    """Get all website images in format expected by admin panels"""
    try:
        if not is_db_connected or gallery_collection is None:
            logger.warning("Database not connected, returning empty gallery")
            return {
                "success": True,
                "images": {},
                "total_count": 0
            }
        
        logger.info("Fetching images from gallery collection...")
        
        # Fetch all images from database
        cursor = gallery_collection.find({})
        images = {}
        doc_count = 0
        processed_count = 0
        
        for doc in cursor:
            doc_count += 1
            logger.info(f"Processing document {doc_count}: {doc.get('id', 'NO_ID')}")
            
            # Check if the document has 'id' field
            image_id = doc.get("id")
            if not image_id:
                logger.warning(f"Document missing 'id' field, skipping: {list(doc.keys())}")
                continue
            
            try:
                # Convert MongoDB document to the expected format
                images[image_id] = {
                    "id": image_id,
                    "name": doc.get("name", "Unknown"),
                    "description": doc.get("description", "No description"),
                    "current_url": doc.get("current_url", ""),
                    "default_url": doc.get("default_url", ""),
                    "locations": doc.get("locations", []),
                    "recommended_size": doc.get("recommended_size", ""),
                    "category": doc.get("category", "other"),
                    "updated_at": datetime.utcnow().isoformat()
                }
                processed_count += 1
                logger.info(f"Successfully processed image: {image_id}")
                
            except Exception as doc_error:
                logger.error(f"Error processing document {image_id}: {doc_error}")
                continue
        
        logger.info(f"Processed {processed_count} out of {doc_count} documents")
        logger.info(f"Final images dict has {len(images)} items")
        
        return {
            "success": True,
            "images": images,
            "total_count": len(images)
        }
        
    except Exception as e:
        logger.error(f"Error fetching website images: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "images": {},
            "total_count": 0,
            "error": str(e)
        }

@app.get("/api/website-images/categories")
async def get_image_categories():
    """Get all unique image categories"""
    try:
        if not is_db_connected or gallery_collection is None:
            return {
                "success": True,
                "categories": ["hero", "about", "services", "portfolio", "contact", "team", "branding", "testimonials", "trading"]
            }
        
        # Get unique categories from database
        categories = gallery_collection.distinct("category")
        categories.sort()
        
        logger.info(f"Retrieved {len(categories)} image categories")
        
        return {
            "success": True,
            "categories": categories
        }
        
    except Exception as e:
        logger.error(f"Error fetching image categories: {e}")
        return {
            "success": True,
            "categories": ["hero", "about", "services", "portfolio", "contact", "team", "branding", "testimonials", "trading"]
        }

@app.post("/api/website-images/{image_id}/upload")
async def upload_image(image_id: str, file: UploadFile = File(...)):
    """Upload a new image for a specific image slot"""
    try:
        if not is_db_connected or gallery_collection is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        
        # Check if image exists
        existing_image = gallery_collection.find_one({"id": image_id})
        if not existing_image:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID '{image_id}' not found"
            )
        
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="No file provided"
            )
        
        # Check file extension
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: .jpg, .jpeg, .png, .gif, .webp"
            )
        
        # Read file content to check size
        file_content = await file.read()
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Generate unique filename
        unique_filename = f"{image_id}_{uuid.uuid4().hex[:8]}{file_extension}"
        file_path = IMAGES_DIR / unique_filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
        
        # Update database with new URL
        new_url = f"/images/{unique_filename}"
        update_result = gallery_collection.update_one(
            {"id": image_id},
            {
                "$set": {
                    "current_url": new_url,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if update_result.modified_count == 0:
            # Clean up uploaded file if database update failed
            if file_path.exists():
                file_path.unlink()
            raise HTTPException(
                status_code=500,
                detail="Failed to update image in database"
            )
        
        logger.info(f"Successfully uploaded image for {image_id}: {unique_filename}")
        
        return {
            "success": True,
            "message": "Image uploaded successfully",
            "image_id": image_id,
            "new_url": new_url,
            "filename": unique_filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to upload image"
        )

@app.put("/api/website-images/{image_id}")
async def update_image_metadata(image_id: str, request: Request):
    """Update image metadata (name and description)"""
    try:
        if not is_db_connected or gallery_collection is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        
        # Get request data
        data = await request.json()
        name = data.get("name", "").strip()
        description = data.get("description", "").strip()
        
        if not name:
            raise HTTPException(
                status_code=400,
                detail="Name is required"
            )
        
        # Update image metadata
        update_result = gallery_collection.update_one(
            {"id": image_id},
            {
                "$set": {
                    "name": name,
                    "description": description,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if update_result.matched_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID '{image_id}' not found"
            )
        
        logger.info(f"Updated metadata for image {image_id}")
        
        return {
            "success": True,
            "message": "Image metadata updated successfully",
            "image_id": image_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating image metadata: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update image metadata"
        )

@app.delete("/api/website-images/{image_id}/reset")
async def reset_image_to_default(image_id: str):
    """Reset image to its default URL"""
    try:
        if not is_db_connected or gallery_collection is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        
        # Get current image data
        image_doc = gallery_collection.find_one({"id": image_id})
        if not image_doc:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID '{image_id}' not found"
            )
        
        # Delete current uploaded file if it exists
        current_url = image_doc.get("current_url", "")
        if current_url.startswith("/images/"):
            file_path = IMAGES_DIR / current_url.replace("/images/", "")
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted uploaded file: {file_path}")
        
        # Reset to default URL
        default_url = image_doc["default_url"]
        update_result = gallery_collection.update_one(
            {"id": image_id},
            {
                "$set": {
                    "current_url": default_url,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if update_result.modified_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to reset image"
            )
        
        logger.info(f"Reset image {image_id} to default")
        
        return {
            "success": True,
            "message": "Image reset to default successfully",
            "image_id": image_id,
            "default_url": default_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting image: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to reset image"
        )

@app.delete("/api/website-images/{image_id}")
async def delete_image(image_id: str, delete_type: str = "image_only"):
    """Delete image (either just the uploaded file or the entire configuration)"""
    try:
        if not is_db_connected or gallery_collection is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        
        # Validate delete_type
        if delete_type not in ["image_only", "complete"]:
            raise HTTPException(
                status_code=400,
                detail="delete_type must be either 'image_only' or 'complete'"
            )
        
        # Get current image data
        image_doc = gallery_collection.find_one({"id": image_id})
        if not image_doc:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID '{image_id}' not found"
            )
        
        # Delete uploaded file if it exists
        current_url = image_doc.get("current_url", "")
        if current_url.startswith("/images/"):
            file_path = IMAGES_DIR / current_url.replace("/images/", "")
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted uploaded file: {file_path}")
        
        if delete_type == "image_only":
            # Reset to default URL
            default_url = image_doc["default_url"]
            update_result = gallery_collection.update_one(
                {"id": image_id},
                {
                    "$set": {
                        "current_url": default_url,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if update_result.modified_count == 0:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to reset image"
                )
            
            logger.info(f"Deleted custom image for {image_id}, reset to default")
            
            return {
                "success": True,
                "message": "Custom image deleted, reset to default",
                "image_id": image_id,
                "default_url": default_url
            }
        
        else:  # complete deletion
            # Remove entire image configuration
            delete_result = gallery_collection.delete_one({"id": image_id})
            
            if delete_result.deleted_count == 0:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to delete image configuration"
                )
            
            logger.info(f"Completely deleted image configuration for {image_id}")
            
            return {
                "success": True,
                "message": "Image configuration deleted completely",
                "image_id": image_id
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting image: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete image"
        )

# ============================================================================
# ENHANCED DEBUG ENDPOINTS
# ============================================================================

@app.get("/api/debug/status")
async def debug_status():
    """Comprehensive debug status endpoint"""
    try:
        status_info = {
            "api_status": "running",
            "timestamp": datetime.utcnow().isoformat(),
            "database_connected": is_db_connected,
            "mongodb_client_status": mongodb_client is not None,
            "collections_status": {
                "gallery_collection": gallery_collection is not None,
                "admin_collection": admin_collection is not None,
                "submissions_collection": collection is not None
            }
        }
        
        # Test MongoDB connection
        if mongodb_client and is_db_connected:
            try:
                mongodb_client.admin.command('ping')
                status_info["mongodb_ping"] = "success"
                
                # Count documents in each collection
                if gallery_collection:
                    status_info["gallery_count"] = gallery_collection.count_documents({})
                if admin_collection:
                    status_info["admin_count"] = admin_collection.count_documents({})
                if collection:
                    status_info["submissions_count"] = collection.count_documents({})
                    
            except Exception as e:
                status_info["mongodb_ping"] = f"failed: {str(e)}"
        else:
            status_info["mongodb_ping"] = "not connected"
            
        return status_info
        
    except Exception as e:
        return {
            "api_status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/api/debug/gallery-simple")
async def debug_gallery_simple():
    """Simple gallery debug without complex processing"""
    try:
        if not is_db_connected:
            return {
                "error": "Database not connected",
                "mongodb_connection_string_exists": MONGODB_CONNECTION_STRING is not None,
                "is_db_connected": is_db_connected
            }
            
        if gallery_collection is None:
            return {
                "error": "Gallery collection is None",
                "database_connected": is_db_connected
            }
            
        # Simple count
        count = gallery_collection.count_documents({})
        
        # Get first document as sample
        sample_doc = gallery_collection.find_one({})
        if sample_doc:
            sample_doc.pop("_id", None)
            
        return {
            "gallery_collection_exists": True,
            "document_count": count,
            "sample_document": sample_doc,
            "collection_name": GALLERY_COLLECTION_NAME
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "error_type": type(e).__name__
        }

# ============================================================================
# DEBUG ENDPOINTS
# ============================================================================

@app.get("/api/debug/admin")
async def debug_admin():
    """Debug admin data and password hashing"""
    try:
        if not is_db_connected or admin_collection is None:
            return {"error": "Database not connected"}
        
        # Get admin data
        admin = admin_collection.find_one({})
        if not admin:
            return {"error": "No admin found"}
        
        # Remove _id for cleaner output
        admin_data = dict(admin)
        admin_data.pop("_id", None)
        
        # Test password hashing
        test_passwords = ["admin123", "mechgenz4"]
        password_tests = {}
        
        stored_password = admin.get("password", "")
        
        for test_pwd in test_passwords:
            hashed = hash_password(test_pwd)
            matches = verify_password(test_pwd, stored_password)
            password_tests[test_pwd] = {
                "hashed": hashed,
                "matches_stored": matches
            }
        
        return {
            "admin_data": admin_data,
            "stored_password": stored_password,
            "password_tests": password_tests,
            "admin_collection_count": admin_collection.count_documents({}),
            "email_config": {
                "admin_email": ADMIN_EMAIL,
                "company_email": COMPANY_EMAIL,
                "notification_emails": NOTIFICATION_EMAILS
            }
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/debug/reset-admin-password")
async def reset_admin_password():
    """Reset admin password to 'mechgenz4'"""
    try:
        if not is_db_connected or admin_collection is None:
            return {"error": "Database not connected"}
        
        # Get admin
        admin = admin_collection.find_one({})
        if not admin:
            return {"error": "No admin found"}
        
        # Reset password to mechgenz4
        new_password = "mechgenz4"
        hashed_password = hash_password(new_password)
        
        # Update password
        result = admin_collection.update_one(
            {"_id": admin["_id"]},
            {
                "$set": {
                    "email": "mechgenz4@gmail.com",
                    "name": "Mechgenz",
                    "password": hashed_password,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            return {
                "success": True,
                "message": "Admin credentials set to mechgenz4@gmail.com / mechgenz4",
                "email": "mechgenz4@gmail.com",
                "new_password": new_password,
                "hashed_password": hashed_password
            }
        else:
            return {"error": "Failed to update password"}
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/debug/gallery")
async def debug_gallery():
    """Debug endpoint to check gallery data"""
    try:
        if not is_db_connected or gallery_collection is None:
            return {"error": "Database not connected", "gallery_collection": gallery_collection is None}
        
        # Get all images from database
        cursor = gallery_collection.find({})
        images = []
        
        for doc in cursor:
            doc.pop("_id", None)  # Remove MongoDB _id
            if "created_at" in doc and hasattr(doc["created_at"], 'isoformat'):
                doc["created_at"] = doc["created_at"].isoformat()
            if "updated_at" in doc and hasattr(doc["updated_at"], 'isoformat'):
                doc["updated_at"] = doc["updated_at"].isoformat()
            images.append(doc)
        
        return {
            "images_count": len(images),
            "images": images,
            "database_connected": is_db_connected,
            "collection_name": GALLERY_COLLECTION_NAME
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/debug/fix-missing-images")
async def fix_missing_images():
    """Fix missing image files by resetting them to defaults"""
    try:
        if not is_db_connected or gallery_collection is None:
            return {"error": "Database not connected"}
        
        fixed_count = 0
        missing_files = []
        
        # Get all gallery images
        cursor = gallery_collection.find({})
        
        for doc in cursor:
            current_url = doc.get("current_url", "")
            default_url = doc.get("default_url", "")
            image_id = doc.get("id", "")
            
            # Check if current_url points to a local file that doesn't exist
            if current_url.startswith("/images/"):
                filename = current_url.replace("/images/", "")
                file_path = IMAGES_DIR / filename
                
                if not file_path.exists():
                    # Reset to default URL
                    gallery_collection.update_one(
                        {"_id": doc["_id"]},
                        {
                            "$set": {
                                "current_url": default_url,
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )
                    fixed_count += 1
                    missing_files.append({
                        "image_id": image_id,
                        "missing_file": filename,
                        "reset_to": default_url
                    })
        
        return {
            "success": True,
            "fixed_count": fixed_count,
            "missing_files": missing_files,
            "message": f"Reset {fixed_count} images with missing files to their default URLs"
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/debug/reinitialize-gallery")
async def reinitialize_gallery():
    """Force reinitialize gallery data"""
    try:
        if gallery_collection is None:
            return {"error": "Gallery collection not available"}
        
        # Drop existing data
        gallery_collection.delete_many({})
        logger.info("Cleared existing gallery data")
        
        # Reinitialize
        success = initialize_gallery_data()
        
        return {
            "success": success,
            "message": "Gallery reinitialized" if success else "Failed to reinitialize"
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/debug/check-missing-files")
async def check_missing_files():
    """Check which image files are missing"""
    try:
        if not is_db_connected or gallery_collection is None:
            return {"error": "Database not connected"}
        
        missing_files = []
        existing_files = []
        
        # Get all gallery images
        cursor = gallery_collection.find({})
        
        for doc in cursor:
            current_url = doc.get("current_url", "")
            image_id = doc.get("id", "")
            
            if current_url.startswith("/images/"):
                filename = current_url.replace("/images/", "")
                file_path = IMAGES_DIR / filename
                
                if file_path.exists():
                    existing_files.append({
                        "image_id": image_id,
                        "filename": filename,
                        "size": file_path.stat().st_size
                    })
                else:
                    missing_files.append({
                        "image_id": image_id,
                        "filename": filename,
                        "current_url": current_url,
                        "default_url": doc.get("default_url", "")
                    })
        
        return {
            "missing_files_count": len(missing_files),
            "existing_files_count": len(existing_files),
            "missing_files": missing_files,
            "existing_files": existing_files
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/stats")
async def get_submission_stats():
    """Get statistics about form submissions"""
    try:
        if not is_db_connected or collection is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        
        # Get total submissions
        total_submissions = collection.count_documents({})
        
        # Get submissions by status
        pipeline = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        status_stats = list(collection.aggregate(pipeline))
        
        # Get submissions by date (last 30 days)
        from datetime import timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_submissions = collection.count_documents({
            "submitted_at": {"$gte": thirty_days_ago}
        })
        
        return {
            "success": True,
            "stats": {
                "total_submissions": total_submissions,
                "recent_submissions_30_days": recent_submissions,
                "status_breakdown": status_stats
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting submission stats: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while retrieving statistics"
        )

@app.get("/api/email-config")
async def get_email_configuration():
    """Get current email configuration"""
    return {
        "success": True,
        "configuration": {
            "admin_email": ADMIN_EMAIL,
            "company_email": COMPANY_EMAIL,
            "notification_recipients": NOTIFICATION_EMAILS,
            "dual_delivery_enabled": True,
            "verified_domain": VERIFIED_DOMAIN,
            "resend_configured": RESEND_API_KEY is not None
        }
    }

@app.get("/api/fix-images-now")
async def fix_images_now():
    """Quick fix for missing images"""
    try:
        if not is_db_connected or gallery_collection is None:
            return {"error": "Database not connected"}
        
        fixed_count = 0
        
        # Get all gallery images and fix missing ones
        cursor = gallery_collection.find({})
        
        for doc in cursor:
            current_url = doc.get("current_url", "")
            default_url = doc.get("default_url", "")
            
            # Check if current_url points to a local file that doesn't exist
            if current_url.startswith("/images/"):
                filename = current_url.replace("/images/", "")
                file_path = IMAGES_DIR / filename
                
                if not file_path.exists():
                    # Reset to default URL
                    gallery_collection.update_one(
                        {"_id": doc["_id"]},
                        {
                            "$set": {
                                "current_url": default_url,
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )
                    fixed_count += 1
        
        return {
            "success": True,
            "fixed_count": fixed_count,
            "message": f"Fixed {fixed_count} missing images"
        }
        
    except Exception as e:
        return {"error": str(e)}

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": "Endpoint not found",
            "message": "The requested endpoint does not exist"
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )