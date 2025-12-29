import logging
import os
import time
from datetime import datetime
from typing import Any, Dict
from functools import wraps

from bson import ObjectId
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import jwt
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Configure CORS to allow requests from browser extensions and web pages
CORS(app, resources={
    r"/api/*": {
        "origins": ["*"],  # Allow all origins for development (restrict in production)
        "methods": ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": False,
        "max_age": 3600
    }
})

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
JWT_ALGORITHM = "HS256"

print("DB URL Loaded:", bool(os.getenv("DATABASE_URL")))


def get_db_connection(max_retries: int = 5, base_delay: float = 1.0):
    """Create a MongoDB database connection with automatic retry logic.

    Args:
        max_retries: Maximum number of connection attempts
        base_delay: Base delay between retries (exponential backoff)
        
    Returns:
        MongoDB database instance
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is required")
    db_name = os.getenv("MONGODB_DB_NAME", "cannerai_db")

    # MongoDB connection with retry logic
    for attempt in range(max_retries + 1):
        try:
            client = MongoClient(db_url, serverSelectionTimeoutMS=5000)
            
            # Test the connection
            client.admin.command('ping')
            
            # Get the database
            db = client[db_name]

            if attempt > 0:
                logging.info(
                    f"✅ MongoDB connection established after {attempt} retries"
                )
            return db

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            if attempt == max_retries:
                logging.error(
                    f"❌ Failed to connect to MongoDB after {max_retries} attempts: {e}"
                )
                raise

            delay = base_delay * (2**attempt)  # Exponential backoff
            logging.warning(
                f"⚠️  MongoDB connection attempt {attempt + 1} failed, retrying in {delay}s: {e}"
            )
            time.sleep(delay)


def init_db(max_retries: int = 10):
    """Initialize the database with required collections and indexes.

    Args:
        max_retries: Maximum number of initialization attempts
    """
    for attempt in range(max_retries + 1):
        try:
            db = get_db_connection()

            # Ensure canned_responses collection exists
            if 'canned_responses' not in db.list_collection_names():
                db.create_collection('canned_responses')
            
            # Ensure indexes exist
            collection = db['canned_responses']
            
            # Text index for full-text search
            try:
                collection.create_index(
                    [('title', TEXT), ('content', TEXT)],
                    name='idx_canned_responses_text_search',
                    weights={'title': 2, 'content': 1},
                    default_language='english'
                )
            except Exception:
                pass  # Index might already exist
            
            # Other indexes
            collection.create_index([('tags', ASCENDING)], name='idx_canned_responses_tags', background=True)
            collection.create_index([('user_id', ASCENDING)], name='idx_canned_responses_user_id', background=True)
            collection.create_index([('created_at', DESCENDING)], name='idx_canned_responses_created_at', background=True)
            collection.create_index([('updated_at', DESCENDING)], name='idx_canned_responses_updated_at', background=True)

            if attempt > 0:
                logging.info(
                    f"✅ Database initialized (MongoDB) after {attempt} retries"
                )
            else:
                logging.info("✅ Database initialized (MongoDB)")
            return

        except Exception as e:
            if attempt == max_retries:
                logging.error(
                    f"❌ Failed to initialize database after {max_retries} attempts: {e}"
                )
                raise

            delay = 2**attempt  # Exponential backoff
            logging.warning(
                f"⚠️  Database initialization attempt {attempt + 1} failed, retrying in {delay}s: {e}"
            )
            time.sleep(delay)


def dict_from_doc(doc) -> Dict[str, Any]:
    """Convert a MongoDB document to a dictionary."""
    tags = doc.get("tags", [])
    if tags is None:
        tags = []

    return {
        "id": str(doc["_id"]),  # ObjectId to string for JSON
        "title": doc["title"],
        "content": doc["content"],
        "tags": tags,
        "user_id": doc.get("user_id"),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None,
    }


# ==================== JWT Authentication ====================

def verify_jwt(token: str) -> dict:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


def require_auth(f):
    """Decorator to protect routes with JWT authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return jsonify({"error": "No authorization header"}), 401
        
        try:
            # Extract Bearer token
            token = auth_header.replace("Bearer ", "")
            payload = verify_jwt(token)
            
            # Add user info to request context
            request.user_id = payload["user_id"]
            
            return f(*args, **kwargs)
        except ValueError as e:
            return jsonify({"error": str(e)}), 401
    
    return decorated_function


# ==================== JWT Verification (Auth handled by FastAPI) ====================
# Flask only verifies JWT tokens - all auth logic is in FastAPI backend


# ==================== Protected Endpoints (Require JWT) ====================

@app.route("/api/templates", methods=["GET"])
@require_auth
def get_templates():
    """Get user-specific canned messages. Protected endpoint."""
    user_id = request.user_id
    search = request.args.get("search", "")

    db = get_db_connection()
    collection = db['canned_responses']

    # Filter by user_id
    base_query = {'user_id': user_id}

    if search:
        try:
            # Text search with user filter
            query = {**base_query, '$text': {'$search': search}}
            cursor = collection.find(query).sort('created_at', DESCENDING)
            responses = [dict_from_doc(doc) for doc in cursor]
        except Exception:
            # Fallback to regex
            query = {
                **base_query,
                '$or': [
                    {'title': {'$regex': search, '$options': 'i'}},
                    {'content': {'$regex': search, '$options': 'i'}},
                    {'tags': {'$regex': search, '$options': 'i'}}
                ]
            }
            cursor = collection.find(query).sort('created_at', DESCENDING)
            responses = [dict_from_doc(doc) for doc in cursor]
    else:
        cursor = collection.find(base_query).sort('created_at', DESCENDING)
        responses = [dict_from_doc(doc) for doc in cursor]

    return jsonify(responses)


@app.route("/api/responses", methods=["GET"])
@require_auth
def get_responses():
    """Get user-specific responses. Protected endpoint."""
    user_id = request.user_id
    search = request.args.get("search", "")

    db = get_db_connection()
    collection = db['canned_responses']

    # Filter by user_id
    base_query = {'user_id': user_id}

    if search:
        # MongoDB text search or regex for partial matching
        try:
            # Try text search first (faster with index)
            query = {**base_query, '$text': {'$search': search}}
            cursor = collection.find(query).sort('created_at', DESCENDING)
            responses = [dict_from_doc(doc) for doc in cursor]
        except Exception:
            # Fallback to regex if text index not available
            query = {
                **base_query,
                '$or': [
                    {'title': {'$regex': search, '$options': 'i'}},
                    {'content': {'$regex': search, '$options': 'i'}},
                    {'tags': {'$regex': search, '$options': 'i'}}
                ]
            }
            cursor = collection.find(query).sort('created_at', DESCENDING)
            responses = [dict_from_doc(doc) for doc in cursor]
    else:
        cursor = collection.find(base_query).sort('created_at', DESCENDING)
        responses = [dict_from_doc(doc) for doc in cursor]

    return jsonify(responses)


@app.route("/api/responses/<response_id>", methods=["GET"])
@require_auth
def get_response(response_id: str):
    """Get a single response by ID. Protected endpoint."""
    user_id = request.user_id
    db = get_db_connection()
    collection = db['canned_responses']

    try:
        doc = collection.find_one({'_id': ObjectId(response_id), 'user_id': user_id})
    except Exception:
        return jsonify({"error": "Invalid response ID"}), 400

    if not doc:
        return jsonify({"error": "Response not found"}), 404

    return jsonify(dict_from_doc(doc))


@app.route("/api/responses", methods=["POST"])
@require_auth
def create_response():
    """Create a new response. Protected endpoint."""
    user_id = request.user_id
    data = request.get_json()

    if not data or "title" not in data or "content" not in data:
        return jsonify({"error": "Title and content are required"}), 400

    title = data["title"]
    content = data["content"]
    tags = data.get("tags", [])

    db = get_db_connection()
    collection = db['canned_responses']

    now = datetime.utcnow()
    doc = {
        'title': title,
        'content': content,
        'tags': tags,
        'user_id': user_id,
        'created_at': now,
        'updated_at': now
    }
    
    result = collection.insert_one(doc)
    doc['_id'] = result.inserted_id

    return jsonify(dict_from_doc(doc)), 201


@app.route("/api/responses/<response_id>", methods=["PATCH"])
@require_auth
def update_response(response_id: str):
    """Update an existing response (partial update). Protected endpoint."""
    user_id = request.user_id
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    db = get_db_connection()
    collection = db['canned_responses']

    try:
        object_id = ObjectId(response_id)
    except Exception:
        return jsonify({"error": "Invalid response ID"}), 400

    # Check if response exists and belongs to user
    existing = collection.find_one({'_id': object_id, 'user_id': user_id})
    
    if not existing:
        return jsonify({"error": "Response not found"}), 404

    # Build update document
    update_fields = {'updated_at': datetime.utcnow()}

    if "title" in data:
        update_fields['title'] = data["title"]

    if "content" in data:
        update_fields['content'] = data["content"]

    if "tags" in data:
        update_fields['tags'] = data["tags"]

    # Update the document
    collection.update_one(
        {'_id': object_id},
        {'$set': update_fields}
    )
    
    # Fetch updated document
    doc = collection.find_one({'_id': object_id})

    return jsonify(dict_from_doc(doc))


@app.route("/api/responses/<response_id>", methods=["DELETE"])
@require_auth
def delete_response(response_id: str):
    """Delete a response. Protected endpoint."""
    user_id = request.user_id
    db = get_db_connection()
    collection = db['canned_responses']

    try:
        object_id = ObjectId(response_id)
    except Exception:
        return jsonify({"error": "Invalid response ID"}), 400

    result = collection.delete_one({'_id': object_id, 'user_id': user_id})
    
    if result.deleted_count == 0:
        return jsonify({"error": "Response not found"}), 404

    return "", 204


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint with database connectivity test."""
    try:
        # Test database connection
        db = get_db_connection(max_retries=1)  # Quick test, don't wait long
        db.command('ping')

        return jsonify(
            {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "database": "MongoDB",
                "database_connected": True,
            }
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "status": "unhealthy",
                    "timestamp": datetime.now().isoformat(),
                    "database": "MongoDB",
                    "database_connected": False,
                    "error": str(e),
                }
            ),
            503,
        )


# ==================== Gemini AI Response Generation ====================

def fetch_media_content(media_items: list, genai_module) -> list:
    """Fetch media content from URLs and prepare for Gemini multimodal input.
    
    Args:
        media_items: List of media objects with type, url, altText, title
        genai_module: The google.generativeai module for uploading files
        
    Returns:
        List of media objects ready for Gemini (PIL Images or uploaded file references)
    """
    import requests
    from PIL import Image
    from io import BytesIO
    import tempfile
    import os as os_module
    
    media_content = []
    
    for item in media_items[:5]:  # Limit to 5 media items to avoid token limits
        try:
            url = item.get("url", "")
            media_type = item.get("type", "image")
            
            if not url or url.startswith("data:"):
                continue
                
            logging.info(f"🖼️ Fetching {media_type}: {url[:80]}...")
            
            # Fetch the media
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "image/*, video/*, application/pdf, */*",
                "Referer": "https://www.linkedin.com/"
            }
            
            # For videos, use longer timeout and stream
            timeout = 60 if media_type == "video" else 15
            response = requests.get(url, headers=headers, timeout=timeout, stream=True)
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "")
            
            if media_type == "image" or "image" in content_type:
                # Load image using PIL
                img = Image.open(BytesIO(response.content))
                # Convert to RGB if necessary (for PNG with transparency)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                # Resize if too large (max 1024px on longest side)
                max_size = 1024
                if max(img.size) > max_size:
                    ratio = max_size / max(img.size)
                    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                media_content.append({
                    "type": "image",
                    "data": img,
                    "description": item.get("altText") or item.get("title") or "Image from post"
                })
                logging.info(f"✅ Image loaded: {img.size}")
                
            elif media_type == "video" or "video" in content_type:
                # Download video to temp file and upload to Gemini
                logging.info(f"🎬 Downloading video for analysis...")
                
                # Get content length to check video size (limit to ~50MB)
                content_length = int(response.headers.get("Content-Length", 0))
                max_video_size = 50 * 1024 * 1024  # 50MB
                
                if content_length > max_video_size:
                    logging.warning(f"⚠️ Video too large ({content_length / 1024 / 1024:.1f}MB), skipping")
                    media_content.append({
                        "type": "description",
                        "description": f"Video attached (too large to analyze: {content_length / 1024 / 1024:.1f}MB)"
                    })
                    continue
                
                # Determine file extension from content type
                ext = ".mp4"  # Default
                if "webm" in content_type:
                    ext = ".webm"
                elif "mov" in content_type or "quicktime" in content_type:
                    ext = ".mov"
                elif "avi" in content_type:
                    ext = ".avi"
                
                # Download to temp file
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    total_downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            tmp_file.write(chunk)
                            total_downloaded += len(chunk)
                            # Safety check - stop if exceeds limit
                            if total_downloaded > max_video_size:
                                break
                
                logging.info(f"✅ Video downloaded: {total_downloaded / 1024 / 1024:.2f}MB")
                
                try:
                    # Upload video to Gemini Files API
                    logging.info(f"📤 Uploading video to Gemini...")
                    video_file = genai_module.upload_file(
                        path=tmp_path,
                        mime_type=content_type or "video/mp4"
                    )
                    
                    # Wait for processing (Gemini needs to process the video)
                    import time
                    while video_file.state.name == "PROCESSING":
                        logging.info("⏳ Waiting for video processing...")
                        time.sleep(2)
                        video_file = genai_module.get_file(video_file.name)
                    
                    if video_file.state.name == "ACTIVE":
                        media_content.append({
                            "type": "video",
                            "data": video_file,  # Gemini file reference
                            "description": item.get("title") or "Video from post"
                        })
                        logging.info(f"✅ Video uploaded and ready for analysis")
                    else:
                        logging.warning(f"⚠️ Video processing failed: {video_file.state.name}")
                        media_content.append({
                            "type": "description",
                            "description": item.get("title") or "Video attached (processing failed)"
                        })
                        
                except Exception as upload_error:
                    logging.warning(f"⚠️ Video upload failed: {upload_error}")
                    media_content.append({
                        "type": "description",
                        "description": item.get("title") or "Video attached"
                    })
                finally:
                    # Clean up temp file
                    try:
                        os_module.unlink(tmp_path)
                    except:
                        pass
                
            elif media_type in ("pdf", "document"):
                # For PDFs, try to upload to Gemini as well
                logging.info(f"📄 Downloading document for analysis...")
                
                # Determine extension
                ext = ".pdf"
                if "doc" in content_type:
                    ext = ".docx"
                
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    tmp_file.write(response.content)
                
                try:
                    doc_file = genai_module.upload_file(
                        path=tmp_path,
                        mime_type=content_type or "application/pdf"
                    )
                    
                    # Wait for processing
                    import time
                    while doc_file.state.name == "PROCESSING":
                        logging.info("⏳ Waiting for document processing...")
                        time.sleep(1)
                        doc_file = genai_module.get_file(doc_file.name)
                    
                    if doc_file.state.name == "ACTIVE":
                        media_content.append({
                            "type": "document",
                            "data": doc_file,
                            "description": item.get("title") or "Document from post"
                        })
                        logging.info(f"✅ Document uploaded and ready for analysis")
                    else:
                        media_content.append({
                            "type": "description",
                            "description": item.get("title") or "Document attached"
                        })
                        
                except Exception as upload_error:
                    logging.warning(f"⚠️ Document upload failed: {upload_error}")
                    media_content.append({
                        "type": "description",
                        "description": item.get("title") or "Document attached"
                    })
                finally:
                    try:
                        os_module.unlink(tmp_path)
                    except:
                        pass
                
        except Exception as e:
            logging.warning(f"⚠️ Failed to fetch media {url[:50]}: {e}")
            # Still include the description if available
            if item.get("altText") or item.get("title"):
                media_content.append({
                    "type": "description",
                    "description": item.get("altText") or item.get("title")
                })
    
    return media_content


@app.route("/api/generate", methods=["POST"])
def generate_ai_response():
    """Generate AI response using Gemini Flash with multimodal support"""
    import google.generativeai as genai
    
    try:
        data = request.json
        text = data.get("text", "")
        context = data.get("context", [])
        media = data.get("media", [])  # NEW: Media items from frontend
        response_type = data.get("type", "comment")
        
        logging.info(f"📥 Generate request - Text: {len(text)} chars, Context items: {len(context)}, Media items: {len(media)}")
        if context:
            logging.info(f"📄 First context item preview: {context[0][:100]}...")
        if media:
            logging.info(f"🖼️ Media types: {[m.get('type') for m in media]}")
        
        # Get API key from environment
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"error": "GEMINI_API_KEY not configured"}), 500
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Use gemini-2.0-flash for multimodal (supports images/video)
        # Use gemini-1.5-flash as fallback for text-only (faster, cheaper)
        # Valid models: gemini-2.0-flash, gemini-1.5-flash, gemini-1.5-pro
        model_name = 'gemini-2.0-flash' if media else 'gemini-1.5-flash'
        model = genai.GenerativeModel(model_name)
        logging.info(f"🤖 Using model: {model_name}")
        
        # Fetch and prepare media content (pass genai for video/doc uploads)
        media_content = []
        if media:
            media_content = fetch_media_content(media, genai)
            logging.info(f"🖼️ Prepared {len(media_content)} media items for Gemini")
        
        # Build multimodal prompt parts
        prompt_parts = []
        
        # Build the text prompt
        if context and len(context) > 0:
            post_content = context[0]
            existing_comments = context[1:4] if len(context) > 1 else []
            
            # Add text prompt
            text_prompt = f"""You are writing a thoughtful, engaging comment on a LinkedIn post.

POST TEXT CONTENT:
{post_content}

"""
            # Add media descriptions to text prompt
            if media_content:
                text_prompt += "POST MEDIA/ATTACHMENTS:\n"
                for i, mc in enumerate(media_content, 1):
                    if mc["type"] == "description":
                        text_prompt += f"- {mc['description']}\n"
                    elif mc["type"] == "image":
                        text_prompt += f"- [Image {i}] {mc.get('description', 'See attached image')}\n"
                    elif mc["type"] == "video":
                        text_prompt += f"- [Video] {mc.get('description', 'Video content attached')}\n"
                    elif mc["type"] == "document":
                        text_prompt += f"- [Document/PDF] {mc.get('description', 'Document attached')}\n"
                text_prompt += "\n"
            
            text_prompt += f"""{"EXISTING COMMENTS:" if existing_comments else ""}
{chr(10).join(f"- {c}" for c in existing_comments) if existing_comments else ""}

{"USER'S DRAFT (optional):" + text if text else ""}

TASK:
Write ONE natural, professional LinkedIn comment (2-3 sentences, max 40 words).
- Be genuine and specific to THIS post
- Show you understood BOTH the text AND any images/videos/documents
- If there's a VIDEO: mention specific scenes, actions, or key moments you observed
- If there's an IMAGE: reference specific visual elements (colors, charts, infographics, people, etc.)
- If there's a DOCUMENT/PDF: reference specific content or insights from it
- Add value (insight, question, or encouragement)
- Use casual professional tone
- NO dashes, bullets, or "Great post!" generic phrases

Also provide 3 different variations as follow-up suggestions.

Return ONLY this JSON format:
{{"reply": "your specific comment here", "suggestions": [{{"label": "Ask question", "example": "question-based version"}}, {{"label": "Add insight", "example": "version with insight"}}, {{"label": "Shorter", "example": "brief version"}}]}}"""
        else:
            text_prompt = f"""You are improving a social media message.

USER'S TEXT: {text if text else "(empty - write something engaging)"}

TASK:
Write a short, natural, engaging message (max 40 words).
Also provide 3 variation suggestions.

Return ONLY this JSON:
{{"reply": "improved message", "suggestions": [{{"label": "Friendlier", "example": "friendly version"}}, {{"label": "Professional", "example": "professional version"}}, {{"label": "Shorter", "example": "brief version"}}]}}"""
        
        # Build the content parts for Gemini
        content_parts = []
        
        # Add media files first (Gemini prefers media before text)
        for mc in media_content:
            if mc["type"] == "image" and "data" in mc:
                content_parts.append(mc["data"])  # PIL Image object
            elif mc["type"] == "video" and "data" in mc:
                content_parts.append(mc["data"])  # Gemini uploaded file reference
            elif mc["type"] == "document" and "data" in mc:
                content_parts.append(mc["data"])  # Gemini uploaded file reference
        
        # Add the text prompt
        content_parts.append(text_prompt)
        
        logging.info(f"🤖 Calling Gemini with {len(content_parts)} content parts (media + text)...")
        
        # Call Gemini with multimodal content
        if len(content_parts) > 1:
            # Multimodal request (images + text)
            response = model.generate_content(content_parts)
        else:
            # Text-only request
            response = model.generate_content(text_prompt)
        
        response_text = response.text.strip()
        
        logging.info(f"✅ Gemini response received: {len(response_text)} chars")
        
        # Clean response (remove markdown code blocks if present)
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        # Parse JSON
        import json
        result = json.loads(response_text)
        
        logging.info(f"📤 Sending reply: {result.get('reply', '')[:50]}...")
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"❌ Gemini API error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ==================== Extension Authentication Routes ====================
# Import and register extension authentication endpoints
from extension_auth import register_extension_auth_routes
register_extension_auth_routes(app)

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Show which database we're using
    db_url = os.getenv("DATABASE_URL", "mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?appName=Cluster0")
    db_name = os.getenv("MONGODB_DB_NAME", "cannerai_db")
    # Mask password in logs for security
    safe_url = db_url.split('@')[0].split(':')[0:2] if '@' in db_url else db_url
    logging.info(f"🔧 Using MongoDB Atlas cluster")
    logging.info(f"🔧 Database: {db_name}")

    try:
        # Initialize database with retry logic
        logging.info("🔄 Initializing database...")
        init_db()

        logging.info("🚀 Starting Flask server on http://0.0.0.0:5000")
        app.run(debug=True, host="0.0.0.0", port=5000)

    except Exception as e:
        logging.error(f"❌ Failed to start application: {e}")
        exit(1)
