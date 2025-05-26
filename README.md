# AGI Prompt System API

This is the REST API for the AGI Prompt System, built with FastAPI. It provides endpoints for generating and refining AGI system prompts with performance monitoring and internationalization support.

## Features

- **RESTful API** with OpenAPI/Swagger documentation
- **Asynchronous** task processing with Celery and Redis
- **Performance Monitoring** with Prometheus and OpenTelemetry
- **Internationalization** support for multiple languages
- **CORS** enabled for cross-origin requests
- **Rate Limiting** to prevent abuse
- **JWT Authentication** (optional)
- **File Uploads** with size and type validation
- **Comprehensive Logging**

## Prerequisites

- Python 3.8+
- Redis server (for caching and task queue)
- NVIDIA API key (for LLM access)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/agi-prompt-system.git
   cd agi-prompt-system
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy the example environment file and update with your settings:
   ```bash
   cp .env.example .env
   ```

5. Start Redis server:
   ```bash
   # On Linux/macOS
   redis-server
   
   # On Windows (if using WSL)
   wsl --exec redis-server
   ```

## Running the API

### Development Mode

For development with auto-reload:

```bash
uvicorn agi_prompt_system.api.main:app --reload
```

### Production Mode

For production, use a production ASGI server like Uvicorn with Gunicorn:

```bash
gunicorn -k uvicorn.workers.UvicornWorker -w 4 agi_prompt_system.api.main:app
```

### Running with Docker

Build and run using Docker Compose:

```bash
docker-compose up --build
```

## API Documentation

Once the server is running, you can access:

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI Schema**: http://localhost:8000/api/openapi.json

## Available Endpoints

### Health Check

```http
GET /api/health
```

### Generate Prompt

```http
POST /api/prompts/generate
Content-Type: application/json

{
  "requirements": "Create a prompt for a creative writing assistant",
  "max_iterations": 5,
  "temperature": 0.7
}
```

### Get Task Status

```http
GET /api/prompts/tasks/{task_id}
```

### Cache Statistics

```http
GET /api/cache/stats
```

### Clear Cache

```http
POST /api/cache/clear
```

## Environment Variables

See `.env.example` for a list of available environment variables.

## Testing

Run the test suite:

```bash
pytest tests/
```

## Monitoring

Metrics are available at:

```
http://localhost:8001/metrics
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
