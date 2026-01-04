# Flask Backend Authentication Implementation for Chrome Extension
# This module provides extension authentication routes

import os
import secrets
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# In-memory storage for auth codes (use Redis in production)
# Format: { "code": { "user_id": "123", "expires_at": datetime, "used": False } }
AUTH_CODES = {}


def generate_jwt(user_id: str) -> str:
    """Generate a JWT token for the user."""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def _cleanup_expired_codes():
    """Remove expired authorization codes."""
    now = datetime.utcnow()
    expired_codes = [
        code for code, data in AUTH_CODES.items()
        if data["expires_at"] < now
    ]
    for code in expired_codes:
        del AUTH_CODES[code]


def register_extension_auth_routes(app):
    """Register extension authentication routes with the Flask app."""
    
    @app.route("/api/auth/extension/login", methods=["GET"])
    def extension_login():
        """
        Extension login initiation endpoint.
        Redirects to the webapp for user authentication.
        
        Query params: extension_id
        """
        from flask import redirect
        
        extension_id = request.args.get('extension_id')
        # Use AUTH_FRONTEND_URL for browser redirects (what user sees in browser)
        auth_frontend_url = os.getenv("AUTH_FRONTEND_URL", "http://localhost:3000")
        
        # Redirect to webapp's extension auth page
        redirect_url = f"{auth_frontend_url}/extension-auth?extension_id={extension_id}"
        return redirect(redirect_url)
    
    @app.route("/api/auth/generate-code", methods=["POST"])
    def generate_extension_code():
        """
        Generate a short-lived authorization code for extension authentication.
        Called by the web app after user logs in.
        
        Expects: Authorization header with web app session token
        Returns: { "code": "abc123..." }
        """
        # TODO: Verify the request is from your web app
        # For now, expecting user_id in request body
        data = request.get_json()
        user_id = data.get("user_id")
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        # Generate a secure random code
        code = secrets.token_urlsafe(32)
        
        # Store code with expiration (10 minutes)
        AUTH_CODES[code] = {
            "user_id": user_id,
            "expires_at": datetime.utcnow() + timedelta(minutes=10),
            "used": False
        }
        
        # Clean up expired codes
        _cleanup_expired_codes()
        
        return jsonify({"code": code}), 200

    @app.route("/api/auth/extension/exchange-code", methods=["POST"])
    def exchange_extension_code():
        """
        Exchange authorization code for JWT token.
        Called by the Chrome extension after receiving the code.
        
        Request: { "auth_code": "abc123..." }
        Response: { "jwt_token": "eyJ...", "user_id": "123" }
        """
        import requests
        
        data = request.get_json()
        auth_code = data.get("auth_code") if data else None
        
        if not auth_code:
            return jsonify({"error": "auth_code is required"}), 400
        
        # First, try local AUTH_CODES (for testing)
        code_data = AUTH_CODES.get(auth_code)
        
        if code_data:
            # Local code validation
            if code_data["used"]:
                return jsonify({"error": "Authorization code already used"}), 401
            
            if datetime.utcnow() > code_data["expires_at"]:
                del AUTH_CODES[auth_code]
                return jsonify({"error": "Authorization code has expired"}), 401
            
            # Mark code as used
            code_data["used"] = True
            user_id = code_data["user_id"]
            
            # Clean up the used code
            del AUTH_CODES[auth_code]
        else:
            # Code not found locally, try forwarding to AUTH backend
            auth_backend_url = os.getenv("AUTH_BACKEND_URL", "http://localhost:3000")
            
            try:
                # Forward the request to the auth backend
                response = requests.post(
                    f"{auth_backend_url}/api/auth/extension/exchange-code",
                    json={"auth_code": auth_code},
                    timeout=5
                )
                
                if response.status_code == 200:
                    # Auth backend validated the code successfully
                    response_data = response.json()
                    user_id = response_data.get("user_id")
                    
                    if not user_id:
                        return jsonify({"error": "Invalid response from auth backend"}), 500
                else:
                    # Auth backend rejected the code
                    error_data = response.json() if response.headers.get('content-type') == 'application/json' else {}
                    return jsonify({"error": error_data.get("error", "Invalid or expired authorization code")}), 401
                    
            except requests.exceptions.RequestException as e:
                return jsonify({"error": "Invalid or expired authorization code"}), 401
        
        # Generate JWT token with Flask backend's secret
        jwt_token = generate_jwt(user_id)
        
        return jsonify({
            "jwt_token": jwt_token,
            "user_id": user_id,
            "expires_in": JWT_EXPIRATION_HOURS * 3600  # seconds
        }), 200

    @app.route("/test/create-test-code", methods=["POST"])
    def create_test_code():
        """
        Development helper to create a test auth code without web app.
        Remove this in production!
        """
        code = secrets.token_urlsafe(32)
        test_user_id = "test_user_123"
        
        AUTH_CODES[code] = {
            "user_id": test_user_id,
            "expires_at": datetime.utcnow() + timedelta(minutes=10),
            "used": False
        }
        
        return jsonify({
            "code": code,
            "user_id": test_user_id,
            "redirect_url": f"chrome-extension://YOUR_EXTENSION_ID/auth-callback.html?code={code}",
            "message": "Use this code to test the extension authentication"
        }), 200

