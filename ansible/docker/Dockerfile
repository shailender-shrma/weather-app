FROM python:3.11-alpine

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory inside the container
WORKDIR /usr/src/metoffice_weather

# Install system dependencies for psycopg2 and other build tools
RUN apk update \
    && apk add --no-cache \
        postgresql-dev \
        gcc \
        python3-dev \
        musl-dev \
        libffi-dev \
        openssl-dev

# Upgrade pip
RUN pip install --upgrade pip

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy project files
COPY . .
RUN python manage.py collectstatic --noinput

# Run app using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "metoffice_weather.wsgi:application"]