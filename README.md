# Fan Dub Backend

FastAPI backend for managing movies, clip scenes, and video storage with MongoDB and Cloudflare R2.

## Architecture

```
Routes (API Endpoints)
    ↓
Controllers (Business Logic)
    ↓
Services (R2 Storage, etc.)
    ↓
Database (MongoDB + Motor async driver)
    ↓
Audit Logs (Operation Tracking)
```

## Project Structure

```
app/
├── config/                  # Configuration
│   ├── __init__.py
│   ├── settings.py         # Environment variables with Pydantic
│   └── database.py         # MongoDB async connection
├── models/                  # Pydantic models
│   ├── __init__.py
│   ├── user.py            # User authentication models
│   ├── audit_log.py       # Audit log models
│   └── flow_model.py      # Reference flow model
├── controllers/             # Business logic
│   ├── __init__.py
│   ├── auth_controller.py        # Authentication & JWT
│   ├── audit_log_controller.py   # Audit log operations
│   └── flow_controller.py        # Reference flow controller
├── routes/                  # API endpoints
│   ├── __init__.py
│   ├── auth_routes.py      # Login endpoint
│   └── audit_log_routes.py # Audit log endpoints
├── utils/                   # Utilities
│   ├── __init__.py
│   └── logger.py          # Centralized logging
├── services/               # External services
│   ├── __init__.py
│   └── r2_storage_service.py  # Cloudflare R2 video storage
├── scripts/                # Utility scripts
│   └── test_r2_connection.py  # Test R2 configuration
├── main.py                 # FastAPI application
└── __init__.py
```

## Features

- **User Authentication**: Login with email and password
- **Video Storage**: Upload and manage videos using Cloudflare R2
- **Movie Management**: CRUD operations for movies and sagas
- **Clip Scenes**: Manage scene clips with video uploads
- **Transcriptions**: Handle scene transcriptions
- **JWT Tokens**: Secure token-based authentication
- **MongoDB Integration**: Async database operations with Motor
- **Audit Logging**: Track all login operations
- **Structured Logging**: Centralized logger with extra data support
- **JSON Responses**: Standardized response format across API
- **PEP8 Compliance**: Code follows Python style guidelines
- **English Documentation**: All docstrings in English

## Installation

### 1. Clone repository

```bash
git clone <repo-url>
cd fan-dub-backend
```

### 2. Create virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
# Copy and edit .env file
cp .env.example .env
```

Edit `.env` with your configuration:
- MongoDB connection
- JWT secret key
- Cloudinary credentials (for images)
- **Cloudflare R2 credentials (for videos)** - See [CLOUDFLARE_R2_SETUP.md](CLOUDFLARE_R2_SETUP.md)

### 5. Test R2 Connection (Optional)

```bash
python app/scripts/test_r2_connection.py
```

Edit `.env` with your values:

```env
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=fan_dub_db
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8000"]
APP_NAME=Fan Dub Backend
APP_VERSION=1.0.0
DEBUG=False
```

### 5. Start MongoDB

```bash
# With Docker (recommended)
docker run -d -p 27017:27017 --name mongodb mongo

# Or install MongoDB locally
# https://www.mongodb.com/try/download/community
```

### 6. Run application

```bash
# Development (with auto-reload)
uvicorn app.main:app --reload

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API Documentation

The API will be available at: `http://localhost:8000`

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## API Endpoints

### Health Check

- `GET /` - Root health check
- `GET /health` - Application health status

### Authentication

- `POST /auth/login` - User login (returns JWT token)

### Audit Logs

- `GET /audit/logs/user/{user_id}` - Get logs for specific user (requires authentication)
- `GET /audit/logs` - Get all system logs (requires authentication)

## Response Format

All API responses follow this format:

```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "email": "user@example.com",
    "created_at": "2024-01-20T10:30:00"
  },
  "log": "User user@example.com authenticated successfully"
}
```

## Database Collections

### users

```json
{
  "_id": ObjectId,
  "email": "user@example.com",
  "password_hash": "$2b$12$...",
  "created_at": ISODate
}
```

### audit_logs

```json
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "user_email": "user@example.com",
  "action": "LOGIN",
  "status": "SUCCESS",
  "details": {
    "ip": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
  },
  "created_at": ISODate
}
```

## Development

### Code Quality

- **Linting**: Code follows PEP8 standards
- **Type Hints**: All functions have proper type annotations
- **Documentation**: All functions have English docstrings
- **Logging**: All operations are logged with structured data

### Adding New Endpoints

1. Create model in `app/models/`
2. Create controller in `app/controllers/`
3. Create routes in `app/routes/`
4. Import and register router in `app/main.py`
5. Create corresponding audit logs if needed

## Testing

```bash
# Run with pytest
pytest

# Run with coverage
pytest --cov=app tests/
```

## Technologies

- **FastAPI**: Modern web framework
- **Motor**: Async MongoDB driver
- **PyJWT**: JWT token management
- **Passlib + Bcrypt**: Password hashing
- **Pydantic**: Data validation
- **Python Logging**: Structured logging

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `DATABASE_NAME` | `fan_dub_db` | Database name |
| `SECRET_KEY` | `your-secret-key-change-in-production` | JWT secret key |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token expiration time |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |
| `DEBUG` | `False` | Debug mode |

## License

MIT License - See LICENSE file for details

## Support

For issues and questions, please open an issue on GitHub.
