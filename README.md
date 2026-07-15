# NeoScape Properties - Room Booking Platform

A comprehensive Django REST Framework-based room booking backend system for NeoScape Properties, a modern villa and room reservation platform.

## Overview

NeoScape Properties is a full-featured room booking API that provides:
- Room management with advanced filtering
- Booking system with date validation
- JWT-based admin authentication
- RESTful API endpoints
- Image upload capabilities
- Admin dashboard statistics

## Features

### Core Functionality
- **Room Management**: Create, read, update, and delete room listings
- **Booking System**: Handle reservations with availability checking
- **Authentication**: JWT-based admin authentication with secure password hashing
- **Search & Filter**: Advanced filtering by location, price, amenities, dates, and guests
- **File Upload**: Image upload support for room photos
- **Admin Dashboard**: Statistics and analytics for bookings and revenue

### Security Features
- JWT token authentication
- Password hashing
- Input validation
- CORS configuration
- Protected admin routes

## Technology Stack

- **Framework**: Django 4.x
- **API**: Django REST Framework (DRF)
- **Authentication**: djangorestframework_simplejwt
- **Database**: PostgreSQL (via psycopg2-binary) / SQLite3 (development)
- **API Documentation**: drf-yasg (Swagger/OpenAPI)
- **Payment Integration**: sslcommerz-lib
- **Storage**: Supabase (storage3, supabase SDK)
- **Server**: Gunicorn (production)
- **Static Files**: WhiteNoise

## Installation

### Prerequisites
- Python 3.8 or higher
- pip
- Virtual environment (recommended)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/ejaz-uddin-swaron/room-booking.git
   cd room-booking
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   Create a `.env` file in the root directory:
   ```env
   # Database
   DATABASE_URL=your_database_connection_string
   
   # JWT
   JWT_SECRET=your_super_secret_jwt_key
   JWT_EXPIRES_IN=24h
   
   # Server
   PORT=3001
   DEBUG=True
   
   # CORS
   CORS_ORIGIN=http://localhost:3000
   
   # File Upload
   UPLOAD_DIR=uploads
   MAX_FILE_SIZE=5242880
   ALLOWED_FILE_TYPES=jpg,jpeg,png,webp
   
   # Admin Credentials
   DEFAULT_ADMIN_USERNAME=admin
   DEFAULT_ADMIN_PASSWORD=admin123
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser (optional)**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run development server**
   ```bash
   python manage.py runserver
   ```

The API will be available at `http://localhost:8000/`

## API Documentation

### Base URL
```
http://localhost:8000/api
```

### Authentication Endpoints

#### Admin Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123"
}
```

#### Verify Token
```http
GET /api/auth/verify
Authorization: Bearer <jwt_token>
```

### Room Endpoints

#### Get All Rooms
```http
GET /api/rooms?location=London&guests=2&min_price=100&max_price=300
```

#### Get Single Room
```http
GET /api/rooms/:id
```

#### Create Room (Admin Only)
```http
POST /api/rooms
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "name": "Luxury Ocean View Suite",
  "type": "Suite",
  "price": 250,
  "location": "London",
  "maxGuests": 4,
  "bedrooms": 2,
  "bathrooms": 2,
  "size": 85,
  "amenities": ["WiFi", "Pool", "Gym", "Spa"],
  "images": ["url1", "url2"],
  "description": "Beautiful suite",
  "available": true
}
```

#### Update Room (Admin Only)
```http
PUT /api/rooms/:id
Authorization: Bearer <jwt_token>
```

#### Delete Room (Admin Only)
```http
DELETE /api/rooms/:id
Authorization: Bearer <jwt_token>
```

### Booking Endpoints

#### Create Booking
```http
POST /api/bookings
Content-Type: application/json

{
  "roomId": "room_1",
  "checkIn": "2024-02-01",
  "checkOut": "2024-02-05",
  "guests": 2,
  "guestInfo": {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1234567890"
  }
}
```

#### Get All Bookings (Admin Only)
```http 
GET /api/bookings
Authorization: Bearer <jwt_token>
```

#### Update Booking Status (Admin Only)
```http
PATCH /api/bookings/:id/status
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "status": "confirmed"
}
```

### Statistics Endpoint

#### Get Admin Dashboard Stats
```http
GET /api/admin/stats
Authorization: Bearer <jwt_token>
```

For complete API documentation, see [API_DOCUMENTATION[1].md](./API_DOCUMENTATION[1].md)

## Project Structure

```
room-booking/
├── accounts/           # User authentication app
├── bookings/          # Booking management app
├── bookings_app/      # Additional booking features
├── core/              # Core project settings
├── rooms/             # Room management app
├── tools/             # Utility functions
├── manage.py          # Django management script
├── requirements.txt   # Python dependencies
├── db.sqlite3        # SQLite database (development)
└── api.ts            # TypeScript API client definitions
```

## Security

- JWT tokens for secure authentication
- Password hashing with bcrypt
- Input validation on all endpoints
- CORS configuration for frontend integration
- SQL injection prevention through Django ORM
- File upload validation (type and size)

## Testing

Run tests using:
```bash
python manage.py test
```

## Deployment

### Using Gunicorn

1. Install Gunicorn (already in requirements.txt)
2. Run with:
   ```bash
   gunicorn core.wsgi:application --bind 0.0.0.0:8000
   ```

### Environment Variables for Production
```env
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
DATABASE_URL=postgresql://user:password@host:port/dbname
```

## Database Schema

### Rooms Table
- id, name, type, price, rating, reviews
- images (JSON), amenities (JSON)
- description, location
- maxGuests, bedrooms, bathrooms, size
- available, created_at, updated_at

### Bookings Table
- id, room_id (FK), check_in, check_out
- guests, total_price, status
- guest_info (JSON)
- created_at, updated_at

### Admin Users Table
- id, username, password_hash
- role, created_at, updated_at

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Authors

- **Ejaz Uddin Swaron** - [@ejaz-uddin-swaron](https://github.com/ejaz-uddin-swaron)

## Acknowledgments

- Django REST Framework documentation
- NeoScape Properties design specifications
- Open source community

## Support

For support and queries:
- Open an issue in the repository
- Check the API documentation for detailed endpoint information
- Review the codebase for implementation details

## Version History

- **v1.0.0** - Initial release with core features
  - Room management
  - Booking system
  - JWT authentication
  - Admin dashboard

---

**Note**: This is a backend API server. For the complete application, you'll need to integrate with a frontend client. See the TypeScript API definitions in `api.ts` for frontend integration guidance.