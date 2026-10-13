# SmartEvent – Event Discovery & Ticket Booking System

SmartEvent is a **FastAPI-based backend API** for discovering events, booking tickets, managing events, processing payments, generating QR code tickets, and viewing booking analytics.

The system supports three user roles — **USER, ORGANIZER, and ADMIN** — with Role-Based Access Control (RBAC) to manage permissions and secure access to different features.

## 1. Features

### Authentication & Authorization
- User registration and login
- JWT-based authentication
- Password hashing and verification
- Role-Based Access Control (RBAC)
- Three roles: USER, ORGANIZER, and ADMIN
- Protected API endpoints

### Event Discovery & Management
- Browse available events
- Search events and filter by category
- Create, view, update, and cancel events
- Manage event details, locations, dates, and ticket prices
- Track event status: ACTIVE, CANCELLED, and COMPLETED
- Associate events with their organizers

### Ticket Booking
- Book tickets for available events
- View personal booking history
- Manage booking records
- Track ticket availability
- Generate QR code tickets
- Access ticket information

### Payment Integration
- Stripe Checkout integration
- Payment processing through Stripe
- Environment-based payment configuration
- Support for payment status management

### Organizer Dashboard & Analytics
- Create and manage organizer-owned events
- Update or cancel their own events
- View bookings for their own events
- Track total tickets sold
- Track remaining tickets
- Calculate event revenue
- View booking statistics

### Admin Dashboard & Analytics
- Manage users
- Manage platform events
- View and manage bookings
- Access platform-level analytics
- Monitor event and booking statistics

### Notifications
- Manage user notifications
- Access notification records through API endpoints

## 2. Tech Stack

| Component | Technology |
|---|---|
| Backend Framework | Python, FastAPI |
| Database | SQLite |
| ORM | SQLAlchemy |
| Authentication | JWT |
| Data Validation | Pydantic |
| Password Security | Password Hashing |
| Payment Gateway | Stripe |
| Ticket Generation | QR Codes |
| API Documentation | Swagger UI |
| Development Server | Uvicorn |
| API Testing | Swagger UI and available automated tests |

## 3. Project Structure

```text
smartevent-backend/
│
├── app/
│   ├── routers/
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── events.py
│   │   ├── bookings.py
│   │   ├── tickets.py
│   │   ├── notifications.py
│   │   ├── organizer.py
│   │   ├── admin.py
│   │   └── payments.py
│   │
│   ├── services/
│   │   └── stripe_service.py
│   │
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   └── database.py
│
├── qr_codes/
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

*Note: Adjust the structure above to match the actual files and folders in your project.*

## 4. Prerequisites

Make sure the following are installed:

- Python 3.10 or later
- pip
- Git (optional)
- A Stripe account for payment integration

## 5. Installation & Setup

### Step 1: Navigate to the project directory

Open PowerShell and execute:

```powershell
cd C:\smartevent-backend
```

### Step 2: Create a virtual environment

```powershell
python -m venv venv
```

### Step 3: Activate the virtual environment

```powershell
.\venv\Scripts\Activate.ps1
```

### Step 4: Install dependencies

```powershell
pip install -r requirements.txt
```

### Step 5: Configure environment variables

Create a `.env` file in the project root directory and configure the required settings.

Example:

```env
SECRET_KEY=your_secure_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
```

Replace the example values with your actual configuration. Use a strong secret key for JWT authentication and your Stripe test secret key during development.

**Security note:** Never commit your `.env` file or expose your JWT secret or Stripe secret key in a public repository. Ensure `.gitignore` excludes sensitive configuration files.

## 6. Run the Project

Start the FastAPI development server:

```powershell
uvicorn app.main:app --reload
```

The API should be available at:

- **Base URL:** http://127.0.0.1:8000
- **Swagger Documentation:** http://127.0.0.1:8000/docs
- **ReDoc Documentation:** http://127.0.0.1:8000/redoc
- **Health Check:** http://127.0.0.1:8000/health

The health-check URL is available only if the `/health` endpoint is registered in your application.

## 7. Main API Modules

| API Module | Description |
|---|---|
| `/auth` | User registration and authentication |
| `/users` | User-related operations |
| `/events` | Event discovery and management |
| `/bookings` | Ticket booking and booking history |
| `/tickets` | Ticket management and QR code functionality |
| `/notifications` | User notifications |
| `/payments` | Stripe Checkout integration |
| `/organizer` | Organizer event management and analytics |
| `/admin` | Administrative management and analytics |

*The listed prefixes represent the intended modules. Refer to Swagger UI for the exact endpoints registered in the application.*

## 8. User Roles & Permissions

### USER
- Browse and search events
- Filter events by category
- Book available tickets
- View personal booking history
- Access personal tickets and QR codes
- View personal notifications

### ORGANIZER
- Create new events
- Update and cancel their own events
- View and manage their own events
- View bookings associated with their events
- Monitor ticket sales and remaining tickets
- View event revenue and booking analytics

### ADMIN
- Manage users
- Manage platform events
- View and manage bookings
- Access administrative analytics
- Monitor overall platform activity

**Important:** Role permissions must be enforced by backend authorization checks, not just by hiding or displaying frontend pages.

## 9. Authentication Workflow

1. Register a user using the registration endpoint.
2. Log in with the registered credentials.
3. Obtain the JWT access token returned by the login endpoint.
4. Open Swagger UI at `/docs`.
5. Click the **Authorize** button.
6. Enter the access token in the format required by the configured authentication scheme.
7. Test protected endpoints according to the authenticated user's role.

## 10. Event Management Workflow

1. An organizer logs in to the system.
2. The organizer creates an event with its title, description, category, location, date, ticket price, and ticket quantity.
3. The backend associates the event with the organizer.
4. Users browse available events and book tickets.
5. Organizers view bookings and monitor ticket availability.
6. Organizers update or cancel their own events when permitted.
7. Administrators oversee platform-wide event management.

## 11. Ticket Booking & QR Code Workflow

1. The user selects an event.
2. The backend validates event availability and ticket quantity.
3. The user submits a booking request.
4. The system records the booking according to the implemented booking workflow.
5. A ticket and QR code are generated when the booking reaches the required status.
6. The user accesses their ticket and booking details.

The backend should validate ticket availability during booking to prevent overbooking and should restrict access to private ticket information.

## 12. Stripe Payment Workflow

1. The user initiates a booking or payment.
2. The backend validates the relevant booking information.
3. The payment endpoint creates a Stripe Checkout session.
4. The user completes payment through Stripe Checkout.
5. The backend verifies the payment status.
6. The booking and ticket status are updated according to the implemented payment workflow.

For production use, validate Stripe webhook signatures and verify payment events on the backend. Do not rely only on a browser redirect to confirm successful payment.

## 13. Organizer Analytics

The organizer dashboard is intended to provide the following metrics:

- **Total Tickets Sold:** Number of tickets sold for the organizer's events.
- **Remaining Tickets:** Tickets available for sale.
- **Total Revenue:** Revenue calculated from qualifying paid bookings.
- **Booking Count:** Number of bookings associated with the organizer's events.

Organizers should only be able to access analytics for events they own.

## 14. Admin Analytics

The admin dashboard is intended to provide an overview of platform activity, including:

- Total registered users
- Total events
- Total bookings
- Ticket sales
- Revenue statistics
- Event status distribution

Administrators should have access only through appropriately protected administrative endpoints.

## 15. Testing

Use Swagger UI to manually test API endpoints:

```text
http://127.0.0.1:8000/docs
```

If automated tests are included in the project, run:

```powershell
pytest
```

If pytest is not installed, install it using:

```powershell
pip install pytest
```

Test authentication, role permissions, event ownership, booking validation, ticket generation, and payment status handling.

## 16. Security & Best Practices

- Store secret keys and credentials in environment variables.
- Hash passwords before storing them.
- Validate request data with Pydantic schemas.
- Protect private endpoints using JWT authentication.
- Enforce role-based permissions on the backend.
- Ensure organizers can manage only their own events.
- Prevent ticket overbooking.
- Verify payment events securely.
- Exclude `.env` and other sensitive files from version control.
- Keep dependencies updated.
- Use appropriate error handling and logging.

## 17. Project Status

**Project:** SmartEvent – Event Discovery & Ticket Booking System

**Backend Framework:** FastAPI

**Architecture:** REST API with SQLAlchemy-based database access

**Phase 1 – Core Event & Booking System**
- User registration and login
- JWT authentication
- Event discovery and management
- Ticket booking
- QR code tickets
- Notifications
- Stripe Checkout integration

**Phase 2 – Role-Based Access & Analytics**
- USER, ORGANIZER, and ADMIN roles
- Role-based access control
- Organizer-owned event management
- Organizer booking insights
- Admin management and analytics

The project is structured to support these features. Actual implementation and testing status should be verified against the current source code before claiming that every feature is complete or production-ready.

## 18. Future Enhancements

- React frontend integration
- Interactive organizer and admin dashboards
- Advanced event search and filtering
- Email notifications
- Enhanced reporting and visualizations
- Automated testing and continuous integration
- Production database deployment
- Cloud deployment and monitoring

## Author

Developed as a full-stack event discovery and ticket-booking project using Python, FastAPI, SQLAlchemy, JWT authentication, and Stripe integration.

