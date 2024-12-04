# Automated SIP Caller with Django

A Django-based application for automated SIP calls with call recording and management capabilities. The system allows for automated outbound calling, call recording, and managing phone numbers through a web interface.

## Features

- Automated outbound SIP calling
- Call recording in WAV format
- Web interface for managing phone numbers and calls
- Queue-based call processing
- Celery-based task scheduling
- Real-time call status updates
- Docker support for easy deployment

## Prerequisites

- Python 3.8+
- Docker and Docker Compose
- PulseAudio (for audio processing)
- SIP account credentials

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yourusername/djangocalldidww1.git
cd djangocalldidww1
```

2. Create and configure `.env` file:
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Build and start the Docker containers:
```bash
docker-compose up -d
```

4. Access the web interface at `http://localhost:8000`

## Environment Variables

Key environment variables that need to be set in `.env`:

```
DJANGO_SETTINGS_MODULE=phone_tracker.settings
OPENAI_API_KEY=your_openai_api_key
LOCAL_IP=your_local_ip
SIP_USER=your_sip_username
SIP_DOMAIN=your_sip_domain
SIP_AUTH_REALM=your_sip_realm
SIP_AUTH_USERNAME=your_sip_auth_username
SIP_AUTH_PASSWORD=your_sip_password
```

## Project Structure

- `phone_numbers/` - Django app for phone number management
- `phone_tracker/` - Main Django project directory
- `recordings/` - Directory for storing call recordings
- `sip_caller.py` - Core SIP calling functionality
- `call_processor.py` - Call processing logic
- `docker-compose.yml` - Docker composition file
- `Dockerfile` - Docker image definition

## API Endpoints

The application provides a web interface for managing phone numbers and viewing call statuses. Key URLs include:

- `/` - Main dashboard
- `/phone-numbers/` - Phone number management
- `/phone-numbers/create/` - Add new phone numbers
- `/phone-numbers/<id>/` - View phone number details

## Development

To set up the development environment:

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run migrations:
```bash
python manage.py migrate
```

4. Start the development server:
```bash
python manage.py runserver
```

## Docker Deployment

The application is containerized and includes:

- Web service (Django)
- Celery worker for async tasks
- Celery beat for scheduled tasks
- Redis for message broker
- PostgreSQL database

Use `docker-compose up -d` to start all services.

## Testing RTP Packets with simple_caller.py

The `simple_caller.py` script provides detailed RTP packet logging functionality for testing and debugging purposes.

### Prerequisites

Ensure all required environment variables are set:
```bash
SIP_USER=your_sip_user
SIP_DOMAIN=your_sip_domain
SIP_AUTH_REALM=your_auth_realm
SIP_AUTH_USERNAME=your_auth_username
SIP_AUTH_PASSWORD=your_auth_password
```

### Running the Test Script

To run the test script with RTP logging:

```bash
# Rebuild and restart only the simple-caller service
docker-compose up --force-recreate simple-caller
```

This command will:
- Rebuild the simple-caller container with latest changes
- Start the script with proper environment variables
- Output logs to both console and sip_caller.log

### Log Information

The logs will contain:
- RTP transport details (local and remote addresses)
- RTP packet statistics (transmitted, received, lost)
- RTP stream creation and destruction events
- Quality metrics (jitter and other parameters)

### Real-time Log Monitoring

To monitor the logs in real-time:
```bash
tail -f sip_caller.log
```

Note: The `sip_caller.log` file is included in `.gitignore` and won't be tracked in the repository.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.
