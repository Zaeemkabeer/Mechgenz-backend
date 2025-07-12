# MECHGENZ Contact Form Backend

A FastAPI backend service for handling contact form submissions with MongoDB Atlas integration and Resend email reply functionality.

## Features

- **Dynamic Form Handling**: Accepts any JSON payload without strict schema validation
- **MongoDB Atlas Integration**: Stores submissions in MongoDB Atlas cloud database
- **Resend Email Integration**: Send professional replies directly to user's email address using Resend API
- **Admin Panel Support**: Full API support for admin panel functionality
- **CORS Support**: Configured for frontend integration
- **Admin Endpoints**: Retrieve and manage form submissions
- **Health Checks**: Monitor service and database connectivity
- **Error Handling**: Comprehensive error handling and logging
- **Statistics**: Get insights about form submissions

## Setup Instructions

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Environment Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` file and add your configurations:
```
MONGODB_CONNECTION_STRING=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
```

**Note**: The Resend API key is already configured in the code. The system uses:
- **Resend API Key**: `re_G4hUh9oq_Dcaj4qoYtfWWv5saNvgG7ZEW`
- **Company Email**: `mechgenz4@gmail.com`

### 3. Run the Server

```bash
# Development mode with auto-reload
python main.py

# Or using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: `http://localhost:8000`

## API Endpoints

### Public Endpoints

- `GET /` - Health check
- `GET /health` - Detailed health status
- `POST /api/contact` - Submit contact form

### Admin Endpoints

- `GET /api/submissions` - Get all submissions (with pagination)
- `PUT /api/submissions/{id}/status` - Update submission status
- `GET /api/stats` - Get submission statistics
- `POST /api/send-reply` - Send email reply to user using Resend

## Admin Panel Access

The admin panel is accessible at: `http://localhost:5173/admin`

**Login Credentials:**
- Email: `mechgenz4@gmail.com`
- Password: `mechgenz4`

## Email Reply System

The admin can reply to user inquiries directly from the admin panel. The system will:

1. Send a professional email reply to the user's original email address using Resend API
2. Include the original message for context
3. Update the inquiry status to "replied"
4. Use the official MECHGENZ email template with company branding
5. Send from `mechgenz4@gmail.com` using Resend's email service

### Email Features

- **Professional HTML Template**: Beautiful, responsive email design
- **Company Branding**: Includes MECHGENZ logo and company information
- **Original Message Context**: Shows the user's original inquiry
- **Contact Information**: Includes complete company contact details
- **Plain Text Fallback**: Ensures compatibility with all email clients

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Usage Examples

### Submit Contact Form

```javascript
const response = await fetch('http://localhost:8000/api/contact', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    name: 'John Doe',
    email: 'john@example.com',
    phone: '+974 1234 5678',
    message: 'Hello, I need more information about your services.'
  })
});

const result = await response.json();
console.log(result);
```

### Send Reply Email (Admin)

```javascript
const response = await fetch('http://localhost:8000/api/send-reply', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    to_email: 'user@example.com',
    to_name: 'John Doe',
    reply_message: 'Thank you for your inquiry. We will contact you soon.',
    original_message: 'Original user message here'
  })
});
```

## Database Structure

The service uses MongoDB with the following structure:

- **Database**: `MECHGENZ`
- **Collection**: `contact_submissions`

Each document contains:
- All form fields (dynamic)
- `submitted_at`: Timestamp
- `ip_address`: Client IP
- `user_agent`: Browser information
- `status`: Submission status ("new", "replied", etc.)
- `updated_at`: Last update timestamp (when status changes)

## Resend Email Configuration

The system is pre-configured with:
- **API Key**: `re_G4hUh9oq_Dcaj4qoYtfWWv5saNvgG7ZEW`
- **From Email**: `mechgenz4@gmail.com`
- **Professional HTML Templates**: Branded email design
- **Error Handling**: Comprehensive email delivery error handling

## Security Considerations

1. **CORS Configuration**: Update the allowed origins in `main.py` to match your frontend domains
2. **Environment Variables**: Never commit your `.env` file with real credentials
3. **API Key Security**: The Resend API key is embedded for demo purposes - consider using environment variables in production
4. **Rate Limiting**: Consider adding rate limiting for production use
5. **Authentication**: The admin panel uses simple authentication - enhance for production
6. **Input Validation**: Add additional validation as needed for your use case

## Deployment

For production deployment:

1. Set environment variables on your hosting platform
2. Update CORS origins to include your production domain
3. Consider using a production WSGI server like Gunicorn
4. Set up proper logging and monitoring
5. Configure SSL/TLS certificates
6. Use environment variables for sensitive data like API keys
7. Use a more robust authentication system for the admin panel

## Troubleshooting

### Common Issues

1. **MongoDB Connection Failed**
   - Check your connection string format
   - Ensure your IP is whitelisted in MongoDB Atlas
   - Verify username/password credentials

2. **Email Sending Failed**
   - Check the Resend API key is valid
   - Verify the from email domain is verified in Resend
   - Check Resend dashboard for delivery status

3. **CORS Errors**
   - Update the `allow_origins` list in the CORS middleware
   - Ensure your frontend URL is included

4. **Port Already in Use**
   - Change the port in `main.py` or kill the process using port 8000

### Logs

The application logs important events and errors. Check the console output for debugging information.

## Admin Panel Features

- **Dashboard**: Overview of inquiries and statistics
- **User Inquiries**: View, filter, and reply to customer inquiries
- **Email System**: Send professional replies directly to users using Resend
- **Status Management**: Track inquiry status (new, replied, etc.)
- **Responsive Design**: Works on desktop and mobile devices
- **Secure Login**: Protected admin access with credentials

## Resend Integration Benefits

- **Reliable Delivery**: High deliverability rates
- **Professional Templates**: Beautiful HTML email templates
- **Tracking**: Email delivery and engagement tracking
- **Scalable**: Handles high volume email sending
- **Easy Integration**: Simple API integration
- **Error Handling**: Comprehensive error reporting